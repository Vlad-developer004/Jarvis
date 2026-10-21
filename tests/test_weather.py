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

from actions import weather, weather_forecast, weather_geo
from core import settings_io


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """Point get_settings_path() at a throwaway file so these tests never
    read or write the real %LOCALAPPDATA%\\Jarvis\\jarvis_settings.json."""
    settings_path = str(tmp_path / 'jarvis_settings.json')
    monkeypatch.setattr('config_pack.config.get_settings_path', lambda: settings_path)
    weather._weather_cache.clear()
    weather._hud_cache.clear()
    weather_geo._city_names.clear()
    yield


def test_format_current_weather_omits_feels_like_when_equal_to_temp():
    text = weather._format_current_weather_text('Киев', 'Ясно', 20, 20, 'ru')
    assert 'ощущается' not in text


def test_format_current_weather_includes_feels_like_when_different():
    text = weather._format_current_weather_text('Киев', 'Ясно', 10, 5, 'ru')
    assert 'ощущается' in text
    assert '5 градусов' in text


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


# ── geocoding and location ────────────────────────────────────────────────

def _fake_geocoder(monkeypatch, table):
    """table: {query: [result names]}; records the queries so tests can see how many lookups happened."""
    calls = []

    def _geocode(name, lang):
        calls.append(name)
        return [{'name': n, 'latitude': 1.0, 'longitude': 2.0} for n in table.get(name, [])]
    monkeypatch.setattr(weather_geo, '_geocode', _geocode)
    return calls


def test_geocode_keeps_a_nominative_name_that_ends_like_a_case_form(monkeypatch):
    calls = _fake_geocoder(monkeypatch, {'Одесса': ['Одесса'], 'Одесс': ['Одесс-что-то']})
    assert weather_geo.geocode_city('Одесса', 'ru')[2] == 'Одесса'
    assert calls == ['Одесса']


def test_geocode_retries_a_prepositional_name_without_its_last_letter(monkeypatch):
    calls = _fake_geocoder(monkeypatch, {'Москве': ['Москвеш'], 'Москв': ['Москва']})
    assert weather_geo.geocode_city('Москве', 'ru')[2] == 'Москва'
    assert calls == ['Москве', 'Москв']


def test_geocode_falls_back_to_the_first_guess_for_the_original_name(monkeypatch):
    _fake_geocoder(monkeypatch, {'Берлине': ['Берлинер']})
    assert weather_geo.geocode_city('Берлине', 'ru')[2] == 'Берлинер'


def test_geocode_unknown_city_is_none(monkeypatch):
    _fake_geocoder(monkeypatch, {})
    assert weather_geo.geocode_city('Нигдея', 'ru') is None
    assert weather_geo.resolve_location('Нигдея', 'ru') == (None, None, 'Нигдея')


def test_resolve_location_without_a_city_uses_manual_city_setting(monkeypatch):
    settings_io.update({'manual_city': 'Киев'})
    _fake_geocoder(monkeypatch, {'Киев': ['Киев']})
    assert weather_geo.resolve_location(None, 'ru') == (1.0, 2.0, 'Киев')


def test_localized_city_is_looked_up_once_per_place(monkeypatch):
    import requests
    hits = []

    class R:
        def json(self):
            return {'city': 'Kyiv'}
    monkeypatch.setattr(requests, 'get', lambda *a, **k: hits.append(a) or R())
    assert weather_geo.localized_city(50.45, 30.52, 'Киев', 'en') == 'Kyiv'
    assert weather_geo.localized_city(50.45, 30.52, 'Киев', 'en') == 'Kyiv'
    assert len(hits) == 1


def test_localized_city_sends_nothing_when_ip_lookups_are_off(monkeypatch):
    import requests
    settings_io.update({'allow_ip_lookup': False})
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('network used'))
    assert weather_geo.localized_city(50.45, 30.52, 'Киев', 'ru') == 'Киев'


# ── yesterday comparison comes with the forecast ──────────────────────────

def _stub_snapshot(monkeypatch):
    snap = {'desc': 'Ясно', 'temp': 20, 'feels': 20, 'wind': 1.0}
    monkeypatch.setattr(weather, '_fetch_snapshot', lambda *a, **k: snap)
    monkeypatch.setattr(weather, 'resolve_location', lambda city, lang: (1.0, 2.0, city or 'Киев'))


def test_hud_falls_back_when_the_settings_file_is_unreadable(monkeypatch):
    """The except path used to hit a NameError when the failure came before headers/lat were bound."""
    def _boom(lang):
        raise RuntimeError('settings broken')
    monkeypatch.setattr(weather, 'home_location', _boom)
    data = weather.get_weather_hud()
    assert data['ok'] is False


# ── "fetching" phrase is skipped only when the text cache really has the answer ──

def test_voice_cache_check_matches_the_key_get_weather_stores(monkeypatch):
    _stub_snapshot(monkeypatch)
    assert weather.is_weather_voice_cached('Берлин') is False
    weather.get_weather('Берлин')
    assert weather.is_weather_voice_cached('Берлин') is True
    assert weather.is_weather_voice_cached('берлин', 0) is True
    assert weather.is_weather_voice_cached('Берлин', 1) is False
    assert weather.is_weather_voice_cached('Берлин', 0, 'вечером') is False
    assert weather.is_weather_voice_cached(None) is False
    weather.get_weather(None)
    assert weather.is_weather_voice_cached(None) is True


def test_forecast_error_text_does_not_leak_the_exception(monkeypatch):
    monkeypatch.setattr(weather_forecast, 'resolve_location', lambda city, lang: (50.0, 30.0, 'Киев'))

    def _boom(*a, **kw):
        raise RuntimeError('secret-host.internal refused')
    import requests
    monkeypatch.setattr(requests, 'get', _boom)
    ok, text = weather_forecast.get_forecast(None, 1)
    assert not ok and 'secret-host' not in text
    ok, text = weather_forecast.get_weather_period(None, 'вечером')
    assert not ok and 'secret-host' not in text
