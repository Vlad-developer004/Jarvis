"""Cinema mode: dims the screen for watching and puts the brightness back afterwards.

State is kept in jarvis_settings.json under "cinema": {"mode": {"active", "saved"}, "mode_brightness": n}, so the saved brightness survives a restart of Jarvis.
"""
from __future__ import annotations

from core import settings_io

DEFAULT_LEVEL = 30


def _cinema() -> dict:
    raw = settings_io.read().get('cinema', {})
    return dict(raw) if isinstance(raw, dict) else {}


def level() -> int:
    try:
        return max(5, min(80, int(_cinema().get('mode_brightness', DEFAULT_LEVEL))))
    except (TypeError, ValueError):
        return DEFAULT_LEVEL


def is_active() -> bool:
    m = _cinema().get('mode')
    return bool(isinstance(m, dict) and m.get('active'))


def _save(**changes) -> bool:
    cur = _cinema()
    cur.update(changes)
    return settings_io.update({'cinema': cur})


def set_level(n) -> dict:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'bad_value'}
    if not 5 <= n <= 80:
        return {'ok': False, 'error': 'bad_value'}
    return {'ok': True} if _save(mode_brightness=n) else {'ok': False, 'error': 'write_failed'}


def _get_brightness() -> list[int] | None:
    """Brightness of every display ([58, 90]); None when it cannot be read."""
    try:
        import screen_brightness_control as sbc
        cur = sbc.get_brightness()
        vals = [int(v) for v in (cur if isinstance(cur, list) else [cur]) if v is not None]
        return vals or None
    except Exception:
        return None


def _set_brightness(value) -> bool:
    """An int sets every display, a list sets display i to value[i]."""
    try:
        import screen_brightness_control as sbc
        if isinstance(value, list):
            for i, v in enumerate(value):
                sbc.set_brightness(int(v), display=i)
        else:
            sbc.set_brightness(int(value))
        return True
    except Exception:
        return False


def enable() -> dict:
    """Dims the screen to the chosen level; remembers the old brightness (kept from the first call if already on)."""
    if is_active():
        return {'ok': True, 'active': True, 'already': True}
    saved = _get_brightness()
    if saved is None or not _set_brightness(level()):
        return {'ok': False, 'error': 'no_brightness'}
    _save(mode={'active': True, 'saved': saved})
    return {'ok': True, 'active': True}


def disable() -> dict:
    m = _cinema().get('mode')
    if not (isinstance(m, dict) and m.get('active')):
        return {'ok': True, 'active': False, 'already': True}
    saved = m.get('saved')
    if isinstance(saved, (int, list)) and not _set_brightness(saved):
        return {'ok': False, 'error': 'no_brightness'}
    _save(mode={'active': False, 'saved': saved})
    return {'ok': True, 'active': False}
