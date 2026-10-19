import json
import time
import urllib.error
import urllib.request

import pytest

from ui_next import bridge
from ui_next.bridge.hub import Hub
from ui_next.bridge.observer import notice_severity


@pytest.fixture
def hub():
    h = Hub()
    h.start()
    yield h
    h.stop()


def _open(h, token=None, origin=None, host=None):
    url = f'http://127.0.0.1:{h.port}/events?token={token or h.token}'
    req = urllib.request.Request(url)
    if origin:
        req.add_header('Origin', origin)
    if host:
        req.add_header('Host', host)
    return urllib.request.urlopen(req, timeout=5)


def _read_events(resp, n):
    """Reads n SSE events as (topic, payload)."""
    out, topic = [], None
    while len(out) < n:
        line = resp.readline().decode('utf-8').rstrip('\n')
        if line.startswith('event: '):
            topic = line[7:]
        elif line.startswith('data: '):
            out.append((topic, json.loads(line[6:])))
    return out


def test_new_client_gets_sticky_snapshot(hub):
    hub.publish('state', {'mode': 'IDLE'})
    hub.publish('game', {'on': True})
    resp = _open(hub)
    assert dict(_read_events(resp, 2)) == {'state': {'mode': 'IDLE'}, 'game': {'on': True}}
    resp.close()


def test_live_event_reaches_connected_client(hub):
    resp = _open(hub)
    time.sleep(0.2)
    hub.publish('heard', {'text': 'привет'}, sticky=False)
    assert _read_events(resp, 1) == [('heard', {'text': 'привет'})]
    resp.close()


def test_non_sticky_event_is_not_replayed(hub):
    hub.publish('level', {'v': 0.5}, sticky=False)
    hub.publish('state', {'mode': 'SPEAKING'})
    resp = _open(hub)
    assert _read_events(resp, 1) == [('state', {'mode': 'SPEAKING'})]
    resp.close()


def test_wrong_token_is_rejected(hub):
    with pytest.raises(urllib.error.HTTPError) as e:
        _open(hub, token='nope')
    assert e.value.code == 403


def test_foreign_origin_is_rejected(hub):
    with pytest.raises(urllib.error.HTTPError) as e:
        _open(hub, origin='https://evil.example')
    assert e.value.code == 403


def test_tauri_origin_is_allowed_and_echoed(hub):
    resp = _open(hub, origin='http://tauri.localhost')
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://tauri.localhost'
    resp.close()


def test_foreign_host_header_is_rejected(hub):
    with pytest.raises(urllib.error.HTTPError) as e:
        _open(hub, host='attacker.example')
    assert e.value.code == 403


def test_discovery_file_roundtrip(hub, tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    path = hub.write_info()
    info = json.load(open(path, encoding='utf-8'))
    assert info['port'] == hub.port and info['token'] == hub.token
    hub.remove_info()
    assert not (tmp_path / 'Jarvis' / 'ui_bridge.json').exists()


@pytest.fixture
def started_bridge(monkeypatch):
    h = Hub()
    monkeypatch.setattr(bridge, '_hub', h)
    monkeypatch.setattr(bridge, '_history', [])
    monkeypatch.setattr(bridge, '_pending_heard', '')
    monkeypatch.setattr(bridge, '_pending_ts', 0.0)
    return h


def _history(h):
    msg = h._last['history']
    return json.loads(msg.split('data: ', 1)[1])


def test_reply_is_paired_with_heard_phrase(started_bridge):
    bridge.heard('открой календарь')
    bridge.reply('Календарь открыт')
    rows = _history(started_bridge)
    assert rows[0]['said'] == 'открой календарь' and rows[0]['did'] == 'Календарь открыт'


def test_streamed_reply_chunks_merge_into_one_row(started_bridge):
    bridge.heard('расскажи про луну')
    bridge.reply('Луна — спутник Земли.')
    bridge.reply('Она вращается вокруг неё.')
    rows = _history(started_bridge)
    assert len(rows) == 1 and 'Она вращается' in rows[0]['did']


def test_reply_without_heard_is_a_row_with_empty_said(started_bridge):
    bridge.reply('Напоминание: созвон')
    assert _history(started_bridge)[0]['said'] == ''


def test_hooks_are_noops_without_a_running_bridge(monkeypatch):
    monkeypatch.setattr(bridge, '_hub', None)
    bridge.heard('x')
    bridge.reply('y')   # must not raise


@pytest.mark.parametrize('color,expected', [('#ff2d55', 'err'), ('#ff6b6b', 'err'), ('#ffbd00', 'warn'), ('#00ffff', 'info'), ('bad', 'info')])
def test_notice_severity(color, expected):
    assert notice_severity(color) == expected


def test_pending_reminders_registry_roundtrip():
    from features import reminder
    fired = []
    # long delay: the daemon thread just sleeps, so no alert sound or window fires during the test
    reminder.schedule_reminder(3600, 'тест', lambda t: fired.append(t))
    try:
        pending = reminder.pending_reminders()
        assert any(msg == 'тест' for _, msg in pending)
        assert all(deadline > time.time() for deadline, _ in pending)
    finally:
        reminder._pending.clear()


def test_cancel_reminder_removes_it_and_stops_the_thread():
    from features import reminder
    fired = []
    reminder.schedule_reminder(3600, 'отмена', lambda t: fired.append(t))
    try:
        rid = next(r for r, _, msg in reminder.pending_items() if msg == 'отмена')
        assert reminder.cancel_reminder(rid) is True
        assert all(msg != 'отмена' for _, _, msg in reminder.pending_items())
        assert reminder.cancel_reminder(rid) is False
        assert fired == []
    finally:
        reminder._pending.clear()
        reminder._cancel_events.clear()


def test_timers_payload_reads_running_timer_and_reminders(monkeypatch):
    import sys
    import types

    from ui_next.bridge.observer import Observer

    fake_timer = types.SimpleNamespace(label='Чай', remaining_sec=lambda: 540, total_sec=lambda: 600)
    gt = types.SimpleNamespace(_lock=__import__('threading').Lock(), _active_timer=fake_timer)
    rm = types.SimpleNamespace(pending_items=lambda: [(7, 2000.5, 'Созвон')])
    monkeypatch.setitem(sys.modules, 'actions.game_timer', gt)
    monkeypatch.setitem(sys.modules, 'features.reminder', rm)
    assert Observer._timers_payload() == {'timer': {'label': 'Чай', 'remaining': 540, 'total': 600}, 'reminders': [{'id': 7, 'text': 'Созвон', 'at': 2000500}]}


def test_timers_payload_empty_when_modules_not_loaded(monkeypatch):
    import sys

    from ui_next.bridge.observer import Observer
    monkeypatch.delitem(sys.modules, 'actions.game_timer', raising=False)
    monkeypatch.delitem(sys.modules, 'features.reminder', raising=False)
    assert Observer._timers_payload() == {'timer': None, 'reminders': []}


def test_display_text_strips_stress_marks_and_markup():
    assert bridge.display_text('Д+а, сэр.') == 'Да, сэр.'
    assert bridge.display_text('Всегд+а к в+ашим усл+угам, сэр.') == 'Всегда к вашим услугам, сэр.'
    assert bridge.display_text('Один <break time="300ms"/> *два*') == 'Один  два'
    assert bridge.display_text('2+2 равно четыре') == '2+2 равно четыре'


def test_reply_history_uses_display_text(started_bridge):
    bridge.reply('Д+а, сэр.')
    assert _history(started_bridge)[0]['did'] == 'Да, сэр.'


def _post(h, body, token=None, origin=None):
    req = urllib.request.Request(f'http://127.0.0.1:{h.port}/cmd?token={token or h.token}', data=json.dumps(body).encode('utf-8'), method='POST')
    req.add_header('Content-Type', 'text/plain')
    if origin:
        req.add_header('Origin', origin)
    return urllib.request.urlopen(req, timeout=5)


def test_command_runs_registered_handler(hub):
    seen = []
    hub.command_handler = lambda cmd, data: (seen.append((cmd, data)) or {'ok': True})
    resp = _post(hub, {'cmd': 'autostart', 'on': True}, origin='http://tauri.localhost')
    assert json.loads(resp.read()) == {'ok': True} and seen == [('autostart', {'on': True})]
    assert resp.headers['Access-Control-Allow-Origin'] == 'http://tauri.localhost'


def test_unknown_command_is_404(hub):
    hub.command_handler = bridge.run_command
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'format_c'})
    assert e.value.code == 404


def test_command_wrong_token_and_origin_rejected(hub):
    hub.command_handler = lambda cmd, data: {'ok': True}
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'x'}, token='bad')
    assert e.value.code == 403
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'x'}, origin='https://evil.example')
    assert e.value.code == 403


def test_malformed_command_body_is_400(hub):
    hub.command_handler = lambda cmd, data: {'ok': True}
    req = urllib.request.Request(f'http://127.0.0.1:{hub.port}/cmd?token={hub.token}', data=b'not json', method='POST')
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=5)
    assert e.value.code == 400


def test_failing_command_is_500_and_server_survives(hub):
    def boom(cmd, data):
        raise RuntimeError('x')
    hub.command_handler = boom
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(hub, {'cmd': 'x'})
    assert e.value.code == 500
    hub.command_handler = lambda cmd, data: {'ok': True}
    assert json.loads(_post(hub, {'cmd': 'x'}).read()) == {'ok': True}


def test_autostart_command_calls_core(monkeypatch):
    import core.system as cs
    calls = []
    monkeypatch.setattr(cs, 'autostart_set', lambda on: calls.append(on))
    monkeypatch.setattr(cs, 'autostart_enabled', lambda: True)
    assert bridge.run_command('autostart', {'on': True}) == {'ok': True, 'on': True}
    assert calls == [True]
