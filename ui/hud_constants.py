from __future__ import annotations
import json, os

# ──────────────────────────────────────────────────────────────────────────────
# Load theme colors from settings BEFORE defining defaults.
# This way, the very first import of this module already has the right colors.
# ──────────────────────────────────────────────────────────────────────────────
def _load_theme_colors() -> dict:
    """Read the saved theme palette without importing other ui modules."""
    _THEMES = {
        'cyber': {
            'BG': '#0a0b10', 'PANEL': '#0d0f1e', 'BRD': '#181b35',
            'BRD_I': '#212448', 'SEP': '#1a1d38', 'GRID': '#121528',
            'CYAN': '#00ffff', 'MAG': '#f500ff', 'GREEN': '#00ff88',
            'AMBER': '#ffcc00', 'RED': '#ff3333', 'WHITE': '#ffffff',
            'TEXT': '#d1d7ef', 'DIM': '#8e98c9',
        },
        'dark': {
            'BG': '#0d0d0d', 'PANEL': '#141414', 'BRD': '#222222',
            'BRD_I': '#2a2a2a', 'SEP': '#1a1a1a', 'GRID': '#080808',
            'CYAN': '#4da6ff', 'MAG': '#b366ff', 'GREEN': '#55cc55',
            'AMBER': '#ffaa33', 'RED': '#ff5555', 'WHITE': '#ffffff',
            'TEXT': '#e8e8e8', 'DIM': '#888888',
        },
        'light': {
            'BG': '#f4f6fa', 'PANEL': '#ffffff', 'BRD': '#dde1ea',
            'BRD_I': '#c8cdd8', 'SEP': '#eceef3', 'GRID': '#f9fafc',
            'CYAN': '#0055cc', 'MAG': '#9900aa', 'GREEN': '#1a7a1a',
            'AMBER': '#cc5500', 'RED': '#bb0000', 'WHITE': '#111111',
            'TEXT': '#1a1a2e', 'DIM': '#5a5a7a',
        },
    }
    try:
        p = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                name = json.load(f).get('theme', 'cyber')
            if name in _THEMES:
                return name, _THEMES[name]
    except Exception:
        pass
    return 'cyber', _THEMES['cyber']

_CURRENT_THEME, _t = _load_theme_colors()

# Apply the loaded palette as module-level constants
_BG    = _t['BG']
_PANEL = _t['PANEL']
_BRD   = _t['BRD']
_BRD_I = _t['BRD_I']
_SEP   = _t['SEP']
_CYAN  = _t['CYAN']
_MAG   = _t['MAG']
_GREEN = _t['GREEN']
_AMBER = _t['AMBER']
_RED   = _t['RED']
_WHITE = _t['WHITE']
_TEXT  = _t['TEXT']
_DIM   = _t['DIM']
_GRID  = _t['GRID']

del _t  # clean up temp variable

_DYN = 'dynamic'
_STA = 'static'
_RU_MON  = {1: 'ЯНВ', 2: 'ФЕВ', 3: 'МАЙ', 4: 'АПР', 5: 'МАЙ', 6: 'ИЮН',
             7: 'ИЮЛ', 8: 'АВГ', 9: 'СЕН', 10: 'ОКТ', 11: 'НОЯ', 12: 'ДЕК'}
_RU_DAYS = {0: 'ПОНЕДЕЛЬНИК', 1: 'ВТОРНИК', 2: 'СРЕДА', 3: 'ЧЕТВЕРГ',
             4: 'ПЯТНИЦА', 5: 'СУББОТА', 6: 'ВОСКРЕСЕНЬЕ'}
_LOW_PERF_MODE: bool = False
_DEFAULT_VIS: dict = {
    'cpu': True, 'storage': True, 'network': True, 'weather': True,
    'ram': True, 'camera': True, 'sysinfo': True, 'gamemode': True,
    'meetings_btn': True, 'videos_btn': True,
}
