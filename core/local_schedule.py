"""Validated, persistent local schedules; no provider calls or background threads."""
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.book_types import require_book_type
from core.grade_policy import ACTIVE_GRADE_BANDS


def validate_schedule(raw):
    """Accept only explicit user settings; reject coercions and impossible dates."""
    if not isinstance(raw, dict):
        raise ValueError('Schedule must be a JSON object.')
    fields = {'enabled', 'frequency', 'weekday', 'time', 'timezone', 'count', 'book_type', 'grade_band'}
    if set(raw) != fields:
        raise ValueError('Supply enabled, frequency, weekday, time, timezone, count, book_type and grade_band.')
    if type(raw['enabled']) is not bool:
        raise ValueError('enabled must be true or false.')
    if raw['frequency'] not in ('daily', 'weekly'):
        raise ValueError('Choose daily or weekly.')
    if type(raw['weekday']) is not int or not 0 <= raw['weekday'] <= 6:
        raise ValueError('Choose a weekday from Monday to Sunday.')
    if not isinstance(raw['time'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', raw['time']):
        raise ValueError('Time must use HH:MM.')
    if not isinstance(raw['timezone'], str) or len(raw['timezone']) > 80:
        raise ValueError('Choose a valid timezone, for example Africa/Casablanca.')
    try:
        ZoneInfo(raw['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Choose a valid timezone, for example Africa/Casablanca.') from None
    if type(raw['count']) is not int or not 1 <= raw['count'] <= 20:
        raise ValueError('Books per run must be from 1 to 20.')
    require_book_type(raw['book_type'])
    if raw['grade_band'] not in ('rotate', *ACTIVE_GRADE_BANDS):
        raise ValueError('Choose rotating grades, grades 3–4 or grades 5–6.')
    return {key: raw[key] for key in sorted(fields)}


def schedule_due(now, state, settings):
    """Only today's eligible slot can run; failed/interrupted attempts stay consumed."""
    local = now.astimezone(ZoneInfo(settings['timezone']))
    return (settings['enabled']
            and (settings['frequency'] == 'daily' or local.weekday() == settings['weekday'])
            and local.strftime('%H:%M') >= settings['time']
            and state.get('local_daily', {}).get('attempted_on') != local.date().isoformat())


def next_run(now, state, settings):
    """Show a due slot or the next local wall-clock slot, including DST changes."""
    if not settings['enabled']:
        return None
    local = now.astimezone(ZoneInfo(settings['timezone']))
    if schedule_due(local, state, settings):
        return 'Due now; waiting for the worker'
    hour, minute = map(int, settings['time'].split(':'))
    for offset in range(8):
        day = local.date() + timedelta(days=offset)
        if settings['frequency'] == 'weekly' and day.weekday() != settings['weekday']:
            continue
        if state.get('local_daily', {}).get('attempted_on') == day.isoformat():
            continue
        slot = datetime(day.year, day.month, day.day, hour, minute, tzinfo=local.tzinfo)
        if slot > local:
            return slot.isoformat(timespec='minutes')
    return None
