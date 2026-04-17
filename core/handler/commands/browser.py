from actions.windows import (
    close_tab, close_tab_by_index, open_new_tab, goto_tab, close_all_tabs
)
from actions.system import open_browser_history
def handle_browser(handler, cmd, text_lower, amount):
    if cmd == 'browser_tab':
        if amount > 0:
            if goto_tab(amount): handler.play_response()
        else:
            if open_new_tab(): handler.play_response()
    elif cmd == 'close_tab':
        if close_tab(): handler.play_response()
    elif cmd == 'close_tab_n':
        if amount > 0:
            if close_tab_by_index(amount): handler.play_response()
    elif cmd == 'close_all_tabs':
        if close_all_tabs(): handler.play_response()
    elif cmd == 'open_browser_history':
        if open_browser_history()[0]: handler.play_response()
