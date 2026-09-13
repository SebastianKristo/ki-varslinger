"""One configuration entry per notification rule, editable through Options."""
import secrets
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, KINDS, PEOPLE, SECURITY_KINDS


def schema(hass, kind, saved):
    fields = {}
    def add(key, sel, default=None, required=True):
        value = saved.get(key, default)
        marker = vol.Required if required else vol.Optional
        if not required:
            fields[marker(key, description={'suggested_value': value}) if value is not None else marker(key)] = sel
        else:
            fields[marker(key, default=value) if value is not None else marker(key)] = sel
    text = selector.TextSelector()
    entity = lambda domains: selector.EntitySelector(selector.EntitySelectorConfig(domain=domains))
    multi = lambda domains: selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, multiple=True))
    services = sorted(k for k in hass.services.async_services().get('notify', {}) if k.startswith('mobile_app_'))
    phone = selector.SelectSelector(selector.SelectSelectorConfig(options=services, multiple=True, custom_value=True))
    add('name', text, KINDS[kind])
    if kind not in SECURITY_KINDS:
        add('ios_targets', phone, [x for x in services if x == 'mobile_app_sebastian_iphone_17_pro'])
        add('android_targets', phone, [x for x in services if x in (['mobile_app_sebastian_pixel_9_pro_fold', 'mobile_app_sebastian_oneplus_15'] if kind in {'weather_ai','ha_start','lock_jammed'} else ['mobile_app_sebastian_pixel_9_pro_fold'])])
        add('sound', text, 'default')
        add('sound_away', text, 'default')
        add('channel', text, 'KI Varsler')
    if kind == 'family':
        for p in PEOPLE:
            known = f'switch.{p}_posisjon_hjemme_borte'
            add(p, entity(['switch', 'input_boolean', 'binary_sensor']), known if hass.states.get(known) else None)
    elif kind == 'vacuum':
        known = 'vacuum.sir_sweeps_a_lot'
        add('entity', entity(['vacuum']), known if hass.states.get(known) else None)
        room = 'sensor.sir_sweeps_a_lot_current_room'
        add('room', entity(['sensor']), room if hass.states.get(room) else None, False)
        add('selected_rooms', multi(['input_boolean']), [s.entity_id for s in hass.states.async_all('input_boolean') if s.entity_id.startswith('input_boolean.sir_sweeps_a_lot_')])
    elif kind == 'alarm':
        add('entity', entity(['alarm_control_panel', 'switch', 'input_boolean']))
        add('triggered_sensor', entity(['binary_sensor', 'switch', 'input_boolean']), required=False)
        add('critical', selector.BooleanSelector(), False)
    elif kind == 'state':
        add('entity', selector.EntitySelector())
        add('from_state', text, 'off')
        add('to_state', text, 'on')
        add('message', text, 'Tilstanden ble endret.')
        add('icon', selector.IconSelector(), 'mdi:bell-ring-outline')
        add('zone_person', entity(['person', 'device_tracker']), required=False)
        add('zones', multi(['zone']), [])
    elif kind == 'autolock':
        known = 'lock.dorlas_blatann'
        add('entity', entity(['lock']), known if hass.states.get(known) else None)
        known = 'sensor.inngangsdor'
        add('door_entity', entity(['sensor','binary_sensor']), known if hass.states.get(known) else None)
        add('door_open', text, 'open')
        add('door_closed', text, 'closed')
        add('autolock_delay', selector.NumberSelector(selector.NumberSelectorConfig(min=5,max=3600,mode='box',unit_of_measurement='s')), 30)
        add('delay_helper', entity(['input_number']), required=False)
        add('security_code', selector.TextSelector(selector.TextSelectorConfig(type='password')), required=False)
    elif kind == 'alarm_sync':
        known = 'alarm_control_panel.alarm'
        add('entity', entity(['alarm_control_panel']), known if hass.states.get(known) else None)
        known = 'select.alarm_homealarm_state'
        add('homey_select', entity(['select']), known if hass.states.get(known) else None)
        add('homey_armed', text, 'armed')
        add('homey_disarmed', text, 'disarmed')
        add('alarm_mode', selector.SelectSelector(selector.SelectSelectorConfig(options=['armed_away','armed_home','armed_night','armed_vacation'])), 'armed_away')
        add('security_code', selector.TextSelector(selector.TextSelectorConfig(type='password')), required=False)
        add('privacy_switches', multi(['switch']), [x for x in ['switch.mellomgang_g5_turret_ultra_privacy_mode','switch.stue_g6_turret_privacy_mode'] if hass.states.get(x)])
        add('sync_timeout', selector.NumberSelector(selector.NumberSelectorConfig(min=10,max=600,mode='box',unit_of_measurement='s')), 120)
    elif kind == 'face_unlock':
        known = 'lock.dorlas_blatann'
        add('entity', entity(['lock']), known if hass.states.get(known) else None)
        add('security_code', selector.TextSelector(selector.TextSelectorConfig(type='password')), required=False)
        for person in PEOPLE:
            add('webhook_'+person, selector.TextSelector(selector.TextSelectorConfig(type='password')), secrets.token_urlsafe(32))
        add('allow_get', selector.BooleanSelector(), False)
        add('face_cooldown', selector.NumberSelector(selector.NumberSelectorConfig(min=1,max=120,mode='box',unit_of_measurement='s')), 10)
    elif kind == 'weather_ai':
        known = 'weather.forecast_home'
        add('weather_entity', entity(['weather']), known if hass.states.get(known) else None)
        add('at', selector.TimeSelector(), '08:00:00')
        add('weekdays', selector.SelectSelector(selector.SelectSelectorConfig(multiple=True, options=[{'value':k,'label':v} for k,v in [('mon','Mandag'),('tue','Tirsdag'),('wed','Onsdag'),('thu','Torsdag'),('fri','Fredag'),('sat','Lørdag'),('sun','Søndag')]])), ['mon','tue','wed','thu','fri','sat','sun'])
        known = 'switch.sebastian_posisjon_hjemme_borte'
        add('home_entity', entity(['switch','input_boolean','binary_sensor','person','device_tracker']), known if hass.states.get(known) else None)
        add('home_state', text, 'on')
        add('ai_entity', entity(['ai_task']), required=False)
    elif kind == 'ha_start':
        add('startup_delay', selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=300,mode='box',unit_of_measurement='s')), 15)
    elif kind == 'lock_jammed':
        known = 'lock.dorlas_blatann'
        add('entity', entity(['lock']), known if hass.states.get(known) else None)
        add('jam_seconds', selector.NumberSelector(selector.NumberSelectorConfig(min=1,max=3600,mode='box',unit_of_measurement='s')), 60)
    elif kind == 'ruter':
        add('trackers', multi(['person', 'device_tracker']), [s.entity_id for s in hass.states.async_all('device_tracker') if s.entity_id in ['device_tracker.sebastian_iphone_17_pro', 'device_tracker.sebastian_pixel_9_pro_fold']])
        add('zones', multi(['zone']), [s.entity_id for s in hass.states.async_all('zone') if s.entity_id.startswith('zone.skole')])
        add('calendar', entity(['calendar']), 'calendar.oslomet_timeplan' if hass.states.get('calendar.oslomet_timeplan') else None, False)
        add('tram_sensors', multi(['sensor']), [s.entity_id for s in hass.states.async_all('sensor') if s.entity_id in ['sensor.transport_frydenlund_platform_11484','sensor.transport_homansbyen_platform_8119','sensor.transport_homansbyen_platform_8120']])
        add('bus_sensors', multi(['sensor']), [s.entity_id for s in hass.states.async_all('sensor') if s.entity_id in ['sensor.transport_majorstuen_platform_g','sensor.transport_majorstuen_platform_j']])
        add('metro', entity(['sensor']), 'sensor.transport_majorstuen_platform_2' if hass.states.get('sensor.transport_majorstuen_platform_2') else None, False)
        add('directions', text, 'majorstuen,ljabru')
        for key, value in [('walk',4),('ride',7),('transfer',3),('before_end',5)]:
            add(key, selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=120,mode='box',unit_of_measurement='min')), value)
    return vol.Schema(fields)


def errors(hass, kind, data, entry_id=None):
    targets = data.get('ios_targets', []) + data.get('android_targets', [])
    if not targets and kind not in SECURITY_KINDS:
        return {'base': 'no_targets'}
    if any(not hass.services.has_service('notify', s) for s in targets):
        return {'base': 'missing_service'}
    if set(data.get('ios_targets', [])) & set(data.get('android_targets', [])):
        return {'base': 'duplicate_target'}
    if kind == 'family' and len({data[p] for p in PEOPLE}) != 3:
        return {'base': 'duplicate_source'}
    if kind == 'state' and data.get('zones') and not data.get('zone_person'):
        return {'base': 'missing_person'}
    if kind == 'ruter' and (not data.get('trackers') or not data.get('zones') or not data.get('tram_sensors')):
        return {'base': 'missing_ruter'}
    if kind == 'weather_ai' and not data.get('weekdays'):
        return {'base': 'no_weekdays'}
    if kind == 'autolock' and (data['door_open'] == data['door_closed'] or data['door_closed'] in ['unknown','unavailable','']):
        return {'base': 'invalid_door_states'}
    if kind == 'alarm_sync':
        source = hass.states.get(data['homey_select'])
        values = [data['homey_armed'],data['homey_disarmed']]
        if values[0] == values[1] or (source and any(v not in source.attributes.get('options',[]) for v in values)):
            return {'base': 'invalid_homey_options'}
    if kind == 'face_unlock':
        ids = [data['webhook_'+p] for p in PEOPLE]
        if len(set(ids)) != 3 or any(len(x)<16 or any(ch in x for ch in '/?#') for x in ids):
            return {'base': 'invalid_webhooks'}
        own = hass.data.get(DOMAIN,{}).get(entry_id)
        owned = {own.cfg.get('webhook_'+p) for p in PEOPLE} if own else set()
        if any(x in hass.data.get('webhook',{}) and x not in owned for x in ids):
            return {'base': 'webhook_in_use'}
        manager = getattr(hass,'config_entries',None)
        if manager:
            for entry in manager.async_entries(DOMAIN):
                if entry.entry_id != entry_id and entry.data.get('kind') == 'face_unlock':
                    cfg = entry.options or entry.data
                    if any(cfg.get('webhook_'+p) in ids for p in PEOPLE):
                        return {'base':'webhook_in_use'}
    return {}


class Flow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.kind = user_input['kind']
            return await self.async_step_settings()
        return self.async_show_form(step_id='user', data_schema=vol.Schema({vol.Required('kind'): selector.SelectSelector(selector.SelectSelectorConfig(options=[{'value':k,'label':v} for k,v in KINDS.items()]))}))

    async def async_step_settings(self, user_input=None):
        err = errors(self.hass, self.kind, user_input) if user_input is not None else {}
        if user_input is not None and not err:
            return self.async_create_entry(title=user_input['name'], data={'kind':self.kind, **user_input})
        return self.async_show_form(step_id='settings', data_schema=schema(self.hass, self.kind, user_input or {}), errors=err)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return Options()


class Options(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        kind = self.config_entry.data['kind']
        err = errors(self.hass, kind, user_input, self.config_entry.entry_id) if user_input is not None else {}
        if user_input is not None and not err:
            return self.async_create_entry(title='', data=user_input)
        saved = dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(step_id='init', data_schema=schema(self.hass, kind, user_input if user_input is not None else saved), errors=err)
