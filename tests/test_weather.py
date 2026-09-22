"""Tests for actions/weather.py and actions/weather_forecast.py.

Covers the two regressions found while building today's weather features:
  - get_forecast()/get_weather_period() raising unhandled instead of
    returning (False, ...) on a network failure, which silently killed the
    background TTS thread in core/handler/commands/info.py._weather (see
    _w_task) with no spoken error at all.
  - _format_current_weather_text repeating "20 градусов, ощущается как
    20 градусов" when feel-like equals the actual temperature.
"""
import json
import os

import pytest

from actions import weather, weather_forecast


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Point get_settings_path() at a throwaway file so these tests never
    read or write the real %LOCALAPPDATA%\\Jarvis\\jarvis_settings.json."""
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr(weather, 'get_settings_path', lambda: settings_path)
    weather._weather_cache.clear()
    weather._hud_cache.clear()
    yield


def test_format_current_weather_omits_feels_like_when_equal_to_temp():
    text = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru')
    assert 'ощущается' not in text


def test_format_current_weather_includes_feels_like_when_different():
    text = weather._format_current_weather_text('Киев', 'Ясно', 10, 5, 'ru')
    assert 'ощущается' in text
    assert '5 градусов' in text


def test_yesterday_compare_adds_sentence_above_threshold(monkeypatch):
    import time as _time
    from datetime import date, timedelta

    weather._save_today_temp(10)
    # _save_today_temp only writes once per calendar day, so directly craft
    # a snapshot dated "yesterday" to exercise the comparison branch.
    settings_path = weather.get_settings_path()
    with open(settings_path, 'r', encoding='utf-8') as f:
        s = json.load(f)
    s['weather_yesterday'] = {'date': (date.today() - timedelta(days=1)).isoformat(), 'temp': 5}
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(s, f)

    text = weather._yesterday_compare_text(20, 'ru')
    assert 'теплее' in text
    assert '15' in text


def test_yesterday_compare_silent_below_threshold():
    from datetime import date, timedelta
    settings_path = weather.get_settings_path()
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump({'weather_yesterday': {'date': (date.today() - timedelta(days=1)).isoformat(), 'temp': 19}}, f)
    assert weather._yesterday_compare_text(20, 'ru') == ''


def test_get_forecast_returns_error_tuple_on_network_failure(monkeypatch):
    monkeypatch.setattr(weather_forecast, 'resolve_location', lambda city, lang: (50.0, 30.0, 'Киев'))

    def _boom(*a, **kw):
        raise RuntimeError('network down')

    import requests
    monkeypatch.setattr(requests, 'get', _boom)

    ok, text = weather_forecast.get_forecast(None, 1)
    assert ok is False
    assert 'Ошибка' in text


def test_get_weather_period_returns_error_tuple_on_network_failure(monkeypatch):
    monkeypatch.setattr(weather_forecast, 'resolve_location', lambda city, lang: (50.0, 30.0, 'Киев'))

    def _boom(*a, **kw):
        raise RuntimeError('network down')

    import requests
    monkeypatch.setattr(requests, 'get', _boom)

    ok, text = weather_forecast.get_weather_period(None, 'вечером')
    assert ok is False
    assert 'Ошибка' in text


def test_get_weather_delegates_forecast_errors_without_crashing(monkeypatch):
    # get_weather()'s date_offset != 0 branch must not let an exception from
    # weather_forecast.get_forecast propagate — that's what killed _w_task.
    def _boom(city, offset):
        raise RuntimeError('boom')

    monkeypatch.setattr(weather_forecast, 'get_forecast', _boom)
    ok, text = weather.get_weather(None, date_offset=1)
    assert ok is False
    assert 'Ошибка' in text


def test_extract_date_offset_recognizes_tomorrow():
    offset, rest = weather_forecast.extract_date_offset('погода завтра')
    assert offset == 1
    assert 'завтра' not in rest


def test_extract_period_strips_matched_word():
    period, rest = weather_forecast.extract_period('погода вечером')
    assert period == 'вечером'
    assert 'вечером' not in rest


def test_extract_period_returns_none_when_absent():
    period, rest = weather_forecast.extract_period('погода')
    assert period is None
    assert rest == 'погода'
