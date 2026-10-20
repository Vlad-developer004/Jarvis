import os
import threading
import numpy as np

from core import native_audio

# Synthesised sounds are built once and kept as raw 16-bit stereo PCM; files from audio/sfx are sent by path.
_cached_pcm: dict[str, tuple[bytes, int]] = {}
_lock = threading.Lock()
_RATE = 44100


def _sounds_dir() -> str:
    from config_pack.config import get_project_root
    return os.path.join(get_project_root(), 'audio', 'sfx')


def _sound_file(sound_type: str) -> str | None:
    for ext in ('.wav', '.mp3', '.ogg'):
        path = os.path.join(_sounds_dir(), sound_type + ext)
        if os.path.isfile(path):
            return path
    return None

# Bell partials: (ratio, weight, decay multiplier). The inharmonic 2.76 gives the "glass" tone, higher ones die out faster.
_BELL = ((1.0, 1.0, 1.0), (2.0, 0.35, 1.6), (2.76, 0.16, 2.2), (5.4, 0.05, 3.5))


def _add_bell(t, wave, t_start, freq, dur, vol=0.5):
    """A struck-bell note: instant attack, exponential decay over ~dur seconds."""
    mask = t >= t_start
    if not np.any(mask):
        return
    tt = t[mask] - t_start
    k = 6.0 / dur
    note = np.zeros_like(tt)
    for ratio, weight, decay in _BELL:
        note += weight * np.sin(2 * np.pi * freq * ratio * tt) * np.exp(-tt * k * decay)
    wave[mask] += note * np.minimum(1.0, tt * 800) * vol


def _add_tone(t, wave, t_start, duration, freq, vol=0.5):
    """A soft held tone (sine with a little third harmonic) with a short fade in and out."""
    mask = (t >= t_start) & (t < t_start + duration)
    if not np.any(mask):
        return
    tt = t[mask] - t_start
    env = np.minimum(1.0, np.minimum(tt / 0.02, (duration - tt) / 0.05))
    wave[mask] += (np.sin(2 * np.pi * freq * tt) + 0.25 * np.sin(2 * np.pi * freq * 3 * tt)) * env * vol


def _synthesize_sound(sound_type: str, sample_rate: int = _RATE) -> bytes:
    """Raw little-endian 16-bit stereo PCM of a UI sound."""
    def canvas(duration):
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        return t, np.zeros_like(t)

    if sound_type == 'milestone':
        # two quick glassy pings, rising
        t, wave = canvas(0.45)
        _add_bell(t, wave, 0.00, 1318.5, 0.25, 0.5)
        _add_bell(t, wave, 0.09, 1760.0, 0.3, 0.5)
    elif sound_type == 'red_alert':
        # two-tone siren (high, low) x3: urgent but not shrill
        t, wave = canvas(1.75)
        for i in range(3):
            _add_tone(t, wave, i * 0.56, 0.28, 784.0, 0.5)
            _add_tone(t, wave, i * 0.56 + 0.28, 0.28, 587.3, 0.5)
    elif sound_type == 'alarm':
        # alarm-clock rhythm: three bursts of three pings
        t, wave = canvas(2.7)
        for burst in range(3):
            for k in range(3):
                _add_bell(t, wave, burst * 0.8 + k * 0.15, 1046.5, 0.28, 0.5)
    elif sound_type == 'reminder':
        # calm descending ding-dong
        t, wave = canvas(1.5)
        _add_bell(t, wave, 0.00, 880.0, 0.9, 0.55)
        _add_bell(t, wave, 0.24, 659.3, 1.1, 0.55)
    else:
        t, wave = canvas(0.6)
        _add_bell(t, wave, 0.0, 880.0, 0.45, 0.55)

    # Normalize to prevent clipping
    max_val = np.max(np.abs(wave))
    if max_val > 1e-4:
        wave = wave / max_val * 0.55

    # Convert to 16-bit stereo
    fade = min(len(wave), int(sample_rate * 0.01))
    if fade:
        wave[-fade:] *= np.linspace(1.0, 0.0, fade)
    audio_data = (wave * 32767).astype('<i2')
    return audio_data.reshape(-1, 1).repeat(2, axis=1).tobytes()

def _pcm(sound_type: str) -> bytes:
    with _lock:
        if sound_type not in _cached_pcm:
            _cached_pcm[sound_type] = (_synthesize_sound(sound_type), _RATE)
        return _cached_pcm[sound_type][0]

def play_alert_sound(sound_type: str = 'reminder') -> None:
    """Plays a UI alert sound (a file from audio/sfx when there is one, a synthesised one otherwise) through the native player."""
    def _play():
        path = _sound_file(sound_type)
        if path is not None and native_audio.play(path, 1.0, 'sfx') is not None:
            return
        native_audio.play_pcm(_pcm(sound_type), _RATE, 2, 1.0, 'sfx')

    # synthesising (red_alert is 1.3 s of numpy work) and the request itself stay off the caller's thread
    threading.Thread(target=_play, daemon=True, name='alert-sound').start()
