"""Rolling buffer of the most recent raw mic audio, fed continuously by
core/engine/jarvis.py's always-open input stream.

Exists so actions/song_id.py can grab "the last few seconds of mic audio"
without opening a second PyAudio stream on the same input device — testing
showed that a second concurrent open on Windows (PortAudio/WASAPI) doesn't
reliably error, it can silently hand back near-silence (observed: peak
amplitude 2/32767 while music was audibly playing next to the mic), because
the engine's own stream already holds the device. Reading from this shared
buffer instead means song recognition always gets the exact same live audio
the rest of the app is already successfully listening to.
"""
import threading
from collections import deque

_lock = threading.Lock()
_buffer: deque[bytes] = deque()
_buffer_bytes = 0
_rate = 16000
_MAX_SECONDS = 20


def configure(rate: int) -> None:
    global _rate
    with _lock:
        _rate = rate


def push(chunk: bytes) -> None:
    global _buffer_bytes
    if not chunk:
        return
    with _lock:
        _buffer.append(chunk)
        _buffer_bytes += len(chunk)
        max_bytes = _rate * 2 * _MAX_SECONDS  # 16-bit mono
        while _buffer_bytes > max_bytes and len(_buffer) > 1:
            _buffer_bytes -= len(_buffer.popleft())


def read_last_seconds(seconds: float) -> tuple[bytes, int]:
    """Returns (raw_pcm16_mono_bytes, rate). May return fewer than
    `seconds` worth of audio if the buffer hasn't filled that much yet."""
    with _lock:
        rate = _rate
        data = b''.join(_buffer)
    need_bytes = int(rate * 2 * seconds)
    return data[-need_bytes:], rate
