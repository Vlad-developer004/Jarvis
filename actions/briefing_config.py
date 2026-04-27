from __future__ import annotations
import json
from copy import deepcopy
from pathlib import Path
from config_pack.config import get_settings_path
_SETTINGS_PATH = Path(get_settings_path())
_DEFAULT = {
    'include_greeting': True,
    'include_time': True,
    'include_weather': True,
    'include_battery': True,
    'include_system_load': True,
    'include_calendar': True,
    'include_mail_unread': True,
    'calendar_reminder_minutes': 15,
    'calendar_reminders_enabled': True,
}
def load_briefing_prefs() -> dict:
    out = deepcopy(_DEFAULT)
    try:
        if _SETTINGS_PATH.exists():
            data = json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
            raw = data.get('briefing')
            if isinstance(raw, dict):
                for k in _DEFAULT:
                    if k not in raw:
                        continue
                    v = raw[k]
                    if k == 'calendar_reminder_minutes':
                        try:
                            n = int(v)
                            if 1 <= n <= 120:
                                out[k] = n
                        except (TypeError, ValueError):
                            pass
                    elif isinstance(v, bool):
                        out[k] = v
    except Exception:
        pass
    return out
def merge_default_briefing_into_settings(data: dict) -> dict:
    cur = data.get('briefing')
    if not isinstance(cur, dict):
        data['briefing'] = deepcopy(_DEFAULT)
    else:
        merged = deepcopy(_DEFAULT)
        merged.update(cur)
        data['briefing'] = merged
    return data
