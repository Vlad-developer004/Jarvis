"""The code that picks windows (YouTube/media control) works from win_list.snapshot()."""
from actions import win_list
from actions.win_list import Win


def _w(hwnd, title, exe, iconic=False):
    return Win(hwnd, title, exe, True, iconic, 'Chrome_WidgetWin_1')


def test_control_youtube_picks_the_foreground_browser_window_with_a_media_title(monkeypatch):
    import win32gui

    import actions.youtube as yt
    wins = [_w(1, 'Some page - Brave', 'brave.exe'), _w(2, 'cats - YouTube - Brave', 'brave.exe'), _w(3, 'notes', 'notepad.exe'), _w(4, '', '')]
    monkeypatch.setattr(win_list, 'snapshot', lambda visible_only=False: wins)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 1)
    sent = []
    monkeypatch.setattr(win32gui, 'SendMessage', lambda h, m, w, l: sent.append(h))
    assert yt.control_youtube('play_pause') is True
    assert sent == [1]   # the window the user was looking at wins over the YouTube-titled one


def test_control_youtube_prefers_the_youtube_tab_when_nothing_is_in_front(monkeypatch):
    import win32gui

    import actions.youtube as yt
    wins = [_w(1, 'Some page - Brave', 'brave.exe'), _w(2, 'cats - YouTube - Brave', 'brave.exe')]
    monkeypatch.setattr(win_list, 'snapshot', lambda visible_only=False: wins)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 999)
    sent = []
    monkeypatch.setattr(win32gui, 'SendMessage', lambda h, m, w, l: sent.append(h))
    assert yt.control_youtube('play_pause') is True and sent == [2]


def test_control_youtube_without_any_browser_returns_false(monkeypatch):
    import win32gui

    import actions.youtube as yt
    monkeypatch.setattr(win_list, 'snapshot', lambda visible_only=False: [_w(3, 'notes', 'notepad.exe')])
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 3)
    assert yt.control_youtube('play_pause') is False


def test_a_failing_snapshot_is_treated_as_no_windows(monkeypatch):
    import win32gui

    import actions.youtube as yt
    def boom(visible_only=False):
        raise OSError('enum failed')
    monkeypatch.setattr(win_list, 'snapshot', boom)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 0)
    assert yt.control_youtube('play_pause') is False


def test_send_play_pause_categorises_windows_from_the_snapshot(monkeypatch, capsys):
    import win32gui

    from actions.system_parts import media
    wins = [_w(10, 'Docs - Brave', 'brave.exe'), _w(20, 'cats - YouTube - Brave', 'brave.exe'), _w(30, 'x', 'notepad.exe')]
    monkeypatch.setattr(win_list, 'snapshot', lambda visible_only=False: wins)
    monkeypatch.setattr(win32gui, 'GetForegroundWindow', lambda: 0)
    monkeypatch.setattr(media.time, 'sleep', lambda t: None)
    media.send_play_pause_to_video(prefer='youtube', action='toggle')   # fake handles: the later Win32 calls may fail, the scan must not
    out = capsys.readouterr().out
    assert 'Scanning 3 windows' in out and 'YTBrowser=1' in out and 'PureBrowser=1' in out and 'HWND: 20' in out
