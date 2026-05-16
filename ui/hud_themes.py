from __future__ import annotations
from core import i18n
import json, os, sys

# ──────────────────────────────────────────────────────────────────────────────
# Theme Definitions
# ──────────────────────────────────────────────────────────────────────────────
THEMES = {
    'cyber': {
        'BG':    '#0a0b10', 'PANEL': '#0d0f1e', 'BRD':  '#181b35',
        'BRD_I': '#212448', 'SEP':   '#1a1d38', 'GRID': '#121528',
        'CYAN':  '#00ffff', 'MAG':   '#f500ff', 'GREEN': '#00ff88',
        'AMBER': '#ffcc00', 'RED':   '#ff3333', 'WHITE': '#ffffff',
        'TEXT':  '#d1d7ef', 'DIM':   '#8e98c9',
    },
    'dark': {
        'BG':    '#0d0d0d', 'PANEL': '#141414', 'BRD':  '#222222',
        'BRD_I': '#2a2a2a', 'SEP':   '#1a1a1a', 'GRID': '#080808',
        'CYAN':  '#4da6ff', 'MAG':   '#b366ff', 'GREEN': '#55cc55',
        'AMBER': '#ffaa33', 'RED':   '#ff5555', 'WHITE': '#ffffff',
        'TEXT':  '#e8e8e8', 'DIM':   '#888888',
    },
    'light': {
        'BG':    '#f4f6fa', 'PANEL': '#ffffff', 'BRD':  '#dde1ea',
        'BRD_I': '#c8cdd8', 'SEP':   '#eceef3', 'GRID': '#f9fafc',
        'CYAN':  '#0055cc', 'MAG':   '#9900aa', 'GREEN': '#1a7a1a',
        'AMBER': '#cc5500', 'RED':   '#bb0000', 'WHITE': '#111111',
        'TEXT':  '#1a1a2e', 'DIM':   '#5a5a7a',
    },
}

_SETTINGS_PATH = os.path.join('data', 'jarvis_settings.json')


def get_current_theme_name() -> str:
    try:
        if os.path.exists(_SETTINGS_PATH):
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f).get('theme', 'cyber')
    except Exception:
        pass
    return 'cyber'


def save_theme_name(name: str) -> None:
    try:
        data = {}
        if os.path.exists(_SETTINGS_PATH):
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['theme'] = name
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def apply_theme(name: str = None) -> None:
    """
    Patches hud_constants module-level variables so ALL code that reads
    from the module object (e.g. _hud_c._BG) sees the new theme immediately.
    Code that did `from .hud_constants import _BG` has a stale copy – those
    windows need a rebuild / restart to pick up the change (we show a notice).
    """
    if not name:
        name = get_current_theme_name()
    if name not in THEMES:
        name = 'cyber'

    t = THEMES[name]

    # Patch the module object directly
    try:
        import ui.hud_constants as _c
    except ImportError:
        try:
            from . import hud_constants as _c  # type: ignore
        except ImportError:
            return

    _c._BG    = t['BG']
    _c._PANEL = t['PANEL']
    _c._BRD   = t['BRD']
    _c._BRD_I = t['BRD_I']
    _c._SEP   = t['SEP']
    _c._GRID  = t['GRID']
    _c._CYAN  = t['CYAN']
    _c._MAG   = t['MAG']
    _c._GREEN = t['GREEN']
    _c._AMBER = t['AMBER']
    _c._RED   = t['RED']
    _c._WHITE = t['WHITE']
    _c._TEXT  = t['TEXT']
    _c._DIM   = t['DIM']
    _c._CURRENT_THEME = name

    try:
        import customtkinter as ctk
        ctk.set_appearance_mode('light' if name == 'light' else 'dark')
    except Exception:
        pass
