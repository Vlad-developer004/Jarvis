from actions.clipboard import (
    clipboard_copy, clipboard_paste, clipboard_cut, clipboard_paste_nth,
    clipboard_open_history, undo_action, redo_action, select_all
)

def _clip_copy(handler, text_lower, amount):
    if clipboard_copy(): handler.play_response()

def _clip_paste(handler, text_lower, amount):
    query = text_lower
    for kw in ['вставь это', 'вставь', 'вставить', 'ставь']:
        if query.startswith(kw):
            query = query[len(kw):].strip()
            break
    if query and query not in ('это', ''):
        from actions.system_parts.files_paste import find_and_paste_file
        ok, res = find_and_paste_file(target_filename=query)
        if ok:
            handler.play_response()
        else:
            handler.speak(res)
    else:
        if clipboard_paste(): handler.play_response()

def _clip_cut(handler, text_lower, amount):
    if clipboard_cut(): handler.play_response()

def _clip_history(handler, text_lower, amount):
    clipboard_open_history(); handler.play_response()

def _clip_paste_last(handler, text_lower, amount):
    if clipboard_paste_nth(0): handler.play_response()

def _clip_paste_prev(handler, text_lower, amount):
    if clipboard_paste_nth(1): handler.play_response()

def _clip_paste_n(handler, text_lower, amount):
    idx = max(0, amount - 1)
    if clipboard_paste_nth(idx): handler.play_response()

def _undo(handler, text_lower, amount):
    undo_action(); handler.play_response()

def _redo(handler, text_lower, amount):
    redo_action(); handler.play_response()

def _select_all(handler, text_lower, amount):
    select_all(); handler.play_response()

_CLIP_ACTIONS = {
    'clip_copy': _clip_copy,
    'clip_paste': _clip_paste,
    'clip_cut': _clip_cut,
    'clip_history': _clip_history,
    'clip_paste_last': _clip_paste_last,
    'clip_paste_prev': _clip_paste_prev,
    'clip_paste_n': _clip_paste_n,
    'undo': _undo,
    'redo': _redo,
    'select_all': _select_all,
}

def handle_clip(handler, cmd, text_lower, amount):
    action = _CLIP_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, amount)
