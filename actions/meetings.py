from __future__ import annotations
import json
import webbrowser
from pathlib import Path
_SETTINGS_PATH = Path('data') / 'jarvis_settings.json'
def _load() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}
def _save(data: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
def get_meetings() -> list[dict]:
    return _load().get('meetings', [])
def save_meetings(meetings: list[dict]) -> None:
    data = _load()
    data['meetings'] = meetings
    _save(data)
def match_meeting(text: str) -> dict | None:
    text_lower = text.lower().strip()
    meetings = get_meetings()
    if not meetings:
        return None
    for m in meetings:
        phrase = m.get('phrase', '').lower().strip()
        if phrase and phrase in text_lower:
            return m
    try:
        from rapidfuzz import fuzz as _fuzz
        best, best_score = None, 0.0
        for m in meetings:
            for field in ('phrase', 'name'):
                val = m.get(field, '').lower().strip()
                if not val:
                    continue
                score = max(
                    _fuzz.partial_ratio(text_lower, val),
                    _fuzz.token_set_ratio(text_lower, val),
                ) / 100.0
                if score > best_score:
                    best_score = score
                    best = m
        if best and best_score >= 0.72:
            return best
    except ImportError:
        pass
    return None
def open_meeting(m: dict) -> bool:
    url = m.get('url', '').strip()
    if not url:
        return False
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    webbrowser.open(url)
    return True
