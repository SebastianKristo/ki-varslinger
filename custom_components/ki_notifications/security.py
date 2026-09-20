"""Door and alarm controls. Secrets stay in config entry data, never diagnostics."""
import asyncio
import math
from datetime import timedelta
from aiohttp import web
from homeassistant.components import webhook
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util
from .const import DOMAIN, PEOPLE, INVALID

class Security:
    def security_init(self):
        self.autolock_seconds = float(self.cfg.get('autolock_delay',30))
        self.door_closed_at = None
        self.auto_cancel = None
        self.auto_generation = 0
        self.autolock_deadline = None
        self.sync_expected = {}
        self.registered_hooks = []
        self.face_future = None
        self.face_last_attempt = None
        self.last_unlock_person = None
        self.last_unlock_at = None
        self.security_error = ''

    def security_register(self):
        if self.kind != 'face_unlock':
            return
        try:
            for person in PEOPLE:
                hook_id = self.cfg['webhook_'+person]
                async def handler(hass, webhook_id, request, person=person):
                    return await self.face_request(person, request)
                methods = ['POST','PUT','HEAD'] + (['GET'] if self.cfg.get('allow_get') else [])
                webhook.async_register(self.hass, DOMAIN, 'Ansiktsgjenkjenning – '+PEOPLE[person], hook_id, handler, local_only=True, allowed_methods=methods)
                self.registered_hooks.append(hook_id)
        except ValueError as err:
            self.security_close()
            raise ConfigEntryError('En webhook-ID er allerede registrert. Deaktiver gammel webhook-automasjon eller velg nye ID-er.') from err

    def security_close(self):
        self.cancel_autolock()
        self.clear_sync()
        for hook_id in self.registered_hooks:
            webhook.async_unregister(self.hass,hook_id)
        self.registered_hooks.clear()
        if self.face_future and not self.face_future.done():
            self.face_future.cancel()

    def cancel_autolock(self):
        self.auto_generation += 1
        self.autolock_deadline = None
        if self.auto_cancel:
            self.auto_cancel()
            self.auto_cancel = None

    def clear_sync(self):
        for expected, cancel in self.sync_expected.values():
            cancel()
        self.sync_expected.clear()

    def security_toggled(self):
        if not self.enabled['enabled']:
            self.cancel_autolock()
            self.door_closed_at = None
            self.clear_sync()
        # Enabling never locks, arms or disarms from an existing snapshot.

    async def set_autolock_delay(self, value):
        value = float(value)
        if not math.isfinite(value) or not 5 <= value <= 3600:
            raise ValueError('Ventetiden må være mellom 5 og 3600 sekunder.')
        self.autolock_seconds = value
        if self.door_closed_at is not None:
            self.schedule_autolock()
        await self.save_settings()
        self.update()

    def autolock_status(self):
        if not self.enabled['enabled']:
            return 'Av'
        door = self.hass.states.get(self.cfg['door_entity'])
        lock = self.hass.states.get(self.cfg['entity'])
        if not door or door.state in INVALID:
            return 'Dørsensor utilgjengelig'
        if door.state not in {self.cfg['door_open'], self.cfg['door_closed']}:
            return 'Kontroller dørverdier'
        if door.state == self.cfg['door_open']:
            return 'Døren er åpen'
        if lock and lock.state == 'locked':
            return 'Døren er låst'
        if not lock or lock.state in INVALID:
            return 'Lås utilgjengelig'
        if self.auto_cancel:
            return 'Venter på autolås'
        if lock.state == 'locking':
            return 'Låser'
        return 'Venter på åpning og lukking'

    def autolock_attributes(self):
        door = self.hass.states.get(self.cfg['door_entity'])
        lock = self.hass.states.get(self.cfg['entity'])
        helper = self.hass.states.get(self.cfg.get('delay_helper', 'input_number.ki_missing'))
        return {
            'dorsensor': self.cfg['door_entity'],
            'dorverdi': door.state if door else None,
            'forventet_apen': self.cfg['door_open'],
            'forventet_lukket': self.cfg['door_closed'],
            'las': self.cfg['entity'],
            'lasverdi': lock.state if lock else None,
            'ventetid_sekunder': helper.state if self.cfg.get('delay_helper') and helper else self.autolock_seconds if not self.cfg.get('delay_helper') else None,
            'ventetid_kilde': self.cfg.get('delay_helper') or 'Ventetid før autolås',
            'planlagt_lasing': self.autolock_deadline,
        }

    def test_result(self, message):
        self.last_test_result = message
        self.last_test_at = dt_util.utcnow().isoformat()
        self.update()

    async def test_autolock(self, *, start=False):
        if self.closed:
            return
        door = self.hass.states.get(self.cfg['door_entity'])
        lock = self.hass.states.get(self.cfg['entity'])
        if not door or door.state not in {self.cfg['door_open'], self.cfg['door_closed']}:
            self.test_result('Feil: dørverdien gjenkjennes ikke. Kontroller åpen/lukket i oppsettet.')
            return
        if not lock or lock.state not in {'locked', 'unlocked'}:
            self.test_result('Feil: låsen rapporterer ikke låst eller ulåst.')
            return
        delay = self.autolock_seconds
        if helper := self.cfg.get('delay_helper'):
            state = self.hass.states.get(helper)
            try:
                delay = float(state.state) if state else float('nan')
            except ValueError:
                delay = float('nan')
        if not math.isfinite(delay) or not 5 <= delay <= 3600:
            self.test_result('Feil: ventetiden må være 5–3600 sekunder.')
            return
        if not self.hass.services.has_service('lock', 'lock'):
            self.test_result('Feil: handlingen lock.lock er utilgjengelig.')
            return
        if not start:
            self.test_result('Sensorverdier gjenkjent. Ingen låsing utført. Autolås er ' + ('på.' if self.enabled['enabled'] else 'av.'))
            return
        if not self.enabled['enabled']:
            self.test_result('Test ikke startet: slå på Autolås først.')
            return
        if door.state != self.cfg['door_closed']:
            self.test_result('Test ikke startet: døren må være lukket.')
            return
        if lock.state == 'locked':
            self.test_result('Test ikke startet: døren er allerede låst.')
            return
        if self.auto_cancel:
            self.test_result('Autolås teller allerede ned. Eksisterende tidspunkt beholdes.')
            return
        self.door_closed_at = self.hass.loop.time()
        self.schedule_autolock()
        self.test_result(f'Nedtelling startet ({delay:g} sekunder). Se Sikkerhetsstatus og Låsen er låst for resultat.')

    def schedule_autolock(self):
        self.cancel_autolock()
        if self.closed or not self.enabled['enabled'] or self.door_closed_at is None:
            return
        door = self.hass.states.get(self.cfg['door_entity'])
        if not door or door.state != self.cfg['door_closed']:
            return
        delay = self.autolock_seconds
        if helper := self.cfg.get('delay_helper'):
            state = self.hass.states.get(helper)
            try:
                delay = float(state.state) if state else float('nan')
                if not math.isfinite(delay) or not 5 <= delay <= 3600:
                    raise ValueError
            except ValueError:
                self.security_error = 'Ventetid-helper må ha en gyldig verdi mellom 5 og 3600 sekunder.'
                self.update()
                return
        remaining = max(0, delay - (self.hass.loop.time()-self.door_closed_at))
        generation = self.auto_generation
        async def due(now):
            await self.autolock_due(generation)
        self.autolock_deadline = (dt_util.utcnow() + timedelta(seconds=remaining)).isoformat()
        self.security_error = ''
        self.auto_cancel = async_call_later(self.hass,remaining,due)
        self.update()

    async def autolock_due(self, generation):
        async with self.lock:
            if self.closed or not self.enabled['enabled'] or generation != self.auto_generation:
                return
            self.auto_cancel = None
            self.autolock_deadline = None
            self.door_closed_at = None
            self.update()
            door = self.hass.states.get(self.cfg['door_entity'])
            lock = self.hass.states.get(self.cfg['entity'])
            if not door or door.state != self.cfg['door_closed']:
                return
            if lock and lock.state == 'locked':
                return
            if not lock or lock.state != 'unlocked':
                self.security_error = 'Autolås avbrutt: låsen er ikke bekreftet ulåst.'
                self.update()
                return
            await self.security_call('lock','lock',self.cfg['entity'])

    async def security_call(self, domain, action, entity_id, **extra):
        data = {'entity_id':entity_id, **extra}
        if domain in {'lock','alarm_control_panel'} and self.cfg.get('security_code'):
            data['code'] = self.cfg['security_code']
        try:
            await asyncio.wait_for(self.hass.services.async_call(domain,action,data,blocking=True),20)
            self.security_error = ''
            self.update()
            return True
        except Exception as err:
            # Exception messages may contain service arguments. Never persist them.
            self.security_error = f'{domain}.{action} mislyktes ({type(err).__name__}).'
            self.update()
            return False

    async def security_changed(self, old, new, entity_id):
        if self.kind == 'door_blink':
            await self.blink_changed(old, new, entity_id)
            return
        if self.kind == 'autolock':
            if entity_id == self.cfg.get('delay_helper'):
                if self.door_closed_at is not None:
                    self.schedule_autolock()
                self.update()
                return
            if entity_id != self.cfg['door_entity']:
                self.update()
                return
            if not new or new.state != self.cfg['door_closed']:
                self.cancel_autolock()
                self.door_closed_at = None
            elif old and old.state == self.cfg['door_open'] and self.enabled['enabled']:
                self.door_closed_at = self.hass.loop.time()
                self.schedule_autolock()
            self.update()
            return
        if self.kind != 'alarm_sync' or not self.enabled['enabled']:
            return
        if old is None or new is None or old.state in INVALID or new.state in INVALID or old.state == new.state:
            return
        alarm_entity = self.cfg['entity']
        is_alarm = entity_id == alarm_entity
        if is_alarm:
            stable = new.state == 'disarmed' or new.state.startswith('armed_')
            if not stable:
                return
        elif new.state not in {self.cfg['homey_armed'],self.cfg['homey_disarmed']}:
            return
        pending = self.sync_expected.pop(entity_id,None)
        if pending:
            expected,cancel = pending
            cancel()
            if new.state != expected:
                self.clear_sync()
                self.security_error = 'Motstridende alarmtilstand. Synkronisering stoppet; kontroller begge systemer.'
                self.update()
                return
            self.security_error = ''
            self.update()
            if is_alarm:
                await self.sync_privacy(new.state)
            return
        if is_alarm:
            await self.sync_homey(new.state)
            sync_error = self.security_error
            await self.sync_privacy(new.state)
            if sync_error:
                self.security_error = sync_error
                self.update()
        else:
            await self.sync_alarm(new.state)

    def expect_sync(self, entity, expected):
        previous = self.sync_expected.pop(entity,None)
        if previous:
            previous[1]()
        async def expired(now):
            async with self.lock:
                if self.closed:
                    return
                if self.sync_expected.get(entity) is not record:
                    return
                current = self.sync_expected.pop(entity,None)
                if current:
                    state = self.hass.states.get(entity)
                    if not state or state.state != expected:
                        self.security_error = 'Alarmsynk ble ikke bekreftet innen ventetiden. Kontroller begge systemer.'
                        self.update()
        cancel = async_call_later(self.hass,self.cfg.get('sync_timeout',120),expired)
        record = (expected,cancel)
        self.sync_expected[entity] = record

    async def sync_alarm(self, value):
        target = self.hass.states.get(self.cfg['entity'])
        if not target or target.state in INVALID:
            self.security_error = 'Alarmo er utilgjengelig; ingen synkroniseringskommando sendt.'
            self.update()
            return
        disarm = value == self.cfg['homey_disarmed']
        expected = 'disarmed' if disarm else self.cfg['alarm_mode']
        if target.state == expected or (not disarm and target.state.startswith('armed_')):
            await self.sync_privacy(target.state)
            return
        self.expect_sync(target.entity_id,expected)
        action = 'alarm_disarm' if disarm else 'alarm_arm_'+expected.removeprefix('armed_')
        if not await self.security_call('alarm_control_panel',action,target.entity_id):
            self.clear_sync()

    async def sync_homey(self, value):
        target = self.hass.states.get(self.cfg['homey_select'])
        expected = self.cfg['homey_disarmed'] if value == 'disarmed' else self.cfg['homey_armed']
        if not target or target.state in INVALID or expected not in target.attributes.get('options',[]):
            self.security_error = 'Heimdall-valget er utilgjengelig eller mangler riktig alternativ.'
            self.update()
            return
        if target.state == expected:
            return
        self.expect_sync(target.entity_id,expected)
        if not await self.security_call('select','select_option',target.entity_id,option=expected):
            self.clear_sync()

    async def sync_privacy(self, value):
        targets = self.cfg.get('privacy_switches',[])
        if targets:
            await self.security_call('switch','turn_on' if value=='disarmed' else 'turn_off',targets)

    async def face_request(self, person, request):
        if request.method == 'HEAD':
            return web.Response(status=200)
        if request.method not in ({'POST','PUT','GET'} if self.cfg.get('allow_get') else {'POST','PUT'}):
            return web.Response(status=405)
        if self.closed or not self.enabled['enabled']:
            return web.Response(status=403,text='Funksjonen er av.')
        async with self.lock:
            if self.closed or not self.enabled['enabled']:
                return web.Response(status=403)
            now = self.hass.loop.time()
            if self.face_last_attempt is not None and now-self.face_last_attempt < self.cfg.get('face_cooldown',10):
                return web.Response(status=429,text='Vent før nytt forsøk.')
            target = self.hass.states.get(self.cfg['entity'])
            if not target or target.state not in {'locked','unlocked'}:
                return web.Response(status=409,text='Låsen har ingen bekreftet stabil tilstand.')
            if target.state == 'unlocked':
                return web.Response(status=200,text='Allerede ulåst; ingen ny opplåsing registrert.')
            self.face_last_attempt = now
            future = self.hass.loop.create_future()
            self.face_future = future
            @callback
            def confirmed(event):
                state = event.data.get('new_state')
                if state and state.state == 'unlocked' and not future.done():
                    future.set_result(True)
            unsubscribe = async_track_state_change_event(self.hass,[target.entity_id],confirmed)
            try:
                if not await self.security_call('lock','unlock',target.entity_id):
                    return web.Response(status=502,text='Opplåsingskommando feilet.')
                current = self.hass.states.get(target.entity_id)
                if current and current.state == 'unlocked' and not future.done():
                    future.set_result(True)
                await asyncio.wait_for(future,15)
                if self.closed:
                    return web.Response(status=503)
                self.last_unlock_person = PEOPLE[person]
                self.last_unlock_at = dt_util.utcnow().isoformat()
                await self.save_settings()
                self.update()
                return web.Response(status=200,text='Opplåsing bekreftet.')
            except TimeoutError:
                self.security_error = 'Opplåsing ble ikke bekreftet av låsen innen 15 sekunder.'
                self.update()
                return web.Response(status=504,text='Ingen bekreftelse fra låsen.')
            except asyncio.CancelledError:
                if self.closed:
                    return web.Response(status=503)
                raise
            finally:
                unsubscribe()
                self.face_future = None
