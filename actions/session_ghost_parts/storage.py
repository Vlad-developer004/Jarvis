import os
import json
SESSIONS_FILE = 'data/sessions.json'
def _ensure_data_dir():
    os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
    if not os.path.exists(SESSIONS_FILE):
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=4)
def _load_sessions():
    _ensure_data_dir()
    try:
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}
def _save_sessions(data):
    _ensure_data_dir()
    with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
