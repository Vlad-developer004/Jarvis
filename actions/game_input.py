from actions.game_input_parts.profile import (
    load_profile,
    unload_profile,
    match_command,
    get_command_list,
    get_hotwords,
    get_binding,
    press_robust,
    _profile_name,
    _entries,
    _flat,
    _bindings,
    _last_cast
)
from actions.game_input_parts.driving import (
    cruise_set_speed,
    set_gear
)
from actions.game_input_parts.runtime import (
    cast_command,
    execute_by_name,
    _wiper_state,
    cast_spell,
    get_spell_list
)

import json
import re
import time
import threading
from pathlib import Path

try:
    import pydirectinput as _input
    _input.PAUSE = 0
except ImportError:
    import pyautogui as _input

PROFILES_DIR = Path('data') / 'game_profiles'
CAST_COOLDOWN = 1.0

# Re-export everything for compatibility
__all__ = [
    'load_profile', 'unload_profile', 'match_command', 'get_command_list',
    'get_hotwords', 'get_binding', 'press_robust', 'cruise_set_speed',
    'set_gear', 'cast_command', 'execute_by_name', 'cast_spell', 'get_spell_list'
]
