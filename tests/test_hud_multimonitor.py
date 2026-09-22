"""Tests for ui/hud_utils.py's multi-monitor work-area resolution
(_get_work_area / _monitor_work_area_physical). Before this change every
dialog centered/sized itself against the primary monitor only
(SystemParametersInfoW / winfo_screenwidth), so on a multi-monitor setup a
dialog opened while Jarvis sat on a secondary monitor would place itself
relative to monitor 0 instead. These tests fake the win32 monitor-enum API
via monkeypatch (ctypes.windll.user32) rather than requiring an actual
multi-monitor rig."""
import ctypes
from ctypes import wintypes

import pytest

from ui import hud_utils


class _FakeRoot:
    def winfo_screenwidth(self):
        return 1920


class _FakeWindow:
    """Stand-in for a Tk widget: only winfo_id() is used by _get_work_area."""
    def __init__(self, hwnd=12345):
        self._hwnd = hwnd

    def winfo_id(self):
        return self._hwnd


@pytest.fixture(autouse=True)
def _no_scaling(monkeypatch):
    # Pin the logical/physical scale factor to 1.0 so returned coordinates
    # match the fake monitor rects exactly, and avoid touching the real
    # display via tk._default_root.
    import tkinter as tk
    monkeypatch.setattr(tk, '_default_root', _FakeRoot())
    monkeypatch.setattr(ctypes.windll.user32, 'GetSystemMetrics', lambda i: 1920)


def _set_monitor_info(monkeypatch, rect):
    left, top, right, bottom = rect

    def _fake_get_monitor_info(hmon, mi_ptr):
        mi = mi_ptr.contents if hasattr(mi_ptr, 'contents') else mi_ptr
        mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom = left, top, right, bottom
        return 1

    monkeypatch.setattr(ctypes.windll.user32, 'GetMonitorInfoW', _fake_get_monitor_info)


def test_get_work_area_uses_monitor_of_given_window(monkeypatch):
    # Secondary monitor sitting to the right of a 1920-wide primary.
    secondary_rect = (1920, 0, 3840, 1080)
    monkeypatch.setattr(ctypes.windll.user32, 'MonitorFromWindow', lambda hwnd, flags: 99)
    _set_monitor_info(monkeypatch, secondary_rect)

    result = hud_utils._get_work_area(_FakeWindow())
    assert result == secondary_rect


def test_get_work_area_uses_point_for_tuple_ref(monkeypatch):
    secondary_rect = (-1920, 0, 0, 1080)
    monkeypatch.setattr(ctypes.windll.user32, 'MonitorFromPoint', lambda pt, flags: 7)
    _set_monitor_info(monkeypatch, secondary_rect)

    result = hud_utils._get_work_area((-500, 200))
    assert result == secondary_rect


def test_get_work_area_falls_back_to_primary_without_ref(monkeypatch):
    primary_rect = (0, 0, 1920, 1040)

    def _fake_spi(action, param, rect_ptr, wini):
        rect_ptr.left, rect_ptr.top, rect_ptr.right, rect_ptr.bottom = primary_rect
        return 1

    monkeypatch.setattr(ctypes.windll.user32, 'SystemParametersInfoW', _fake_spi)

    result = hud_utils._get_work_area()
    assert result == primary_rect


def test_get_work_area_falls_back_to_primary_when_monitor_lookup_fails(monkeypatch):
    # MonitorFromWindow returns a null handle -> _monitor_work_area_physical
    # returns None -> must still fall back to SystemParametersInfoW, not crash.
    monkeypatch.setattr(ctypes.windll.user32, 'MonitorFromWindow', lambda hwnd, flags: 0)
    primary_rect = (0, 0, 1920, 1040)

    def _fake_spi(action, param, rect_ptr, wini):
        rect_ptr.left, rect_ptr.top, rect_ptr.right, rect_ptr.bottom = primary_rect
        return 1

    monkeypatch.setattr(ctypes.windll.user32, 'SystemParametersInfoW', _fake_spi)

    result = hud_utils._get_work_area(_FakeWindow())
    assert result == primary_rect


def test_monitor_work_area_physical_returns_none_without_hwnd_or_point():
    assert hud_utils._monitor_work_area_physical() is None


def test_center_window_picks_master_monitor_over_own(monkeypatch):
    # _center_window should resolve the monitor via window.master, not the
    # (freshly-created, unpositioned) window itself.
    secondary_rect = (1920, 0, 3840, 1080)
    seen = {}

    def _fake_get_work_area(ref=None):
        seen['ref'] = ref
        return secondary_rect

    monkeypatch.setattr(hud_utils, '_get_work_area', _fake_get_work_area)

    master = _FakeWindow(hwnd=1)
    win = _FakeWindow(hwnd=2)
    win.master = master
    win.update_idletasks = lambda: None
    win.geometry = lambda *a, **k: None

    import tkinter as tk
    monkeypatch.setattr(tk.Toplevel, 'geometry', lambda self, g: seen.setdefault('geometry', g))

    hud_utils._center_window(win, 400, 300)
    assert seen['ref'] is master


def test_constrain_window_uses_target_point_monitor(monkeypatch):
    seen = {}

    def _fake_get_work_area(ref=None):
        seen['ref'] = ref
        return (1920, 0, 3840, 1080)

    monkeypatch.setattr(hud_utils, '_get_work_area', _fake_get_work_area)

    win = _FakeWindow()
    win.winfo_rooty = lambda: 100
    win.winfo_y = lambda: 90
    win.winfo_rootx = lambda: 2000
    win.winfo_x = lambda: 1995
    win.winfo_height = lambda: 300
    win.winfo_width = lambda: 400

    hud_utils._constrain_window(win, 2500, 200)
    assert seen['ref'] == (2500, 200)
