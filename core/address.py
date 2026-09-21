import json

_ADDRESSES = {
    'ru': {'male': 'сэр', 'female': 'леди'},
    'uk': {'male': 'сер', 'female': 'пані'},
}

def _load() -> dict:
    try:
        from config_pack.config import get_settings_path
        with open(get_settings_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def get_address(lang: str | None = None) -> str:
    """Return the address term (сэр / леди / custom) based on user settings."""
    data = _load()
    mode = data.get('address_mode', 'male')
    if mode == 'custom':
        custom = (data.get('custom_address') or '').strip()
        return custom if custom else _default(lang)

    if lang is None:
        try:
            from core.i18n import get_speech_language
            lang = get_speech_language()
        except Exception:
            lang = 'ru'

    table = _ADDRESSES.get(lang, _ADDRESSES['ru'])
    return table.get(mode, table['male'])


def _default(lang: str | None = None) -> str:
    if lang is None:
        try:
            from core.i18n import get_speech_language
            lang = get_speech_language()
        except Exception:
            lang = 'ru'
    return _ADDRESSES.get(lang, _ADDRESSES['ru'])['male']
