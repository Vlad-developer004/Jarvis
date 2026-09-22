"""Tests for core/handler/commands/utils.py — bluetooth, session
save/restore/delete, command macros, keyboard layout switching. Previously
untested; covers the text-stripping parsers that turn a raw utterance into a
session/command name (a bug here silently saves/loads the wrong slot) plus
the exact-command dispatch table.
"""
import threading

import core.handler.commands.utils as utils_cmd


class _FakeHandler:
    def __init__(self):
        self.spoken = []
        self.play_response_calls = []

    def speak(self, text):
        self.spoken.append(text)

    def play_response(self, *a, **k):
        self.play_response_calls.append((a, k))


class _ImmediateThread:
    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


def _immediate_threads(monkeypatch):
    monkeypatch.setattr(threading, 'Thread', _ImmediateThread)


# ── handle_utils routing ──────────────────────────────────────────────────

def test_handle_utils_routes_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(utils_cmd._UTILS_EXACT, 'bt_list', lambda h, t: called.append(t))
    handler = _FakeHandler()

    utils_cmd.handle_utils(handler, 'bt_list', 'какие устройства подключены')

    assert called == ['какие устройства подключены']


def test_handle_utils_unknown_command_does_nothing():
    handler = _FakeHandler()
    utils_cmd.handle_utils(handler, 'nonexistent', 'text')
    assert handler.spoken == []


def test_utils_exact_keys_are_real_intents():
    from core.nlp.intents import INTENTS
    unknown = set(utils_cmd._UTILS_EXACT.keys()) - set(INTENTS.keys())
    assert not unknown, f'_UTILS_EXACT has non-existent intent keys: {unknown}'


# ── bluetooth ─────────────────────────────────────────────────────────────

def test_bt_connect_with_device_name_starts_background_task(monkeypatch):
    _immediate_threads(monkeypatch)
    connected = []
    monkeypatch.setattr(utils_cmd, 'bt_connect', lambda name: connected.append(name) or (True, 'ok'))
    monkeypatch.setattr(utils_cmd, '_bt_handle_result', lambda *a, **k: None)
    handler = _FakeHandler()

    utils_cmd._bt_connect(handler, 'подключи блютуз наушники')

    assert connected == ['наушники']


def test_bt_connect_without_device_name_lists_paired_devices(monkeypatch):
    monkeypatch.setattr(utils_cmd, 'bt_list', lambda: ['Наушники', 'Мышь'])
    handler = _FakeHandler()

    utils_cmd._bt_connect(handler, 'подключи блютуз')

    assert handler.spoken and 'Наушники' in handler.spoken[0]


def test_bt_connect_speaks_none_when_no_paired_devices(monkeypatch):
    monkeypatch.setattr(utils_cmd, 'bt_list', lambda: [])
    handler = _FakeHandler()

    utils_cmd._bt_connect(handler, 'подключи блютуз')

    assert handler.spoken


def test_bt_disconnect_with_empty_target_does_nothing(monkeypatch):
    _immediate_threads(monkeypatch)
    monkeypatch.setattr(utils_cmd, 'bt_disconnect',
                         lambda name: (_ for _ in ()).throw(AssertionError('must not be called')))
    handler = _FakeHandler()

    utils_cmd._bt_disconnect(handler, 'отключи')

    assert handler.spoken == []


# ── session save/restore/delete name parsing ─────────────────────────────

def test_session_save_strips_keywords_to_get_name(monkeypatch):
    _immediate_threads(monkeypatch)
    saved = []
    monkeypatch.setattr(utils_cmd, 'save_session',
                         lambda name, speak, play: saved.append(name))
    handler = _FakeHandler()

    utils_cmd._session_save(handler, 'сохрани сессию работа')

    assert saved == ['работа']


def test_session_save_defaults_to_default_name_when_empty(monkeypatch):
    _immediate_threads(monkeypatch)
    saved = []
    monkeypatch.setattr(utils_cmd, 'save_session', lambda name, speak, play: saved.append(name))
    handler = _FakeHandler()

    utils_cmd._session_save(handler, 'сохрани сессию')

    assert saved == ['default']


def test_session_restore_strips_keywords_to_get_name(monkeypatch):
    _immediate_threads(monkeypatch)
    restored = []
    monkeypatch.setattr(utils_cmd, 'restore_session', lambda name, play: restored.append(name))
    handler = _FakeHandler()

    utils_cmd._session_restore(handler, 'восстанови сессию работа')

    assert restored == ['работа']


def test_session_delete_strips_keywords_and_deletes(monkeypatch):
    deleted = []
    monkeypatch.setattr(utils_cmd, 'delete_session', lambda name: deleted.append(name) or True)
    handler = _FakeHandler()

    utils_cmd._session_delete(handler, 'удали сессию работа')

    assert deleted == ['работа']
    assert handler.play_response_calls


# ── command macros ────────────────────────────────────────────────────────

def test_command_save_extracts_name_and_saves(monkeypatch):
    saved = []
    monkeypatch.setattr(utils_cmd, 'save_command', lambda name: saved.append(name) or True)
    handler = _FakeHandler()

    utils_cmd._command_save(handler, 'запомни команду как открой проект')

    assert saved == ['открой проект']
    assert handler.play_response_calls


def test_command_save_empty_name_does_not_save(monkeypatch):
    monkeypatch.setattr(utils_cmd, 'save_command',
                         lambda name: (_ for _ in ()).throw(AssertionError('must not save empty name')))
    handler = _FakeHandler()

    utils_cmd._command_save(handler, 'запомни команду')

    assert handler.play_response_calls == []


def test_command_get_extracts_name_and_executes(monkeypatch):
    executed = []
    monkeypatch.setattr(utils_cmd, 'get_command', lambda name: executed.append(name) or True)
    handler = _FakeHandler()

    utils_cmd._command_get(handler, 'выполни команду открой проект')

    assert executed == ['открой проект']


def test_command_delete_with_name_present_deletes_without_dialog(monkeypatch):
    deleted = []
    monkeypatch.setattr(utils_cmd, 'delete_command', lambda name: deleted.append(name) or True)
    handler = _FakeHandler()

    utils_cmd._command_delete(handler, 'удали команду открой проект')

    assert deleted == ['открой проект']


# ── change_layout language detection ──────────────────────────────────────

def test_change_layout_detects_english(monkeypatch):
    captured = []
    monkeypatch.setattr(utils_cmd, 'change_keyboard_layout',
                         lambda target: captured.append(target) or (True, 'ok'))
    handler = _FakeHandler()

    utils_cmd._change_layout(handler, 'переключи на английскую раскладку')

    assert captured == ['английский']


def test_change_layout_defaults_to_russian(monkeypatch):
    captured = []
    monkeypatch.setattr(utils_cmd, 'change_keyboard_layout',
                         lambda target: captured.append(target) or (True, 'ok'))
    handler = _FakeHandler()

    utils_cmd._change_layout(handler, 'переключи раскладку')

    assert captured == ['русский']


def test_change_layout_detects_ukrainian(monkeypatch):
    captured = []
    monkeypatch.setattr(utils_cmd, 'change_keyboard_layout',
                         lambda target: captured.append(target) or (True, 'ok'))
    handler = _FakeHandler()

    utils_cmd._change_layout(handler, 'на украинскую мову')

    assert captured == ['украинский']
