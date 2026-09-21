from actions.windows import (
    minimize_all_windows, minimize_current_window, unminimize_last_window,
    close_current_window, close_all_windows, close_other_windows,
    minimize_other_windows, maximize_current_window, snap_window, move_to_monitor
)
from core.responses import spk

def _min_all(handler, text_lower, amount):
    success, msg = minimize_all_windows()
    if not success:
        import pyautogui
        try:
            pyautogui.hotkey('win', 'd')
            handler.play_response()
        except Exception:
            handler.speak(spk('win.min_all_error', msg=msg))
    else:
        handler.play_response()

def _min_win(handler, text_lower, amount):
    minimize_current_window(); handler.play_response()

def _unmin_win(handler, text_lower, amount):
    unminimize_last_window(); handler.play_response()

def _max_win(handler, text_lower, amount):
    maximize_current_window(); handler.play_response()

def _close_win(handler, text_lower, amount):
    close_current_window(); handler.play_response()

def _close_all_win(handler, text_lower, amount):
    close_all_windows(); handler.play_response()

def _close_other_win(handler, text_lower, amount):
    close_other_windows(); handler.play_response()

def _min_other_win(handler, text_lower, amount):
    minimize_other_windows(); handler.play_response()

def _move_monitor(handler, text_lower, amount):
    if move_to_monitor(amount or 1): handler.play_response()
    else: handler.speak(spk('win.move_error'))

def _win_snap(handler, cmd, text_lower, amount):
    direction = cmd.replace('win_snap_', '')
    snap_window(direction); handler.play_response()

_WINDOW_ACTIONS = {
    'min_all': _min_all,
    'min_win': _min_win,
    'unmin_win': _unmin_win,
    'max_win': _max_win,
    'close_win': _close_win,
    'close_all_win': _close_all_win,
    'close_other_win': _close_other_win,
    'min_other_win': _min_other_win,
    'move_monitor': _move_monitor,
}

def handle_window(handler, cmd, text_lower, amount):
    action = _WINDOW_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, amount)
    elif cmd.startswith('win_snap_'):
        _win_snap(handler, cmd, text_lower, amount)
