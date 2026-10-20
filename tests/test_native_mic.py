"""core/native_audio.MicStream: the frames protocol, the engine-facing read()/close(), and errors; a scripted program stands in for the sidecar."""
import json
import struct
import sys

import pytest

from core import audio_utils, native, native_audio

FAKE = r'''
import json, struct, sys, time
def frame(kind, payload):
    sys.stdout.buffer.write(bytes([kind]) + struct.pack("<I", len(payload)) + payload); sys.stdout.buffer.flush()
mode = sys.argv[1]
if mode == "error":
    frame(2, json.dumps({"event": "error", "error": "no input device"}).encode()); sys.stdin.readline(); sys.exit(0)
if mode == "silent":
    frame(2, json.dumps({"event": "started", "device": "Quiet mic"}).encode()); sys.stdin.readline(); sys.exit(0)
frame(2, json.dumps({"event": "started", "device": "Test mic", "rate": 16000, "chunk": 4}).encode())
for i in range(int(sys.argv[2])):
    frame(1, struct.pack("<4h", i, i, i, i))
if mode == "burst_then_end":
    sys.exit(0)
sys.stdin.readline()
'''


@pytest.fixture
def script(tmp_path):
    p = tmp_path / 'fake_capture.py'
    p.write_text(FAKE)
    return p


def _mic(script, mode, n=3, **kw):
    return native_audio.MicStream(16000, 4, cmd=[sys.executable, str(script), mode, str(n)], **kw)


def test_chunks_arrive_in_order_with_their_bytes(script):
    mic = _mic(script, 'ok', 3)
    try:
        assert mic.device == 'Test mic'
        got = [struct.unpack('<4h', mic.read(4)) for _ in range(3)]
        assert got == [(0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2)]
    finally:
        mic.close()


def test_a_silent_microphone_raises_oserror_so_the_engine_reopens_it(script):
    mic = _mic(script, 'silent', read_timeout=0.3)
    try:
        with pytest.raises(OSError, match='no audio'):
            mic.read(4)
    finally:
        mic.close()


def test_the_end_of_the_program_is_reported_after_the_buffered_chunks_are_read(script):
    mic = _mic(script, 'burst_then_end', 2, read_timeout=0.5)
    try:
        assert len([mic.read(4), mic.read(4)]) == 2
        with pytest.raises(OSError, match='closed'):
            mic.read(4)
    finally:
        mic.close()


def test_a_device_that_cannot_be_opened_fails_at_once(script):
    with pytest.raises(OSError, match='no input device'):
        _mic(script, 'error', startup_timeout=3)


def test_close_ends_the_program(script):
    mic = _mic(script, 'ok', 1)
    mic.close()
    assert mic._proc.poll() is not None
    with pytest.raises(OSError):
        mic.read(4)


def test_open_mic_needs_the_sidecar(monkeypatch):
    monkeypatch.setattr(native, 'sidecar_path', lambda name: None)
    with pytest.raises(native.NativeUnavailable):
        native_audio.open_mic(16000, 512)


def test_open_input_uses_the_saved_name_unless_the_default_is_forced(monkeypatch):
    opened = []
    monkeypatch.setattr(native_audio, 'open_mic', lambda rate, chunk, name=None: opened.append((rate, chunk, name)) or 'stream')
    monkeypatch.setattr(audio_utils, '_load_audio_settings', lambda: {'audio_input_device_name': 'Mic X'})
    assert audio_utils.open_input(16000, 512) == 'stream'
    audio_utils.open_input(16000, 512, force_default=True)
    audio_utils.open_input(16000, 512, device_name='Other')
    assert opened == [(16000, 512, 'Mic X'), (16000, 512, None), (16000, 512, 'Other')]


def test_resilient_open_retries_with_the_system_default(monkeypatch):
    tries = []

    def fake(rate, chunk, device_name=None, force_default=False):
        tries.append(force_default)
        if len(tries) < 3:
            raise OSError('gone')
        return 'ok'
    monkeypatch.setattr(audio_utils, 'open_input', fake)
    monkeypatch.setattr(audio_utils.time, 'sleep', lambda t: None)
    assert audio_utils.open_input_resilient(16000, 512) == 'ok'
    assert tries == [False, True, True]
    monkeypatch.setattr(audio_utils, 'open_input', lambda *a, **k: (_ for _ in ()).throw(OSError('dead')))
    with pytest.raises(OSError, match='dead'):
        audio_utils.open_input_resilient(16000, 512, attempts=2)


def test_no_portaudio_is_left_in_the_main_path():
    import inspect
    import os

    from core.engine import jarvis
    # main.py is read as text: importing it runs bootstrap() (changes the working folder, takes the single-instance mutex, replaces stdout)
    main_src = open(os.path.join(os.path.dirname(__file__), '..', 'main.py'), encoding='utf-8').read()
    for name, src in (('main', main_src), ('jarvis', inspect.getsource(jarvis)), ('audio_utils', inspect.getsource(audio_utils))):
        text = '\n'.join(ln for ln in src.splitlines() if not ln.lstrip().startswith('#'))
        assert 'import pyaudio' not in text and 'PyAudio(' not in text, name
    assert json and struct   # the protocol helpers above are what the real program speaks


def test_closing_twice_is_harmless(script):
    mic = _mic(script, 'ok', 1)
    mic.close()
    mic.close()
