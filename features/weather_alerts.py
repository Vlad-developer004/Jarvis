"""Proactive weather voice alerts, unprompted:
- once a day when current conditions turn dangerous (storm, blizzard, extreme temp/wind);
- once a day per kind for what is coming in the next hours (frost, a sharp change tomorrow, strong wind, a downpour);
- an hour before a calendar event when rain is expected at that time.
Reuses the HUD's already-fresh weather cache (actions.weather.get_current_conditions) for the place and the current values."""
import json
import os
import threading
import time
from datetime import date, datetime
from core.system import module_enabled
from core.safe import swallow as _swallow

LOG_DIR = os.path.join('logs')
LOG_FILE = os.path.join(LOG_DIR, 'last_weather_alert.txt')
OUTLOOK_FILE = os.path.join(LOG_DIR, 'last_weather_outlook.json')
_QUIET_BEFORE_HOUR, _QUIET_FROM_HOUR = 8, 22      # no look-ahead warnings at night
_EVENT_WINDOW_MIN = (35, 95)                       # minutes before an event in which the rain check runs
_announced_events: set[str] = set()
_CHECK_INTERVAL_SEC = 1800
_SEVERE_KEYWORDS_RU = ('гроза', 'ливен', 'метель', 'вьюг')
_SEVERE_KEYWORDS_UK = ('гроза', 'злив', 'хуртовин', 'завірюх')


def _read_last_date() -> str:
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        _swallow()
    return ''


def _write_today() -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(date.today().isoformat())
    except Exception:
        _swallow()


def _is_severe(desc: str, temp: float, wind: float, lang: str) -> bool:
    d = (desc or '').lower()
    keywords = _SEVERE_KEYWORDS_UK if lang == 'uk' else _SEVERE_KEYWORDS_RU
    if any(k in d for k in keywords):
        return True
    if temp <= -15 or temp >= 35:
        return True
    if wind >= 15:
        return True
    return False


def _read_outlook_keys() -> list[str]:
    try:
        with open(OUTLOOK_FILE, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return list(d.get('keys', [])) if d.get('date') == date.today().isoformat() else []
    except Exception:
        return []


def _write_outlook_keys(keys: list[str]) -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(OUTLOOK_FILE, 'w', encoding='utf-8') as f:
            json.dump({'date': date.today().isoformat(), 'keys': keys}, f)
    except Exception:
        _swallow()


def _severe_step(handler) -> None:
    if _read_last_date() == date.today().isoformat():
        return
    from actions.weather import get_current_conditions
    from core.i18n import get_language
    cond = get_current_conditions()
    if not cond:
        return
    lang = get_language()
    desc = cond.get('desc', '')
    temp = cond.get('temp', 0)
    wind = cond.get('wind', 0)
    if not _is_severe(desc, temp, wind, lang):
        return
    from core.address import get_address as _ga
    if lang == 'uk':
        msg = f'{_ga()}, попередження: зараз {desc.lower()}, будьте обережні.'
    else:
        msg = f'{_ga()}, предупреждение: сейчас {desc.lower()}, будьте осторожны.'
    handler.speak(msg)
    _write_today()


def _outlook_step(handler) -> None:
    """What the next hours bring, each kind of warning once a day and not at night."""
    if not (_QUIET_BEFORE_HOUR <= datetime.now().hour < _QUIET_FROM_HOUR):
        return
    from actions.weather import get_current_conditions
    from actions.weather_extra import check_outlook
    from core.i18n import get_language
    cond = get_current_conditions()
    if not cond or cond.get('lat') is None:
        return
    sent = _read_outlook_keys()
    new = [(k, t) for k, t in check_outlook(cond['lat'], cond['lon'], get_language()) if k not in sent]
    if not new:
        return
    from core.address import get_address as _ga
    handler.speak(f'{_ga()}, ' + ' '.join(t for _, t in new))
    _write_outlook_keys(sent + [k for k, _ in new])


def _event_step(handler) -> None:
    """An hour before the next timed calendar event: say so if it is going to rain then."""
    if not module_enabled('calendar_ics'):
        return
    from actions.calendar_ics import next_event_dt
    ev = next_event_dt()
    if not ev:
        return
    dt, title = ev
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    minutes = (dt - now).total_seconds() / 60
    key = f'{dt.isoformat()}|{title}'
    if not (_EVENT_WINDOW_MIN[0] <= minutes <= _EVENT_WINDOW_MIN[1]) or key in _announced_events:
        return
    from actions.weather import get_current_conditions
    from actions.weather_extra import rain_chance_at
    from core.i18n import get_language
    cond = get_current_conditions()
    if not cond or cond.get('lat') is None:
        return
    _announced_events.add(key)          # one check per event, whatever it finds
    local = dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    res = rain_chance_at(cond['lat'], cond['lon'], local)
    if not res or (res[0] < 50 and res[1] < 0.5):
        return
    from core.address import get_address as _ga
    at = local.strftime('%H:%M')
    if get_language() == 'uk':
        handler.speak(f'{_ga()}, до події «{title}» о {at} очікується дощ, візьміть парасольку.')
    else:
        handler.speak(f'{_ga()}, к событию «{title}» в {at} ожидается дождь, возьмите зонт.')


def _alert_loop(handler) -> None:
    while True:
        time.sleep(_CHECK_INTERVAL_SEC)
        if not module_enabled('morning_briefing'):
            continue
        for step in (_severe_step, _outlook_step, _event_step):
            try:
                step(handler)
            except Exception:
                _swallow()


def start_weather_alerts(handler) -> None:
    if not module_enabled('morning_briefing'):
        return
    threading.Thread(target=_alert_loop, args=(handler,), daemon=True).start()
