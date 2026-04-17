from __future__ import annotations
import os
import threading
import time
from pathlib import Path
_LOCK = threading.Lock()
_PATH = Path('logs') / 'voice_engine.log'
_LAST_HB = 0.0
_HB_INTERVAL_SEC = 2.5
_MAX_FILE_BYTES = 1_500_000
def _enabled() -> bool:
    v = os.environ.get('JARVIS_VOICE_DEBUG', '1').strip().lower()
    return v not in ('0', 'false', 'no', 'off')
def _write_line(msg: str) -> None:
    if not _enabled():
        return
    ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    line = f'{ts} {msg}\n'
    # Only log if it's an error or critical msg
    msg_low = msg.lower()
    is_crit = 'error' in msg_low or 'fail' in msg_low or 'crit' in msg_low or 'exception' in msg_low
    if not is_crit:
        return
    with _LOCK:
        try:
            _PATH.parent.mkdir(parents=True, exist_ok=True)
            if _PATH.exists() and _PATH.stat().st_size > _MAX_FILE_BYTES:
                _PATH.unlink(missing_ok=True)
            with open(_PATH, 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass
def voice_event(msg: str) -> None:
    _write_line(msg)
def voice_heartbeat(
    *,
    rms: float,
    voice_on: int,
    voice_off: int,
    energy: int,
    game: bool,
    jarvis_on: bool,
    speaking: bool,
    tts: bool,
    gain: float,
) -> None:
    if not _enabled():
        return
    global _LAST_HB
    now = time.time()
    if now - _LAST_HB < _HB_INTERVAL_SEC:
        return
    _LAST_HB = now
    _write_line(
        f'HB rms={rms:.0f} v_on={voice_on} v_off={voice_off} et={energy} '
        f'game={int(game)} jarvis={int(jarvis_on)} speak={int(speaking)} tts={int(tts)} gain={gain:.2f}'
    )
def voice_session_banner(stt_engine: str, rate: int, chunk: int) -> None:
    _write_line(f'=== session stt={stt_engine!r} rate={rate} chunk={chunk} (JARVIS_VOICE_DEBUG=0 to disable) ===')
