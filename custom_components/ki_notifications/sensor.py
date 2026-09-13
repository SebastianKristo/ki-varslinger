from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([KIStatus(hass.data[DOMAIN][entry.entry_id])])

class KIStatus(KIEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self,r):
        super().__init__(r,'status','Varslingsstatus','mdi:message-badge-outline')
    @property
    def native_value(self):
        return 'Sendefeil' if self.runtime.last_error else 'Datakildefeil' if self.runtime.last_source_error else 'Sendt' if self.runtime.last_sent else 'Klar'
    @property
    def extra_state_attributes(self):
        r=self.runtime
        return {'siste_melding':r.last_message,'siste_sendt':r.last_sent,'siste_feil':r.last_error,'datakildefeil':r.last_source_error,'type':r.kind, 'hovedbryter':r.master_enabled}
