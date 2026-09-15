"""Visual door notification; never sends lock or alarm commands."""
import asyncio
from copy import deepcopy
from homeassistant.util import dt as dt_util
from homeassistant.components.light import LightEntityFeature
from .const import DOMAIN, INVALID


class DoorBlink:
    def blink_init(self):
        self.blink_unlocked_at = None
        self.blink_lock_was_locked = False
        self.blink_task = None
        self.blink_stop = asyncio.Event()
        self.blink_last_at = None

    def blink_close(self):
        self.blink_unlocked_at = None
        self.blink_lock_was_locked = False
        self.blink_stop.set()

    async def blink_finish(self, event=None):
        self.blink_close()
        if self.blink_task:
            await self.blink_task

    async def blink_changed(self, old, new, entity_id):
        if not self.enabled['enabled'] or self.closed:
            self.blink_unlocked_at = None
            self.blink_lock_was_locked = False
            self.update()
            return
        if not new or new.state in INVALID:
            self.blink_unlocked_at = None
            self.blink_lock_was_locked = False
            self.update()
            return
        if old and old.state == new.state:
            return
        if entity_id == self.cfg['entity']:
            if new.state == 'locked':
                self.blink_unlocked_at = None
                self.blink_lock_was_locked = True
            elif new.state == 'unlocking':
                self.blink_lock_was_locked = bool(old and old.state == 'locked')
            elif new.state == 'unlocked':
                known_unlock = self.blink_lock_was_locked or bool(old and old.state == 'locked')
                self.blink_lock_was_locked = False
                door = self.hass.states.get(self.cfg['door_entity'])
                self.blink_unlocked_at = self.hass.loop.time() if known_unlock and door and door.state == self.cfg['door_closed'] else None
            else:
                self.blink_unlocked_at = None
                self.blink_lock_was_locked = False
        elif entity_id == self.cfg['door_entity']:
            if new.state not in {self.cfg['door_open'], self.cfg['door_closed']}:
                self.blink_unlocked_at = None
            elif new.state == self.cfg['door_open']:
                unlocked_at = self.blink_unlocked_at
                self.blink_unlocked_at = None  # One opening per confirmed unlock.
                lock = self.hass.states.get(self.cfg['entity'])
                if (old and old.state == self.cfg['door_closed'] and unlocked_at is not None
                    and self.hass.loop.time() - unlocked_at <= self.cfg.get('unlock_window', 60)
                    and lock and lock.state == 'unlocked'):
                    self.blink_start()
        self.update()

    def blink_snapshots(self, entity_id, seen=None):
        """Snapshot leaf lights too, preserving different colors in a light group."""
        seen = seen if seen is not None else set()
        if entity_id in seen:
            return []
        seen.add(entity_id)
        state = self.hass.states.get(entity_id)
        if not state or state.state not in {'on', 'off'}:
            raise ValueError('Lyset er utilgjengelig.')
        members = state.attributes.get('entity_id')
        if isinstance(members, (list, tuple)) and members and all(isinstance(x, str) and x.startswith('light.') for x in members):
            return [s for member in members for s in self.blink_snapshots(member, seen)]
        return [state]

    def blink_start(self, *, test=False):
        if self.closed or (not self.enabled['enabled'] and not test):
            return
        if self.blink_task and not self.blink_task.done():
            if test: self.test_result('Lyset blinker allerede.')
            return
        self.blink_stop = asyncio.Event()
        self.blink_task = self.hass.async_create_task(self.blink_run(test=test), 'KI dørlys', eager_start=False)
        if test: self.test_result('Blinketest startet.')

    async def blink_light_call(self, action, data):
        state = self.hass.states.get(data['entity_id'])
        if state and state.attributes.get('supported_features', 0) & LightEntityFeature.TRANSITION:
            data = {**data, 'transition': 0}
        await asyncio.wait_for(self.hass.services.async_call('light', action, data, blocking=True), 10)

    async def blink_wait(self):
        try:
            await asyncio.wait_for(self.blink_stop.wait(), float(self.cfg.get('blink_interval', 0.5)))
        except TimeoutError:
            pass

    @staticmethod
    def blink_restore_data(state):
        data = {'entity_id': state.entity_id}
        if state.state == 'off':
            return 'turn_off', data
        attrs = state.attributes
        for key in ('brightness', 'effect'):
            if attrs.get(key) is not None:
                data[key] = deepcopy(attrs[key])
        mode = attrs.get('color_mode')
        key = {'hs':'hs_color', 'xy':'xy_color', 'rgb':'rgb_color', 'rgbw':'rgbw_color',
               'rgbww':'rgbww_color', 'color_temp':'color_temp_kelvin'}.get(mode)
        if key and attrs.get(key) is not None:
            data[key] = deepcopy(attrs[key])
        elif mode == 'color_temp' and attrs.get('color_temp'):
            data['color_temp_kelvin'] = round(1000000 / attrs['color_temp'])
        elif mode == 'white' and attrs.get('brightness') is not None:
            data['white'] = attrs['brightness']
        return 'turn_on', data

    async def blink_run(self, *, test=False):
        reserved = self.hass.data.setdefault(DOMAIN + '_blink_lights', set())
        snapshots = []
        owned = set()
        try:
            if self.blink_stop.is_set() or self.closed:
                return
            snapshots = self.blink_snapshots(self.cfg['blink_light'])
            targets = {state.entity_id for state in snapshots}
            if targets & reserved:
                self.security_error = 'Lyset blinker allerede fra et annet oppsett.'
                return
            reserved.update(targets)
            owned = targets
            self.security_error = ''
            self.update()
            initial = self.hass.states.get(self.cfg['blink_light']).state
            actions = ('turn_off', 'turn_on') if initial == 'on' else ('turn_on', 'turn_off')
            for _ in range(int(self.cfg.get('blink_count', 3))):
                for action in actions:
                    if self.blink_stop.is_set() or self.closed:
                        return
                    await self.blink_light_call(action, {'entity_id':self.cfg['blink_light']})
                    await self.blink_wait()
            self.blink_last_at = dt_util.utcnow().isoformat()
        except Exception as err:
            self.security_error = f'Blinking mislyktes ({type(err).__name__}).'
        finally:
            # Always send restoration, even if HA still reports an old light state.
            for state in snapshots if owned else []:
                try:
                    action, data = self.blink_restore_data(state)
                    await self.blink_light_call(action, data)
                except Exception as err:
                    self.security_error = f'Kunne ikke gjenopprette lyset ({type(err).__name__}).'
            reserved.difference_update(owned)
            self.blink_task = None
            if test:
                self.test_result(self.security_error or ('Blinketest avbrutt; gjenoppretting sendt.' if self.blink_stop.is_set() or self.closed else 'Blinketest fullført; gjenoppretting sendt.'))
            self.update()
