from homeassistant.components.button import ButtonEntity
from .const import DOMAIN, SECURITY_KINDS
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r=hass.data[DOMAIN][entry.entry_id]
    if r.kind in SECURITY_KINDS:
        return
    tests={'home':'Test kom hjem','away':'Test forlot huset'} if r.kind=='family' else {'armed':'Test aktivering','disarmed':'Test deaktivering','triggered':'Test utløst alarm'} if r.kind=='alarm' else {'test':'Send testvarsel'}
    async_add_entities(KIButton(r,k,n) for k,n in tests.items())

class KIButton(KIEntity, ButtonEntity):
    def __init__(self,r,key,name):
        super().__init__(r,'button_'+key,name,'mdi:bell-ring-outline')
        self.key=key
    async def async_press(self):
        await self.runtime.test(self.key)
