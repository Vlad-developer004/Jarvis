"""Spoken calendar reminders: once a minute asks actions/calendar_hub.py which reminders are due (the default lead time from the briefing
settings for every timed event, the event's own lead times for the user's own events) and says each one once. Which ones were already said
is kept in %APPDATA%\\Jarvis\\calendar_reminders_announced.json, so a restart does not repeat them."""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime

from actions.briefing_config import load_briefing_prefs
from core.system import module_enabled
from core.safe import swallow as _swallow

_LOCK = threading.Lock()
_announced: dict[str, None] = {}                    # insertion-ordered set


def _path() -> str:
    from config_pack.config import get_app_data_root
    return os.path.join(get_app_data_root(), 'calendar_reminders_announced.json')


def _load_announced() -> dict[str, None]:
    try:
        with open(_path(), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return dict.fromkeys(str(x) for x in data) if isinstance(data, list) else {}
    except Exception:
        return {}


def _save_announced() -> None:
    try:
        keys = list(_announced)[-500:]
        with open(_path(), 'w', encoding='utf-8') as f:
            json.dump(keys, f, ensure_ascii=False, indent=1)
    except Exception:
        _swallow()


def _plural(n: int, one: str, few: str, many: str) -> str:
    k = n % 100
    return one if n % 10 == 1 and k != 11 else few if 2 <= n % 10 <= 4 and not 12 <= k <= 14 else many


def when_phrase(minutes: int) -> str:
    if minutes >= 60 and minutes % 60 == 0:
        h = minutes // 60
        return f'{h} {_plural(h, "час", "часа", "часов")}'
    return f'{minutes} {_plural(minutes, "минуту", "минуты", "минут")}'


def check_once(now: datetime | None = None) -> list[str]:
    """Reminders due right now that were not said yet, as sentences; they are marked as said."""
    from actions import calendar_hub
    now = now or datetime.now()
    prefs = load_briefing_prefs()
    try:
        lead = max(1, min(int(prefs.get('calendar_reminder_minutes') or 15), 120))
    except (TypeError, ValueError):
        lead = 15
    out = []
    for key, minutes, title in calendar_hub.due_reminders(now, lead, bool(prefs.get('calendar_reminders_enabled', True))):
        with _LOCK:
            if key in _announced:
                continue
            _announced[key] = None
            _save_announced()
        out.append(f'Через {when_phrase(minutes)}: {title}.')
    return out


def _run_loop(handler):
    global _announced
    with _LOCK:
        _announced = _load_announced()
    while True:
        try:
            time.sleep(60)
            if not module_enabled('calendar_ics'):
                continue
            for msg in check_once():
                try:
                    from features.reminder import schedule_reminder
                    schedule_reminder(1, msg, handler.speak)
                except Exception:
                    try:
                        handler.speak(msg)
                    except Exception:
                        _swallow()
        except Exception:
            time.sleep(30)


def start_calendar_reminders(handler) -> None:
    if not module_enabled('calendar_ics'):
        return
    threading.Thread(target=_run_loop, args=(handler,), daemon=True, name='calendar_reminders').start()
