"""Dørvarsel med kamerabilde.

Notify-tjenesten er simulert: testene sjekker hva som ville blitt sendt til telefonen –
tittel, tekst, bilde og tag – ikke at en telefon faktisk mottar det.
"""
import os
import tempfile
import unittest
from types import SimpleNamespace

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import selector

from custom_components.ki_notifications import Runtime
from custom_components.ki_notifications.config_flow import errors, schema
from custom_components.ki_notifications.const import flags


class DoorCamera(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.tmp.name)
        self.sent = []
        self.runtimes = []

        async def notify(call):
            self.sent.append(dict(call.data))

        self.hass.services.async_register('notify', 'mobile_app_iphone', notify)
        self.hass.services.async_register('notify', 'mobile_app_pixel', notify)

    async def asyncTearDown(self):
        for r in self.runtimes:
            r.close()
        await self.hass.async_block_till_done()
        self.tmp.cleanup()

    def runtime(self, **cfg):
        base = {'kind': 'door_camera', 'name': 'Inngangsdør', 'ios_targets': ['mobile_app_iphone'],
                'android_targets': ['mobile_app_pixel'], 'sound': 'default',
                'entity': 'lock.dor', 'door_entity': 'sensor.dor', 'door_open': 'open',
                'door_closed': 'closed', 'camera': 'camera.gang', 'image_mode': 'proxy',
                'image_delay': 0, 'group_seconds': 60, 'live_ios': True}
        base.update(cfg)
        r = Runtime(self.hass, SimpleNamespace(entry_id='dør', options={}, data=base))
        self.runtimes.append(r)
        return r

    async def event(self, r, entity_id, old, new, attrs=None):
        await r.door_camera_changed(State(entity_id, old), State(entity_id, new, attrs or {}), entity_id)
        await self.hass.async_block_till_done()

    def ios(self):
        return [m for m in self.sent if 'push' in m['data']]

    def android(self):
        return [m for m in self.sent if 'channel' in m['data']]

    # ---- oppsett --------------------------------------------------------

    def test_flags_and_closed_is_off_by_default(self):
        self.assertEqual(set(flags('door_camera')), {'locked', 'unlocked', 'opened', 'closed'})

    async def test_closed_off_on_first_load(self):
        r = self.runtime()
        await r.load()
        self.assertFalse(r.enabled['closed'])
        self.assertTrue(r.enabled['locked'] and r.enabled['unlocked'] and r.enabled['opened'])

    def test_schema_has_camera_fields(self):
        keys = {str(k) for k in schema(self.hass, 'door_camera', {}).schema}
        for key in ('entity', 'door_entity', 'camera', 'image_mode', 'image_delay', 'group_seconds', 'live_ios'):
            self.assertIn(key, keys)

    def test_errors_require_camera_and_valid_door_states(self):
        data = {'ios_targets': ['mobile_app_iphone'], 'android_targets': [], 'door_entity': 'sensor.dor',
                'door_open': 'open', 'door_closed': 'closed'}
        self.assertEqual(errors(self.hass, 'door_camera', data), {'base': 'missing_camera'})
        data['camera'] = 'camera.gang'
        self.assertEqual(errors(self.hass, 'door_camera', data), {})
        data['door_closed'] = 'open'
        self.assertEqual(errors(self.hass, 'door_camera', data), {'base': 'invalid_door_states'})
        # Uten dørsensor spiller dørtilstandene ingen rolle.
        data['door_entity'] = None
        self.assertEqual(errors(self.hass, 'door_camera', data), {})

    # ---- hendelser ------------------------------------------------------

    async def test_unlock_sends_image_to_both_and_live_camera_to_iphone(self):
        r = self.runtime()
        await r.load()
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        self.assertEqual(len(self.sent), 2)
        for m in self.sent:
            self.assertEqual(m['title'], '🔓 Døra ble låst opp')
            self.assertTrue(m['data']['image'].startswith('/api/camera_proxy/camera.gang?ki='))
            self.assertTrue(m['data']['tag'].startswith('ki_door_dør_'))
        self.assertEqual(self.ios()[0]['data']['entity_id'], 'camera.gang')
        self.assertNotIn('entity_id', self.android()[0]['data'])

    async def test_lock_mentions_who_when_the_lock_says(self):
        r = self.runtime()
        await r.load()
        await self.event(r, 'lock.dor', 'unlocked', 'locked', {'changed_by': 'Sebastian'})
        self.assertIn('av Sebastian', self.sent[0]['message'])
        self.assertEqual(self.sent[0]['title'], '🔒 Døra ble låst')

    async def test_transitional_and_unavailable_states_are_ignored(self):
        r = self.runtime()
        await r.load()
        await self.event(r, 'lock.dor', 'locked', 'unlocking')
        await self.event(r, 'lock.dor', 'unavailable', 'locked')
        await self.event(r, 'lock.dor', 'locked', 'locked')
        self.assertEqual(self.sent, [])
        # Fra mellomtilstanden og fram til landet: nå varsles det.
        await self.event(r, 'lock.dor', 'unlocking', 'unlocked')
        self.assertEqual(len(self.sent), 2)

    async def test_door_open_notifies_and_closed_stays_quiet(self):
        r = self.runtime()
        await r.load()
        await self.event(r, 'sensor.dor', 'closed', 'open')
        self.assertEqual(self.sent[0]['title'], '🚪 Døra ble åpnet')
        self.sent.clear()
        await self.event(r, 'sensor.dor', 'open', 'closed')
        self.assertEqual(self.sent, [])

    async def test_switches_turn_single_events_off(self):
        r = self.runtime()
        await r.load()
        await r.toggle('unlocked', False)
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        self.assertEqual(self.sent, [])

    async def test_unlock_then_open_is_one_updating_notification(self):
        r = self.runtime()
        await r.load()
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        await self.event(r, 'sensor.dor', 'closed', 'open')
        first, second = self.ios()
        self.assertEqual(first['data']['tag'], second['data']['tag'])
        self.assertIn('Låst opp', second['message'])
        self.assertIn('åpnet', second['message'])

    async def test_group_zero_gives_separate_notifications(self):
        r = self.runtime(group_seconds=0)
        await r.load()
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        await self.event(r, 'sensor.dor', 'closed', 'open')
        first, second = self.ios()
        self.assertNotEqual(first['data']['tag'], second['data']['tag'])
        self.assertNotIn('Låst opp', second['message'])

    async def test_master_off_sends_nothing(self):
        r = self.runtime()
        await r.load()
        await r.toggle('master', False)
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        self.assertEqual(self.sent, [])

    # ---- bildet ---------------------------------------------------------

    async def test_snapshot_mode_saves_file_and_links_local(self):
        r = self.runtime(image_mode='snapshot')
        await r.load()
        taken = []

        async def snapshot(call):
            taken.append(call.data['filename'])
            with open(call.data['filename'], 'wb') as f:
                f.write(b'jpg')

        self.hass.services.async_register('camera', 'snapshot', snapshot)
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        self.assertEqual(len(taken), 1)
        self.assertTrue(os.path.exists(taken[0]))
        self.assertIn(os.path.join('www', 'ki_varslinger'), taken[0])
        self.assertTrue(self.sent[0]['data']['image'].startswith('/local/ki_varslinger/'))

    async def test_snapshot_failure_falls_back_to_proxy(self):
        r = self.runtime(image_mode='snapshot')
        await r.load()

        async def snapshot(call):
            raise ValueError('Cannot write, no access to path')

        self.hass.services.async_register('camera', 'snapshot', snapshot)
        await self.event(r, 'lock.dor', 'locked', 'unlocked')
        self.assertTrue(self.sent[0]['data']['image'].startswith('/api/camera_proxy/camera.gang'))
        self.assertIn('allowlist_external_dirs', r.last_source_error)

    async def test_old_snapshots_are_cleaned_up(self):
        r = self.runtime()
        folder = self.hass.config.path('www', 'ki_varslinger')
        os.makedirs(folder, exist_ok=True)
        for i in range(25):
            path = os.path.join(folder, f'{i:02d}.jpg')
            with open(path, 'wb') as f:
                f.write(b'x')
            os.utime(path, (1000 + i, 1000 + i))
        r._door_cleanup(folder)
        rest = sorted(os.listdir(folder))
        self.assertEqual(len(rest), 20)
        self.assertEqual(rest[0], '05.jpg')  # de fem eldste er borte

    async def test_test_button_sends_test_with_image(self):
        r = self.runtime()
        await r.load()
        await r.test('test')
        await self.hass.async_block_till_done()
        self.assertTrue(self.sent[0]['message'].startswith('TEST:'))
        self.assertIn('image', self.sent[0]['data'])
        self.assertNotIn('tag', self.sent[0]['data'])


if __name__ == '__main__':
    unittest.main()
