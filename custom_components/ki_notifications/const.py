DOMAIN = 'ki_notifications'
KINDS = {'family': 'Familie – hjemme/borte', 'vacuum': 'Støvsuger', 'alarm': 'Alarm', 'state': 'Egendefinert tilstandsvarsel', 'ruter': 'Ruter – fra skolen', 'weather_ai': 'Værmelding – AI', 'ha_start': 'Home Assistant startet', 'lock_jammed': 'Dørlås fastkjørt', 'autolock': 'Autolås', 'alarm_sync': 'Heimdall ↔ Alarmo', 'face_unlock': 'Ansiktsgjenkjenning – dørlås', 'door_blink': 'Dørlys – blink ved åpning'}
PEOPLE = {'rune': 'Rune', 'cybele': 'Cybele', 'sebastian': 'Sebastian'}
INVALID = {'unknown', 'unavailable', ''}

def flags(kind):
    if kind == 'family':
        return {f'{p}_{e}': f'{n} – {label}' for p, n in PEOPLE.items() for e, label in [('home', 'kom hjem'), ('away', 'forlot huset')]}
    if kind == 'alarm':
        return {'armed': 'Alarm aktivert', 'disarmed': 'Alarm deaktivert', 'triggered': 'Alarm utløst'}
    if kind in SECURITY_KINDS:
        return {'enabled': KINDS[kind]}
    return {'enabled': 'Varsling'}

SECURITY_KINDS = {'autolock', 'alarm_sync', 'face_unlock', 'door_blink'}
