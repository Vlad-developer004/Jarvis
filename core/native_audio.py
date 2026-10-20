"""Client for the jarvis_audio program (native/jarvis_audio).

- `query_output()`, `list_devices()`: one-shot calls; start the program, read one JSON line and let it exit.
- `service()`: a long-lived `--serve` process for volume work (ducking, per-app volume, master volume) and playback (speech and sound
  effects), one JSON line per request. COM lives in that process, so a Core Audio fault cannot take Jarvis down, and when Jarvis exits
  the program gives back every volume it had lowered.
- `open_mic()`: the microphone through `--capture`.

Everything returns None (or raises OSError for the microphone) when the program is missing, slow or answers badly; there is no Python
path behind it, so the callers report the failure (or do nothing, for ducking).
"""
from __future__ import annotations

import atexit
import itertools
import json
import os
import queue
import subprocess  # nosec B404
import sys
import threading

from core import native

_TIMEOUT_SEC = 2.0
_CREATE_NO_WINDOW = 0x08000000


def _run(arg: str) -> dict | None:
    path = native.sidecar_path('audio')
    if path is None:
        return None
    try:
        proc = subprocess.run([path, arg], capture_output=True, text=True, timeout=_TIMEOUT_SEC,   # nosec B603
                              creationflags=_CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None
    return data if isinstance(data, dict) and data.get('ok') is True else None


def query_output() -> dict | None:
    """{'name', 'id', 'form_factor', 'kind', 'is_headphones'} of the default playback device, or None."""
    info = _run('--query-output')
    if info is None or not isinstance(info.get('is_headphones'), bool):
        return None
    return info


def list_devices() -> dict | None:
    """{'inputs': [{'index', 'id', 'name', 'default'}], 'outputs': [...]} or None."""
    return _run('--list-devices')


class Service:
    """A `jarvis_audio --serve` process kept open. `request()` is safe to call from several threads; one at a time talks to the pipe."""

    def __init__(self, cmd: list[str] | None = None):
        self._cmd = cmd
        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._ids = itertools.count(1)

    def _command(self) -> list[str] | None:
        if self._cmd is not None:
            return self._cmd
        path = native.sidecar_path('audio')
        return [path, '--serve'] if path else None

    def _start(self) -> bool:
        cmd = self._command()
        if cmd is None:
            return False
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,   # nosec B603
                                    creationflags=_CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        except OSError:
            return False
        self._proc, self._lines = proc, queue.Queue()
        threading.Thread(target=self._read, args=(proc, self._lines), daemon=True, name='native-audio-reader').start()
        return True

    @staticmethod
    def _read(proc, lines) -> None:
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)   # the process ended

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def request(self, timeout: float = _TIMEOUT_SEC, **req) -> dict | None:
        """Send one request, return the answer dict (check its 'ok'), or None when there is no usable service."""
        with self._lock:
            if not self._alive() and not self._start():
                return None
            rid = next(self._ids)
            try:
                self._proc.stdin.write(json.dumps({**req, 'id': rid}) + '\n')
                self._proc.stdin.flush()
                while True:
                    line = self._lines.get(timeout=timeout)
                    if line is None:
                        raise OSError('sidecar ended')
                    try:
                        ans = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(ans, dict) and ans.get('id') == rid:
                        return ans
            except (OSError, ValueError, queue.Empty):
                self.close()   # a stuck or dead process is dropped; the next request starts a fresh one
                return None

    def close(self) -> None:
        with self._lock:
            proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.stdin.close()   # EOF is the signal to restore volumes and exit
            proc.wait(timeout=2)
        except (OSError, ValueError, subprocess.SubprocessError):
            proc.kill()


_service: Service | None = None
_service_lock = threading.Lock()


def service() -> Service:
    global _service
    with _service_lock:
        if _service is None:
            _service = Service()
            atexit.register(_service.close)
        return _service


def duck(enable: bool) -> bool:
    """Lower (or give back) the other apps' volume through the sidecar. True when the sidecar handled it."""
    ans = service().request(op='duck', enable=enable, skip_pid=os.getpid())
    return bool(ans and ans.get('ok'))


def unduck() -> bool:
    ans = service().request(op='unduck')
    return bool(ans and ans.get('ok'))


# ── playback (TTS speech and sound effects) ───────────────────────────────

_PLAY_TIMEOUT_SEC = 5.0   # decoding a long clip can take a moment


def play(path: str, volume: float = 1.0, channel: str = 'tts') -> float | None:
    """Queue an audio file (WAV, MP3, Ogg) for playback; 'tts' clips play one after another without a gap, 'sfx' clips mix over them.
    Returns the clip length in seconds, or None when the service refused or is not there."""
    ans = service().request(timeout=_PLAY_TIMEOUT_SEC, op='play', path=path, volume=volume, channel=channel)
    return float(ans['seconds']) if ans and ans.get('ok') else None


def play_pcm(pcm: bytes, rate: int, channels: int, volume: float = 1.0, channel: str = 'sfx') -> float | None:
    """Same for raw little-endian 16-bit PCM (synthesised sounds)."""
    import base64
    ans = service().request(timeout=_PLAY_TIMEOUT_SEC, op='play_pcm', data=base64.b64encode(pcm).decode('ascii'),
                            rate=rate, channels=channels, volume=volume, channel=channel)
    return float(ans['seconds']) if ans and ans.get('ok') else None


def stop(channel: str = 'all') -> bool:
    """Cut off what is playing and queued ('tts', 'sfx' or 'all')."""
    ans = service().request(op='stop', channel=channel)
    return bool(ans and ans.get('ok'))


def player_status() -> dict | None:
    """{'busy', 'queued', 'remaining', 'ready', 'device', 'rebuilds', ...} or None when the service is not there."""
    ans = service().request(op='player_status')
    return ans if ans and ans.get('ok') else None


def is_busy() -> bool:
    st = player_status()
    return bool(st and st['busy'])


def wait_idle(timeout: float = 90.0, poll: float = 0.05) -> None:
    """Block until nothing is playing (or the service is gone, or `timeout` passes)."""
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if not is_busy():
            return
        time.sleep(poll)


def ensure_ready(timeout: float = 5.0) -> bool:
    """Start the service if needed and wait until its output stream is open."""
    import time
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        st = player_status()
        if st is None:
            return False
        if st['ready']:
            return True
        time.sleep(0.05)
    return False


# ── microphone capture ───────────────────────────────────────────────────

class MicStream:
    """The microphone as mono 16-bit PCM from `jarvis_audio --capture`, with the two calls the engine uses on an audio stream: read()
    and close(). Chunks arrive in a queue filled by a reader thread; when nothing arrives for `read_timeout` seconds read() raises
    OSError, which the engine treats as a lost device and re-opens."""

    def __init__(self, rate: int, chunk_frames: int, device_name: str | None = None, startup_timeout: float = 5.0, cmd: list[str] | None = None,
                 read_timeout: float = 2.0):
        import collections
        self.rate, self.chunk_frames, self.read_timeout = rate, chunk_frames, read_timeout
        self.device = ''
        self.events: list[dict] = []
        self._chunks: collections.deque = collections.deque(maxlen=64)
        self._cond = threading.Condition()
        self._started = threading.Event()
        self._error = ''
        self._closed = False
        self._user_closed = False
        if cmd is None:
            cmd = [native.require_sidecar('audio'), '--capture', '--rate', str(rate), '--chunk', str(chunk_frames)]
            if device_name:
                cmd += ['--device', device_name]
        self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,   # nosec B603
                                      creationflags=_CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        threading.Thread(target=self._read_frames, daemon=True, name='native-mic-reader').start()
        if not self._started.wait(startup_timeout) or (self._error and not self.device):
            err = self._error or 'no answer from the capture program'
            self.close()
            raise OSError(f'microphone cannot be opened: {err}')

    def _read_frames(self) -> None:
        out = self._proc.stdout
        try:
            while True:
                head = out.read(5)
                if len(head) < 5:
                    break
                kind, size = head[0], int.from_bytes(head[1:5], 'little')
                body = out.read(size)
                if len(body) < size:
                    break
                if kind == 1:
                    with self._cond:
                        self._chunks.append(body)   # a full deque drops the oldest: a stalled reader loses old audio, not memory
                        self._cond.notify()
                elif kind == 2:
                    try:
                        ev = json.loads(body)
                    except ValueError:
                        continue
                    self.events.append(ev)
                    if ev.get('event') == 'started':
                        self.device = ev.get('device', '')
                        self._started.set()
                    elif ev.get('event') == 'error':
                        self._error = ev.get('error', '')
                        # a device that cannot be opened is reported at once instead of after the whole startup timeout
                        if not self._started.is_set():
                            self._started.set()
        finally:
            with self._cond:
                self._closed = True
                self._cond.notify_all()

    def read(self, frames: int | None = None, exception_on_overflow: bool = False) -> bytes:
        """One chunk (`chunk_frames` samples as bytes). Raises OSError when the stream is closed or silent for too long."""
        if self._user_closed:
            raise OSError('microphone stream closed')
        with self._cond:
            if not self._chunks and not self._closed:
                self._cond.wait(self.read_timeout)
            if self._chunks:
                return self._chunks.popleft()
            raise OSError('microphone stream closed' if self._closed else 'no audio from the microphone')

    def close(self) -> None:
        self._closed = self._user_closed = True
        proc = self._proc
        try:
            proc.stdin.write(b'stop\n')
            proc.stdin.flush()
            proc.stdin.close()
        except (OSError, ValueError):   # the pipe is already gone, or close() ran before
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.SubprocessError:
            proc.kill()
        with self._cond:
            self._cond.notify_all()


def open_mic(rate: int, chunk_frames: int, device_name: str | None = None) -> MicStream:
    """Start capturing; raises OSError when the microphone cannot be opened, native.NativeUnavailable when the program is missing."""
    return MicStream(rate, chunk_frames, device_name)
