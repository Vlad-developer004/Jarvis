"""Tests for actions/session_ghost.py's delete_session() — the one
self-contained, safe-to-test function in this module. save_session() and
restore_session() drive real keyboard/window automation (Ctrl+L, Ctrl+Tab,
focus stealing across every open browser window) to capture/replay browser
tabs and are out of scope here, same reasoning as actions/app_launcher.py.
"""
import json

import actions.session_ghost as ghost


def _isolated_sessions_file(tmp_path, monkeypatch):
    monkeypatch.setattr(ghost, 'SESSIONS_FILE', str(tmp_path / 'sessions.json'))


def test_delete_session_removes_existing_entry(tmp_path, monkeypatch):
    _isolated_sessions_file(tmp_path, monkeypatch)
    ghost._save_sessions({'работа': {'urls': []}, 'игры': {'urls': []}})

    # delete_session() only strips 'сессию'/'работу' itself — the command
    # verb ('удали') is stripped by the caller (core/handler/commands/
    # utils.py::_session_delete) before this is ever invoked in production.
    ok = ghost.delete_session('сессию работа')

    assert ok is True
    remaining = json.loads(open(ghost.SESSIONS_FILE, encoding='utf-8').read())
    assert 'работа' not in remaining
    assert 'игры' in remaining


def test_delete_session_returns_false_for_unknown_name(tmp_path, monkeypatch):
    _isolated_sessions_file(tmp_path, monkeypatch)
    ghost._save_sessions({'работа': {}})

    ok = ghost.delete_session('удали сессию несуществующая')

    assert ok is False


def test_delete_session_defaults_to_default_name_when_stripped_empty(tmp_path, monkeypatch):
    _isolated_sessions_file(tmp_path, monkeypatch)
    ghost._save_sessions({'default': {}})

    ok = ghost.delete_session('сессию')

    assert ok is True


def test_load_sessions_creates_empty_file_when_missing(tmp_path, monkeypatch):
    _isolated_sessions_file(tmp_path, monkeypatch)

    sessions = ghost._load_sessions()

    assert sessions == {}
    import os
    assert os.path.exists(ghost.SESSIONS_FILE)


def test_load_sessions_recovers_from_corrupt_json(tmp_path, monkeypatch):
    _isolated_sessions_file(tmp_path, monkeypatch)
    with open(ghost.SESSIONS_FILE, 'w', encoding='utf-8') as f:
        f.write('{corrupt')

    assert ghost._load_sessions() == {}
