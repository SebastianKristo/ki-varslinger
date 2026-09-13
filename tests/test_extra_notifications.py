import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch,Mock
from homeassistant.core import HomeAssistant,Event,State,SupportsResponse,CoreState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.util import dt as dt_util
from custom_components.ki_notifications import Runtime
from custom_components.ki_notifications.extra_notifications import DAYS

MODULE='custom_components.ki_notifications.extra_notifications.'

class NewNotifications(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.hass=HomeAssistant(self.tmp.name)
        self.sent=[];self.runtimes=[]
        async def notify(call):self.sent.append(dict(call.data))
        self.hass.services.async_register('notify','mobile_app_test',notify)
    async def asyncTearDown(self):
        for r in self.runtimes:r.close()
        await self.hass.async_block_till_done();self.tmp.cleanup()
    def runtime(self,kind,**cfg):
        r=Runtime(self.hass,SimpleNamespace(entry_id='test_'+kind,options={},data={'kind':kind,'name':'Test','ios_targets':['mobile_app_test'],'android_targets':[],'sound':'default',**cfg}))
        self.runtimes.append(r);return r
    def weather(self):
        self.hass.states.async_set('weather.home','cloudy',{'temperature':12,'temperature_unit':'°C','wind_speed':18,'wind_speed_unit':'km/h','precipitation_unit':'mm'})
        return self.runtime('weather_ai',weather_entity='weather.home',home_entity='switch.home',home_state='on',weekdays=list(DAYS),at='08:00:00')
    def weather_service(self):
        async def forecast(call):
            self.assertEqual(call.data['type'],'daily')
            return {'weather.home':{'forecast':[{'datetime':dt_util.now().isoformat(),'temperature':18,'templow':8,'precipitation':2}]}}
        self.hass.services.async_register('weather','get_forecasts',forecast,supports_response=SupportsResponse.ONLY)
    async def test_weather_home_filter_weekdays_and_daily_dedup(self):
        r=self.weather();self.weather_service()
        async def ai(call):return {'data':'Ta med en lett jakke.'}
        self.hass.services.async_register('ai_task','generate_data',ai,supports_response=SupportsResponse.ONLY)
        now=dt_util.now()
        self.hass.states.async_set('switch.home','off');await r.weather_due(now)
        self.assertFalse(self.sent)
        self.hass.states.async_set('switch.home','on')
        r.cfg['weekdays']=[];await r.weather_due(now);self.assertFalse(self.sent)
        r.cfg['weekdays']=list(DAYS);await r.weather_due(now);await r.weather_due(now)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0]['message'],'Ta med en lett jakke.')
        other=self.weather();await other.load()
        self.assertEqual(other.last_weather_date,now.date().isoformat())
    async def test_weather_units_entity_and_test_bypasses_home(self):
        r=self.weather();self.weather_service();r.cfg['ai_entity']='ai_task.writer'
        async def ai(call):
            self.assertIn('km/h',call.data['instructions'])
            self.assertEqual(call.data['entity_id'],'ai_task.writer')
            return {'data':'En fin dag.'}
        self.hass.services.async_register('ai_task','generate_data',ai,supports_response=SupportsResponse.ONLY)
        await r.test('test')
        self.assertEqual(self.sent[0]['message'],'TEST: En fin dag.')
        self.assertIsNone(r.last_weather_date)
    async def test_weather_fallback_without_ai(self):
        r=self.weather();self.weather_service()
        await r.test('test')
        self.assertIn('12°C',self.sent[0]['message'])
        self.assertIn('ai_task.generate_data',r.last_source_error)
    async def test_weather_missing_forecast_does_not_crash(self):
        r=self.weather()
        await r.test('test')
        self.assertIn('12°C',self.sent[0]['message'])
        self.assertIn('weather.get_forecasts',r.last_source_error)
    async def test_weather_schedule_at_eight(self):
        r=self.weather()
        with patch(MODULE+'async_track_time_change',return_value=Mock()) as track:
            r.listen()
            self.assertEqual(track.call_args.kwargs,{'hour':8,'minute':0,'second':0})
    async def test_lock_duration_cancel_rearm_and_attribute_changes(self):
        r=self.runtime('lock_jammed',entity='lock.front',jam_seconds=60)
        self.hass.states.async_set('lock.front','jammed')
        cancelled=Mock()
        with patch(MODULE+'async_call_later',return_value=cancelled) as later:
            await r.jam_changed(State('lock.front','locking'),State('lock.front','jammed'))
            self.assertEqual(later.call_args.args[1],60)
            old_due=later.call_args.args[2]
            await r.jam_changed(State('lock.front','jammed'),State('lock.front','jammed',{'battery':50}))
            self.assertEqual(later.call_count,1)
            self.hass.states.async_set('lock.front','locked')
            await r.jam_changed(State('lock.front','jammed'),State('lock.front','locked'))
            cancelled.assert_called()
            await old_due(dt_util.utcnow());self.assertFalse(self.sent)
            self.hass.states.async_set('lock.front','jammed')
            await r.jam_changed(State('lock.front','locked'),State('lock.front','jammed'))
            await old_due(dt_util.utcnow());self.assertFalse(self.sent)
            await later.call_args.args[2](dt_util.utcnow())
            self.assertEqual(len(self.sent),1)
            self.assertIn('fastkjørt',self.sent[0]['message'])
    async def test_lock_disable_and_test_without_actuating(self):
        r=self.runtime('lock_jammed',entity='lock.front',jam_seconds=60)
        self.hass.states.async_set('lock.front','jammed')
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            r.arm_jam_timer();due=later.call_args.args[2]
            await r.toggle('enabled',False);await due(dt_util.utcnow());self.assertFalse(self.sent)
            await r.test('test');self.assertIn('TEST:',self.sent[0]['message'])
    async def test_start_only_on_core_start_not_reload(self):
        r=self.runtime('ha_start',startup_delay=15)
        self.hass.set_state(CoreState.running)
        with patch.object(type(self.hass.bus),'async_listen_once') as listen:
            r.listen();listen.assert_not_called()
        self.assertFalse(self.sent)
        self.hass.set_state(CoreState.not_running)
        with patch.object(type(self.hass.bus),'async_listen_once',return_value=Mock()) as listen:
            r.listen();self.assertEqual(listen.call_args.args[0],EVENT_HOMEASSISTANT_STARTED)
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            event=Event(EVENT_HOMEASSISTANT_STARTED)
            await r.homeassistant_started(event)
            self.assertEqual(later.call_args.args[1],15)
            await later.call_args.args[2](dt_util.utcnow())
            self.assertIn(dt_util.as_local(event.time_fired).strftime('%d.%m.%Y kl %H:%M:%S'),self.sent[0]['message'])
    async def test_start_delay_cancelled_on_unload(self):
        r=self.runtime('ha_start',startup_delay=15)
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            await r.homeassistant_started(Event(EVENT_HOMEASSISTANT_STARTED))
            r.close();later.return_value.assert_called_once()
            await later.call_args.args[2](dt_util.utcnow())
            self.assertFalse(self.sent)

if __name__=='__main__':unittest.main()
