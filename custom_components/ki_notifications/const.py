DOMAIN = 'ki_notifications'
KINDS = {'family': 'Familie – hjemme/borte', 'vacuum': 'Støvsuger', 'alarm': 'Alarm', 'state': 'Egendefinert tilstandsvarsel', 'ruter': 'Ruter – fra skolen'}
PEOPLE = {'rune': 'Rune', 'cybele': 'Cybele', 'sebastian': 'Sebastian'}
INVALID = {'unknown', 'unavailable', ''}

def flags(kind):
    if kind == 'family':
        return {f'{p}_{e}': f'{n} – {label}' for p, n in PEOPLE.items() for e, label in [('home', 'kom hjem'), ('away', 'forlot huset')]}
    if kind == 'alarm':
        return {'armed': 'Alarm aktivert', 'disarmed': 'Alarm deaktivert', 'triggered': 'Alarm utløst'}
    return {'enabled': 'Varsling'}
