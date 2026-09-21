import threading
from core.system import app_state
from core.responses import spk
def _fmt_delay(seconds: int) -> str:
    from core.nlp import format_duration_russian, get_russian_plural
    if seconds < 60:
        forms = ['секунду', 'секунды', 'секунд']
        return f'{seconds} {get_russian_plural(seconds, forms)}'
    return format_duration_russian(seconds // 60)

# ---------------------------------------------------------------------------
# cmd -> action lookup. Each action takes (handler, text_lower, amount); to
# add a new system command, add one function and one row in _SYSTEM_ACTIONS
# instead of a new elif branch.
# ---------------------------------------------------------------------------
def _sys_shutdown(handler, text_lower, amount):
    from actions.system import shutdown_pc
    handler.play_response('shutdown'); shutdown_pc()

def _sys_restart(handler, text_lower, amount):
    from actions.system import restart_pc
    handler.play_response(); restart_pc()

def _sys_dictation_on(handler, text_lower, amount):
    from actions.dictation import start_dictation
    if start_dictation():
        app_state.dictation_mode = True; handler.play_response()

def _sys_cleanup(handler, text_lower, amount):
    from actions.system import clean_system
    ok, _ = clean_system()
    if ok: handler.speak(spk('system.cleanup_start'))

def _sys_internet_speed(handler, text_lower, amount):
    from actions.system_control import check_internet_speed
    handler.speak(spk('net.speed_start'))
    def _speed_task():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            f = ex.submit(check_internet_speed)
            try:
                handler.speak(f.result(timeout=35))
            except concurrent.futures.TimeoutError:
                handler.speak(spk('net.speed_timeout'))
    threading.Thread(target=_speed_task, daemon=True).start()

def _sys_brightness_set(handler, text_lower, amount):
    from actions.system import change_brightness
    change_brightness('set', amount); handler.play_response()

def _sys_brightness_up(handler, text_lower, amount):
    from actions.system import change_brightness
    change_brightness('up', amount or 20); handler.play_response()

def _sys_brightness_down(handler, text_lower, amount):
    from actions.system import change_brightness
    change_brightness('down', amount or 20); handler.play_response()

def _sys_wifi_toggle(handler, text_lower, amount):
    from actions.system import toggle_wifi
    enabled = not any(w in text_lower for w in ['отключи', 'выключи', 'выруби', 'офф', 'стоп'])
    if toggle_wifi(enabled): handler.play_response()

def _sys_bluetooth_toggle(handler, text_lower, amount):
    from actions.system import toggle_bluetooth
    enabled = not any(w in text_lower for w in ['отключи', 'выключи', 'выруби', 'офф', 'стоп'])
    if toggle_bluetooth(enabled): handler.play_response()

def _set_hud_guard_status(active: bool) -> None:
    try:
        from ui import hud as _hud_mod
        h = getattr(_hud_mod, '_hud', None)
        if h:
            from ui.hud_camera import set_guard_status
            h._hud_queue.put(lambda: set_guard_status(h, active))
    except Exception:
        pass

def _sys_guard_on(handler, text_lower, amount):
    from features.guard import start_guard
    handler.speak(spk('guard.activating'))
    ok, res = start_guard()
    if ok:
        handler.speak(spk('guard.on'))
        _set_hud_guard_status(True)
    else:
        handler.speak(spk('guard.on_error', res=res))

def _sys_guard_off(handler, text_lower, amount):
    from features.guard import stop_guard
    ok, res = stop_guard()
    if ok:
        handler.speak(spk('guard.off'))
        _set_hud_guard_status(False)
    else:
        handler.speak(spk('guard.not_active'))

def _sys_shutdown_timer(handler, text_lower, amount):
    from core.nlp import extract_duration_seconds
    from actions.system_control import schedule_shutdown
    delay = extract_duration_seconds(text_lower)
    if delay > 0:
        schedule_shutdown(delay)
        handler.speak(spk("shutdown.timer_ok", delay=_fmt_delay(delay)))
    else:
        handler.speak(spk("shutdown.timer_error"))

def _sys_keyboard_lock(handler, text_lower, amount):
    from actions.system import disable_keyboards_hardware
    ok, res = disable_keyboards_hardware()
    handler.speak(res)

def _sys_keyboard_unlock(handler, text_lower, amount):
    from actions.system import enable_keyboards_hardware
    ok, res = enable_keyboards_hardware()
    handler.speak(res)

def _sys_jarvis_exit(handler, text_lower, amount):
    handler.speak(spk("shutdown.now"), wait=True)
    import os; os._exit(0)

def _sys_show_hud(handler, text_lower, amount):
    try:
        from ui.hud import show_hud
        show_hud()
    except Exception:
        pass

def _sys_show_help(handler, text_lower, amount):
    try:
        from ui.hud import _hud as _h
        from ui.dialogs.welcome_dlg import open_welcome
        if _h is not None:
            _h._hud_queue.put(lambda: open_welcome(_h, force=True))
    except Exception:
        pass

def _sys_restart_jarvis(handler, text_lower, amount):
    # wait=True blocks until the phrase actually finishes playing, instead
    # of guessing a fixed sleep duration (which could cut the phrase off
    # for a longer sentence, or add needless delay for a shorter one).
    handler.speak(spk("restart.jarvis_now"), wait=True)
    import sys, subprocess, os as _os
    try:
        if getattr(sys, 'frozen', False):
            subprocess.Popen([sys.executable], creationflags=0x00000008)
        else:
            subprocess.Popen([sys.executable] + sys.argv)
    except Exception:
        pass
    finally:
        _os._exit(0)

def _sys_listen_off(handler, text_lower, amount):
    app_state.ignore_mode = True
    handler.speak(spk("listen.off_v2"))

def _sys_listen_on(handler, text_lower, amount):
    app_state.ignore_mode = False
    handler.speak(spk("listen.on"))

def _sys_economy_on(handler, text_lower, amount):
    import subprocess
    subprocess.run(['powercfg', '/setactive', 'a1841308-3541-4fab-bc81-f71556f20b4a'], creationflags=134217728)
    handler.speak(spk("economy.on"))

def _sys_economy_off(handler, text_lower, amount):
    import subprocess
    subprocess.run(['powercfg', '/setactive', '381b4222-f694-41f0-9685-ff5bb260df2e'], creationflags=134217728)
    handler.speak(spk("economy.off"))

def _sys_cancel_timer(handler, text_lower, amount):
    from actions.system_control import cancel_shutdown
    cancel_shutdown()
    handler.speak(spk("shutdown.cancel"))

def _sys_reminder(handler, text_lower, amount):
    from core.nlp import extract_duration_seconds
    from features.reminder import schedule_reminder, extract_reminder_text
    delay = extract_duration_seconds(text_lower)
    if delay <= 0:
        # Couldn't parse a duration from the original phrase — ask instead
        # of just erroring out. Handled by 'reminder_ask' in interactive.py,
        # which also uses schedule_reminder() so the HUD countdown widget
        # shows up regardless of which turn supplied the duration.
        handler.speak(spk("reminder.ask_time"))
        handler._set_interactive('reminder_ask', {}, timeout=30.0)
        return
    msg = extract_reminder_text(text_lower)
    hud = getattr(app_state, 'hud', None)
    schedule_reminder(delay, msg, handler.speak, hud)
    handler.speak(spk("reminder.set_ok", delay=_fmt_delay(delay)))

_SYSTEM_ACTIONS = {
    'shutdown': _sys_shutdown,
    'restart': _sys_restart,
    'dictation_on': _sys_dictation_on,
    'system_cleanup': _sys_cleanup,
    'internet_speed': _sys_internet_speed,
    'brightness_set': _sys_brightness_set,
    'brightness_up': _sys_brightness_up,
    'brightness_down': _sys_brightness_down,
    'wifi_toggle': _sys_wifi_toggle,
    'bluetooth_toggle': _sys_bluetooth_toggle,
    'guard_on': _sys_guard_on,
    'guard_off': _sys_guard_off,
    'shutdown_timer': _sys_shutdown_timer,
    'keyboard_lock': _sys_keyboard_lock,
    'keyboard_unlock': _sys_keyboard_unlock,
    'jarvis_exit': _sys_jarvis_exit,
    'show_hud': _sys_show_hud,
    'show_help': _sys_show_help,
    'restart_jarvis': _sys_restart_jarvis,
    'listen_off': _sys_listen_off,
    'listen_on': _sys_listen_on,
    'economy_on': _sys_economy_on,
    'economy_off': _sys_economy_off,
    'cancel_timer': _sys_cancel_timer,
    'reminder': _sys_reminder,
}

def handle_system(handler, cmd, text_lower, amount):
    action = _SYSTEM_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, amount)
