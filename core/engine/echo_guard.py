"""Tells the audio loop when the microphone may still hear Jarvis's own voice.

is_tts_audio_playing is a thin wrapper around the mixer's busy check, which can read False for a moment between two chunks of a
multi-sentence reply, or before the room echo has died out. On a speaker-only setup (no AEC) that gap was enough for the mic to pick up
Jarvis's own words as a new utterance, which fed a second concurrent call into the local model (see core/speech/llm_chat.py's
_infer_lock). The guard keeps "TTS is playing" true for a short tail after the mixer goes quiet.
"""
import time

ECHO_TAIL_SEC = 0.6


class EchoGuard:
    def __init__(self, tail_sec: float = ECHO_TAIL_SEC):
        self.tail_sec = tail_sec
        self._last_active_ts = 0.0

    def update(self, playing: bool, now: float | None = None) -> bool:
        """Feeds the current mixer state; returns True while the mic should be treated as covered by TTS (playing, or within the tail)."""
        if now is None:
            now = time.time()
        if playing:
            self._last_active_ts = now
            return True
        return now - self._last_active_ts < self.tail_sec
