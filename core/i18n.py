import json
from pathlib import Path

_language = 'ru'
_translations = {}
_refresh_callbacks = []

def _load_locale(lang: str) -> dict:
    locale_dir = Path(__file__).parent.parent / 'data' / 'locales'
    locale_file = locale_dir / f'{lang}.json'
    if not locale_file.exists():
        return {}
    with open(locale_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def tr(key: str) -> str:
    return _translations.get(key, key)

def set_language(lang: str) -> None:
    global _language, _translations
    _language = lang
    _translations = _load_locale(lang)
    for callback in _refresh_callbacks:
        try:
            callback()
        except Exception as e:
            print(f"Error calling refresh callback: {e}")

def get_language() -> str:
    return _language

def register_refresh(callback) -> None:
    _refresh_callbacks.append(callback)

def unregister_refresh(callback) -> None:
    if callback in _refresh_callbacks:
        _refresh_callbacks.remove(callback)
