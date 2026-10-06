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


# --- Live Activities ---------------------------------------------------------

def states_set(text, default=''):
    """'on, Charging' -> {'on', 'charging'}. Tomt felt gir standardverdiene."""
    values = {x.strip().lower() for x in str(text or '').split(',') if x.strip()}
    return values or {x.strip().lower() for x in default.split(',') if x.strip()}

def number(value):
    try:
        n = float(str(value).replace(',', '.').replace('%', '').strip())
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None

def chip_text(text, limit=7):
    """Teksten i statuslinjebrikken på Android. Lengre tekst gjør at bare ikonet vises."""
    text = str(text or '').strip()
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'

def clock_seconds(value):
    """'1:05:30' eller '05:30' -> sekunder. Brukes for timer-attributter."""
    parts = str(value).strip().split(':')
    if not 2 <= len(parts) <= 3:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if any(not math.isfinite(n) or n < 0 for n in nums):
        return None
    seconds = 0.0
    for n in nums:
        seconds = seconds * 60 + n
    return seconds

UNIT_SECONDS = {'s': 1, 'sec': 1, 'sek': 1, 'min': 60, 'm': 60, 'h': 3600, 't': 3600, 'd': 86400}

def end_timestamp(value, unit, device_class, now, parse=None):
    """Når er det ferdig? Unix-tid, eller None hvis kilden ikke gir et brukbart svar.

    Tåler en tidsstempel-sensor (slutt-tidspunkt), et tall med enhet (gjenstående
    tid) og klokkeformat (1:05:30). Et tall uten enhet tolkes som minutter, som er
    det vanlige for «remaining time»-sensorer. Tid som allerede er ute gir None.
    """
    text = str(value).strip()
    if device_class == 'timestamp' or 'T' in text or (text.count('-') >= 2 and ':' in text):
        moment = parse(text) if parse else None
        if moment is None:
            return None
        end = moment.timestamp()
    else:
        n = number(text)
        if n is not None:
            seconds = n * UNIT_SECONDS.get(str(unit or 'min').strip().lower(), 60)
        else:
            seconds = clock_seconds(text)
        if seconds is None:
            return None
        end = now + seconds
    return end if end > now else None
