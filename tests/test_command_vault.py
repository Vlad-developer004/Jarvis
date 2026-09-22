"""Tests for actions/command_vault.py — voice macro record/replay/delete.
Previously untested. keysend.hotkey() sends real OS-level key events and
must always be mocked here (never let a test send Ctrl+Insert/Shift+Insert
to the host machine); pyperclip is mocked too so tests don't depend on or
mutate the real system clipboard. COMMANDS_FILE is redirected to a tmp_path
file so tests never touch the real data/commands_vault.json.
"""
import json

import pytest

import actions.command_vault as vault


@pytest.fixture(autouse=True)
def _isolated_vault_file(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, 'COMMANDS_FILE', str(tmp_path / 'commands_vault.json'))
    monkeypatch.setattr(vault.keysend, 'hotkey', lambda *keys: None)


class _FakeClipboard:
    def __init__(self, initial=''):
        self._text = initial

    def copy(self, text):
        self._text = text

    def paste(self):
        return self._text


def test_save_command_stores_clipboard_text_under_cleaned_name(monkeypatch):
    # save_command() clears the clipboard then sends ctrl+insert (mocked,
    # no-op) to trigger a "copy" — simulate that copy having landed text.
    monkeypatch.setattr(vault.pyperclip, 'copy', lambda text: None)
    monkeypatch.setattr(vault.pyperclip, 'paste', lambda: 'открой проект')

    ok = vault.save_command('команду тест')

    assert ok is True
    saved = json.loads(open(vault.COMMANDS_FILE, encoding='utf-8').read())
    assert saved['тест'] == 'открой проект'


def test_save_command_fails_when_clipboard_stays_empty(monkeypatch):
    monkeypatch.setattr(vault.pyperclip, 'copy', lambda text: None)
    monkeypatch.setattr(vault.pyperclip, 'paste', lambda: '')

    ok = vault.save_command('команду тест')

    assert ok is False


def test_save_command_defaults_to_default_cmd_name_when_name_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(vault.pyperclip, 'copy', lambda text: None)
    monkeypatch.setattr(vault.pyperclip, 'paste', lambda: 'какой-то текст')

    ok = vault.save_command('команду')  # strips to '' after removing 'команду'

    assert ok is True
    saved = json.loads(open(vault.COMMANDS_FILE, encoding='utf-8').read())
    assert saved['default_cmd'] == 'какой-то текст'


def test_get_command_pastes_saved_text(monkeypatch):
    vault._save_commands({'тест': 'сохранённый текст'})
    clip = _FakeClipboard()
    monkeypatch.setattr(vault.pyperclip, 'copy', clip.copy)
    monkeypatch.setattr(vault.pyperclip, 'paste', clip.paste)

    ok = vault.get_command('команду тест')

    assert ok is True
    assert clip.paste() == 'сохранённый текст'


def test_get_command_returns_false_for_unknown_name(monkeypatch):
    vault._save_commands({'тест': 'x'})
    monkeypatch.setattr(vault.pyperclip, 'copy', lambda text: None)

    ok = vault.get_command('команду несуществующая')

    assert ok is False


def test_delete_command_removes_existing_entry():
    vault._save_commands({'тест': 'x', 'другая': 'y'})

    ok = vault.delete_command('команду тест')

    assert ok is True
    remaining = json.loads(open(vault.COMMANDS_FILE, encoding='utf-8').read())
    assert 'тест' not in remaining
    assert 'другая' in remaining


def test_delete_command_returns_false_for_unknown_name():
    vault._save_commands({'тест': 'x'})

    ok = vault.delete_command('команду несуществующая')

    assert ok is False


def test_load_commands_creates_empty_file_when_missing():
    commands = vault._load_commands()
    assert commands == {}
    import os
    assert os.path.exists(vault.COMMANDS_FILE)


def test_load_commands_recovers_from_corrupt_json(tmp_path):
    with open(vault.COMMANDS_FILE, 'w', encoding='utf-8') as f:
        f.write('{not valid json')

    commands = vault._load_commands()

    assert commands == {}
