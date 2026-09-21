from actions.windows import (
    close_tab, close_tab_by_index, open_new_tab, goto_tab, close_all_tabs
)
from actions.system import open_browser_history

def _browser_tab(handler, text_lower, amount):
    _new_tab_words = ('новую', 'нову', 'создай', 'створи', 'new')
    _wants_new = any(w in text_lower for w in _new_tab_words)
    if amount > 0 and not _wants_new:
        ok, _ = goto_tab(amount)
        if ok: handler.play_response()
    else:
        ok, _ = open_new_tab()
        if ok: handler.play_response()

def _close_tab(handler, text_lower, amount):
    # context_close ("закрой" said bare, with no object) — closes the
    # current browser tab (Ctrl+W). Was previously unreachable: matched
    # by the rule-based intent layer but dispatch.py never routed it
    # anywhere, so saying just "закрой" silently did nothing.
    ok, _ = close_tab()
    if ok: handler.play_response()

def _close_tab_n(handler, text_lower, amount):
    if amount > 0:
        ok, _ = close_tab_by_index(amount)
        if ok: handler.play_response()

def _close_all_tabs(handler, text_lower, amount):
    ok, _ = close_all_tabs()
    if ok: handler.play_response()

def _open_browser_history(handler, text_lower, amount):
    if open_browser_history()[0]: handler.play_response()

_BROWSER_ACTIONS = {
    'browser_tab': _browser_tab,
    'close_tab': _close_tab,
    'context_close': _close_tab,
    'close_tab_n': _close_tab_n,
    'close_all_tabs': _close_all_tabs,
    'open_browser_history': _open_browser_history,
}

def handle_browser(handler, cmd, text_lower, amount):
    action = _BROWSER_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, amount)
