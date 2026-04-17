import pygetwindow as gw
from actions.windows import (
    minimize_all_windows, minimize_current_window, unminimize_last_window,
    close_current_window, close_all_windows, close_other_windows,
    minimize_other_windows, maximize_current_window, snap_window, move_to_monitor
)
def handle_window(handler, cmd, text_lower, amount):
    if cmd == 'min_all':
        success, msg = minimize_all_windows()
        if not success:
            import pyautogui
            try:
                pyautogui.hotkey('win', 'd')
                handler.play_response()
            except Exception:
                handler.speak(f"Не удалось свернуть все окна: {msg}")
        else:
            handler.play_response()
    elif cmd == 'min_win':
        minimize_current_window(); handler.play_response()
    elif cmd == 'unmin_win':
        unminimize_last_window(); handler.play_response()
    elif cmd == 'max_win':
        maximize_current_window(); handler.play_response()
    elif cmd == 'close_win':
        close_current_window(); handler.play_response()
    elif cmd == 'close_all_win':
        close_all_windows(); handler.play_response()
    elif cmd == 'close_other_win':
        close_other_windows(); handler.play_response()
    elif cmd == 'min_other_win':
        minimize_other_windows(); handler.play_response()
    elif cmd.startswith('win_snap_'):
        direction = cmd.replace('win_snap_', '')
        snap_window(direction); handler.play_response()
    elif cmd == 'move_monitor':
        if move_to_monitor(amount or 1): handler.play_response()
        else: handler.speak('Не удалось переместить окно.')
