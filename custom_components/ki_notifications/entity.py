from homeassistant.helpers.entity import Entity, DeviceInfo
from .const import DOMAIN

class KIEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, runtime, key, name, icon):
        self.runtime = runtime
        self._attr_unique_id = f'{runtime.entry.entry_id}_{key}'
        self._attr_name = name
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN,runtime.entry.entry_id)}, name=runtime.cfg['name'], manufacturer='KI', model='KI Varslinger og sikkerhet', sw_version='2.1.0')

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.runtime.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.runtime.listeners.discard(self.async_write_ha_state))
