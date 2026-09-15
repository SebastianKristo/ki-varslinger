from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN, flags
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r = hass.data[DOMAIN][entry.entry_id]
    choices = flags(r.kind)
    entities = [KISwitch(r,k,n) for k,n in choices.items()]
    if len(choices) > 1:
        entities.insert(0, KISwitch(r, 'master', 'Alle varsler'))
    async_add_entities(entities)

class KISwitch(KIEntity, SwitchEntity):
    def __init__(self,r,key,name):
        super().__init__(r,'switch_'+key,name,'mdi:bell-outline')
        self.key=key
        if r.kind == 'door_blink':
            self._attr_icon = 'mdi:lightbulb-alert-outline'
        if key == 'master':
            self._attr_icon = 'mdi:bell-cog-outline'
    @property
    def is_on(self):
        return self.runtime.master_enabled if self.key == 'master' else self.runtime.enabled[self.key]
    async def async_turn_on(self, **kwargs):
        await self.runtime.toggle(self.key,True)
    async def async_turn_off(self, **kwargs):
        await self.runtime.toggle(self.key,False)
