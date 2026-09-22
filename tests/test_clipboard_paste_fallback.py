"""Regression test for a real bug: ui/dialogs/extensions_common.py's
_bind_ctk_entry_clipboard bound Ctrl+V/Ctrl+A/Ctrl+C to handlers that always
returned 'break', even when the handler itself failed to read the clipboard
or select text. Tk's native Entry widget already implements Ctrl+V/Ctrl+A
correctly via the built-in <<Paste>>/<<SelectAll>> virtual events — but
returning 'break' unconditionally swallows the key event and prevents that
native fallback from ever running, turning "our extra logic failed" into
"Ctrl+V and Ctrl+A do nothing at all" (reported 2026-09-22 across the mail,
calendar, and LLM API key settings dialogs).

These tests capture the actual bound callback (via a Tk widget, which runs
headlessly fine in this environment) and verify it returns None — not
'break' — when it can't do anything, so native key handling isn't blocked.
The same fix was applied identically to the duplicated _add_context_menu
copies in ui/dialogs/settings_tabs/{appearance,tools,voice}.py.
"""
import tkinter as tk

import pytest

from ui.dialogs.extensions_common import _bind_ctk_entry_clipboard


class _FakeHud:
    _F = 'Consolas'


def _capture_bound_callback(entry, sequence):
    """Returns the last python callback bound to `sequence` on `entry`,
    by intercepting Widget.bind while _bind_ctk_entry_clipboard registers
    its handlers."""
    captured = {}
    orig_bind = tk.Widget.bind

    def _spy_bind(self, seq=None, func=None, add=None):
        if seq == sequence and func is not None:
            captured['fn'] = func
        return orig_bind(self, seq, func, add)

    tk.Widget.bind = _spy_bind
    try:
        _bind_ctk_entry_clipboard(entry.master, entry, _FakeHud())
    finally:
        tk.Widget.bind = orig_bind
    return captured.get('fn')


@pytest.fixture
def root():
    # tk.Tk() init occasionally races with something else on first use in
    # this environment (observed: transient "Can't find a usable init.tcl"),
    # unrelated to the code under test — retry once rather than flake.
    try:
        r = tk.Tk()
    except tk.TclError:
        r = tk.Tk()
    yield r
    r.destroy()


def test_paste_returns_none_not_break_when_clipboard_unreadable(root, monkeypatch):
    entry = tk.Entry(root)
    entry.pack()

    # Simulate total clipboard failure: no pyperclip, and Tk's own
    # clipboard_get() also raises (e.g. no clipboard owner).
    monkeypatch.setattr(root, 'clipboard_get', lambda: (_ for _ in ()).throw(tk.TclError('no clipboard')))
    import builtins
    real_import = builtins.__import__
    def _no_pyperclip(name, *a, **k):
        if name == 'pyperclip':
            raise ImportError('no pyperclip')
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', _no_pyperclip)

    fn = _capture_bound_callback(entry, '<Control-v>')
    assert fn is not None
    result = fn(None)
    assert result is None  # must NOT be 'break' — native <<Paste>> must still get a chance


def test_paste_returns_break_and_inserts_text_on_success(root, monkeypatch):
    entry = tk.Entry(root)
    entry.pack()
    root.clipboard_clear()
    root.clipboard_append('pasted-value')
    root.update()

    fn = _capture_bound_callback(entry, '<Control-v>')
    result = fn(None)
    assert result == 'break'
    assert entry.get() == 'pasted-value'


def test_select_all_returns_none_on_failure(root, monkeypatch):
    entry = tk.Entry(root)
    entry.pack()

    def _boom(*a, **k):
        raise tk.TclError('simulated failure')
    monkeypatch.setattr(entry, 'select_range', _boom)

    fn = _capture_bound_callback(entry, '<Control-a>')
    result = fn(None)
    assert result is None


def test_select_all_returns_break_on_success(root):
    entry = tk.Entry(root)
    entry.insert(0, 'some text')
    entry.pack()

    fn = _capture_bound_callback(entry, '<Control-a>')
    result = fn(None)
    assert result == 'break'
