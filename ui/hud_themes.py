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
        'BG':    '#0c0c0e', 'PANEL': '#13131a', 'BRD':  '#1e1e2a',
        'BRD_I': '#26263a', 'SEP':   '#16161e', 'GRID': '#0a0a0c',
        'CYAN':  '#4895ef', 'MAG':   '#4895ef', 'GREEN': '#4895ef',
        'AMBER': '#f9a825', 'RED':   '#ef5350', 'WHITE': '#f0f0f0',
        'TEXT':  '#f0f0f0', 'DIM':   '#888899',
    },
    'neon_white': {
        'BG':    '#f4f4f6', 'PANEL': '#ebebee', 'BRD':  '#d8d8dd',
        'BRD_I': '#c8c8ce', 'SEP':   '#e4e4e8', 'GRID': '#f8f8fa',
        'CYAN':  '#0077cc', 'MAG':   '#0077cc', 'GREEN': '#0077cc',
        'AMBER': '#e8780a', 'RED':   '#cc2200', 'WHITE': '#111111',
        'TEXT':  '#111111', 'DIM':   '#777788',
    },
    'minimal': {
        'BG':    '#fafafa', 'PANEL': '#f2f2f2', 'BRD':  '#dedede',
        'BRD_I': '#cecece', 'SEP':   '#e8e8e8', 'GRID': '#f6f6f6',
        'CYAN':  '#1a56db', 'MAG':   '#1a56db', 'GREEN': '#1a56db',
        'AMBER': '#1a56db', 'RED':   '#cc2200', 'WHITE': '#111111',
        'TEXT':  '#111111', 'DIM':   '#888888',
    },
}

def _settings_path() -> str:
    try:
        from config_pack.config import get_settings_path
        return get_settings_path()
    except Exception:
        return os.path.join('data', 'jarvis_settings.json')


def get_current_theme_name() -> str:
    try:
        p = _settings_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return json.load(f).get('theme', 'cyber')
    except Exception:
        pass
    return 'cyber'


def save_theme_name(name: str) -> None:
    try:
        p = _settings_path()
        data = {}
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['theme'] = name
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
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
        ctk.set_appearance_mode('light' if name in ('neon_white', 'minimal') else 'dark')
    except Exception:
        pass

    try:
        from ui.hud_utils import _blend
        _blend.cache_clear()
    except Exception:
        pass
