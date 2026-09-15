"""Live interpretation of configured door and lock sources."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r = hass.data[DOMAIN][entry.entry_id]
    if r.kind in {'autolock', 'door_blink'}:
        async_add_entities([DoorReading(r, key, name, icon) for key, name, icon in [
            ('door_valid', 'Dørverdi gjenkjent', 'mdi:check-decagram-outline'),
            ('door_closed', 'Døren er lukket', 'mdi:door-closed'),
            ('lock_locked', 'Låsen er låst', 'mdi:lock-outline'),
        ]])

class DoorReading(KIEntity, BinarySensorEntity):
    def __init__(self, r, key, name, icon):
        super().__init__(r, key, name, icon)
        self.key = key

    @property
    def is_on(self):
        r = self.runtime
        if self.key == 'lock_locked':
            source = r.hass.states.get(r.cfg['entity'])
            return source.state == 'locked' if source and source.state in {'locked', 'unlocked'} else None
        source = r.hass.states.get(r.cfg['door_entity'])
        valid = bool(source and source.state in {r.cfg['door_open'], r.cfg['door_closed']})
        if self.key == 'door_valid':
            return valid
        return source.state == r.cfg['door_closed'] if valid else None

    @property
    def extra_state_attributes(self):
        r = self.runtime
        entity = r.cfg['entity'] if self.key == 'lock_locked' else r.cfg['door_entity']
        source = r.hass.states.get(entity)
        return {'kilde': entity, 'raverdi': source.state if source else None,
                'tolket_verdi': self.is_on,
                **({'forventet_apen': r.cfg['door_open'], 'forventet_lukket': r.cfg['door_closed']}
                   if self.key != 'lock_locked' else {})}
