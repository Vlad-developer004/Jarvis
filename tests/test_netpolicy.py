"""The IP-lookup setting: on by default, and when off nothing asks a third party for the address or the place."""
import pytest

from core import netpolicy, settings_io


@pytest.fixture
def settings(monkeypatch):
    data = {}
    monkeypatch.setattr(settings_io, 'read', lambda: dict(data))
    return data


def test_allowed_by_default_and_switchable(settings):
    assert netpolicy.ip_lookup_allowed() is True
    settings['allow_ip_lookup'] = False
    assert netpolicy.ip_lookup_allowed() is False
    settings['allow_ip_lookup'] = True
    assert netpolicy.ip_lookup_allowed() is True


def test_my_ip_does_not_touch_the_network_when_off(settings, monkeypatch):
    import requests

    from actions import system_control
    settings['allow_ip_lookup'] = False
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('network used'))
    assert 'выключено' in system_control.get_my_ip()


def test_my_ip_asks_the_service_when_on(settings, monkeypatch):
    import requests

    from actions import system_control

    class R:
        text = '203.0.113.7'
    monkeypatch.setattr(requests, 'get', lambda url, **k: R())
    assert '203.0.113.7' in system_control.get_my_ip()


def test_ip_geolocation_is_skipped_when_off(settings, monkeypatch):
    import requests

    from actions import weather
    settings['allow_ip_lookup'] = False
    monkeypatch.setattr(requests, 'get', lambda *a, **k: pytest.fail('network used'))
    monkeypatch.setattr(weather.subprocess if hasattr(weather, 'subprocess') else __import__('subprocess'), 'check_output', lambda *a, **k: b'')
    assert weather._ip_geolocation({}) is None


def test_geolocation_providers_are_https_only(settings, monkeypatch):
    import requests

    from actions import weather
    urls = []

    class R:
        status_code = 500

        def json(self):
            return {}
    monkeypatch.setattr(requests, 'get', lambda url, **k: urls.append(url) or R())
    monkeypatch.setattr(__import__('subprocess'), 'check_output', lambda *a, **k: b'')
    weather._ip_geolocation({})
    assert urls and all(u.startswith('https://') for u in urls)
