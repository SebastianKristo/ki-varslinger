from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from .const import DOMAIN, SECURITY_KINDS
from .entity import KIEntity

async def async_setup_entry(hass, entry, async_add_entities):
    r=hass.data[DOMAIN][entry.entry_id]
    entities=[KIStatus(r)]
    if r.kind == 'face_unlock':
        entities.append(LastUnlock(r))
    async_add_entities(entities)

class KIStatus(KIEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self,r):
        super().__init__(r,'status','Sikkerhetsstatus' if r.kind in SECURITY_KINDS else 'Varslingsstatus','mdi:shield-check-outline' if r.kind in SECURITY_KINDS else 'mdi:message-badge-outline')
    @property
    def native_value(self):
        if self.runtime.security_error:
            return 'Sikkerhetsfeil'
        if self.runtime.kind in SECURITY_KINDS:
            return 'Aktiv' if self.runtime.enabled['enabled'] else 'Av'
        return 'Sendefeil' if self.runtime.last_error else 'Datakildefeil' if self.runtime.last_source_error else 'Sendt' if self.runtime.last_sent else 'Klar'
    @property
    def extra_state_attributes(self):
        r=self.runtime
        return {'siste_melding':r.last_message,'siste_sendt':r.last_sent,'siste_feil':r.last_error,'datakildefeil':r.last_source_error,'type':r.kind, 'hovedbryter':r.master_enabled, 'sikkerhetsfeil':r.security_error}

class LastUnlock(KIEntity, SensorEntity):
    def __init__(self,r):
        super().__init__(r,'last_unlock_person','Sist låst opp av','mdi:face-recognition')
    @property
    def native_value(self):
        return self.runtime.last_unlock_person
    @property
    def extra_state_attributes(self):
        return {'bekreftet_tid':self.runtime.last_unlock_at, 'kilde':'Lokal webhook; bekreftet ulåst tilstand'}
