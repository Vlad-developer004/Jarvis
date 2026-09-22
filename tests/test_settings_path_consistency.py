"""Regression guard for a real bug reported 2026-09-22: mail/calendar
settings appeared to silently reset. Root cause — a whole family of modules
each hardcoded their own project-relative 'data/jarvis_settings.json' path
instead of using config_pack.config.get_settings_path()
(%APPDATA%\\Jarvis\\jarvis_settings.json), which is what the rest of the app
(ui/hud_utils.py, weather, gaming_common, etc.) actually reads/writes.
Settings saved through one code path went to a file nothing else read, and a
packaged-build reinstall overwrites the project-relative copy (bundled data/
gets replaced), so it looked like config kept "resetting". Likewise
mail_client._update_env_var wrote the app password to an ad-hoc '.env'
instead of config_pack.config.get_secrets_path(), the file
llm_processor._load_api_key() and the startup loader actually read from.

Found and fixed in: actions/mail_client.py, actions/calendar_ics.py,
actions/network_profiles.py, actions/meetings.py,
actions/programming_extensions.py, actions/dev_projects.py,
actions/filesystem.py (inline, checked via behavior not import-time path),
core/audio_utils.py (inline), ui/dialogs/extensions_common.py,
ui/dialogs/welcome_dlg.py, ui/hud_constants.py (inline).

Most of these modules cache the resolved path at import time as
_SETTINGS_PATH, so this test just asserts that cached value matches the
canonical get_settings_path()/get_secrets_path() — regressing to a
hardcoded relative path would fail this immediately. The two that resolve
the path inline on each call (filesystem.py, audio_utils.py) are instead
checked by verifying they actually read a file written via get_settings_path().
"""
import json
from pathlib import Path

import pytest

from config_pack.config import get_settings_path, get_secrets_path


@pytest.mark.parametrize('module_name', [
    'actions.mail_client',
    'actions.calendar_ics',
    'actions.network_profiles',
    'actions.meetings',
    'actions.programming_extensions',
    'actions.dev_projects',
    'ui.dialogs.extensions_common',
    'ui.dialogs.welcome_dlg',
])
def test_module_settings_path_matches_canonical(module_name):
    import importlib
    mod = importlib.import_module(module_name)
    assert Path(mod._SETTINGS_PATH) == Path(get_settings_path()), (
        f'{module_name}._SETTINGS_PATH does not match the canonical '
        f'get_settings_path() — settings saved elsewhere will not be seen here.'
    )


def test_mail_client_update_env_var_writes_to_canonical_secrets_path(tmp_path, monkeypatch):
    import actions.mail_client as mail_client
    secrets_path = tmp_path / 'secrets.env'
    monkeypatch.setattr(mail_client, 'get_secrets_path', lambda: str(secrets_path))

    mail_client._update_env_var('JARVIS_IMAP_PASS', 'my-app-password')

    assert secrets_path.exists()
    content = secrets_path.read_text(encoding='utf-8')
    assert 'JARVIS_IMAP_PASS="my-app-password"' in content


def test_filesystem_allow_parent_search_reads_canonical_settings_path(tmp_path, monkeypatch):
    import actions.filesystem as fs

    real_settings = tmp_path / 'jarvis_settings.json'
    real_settings.write_text(json.dumps({'allow_parent_search': True}), encoding='utf-8')
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: str(real_settings))

    base = tmp_path / 'base'
    base.mkdir()
    monkeypatch.setattr(fs, '_find_subdir_ci_or_fuzzy', lambda *a, **k: None)
    seen_roots = {}
    def _fake_roots(base_ctx):
        return (['fallback-root'], 3)
    def _fake_find_anywhere(roots, hint, max_depth):
        seen_roots['roots'] = roots
        return None
    monkeypatch.setattr(fs, 'folder_search_roots_and_depth', _fake_roots)
    monkeypatch.setattr(fs, '_find_folder_anywhere', _fake_find_anywhere)

    fs.resolve_folder_for_hint('nonexistent-hint', str(base))

    # allow_parent_search=True (read from our patched canonical settings
    # file) -> roots stay as folder_search_roots_and_depth's wider set,
    # not narrowed to [str(base)] the way allow_parent_search=False would.
    assert seen_roots['roots'] == ['fallback-root']


def test_hud_constants_theme_loader_reads_canonical_settings_path(tmp_path, monkeypatch):
    real_settings = tmp_path / 'jarvis_settings.json'
    real_settings.write_text(json.dumps({'theme': 'dark'}), encoding='utf-8')
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: str(real_settings))

    import ui.hud_constants as hc
    name, _colors = hc._load_theme_colors()
    assert name == 'dark'


def test_audio_utils_reads_canonical_settings_path(tmp_path, monkeypatch):
    real_settings = tmp_path / 'jarvis_settings.json'
    real_settings.write_text(json.dumps({'audio_input_device_index': 7}), encoding='utf-8')
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: str(real_settings))

    import core.audio_utils as au
    settings = au._load_audio_settings()
    assert settings.get('audio_input_device_index') == 7
