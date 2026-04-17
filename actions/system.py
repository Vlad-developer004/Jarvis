from actions.system_parts.game_mode import (
    POWER_PLAN_FILE,
    activate_game_mode,
    deactivate_game_mode,
    open_work,
    _load_game_mode_prefs,
    _game_keep_title,
)
from actions.system_parts.power import (
    activate_economy_mode,
    deactivate_economy_mode,
)
from actions.system_parts.translate import (
    LANG_MAP,
    translate_selected,
)
from actions.system_parts.media import (
    open_last_video_file,
    open_latest_clipchamp_video,
    send_play_pause_to_video,
)
from actions.system_parts.files_paste import (
    find_and_paste_file,
)
from actions.system_parts.input_hw import (
    press_enter,
    change_keyboard_layout,
    open_browser_history,
    open_terminal,
    disable_keyboards_hardware,
    enable_keyboards_hardware,
    close_active_game,
    _switch_to_hwnd,
    _send_hotkey,
)
from actions.app_launcher import open_app, close_app, APPS, SYSTEM_WHITELIST
from actions.system_control import (
    shutdown_pc,
    restart_pc,
    schedule_shutdown,
    cancel_shutdown,
    toggle_wifi,
    toggle_bluetooth,
    change_brightness,
    check_internet_speed,
    clean_system,
)
