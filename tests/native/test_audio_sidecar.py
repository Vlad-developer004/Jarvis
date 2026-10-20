"""The real jarvis_audio program: skipped unless it is built (cargo build --release -p jarvis_audio in native/)."""
import json
import subprocess

import pytest

from core import native

pytestmark = pytest.mark.skipif(native.sidecar_path('audio') is None, reason='jarvis_audio.exe is not built')


def _run(*args):
    return subprocess.run([native.sidecar_path('audio'), *args], capture_output=True, text=True, timeout=10)   # nosec B603


def test_version():
    assert _run('--version').stdout.strip().count('.') == 2


def test_query_output_prints_one_json_line_with_a_verdict():
    p = _run('--query-output')
    info = json.loads(p.stdout)
    if info['ok']:   # a machine without a playback device answers ok=false and exit code 1
        assert p.returncode == 0 and isinstance(info['is_headphones'], bool) and info['kind'] and info['name']
    else:
        assert p.returncode == 1 and info['error']


def test_unknown_command_fails_cleanly():
    p = _run('--nope')
    assert p.returncode == 2 and p.stdout == ''


def test_serve_answers_ping_and_survives_bad_input():
    p = subprocess.run([native.sidecar_path('audio'), '--serve'], input='{"op":"ping","id":7}\nnot json\n{"op":"nope"}\n', capture_output=True, text=True, timeout=10)   # nosec B603
    a = [json.loads(x) for x in p.stdout.splitlines()]
    assert a[0] == {'id': 7, 'ok': True, 'version': a[0]['version']}
    assert a[1]['ok'] is False and 'bad json' in a[1]['error']
    assert a[2]['ok'] is False and 'unknown op' in a[2]['error']
    assert p.returncode == 0   # stdin ended: a clean exit


def test_serve_sessions_and_duck_never_crash_even_without_a_device():
    req = '{"op":"sessions"}\n{"op":"duck","enable":true,"skip_pid":1}\n{"op":"duck","enable":false}\n{"op":"unduck"}\n{"op":"master_get"}\n'
    p = subprocess.run([native.sidecar_path('audio'), '--serve'], input=req, capture_output=True, text=True, timeout=15)   # nosec B603
    answers = [json.loads(x) for x in p.stdout.splitlines()]
    assert len(answers) == 5 and p.returncode == 0
    assert all(isinstance(a['ok'], bool) for a in answers)
