"""One configuration entry per notification rule, editable through Options."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import DOMAIN, KINDS, PEOPLE


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
    add('ios_targets', phone, [x for x in services if x == 'mobile_app_sebastian_iphone_17_pro'])
    add('android_targets', phone, [x for x in services if x == 'mobile_app_sebastian_pixel_9_pro_fold'])
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


def errors(hass, kind, data):
    targets = data.get('ios_targets', []) + data.get('android_targets', [])
    if not targets:
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
        err = errors(self.hass, kind, user_input) if user_input is not None else {}
        if user_input is not None and not err:
            return self.async_create_entry(title='', data=user_input)
        saved = dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(step_id='init', data_schema=schema(self.hass, kind, user_input if user_input is not None else saved), errors=err)
