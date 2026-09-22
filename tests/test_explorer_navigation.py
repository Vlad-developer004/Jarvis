"""Tests for actions/explorer.py's navigate_to_system_folder() — exact and
fuzzy folder-name matching against SYSTEM_FOLDERS, and the special '..'
parent-navigation case. open_in_explorer() itself drives real Shell/COM
window navigation and is mocked throughout.
"""
import os

import actions.explorer as explorer


def test_navigate_exact_match_known_folder(monkeypatch):
    navigated = []
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: navigated.append(path) or True)

    ok, target = explorer.navigate_to_system_folder('загрузки')

    assert ok is True
    assert target == os.path.join(explorer.USER_HOME, 'Downloads')
    assert navigated == [target]


def test_navigate_case_and_whitespace_insensitive(monkeypatch):
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: True)

    ok, target = explorer.navigate_to_system_folder('  ЗАГРУЗКИ  ')

    assert ok is True
    assert target.endswith('Downloads')


def test_navigate_fuzzy_matches_close_misspelling(monkeypatch):
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: True)

    # 'загрзки' is a plausible ASR mishearing of 'загрузки'
    ok, target = explorer.navigate_to_system_folder('загрзки')

    assert ok is True
    assert target.endswith('Downloads')


def test_navigate_recycle_bin_uses_shell_path(monkeypatch):
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: True)

    ok, target = explorer.navigate_to_system_folder('корзина')

    assert ok is True
    assert target == 'shell:RecycleBinFolder'


def test_navigate_parent_dots_goes_up_from_active_explorer(monkeypatch):
    monkeypatch.setattr(explorer, 'get_active_explorer_path', lambda: 'C:\\Users\\me\\Documents\\sub')
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: True)

    ok, target = explorer.navigate_to_system_folder('назад')

    assert ok is True
    assert target == 'C:\\Users\\me\\Documents'


def test_navigate_parent_dots_fails_when_already_at_root(monkeypatch):
    monkeypatch.setattr(explorer, 'get_active_explorer_path', lambda: 'C:\\')

    ok, msg = explorer.navigate_to_system_folder('назад')

    assert ok is False


def test_navigate_parent_dots_fails_without_active_explorer(monkeypatch):
    monkeypatch.setattr(explorer, 'get_active_explorer_path', lambda: None)

    ok, msg = explorer.navigate_to_system_folder('наверх')

    assert ok is False
    assert 'проводник' in msg.lower() or 'явно' in msg.lower() or 'нет' in msg.lower()


def test_navigate_unrelated_query_not_found_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(explorer, 'get_active_explorer_path', lambda: None)
    # Ensure the on-disk fallback search finds nothing either
    monkeypatch.setattr('core.system.windows.get_known_folder_path', lambda k: None)
    monkeypatch.setattr('actions.filesystem._find_folder_anywhere', lambda roots, name, max_depth: None)
    monkeypatch.setattr('actions.filesystem._get_search_depth', lambda: 2)

    ok, msg = explorer.navigate_to_system_folder('совершенно неизвестная папка xyz123')

    assert ok is False


def test_navigate_calls_open_in_explorer_failure_returns_error(monkeypatch):
    monkeypatch.setattr(explorer, 'open_in_explorer', lambda path: False)

    ok, msg = explorer.navigate_to_system_folder('документы')

    assert ok is False
