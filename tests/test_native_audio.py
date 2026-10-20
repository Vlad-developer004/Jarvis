"""core/native_audio.py and its use in core/audio_utils.py: the sidecar answer wins when it is valid, anything else falls back."""
import json
import subprocess
import sys

import pytest

from core import audio_utils, native, native_audio

GOOD = {'ok': True, 'name': 'Kopfhörer (X)', 'id': '{1}', 'form_factor': 3, 'kind': 'headphones', 'is_headphones': True}


class _Proc:
    def __init__(self, out): self.stdout = out


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(native, 'sidecar_path', lambda name: 'C:/x/jarvis_audio.exe')


def _answer(monkeypatch, out):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: _Proc(out))


def test_valid_answer_is_returned(on, monkeypatch):
    _answer(monkeypatch, json.dumps(GOOD) + '\n')
    assert native_audio.query_output()['is_headphones'] is True


@pytest.mark.parametrize('out', ['', 'not json', '[]', json.dumps({'ok': False, 'error': 'x'}), json.dumps({'ok': True}), json.dumps({'ok': True, 'is_headphones': 'yes'})])
def test_bad_answers_mean_no_answer(on, monkeypatch, out):
    _answer(monkeypatch, out)
    assert native_audio.query_output() is None


@pytest.mark.parametrize('exc', [OSError('gone'), subprocess.TimeoutExpired('x', 2)])
def test_failures_mean_no_answer(on, monkeypatch, exc):
    def boom(*a, **k): raise exc
    monkeypatch.setattr(subprocess, 'run', boom)
    assert native_audio.query_output() is None


def test_missing_sidecar_never_starts_a_process(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('process started'))
    monkeypatch.setattr(native, 'sidecar_path', lambda name: None)
    assert native_audio.query_output() is None


def test_output_check_uses_the_sidecar_answer_and_reports_false_without_one(monkeypatch):
    monkeypatch.setattr(audio_utils, '_last_hp_check', 0.0)
    monkeypatch.setattr(native_audio, 'query_output', lambda: {'is_headphones': True})
    assert audio_utils.is_current_output_headphones() is True

    monkeypatch.setattr(audio_utils, '_last_hp_check', 0.0)
    monkeypatch.setattr(native_audio, 'query_output', lambda: {'is_headphones': False})
    assert audio_utils.is_current_output_headphones() is False

    monkeypatch.setattr(audio_utils, '_last_hp_check', 0.0)
    monkeypatch.setattr(native_audio, 'query_output', lambda: None)
    assert audio_utils.is_current_output_headphones() is False


# ── the long-lived service client ────────────────────────────────────────

FAKE_SERVER = r'''
import json, sys
log = open(sys.argv[1], "a")
for line in sys.stdin:
    req = json.loads(line)
    log.write(json.dumps(req) + "\n"); log.flush()
    op = req.get("op")
    if op == "hang":
        continue
    if op == "die":
        sys.exit(1)
    if op == "noise":
        print("not json", flush=True)
    print(json.dumps({"ok": op != "fail", "echo": op, "id": req["id"]}), flush=True)
log.write("EOF\n"); log.close()
'''


@pytest.fixture
def fake(tmp_path):
    script = tmp_path / 'fake_sidecar.py'
    script.write_text(FAKE_SERVER)
    log = tmp_path / 'log.txt'
    svc = native_audio.Service([sys.executable, str(script), str(log)])
    yield svc, log
    svc.close()


def test_service_matches_answers_and_ignores_noise(fake):
    svc, _ = fake
    assert svc.request(op='ping')['echo'] == 'ping'
    assert svc.request(op='noise')['echo'] == 'noise'   # a garbage line before the answer is skipped
    assert svc.request(op='fail')['ok'] is False


def test_service_keeps_one_process_for_many_requests(fake):
    svc, log = fake
    for _ in range(3):
        svc.request(op='ping')
    pid = svc._proc.pid
    svc.request(op='ping')
    assert svc._proc.pid == pid and log.read_text().count('"op": "ping"') == 4


def test_a_silent_server_times_out_and_is_replaced(fake):
    svc, _ = fake
    assert svc.request(timeout=0.3, op='hang') is None
    assert svc._proc is None
    assert svc.request(op='ping')['echo'] == 'ping'   # the next request starts a fresh process


def test_a_dead_server_returns_none_then_recovers(fake):
    svc, _ = fake
    assert svc.request(op='die') is None
    assert svc.request(op='ping')['ok'] is True


def test_closing_sends_eof_so_the_sidecar_can_restore_volumes(fake):
    svc, log = fake
    svc.request(op='ping')
    svc.close()
    assert log.read_text().strip().endswith('EOF')


def test_service_without_a_sidecar_answers_none(monkeypatch):
    monkeypatch.setattr(native, 'sidecar_path', lambda name: None)
    assert native_audio.Service().request(op='ping') is None


def test_duck_helpers_report_whether_the_sidecar_handled_it(monkeypatch):
    calls = []

    class _Svc:
        def request(self, **kw):
            calls.append(kw)
            return {'ok': True}

    monkeypatch.setattr(native_audio, '_service', _Svc())
    assert native_audio.duck(True) is True and native_audio.unduck() is True
    assert calls[0]['op'] == 'duck' and calls[0]['enable'] is True and calls[0]['skip_pid'] > 0
    assert calls[1] == {'op': 'unduck'}
    monkeypatch.setattr(native_audio, '_service', type('N', (), {'request': lambda self, **kw: None})())
    assert native_audio.duck(True) is False
