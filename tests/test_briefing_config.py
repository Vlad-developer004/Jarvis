"""Tests for actions/briefing_config.py's load_briefing_prefs() — defaults,
validation bounds for calendar_reminder_minutes, and type-checked overrides
from settings.json. Previously untested.
"""
import json

import actions.briefing_config as cfg


def test_load_briefing_prefs_returns_defaults_when_settings_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', tmp_path / 'jarvis_settings.json')

    prefs = cfg.load_briefing_prefs()

    assert prefs == cfg._DEFAULT


def test_load_briefing_prefs_applies_boolean_overrides(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'include_weather': False}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs['include_weather'] is False
    assert prefs['include_greeting'] is True  # untouched default


def test_load_briefing_prefs_applies_valid_reminder_minutes(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'calendar_reminder_minutes': 30}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs['calendar_reminder_minutes'] == 30


def test_load_briefing_prefs_rejects_out_of_range_reminder_minutes(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'calendar_reminder_minutes': 500}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs['calendar_reminder_minutes'] == cfg._DEFAULT['calendar_reminder_minutes']


def test_load_briefing_prefs_rejects_non_numeric_reminder_minutes(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'calendar_reminder_minutes': 'soon'}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs['calendar_reminder_minutes'] == cfg._DEFAULT['calendar_reminder_minutes']


def test_load_briefing_prefs_ignores_non_bool_value_for_bool_key(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'include_weather': 'yes'}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    # A string isn't a bool -> ignored, default preserved
    assert prefs['include_weather'] is True


def test_load_briefing_prefs_ignores_unknown_keys(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'totally_unknown_key': True}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert 'totally_unknown_key' not in prefs


def test_load_briefing_prefs_recovers_from_corrupt_json(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text('{not valid json', encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs == cfg._DEFAULT


def test_load_briefing_prefs_ignores_briefing_key_that_is_not_a_dict(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': 'not a dict'}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    prefs = cfg.load_briefing_prefs()

    assert prefs == cfg._DEFAULT


def test_load_briefing_prefs_does_not_mutate_default_dict(tmp_path, monkeypatch):
    settings_file = tmp_path / 'jarvis_settings.json'
    settings_file.write_text(json.dumps({'briefing': {'include_weather': False}}), encoding='utf-8')
    monkeypatch.setattr(cfg, '_SETTINGS_PATH', settings_file)

    cfg.load_briefing_prefs()

    assert cfg._DEFAULT['include_weather'] is True  # module-level default untouched
