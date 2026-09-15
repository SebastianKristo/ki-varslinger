from homeassistant.components.button import ButtonEntity
from .const import DOMAIN, SECURITY_KINDS
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r=hass.data[DOMAIN][entry.entry_id]
    if r.kind == 'autolock':
        async_add_entities([KIButton(r, 'autolock_check', 'Kontroller autolås'),
                            KIButton(r, 'autolock_start', 'Test autolås – lås etter ventetid')])
        return
    if r.kind == 'door_blink':
        async_add_entities([KIButton(r, 'blink', 'Test blinking')])
        return
    if r.kind in SECURITY_KINDS:
        return
    tests={'home':'Test kom hjem','away':'Test forlot huset'} if r.kind=='family' else {'armed':'Test aktivering','disarmed':'Test deaktivering','triggered':'Test utløst alarm'} if r.kind=='alarm' else {'test':'Send testvarsel'}
    async_add_entities(KIButton(r,k,n) for k,n in tests.items())

class KIButton(KIEntity, ButtonEntity):
    def __init__(self,r,key,name):
        super().__init__(r,'button_'+key,name,'mdi:bell-ring-outline')
        self.key=key
        if key == 'blink': self._attr_icon = 'mdi:lightbulb-alert-outline'
        elif key == 'autolock_check': self._attr_icon = 'mdi:clipboard-check-outline'
        elif key == 'autolock_start': self._attr_icon = 'mdi:timer-lock-outline'
    async def async_press(self):
        await self.runtime.test(self.key)
