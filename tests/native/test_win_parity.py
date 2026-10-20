"""jarvis_win.list_windows must describe the live windows exactly as the pywin32 snapshot does (it may read more process names)."""
import sys

import pytest

from actions import win_list


def _pywin32_snapshot():
    import win32gui

    from core.system.windows import get_hwnd_process_name
    out = {}

    def each(hwnd, _):
        out[hwnd] = win_list.Win(hwnd, win32gui.GetWindowText(hwnd), get_hwnd_process_name(hwnd), bool(win32gui.IsWindowVisible(hwnd)), bool(win32gui.IsIconic(hwnd)), win32gui.GetClassName(hwnd))
        return True
    win32gui.EnumWindows(each, None)
    return out

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='Windows only')


def test_native_list_matches_pywin32_on_the_live_desktop(native_win):
    rows = {r[0]: r for r in native_win.list_windows()}
    py = _pywin32_snapshot()
    assert rows and set(rows) == set(py) or len(set(rows) ^ set(py)) <= 3   # a window may open or close between the two calls
    for hwnd in set(rows) & set(py):
        _, title, exe, visible, iconic, cls = rows[hwnd]
        p = py[hwnd]
        assert (title, visible, iconic, cls) == (p.title, p.visible, p.iconic, p.cls)
        assert p.exe in ('', exe)   # pywin32 cannot read some processes, the native lister can


def test_visible_only_drops_hidden_windows(native_win):
    assert all(r[3] for r in native_win.list_windows(True))
    assert len(native_win.list_windows(True)) <= len(native_win.list_windows(False))


def test_the_snapshot_wrapper_returns_win_rows(native_win):
    rows = win_list.snapshot()
    assert rows and isinstance(rows[0], win_list.Win)
    assert all(w.visible for w in win_list.snapshot(visible_only=True))


def test_the_snapshot_raises_when_the_module_is_missing(monkeypatch):
    from core import native
    monkeypatch.setattr(native, '_loaded', {})
    monkeypatch.setitem(sys.modules, 'jarvis_win', None)
    with pytest.raises(native.NativeUnavailable):
        win_list.snapshot()
