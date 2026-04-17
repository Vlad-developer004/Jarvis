from .state import app_state, AppState
from .windows import (
    force_foreground, autostart_enabled, autostart_set,
    add_defender_exclusion, defender_exclusion_needed,
    mark_defender_exclusion_done, get_active_explorer_path,
    get_foreground_process_name, get_foreground_process_exe, set_process_priority
)
from .bootstrap import bootstrap, play_early_greeting
from .updater import start as start_updater, stop as stop_updater, apply_if_ready as apply_update_if_ready
from .modules import module_enabled, refresh_module_flags, active_module_profile
