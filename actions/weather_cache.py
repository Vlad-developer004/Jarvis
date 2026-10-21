"""The last good HUD snapshot on disk, so the window shows the old values after a restart without a connection instead of an error."""
import json
import os
import time

from core.safe import swallow as _swallow

_MAX_AGE_SEC = 12 * 3600


def _path() -> str:
    from config_pack.config import get_settings_path
    return os.path.join(os.path.dirname(get_settings_path()), 'weather_last.json')


def save_snapshot(data: dict) -> None:
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        _swallow()


def load_snapshot() -> dict | None:
    try:
        with open(_path(), 'r', encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get('ok') and time.time() - float(d.get('updated_ts', 0)) < _MAX_AGE_SEC:
            return d
    except Exception:
        _swallow()
    return None
