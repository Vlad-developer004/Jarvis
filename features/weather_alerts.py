"""Proactive severe-weather voice alert — speaks up once a day, unprompted,
when current conditions turn dangerous (storm, blizzard, extreme temp/wind).
Reuses the HUD's already-fresh weather cache (actions.weather.get_current_conditions)
instead of polling the network on its own."""
import os
import threading
import time
from datetime import date
from core.system import module_enabled

LOG_DIR = os.path.join('logs')
LOG_FILE = os.path.join(LOG_DIR, 'last_weather_alert.txt')
_CHECK_INTERVAL_SEC = 1800
_SEVERE_KEYWORDS_RU = ('гроза', 'ливен', 'метель', 'вьюг')
_SEVERE_KEYWORDS_UK = ('гроза', 'злив', 'хуртовин', 'завірюх')


def _read_last_date() -> str:
    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip()
    except Exception:
        pass
    return ''


def _write_today() -> None:
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            f.write(date.today().isoformat())
    except Exception:
        pass


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


def _alert_loop(handler) -> None:
    while True:
        time.sleep(_CHECK_INTERVAL_SEC)
        try:
            if not module_enabled('morning_briefing'):
                continue
            today = date.today().isoformat()
            if _read_last_date() == today:
                continue
            from actions.weather import get_current_conditions
            from core.i18n import get_language
            cond = get_current_conditions()
            if not cond:
                continue
            lang = get_language()
            desc = cond.get('desc', '')
            temp = cond.get('temp', 0)
            wind = cond.get('wind', 0)
            if not _is_severe(desc, temp, wind, lang):
                continue
            from core.address import get_address as _ga
            if lang == 'uk':
                msg = f'{_ga()}, попередження: зараз {desc.lower()}, будьте обережні.'
            else:
                msg = f'{_ga()}, предупреждение: сейчас {desc.lower()}, будьте осторожны.'
            handler.speak(msg)
            _write_today()
        except Exception:
            pass


def start_weather_alerts(handler) -> None:
    if not module_enabled('morning_briefing'):
        return
    threading.Thread(target=_alert_loop, args=(handler,), daemon=True).start()
