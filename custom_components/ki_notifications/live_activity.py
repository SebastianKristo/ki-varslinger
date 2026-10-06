"""Live Activities (iPhone) og Live Updates (Android).

En Live Activity er ett varsel som blir stående på låseskjermen og oppdateres, i
stedet for en rekke bannere. Companion-appen lager den av et vanlig varsel med
`live_update: true` og en `tag`; samme tag oppdaterer, `clear_notification` avslutter.
Telefoner som ikke støtter det, viser det samme som et vanlig varsel som byttes ut.

Motoren her er én avstemming: hver regel sier hva som *burde* stå på skjermen akkurat
nå (`live_desired`), og `live_sync` sammenligner med det som sist ble sendt og
starter, oppdaterer eller avslutter. Da trenger ingen regel å huske hvor den er i
forløpet, og en omstart eller et nytt oppsett finner tilbake av seg selv.

Tre ting iOS straffer, og som motoren derfor passer på:

* **Hyppige oppdateringer** strupes og droppes. Like innhold sendes aldri på nytt, og
  det går minst `live_interval` sekunder mellom to oppdateringer – den siste vinner.
* **Nedtellinger** sendes som et klokkeslett (`when`), så telefonen teller selv. En
  gjenstående tid som flytter seg under et minutt, sendes ikke på nytt.
* **Start og stopp** har et eget, lite budsjett. En aktivitet avsluttes derfor ikke
  for å startes på nytt, bortsett fra når tittelen må byttes (iOS låser den ved start).
"""
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

import asyncio

from .const import (ANDROID_CHIP, INVALID, LIVE_COLORS, LIVE_INTERVAL, LIVE_KINDS, LIVE_LINGER,
                    LIVE_MAX_SECONDS, LIVE_OPTION_KINDS, LIVE_WHEN_TOLERANCE)
from .logic import chip_text, end_timestamp, number, states_set

VACUUM_LABELS = {'cleaning': 'Støvsuger', 'paused': 'Satt på pause', 'idle': 'Stoppet',
                 'returning': 'Returnerer hjem', 'docked': 'Tilbake i ladestasjonen',
                 'error': 'Støvsugeren melder feil', 'off': 'Av', 'unavailable': 'Utilgjengelig'}
SOURCE_KINDS = {'live_ev', 'live_appliance', 'live_pool', 'live_progress'}
AUTOLOCK_MIN_SECONDS = 60   # kortere ventetid enn dette er over før aktiviteten rekker å vises


class LiveActivity:
    # ---- tilstand -------------------------------------------------------
    def live_init(self):
        self.live_lock = asyncio.Lock()
        self.live_active = False        # står det en aktivitet på telefonen nå?
        self.live_orphan = False        # sto det en da HA ble stoppet eller oppsettet lastet på nytt?
        self.live_payload = None        # det som sist ble sendt
        self.live_sent_at = None        # monotonisk tid for siste sending
        self.live_lingering = False     # «ferdig» står og venter på å bli fjernet
        self.live_suppressed = False    # 8-timersgrensen er nådd for dette forløpet
        self.live_timers = {}
        self.live_count = 0             # antall sendinger, til statusentiteten
        self.ruter_live = None
        self.state_live = False
        self.autolock_live_ok = False

    @property
    def live_on(self):
        return self.kind in LIVE_KINDS or (self.kind in LIVE_OPTION_KINDS and bool(self.cfg.get('live_activity')))

    @property
    def live_tag(self):
        return f'ki_live_{self.entry.entry_id}'

    def live_close(self):
        for cancel in self.live_timers.values():
            cancel()
        self.live_timers.clear()

    def live_allowed(self):
        return self.live_on and self.master_enabled and self.enabled.get('enabled', True)

    # ---- tidsur ---------------------------------------------------------
    def live_timer(self, name, seconds=None):
        """Ett tidsur per navn. Uten sekunder avbrytes det bare."""
        cancel = self.live_timers.pop(name, None)
        if cancel:
            cancel()
        if seconds is None or self.closed:
            return
        async def due(now):
            self.live_timers.pop(name, None)
            if name == 'test':
                await self.live_clear_tag(self.live_tag + '_test')
            else:
                await self.live_sync(name)
        self.live_timers[name] = async_call_later(self.hass, max(1, seconds), due)

    def live_wake(self, seconds):
        """Regelen ber om å bli spurt igjen – f.eks. når en dør har stått åpen lenge nok."""
        self.live_timer('wake', seconds)

    def live_refresh(self):
        """Fra synkron kode: avstem så snart løkka er ledig."""
        if not self.closed and (self.live_on or self.live_active or self.live_orphan):
            self.hass.async_create_task(self.live_sync())

    # ---- avstemming -----------------------------------------------------
    async def live_sync(self, reason=None):
        if not (self.live_on or self.live_active or self.live_orphan):
            return
        async with self.live_lock:
            if self.closed:
                return
            now = dt_util.utcnow().timestamp()
            if reason == 'expire' and self.live_active:
                # iOS avslutter selv etter åtte timer. Fjern den ryddig like før, og la
                # den være borte til forløpet er over – ellers startes den straks igjen.
                await self._live_clear()
                self.live_suppressed = True
                return
            desired = self.live_desired(now) if self.live_allowed() else None
            if desired is None:
                self.live_suppressed = False
                if not self.live_active:
                    if self.live_orphan:
                        await self._live_clear()
                    return
                if self.live_lingering:
                    if reason == 'linger':
                        await self._live_clear()
                    return
                final = self.live_done(now) if self.live_allowed() and self.live_payload else None
                linger = float(self.cfg.get('live_linger', LIVE_LINGER))
                if final and linger > 0:
                    last = {k: v for k, v in self.live_payload.items() if k not in ('when', 'critical_text')}
                    alert = final.pop('alert', False)
                    await self._live_push(self._live_normalise({**last, **final}), alert=alert)
                    self.live_lingering = True
                    self.live_timer('throttle')
                    self.live_timer('linger', linger)
                else:
                    await self._live_clear()
                return
            if self.live_suppressed:
                return
            desired = self._live_normalise(desired)
            if self.live_active and self.live_payload and desired['title'] != self.live_payload['title']:
                await self._live_clear()
            if not self.live_active:
                # Etter omstart eller nytt oppsett står aktiviteten kanskje fortsatt på
                # telefonen: da er dette en stille oppdatering, ikke en ny start med lyd.
                await self._live_push(desired, start=not self.live_orphan)
                return
            if self.live_lingering:
                # Et nytt forløp mens «ferdig» står: bruk aktiviteten om igjen, straks.
                self.live_lingering = False
                self.live_timer('linger')
                await self._live_push(desired)
                return
            if desired == self.live_payload:
                return
            interval = float(self.cfg.get('live_interval', LIVE_INTERVAL))
            wait = interval - (self.hass.loop.time() - self.live_sent_at) if self.live_sent_at is not None else 0
            if wait > 0:
                if 'throttle' not in self.live_timers:
                    self.live_timer('throttle', wait)
                return
            await self._live_push(desired)

    def _live_normalise(self, payload):
        out = {k: v for k, v in payload.items() if v is not None}
        for key in ('progress', 'progress_max'):
            if key in out:
                out[key] = int(round(out[key]))
        if 'progress' in out and not out.get('progress_max'):
            out.pop('progress')
            out.pop('progress_max', None)
        if 'when' in out:
            out['when'] = int(round(out['when']))
            previous = (self.live_payload or {}).get('when')
            if previous is not None and abs(previous - out['when']) < LIVE_WHEN_TOLERANCE:
                out['when'] = previous
        out.setdefault('icon', self._live_default(0, 'mdi:bell-ring-outline'))
        out['title'] = str(out.get('title') or self.cfg['name'])
        out['message'] = str(out.get('message') or '')
        return out

    def _live_default(self, index, fallback):
        return LIVE_KINDS[self.kind][index] if self.kind in LIVE_KINDS else fallback

    async def _live_push(self, payload, *, start=False, alert=False, tag=None, test=False):
        c = self.cfg
        data = {'live_update': True}
        for key in ('progress', 'progress_max', 'critical_text'):
            if key in payload:
                data[key] = payload[key]
        if 'when' in payload:
            data.update({'chronometer': True, 'when': payload['when'], 'when_relative': False})
        color = payload.get('color') or c.get('live_color') or self._live_default(1, LIVE_COLORS.get(self.kind, '#03A9F4'))
        data.update({'notification_icon_color': color, 'color': color})
        if c.get('live_url'):
            data['url'] = c['live_url']
        priority = payload.get('relevance', c.get('live_priority', self._live_default(2, 0.5)))
        data['relevance_score'] = max(0.0, min(1.0, float(priority)))
        loud = start or alert
        await self.send(
            payload['title'], payload['message'], payload['icon'], tag=tag or self.live_tag,
            quiet=not loud, extra=data, test=test, force=True,
            ios_extra=None if loud else {'silent': True},
            android_extra=self._live_android(payload, alert))
        if tag:
            return
        # Android teller videre under null. Når nedtellingen er ute, spørres regelen på nytt,
        # så klokka fjernes eller flyttes i stedet for å vise minustid.
        left = payload.get('when', 0) - dt_util.utcnow().timestamp()
        self.live_timer('zero', left + 1 if left > 0 else None)
        was_known = self.live_active or self.live_orphan
        self.live_active, self.live_orphan = True, False
        self.live_payload = payload
        self.live_sent_at = self.hass.loop.time()
        self.live_count += 1
        if not was_known or 'expire' not in self.live_timers:
            self.live_timer('expire', LIVE_MAX_SECONDS)
        if not was_known:
            await self.save_settings()
        self.update()

    def _live_android(self, payload, alert):
        """Live Update på Android 16 (Now Bar og statuslinjebrikke på Samsung med One UI 8).

        Eldre Android-telefoner viser det samme som et vanlig varsel med fremdriftslinje
        og klokke. «persistent» gjør at det ikke sveipes bort ved et uhell mens det pågår;
        det fjernes uansett når forløpet er over.
        """
        c = self.cfg
        # Samme kanal for start og oppdatering; alert_once holder oppdateringene stille.
        out = {'channel': f"{c.get('channel', 'KI Varsler')} – live", 'importance': 'high', 'sticky': True,
               'persistent': bool(c.get('live_android_persistent', True)), 'alert_once': not alert}
        chip = payload.get('critical_text')
        if not chip and 'when' not in payload and payload.get('progress_max'):
            chip = f"{round(100 * payload['progress'] / payload['progress_max'])}%"
        if chip:
            out['critical_text'] = chip_text(chip, ANDROID_CHIP)
        return out

    async def live_clear_tag(self, tag):
        message = self.last_message
        await self.send('', 'clear_notification', tag=tag, quiet=True, force=True)
        self.last_message = message

    async def _live_clear(self):
        for name in ('throttle', 'linger', 'expire', 'zero'):
            self.live_timer(name)
        await self.live_clear_tag(self.live_tag)
        self.live_active = self.live_orphan = self.live_lingering = False
        self.live_payload = None
        await self.save_settings()
        self.update()

    async def live_test(self):
        """Viser en eksempelaktivitet i ett minutt, under egen tag, uten å røre den ekte."""
        now = dt_util.utcnow().timestamp()
        payload = self._live_normalise({'title': 'Test – ' + self.cfg['name'], 'message': 'Slik ser aktiviteten ut',
                                        'icon': self.cfg.get('icon') or None, 'progress': 40, 'progress_max': 100,
                                        'when': now + 60})
        payload['when'] = int(now + 60)
        await self._live_push(payload, start=True, tag=self.live_tag + '_test', test=True)
        self.live_timer('test', 60)

    # ---- hva burde stå på skjermen? -------------------------------------
    def live_state(self, key):
        entity_id = self.cfg.get(key)
        state = self.hass.states.get(entity_id) if entity_id else None
        return state if state and state.state not in INVALID else None

    def live_metrics(self, now):
        """Fremdrift og nedtelling fra de valgfrie kildene i oppsettet."""
        out = {}
        source = self.live_state('progress_entity')
        value = number(source.state) if source else None
        if value is not None:
            limit = self.live_state('limit_entity')
            top = (number(limit.state) if limit else None) or number(self.cfg.get('progress_max')) or 100
            unit = source.attributes.get('unit_of_measurement') or ('%' if top == 100 else '')
            out.update({'progress': max(0, min(value, top)), 'progress_max': top,
                        'critical_text': f'{value:g}{" " if len(unit) > 1 else ""}{unit}'})
        remaining = self.live_state('remaining_entity')
        if remaining:
            out['when'] = end_timestamp(remaining.state, remaining.attributes.get('unit_of_measurement'),
                                        remaining.attributes.get('device_class'), now, dt_util.parse_datetime)
        return out

    def live_desired(self, now):
        handler = getattr(self, 'desired_source' if self.kind in SOURCE_KINDS else 'desired_' + self.kind, None)
        return handler(now) if handler else None

    def live_done(self, now):
        """Det siste som vises før aktiviteten fjernes, eller None for å fjerne den straks."""
        if self.kind in SOURCE_KINDS:
            final = {'message': LIVE_KINDS[self.kind][5], 'alert': True}
            if self.kind != 'live_ev' and 'progress_max' in self.live_payload:
                final['progress'] = self.live_payload['progress_max']
            return final
        if self.kind == 'vacuum':
            state = self.hass.states.get(self.cfg['entity'])
            return {'message': VACUUM_LABELS.get(state.state, state.state) if state else 'Ferdig'}
        if self.kind == 'autolock':
            lock = self.hass.states.get(self.cfg['entity'])
            return {'message': 'Døra er låst', 'icon': 'mdi:lock'} if lock and lock.state == 'locked' else None
        if self.kind == 'lock_jammed':
            return {'message': 'Låsen er i orden igjen', 'icon': 'mdi:lock-check'}
        return None

    def desired_source(self, now):
        """Elbil, hvitevare, basseng og egen fremdrift: «pågår» + valgfri fremdrift og tid."""
        c = self.cfg
        source = self.live_state('entity')
        defaults = LIVE_KINDS[self.kind]
        if not source or source.state.lower() not in states_set(c.get('active_states'), defaults[3]):
            return None
        out = {'title': c['name'], 'icon': c.get('icon') or defaults[0], **self.live_metrics(now)}
        phase = self.live_state('phase_entity')
        message = phase.state if phase else defaults[4]
        if self.kind == 'live_ev' and 'progress' in out:
            message = f"Lader · {out['progress']:g} % av {out['progress_max']:g} %"
        if self.kind == 'live_progress' and c.get('message'):
            message = (c['message'].replace('{state}', source.state)
                       .replace('{phase}', phase.state if phase else '')
                       .replace('{progress}', out.get('critical_text', '')))
        if self.kind == 'live_pool':
            if out.get('when') is None and number(c.get('duration')):
                end = source.last_changed.timestamp() + float(c['duration']) * 60
                out['when'] = end if end > now else None
            temperature = self.live_state('temp_entity')
            if temperature:
                message += f" · {temperature.state} {temperature.attributes.get('unit_of_measurement') or '°C'}"
        out['message'] = message
        return out

    def desired_live_open(self, now):
        c = self.cfg
        delay = float(c.get('open_delay', 120))
        wanted = states_set(c.get('open_states'), LIVE_KINDS['live_open'][3])
        opened, soonest = [], None
        for entity_id in c.get('entities', []):
            state = self.hass.states.get(entity_id)
            if not state or state.state.lower() not in wanted:
                continue
            since = state.last_changed.timestamp()
            if now - since >= delay:
                opened.append((since, state.name))
            else:
                # En dør som åpnes og lukkes igjen skal ikke bruke av startbudsjettet.
                soonest = min(soonest or 1e12, since + delay - now)
        if soonest is not None:
            self.live_wake(soonest)
        if not opened:
            return None
        opened.sort()
        names = ', '.join(name for _, name in opened)
        one = len(opened) == 1
        return {'title': c['name'], 'icon': c.get('icon') or LIVE_KINDS['live_open'][0],
                'message': names if one else f'{len(opened)} åpne: {names}',
                'critical_text': names[:14] if one else f'{len(opened)} åpne',
                'when': opened[0][0]}

    def desired_live_timer(self, now):
        c = self.cfg
        timer = self.live_state('entity')
        if not timer:
            return None
        out = {'title': c['name'], 'icon': c.get('icon') or LIVE_KINDS['live_timer'][0]}
        if timer.state == 'active':
            end = dt_util.parse_datetime(str(timer.attributes.get('finishes_at', '')))
            if end is None or end.timestamp() <= now:
                return None
            return {**out, 'message': 'Nedtelling', 'when': end.timestamp()}
        if timer.state == 'paused':
            left = timer.attributes.get('remaining')
            return {**out, 'message': f'Satt på pause · {left} igjen' if left else 'Satt på pause', 'critical_text': 'Pause'}
        return None

    def desired_vacuum(self, now):
        if not self.active:
            return None
        vacuum = self.hass.states.get(self.cfg['entity'])
        state = self.command_state or (vacuum.state if vacuum else 'unavailable')
        return {'title': '🧹 ' + (vacuum.name if vacuum else self.cfg['name']), 'icon': 'mdi:robot-vacuum',
                'message': self.vacuum_text(state), **self.live_metrics(now)}

    def desired_alarm(self, now):
        panel = self.live_state('entity')
        if not panel or not panel.entity_id.startswith('alarm_control_panel.'):
            return None
        phases = {'arming': ('armed', '🔒 Alarmen aktiveres', 'Forlat huset', '#FF9800', 0.9, 'mdi:shield-lock'),
                  'pending': ('triggered', '🚨 Slå av alarmen', 'Inngangstid', '#F44336', 1.0, 'mdi:shield-alert'),
                  'triggered': ('triggered', '🚨 Alarm utløst', 'Alarmen er utløst', '#F44336', 1.0, 'mdi:alarm-light')}
        phase = phases.get(panel.state)
        if not phase or not self.enabled[phase[0]]:
            return None
        out = {'title': phase[1], 'message': phase[2], 'color': phase[3], 'relevance': phase[4], 'icon': phase[5]}
        # Alarmo oppgir forsinkelsen i sekunder mens den teller; uten den vises bare teksten.
        delay = number(panel.attributes.get('delay'))
        if panel.state != 'triggered' and delay:
            end = panel.last_changed.timestamp() + delay
            out['when'] = end if end > now else None
        return out

    def desired_ruter(self, now):
        live = self.ruter_live
        if not live or now >= live['until']:
            self.ruter_live = None
            return None
        self.live_wake(live['until'] - now)
        gone = now >= live['when']
        return {'title': live['title'], 'message': 'Har gått nå' if gone else live['message'], 'icon': 'mdi:bus-clock',
                'critical_text': 'Gått' if gone else live['time'], 'when': None if gone else live['when'], 'relevance': 0.8}

    def desired_autolock(self, now):
        if not self.auto_cancel or not self.autolock_deadline or not self.autolock_live_ok:
            return None
        end = dt_util.parse_datetime(self.autolock_deadline)
        if end is None or end.timestamp() <= now:
            return None
        return {'title': '🔒 Låser døra', 'message': 'Låses automatisk når tiden er ute',
                'icon': 'mdi:timer-lock-outline', 'when': end.timestamp(), 'relevance': 0.8}

    def desired_lock_jammed(self, now):
        lock = self.live_state('entity')
        if not lock or lock.state != 'jammed':
            return None
        since = lock.last_changed.timestamp()
        wait = since + float(self.cfg.get('jam_seconds', 60)) - now
        if wait > 0:
            self.live_wake(wait)
            return None
        return {'title': '🔒 Dørlås fastkjørt', 'message': 'Låsen får ikke låst seg', 'icon': 'mdi:lock-alert',
                'when': since, 'relevance': 0.9}

    def desired_state(self, now):
        c = self.cfg
        source = self.live_state('entity')
        if not self.state_live or not source or source.state != c['to_state']:
            self.state_live = False
            return None
        return {'title': c['name'], 'message': c['message'], 'icon': c['icon'], **self.live_metrics(now)}
