"""Hub limits and the window's Content-Security-Policy."""
import json
import os
import time
import urllib.error
import urllib.request

import pytest

from ui_next.bridge import hub as hubmod
from ui_next.bridge.hub import Hub

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TAURI_CONF = os.path.join(ROOT, 'ui_next', 'shell', 'src-tauri', 'tauri.conf.json')


@pytest.fixture
def hub():
    h = Hub()
    h.start()
    yield h
    h.stop()


def _get(h, path='/events', token=None, headers=None):
    req = urllib.request.Request(f'http://127.0.0.1:{h.port}{path}?token={token or h.token}', headers=headers or {})
    return urllib.request.urlopen(req, timeout=5)


def _post(h, body, token=None, headers=None, raw=None):
    data = raw if raw is not None else json.dumps(body).encode()
    req = urllib.request.Request(f'http://127.0.0.1:{h.port}/cmd?token={token or h.token}', data=data, headers={'Content-Type': 'application/json', **(headers or {})}, method='POST')
    return urllib.request.urlopen(req, timeout=5)


def test_event_streams_are_capped(hub, monkeypatch):
    monkeypatch.setattr(hubmod, '_MAX_CLIENTS', 3)
    open_streams = []
    try:
        for _ in range(3):
            r = _get(hub)
            r.readline()
            open_streams.append(r)
        assert hub.client_count() == 3
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(hub)
        assert e.value.code == 429
        open_streams.pop().close()
        for _ in range(60):                 # a closed stream is noticed on the next write to it
            hub.publish('tick', {}, sticky=False)
            if hub.client_count() < 3:
                break
            time.sleep(0.05)
        assert _get(hub).status == 200
    finally:
        for r in open_streams:
            r.close()


def test_command_endpoint_checks_token_origin_and_host(hub):
    hub.command_handler = lambda cmd, data: {'ok': True, 'cmd': cmd}
    assert json.load(_post(hub, {'cmd': 'ping'})) == {'ok': True, 'cmd': 'ping'}
    for kwargs in ({'token': 'nope'}, {'headers': {'Origin': 'https://evil.example'}}, {'headers': {'Host': 'attacker.example'}}):
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(hub, {'cmd': 'ping'}, **kwargs)
        assert e.value.code == 403


def test_command_endpoint_rejects_bad_bodies(hub):
    hub.command_handler = lambda cmd, data: {'ok': True}
    for raw in (b'', b'not json', b'[]', b'{"no_cmd": 1}', b'x' * 400_001):
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(hub, None, raw=raw)
        assert e.value.code == 400, raw[:20]


def test_unknown_command_and_failing_command_do_not_break_the_server(hub):
    hub.command_handler = lambda cmd, data: None
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'nothing'})
    assert e.value.code == 404

    def boom(cmd, data):
        raise RuntimeError('secret detail')
    hub.command_handler = boom
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'x'})
    assert e.value.code == 500
    assert b'secret detail' not in e.value.read()
    hub.command_handler = lambda cmd, data: {'ok': True}
    assert json.load(_post(hub, {'cmd': 'x'})) == {'ok': True}


def test_only_known_paths_exist(hub):
    for path in ('/', '/admin', '/events/../cmd'):
        with pytest.raises(urllib.error.HTTPError) as e:
            _get(hub, path)
        assert e.value.code == 404


def test_the_server_listens_on_loopback_only(hub):
    assert hub._server.server_address[0] == '127.0.0.1'


def test_the_window_has_a_strict_content_security_policy():
    csp = json.load(open(TAURI_CONF, encoding='utf-8'))['app']['security']['csp']
    assert csp, 'csp must be set'
    directives = {d.split()[0]: d.split()[1:] for d in (x.strip() for x in csp.split(';')) if d}
    assert directives['default-src'] == ["'self'"]
    assert directives['object-src'] == ["'none'"] and directives['base-uri'] == ["'none'"] and directives['form-action'] == ["'none'"]
    assert 'unsafe-eval' not in csp and '*' not in directives['default-src']
    assert all(src != '*' for src in directives['connect-src']), 'connect-src must name the loopback bridge, not any host'
    assert any(src.startswith('http://127.0.0.1') for src in directives['connect-src'])
    assert 'http://ipc.localhost' in directives['connect-src']
