import threading
import queue
import re
from core.nlp import extract_amount
from core.system import module_enabled
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
from .base import BaseHandler
from .interactive import handle_interactive

_log = _get_logger('dispatch')

# ---------------------------------------------------------------------------
# Module-availability gates, checked before routing. To gate a new command
# behind a module toggle, append one row here.
# ---------------------------------------------------------------------------
_GATE_GAMES_CMDS = frozenset({'game_mode_on', 'game_mode_off', 'exit_game', 'spell_list'})
_GATE_NET_CMDS = frozenset({'net_profile_status', 'net_profile_switch', 'vpn_reminder'})
_MODULE_GATES = (
    (lambda c: c == 'qa_search', 'qa', 'module.ai_disabled'),
    (lambda c: c.startswith('cinema_'), 'cinema', 'module.cinema_disabled'),
    (lambda c: c in _GATE_GAMES_CMDS, 'games', 'module.games_disabled'),
    (lambda c: c.startswith('ps_'), 'photoshop_voice', 'module.ps_disabled'),
    (lambda c: c.startswith('figma_'), 'figma_voice', 'module.figma_disabled'),
    (lambda c: c in _GATE_NET_CMDS, 'network_profiles', 'module.net_disabled'),
    (lambda c: c == 'health_disks', 'system_health', 'module.net_disabled'),
    (lambda c: c == 'calendar_next', 'calendar_ics', 'module.integrations_disabled'),
    (lambda c: c == 'inbox_unread', 'inbox_digest', 'module.integrations_disabled'),
    (lambda c: c == 'mail_compose', 'inbox_digest', 'module.mail_disabled'),
)

# ---------------------------------------------------------------------------
# Inline handlers that don't delegate to a commands/*.py module, kept as
# standalone functions so they can be registered in the dispatch tables below.
# ---------------------------------------------------------------------------
def _handle_media_group(handler, cmd, text_lower, amount):
    from .commands.media import handle_yt_control, handle_volume
    if cmd.startswith('yt_'):
        handle_yt_control(handler, cmd, text_lower)
    elif cmd.startswith('vol_') or cmd.startswith('app_vol_') or cmd == 'audio_switch':
        handle_volume(handler, cmd, text_lower, amount)
    elif cmd in ('media_pause', 'media_play', 'media_pause_youtube', 'media_pause_browser', 'media_play_youtube', 'media_play_browser'):
        from core.system import app_state
        if app_state.mouse_moving:
            app_state.mouse_moving = False
        elif app_state.game_mode:
            # In game mode: control YouTube/browser in background, never touch the game
            try:
                from actions.system import send_play_pause_to_video
                action = 'play' if 'play' in cmd else ('pause' if 'pause' in cmd else 'toggle')
                send_play_pause_to_video(prefer='youtube', action=action)
            except Exception:
                pass
        else:
            ok = False
            try:
                from actions.system import send_play_pause_to_video
                action = 'play' if 'play' in cmd else ('pause' if 'pause' in cmd else 'toggle')
                if 'youtube' in cmd:
                    ok = send_play_pause_to_video(prefer='youtube', action=action)
                elif 'browser' in cmd:
                    ok = send_play_pause_to_video(prefer='browser', action=action)
                else:
                    ok = send_play_pause_to_video(action=action)
            except Exception:
                ok = False
            if not ok:
                import pyautogui; pyautogui.press('space')
        handler.play_response()

def _handle_game_mode_on(handler, cmd, text_lower, amount):
    from .commands.game import start_game_selection_flow
    query = text_lower
    query = re.sub(r'\bджарвис(а|у|е)?\b', ' ', query)
    query = re.sub(r'^\s*(активируй|включи|запусти|подготовь)\s+(игровой\s+режим|игровой|игр\w+|геймод|режим игры|режим)\s*(для)?\s*', '', query)
    query = re.sub(r'^\s*(игровой\s+режим|игровой|игр\w+|геймод|режим игры|режим)\s*(для)?\s*', '', query)
    query = re.sub(r'^\s*(запусти игру|запусти|хочу играть в|хочу играть|играть в|играть|игру)\s*', '', query)
    query = re.sub(r'^\s*(го\s+в|хочу\s+в|включи|запусти|играть\s+в)\s*', '', query)
    query = re.sub(r'\s+', ' ', query).strip()
    start_game_selection_flow(handler, query if query else None)

def _handle_game_mode_off(handler, cmd, text_lower, amount):
    from actions.system import deactivate_game_mode, close_active_game
    if any(w in text_lower for w in ['закрой', 'выйди', 'выход']):
        close_active_game()
    deactivate_game_mode()
    try:
        handler.asr.set_vad_mode(False)
        handler.asr.clear_hotwords()
    except Exception:
        pass
    try:
        from actions.game_audio import game_matcher
        game_matcher.clear()
    except Exception:
        pass
    handler.play_response()

def _handle_exit_game(handler, cmd, text_lower, amount):
    from actions.system import close_active_game
    close_active_game()
    handler.play_response()

def _handle_app_launcher(handler, cmd, text_lower, amount):
    if cmd == 'open_task_manager':
        import subprocess; subprocess.Popen(['taskmgr']); handler.play_response()
    elif cmd == 'open_terminal':
        from actions.system import open_terminal; open_terminal(); handler.play_response()
    elif cmd == 'open_work':
        from actions.system import open_work; open_work(); handler.play_response()
    elif cmd == 'close_work':
        from actions.app_launcher import close_app; close_app('antigravity'); handler.play_response()
    else:
        from actions.app_launcher import open_app, close_app
        if cmd.startswith('open_'):
            app_key = cmd[5:]
            ok, res = open_app(app_key)
        else:
            app_key = cmd[6:]
            ok, res = close_app(app_key)
        if ok: handler.play_response()
        elif cmd.startswith('open_'): handler.speak(spk('open.error', res=res))

def _handle_open_youtube(handler, cmd, text_lower, amount):
    from actions.app_launcher import open_app
    ok, _ = open_app('youtube')
    if not ok:
        from actions.youtube import _open_youtube_url
        _open_youtube_url('https://www.youtube.com')
    handler.play_response()

def _handle_play_yt(handler, cmd, text_lower, amount):
    from core.system import app_state as _app_state
    is_music = any(w in text_lower for w in ['песню', 'песня', 'музыку', 'музыка', 'трек'])
    is_video = any(w in text_lower for w in ['видео', 'ролик', 'клип'])
    _BG_WORDS = ('в фоне', 'фоном', 'у фоні', 'фоном', 'в фоновому режимі')
    _bg = _app_state.game_mode or any(w in text_lower for w in _BG_WORDS)
    query = text_lower
    for sw in ['включи песню', 'поставь песню', 'найди песню',
               'включи музыку', 'поставь музыку', 'найди музыку',
               'включи видео', 'поставь видео', 'найди видео',
               'включи', 'поставь', 'найди']:
        query = query.replace(sw, '')
    for bg_w in _BG_WORDS:
        query = query.replace(bg_w, '')
    query = query.strip()
    if not query:
        handler._set_interactive('play_yt_ask', {'is_music': is_music, 'is_video': is_video, 'background': _bg}, timeout=20.0)
    else:
        from core.handler.yt_play import resolve_and_play_youtube
        threading.Thread(
            target=resolve_and_play_youtube,
            args=(handler, query, is_music, is_video, _bg),
            daemon=True,
        ).start()

def _handle_show_help(handler, cmd, text_lower, amount):
    try:
        from ui.dialogs.welcome_dlg import open_welcome
        from ui import hud
        h = getattr(hud, '_hud', None)
        if h:
            h._hud_queue.put(lambda: open_welcome(h, force=True))
            handler.speak(spk('help.intro'))
        else:
            handler.speak(spk('hud.not_running'))
    except Exception as e:
        _log.error('show_help error: %s', e)
        handler.speak(spk('open.help_error'))

def _handle_hud_group(handler, cmd, text_lower, amount):
    try:
        from ui import hud
        h = getattr(hud, '_hud', None)
        if not h:
            from ui.hud import show_hud
            show_hud()
            h = getattr(hud, '_hud', None)

        if h:
            if cmd == 'show_hud':
                from ui.hud import show_hud
                h._hud_queue.put(lambda: show_hud())
            elif cmd == 'open_settings':
                h._hud_queue.put(lambda: h._open_settings())
            elif cmd == 'open_keybinds':
                h._hud_queue.put(lambda: h._open_keybind_editor())
            elif cmd == 'open_extensions':
                h._hud_queue.put(lambda: h._open_extensions())
            elif cmd == 'open_perf':
                h._hud_queue.put(lambda: h._open_perf_monitor())
            elif cmd == 'open_deck':
                h._hud_queue.put(lambda: h._open_deck())
            handler.play_response()
        else:
            handler.speak(spk('hud.not_running'))
    except Exception as e:
        _log.error('interface command error: %s', e)
        handler.speak(spk('hud.error'))

# ---------------------------------------------------------------------------
# Thin arity-adapters for commands/*.py handlers, so every entry in the
# dispatch tables below shares the same (handler, cmd, text_lower, amount)
# call signature regardless of what the underlying handle_xxx() needs.
# Imports stay lazy (inside the function), matching the original behavior of
# only importing a command module once a matching command is actually seen.
# ---------------------------------------------------------------------------
def _w_window(h, cmd, t, a):
    from .commands.windows import handle_window
    handle_window(h, cmd, t, a)
def _w_mouse(h, cmd, t, a):
    from .commands.mouse import handle_mouse
    handle_mouse(h, cmd, t, a)
def _w_system(h, cmd, t, a):
    from .commands.system import handle_system
    handle_system(h, cmd, t, a)
def _w_clip(h, cmd, t, a):
    from .commands.clip import handle_clip
    handle_clip(h, cmd, t, a)
def _w_browser(h, cmd, t, a):
    from .commands.browser import handle_browser
    handle_browser(h, cmd, t, a)
def _w_ai(h, cmd, t, a):
    from .commands.ai import handle_ai
    handle_ai(h, cmd, t, a)
def _w_info(h, cmd, t, a):
    from .commands.info import handle_info
    handle_info(h, cmd, t)
def _w_files(h, cmd, t, a):
    from .commands.files import handle_files
    handle_files(h, cmd, t)
def _w_video(h, cmd, t, a):
    from .commands.video import handle_video
    handle_video(h, cmd, t)
def _w_notes(h, cmd, t, a):
    from .commands.notes import handle_notes
    handle_notes(h, cmd, t, a)
def _w_utils(h, cmd, t, a):
    from .commands.utils import handle_utils
    handle_utils(h, cmd, t)
def _w_cinema(h, cmd, t, a):
    from .commands.cinema import handle_cinema
    handle_cinema(h, cmd, t)
def _w_creative(h, cmd, t, a):
    from .commands.creative import handle_creative
    handle_creative(h, cmd, t)
def _w_game_extra(h, cmd, t, a):
    from .commands.game import handle_game_extra
    handle_game_extra(h, cmd, t)
def _w_work_session(h, cmd, t, a):
    _handle_work_session(h)
def _w_timer(h, cmd, t, a):
    from .commands.game import handle_timer
    handle_timer(h, cmd, t)
def _w_integrations(h, cmd, t, a):
    from .commands.integrations import handle_integrations
    handle_integrations(h, cmd, t)
def _w_social(h, cmd, t, a):
    from .commands.social import handle_social
    handle_social(h, cmd, t)
def _w_reactor(h, cmd, t, a):
    from .commands.reactor import handle_reactor
    handle_reactor(h, cmd, t, a)

# ---------------------------------------------------------------------------
# Dispatch tables. Exact-match commands are looked up in _EXACT (O(1)); only
# if that misses do we fall back to scanning _PREFIXES in order. Because exact
# matches always take priority over prefix fallbacks, a specific command never
# needs to be explicitly excluded from a broader prefix handler (e.g.
# 'open_settings' is an exact entry below, so the generic 'open_' prefix
# handler never sees it — no exclusion list to keep in sync as new commands
# are added).
#
# To add a new command: add it to _EXACT (or a new/existing prefix in
# _PREFIXES) pointing at its handler. That's it — no new if/elif branch.
#
# Registration order below mirrors the original if/elif chain's order, so
# that if the same command is ever listed under two different handlers (which
# happened before this refactor — see project memory on the dispatch cleanup),
# the first-registered one wins, same as the old top-to-bottom elif chain.
# ---------------------------------------------------------------------------
_EXACT: dict = {}
_PREFIXES: list = []

def _reg_exact(cmds, fn):
    for c in cmds:
        _EXACT.setdefault(c, fn)

def _reg_prefix(prefix, fn):
    _PREFIXES.append((prefix, fn))

_reg_prefix('yt_', _handle_media_group)
_reg_prefix('vol_', _handle_media_group)
_reg_prefix('app_vol_', _handle_media_group)
_reg_prefix('media_', _handle_media_group)
_reg_exact(['audio_switch'], _handle_media_group)

_reg_exact(['min_all', 'min_win', 'unmin_win', 'max_win', 'close_win', 'close_all_win', 'close_other_win', 'min_other_win', 'move_monitor'], _w_window)
_reg_prefix('win_snap_', _w_window)

_reg_prefix('mouse_', _w_mouse)

_reg_exact(['shutdown', 'restart', 'restart_jarvis', 'dictation_on', 'system_cleanup', 'internet_speed', 'wifi_toggle', 'keyboard_lock', 'keyboard_unlock', 'shutdown_timer', 'cancel_timer', 'guard_on', 'guard_off', 'economy_on', 'economy_off', 'listen_off', 'listen_on', 'jarvis_exit', 'bluetooth_toggle', 'reminder'], _w_system)
_reg_prefix('brightness_', _w_system)

_reg_prefix('clip_', _w_clip)
_reg_exact(['undo', 'redo', 'select_all'], _w_clip)

_reg_exact(['browser_tab', 'close_tab', 'close_tab_n', 'close_all_tabs', 'open_browser_history', 'context_close'], _w_browser)

_reg_exact(['qa_search'], _w_ai)

_reg_exact(['currency_rate', 'weather', 'set_weather_city', 'google_search', 'translate', 'translate_speech', 'my_ip', 'system_specs', 'nasa_apod'], _w_info)

_reg_exact(['empty_trash', 'create_folder', 'delete_folder', 'delete_file', 'cd_folder', 'explorer_go_up', 'explorer_goto', 'find_doc', 'find_sheet', 'find_file', 'create_word_doc'], _w_files)
_reg_prefix('recent_', _w_files)

_reg_exact(['screenshot', 'screenshot_terminal', 'screenshot_site', 'start_video', 'stop_video', 'save_video', 'open_saved', 'clipchamp_last', 'open_last_video', 'paste_file', 'paste_video', 'download_video'], _w_video)
_reg_prefix('ocr_', _w_video)

_reg_exact(['note_save', 'cancel_reminder'], _w_notes)

# Dead in the original elif chain: 'reminder'/'cancel_reminder' were also
# listed here, but the branches above (system/notes) always matched first and
# this code could never run. Removed rather than carried forward.
_reg_prefix('bt', _w_utils)
_reg_prefix('session_', _w_utils)
_reg_prefix('command_', _w_utils)
_reg_exact(['change_layout', 'press_enter', 'git_commit', 'today_summary'], _w_utils)

_reg_prefix('cinema_', _w_cinema)

_reg_prefix('ps_', _w_creative)
_reg_prefix('figma_', _w_creative)

_reg_exact(['game_mode_on'], _handle_game_mode_on)
_reg_exact(['game_mode_off'], _handle_game_mode_off)
_reg_exact(['exit_game'], _handle_exit_game)
_reg_exact(['spell_list'], _w_game_extra)

_reg_exact(['work_session'], _w_work_session)

_reg_exact(['timer_set', 'timer_status', 'timer_cancel', 'timer_add'], _w_timer)

# Generic app launcher is a prefix fallback only — every command above that
# happens to start with 'open_'/'close_' but has its own specific handler
# (open_youtube, open_browser_history, open_last_video, open_saved,
# open_settings, open_keybinds, open_extensions, open_perf) is already an
# exact-match entry, so it's resolved before this fallback is ever consulted.
_reg_prefix('open_', _handle_app_launcher)
_reg_prefix('close_', _handle_app_launcher)

_reg_exact(['open_youtube'], _handle_open_youtube)
_reg_exact(['play_yt'], _handle_play_yt)

_reg_exact(['net_profile_status', 'net_profile_switch', 'vpn_reminder', 'health_disks', 'calendar_next', 'inbox_unread', 'mail_compose'], _w_integrations)

_reg_exact(['time_now', 'system_status', 'how_are_you', 'system_insult', 'praise', 'thanks'], _w_social)

_reg_exact(['show_help'], _handle_show_help)

_reg_exact(['show_hud', 'open_settings', 'open_keybinds', 'open_extensions', 'open_perf', 'open_deck'], _handle_hud_group)

_reg_prefix('reactor_', _w_reactor)

class CommandHandler(BaseHandler):
    def __init__(self, pa, rate, chunk, asr):
        super().__init__(pa, rate, chunk, asr)
        try:
            from ui.hud_utils import _load_hud_settings
            self._settings = _load_hud_settings()
        except Exception:
            self._settings = {}
        # One dedicated worker serializes command execution — previously every
        # recognized utterance spawned its own unconditional daemon thread, so
        # two commands recognized close together (e.g. a follow-up said while
        # the first is still finishing its speak(wait=True) intro line) could
        # run _execute_command concurrently with no ordering guarantee and no
        # cap on how many could pile up at once. Slow work (network calls,
        # etc.) already runs in each handler's own background thread and
        # returns from _execute_command quickly (see _weather/_nasa_apod/...),
        # so serializing this queue doesn't make anything wait on slow I/O.
        self._cmd_queue: "queue.Queue" = queue.Queue()
        self._cmd_worker = threading.Thread(target=self._cmd_worker_loop, daemon=True)
        self._cmd_worker.start()
    def _cmd_worker_loop(self):
        while True:
            cmd, text, text_lower, amount = self._cmd_queue.get()
            try:
                self._execute_command(cmd, text, text_lower, amount)
            except Exception as e:
                _log.error('command worker error: cmd=%r: %s', cmd, e, exc_info=True)
    def handle(self, cmd: str, text: str):
        text_lower = text.lower().strip()
        amount = extract_amount(text_lower)
        if cmd == 'wake': self.play_response('wake')
        self._cmd_queue.put((cmd, text, text_lower, amount))
    def handle_interactive(self, text: str):
        return handle_interactive(self, text)
    def _execute_command(self, cmd: str, text: str, text_lower: str, amount: int):
        _log.debug('cmd=%r text=%r', cmd, text)
        for pred, mod, msg_key in _MODULE_GATES:
            if pred(cmd) and not module_enabled(mod):
                self.speak(spk(msg_key)); return
        handler_fn = _EXACT.get(cmd)
        if handler_fn is None:
            for prefix, fn in _PREFIXES:
                if cmd.startswith(prefix):
                    handler_fn = fn
                    break
        if handler_fn is not None:
            handler_fn(self, cmd, text_lower, amount)
    def _launch_game_engine(self, game_info):
        from .commands.game import launch_game_engine
        launch_game_engine(self, game_info)
    def _apply_game_profile(self, profile, name):
        from .commands.game import apply_game_profile
        apply_game_profile(self, profile, name)
def _handle_work_session(handler) -> None:
    from actions.dev_projects import get_projects, open_project
    from core.responses import spk
    projects = get_projects()
    if not projects:
        handler.speak(spk('work.no_projects'))
        return
    if len(projects) == 1:
        p = projects[0]
        ok, err = open_project(p)
        if ok:
            handler.speak(spk('work.open_one', name=p['name']))
        else:
            handler.speak(spk('work.error'))
        return
    # Multiple projects — ask which one
    handler.speak(spk('work.ask_which'))
    handler._set_interactive({'type': 'work_select'}, {}, timeout=20.0)


def parse_folder_name(text_lower: str, mode: str) -> str:
    tokens = text_lower.replace('—', ' ').split()
    keyword = 'создай' if mode == 'create' else 'удали'
    if 'папку' in tokens:
        idx = tokens.index('папку')
        name = ' '.join([t for t in tokens[idx+1:] if t != 'здесь']).strip()
        for word in ['новую', 'новой', 'новый']:
            if name.lower().startswith(word):
                name = name[len(word):].strip()
        return name
    elif keyword in tokens:
        idx = tokens.index(keyword)
        return ' '.join([t for t in tokens[idx+1:] if t not in ('здесь', 'папку')]).strip()
    return ''
def parse_cd_name(text_lower: str) -> str:
    tokens = text_lower.replace('—', ' ').split()
    if 'папку' in tokens:
        idx = tokens.index('папку')
        return ' '.join([t for t in tokens[idx+1:] if t not in ('здесь', 'сюда', 'тут')]).strip()
    elif 'папка' in tokens:
        idx = tokens.index('папка')
        return ' '.join([t for t in tokens[idx+1:] if t not in ('здесь', 'сюда', 'тут')]).strip()

    # Generic "go to" logic
    for kw in ('зайди', 'перейди', 'открой', 'goto', 'open'):
        if kw in tokens:
            idx = tokens.index(kw)
            return ' '.join([t for t in tokens[idx+1:] if t not in ('в', 'у', 'to', 'папку', 'папка', 'сюда', 'здесь', 'тут')]).strip()
    return ''
