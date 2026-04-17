from actions.clipboard import (
    clipboard_copy, clipboard_paste, clipboard_cut, clipboard_paste_nth,
    clipboard_open_history, undo_action, redo_action, select_all
)
def handle_clip(handler, cmd, text_lower, amount):
    if cmd == 'clip_copy':
        if clipboard_copy(): handler.play_response()
    elif cmd == 'clip_paste':
        if clipboard_paste(): handler.play_response()
    elif cmd == 'clip_cut':
        if clipboard_cut(): handler.play_response()
    elif cmd == 'clip_history':
        clipboard_open_history(); handler.play_response()
    elif cmd == 'clip_paste_last':
        if clipboard_paste_nth(0): handler.play_response()
    elif cmd == 'clip_paste_prev':
        if clipboard_paste_nth(1): handler.play_response()
    elif cmd == 'clip_paste_n':
        idx = max(0, amount - 1)
        if clipboard_paste_nth(idx): handler.play_response()
    elif cmd == 'undo':
        undo_action(); handler.play_response()
    elif cmd == 'redo':
        redo_action(); handler.play_response()
    elif cmd == 'select_all':
        select_all(); handler.play_response()
