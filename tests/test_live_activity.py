"""Live Activities: motoren, de seks nye regeltypene og valget i de eksisterende reglene.

Varslingshandlingene er simulerte; ingenting sendes til en telefon. Tidsur fanges opp
med en Mock, så testene venter aldri på ekte tid.
"""
import tempfile
import time
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from homeassistant.core import Event, HomeAssistant, State
from homeassistant.util import dt as dt_util

from custom_components.ki_notifications import Runtime
from custom_components.ki_notifications.config_flow import errors, schema
from custom_components.ki_notifications.const import KINDS, LIVE_KINDS, LIVE_OPTION_KINDS, flags
from custom_components.ki_notifications.logic import clock_seconds, end_timestamp, number, states_set

LIVE = 'custom_components.ki_notifications.live_activity.'


class Logic(unittest.TestCase):
    def test_states(self):
        self.assertEqual(states_set(' On, Charging ,'), {'on', 'charging'})
        self.assertEqual(states_set('', 'on,open'), {'on', 'open'})
        self.assertEqual(states_set(None, 'on'), {'on'})

    def test_number_rejects_text_and_nan(self):
        self.assertEqual(number('42'), 42)
        self.assertEqual(number('42,5 %'), 42.5)
        for bad in ('unavailable', 'nan', 'inf', None, ''):
            self.assertIsNone(number(bad))

    def test_clock(self):
        self.assertEqual(clock_seconds('1:05:30'), 3930)
        self.assertEqual(clock_seconds('05:30'), 330)
        for bad in ('30', '1:xx', '1:2:3:4', '-1:00'):
            self.assertIsNone(clock_seconds(bad))

    def test_end_timestamp(self):
        now = 1_000_000.0
        self.assertEqual(end_timestamp('45', 'min', None, now), now + 2700)
        self.assertEqual(end_timestamp('45', None, None, now), now + 2700)      # uten enhet: minutter
        self.assertEqual(end_timestamp('1.5', 'h', 'duration', now), now + 5400)
        self.assertEqual(end_timestamp('90', 's', None, now), now + 90)
        self.assertEqual(end_timestamp('0:10:00', None, None, now), now + 600)
        end = dt_util.utc_from_timestamp(now + 120).isoformat()
        self.assertEqual(end_timestamp(end, None, 'timestamp', now, dt_util.parse_datetime), now + 120)
        self.assertEqual(end_timestamp(end, None, None, now, dt_util.parse_datetime), now + 120)

    def test_end_timestamp_never_in_the_past_or_invented(self):
        now = 1_000_000.0
        past = dt_util.utc_from_timestamp(now - 5).isoformat()
        for value, unit, device_class in [('0', 'min', None), ('-3', 'min', None), ('unknown', 'min', None),
                                          (past, None, 'timestamp'), ('tull', None, 'timestamp')]:
            self.assertIsNone(end_timestamp(value, unit, device_class, now, dt_util.parse_datetime))


class Base(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.tmp.name)
        self.sent, self.runtimes = [], []

        async def notify(call):
            self.sent.append((call.service, dict(call.data)))
        self.hass.services.async_register('notify', 'mobile_app_iphone', notify)
        self.hass.services.async_register('notify', 'mobile_app_pixel', notify)
        self.later = Mock(side_effect=lambda hass, seconds, action: Mock())
        patcher = patch(LIVE + 'async_call_later', self.later)
        patcher.start()
        self.addCleanup(patcher.stop)

    async def asyncTearDown(self):
        for r in self.runtimes:
            r.close()
        await self.hass.async_block_till_done()
        self.tmp.cleanup()

    def runtime(self, kind, entry_id=None, android=False, **cfg):
        data = {'kind': kind, 'name': 'Test', 'ios_targets': ['mobile_app_iphone'],
                'android_targets': ['mobile_app_pixel'] if android else [], 'sound': 'default', **cfg}
        r = Runtime(self.hass, SimpleNamespace(data=data, options={}, entry_id=entry_id or 'test_' + kind))
        self.runtimes.append(r)
        return r

    def set(self, entity_id, state, attributes=None, ago=0):
        self.hass.states.async_set(entity_id, state, attributes, timestamp=time.time() - ago)

    def data(self, index=-1):
        return self.sent[index][1]['data']

    def message(self, index=-1):
        return self.sent[index][1]['message']

    def timer(self, r, name):
        """Kjør tidsuret med dette navnet, slik HA ville gjort når tiden var ute."""
        self.assertIn(name, r.live_timers)
        seconds, action = next((c.args[1], c.args[2]) for c in reversed(self.later.call_args_list)
                               if c.args[2].__closure__ and name in [x.cell_contents for x in c.args[2].__closure__ if isinstance(x.cell_contents, str)])
        return seconds, action

    async def change(self, r, entity, old, new):
        await r.changed(Event('state_changed', {'old_state': State(entity, old), 'new_state': State(entity, new), 'entity_id': entity}))


class Engine(Base):
    def washer(self, **cfg):
        return self.runtime('live_appliance', entity='sensor.washer', remaining_entity='sensor.washer_left',
                            progress_entity='sensor.washer_progress', phase_entity='sensor.washer_phase', **cfg)

    def running(self, left='45', progress='25', phase='Vasker'):
        self.set('sensor.washer', 'run')
        self.set('sensor.washer_left', left, {'unit_of_measurement': 'min'})
        self.set('sensor.washer_progress', progress, {'unit_of_measurement': '%'})
        self.set('sensor.washer_phase', phase)

    async def test_nothing_until_active(self):
        r = self.washer()
        self.set('sensor.washer', 'idle')
        await r.live_sync()
        self.assertFalse(self.sent)
        self.assertFalse(r.live_active)

    async def test_start_payload_matches_companion_fields(self):
        r = self.washer(live_url='/lovelace/vaskerom')
        self.running()
        before = time.time()
        await r.live_sync()
        self.assertEqual(len(self.sent), 1)
        body, data = self.sent[0][1], self.data()
        self.assertEqual((body['title'], body['message']), ('Test', 'Vasker'))
        self.assertIs(data['live_update'], True)
        self.assertEqual(data['tag'], 'ki_live_test_live_appliance')
        self.assertRegex(data['tag'], r'^[A-Za-z0-9_-]{1,64}$')
        self.assertEqual((data['progress'], data['progress_max'], data['critical_text']), (25, 100, '25%'))
        self.assertIs(data['chronometer'], True)
        self.assertIs(data['when_relative'], False)
        self.assertAlmostEqual(data['when'], before + 2700, delta=3)
        self.assertEqual(data['notification_icon'], 'mdi:washing-machine')
        self.assertEqual(data['notification_icon_color'], '#2196F3')
        self.assertEqual(data['url'], '/lovelace/vaskerom')
        self.assertEqual(data['relevance_score'], 0.5)
        # Starten varsler med lyd; «silent» hører bare hjemme på oppdateringer.
        self.assertNotIn('silent', data)
        self.assertEqual(data['push']['sound'], 'default')
        self.assertTrue(r.live_active)

    async def test_android_gets_title_colour_and_one_alert(self):
        r = self.washer()
        r.cfg['android_targets'] = ['mobile_app_pixel']
        self.running()
        await r.live_sync()
        android = next(d for s, d in self.sent if s == 'mobile_app_pixel')
        self.assertTrue(android['title'])                 # uten tittel blir det et vanlig banner på Android
        self.assertEqual(android['data']['color'], '#2196F3')
        self.assertIs(android['data']['alert_once'], True)
        self.assertIs(android['data']['sticky'], True)
        self.assertIs(android['data']['live_update'], True)
        self.assertNotIn('push', android['data'])

    async def test_identical_state_is_not_sent_again(self):
        r = self.washer()
        self.running()
        await r.live_sync()
        r.live_sent_at -= 600
        for _ in range(5):
            await r.live_sync()
        self.assertEqual(len(self.sent), 1)

    async def test_remaining_time_ticking_does_not_push(self):
        """Sensoren teller ned et minutt i minuttet. Telefonen teller selv – ingen sending."""
        r = self.washer()
        self.running(left='45')
        await r.live_sync()
        first = self.data()['when']
        r.live_sent_at -= 600
        self.running(left='44.5')        # 30 sekunder «forskjøvet»: innenfor toleransen
        await r.live_sync()
        self.assertEqual(len(self.sent), 1)
        self.running(left='30')          # programmet hoppet: det er en ekte endring
        await r.live_sync()
        self.assertEqual(len(self.sent), 2)
        self.assertLess(self.data()['when'], first - 600)

    async def test_updates_are_silent_and_throttled_to_latest(self):
        r = self.washer()
        self.running(progress='25')
        await r.live_sync()
        for value in ('26', '27', '28'):
            self.running(progress=value)
            await r.live_sync()
        self.assertEqual(len(self.sent), 1)                     # innenfor 30 s: ingenting sendt
        seconds, action = self.timer(r, 'throttle')
        self.assertTrue(0 < seconds <= 30)
        throttles = [c for c in self.later.call_args_list if 0 < c.args[1] <= 30]
        self.assertEqual(len(throttles), 1)                     # ett tidsur, ikke ett per endring
        r.live_sent_at -= 31
        await action(dt_util.utcnow())
        self.assertEqual(len(self.sent), 2)
        data = self.data()
        self.assertEqual(data['progress'], 28)                  # bare den siste verdien
        self.assertIs(data['silent'], True)
        self.assertEqual(data['push'], {'sound': 'none', 'interruption-level': 'passive'})
        self.assertEqual(data['tag'], self.data(0)['tag'])

    async def test_interval_is_configurable(self):
        r = self.washer(live_interval=300)
        self.running()
        await r.live_sync()
        r.live_sent_at -= 100
        self.running(progress='50')
        await r.live_sync()
        self.assertEqual(len(self.sent), 1)
        r.live_sent_at -= 250
        await r.live_sync()
        self.assertEqual(len(self.sent), 2)

    async def test_finish_shows_done_then_clears(self):
        r = self.washer()
        self.running()
        await r.live_sync()
        self.set('sensor.washer', 'idle')
        await r.live_sync()
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.message(), 'Ferdig')
        data = self.data()
        self.assertEqual((data['progress'], data['progress_max']), (100, 100))
        self.assertNotIn('chronometer', data)
        self.assertNotIn('silent', data)                        # «ferdig» er verdt en lyd
        self.assertTrue(r.live_active)
        await r.live_sync()                                     # flere hendelser mens den står: ingenting
        self.assertEqual(len(self.sent), 2)
        seconds, action = self.timer(r, 'linger')
        self.assertEqual(seconds, 300)
        await action(dt_util.utcnow())
        self.assertEqual(self.message(), 'clear_notification')
        self.assertEqual(self.data()['tag'], 'ki_live_test_live_appliance')
        self.assertFalse(r.live_active)
        self.assertEqual(r.last_message, 'Ferdig')              # statusen viser ikke «clear_notification»

    async def test_linger_zero_clears_at_once(self):
        r = self.washer(live_linger=0)
        self.running()
        await r.live_sync()
        self.set('sensor.washer', 'idle')
        await r.live_sync()
        self.assertEqual([self.message(0), self.message(1)], ['Vasker', 'clear_notification'])

    async def test_new_run_while_done_is_shown_reuses_activity(self):
        r = self.washer()
        self.running()
        await r.live_sync()
        self.set('sensor.washer', 'idle')
        await r.live_sync()
        self.running(phase='Skyller')
        await r.live_sync()
        self.assertEqual(self.message(), 'Skyller')
        self.assertNotIn('clear_notification', [d['message'] for _, d in self.sent])
        self.assertFalse(r.live_lingering)
        self.assertNotIn('linger', r.live_timers)

    async def test_switch_off_clears_without_done_message(self):
        r = self.washer()
        self.running()
        await r.live_sync()
        await r.toggle('enabled', False)
        self.assertEqual(self.message(), 'clear_notification')
        self.assertFalse(r.live_active)
        self.running(progress='90')
        await r.live_sync()
        self.assertEqual(len(self.sent), 2)
        await r.toggle('enabled', True)
        self.assertEqual(self.data()['progress'], 90)

    async def test_eight_hour_limit_ends_it_until_next_run(self):
        r = self.runtime('live_open', entities=['binary_sensor.port'], open_delay=0)
        self.set('binary_sensor.port', 'on', ago=10)
        await r.live_sync()
        seconds, action = self.timer(r, 'expire')
        self.assertLess(seconds, 8 * 3600)                      # før iOS selv avslutter
        await action(dt_util.utcnow())
        self.assertEqual(self.message(), 'clear_notification')
        await r.live_sync()
        self.assertEqual(len(self.sent), 2)                     # startes ikke på nytt mens porten står åpen
        self.set('binary_sensor.port', 'off')
        await r.live_sync()
        self.set('binary_sensor.port', 'on', ago=10)
        await r.live_sync()
        self.assertEqual(len(self.sent), 3)

    async def test_restart_resumes_quietly_or_clears_leftover(self):
        r = self.washer()
        self.running()
        await r.live_sync()
        r.close()
        again = self.washer()
        await again.load()
        self.assertTrue(again.live_orphan)
        self.running(progress='60')
        await again.live_sync()
        self.assertIs(self.data()['silent'], True)              # samme aktivitet, ingen ny lyd
        self.assertEqual(self.data()['progress'], 60)
        again.close()
        # Var vasken ferdig mens HA var nede, fjernes aktiviteten som ble stående.
        third = self.washer()
        await third.load()
        self.set('sensor.washer', 'idle')
        await third.live_sync()
        self.assertEqual(self.message(), 'clear_notification')
        fourth = self.washer()
        await fourth.load()
        self.assertFalse(fourth.live_orphan)

    async def test_unavailable_sources_do_not_invent_values(self):
        r = self.washer()
        self.set('sensor.washer', 'run')
        self.set('sensor.washer_left', 'unavailable')
        self.set('sensor.washer_progress', 'unknown')
        await r.live_sync()
        data = self.data()
        for key in ('progress', 'progress_max', 'chronometer', 'when', 'critical_text'):
            self.assertNotIn(key, data)
        self.assertEqual(self.message(), 'Pågår')

    async def test_test_button_uses_own_tag_and_cleans_up(self):
        r = self.washer()
        await r.test('test')
        data = self.data()
        self.assertEqual(data['tag'], 'ki_live_test_live_appliance_test')
        self.assertEqual((data['progress'], data['progress_max']), (40, 100))
        self.assertFalse(r.live_active)                         # den ekte aktiviteten er urørt
        seconds, action = self.timer(r, 'test')
        self.assertEqual(seconds, 60)
        await action(dt_util.utcnow())
        self.assertEqual(self.message(), 'clear_notification')
        self.assertEqual(self.data()['tag'], 'ki_live_test_live_appliance_test')

    async def test_listeners_drive_it_end_to_end(self):
        r = self.washer()
        self.hass.set_state(__import__('homeassistant.core', fromlist=['CoreState']).CoreState.running)
        self.set('sensor.washer', 'idle')
        await self.hass.async_block_till_done()
        r.listen()
        self.running()
        await self.hass.async_block_till_done()
        self.assertEqual([d['message'] for _, d in self.sent], ['Vasker'])     # én start, av fire tilstandsendringer
        self.assertTrue(r.live_active)
        r.close()
        self.set('sensor.washer', 'idle')
        await self.hass.async_block_till_done()
        self.assertNotIn('Ferdig', [d['message'] for _, d in self.sent])


class NewKinds(Base):
    async def test_ev_progress_against_charge_limit(self):
        r = self.runtime('live_ev', entity='binary_sensor.charging', progress_entity='sensor.battery',
                         limit_entity='number.limit', remaining_entity='sensor.left')
        self.set('binary_sensor.charging', 'on')
        self.set('sensor.battery', '45', {'unit_of_measurement': '%'})
        self.set('number.limit', '80')
        self.set('sensor.left', '0.75', {'unit_of_measurement': 'h'})
        await r.live_sync()
        data = self.data()
        self.assertEqual((data['progress'], data['progress_max'], data['critical_text']), (45, 80, '45%'))
        self.assertEqual(self.message(), 'Lader · 45 % av 80 %')
        self.assertAlmostEqual(data['when'], time.time() + 2700, delta=3)
        self.assertEqual(data['notification_icon'], 'mdi:ev-station')
        self.set('binary_sensor.charging', 'off')
        await r.live_sync()
        self.assertEqual(self.message(), 'Lading ferdig')
        self.assertEqual(self.data()['progress'], 45)           # avbrutt lading vises ikke som full

    async def test_ev_custom_active_state(self):
        r = self.runtime('live_ev', entity='sensor.charger', active_states='Charging, Boost')
        self.set('sensor.charger', 'connected')
        await r.live_sync()
        self.assertFalse(self.sent)
        self.set('sensor.charger', 'charging')
        await r.live_sync()
        self.assertEqual(self.message(), 'Lader')

    async def test_open_waits_then_counts_up(self):
        r = self.runtime('live_open', entities=['binary_sensor.port', 'cover.garasje'], open_delay=120)
        self.set('binary_sensor.port', 'on', {'friendly_name': 'Port'}, ago=30)
        self.set('cover.garasje', 'closed')
        await r.live_sync()
        self.assertFalse(self.sent)                             # åpnet nettopp: ingen aktivitet ennå
        seconds, action = self.timer(r, 'wake')
        self.assertAlmostEqual(seconds, 90, delta=2)
        opened = time.time() - 300
        self.hass.states.async_set('binary_sensor.port', 'on', {'friendly_name': 'Port'}, force_update=True)
        self.set('binary_sensor.port', 'off')
        self.hass.states.async_set('binary_sensor.port', 'on', {'friendly_name': 'Port'}, timestamp=opened)
        await action(dt_util.utcnow())
        data = self.data()
        self.assertEqual(self.message(), 'Port')
        self.assertAlmostEqual(data['when'], opened, delta=2)   # teller opp fra da den ble åpnet
        self.assertIs(data['chronometer'], True)
        self.assertEqual(data['relevance_score'], 0.2)          # tar ikke Dynamic Island
        self.assertNotIn('progress', data)

    async def test_open_lists_several_and_ends_when_all_closed(self):
        r = self.runtime('live_open', entities=['binary_sensor.port', 'cover.garasje'], open_delay=0)
        self.set('binary_sensor.port', 'on', {'friendly_name': 'Port'}, ago=500)
        await r.live_sync()
        r.live_sent_at -= 60
        self.set('cover.garasje', 'open', {'friendly_name': 'Garasje'}, ago=5)
        await r.live_sync()
        self.assertEqual(self.message(), '2 åpne: Port, Garasje')
        self.assertEqual(self.data()['critical_text'], '2 åpne')
        self.set('binary_sensor.port', 'off')
        self.set('cover.garasje', 'closed')
        await r.live_sync()
        self.assertEqual(self.message(), 'clear_notification')

    async def test_timer_counts_down_pauses_and_ends(self):
        r = self.runtime('live_timer', entity='timer.pasta')
        end = dt_util.utcnow() + timedelta(minutes=8)
        self.set('timer.pasta', 'active', {'finishes_at': end.isoformat(), 'duration': '0:08:00'})
        await r.live_sync()
        self.assertEqual(self.data()['when'], int(round(end.timestamp())))
        self.assertEqual(self.data()['relevance_score'], 0.7)
        r.live_sent_at -= 60
        self.set('timer.pasta', 'paused', {'remaining': '0:05:12'})
        await r.live_sync()
        self.assertEqual(self.message(), 'Satt på pause · 0:05:12 igjen')
        self.assertNotIn('chronometer', self.data())
        self.set('timer.pasta', 'idle')
        await r.live_sync()
        self.assertEqual(self.message(), 'clear_notification')

    async def test_pool_fixed_duration_and_temperature(self):
        r = self.runtime('live_pool', entity='switch.pumpe', duration=120, temp_entity='sensor.vann')
        self.set('switch.pumpe', 'on', ago=1800)
        self.set('sensor.vann', '27.5', {'unit_of_measurement': '°C'})
        await r.live_sync()
        self.assertEqual(self.message(), 'Pumpa går · 27.5 °C')
        self.assertAlmostEqual(self.data()['when'], time.time() + 5400, delta=3)
        self.assertEqual(self.data()['relevance_score'], 0.3)
        self.set('switch.pumpe', 'off')
        await r.live_sync()
        self.assertEqual(self.message(), 'Pumpa har stoppet')

    async def test_pool_past_fixed_duration_shows_no_timer(self):
        r = self.runtime('live_pool', entity='switch.pumpe', duration=10)
        self.set('switch.pumpe', 'on', ago=1800)
        await r.live_sync()
        self.assertNotIn('chronometer', self.data())

    async def test_generic_progress_text_and_scale(self):
        r = self.runtime('live_progress', entity='binary_sensor.print', progress_entity='sensor.layer',
                         progress_max=240, phase_entity='sensor.stage', message='{phase} · lag {progress} ({state})',
                         icon='mdi:printer-3d', live_color='#9C27B0', live_priority=0.9)
        self.set('binary_sensor.print', 'on')
        self.set('sensor.layer', '60')
        self.set('sensor.stage', 'Skriver')
        await r.live_sync()
        data = self.data()
        self.assertEqual(self.message(), 'Skriver · lag 60 (on)')
        self.assertEqual((data['progress'], data['progress_max']), (60, 240))
        self.assertEqual((data['notification_icon'], data['notification_icon_color'], data['relevance_score']),
                         ('mdi:printer-3d', '#9C27B0', 0.9))


class ExistingRules(Base):
    async def test_off_by_default_changes_nothing(self):
        for kind in LIVE_OPTION_KINDS:
            self.assertFalse(self.runtime(kind, entry_id='off_' + kind).live_on)
        r = self.runtime('state', entity='binary_sensor.x', from_state='off', to_state='on', message='Hei', icon='mdi:bell')
        self.set('binary_sensor.x', 'on')
        await self.change(r, 'binary_sensor.x', 'off', 'on')
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn('live_update', self.data())
        self.assertNotIn('tag', self.data())

    async def test_vacuum_progress_and_buttons_kept(self):
        r = self.runtime('vacuum', entity='vacuum.robot', live_activity=True, progress_entity='sensor.cleaned')
        self.set('vacuum.robot', 'cleaning', {'friendly_name': 'Robot'})
        self.set('sensor.cleaned', '10', {'unit_of_measurement': '%'})
        await self.change(r, 'vacuum.robot', 'docked', 'cleaning')
        classic, live = self.sent[0][1], self.sent[1][1]
        self.assertEqual(classic['data']['tag'], 'ki_vacuum_test_vacuum')
        self.assertEqual(classic['data']['actions'][0]['title'], 'Pause')   # knappene finnes fortsatt
        self.assertEqual(classic['data']['push']['sound'], 'none')          # én lyd ved start, ikke to
        self.assertNotIn('live_update', classic['data'])
        self.assertEqual(live['data']['tag'], 'ki_live_test_vacuum')
        self.assertEqual(live['data']['progress'], 10)
        self.assertEqual(live['data']['push']['sound'], 'default')
        self.assertEqual(live['title'], '🧹 Robot')
        self.set('vacuum.robot', 'docked', {'friendly_name': 'Robot'})
        await self.change(r, 'vacuum.robot', 'cleaning', 'docked')
        self.assertEqual(self.message(), 'Tilbake i ladestasjonen')
        self.assertIs(self.data()['live_update'], True)

    async def test_vacuum_progress_sensor_does_not_touch_button_notification(self):
        r = self.runtime('vacuum', entity='vacuum.robot', live_activity=True, progress_entity='sensor.cleaned')
        self.hass.set_state(__import__('homeassistant.core', fromlist=['CoreState']).CoreState.running)
        self.set('vacuum.robot', 'docked')
        self.set('sensor.cleaned', '0')
        await self.hass.async_block_till_done()
        r.listen()
        self.set('vacuum.robot', 'cleaning')
        await self.hass.async_block_till_done()
        count = len(self.sent)
        r.live_sent_at -= 60
        self.set('sensor.cleaned', '35')
        await self.hass.async_block_till_done()
        self.assertEqual(len(self.sent), count + 1)             # bare aktiviteten, ikke knappevarselet
        self.assertEqual(self.data()['progress'], 35)

    async def test_alarm_exit_and_entry_countdown(self):
        r = self.runtime('alarm', entity='alarm_control_panel.home', live_activity=True)
        self.set('alarm_control_panel.home', 'arming', {'delay': 45}, ago=5)
        await self.change(r, 'alarm_control_panel.home', 'disarmed', 'arming')
        self.assertEqual(self.sent[-1][1]['title'], '🔒 Alarmen aktiveres')
        self.assertAlmostEqual(self.data()['when'], time.time() + 40, delta=3)
        self.assertEqual(self.data()['relevance_score'], 0.9)
        self.set('alarm_control_panel.home', 'armed_away')
        await self.change(r, 'alarm_control_panel.home', 'arming', 'armed_away')
        self.assertEqual([d['message'] for _, d in self.sent[1:]], ['clear_notification', 'Alarm aktivert.'][::-1])
        self.sent.clear()
        self.set('alarm_control_panel.home', 'pending', {'delay': 30})
        await self.change(r, 'alarm_control_panel.home', 'armed_away', 'pending')
        self.assertEqual(self.sent[-1][1]['title'], '🚨 Slå av alarmen')
        self.assertEqual(self.data()['notification_icon_color'], '#F44336')
        self.assertEqual(self.data()['relevance_score'], 1.0)
        # Utløst har en annen tittel, og iOS låser tittelen ved start: ny aktivitet.
        self.set('alarm_control_panel.home', 'triggered')
        await self.change(r, 'alarm_control_panel.home', 'pending', 'triggered')
        live = [d for _, d in self.sent if d['data'].get('tag') == 'ki_live_test_alarm']
        self.assertEqual([d['message'] for d in live], ['Inngangstid', 'clear_notification', 'Alarmen er utløst'])
        self.assertNotIn('chronometer', live[-1]['data'])
        self.set('alarm_control_panel.home', 'disarmed')
        await self.change(r, 'alarm_control_panel.home', 'triggered', 'disarmed')
        self.assertFalse(r.live_active)

    async def test_alarm_respects_flags_and_master(self):
        r = self.runtime('alarm', entity='alarm_control_panel.home', live_activity=True)
        r.enabled['armed'] = False
        self.set('alarm_control_panel.home', 'arming', {'delay': 45})
        await self.change(r, 'alarm_control_panel.home', 'disarmed', 'arming')
        self.assertFalse(self.sent)
        r.enabled['armed'] = True
        await r.toggle('master', False)
        self.assertFalse(self.sent)
        await r.toggle('master', True)
        self.assertEqual(len(self.sent), 1)
        # Hovedbryteren av mens aktiviteten står: den fjernes, selv om varsler ellers er sperret.
        await r.toggle('master', False)
        self.assertEqual(self.message(), 'clear_notification')

    async def test_homey_switch_alarm_has_no_countdown(self):
        r = self.runtime('alarm', entity='switch.alarm', live_activity=True)
        self.set('switch.alarm', 'on')
        await self.change(r, 'switch.alarm', 'off', 'on')
        self.assertEqual([d['message'] for _, d in self.sent], ['Alarm aktivert.'])

    def ruter(self, **cfg):
        self.set('zone.skole', '0', {'latitude': 59.9, 'longitude': 10.7, 'radius': 100, 'friendly_name': 'Skole'})
        self.set('sensor.trikk', '6', {'route': '17 Majorstuen', 'due_at': '14:06', 'friendly_name': 'Frydenlund'})
        return self.runtime('ruter', trackers=['device_tracker.phone'], zones=['zone.skole'], tram_sensors=['sensor.trikk'],
                            bus_sensors=[], directions='majorstuen', walk=4, ride=7, transfer=3, **cfg)

    async def test_ruter_counts_down_to_departure(self):
        r = self.ruter(live_activity=True)
        await r.ruter_notice()
        self.assertEqual(len(self.sent), 1)
        body = self.sent[0][1]
        self.assertEqual(body['title'], '🚋 17 Majorstuen kl. 14:06')
        self.assertIn('om 6 min', body['message'])
        self.assertAlmostEqual(body['data']['when'], time.time() + 360, delta=3)
        self.assertEqual(body['data']['critical_text'], '14:06')
        seconds, action = self.timer(r, 'wake')
        self.assertAlmostEqual(seconds, 420, delta=3)            # ett minutt etter avgang
        r.ruter_live['until'] = time.time() - 1
        await action(dt_util.utcnow())
        self.assertEqual(self.message(), 'clear_notification')

    async def test_ruter_without_reachable_departure_is_ordinary(self):
        r = self.ruter(live_activity=True)
        self.set('sensor.trikk', '2', {'route': '17 Majorstuen', 'due_at': '14:02'})
        await r.ruter_notice()
        self.assertNotIn('live_update', self.data())
        await r.ruter_notice(test=True)
        self.assertNotIn('live_update', self.data())

    def autolock(self, delay, **cfg):
        self.set('lock.front', 'unlocked')
        self.set('sensor.door', 'closed')
        r = self.runtime('autolock', entity='lock.front', door_entity='sensor.door', door_open='open',
                         door_closed='closed', autolock_delay=delay, **cfg)
        r.enabled['enabled'] = True
        return r

    async def test_autolock_countdown_and_locked(self):
        r = self.autolock(120, live_activity=True)
        with patch('custom_components.ki_notifications.security.async_call_later', return_value=Mock()) as later:
            await self.change(r, 'sensor.door', 'open', 'closed')
            await self.hass.async_block_till_done()
            self.assertEqual(self.sent[0][1]['title'], '🔒 Låser døra')
            self.assertAlmostEqual(self.data()['when'], time.time() + 120, delta=3)
            locked = []
            async def lock(call):
                locked.append(1)
                self.set('lock.front', 'locked')
            self.hass.services.async_register('lock', 'lock', lock)
            await later.call_args.args[2](dt_util.utcnow())
        self.assertEqual(locked, [1])
        self.assertEqual(self.message(), 'Døra er låst')

    async def test_autolock_door_reopened_ends_countdown(self):
        r = self.autolock(120, live_activity=True)
        with patch('custom_components.ki_notifications.security.async_call_later', return_value=Mock()):
            await self.change(r, 'sensor.door', 'open', 'closed')
            await self.hass.async_block_till_done()
            self.set('sensor.door', 'open')
            await self.change(r, 'sensor.door', 'closed', 'open')
        self.assertEqual(self.message(), 'clear_notification')

    async def test_autolock_short_delay_and_missing_phone_stay_silent(self):
        with patch('custom_components.ki_notifications.security.async_call_later', return_value=Mock()):
            short = self.autolock(30, live_activity=True)
            await self.change(short, 'sensor.door', 'open', 'closed')
            await self.hass.async_block_till_done()
            self.assertFalse(self.sent)                         # over før den rekker å vises
            off = self.autolock(120)
            await self.change(off, 'sensor.door', 'open', 'closed')
            await self.hass.async_block_till_done()
            self.assertFalse(self.sent)

    async def test_jammed_lock_counts_up_until_fixed(self):
        r = self.runtime('lock_jammed', entity='lock.front', jam_seconds=60, live_activity=True)
        jammed = time.time() - 90
        self.hass.states.async_set('lock.front', 'jammed', timestamp=jammed)
        await r.jam_due(r.jam_generation)
        self.assertEqual(len(self.sent), 1)                     # aktiviteten erstatter banneret
        self.assertEqual(self.sent[0][1]['title'], '🔒 Dørlås fastkjørt')
        self.assertAlmostEqual(self.data()['when'], jammed, delta=2)
        self.set('lock.front', 'locked')
        await self.change(r, 'lock.front', 'jammed', 'locked')
        self.assertEqual(self.message(), 'Låsen er i orden igjen')

    async def test_jammed_lock_not_shown_before_the_wait_is_over(self):
        r = self.runtime('lock_jammed', entity='lock.front', jam_seconds=60, live_activity=True)
        self.set('lock.front', 'jammed', ago=10)
        await r.live_sync()
        self.assertFalse(self.sent)
        seconds, _ = self.timer(r, 'wake')
        self.assertAlmostEqual(seconds, 50, delta=2)

    async def test_custom_state_shows_until_state_is_gone(self):
        r = self.runtime('state', entity='binary_sensor.oven', from_state='off', to_state='on', message='Ovnen står på',
                         icon='mdi:stove', live_activity=True, progress_entity='sensor.temp', remaining_entity='sensor.left')
        self.set('binary_sensor.oven', 'on')
        self.set('sensor.temp', '50')
        self.set('sensor.left', '0:20:00')
        await self.change(r, 'binary_sensor.oven', 'off', 'on')
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.message(), 'Ovnen står på')
        self.assertEqual(self.data()['progress'], 50)
        self.assertAlmostEqual(self.data()['when'], time.time() + 1200, delta=3)
        self.set('binary_sensor.oven', 'off')
        await self.change(r, 'binary_sensor.oven', 'on', 'off')
        self.assertEqual(self.message(), 'clear_notification')

    async def test_custom_state_ignores_matching_change_on_progress_sensor(self):
        r = self.runtime('state', entity='binary_sensor.oven', from_state='off', to_state='on', message='Ovnen står på',
                         icon='mdi:stove', live_activity=True, progress_entity='input_number.x')
        r.listen()
        self.set('binary_sensor.oven', 'off')
        await self.change(r, 'input_number.x', 'off', 'on')
        self.assertFalse(r.state_live)
        self.assertFalse(self.sent)


class Setup(Base):
    async def test_new_kinds_build_forms_and_single_switch(self):
        for kind in LIVE_KINDS:
            self.assertIn(kind, KINDS)
            keys = {str(k) for k in schema(self.hass, kind, {}).schema}
            self.assertTrue({'name', 'ios_targets', 'icon', 'live_color', 'live_priority', 'live_interval', 'live_linger'} <= keys, kind)
            self.assertNotIn('live_activity', keys)             # de er alltid en Live Activity
            self.assertEqual(flags(kind), {'enabled': 'Live Activity'})

    async def test_existing_kinds_get_the_choice_default_off(self):
        for kind in LIVE_OPTION_KINDS:
            form = schema(self.hass, kind, {})
            marker = next(k for k in form.schema if str(k) == 'live_activity')
            self.assertIs(marker.default(), False)
        for kind in set(KINDS) - LIVE_OPTION_KINDS - set(LIVE_KINDS):
            self.assertNotIn('live_activity', {str(k) for k in schema(self.hass, kind, {}).schema}, kind)

    async def test_translations_cover_every_field(self):
        import json
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / 'custom_components' / 'ki_notifications'
        keys = set()
        for kind in KINDS:
            keys |= {str(k) for k in schema(self.hass, kind, {}).schema}
        for name in ('strings.json', 'translations/nb.json', 'translations/en.json'):
            text = json.loads((root / name).read_text())
            for step in (text['config']['step']['settings'], text['options']['step']['init']):
                self.assertFalse(keys - set(step['data']), name)
            for code in ('missing_entities', 'invalid_color', 'invalid_url'):
                self.assertIn(code, text['config']['error'])
                self.assertIn(code, text['options']['error'])

    async def test_validation(self):
        ok = {'ios_targets': ['mobile_app_iphone'], 'android_targets': []}
        self.assertEqual(errors(self.hass, 'live_open', {**ok, 'entities': []}), {'base': 'missing_entities'})
        self.assertEqual(errors(self.hass, 'live_open', {**ok, 'entities': ['cover.x']}), {})
        self.assertEqual(errors(self.hass, 'live_timer', {**ok, 'live_color': 'blå'}), {})        # CSS-navn slippes gjennom
        self.assertEqual(errors(self.hass, 'live_timer', {**ok, 'live_color': '#12'}), {'base': 'invalid_color'})
        self.assertEqual(errors(self.hass, 'live_timer', {**ok, 'live_color': '#2196F3'}), {})
        self.assertEqual(errors(self.hass, 'live_timer', {**ok, 'live_url': 'lovelace/x'}), {'base': 'invalid_url'})
        self.assertEqual(errors(self.hass, 'live_timer', {**ok, 'live_url': '/lovelace/x'}), {})
        self.assertEqual(errors(self.hass, 'live_timer', {}), {'base': 'no_targets'})

    async def test_autolock_needs_a_phone_only_with_live_activity(self):
        door = {'door_open': 'open', 'door_closed': 'closed'}
        self.assertEqual(errors(self.hass, 'autolock', door), {})
        self.assertEqual(errors(self.hass, 'autolock', {**door, 'live_activity': True}), {'base': 'no_targets'})
        self.assertEqual(errors(self.hass, 'autolock', {**door, 'live_activity': True, 'ios_targets': ['mobile_app_iphone']}), {})

    async def test_buttons_and_status(self):
        from custom_components.ki_notifications import button, sensor
        from custom_components.ki_notifications.const import DOMAIN
        cases = [('live_ev', {}, ['test']), ('vacuum', {'entity': 'vacuum.r'}, ['test']),
                 ('vacuum', {'entity': 'vacuum.r', 'live_activity': True}, ['live_test', 'test'])]
        for index, (kind, cfg, expected) in enumerate(cases):
            r = self.runtime(kind, entry_id=f'b{index}', **cfg)
            self.hass.data[DOMAIN] = {r.entry.entry_id: r}
            buttons, sensors = [], []
            await button.async_setup_entry(self.hass, r.entry, lambda items: buttons.extend(items))
            await sensor.async_setup_entry(self.hass, r.entry, sensors.extend)
            self.assertEqual(sorted(b.key for b in buttons), expected)
            self.assertEqual('live_activity' in sensors[0].extra_state_attributes, r.live_on)


if __name__ == '__main__':
    unittest.main()
