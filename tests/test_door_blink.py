import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from homeassistant.core import HomeAssistant, State, CoreState
from custom_components.ki_notifications import Runtime


class DoorBlinkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.tmp.name)
        self.calls = []
        self.runtimes = []
        async def light_service(call):
            self.calls.append((call.service, dict(call.data)))
            eid = call.data['entity_id']
            old = self.hass.states.get(eid)
            self.hass.states.async_set(eid, 'on' if call.service == 'turn_on' else 'off', dict(old.attributes) if old else {})
        for action in ['turn_on', 'turn_off']:
            self.hass.services.async_register('light', action, light_service)
        self.hass.states.async_set('lock.front', 'locked')
        self.hass.states.async_set('sensor.door', 'closed')
        self.hass.states.async_set('light.pultskjermer', 'on', {'color_mode':'rgb', 'rgb_color':(12,34,56), 'brightness':81})

    async def asyncTearDown(self):
        for r in self.runtimes:
            r.close()
            await r.blink_finish()
        await self.hass.async_block_till_done()
        self.tmp.cleanup()

    def runtime(self):
        data = dict(kind='door_blink', name='Dørlys', entity='lock.front', door_entity='sensor.door', door_open='open', door_closed='closed', blink_light='light.pultskjermer', blink_count=3, blink_interval=0.5, unlock_window=60)
        r = Runtime(self.hass, SimpleNamespace(entry_id='blink'+str(len(self.runtimes)), data=data, options={}))
        self.runtimes.append(r)
        r.blink_wait = AsyncMock()
        return r

    async def change(self, r, eid, new):
        old = self.hass.states.get(eid)
        self.hass.states.async_set(eid, new)
        await r.blink_changed(old, self.hass.states.get(eid), eid)

    async def unlock_open(self, r):
        await self.change(r, 'lock.front', 'unlocked')
        await self.change(r, 'sensor.door', 'open')
        if r.blink_task:
            await r.blink_task

    async def test_unlock_then_open_blinks_three_times_and_restores_rgb(self):
        r = self.runtime()
        await r.toggle('enabled', True)
        await self.unlock_open(r)
        self.assertEqual([s for s,d in self.calls], ['turn_off','turn_on']*3+['turn_on'])
        self.assertEqual(self.calls[-1][1], {'entity_id':'light.pultskjermer','brightness':81,'rgb_color':(12,34,56)})
        self.assertIsNotNone(r.blink_last_at)
        await self.change(r, 'sensor.door', 'closed')
        await self.change(r, 'sensor.door', 'open')
        self.assertEqual(len(self.calls), 7)

    async def test_previously_off_light_returns_off(self):
        r = self.runtime()
        self.hass.states.async_set('light.pultskjermer','off')
        await r.toggle('enabled', True)
        await self.unlock_open(r)
        self.assertEqual([s for s,d in self.calls], ['turn_on','turn_off']*3+['turn_off'])
        self.assertEqual(self.hass.states.get('light.pultskjermer').state, 'off')

    async def test_no_blink_when_disabled_or_without_unlock(self):
        r = self.runtime()
        await self.unlock_open(r)
        self.assertFalse(self.calls)
        await r.toggle('enabled', True)
        await self.change(r, 'sensor.door', 'closed')
        await self.change(r, 'sensor.door', 'open')
        self.assertFalse(self.calls)

    async def test_expired_unlock_and_relock_do_not_blink(self):
        r = self.runtime()
        await r.toggle('enabled', True)
        await self.change(r, 'lock.front', 'unlocked')
        r.blink_unlocked_at -= 61
        await self.change(r, 'sensor.door', 'open')
        self.assertFalse(self.calls)
        await self.change(r, 'sensor.door', 'closed')
        await self.change(r, 'lock.front', 'locked')
        await self.change(r, 'lock.front', 'unlocked')
        await self.change(r, 'lock.front', 'locked')
        await self.change(r, 'sensor.door', 'open')
        self.assertFalse(self.calls)

    async def test_unlocking_intermediate_is_supported(self):
        r = self.runtime()
        await r.toggle('enabled', True)
        await self.change(r, 'lock.front', 'unlocking')
        await self.unlock_open(r)
        self.assertEqual(len(self.calls),7)

    async def test_unavailable_recovery_does_not_count_as_unlock(self):
        r = self.runtime()
        await r.toggle('enabled', True)
        await self.change(r, 'lock.front', 'unavailable')
        await self.unlock_open(r)
        self.assertFalse(self.calls)

    async def test_unknown_door_after_unlock_invalidates_sequence(self):
        r = self.runtime()
        await r.toggle('enabled', True)
        await self.change(r, 'lock.front', 'unlocked')
        await self.change(r, 'sensor.door', 'unavailable')
        await self.change(r, 'sensor.door', 'closed')
        await self.change(r, 'sensor.door', 'open')
        self.assertFalse(self.calls)

    async def test_disable_during_blink_restores_before_return(self):
        r = self.runtime()
        began = asyncio.Event()
        async def wait():
            began.set()
            await r.blink_stop.wait()
        r.blink_wait = wait
        await r.toggle('enabled', True)
        await self.change(r, 'lock.front', 'unlocked')
        await self.change(r, 'sensor.door', 'open')
        await began.wait()
        await r.toggle('enabled', False)
        self.assertEqual([s for s,d in self.calls], ['turn_off','turn_on'])
        self.assertEqual(self.calls[-1][1]['brightness'],81)
        self.assertIsNone(r.blink_task)

    async def test_close_during_blink_restores_and_releases_light(self):
        r = self.runtime()
        began = asyncio.Event()
        async def wait():
            began.set()
            await r.blink_stop.wait()
        r.blink_wait = wait
        await r.toggle('enabled', True)
        r.blink_start()
        await began.wait()
        r.close()
        await r.blink_finish()
        self.assertEqual(self.calls[-1][0], 'turn_on')
        self.assertFalse(self.hass.data['ki_notifications_blink_lights'])

    async def test_service_failure_still_restores_light(self):
        r = self.runtime()
        async def fail(call):
            raise ValueError('simulated')
        self.hass.services.async_register('light','turn_off',fail)
        await r.toggle('enabled', True)
        await self.unlock_open(r)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][0], 'turn_on')
        self.assertIn('mislyktes',r.security_error)

    async def test_light_group_restores_each_member(self):
        r = self.runtime()
        self.hass.states.async_set('light.pultskjermer','on',{'entity_id':['light.left','light.right']})
        self.hass.states.async_set('light.left','off')
        self.hass.states.async_set('light.right','on',{'brightness':120,'color_mode':'color_temp','color_temp_kelvin':2700})
        await r.toggle('enabled', True)
        await self.unlock_open(r)
        self.assertEqual(self.calls[-2],('turn_off',{'entity_id':'light.left'}))
        self.assertEqual(self.calls[-1],('turn_on',{'entity_id':'light.right','brightness':120,'color_temp_kelvin':2700}))

    async def test_conflicting_blink_is_skipped(self):
        r = self.runtime()
        self.hass.data['ki_notifications_blink_lights'] = {'light.pultskjermer'}
        await r.toggle('enabled', True)
        await self.unlock_open(r)
        self.assertFalse(self.calls)
        self.assertIn('allerede',r.security_error)
        self.assertEqual(self.hass.data['ki_notifications_blink_lights'],{'light.pultskjermer'})

    async def test_real_state_listeners_start_blink_and_zero_transition(self):
        r = self.runtime()
        self.hass.set_state(CoreState.running)
        self.hass.states.async_set('light.pultskjermer', 'on', {'supported_features':32})
        await r.toggle('enabled', True)
        r.listen()
        self.hass.states.async_set('lock.front', 'unlocked')
        await self.hass.async_block_till_done()
        self.hass.states.async_set('sensor.door', 'open')
        await self.hass.async_block_till_done()
        self.assertEqual(len(self.calls), 7)
        self.assertTrue(all(data['transition'] == 0 for action, data in self.calls))

    async def test_blink_button_runs_while_automatic_function_disabled(self):
        r = self.runtime()
        self.assertFalse(r.enabled['enabled'])
        await r.test('blink')
        await r.blink_task
        self.assertEqual(len(self.calls), 7)
        self.assertIn('fullført', r.last_test_result)
        self.assertFalse(r.enabled['enabled'])

    async def test_blink_test_reports_unavailable_light(self):
        r = self.runtime()
        self.hass.states.async_set('light.pultskjermer', 'unavailable')
        await r.test('blink')
        await r.blink_task
        self.assertFalse(self.calls)
        self.assertIn('mislyktes', r.last_test_result)

    async def test_disabled_blink_still_updates_reading_sensors(self):
        r = self.runtime()
        updates = []
        r.listeners.add(lambda: updates.append(True))
        await self.change(r, 'sensor.door', 'open')
        self.assertTrue(updates)
        self.assertFalse(self.calls)
