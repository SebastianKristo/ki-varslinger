import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from aiohttp.test_utils import make_mocked_request
from homeassistant.components import webhook
from homeassistant.core import Event,HomeAssistant,State
from homeassistant.exceptions import ConfigEntryError
from custom_components.ki_notifications import Runtime
from custom_components.ki_notifications.const import DOMAIN,PEOPLE
from custom_components.ki_notifications.config_flow import errors
from custom_components.ki_notifications import number,sensor,button

MODULE='custom_components.ki_notifications.security.'

class SecurityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.hass=HomeAssistant(self.tmp.name)
        self.calls=[];self.runtimes=[]
        async def service(call):self.calls.append((call.domain,call.service,dict(call.data)))
        for domain,actions in {'lock':['lock','unlock'],'alarm_control_panel':['alarm_arm_away','alarm_disarm'],'select':['select_option'],'switch':['turn_off','turn_on']}.items():
            for action in actions:self.hass.services.async_register(domain,action,service)
    async def asyncTearDown(self):
        for r in self.runtimes:r.close()
        await self.hass.async_block_till_done();self.tmp.cleanup()
    def runtime(self,kind,**cfg):
        data={'kind':kind,'name':'Test','entity':'lock.front','security_code':'test-code',**cfg}
        r=Runtime(self.hass,SimpleNamespace(entry_id='test_'+kind,data=data,options={}))
        self.runtimes.append(r);return r
    def auto(self,**cfg):
        return self.runtime('autolock',door_entity='sensor.door',door_open='open',door_closed='closed',autolock_delay=30,**cfg)
    def sync(self):
        self.hass.states.async_set('alarm_control_panel.alarm','disarmed')
        self.hass.states.async_set('select.homey','disarmed',{'options':['armed','disarmed']})
        return self.runtime('alarm_sync',entity='alarm_control_panel.alarm',homey_select='select.homey',homey_armed='armed',homey_disarmed='disarmed',alarm_mode='armed_away',privacy_switches=['switch.privacy'])
    def face(self,**cfg):
        return self.runtime('face_unlock',**{'webhook_'+p:'test-only-'+p+'-x'*20 for p in PEOPLE},**cfg)
    async def change(self,r,eid,old,new):
        state=State(eid,new)
        await r.changed(Event('state_changed',{'entity_id':eid,'old_state':State(eid,old) if old is not None else None,'new_state':state}))
    async def test_security_starts_disabled_and_has_no_test_actions(self):
        for r in [self.auto(),self.sync(),self.face()]:
            self.assertFalse(r.enabled['enabled'])
            self.hass.data[DOMAIN]={r.entry.entry_id:r};entities=[]
            await button.async_setup_entry(self.hass,r.entry,entities.extend)
            self.assertEqual(entities,[])
            await r.test('test')
        self.assertEqual(self.calls,[])
    async def test_autolock_close_timer_and_final_door_check(self):
        r=self.auto();await r.toggle('enabled',True)
        self.hass.states.async_set('lock.front','unlocked')
        self.hass.states.async_set('sensor.door','closed')
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            await self.change(r,'sensor.door','open','closed')
            self.assertAlmostEqual(later.call_args.args[1],30,delta=1)
            callback=later.call_args.args[2]
            self.hass.states.async_set('sensor.door','open')
            await callback(None)
            self.assertFalse(self.calls)
            self.hass.states.async_set('sensor.door','closed')
            await self.change(r,'sensor.door','open','closed')
            await later.call_args.args[2](None)
            self.assertEqual(self.calls[0][:2],('lock','lock'))
    async def test_autolock_cancels_reopen_unknown_and_disable(self):
        r=self.auto();await r.toggle('enabled',True)
        self.hass.states.async_set('lock.front','unlocked')
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            for cancellation in ['open','unavailable']:
                self.hass.states.async_set('sensor.door','closed')
                await self.change(r,'sensor.door','open','closed')
                due=later.call_args.args[2]
                await self.change(r,'sensor.door','closed',cancellation)
                await due(None)
                self.assertFalse(self.calls)
            await self.change(r,'sensor.door','open','closed');due=later.call_args.args[2]
            await r.toggle('enabled',False);await due(None);self.assertFalse(self.calls)
    async def test_autolock_does_not_lock_on_recovery_or_jammed_lock(self):
        r=self.auto();await r.toggle('enabled',True)
        self.hass.states.async_set('sensor.door','closed')
        self.hass.states.async_set('lock.front','jammed')
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            await self.change(r,'sensor.door','unavailable','closed');later.assert_not_called()
            await self.change(r,'sensor.door','open','closed')
            await later.call_args.args[2](None)
            self.assertFalse(self.calls);self.assertTrue(r.security_error)
    async def test_number_and_input_number(self):
        r=self.auto();self.hass.data[DOMAIN]={r.entry.entry_id:r};entities=[]
        await number.async_setup_entry(self.hass,r.entry,entities.extend)
        await entities[0].async_set_native_value(50)
        self.assertEqual(entities[0].native_value,50)
        other=self.auto();await other.load();self.assertEqual(other.autolock_seconds,50)
        with self.assertRaises(ValueError):await r.set_autolock_delay(0)
        helper=self.auto(delay_helper='input_number.delay');helper.enabled['enabled']=True
        self.hass.data[DOMAIN]={helper.entry.entry_id:helper};entities=[]
        await number.async_setup_entry(self.hass,helper.entry,entities.extend);self.assertFalse(entities)
        self.hass.states.async_set('sensor.door','closed');self.hass.states.async_set('input_number.delay','90')
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            await self.change(helper,'sensor.door','open','closed')
            self.assertAlmostEqual(later.call_args.args[1],90,delta=1)
            self.hass.states.async_set('input_number.delay','unavailable')
            await self.change(helper,'input_number.delay','90','unavailable')
            self.assertIsNone(helper.auto_cancel)
    async def test_alarmo_home_mode_echo_does_not_rearm_away(self):
        r=self.sync();await r.toggle('enabled',True)
        self.hass.states.async_set(r.cfg['entity'],'armed_home')
        await self.change(r,r.cfg['entity'],'arming','armed_home')
        self.assertEqual(self.calls[0][:2],('select','select_option'))
        self.assertEqual(self.calls[1][:2],('switch','turn_off'))
        self.hass.states.async_set('select.homey','armed',{'options':['armed','disarmed']})
        await self.change(r,'select.homey','disarmed','armed')
        self.assertFalse(any(d=='alarm_control_panel' for d,a,data in self.calls))
    async def test_homey_arm_disarm_and_confirmed_privacy(self):
        r=self.sync();await r.toggle('enabled',True)
        await self.change(r,'select.homey','disarmed','armed')
        self.assertEqual([x[:2] for x in self.calls],[('alarm_control_panel','alarm_arm_away')])
        self.hass.states.async_set(r.cfg['entity'],'armed_away')
        await self.change(r,r.cfg['entity'],'arming','armed_away')
        self.assertEqual(self.calls[-1][:2],('switch','turn_off'))
        await self.change(r,'select.homey','armed','disarmed')
        self.assertEqual(self.calls[-1][:2],('alarm_control_panel','alarm_disarm'))
        self.hass.states.async_set(r.cfg['entity'],'disarmed')
        await self.change(r,r.cfg['entity'],'armed_away','disarmed')
        self.assertEqual(self.calls[-1][:2],('switch','turn_on'))
    async def test_failed_arm_does_not_change_privacy_or_expose_code(self):
        r=self.sync();await r.toggle('enabled',True)
        async def fail(call):raise ValueError('secret '+call.data['code'])
        self.hass.services.async_register('alarm_control_panel','alarm_arm_away',fail)
        await self.change(r,'select.homey','disarmed','armed')
        self.assertFalse(self.calls);self.assertNotIn('test-code',r.security_error)
        self.assertFalse(r.sync_expected)
    async def test_sync_no_startup_reconciliation_and_timeout(self):
        r=self.sync();await r.toggle('enabled',True)
        r.listen();self.assertFalse(self.calls)
        with patch(MODULE+'async_call_later',return_value=Mock()) as later:
            await self.change(r,'select.homey','disarmed','armed')
            await later.call_args.args[2](None)
            self.assertIn('ikke bekreftet',r.security_error)
    async def test_webhooks_local_methods_collision_and_cleanup(self):
        r=self.face();r.security_register()
        self.assertEqual(len(self.hass.data['webhook']),3)
        for handler in self.hass.data['webhook'].values():
            self.assertTrue(handler['local_only']);self.assertNotIn('GET',handler['allowed_methods'])
        other=self.face()
        with self.assertRaises(ConfigEntryError):other.security_register()
        self.assertEqual(len(self.hass.data['webhook']),3)
        r.close();self.assertFalse(self.hass.data['webhook'])
    async def test_external_webhook_rejected_by_homeassistant(self):
        r=self.face();r.security_register();await r.toggle('enabled',True)
        self.hass.states.async_set('lock.front','locked')
        request=make_mocked_request('POST','/').clone(remote='203.0.113.10')
        with patch('homeassistant.components.webhook.is_cloud_connection',return_value=False),self.assertLogs('homeassistant.components.webhook',level='WARNING'):
            await webhook.async_handle_webhook(self.hass,r.cfg['webhook_sebastian'],request)
        self.assertFalse(self.calls)
    async def test_face_records_only_confirmed_person_and_persists(self):
        r=self.face();await r.toggle('enabled',True);self.hass.states.async_set('lock.front','locked')
        async def unlock(call):self.hass.states.async_set('lock.front','unlocked')
        self.hass.services.async_register('lock','unlock',unlock)
        response=await r.face_request('sebastian',SimpleNamespace(method='POST'))
        self.assertEqual(response.status,200);self.assertEqual(r.last_unlock_person,'Sebastian')
        other=self.face();await other.load();self.assertEqual(other.last_unlock_person,'Sebastian')
        self.hass.data[DOMAIN]={r.entry.entry_id:r};entities=[]
        await sensor.async_setup_entry(self.hass,r.entry,entities.extend)
        self.assertEqual(entities[-1].native_value,'Sebastian')
        self.assertNotIn('test-code',str(entities[-1].extra_state_attributes))
    async def test_face_failure_head_get_and_disabled_never_attribute(self):
        r=self.face();self.hass.states.async_set('lock.front','locked')
        self.assertEqual((await r.face_request('rune',SimpleNamespace(method='POST'))).status,403)
        await r.toggle('enabled',True)
        self.assertEqual((await r.face_request('rune',SimpleNamespace(method='HEAD'))).status,200)
        self.assertEqual((await r.face_request('rune',SimpleNamespace(method='GET'))).status,405)
        self.assertFalse(self.calls)
        async def fail(call):raise ValueError('secret '+call.data['code'])
        self.hass.services.async_register('lock','unlock',fail)
        self.assertEqual((await r.face_request('rune',SimpleNamespace(method='POST'))).status,502)
        self.assertIsNone(r.last_unlock_person);self.assertNotIn('test-code',r.security_error)
    async def test_face_already_unlocked_does_not_claim_new_person(self):
        r=self.face();await r.toggle('enabled',True);r.last_unlock_person='Cybele'
        self.hass.states.async_set('lock.front','unlocked')
        response=await r.face_request('rune',SimpleNamespace(method='POST'))
        self.assertEqual(response.status,200);self.assertEqual(r.last_unlock_person,'Cybele');self.assertFalse(self.calls)
    async def test_face_no_confirmation_does_not_attribute(self):
        r=self.face();await r.toggle('enabled',True);self.hass.states.async_set('lock.front','locked')
        original=asyncio.wait_for
        async def wait(awaitable,timeout):
            if timeout==15:
                awaitable.cancel();raise TimeoutError
            return await original(awaitable,timeout)
        with patch(MODULE+'asyncio.wait_for',side_effect=wait):
            response=await r.face_request('cybele',SimpleNamespace(method='PUT'))
        self.assertEqual(response.status,504);self.assertIsNone(r.last_unlock_person)
    async def test_three_local_webhooks_attribute_their_own_person(self):
        r=self.face();r.security_register();await r.toggle('enabled',True)
        async def unlock(call):self.hass.states.async_set('lock.front','unlocked')
        self.hass.services.async_register('lock','unlock',unlock)
        with patch('homeassistant.components.webhook.is_cloud_connection',return_value=False):
            for key,name in PEOPLE.items():
                r.face_last_attempt=None
                self.hass.states.async_set('lock.front','locked')
                await self.hass.async_block_till_done()
                request=make_mocked_request('POST','/').clone(remote='192.168.1.20')
                response=await webhook.async_handle_webhook(self.hass,r.cfg['webhook_'+key],request)
                self.assertEqual(response.status,200)
                self.assertEqual(r.last_unlock_person,name)
    async def test_conflicting_alarm_confirmation_stops_echo(self):
        r=self.sync();await r.toggle('enabled',True)
        await self.change(r,'select.homey','disarmed','armed')
        count=len(self.calls)
        await self.change(r,r.cfg['entity'],'arming','armed_home')
        self.assertEqual(len(self.calls),count)
        self.assertFalse(r.sync_expected)
        self.assertIn('Motstridende',r.security_error)
    async def test_security_config_needs_no_phone_and_validates_states(self):
        r=self.auto()
        self.assertEqual(errors(self.hass,'autolock',r.cfg),{})
        self.assertEqual(errors(self.hass,'autolock',{**r.cfg,'door_closed':'open'}),{'base':'invalid_door_states'})

if __name__=='__main__':unittest.main()
