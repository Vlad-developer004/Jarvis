"""Read-modify-write access to jarvis_settings.json for code outside the old HUD (the new UI bridge, the exchange-rate command).

The old HUD keeps its own copy of the file (`hud._settings`) and writes the whole copy back on some changes. A key written here would be
lost the next time it does that, so every update is mirrored into that copy as well.
"""
from __future__ import annotations

import json
import os
import threading
from core.safe import swallow as _swallow

_lock = threading.Lock()


def _path() -> str:
    from config_pack.config import get_settings_path
    return get_settings_path()


def read() -> dict:
    try:
        with open(_path(), 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def update(changes: dict, remove: tuple = ()) -> bool:
    """Merges `changes` into the file (top-level keys), drops the `remove` keys, and does the same in the HUD's in-memory copy. False when the file cannot be written."""
    with _lock:
        s = read()
        for k in remove:
            s.pop(k, None)
        s.update(changes)
        try:
            path = _path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
        except Exception:
            return False
    return True
