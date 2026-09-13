from homeassistant.components.number import NumberEntity, NumberMode
from .const import DOMAIN
from .entity import KIEntity

async def async_setup_entry(hass,entry,async_add_entities):
    r=hass.data[DOMAIN][entry.entry_id]
    if r.kind=='autolock' and not r.cfg.get('delay_helper'):
        async_add_entities([AutolockDelay(r)])

class AutolockDelay(KIEntity,NumberEntity):
    _attr_native_min_value=5
    _attr_native_max_value=3600
    _attr_native_step=1
    _attr_native_unit_of_measurement='s'
    _attr_mode=NumberMode.BOX
    def __init__(self,r):
        super().__init__(r,'autolock_delay','Ventetid før autolås','mdi:timer-lock-outline')
    @property
    def native_value(self):
        return self.runtime.autolock_seconds
    async def async_set_native_value(self,value):
        await self.runtime.set_autolock_delay(value)
