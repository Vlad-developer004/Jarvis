"""Regression test for the wake-mode sleep-timeout setting.

Bug: JarvisEngine.active_timeout_sec was hardcoded to 30 at construction,
ignoring the persisted 'wake_word_mode'/'wake_active_timeout_sec' settings —
a user's choice of "single response" mode (should go back to sleep after
every command) silently reverted to the 30s default on every app restart,
only taking effect again if they reopened Settings and re-toggled the radio
button in the same session. Fixed by reading both from settings.json at
startup, same as every other _read_*() config value in config_pack/config.py.
"""
import json

import config_pack.config as cfg


def test_read_wake_word_mode_reflects_settings_file(tmp_path, monkeypatch):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text(json.dumps({'wake_word_mode': 'single'}), encoding='utf-8')
    monkeypatch.setattr(cfg, 'get_settings_path', lambda: str(settings_file))
    assert cfg._read_wake_word_mode() == 'single'


def test_read_wake_active_timeout_reflects_settings_file(tmp_path, monkeypatch):
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text(json.dumps({'wake_active_timeout_sec': 75}), encoding='utf-8')
    monkeypatch.setattr(cfg, 'get_settings_path', lambda: str(settings_file))
    assert cfg._read_wake_active_timeout() == 75.0


def test_read_wake_active_timeout_defaults_to_30_without_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, 'get_settings_path', lambda: str(tmp_path / 'missing.json'))
    assert cfg._read_wake_active_timeout() == 30.0
