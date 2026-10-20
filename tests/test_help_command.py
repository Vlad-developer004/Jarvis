"""'что ты умеешь' (show_help) opens the commands catalog, not the first-run wizard."""
from core.handler import dispatch
from core.handler.commands import system
from ui_next import host


class _Handler:
    def __init__(self):
        self.said = []

    def speak(self, text, *a, **k):
        self.said.append(text)


def _spy(monkeypatch):
    calls = []
    monkeypatch.setattr(host, 'open_view', lambda name: calls.append(('view', name)) or True)
    monkeypatch.setattr(host, 'open_wizard', lambda: calls.append(('wizard',)) or True)
    return calls


def test_voice_help_shows_the_commands_view(monkeypatch):
    calls = _spy(monkeypatch)
    h = _Handler()
    dispatch._handle_show_help(h, 'show_help', 'что ты умеешь', 0)
    assert calls == [('view', 'commands')] and len(h.said) == 1


def test_the_handler_table_entry_does_the_same(monkeypatch):
    calls = _spy(monkeypatch)
    system._sys_show_help(_Handler(), 'помощь', 0)
    assert calls == [('view', 'commands')]


def test_without_a_window_it_says_so_instead_of_staying_silent(monkeypatch):
    monkeypatch.setattr(host, 'open_view', lambda name: False)
    h = _Handler()
    dispatch._handle_show_help(h, 'show_help', 'помощь', 0)
    assert len(h.said) == 1
