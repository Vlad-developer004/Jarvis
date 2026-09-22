"""Shared JSON read/write for a game module's "previous session" snapshot.
Extracted from features/ets2/session_history.py and
features/planetbase/session_history.py, which had identical file I/O around
different field sets — each game keeps its own thin wrapper with its own
field names, calling save_json()/load_json() here for the plumbing."""
from __future__ import annotations
import json
import os
import time
from config_pack.config import get_settings_path


def _history_path(filename: str) -> str:
    return os.path.join(os.path.dirname(get_settings_path()), filename)


def load_json(filename: str) -> dict | None:
    try:
        p = _history_path(filename)
        if not os.path.exists(p):
            return None
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_json(filename: str, fields: dict) -> None:
    try:
        p = _history_path(filename)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        data = dict(fields)
        data['ts'] = time.time()
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
