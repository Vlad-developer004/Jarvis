"""The answer picture lookup (verified TLS only) and the window's guard command."""
import io
import json

import pytest

from actions import wiki_image


class Resp:
    def __init__(self, body: bytes):
        self._b = io.BytesIO(body)

    def read(self, n=-1):
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_picture_is_found_downloaded_and_cached(monkeypatch, tmp_path):
    calls = []

    def fake_open(req, timeout=0, **kw):
        assert 'context' not in kw, 'certificates must be verified'
        calls.append(req.full_url)
        if 'api.php' in req.full_url:
            return Resp(json.dumps({'query': {'pages': {'1': {'index': 1, 'title': 'Марс', 'thumbnail': {'source': 'https://upload.test/mars.jpg'}}}}}).encode())
        return Resp(b'JPEGDATA')
    monkeypatch.setattr(wiki_image.urllib.request, 'urlopen', fake_open)
    monkeypatch.setattr(wiki_image.tempfile, 'gettempdir', lambda: str(tmp_path))
    path = wiki_image.wiki_image_path('Марс')
    assert path and open(path, 'rb').read() == b'JPEGDATA'
    n = len(calls)
    assert wiki_image.wiki_image_path('Марс') == path and len(calls) == n + 1      # only the search again; the picture comes from the cache


def test_plain_http_pictures_are_refused(monkeypatch, tmp_path):
    def fake_open(req, timeout=0, **kw):
        return Resp(json.dumps({'query': {'pages': {'1': {'index': 1, 'title': 'x', 'thumbnail': {'source': 'http://evil.test/a.jpg'}}}}}).encode())
    monkeypatch.setattr(wiki_image.urllib.request, 'urlopen', fake_open)
    monkeypatch.setattr(wiki_image.tempfile, 'gettempdir', lambda: str(tmp_path))
    assert wiki_image.wiki_image_path('x') is None


def test_network_errors_give_none(monkeypatch):
    def boom(*a, **k):
        raise OSError('offline')
    monkeypatch.setattr(wiki_image.urllib.request, 'urlopen', boom)
    assert wiki_image.wiki_image_path('x') is None


def test_the_source_never_builds_an_unverified_context():
    src = open(wiki_image.__file__, encoding='utf-8').read()
    assert '_create_unverified_context' not in src and 'CERT_NONE' not in src


# ---- the guard command ----
def test_guard_command_reports_and_switches(monkeypatch):
    from features import guard
    from ui_next import bridge
    state = {'on': False}
    monkeypatch.setattr(guard, 'is_active', lambda: state['on'])
    done = []
    monkeypatch.setattr(guard, 'start_guard', lambda: done.append('start') or state.update(on=True) or (True, 'OK'))
    monkeypatch.setattr(guard, 'stop_guard', lambda: done.append('stop') or state.update(on=False) or (True, 'OK'))
    assert bridge.run_command('guard', {}) == {'ok': True, 'on': False}
    assert bridge.run_command('guard', {'on': True}) == {'ok': True, 'pending': True}
    import time
    for _ in range(50):
        if done:
            break
        time.sleep(0.02)
    assert done == ['start'] and bridge.run_command('guard', {})['on'] is True
    bridge.run_command('guard', {'on': False})
    for _ in range(50):
        if len(done) == 2:
            break
        time.sleep(0.02)
    assert done == ['start', 'stop']


def test_a_failed_guard_start_shows_a_notice(monkeypatch):
    from features import guard
    from ui_next import bridge, host
    monkeypatch.setattr(guard, 'start_guard', lambda: (False, 'camera error'))
    bridge.run_command('guard', {'on': True})
    import time
    for _ in range(50):
        if host.active_notices():
            break
        time.sleep(0.02)
    assert any('camera error' in n[1] for n in host.active_notices())
    host.clear_notify('guard')


def test_the_observer_publishes_the_guard_and_notices(monkeypatch):
    import sys
    import types

    from ui_next import host
    from ui_next.bridge.observer import Observer
    seen = []
    ob = Observer(lambda topic, payload, sticky=True: seen.append((topic, payload)))
    fake = types.SimpleNamespace(is_active=lambda: True)
    monkeypatch.setitem(sys.modules, 'features.guard', fake)
    host.notify('t', 'hello', host.AMBER)
    try:
        ob._tick()
    finally:
        host.clear_notify('t')
    assert ('guard', {'on': True}) in seen
    assert ('notices', [{'id': 't', 'text': 'hello', 'sev': 'warn'}]) in seen
