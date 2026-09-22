from __future__ import annotations
from features.gaming_common.session_history import load_json, save_json

_FILENAME = 'fs22_session_history.json'

def load_last_session() -> dict | None:
    return load_json(_FILENAME)

def save_session(minutes: float) -> None:
    save_json(_FILENAME, {'minutes': minutes})
