"""Tests for ui/dialogs/extensions_common.py::_hud_popup_menu — the themed
right-click popup that replaced plain tk.Menu across the entry-field context
menus (mail, calendar, LLM API key, appearance/tools/voice settings tabs).
tk.Menu renders with unstyled native OS chrome on Windows (small system
font, no theming) regardless of bg/fg/font kwargs passed to it, which is
what the 2026-09-22 "некрасиво смотрится" report was about; _hud_popup_menu
is a plain Toplevel + Label rows instead, so it's actually skinnable."""
import tkinter as tk

import pytest

from ui.dialogs.extensions_common import _hud_popup_menu


class _FakeHud:
    _F = 'Consolas'


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError:
        r = tk.Tk()
    yield r
    r.destroy()


def test_popup_creates_a_row_per_item_and_a_separator(root):
    calls = []
    _hud_popup_menu(root, 10, 10, _FakeHud(), [
        ('Paste', lambda: calls.append('paste')),
        ('Copy', lambda: calls.append('copy')),
        None,
        ('Select all', lambda: calls.append('select_all')),
    ])
    root.update()
    popups = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
    assert len(popups) == 1
    top = popups[0]
    inner = top.winfo_children()[0]
    labels = [w for w in inner.winfo_children() if isinstance(w, tk.Label)]
    assert [l.cget('text') for l in labels] == ['Paste', 'Copy', 'Select all']
    top.destroy()


def test_clicking_a_row_runs_its_command_and_closes_popup(root):
    calls = []
    _hud_popup_menu(root, 10, 10, _FakeHud(), [
        ('Paste', lambda: calls.append('paste')),
    ])
    root.update()
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    inner = top.winfo_children()[0]
    row = [w for w in inner.winfo_children() if isinstance(w, tk.Label)][0]

    row.event_generate('<ButtonRelease-1>')
    root.update()

    assert calls == ['paste']
    assert not top.winfo_exists()


def test_popup_is_borderless_and_topmost(root):
    _hud_popup_menu(root, 10, 10, _FakeHud(), [('X', lambda: None)])
    root.update()
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    assert top.overrideredirect()
    top.destroy()


def test_popup_stays_on_screen_near_bottom_right_corner(root):
    root.update()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    _hud_popup_menu(root, sw + 500, sh + 500, _FakeHud(), [
        ('Paste', lambda: None), ('Copy', lambda: None),
    ])
    root.update()
    top = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    x = top.winfo_x()
    y = top.winfo_y()
    assert x < sw
    assert y < sh
    top.destroy()
