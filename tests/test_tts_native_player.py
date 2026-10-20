"""The TTS worker plays through the native audio player: clips go out in order with the computed volume, other apps are ducked for the
duration and given back when it ends, and stop() cuts the player off. The player itself is replaced by a recorder here."""
import os
import struct
import time
import wave

import pytest

from core import native_audio
from core.speech import tts


def _wav(path, ms=50, rate=8000):
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack('<h', 1000) * (rate * ms // 1000))
    return str(path)


class _Player:
    def __init__(self):
        self.calls, self.busy_until, self.stopped = [], 0.0, []

    def play(self, path, volume=1.0, channel='tts'):
        self.calls.append((os.path.basename(path), round(volume, 3), channel))
        self.busy_until = time.monotonic() + 0.15
        return 0.05

    def is_busy(self):
        return time.monotonic() < self.busy_until

    def stop(self, channel='all'):
        self.stopped.append(channel)
        self.busy_until = 0.0
        return True


@pytest.fixture
def manager(monkeypatch):
    player = _Player()
    events = []
    monkeypatch.setattr(native_audio, 'play', player.play)
    monkeypatch.setattr(native_audio, 'is_busy', player.is_busy)
    monkeypatch.setattr(native_audio, 'stop', player.stop)
    import actions.volume as volume
    monkeypatch.setattr(volume, 'duck_volume', lambda enable: events.append(('duck', enable)))
    monkeypatch.setattr(volume, 'force_unduck', lambda: events.append(('unduck',)))
    monkeypatch.setattr(tts.TTSManager, '_safe_hud_set_mode', lambda self, mode: events.append(('hud', mode)), raising=False)
    monkeypatch.setattr(tts, '_get_night_vol_settings', lambda: (False, 22, 0, 7, 0, 0.5))
    monkeypatch.setattr(tts, '_MASTER_VOLUME', 0.8)
    monkeypatch.setattr(tts.TTSManager, '_instance', None)
    mgr = tts.TTSManager()
    yield mgr, player, events
    mgr.queue.put((-1, time.time(), None))   # ends the worker thread
    mgr.worker_thread.join(timeout=3)


def _wait(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_clips_are_played_in_order_at_the_master_volume_and_the_session_is_ducked_once(manager, tmp_path):
    mgr, player, events = manager
    a, b = _wav(tmp_path / 'silero_a.wav'), _wav(tmp_path / 'silero_b.wav')
    mgr.queue.put((10, 1.0, a))
    mgr.queue.put((10, 2.0, b))
    assert _wait(lambda: len(player.calls) == 2)
    assert player.calls == [('silero_a.wav', 0.8, 'tts'), ('silero_b.wav', 0.8, 'tts')]
    assert events.count(('duck', True)) == 1                      # one duck for the whole run of clips
    assert _wait(lambda: ('unduck',) in events)                   # and it is given back once the player has run dry
    assert ('hud', 'speaking') in events and ('hud', 'idle') in events


def test_a_temporary_file_is_removed_after_the_player_took_it(manager, tmp_path):
    mgr, player, _ = manager
    tmp = _wav(tmp_path / 'silero_tmp_x.wav')
    mgr.queue.put((10, 1.0, tmp))
    assert _wait(lambda: len(player.calls) == 1)
    assert _wait(lambda: not os.path.exists(tmp))


def test_night_volume_is_applied(manager, tmp_path, monkeypatch):
    mgr, player, _ = manager
    monkeypatch.setattr(tts, '_get_night_vol_settings', lambda: (True, 0, 0, 23, 59, 0.5))   # night all day
    mgr.queue.put((10, 1.0, _wav(tmp_path / 'silero_n.wav')))
    assert _wait(lambda: len(player.calls) == 1)
    assert player.calls[0][1] == pytest.approx(0.4)


def test_a_refused_clip_does_not_wedge_the_worker(manager, tmp_path, monkeypatch):
    mgr, player, events = manager
    monkeypatch.setattr(native_audio, 'play', lambda *a, **k: None)   # the service is gone
    mgr.queue.put((10, 1.0, _wav(tmp_path / 'silero_a.wav')))
    assert _wait(lambda: mgr.queue.empty() and not mgr.active_playback)
    monkeypatch.setattr(native_audio, 'play', player.play)
    mgr.queue.put((10, 2.0, _wav(tmp_path / 'silero_b.wav')))
    assert _wait(lambda: len(player.calls) == 1)


def test_stop_cuts_the_player_and_asks_for_an_unduck(manager):
    mgr, player, events = manager
    mgr.stop()
    assert player.stopped == ['tts']
    assert _wait(lambda: ('unduck',) in events)


def test_is_speaking_follows_the_player(manager, tmp_path):
    mgr, player, _ = manager
    assert tts.is_speaking() is False
    mgr.queue.put((10, 1.0, _wav(tmp_path / 'silero_a.wav')))
    assert _wait(lambda: len(player.calls) == 1)
    assert tts.is_speaking() is True
    assert _wait(lambda: not tts.is_speaking())


def test_the_tts_module_no_longer_depends_on_pygame_or_com():
    import inspect
    src = inspect.getsource(tts)
    assert 'pygame' not in src and 'pythoncom' not in src
