"""Run with a Home Assistant installation: python -m unittest discover -s tests -v."""
import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from homeassistant.core import HomeAssistant, State, Event
from custom_components.ki_notifications import Runtime
from custom_components.ki_notifications.config_flow import schema, errors, Flow, Options
from custom_components.ki_notifications.logic import alarm_event, presence_event, choose_departure, minutes
from custom_components.ki_notifications.const import PEOPLE, KINDS

class Logic(unittest.TestCase):
    def test_alarm_cycle(self):
        self.assertIsNone(alarm_event('disarmed','arming'))
        self.assertEqual(alarm_event('arming','armed_away'),'armed')
        self.assertEqual(alarm_event('pending','triggered'),'triggered')
        self.assertEqual(alarm_event('triggered','disarmed'),'disarmed')
        self.assertIsNone(alarm_event('triggered','armed_away'))
        self.assertIsNone(alarm_event('armed_home','armed_away'))
    def test_recovery_does_not_notify(self):
        self.assertIsNone(alarm_event('unavailable','triggered'))
        self.assertIsNone(presence_event('unknown','on'))
    def test_departures_reject_missing_and_unreachable(self):
        self.assertIsNone(minutes('unavailable'))
        self.assertIsNone(minutes('nan'))
        self.assertEqual(minutes('0 min'),0)
        values=[{'due':2},{'due':10},{'due':None},{'due':6}]
        self.assertEqual(choose_departure(values,4),{'due':6})
        self.assertIsNone(choose_departure(values,11))

class Integration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.hass=HomeAssistant(self.temp.name)
        self.sent=[]
        async def notify(call):
            self.sent.append((call.service,dict(call.data)))
        self.hass.services.async_register('notify','mobile_app_iphone',notify)
        self.hass.services.async_register('notify','mobile_app_pixel',notify)
        self.runtimes=[]
    async def asyncTearDown(self):
        for r in self.runtimes:r.close()
        await self.hass.async_block_till_done()
        self.temp.cleanup()
    def runtime(self,kind,**cfg):
        data={'kind':kind,'name':'Test','ios_targets':['mobile_app_iphone'],'android_targets':['mobile_app_pixel'],'sound':'kom_hjem.wav','sound_away':'forlot_huset.wav','channel':'KI Test',**cfg}
        if kind=='family': data.update({p:f'switch.{p}' for p in PEOPLE})
        r=Runtime(self.hass,SimpleNamespace(data=data,options={},entry_id='test_'+kind))
        self.runtimes.append(r)
        return r
    async def change(self,r,entity,old,new):
        await r.changed(Event('state_changed',{'old_state':State(entity,old),'new_state':State(entity,new),'entity_id':entity}))
    async def test_forms_construct(self):
        for kind in KINDS:
            self.assertGreater(len(schema(self.hass,kind,{}).schema),5)
    async def test_config_flow_creates_entry(self):
        flow=Flow();flow.hass=self.hass
        result=await flow.async_step_user({'kind':'alarm'})
        self.assertEqual(result['type'],'form')
        data={'name':'Alarm','ios_targets':['mobile_app_iphone'],'android_targets':[], 'entity':'alarm_control_panel.home'}
        result=await flow.async_step_settings(data)
        self.assertEqual(result['type'],'create_entry')
        self.assertEqual(result['data']['kind'],'alarm')
    async def test_options_clear_optional_entity(self):
        form=schema(self.hass,'alarm',{'triggered_sensor':'binary_sensor.old'})
        data=form({'name':'Alarm','ios_targets':['mobile_app_iphone'],'android_targets':[], 'entity':'alarm_control_panel.home'})
        self.assertNotIn('triggered_sensor',data)
    async def test_zone_filter(self):
        self.hass.states.async_set('zone.skole','0',{'latitude':59.9,'longitude':10.7,'radius':100,'friendly_name':'Skole'})
        self.hass.states.async_set('person.sebastian','not_home',{'latitude':59.0,'longitude':10.7})
        r=self.runtime('state',entity='binary_sensor.test',from_state='off',to_state='on',message='Test',icon='mdi:bell',zones=['zone.skole'],zone_person='person.sebastian')
        await self.change(r,'binary_sensor.test','off','on')
        self.assertEqual(len(self.sent),0)
        self.hass.states.async_set('person.sebastian','Skole',{'latitude':59.9,'longitude':10.7})
        await self.change(r,'binary_sensor.test','off','on')
        self.assertEqual(len(self.sent),2)
    async def test_platform_entities_construct(self):
        from custom_components.ki_notifications import switch, button, sensor
        from custom_components.ki_notifications.const import DOMAIN
        r=self.runtime('family');self.hass.data[DOMAIN]={r.entry.entry_id:r}
        entities=[]
        for platform in [switch,button,sensor]:
            await platform.async_setup_entry(self.hass,r.entry,entities.extend)
        self.assertEqual(len(entities),9)
        self.assertEqual(len({e.unique_id for e in entities}),9)
        self.assertTrue(entities[0].is_on)
        self.assertEqual(entities[-1].native_value,'Klar')
    async def test_reject_invalid_recipients(self):
        self.assertEqual(errors(self.hass,'alarm',{}),{'base':'no_targets'})
        self.assertEqual(errors(self.hass,'alarm',{'ios_targets':['missing']}),{'base':'missing_service'})
    async def test_family_exact_message_and_sound(self):
        r=self.runtime('family')
        await self.change(r,'switch.rune','on','off')
        self.assertEqual(len(self.sent),2)
        self.assertEqual(self.sent[0][1]['message'],'Rune forlot huset.')
        self.assertEqual(self.sent[0][1]['data']['push']['sound'],'forlot_huset.wav')
    async def test_independent_flags_and_test_bypass(self):
        r=self.runtime('family');r.enabled['rune_home']=False
        await self.change(r,'switch.rune','off','on')
        self.assertEqual(len(self.sent),0)
        await self.change(r,'switch.rune','on','off')
        self.assertEqual(len(self.sent),2)
        await r.test('home')
        self.assertEqual(len(self.sent),4)
    async def test_failure_on_one_phone_does_not_block_other(self):
        async def fail(call): raise RuntimeError('Test error')
        self.hass.services.async_register('notify','mobile_app_iphone',fail)
        r=self.runtime('family')
        with self.assertLogs('custom_components.ki_notifications',level='ERROR'):
            await r.test('home')
        self.assertEqual(len(self.sent),1)
        self.assertIn('Test error',r.last_error)
        self.assertIsNotNone(r.last_sent)
    async def test_alarm_critical_only_real_trigger(self):
        r=self.runtime('alarm',entity='alarm_control_panel.home',critical=True)
        await r.test('triggered')
        self.assertNotEqual(self.sent[0][1]['data']['push']['interruption-level'],'critical')
        await self.change(r,'alarm_control_panel.home','armed_away','triggered')
        self.assertEqual(self.sent[-2][1]['data']['push']['interruption-level'],'critical')
    async def test_homey_alarm(self):
        r=self.runtime('alarm',entity='switch.alarm',triggered_sensor='binary_sensor.alarm')
        await self.change(r,'switch.alarm','off','on')
        await self.change(r,'binary_sensor.alarm','off','on')
        self.assertEqual(len(self.sent),4)
        self.assertEqual(self.sent[0][1]['message'],'Alarm aktivert.')
        self.assertEqual(self.sent[2][1]['message'],'Alarm utløst.')
    async def test_vacuum_pause_updates_same_tag_and_start_button(self):
        r=self.runtime('vacuum',entity='vacuum.robot')
        self.hass.states.async_set('vacuum.robot','cleaning')
        await self.change(r,'vacuum.robot','docked','cleaning')
        tag=self.sent[0][1]['data']['tag']
        action=self.sent[0][1]['data']['actions'][0]['action']
        commands=[]
        async def command(call):commands.append(call.service)
        self.hass.services.async_register('vacuum','pause',command)
        await r.action(Event('mobile_app_notification_action',{'action':action}))
        self.assertEqual(commands,['pause'])
        self.assertEqual(self.sent[-2][1]['data']['tag'],tag)
        self.assertEqual(self.sent[-2][1]['data']['actions'][0]['title'],'Start')
        self.assertEqual(self.sent[-2][1]['data']['push']['sound'],'none')
        await r.action(Event('mobile_app_notification_action',{'action':'KI_invalid_pause'}))
        self.assertEqual(commands,['pause'])
        self.hass.services.async_register('vacuum','start',command)
        start=self.sent[-2][1]['data']['actions'][0]['action']
        # HA still reports cleaning; Start must nevertheless work after Pause.
        await r.action(Event('mobile_app_notification_action',{'action':start}))
        self.assertEqual(commands,['pause','start'])
        await r.action(Event('mobile_app_notification_action',{'action':action}))
        self.assertEqual(commands,['pause','start'])
    async def test_vacuum_test_has_no_controls(self):
        r=self.runtime('vacuum',entity='vacuum.robot')
        self.hass.states.async_set('vacuum.robot','cleaning')
        await r.test('test')
        self.assertEqual(self.sent[0][1]['data']['actions'],[])
        self.assertNotIn('tag',self.sent[0][1]['data'])
    async def test_store_flags(self):
        r=self.runtime('family')
        await r.toggle('rune_home',False)
        other=self.runtime('family');await other.load()
        self.assertFalse(other.enabled['rune_home'])
        self.assertTrue(other.enabled['rune_away'])
    async def test_actual_listener_unsubscribes(self):
        r=self.runtime('family')
        self.hass.states.async_set('switch.rune','off')
        await self.hass.async_block_till_done()
        r.listen()
        self.hass.states.async_set('switch.rune','on')
        await self.hass.async_block_till_done()
        self.assertEqual(len(self.sent),2)
        r.close()
        self.hass.states.async_set('switch.rune','off')
        await self.hass.async_block_till_done()
        self.assertEqual(len(self.sent),2)

if __name__=='__main__':unittest.main()
