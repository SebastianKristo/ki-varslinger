"""Pure decision functions; no network or Home Assistant dependency."""
import math
from .const import INVALID

def alarm_event(old, new):
    if old in INVALID or new in INVALID or old == new:
        return None
    if new == 'triggered':
        return 'triggered'
    if new == 'disarmed':
        return 'disarmed'
    if new.startswith('armed_') and not old.startswith('armed_') and old not in {'triggered', 'pending'}:
        return 'armed'
    return None

def presence_event(old, new):
    return {('off', 'on'): 'home', ('on', 'off'): 'away'}.get((old, new))

def minutes(value):
    try:
        n = float(str(value).replace(' min', '').strip())
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None

def choose_departure(candidates, earliest):
    usable = [c for c in candidates if c['due'] is not None and c['due'] >= earliest]
    return min(usable, key=lambda c: c['due']) if usable else None

def vacuum_actions(state):
    if state == 'cleaning':
        return [('pause', 'Pause', 'pause.fill'), ('stop', 'Stopp', 'stop.fill'), ('return_to_base', 'Hjem', 'house.fill')]
    if state in {'paused', 'idle'}:
        return [('start', 'Start', 'play.fill'), ('stop', 'Stopp', 'stop.fill'), ('return_to_base', 'Hjem', 'house.fill')]
    if state == 'returning':
        return [('stop', 'Stopp', 'stop.fill')]
    return []
