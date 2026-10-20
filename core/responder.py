import time

from core import native_audio

# Voice replies were always boosted by 30% (and clipped) on top of the recorded level.
_GAIN = 1.3


class Responder:
    """A recorded reply ("Да, сэр"): played through the native audio player as an effect, so it mixes over any speech instead of queueing."""

    def __init__(self, wav_path: str):
        self._path = wav_path

    def play(self):
        """Blocks until the reply has finished, as the earlier PyAudio version did."""
        seconds = native_audio.play(self._path, _GAIN, 'sfx')
        if seconds is not None:
            time.sleep(seconds + 0.2)

    def close(self):
        self._path = None
