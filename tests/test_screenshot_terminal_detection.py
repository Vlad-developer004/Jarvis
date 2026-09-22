"""Tests for actions/screenshot.py's _is_terminal_window() — the only
self-contained, safely-mockable logic in this module. Everything else
(screenshot_screen, screenshot_terminal, start/stop_video_recording,
screenshot_full_page) drives real mouse drag-selection and keyboard
shortcuts across live windows and is out of scope here, same reasoning as
actions/app_launcher.py and actions/session_ghost.py.
"""
import actions.screenshot as shot


def test_is_terminal_window_matches_known_console_class(monkeypatch):
    monkeypatch.setattr(shot.win32gui, 'GetClassName', lambda hwnd: 'ConsoleWindowClass')
    monkeypatch.setattr(shot.win32gui, 'GetWindowText', lambda hwnd: 'cmd.exe')

    assert shot._is_terminal_window(12345) is True


def test_is_terminal_window_matches_windows_terminal_class(monkeypatch):
    monkeypatch.setattr(shot.win32gui, 'GetClassName', lambda hwnd: 'CASCADIA_HOSTING_WINDOW_CLASS')
    monkeypatch.setattr(shot.win32gui, 'GetWindowText', lambda hwnd: 'Windows Terminal')

    assert shot._is_terminal_window(12345) is True


def test_is_terminal_window_matches_by_title_keyword(monkeypatch):
    monkeypatch.setattr(shot.win32gui, 'GetClassName', lambda hwnd: 'SomeOtherClass')
    monkeypatch.setattr(shot.win32gui, 'GetWindowText', lambda hwnd: 'PowerShell 7')

    assert shot._is_terminal_window(12345) is True


def test_is_terminal_window_false_for_unrelated_window(monkeypatch):
    monkeypatch.setattr(shot.win32gui, 'GetClassName', lambda hwnd: 'Chrome_WidgetWin_1')
    monkeypatch.setattr(shot.win32gui, 'GetWindowText', lambda hwnd: 'YouTube - Brave')

    assert shot._is_terminal_window(12345) is False


def test_is_terminal_window_handles_win32_error_gracefully(monkeypatch):
    def _boom(hwnd):
        raise OSError('invalid window handle')
    monkeypatch.setattr(shot.win32gui, 'GetClassName', _boom)

    assert shot._is_terminal_window(99999) is False
