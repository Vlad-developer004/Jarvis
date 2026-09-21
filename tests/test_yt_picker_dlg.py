"""Regression tests for ui/dialogs/yt_picker_dlg.py.

The 2026-09 production crash this guards against: _finish() was changed to
take (choice, idx), but two call sites — the 20s auto-timeout and the
window's X-button (WM_DELETE_WINDOW) — were left calling _finish(None) with
only one argument. Tkinter callback exceptions don't propagate or crash the
app; they just print a traceback and the window is left open in a stuck
state with no way to resolve it — from the user's side, the picker "hung"
and any answer after that point (voice or click) went nowhere. Needs a real
Tk display; skips cleanly if one isn't available.
"""
import time

import pytest

tk = pytest.importorskip('tkinter')


@pytest.fixture
def tk_root():
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as e:
        pytest.skip(f'no display available: {e}')
    yield root
    root.destroy()


def _candidates():
    return [
        {'id': 'a', 'title': 'X', 'url': 'u1', 'thumbnail': None},
        {'id': 'b', 'title': 'Y', 'url': 'u2', 'thumbnail': None},
    ]


def test_timeout_resolves_without_crashing(tk_root):
    from ui.dialogs.yt_picker_dlg import open_yt_picker, is_picker_open

    timed_out = []
    open_yt_picker(
        tk_root_fake(tk_root), _candidates(),
        on_select=lambda c, i: None, on_timeout=lambda: timed_out.append(True),
        timeout_sec=0.2,
    )
    deadline = time.time() + 2.0
    while time.time() < deadline and not timed_out:
        tk_root.update()
        time.sleep(0.02)
    assert timed_out == [True]
    assert not is_picker_open()


def test_close_button_cancels_without_playing_anything(tk_root):
    # Regression: the X button used to be wired to the same code path as a
    # real timeout, so closing the dialog auto-played the top result anyway
    # — from the user's side, clicking "no" still started a video. It must
    # resolve through on_cancel instead, and on_timeout must NOT fire.
    from ui.dialogs.yt_picker_dlg import open_yt_picker, is_picker_open

    timed_out, cancelled = [], []
    open_yt_picker(
        tk_root_fake(tk_root), _candidates(),
        on_select=lambda c, i: None,
        on_timeout=lambda: timed_out.append(True),
        on_cancel=lambda: cancelled.append(True),
        timeout_sec=30.0,
    )
    tk_root.update()
    win = tk_root.winfo_children()[0]
    close_cmd = win.tk.call('wm', 'protocol', win._w, 'WM_DELETE_WINDOW')
    win.tk.call(close_cmd)  # simulates the user clicking the titlebar X
    tk_root.update()
    assert cancelled == [True]
    assert timed_out == []
    assert not is_picker_open()


def test_cancel_picker_does_not_play_anything(tk_root):
    from ui.dialogs.yt_picker_dlg import open_yt_picker, cancel_picker, is_picker_open

    timed_out, cancelled = [], []
    open_yt_picker(
        tk_root_fake(tk_root), _candidates(),
        on_select=lambda c, i: None,
        on_timeout=lambda: timed_out.append(True),
        on_cancel=lambda: cancelled.append(True),
        timeout_sec=30.0,
    )
    tk_root.update()
    cancel_picker()
    tk_root.update()
    assert cancelled == [True]
    assert timed_out == []
    assert not is_picker_open()


def test_real_timeout_still_calls_on_timeout_not_on_cancel(tk_root):
    from ui.dialogs.yt_picker_dlg import open_yt_picker, is_picker_open

    timed_out, cancelled = [], []
    open_yt_picker(
        tk_root_fake(tk_root), _candidates(),
        on_select=lambda c, i: None,
        on_timeout=lambda: timed_out.append(True),
        on_cancel=lambda: cancelled.append(True),
        timeout_sec=0.2,
    )
    deadline = time.time() + 2.0
    while time.time() < deadline and not timed_out:
        tk_root.update()
        time.sleep(0.02)
    assert timed_out == [True]
    assert cancelled == []
    assert not is_picker_open()


def test_click_select_passes_index(tk_root):
    from ui.dialogs.yt_picker_dlg import open_yt_picker, select_index

    picked = []
    open_yt_picker(
        tk_root_fake(tk_root), _candidates(),
        on_select=lambda c, i: picked.append((c, i)), on_timeout=None,
        timeout_sec=30.0,
    )
    tk_root.update()
    assert select_index(1) is True
    tk_root.update()
    assert picked == [({'id': 'b', 'title': 'Y', 'url': 'u2', 'thumbnail': None}, 1)]


def tk_root_fake(root):
    """A minimal stand-in for the real HUD object — open_yt_picker only
    ever touches `.root`."""
    class _FakeHud:
        pass
    h = _FakeHud()
    h.root = root
    return h
