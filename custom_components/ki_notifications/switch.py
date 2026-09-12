from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN, flags
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(KISwitch(r,k,n) for k,n in flags(r.kind).items())

class KISwitch(KIEntity, SwitchEntity):
    def __init__(self,r,key,name):
        super().__init__(r,'switch_'+key,name,'mdi:bell-outline')
        self.key=key
    @property
    def is_on(self):
        return self.runtime.enabled[self.key]
    async def async_turn_on(self, **kwargs):
        await self.runtime.toggle(self.key,True)
    async def async_turn_off(self, **kwargs):
        await self.runtime.toggle(self.key,False)
