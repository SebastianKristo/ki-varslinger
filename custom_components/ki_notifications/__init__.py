"""KI Notifications: local event routing to the Companion app."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import logging
import secrets
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval, async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.components.zone import in_zone
from .security import Security
from .door_blink import DoorBlink
from .extra_notifications import ExtraNotifications
from .const import DOMAIN, PEOPLE, INVALID, flags, SECURITY_KINDS
from .logic import alarm_event, presence_event, vacuum_actions, minutes, choose_departure

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SWITCH, Platform.BUTTON, Platform.SENSOR, Platform.NUMBER]

async def async_setup_entry(hass, entry):
    runtime = Runtime(hass, entry)
    await runtime.load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    try:
        runtime.security_register()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        runtime.listen()
    except Exception:
        runtime.close()
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        hass.data[DOMAIN].pop(entry.entry_id,None)
        raise
    entry.async_on_unload(entry.add_update_listener(reload_entry))
    return True

async def reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime = hass.data[DOMAIN].pop(entry.entry_id)
        runtime.close()
        await runtime.blink_finish()
        return True
    return False

async def async_remove_entry(hass, entry):
    await Store(hass, 1, f'{DOMAIN}.{entry.entry_id}').async_remove()

class Runtime(ExtraNotifications, Security, DoorBlink):
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        self.cfg = dict(entry.options or entry.data)
        self.kind = entry.data['kind']
        self.store = Store(hass, 1, f'{DOMAIN}.{entry.entry_id}')
        self.enabled = {k:self.kind not in SECURITY_KINDS for k in flags(self.kind)}
        self.master_enabled = True
        self.listeners, self.unsubs = set(), []
        self.lock = asyncio.Lock()
        self.closed = False
        self.last_message, self.last_error, self.last_sent = '', '', None
        self.active = False
        self.command_state = None
        self.reconcile_cancel = None
        self.token = secrets.token_hex(16)
        self.last_calendar = None
        self.last_ruter = None
        self.last_source_error = ''
        self.last_weather_date = None
        self.startup_cancel = None
        self.jam_cancel = None
        self.jam_generation = 0
        self.security_init()
        self.blink_init()

    async def load(self):
        saved = await self.store.async_load() or {}
        if not saved and self.kind == 'family':
            for person in PEOPLE:
                for key, old_key in [('home','kom_hjem'),('away','forlot_huset')]:
                    old = self.hass.states.get(f'input_boolean.posisjonsvarsel_{person}_{old_key}')
                    if old and old.state in {'on','off'}:
                        self.enabled[f'{person}_{key}'] = old.state == 'on'
        self.enabled.update({k:bool(v) for k,v in saved.get('enabled',{}).items() if k in self.enabled})
        self.master_enabled = bool(saved.get('master_enabled', True))
        self.last_weather_date = saved.get('last_weather_date')
        # Preserve number changes until the configured delay is explicitly changed.
        configured_delay = float(self.cfg.get('autolock_delay', 30))
        previous_delay = saved.get('autolock_config_delay', configured_delay)
        if previous_delay == configured_delay:
            self.autolock_seconds = saved.get('autolock_seconds', configured_delay)
        else:
            self.autolock_seconds = configured_delay
        self.last_unlock_person = saved.get('last_unlock_person')
        self.last_unlock_at = saved.get('last_unlock_at')
        if not saved or 'autolock_config_delay' not in saved or previous_delay != configured_delay:
            await self.save_settings()

    async def save_settings(self):
        await self.store.async_save({'enabled': self.enabled, 'master_enabled': self.master_enabled, 'last_weather_date': self.last_weather_date, 'autolock_seconds':self.autolock_seconds, 'autolock_config_delay':float(self.cfg.get('autolock_delay',30)), 'last_unlock_person':self.last_unlock_person, 'last_unlock_at':self.last_unlock_at})

    @callback
    def update(self):
        for fn in list(self.listeners):
            fn()

    async def toggle(self, key, value):
        if key == 'master':
            self.master_enabled = value
        else:
            self.enabled[key] = value
        if self.kind in SECURITY_KINDS:
            self.security_toggled()
            if self.kind == 'door_blink' and not value:
                await self.blink_finish()
        await self.save_settings()
        if self.kind == 'lock_jammed':
            self.arm_jam_timer()
        self.update()
        if self.kind == 'vacuum':
            self.token = secrets.token_hex(16)
            self.command_state = None
            state = self.hass.states.get(self.cfg['entity'])
            self.active = bool(value and state and state.state in {'cleaning','paused','returning'})
            if not value:
                await self.send('', 'clear_notification', tag=self.tag, quiet=True)
            elif self.active:
                await self.vacuum_notice(quiet=True)

    @property
    def tag(self):
        return f'ki_vacuum_{self.entry.entry_id}'

    def listen(self):
        c = self.cfg
        self.extra_listen()
        entities = [c[p] for p in PEOPLE] if self.kind == 'family' else ([c['entity']] if 'entity' in c else [])
        if self.kind == 'autolock':
            entities.append(c['door_entity'])
            if c.get('delay_helper'):
                entities.append(c['delay_helper'])
        if self.kind == 'door_blink':
            entities.append(c['door_entity'])
            self.unsubs.append(self.hass.bus.async_listen_once('homeassistant_stop', self.blink_finish))
        if self.kind == 'alarm_sync':
            entities.append(c['homey_select'])
        if self.kind == 'alarm' and c.get('triggered_sensor'):
            entities.append(c['triggered_sensor'])
        if self.kind == 'vacuum':
            entities += [c['room']] if c.get('room') else []
            entities += c.get('selected_rooms', [])
            self.unsubs.append(self.hass.bus.async_listen('mobile_app_notification_action', self.action))
            state = self.hass.states.get(c['entity'])
            self.active = bool(state and state.state in {'cleaning','paused','returning'})
        if self.kind == 'ruter':
            entities += c['trackers']
            self.unsubs.append(async_track_time_interval(self.hass, self.calendar_tick, timedelta(seconds=30)))
        if entities:
            self.unsubs.append(async_track_state_change_event(self.hass, entities, self.changed))

    def close(self):
        self.closed = True
        self.extra_close()
        self.security_close()
        self.blink_close()
        self.token = secrets.token_hex(16)
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()
        self.listeners.clear()
        if self.reconcile_cancel:
            self.reconcile_cancel()
            self.reconcile_cancel = None

    def inside(self, state):
        if state is None or state.state in INVALID:
            return False
        for zid in self.cfg.get('zones', []):
            zone = self.hass.states.get(zid)
            if zone is None:
                continue
            lat, lon = state.attributes.get('latitude'), state.attributes.get('longitude')
            if lat is not None and lon is not None:
                if in_zone(zone, lat, lon, state.attributes.get('gps_accuracy', 0)):
                    return True
            elif state.state == ('home' if zid == 'zone.home' else zone.name):
                return True
        return False

    async def changed(self, event):
        async with self.lock:
            if self.closed:
                return
            old, new = event.data.get('old_state'), event.data.get('new_state')
            if self.kind in SECURITY_KINDS:
                await self.security_changed(old, new, event.data.get('entity_id'))
                return
            if self.kind == 'lock_jammed':
                await self.jam_changed(old, new)
                return
            if old is None or new is None or old.state in INVALID or new.state in INVALID:
                return
            c = self.cfg
            if self.kind == 'vacuum':
                if not self.enabled['enabled']:
                    return
                if new.entity_id == c['entity']:
                    if old.state == new.state:
                        return
                    self.command_state = None
                    if new.state == 'cleaning' and not self.active:
                        self.active = True
                        self.token = secrets.token_hex(16)
                        await self.vacuum_notice('cleaning', quiet=False, started=True)
                    elif self.active:
                        await self.vacuum_notice(new.state, quiet=True)
                        if new.state in {'docked','off','error'}:
                            self.active = False
                            self.token = secrets.token_hex(16)
                elif self.active and old.state != new.state:
                    await self.vacuum_notice(quiet=True)
                return
            if self.kind == 'ruter':
                if self.enabled['enabled'] and self.inside(old) and not self.inside(new):
                    await self.ruter_notice()
                return
            if old.state == new.state:
                return
            if self.kind == 'family':
                p = next(p for p in PEOPLE if c[p] == new.entity_id)
                e = presence_event(old.state, new.state)
                if e and self.enabled[f'{p}_{e}']:
                    await self.family_notice(p,e)
            elif self.kind == 'alarm':
                if new.entity_id == c.get('triggered_sensor'):
                    e = 'triggered' if (old.state, new.state) == ('off', 'on') else None
                elif new.entity_id.startswith(('switch.', 'input_boolean.')):
                    e = {('off','on'):'armed', ('on','off'):'disarmed'}.get((old.state,new.state))
                else:
                    e = alarm_event(old.state, new.state)
                if e and self.enabled[e]:
                    await self.alarm_notice(e)
            elif self.kind == 'state':
                if self.enabled['enabled'] and old.state == c['from_state'] and new.state == c['to_state']:
                    if not c.get('zones') or self.inside(self.hass.states.get(c.get('zone_person'))):
                        await self.send(c['name'], c['message'], c['icon'])

    async def send(self, title, message, icon='mdi:bell-ring-outline', *, away=False, critical=False, tag=None, actions=None, quiet=False, test=False):
        if self.closed or (len(flags(self.kind)) > 1 and not self.master_enabled and not test):
            return
        c = self.cfg
        base = {'notification_icon':icon}
        if tag:
            base['tag'] = tag
        sound = c.get('sound_away' if away else 'sound', 'default') or 'default'
        async def one(target, ios):
            payload = deepcopy(base)
            if ios:
                payload['push'] = {'sound': 'none' if quiet else sound, 'interruption-level':'passive' if quiet else 'time-sensitive'}
                if critical and not test:
                    payload['push'] = {'sound':{'name':sound, 'critical':1, 'volume':1.0}, 'interruption-level':'critical'}
                if actions is not None:
                    payload['actions'] = actions
            else:
                payload.update({'channel': f"{c.get('channel','KI Varsler')} – {'stille oppdateringer' if quiet else 'avreise' if away else 'varsler'}", 'importance':'low' if quiet else 'high', 'priority':'high', 'ttl':0})
                if tag:
                    payload.update({'alert_once':True, 'sticky':bool(actions), 'persistent':bool(actions)})
                if actions is not None:
                    payload['actions'] = [{k:v for k,v in a.items() if k != 'icon'} for a in actions]
            try:
                await asyncio.wait_for(self.hass.services.async_call('notify', target, {'title':title, 'message':message, 'data':payload}, blocking=True), timeout=20)
                return None
            except Exception as err:
                _LOGGER.exception('Could not send KI notification to %s', target)
                return f'{target}: {err}'
        results = await asyncio.gather(*(one(t,True) for t in c.get('ios_targets',[])), *(one(t,False) for t in c.get('android_targets',[])))
        self.last_error = '; '.join(r for r in results if r)
        self.last_message = message
        if results and any(r is None for r in results):
            self.last_sent = dt_util.utcnow().isoformat()
        self.update()

    async def family_notice(self, p, event, test=False):
        name = 'Test' if test else PEOPLE[p]
        away = event == 'away'
        await self.send('🚶 Forlot huset' if away else '🏠 Kom hjem', f"{name} {'forlot huset' if away else 'kom hjem'}.", 'mdi:home-export-outline' if away else 'mdi:home-import-outline', away=away, test=test)

    async def alarm_notice(self, event, test=False):
        titles = {'armed':'🔒 Alarm aktivert', 'disarmed':'🔓 Alarm deaktivert', 'triggered':'🚨 Alarm utløst'}
        icons = {'armed':'mdi:shield-lock', 'disarmed':'mdi:shield-off-outline', 'triggered':'mdi:alarm-light'}
        await self.send(titles[event], ('TEST: ' if test else '') + titles[event][2:].strip() + '.', icons[event], critical=event == 'triggered' and self.cfg.get('critical',False), test=test)

    async def vacuum_notice(self, state=None, *, quiet=True, started=False, test=False):
        v = self.hass.states.get(self.cfg['entity'])
        state = state or self.command_state or (v.state if v else 'unavailable')
        labels = {'cleaning':'Støvsuger', 'paused':'Satt på pause', 'idle':'Stoppet', 'returning':'Returnerer hjem', 'docked':'Tilbake i ladestasjonen', 'error':'Støvsugeren melder feil', 'off':'Av', 'unavailable':'Utilgjengelig'}
        message = 'Har startet.' if started else labels.get(state,state)
        room = self.hass.states.get(self.cfg.get('room',''))
        if room and room.state not in INVALID and state in {'cleaning','paused'}:
            message += f' Rom: {room.state}.'
        rooms = [s.name for eid in self.cfg.get('selected_rooms',[]) if (s:=self.hass.states.get(eid)) and s.state == 'on']
        if rooms:
            message += ' Valgte rom: ' + ', '.join(rooms) + '.'
        actions = [] if test else [{'action':f'KI_{self.entry.entry_id}_{self.token}_{cmd}', 'title':name, 'icon':f'sfsymbols:{icon}'} for cmd,name,icon in vacuum_actions(state)]
        await self.send('🧹 ' + (v.name if v else self.cfg['name']), ('TEST: ' if test else '') + message, 'mdi:robot-vacuum', tag=None if test else self.tag, actions=actions, quiet=quiet, test=test)

    async def action(self, event):
        async with self.lock:
            if self.closed or not self.active or not self.enabled.get('enabled'):
                return
            prefix = f'KI_{self.entry.entry_id}_{self.token}_'
            action = event.data.get('action','')
            if not isinstance(action,str) or not action.startswith(prefix):
                return
            cmd = action[len(prefix):]
            v = self.hass.states.get(self.cfg['entity'])
            if v is None or cmd not in {x[0] for x in vacuum_actions(self.command_state or v.state)}:
                return
            try:
                await asyncio.wait_for(self.hass.services.async_call('vacuum', cmd, {'entity_id':self.cfg['entity']}, blocking=True), timeout=20)
            except Exception as err:
                self.last_error = f'vacuum.{cmd}: {err}'
                self.update()
                await self.send('🧹 Kommando mislyktes', 'Kunne ikke styre støvsugeren. Se KI-status i Home Assistant.')
                return
            # Update immediately after accepted command; real device updates reconcile it.
            expected = {'pause':'paused','start':'cleaning','stop':'idle','return_to_base':'returning'}[cmd]
            self.command_state = expected
            self.token = secrets.token_hex(16)
            await self.vacuum_notice(expected)
            if self.reconcile_cancel:
                self.reconcile_cancel()
            self.reconcile_cancel = async_call_later(self.hass, 10, self.reconcile)

    async def reconcile(self, now):
        async with self.lock:
            self.reconcile_cancel = None
            self.command_state = None
            if not self.closed and self.active and self.enabled['enabled']:
                await self.vacuum_notice(quiet=True)

    async def calendar_tick(self, now):
        async with self.lock:
            if self.closed or not self.enabled['enabled'] or not self.cfg.get('calendar'):
                return
            cal = self.hass.states.get(self.cfg['calendar'])
            if not cal or cal.state != 'on' or cal.attributes.get('all_day'):
                return
            end = dt_util.parse_datetime(str(cal.attributes.get('end_time','')))
            if end is None:
                return
            end = dt_util.as_utc(end)
            due = end - timedelta(minutes=self.cfg.get('before_end',5))
            if due <= now < min(end,due+timedelta(seconds=60)) and self.last_calendar != end.isoformat():
                if any(self.inside(self.hass.states.get(t)) for t in self.cfg['trackers']):
                    self.last_calendar = end.isoformat()
                    await self.ruter_notice()

    def departures(self, entities, directions=None):
        result=[]
        for eid in entities:
            s = self.hass.states.get(eid)
            if not s or s.state in INVALID:
                continue
            for nxt in (False,True):
                prefix = 'next_' if nxt else ''
                route = str(s.attributes.get(prefix+'route',''))
                if directions and not any(d in route.lower() for d in directions):
                    continue
                result.append({'due':minutes(s.attributes.get('next_due_in') if nxt else s.state), 'route':route or s.name, 'time':s.attributes.get(prefix+'due_at','ukjent'), 'station':s.name})
        return result

    async def ruter_notice(self, test=False):
        now = dt_util.utcnow()
        if not test and self.last_ruter and (now-self.last_ruter).total_seconds()<90:
            return
        self.last_ruter = now if not test else self.last_ruter
        c = self.cfg
        tram = choose_departure(self.departures(c['tram_sensors'],[x.strip().lower() for x in c['directions'].split(',') if x.strip()]), c['walk'])
        lines=[]
        if tram:
            lines.append(f"🚋 {tram['station']}: {tram['route']} kl. {tram['time']} (om {tram['due']:g} min).")
            # due is measured from now: walking must not be added twice.
            bus = choose_departure(self.departures(c['bus_sensors']), tram['due']+c['ride']+c['transfer'])
            lines.append(f"🚌 {bus['route']} kl. {bus['time']} (om {bus['due']:g} min)." if bus else '🚌 Ingen registrert bussavgang som rekker overgangen.')
        else:
            lines.append('🚋 Ingen registrert avgang i riktig retning som du rekker med valgt gangtid.')
        if c.get('metro'):
            metro = choose_departure(self.departures([c['metro']]), 0)
            if metro:
                lines.append(f"🚇 {metro['route']} kl. {metro['time']} (om {metro['due']:g} min). Ikke kontrollert som overgang.")
        await self.send('🚏 Neste avganger' + (' – TEST' if test else ''), '\n'.join(lines), 'mdi:bus-clock', test=test)

    async def test(self, key):
        if self.kind in SECURITY_KINDS:
            return
        async with self.lock:
            if self.kind == 'family':
                await self.family_notice('rune',key,True)
            elif self.kind == 'alarm':
                await self.alarm_notice(key,True)
            elif self.kind == 'vacuum':
                await self.vacuum_notice(quiet=False,test=True)
            elif self.kind == 'ruter':
                await self.ruter_notice(test=True)
            elif self.kind == 'weather_ai':
                await self.weather_notice(test=True)
            elif self.kind == 'ha_start':
                await self.startup_notice(test=True)
            elif self.kind == 'lock_jammed':
                await self.jam_notice(test=True)
            else:
                await self.send('🔔 Test – '+self.cfg['name'], self.cfg['message'], self.cfg['icon'], test=True)
