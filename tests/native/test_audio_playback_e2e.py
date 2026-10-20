"""Real playback through the native player, recorded back from the output device (WASAPI loopback) by a second sidecar process.

Opt-in because it makes a quiet tone for a few seconds: set JARVIS_AUDIO_TESTS=1. Skipped without a built sidecar or an output device.
"""
import json
import math
import os
import struct
import subprocess
import time
import wave

import pytest

from core import native, native_audio

pytestmark = [
    pytest.mark.skipif(native.sidecar_path('audio') is None, reason='jarvis_audio.exe is not built'),
    pytest.mark.skipif(os.environ.get('JARVIS_AUDIO_TESTS') != '1', reason='set JARVIS_AUDIO_TESTS=1 to play real (quiet) test tones'),
    pytest.mark.timeout(60),
]


def _tone(path, ms, hz=440.0, rate=24000, amp=0.25):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h', int(math.sin(i * hz * 2 * math.pi / rate) * amp * 32767)) for i in range(rate * ms // 1000)))
    return str(path)


def _listen(record_ms):
    return subprocess.Popen([native.sidecar_path('audio'), '--analyse-loopback', str(record_ms)], stdout=subprocess.PIPE, text=True)   # nosec B603


@pytest.fixture
def player():
    assert native_audio.ensure_ready(10), 'the native player did not open an output stream'
    yield native_audio
    native_audio.stop()
    native_audio.service().close()


def _result(rec):
    return json.loads(rec.communicate(timeout=30)[0])


def test_a_clip_arrives_whole_at_the_right_pitch(player, tmp_path):
    rec = _listen(4000)
    time.sleep(0.8)
    seconds = player.play(_tone(tmp_path / 'one.wav', 1200), 1.0)
    assert seconds == pytest.approx(1.2, abs=0.01)
    player.wait_idle(10)
    r = _result(rec)
    assert r['ok'], r
    assert abs(r['span_ms'] - 1200) <= 60 and r['dropouts'] == 0 and r['glitches'] == 0 and abs(r['freq_hz'] - 440) < 3


def test_queued_clips_play_back_to_back_without_a_gap(player, tmp_path):
    rec = _listen(5500)
    time.sleep(0.8)
    for i in range(3):
        assert player.play(_tone(tmp_path / f'q{i}.wav', 1000), 1.0) is not None
    assert player.player_status()['queued'] >= 1
    player.wait_idle(10)
    r = _result(rec)
    assert r['ok'], r
    assert abs(r['span_ms'] - 3000) <= 100 and r['dropouts'] == 0 and r['glitches'] == 0


def test_stop_cuts_the_speech_short_and_leaves_the_player_idle(player, tmp_path):
    rec = _listen(4000)
    time.sleep(0.8)
    player.play(_tone(tmp_path / 'long.wav', 3000), 1.0)
    time.sleep(0.6)
    assert player.is_busy() and player.stop('tts') and not player.is_busy()
    r = _result(rec)
    assert r['ok'] and r['span_ms'] < 1500


def test_an_effect_mixes_over_speech_instead_of_waiting(player, tmp_path):
    player.play(_tone(tmp_path / 'speech.wav', 1500, hz=440), 0.5, 'tts')
    time.sleep(0.2)
    assert player.play(_tone(tmp_path / 'fx.wav', 300, hz=880), 0.5, 'sfx') is not None
    st = player.player_status()
    assert st['busy']
    player.wait_idle(10)
    assert not player.is_busy()


def test_the_shipped_effect_sounds_play(player):
    sfx = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'audio', 'sfx', 'milestone.mp3')
    if not os.path.isfile(sfx):
        pytest.skip('no audio/sfx in this checkout')
    assert player.play(sfx, 0.3, 'sfx') > 0.05
    player.wait_idle(10)
