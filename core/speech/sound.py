import os
import time
import threading
import numpy as np
import pygame

_cached_sounds = {}
_lock = threading.Lock()


def _sounds_dir() -> str:
    from config_pack.config import get_project_root
    return os.path.join(get_project_root(), 'audio', 'sfx')


def _load_sound_file(sound_type: str) -> "pygame.mixer.Sound | None":
    for ext in ('.wav', '.mp3', '.ogg'):
        path = os.path.join(_sounds_dir(), sound_type + ext)
        if os.path.isfile(path):
            try:
                return pygame.mixer.Sound(path)
            except Exception:
                return None
    return None

def _add_trill_pulse(t, wave, sample_rate, t_start, duration, f_start, f_end, vol=0.3):
    t_end = t_start + duration
    mask = (t >= t_start) & (t <= t_end)
    if not np.any(mask):
        return
    t_pulse = t[mask] - t_start
    phase = 2 * np.pi * (f_start * t_pulse + 0.5 * (f_end - f_start) / duration * t_pulse * t_pulse)
    pulse_wave = np.sin(phase)
    env = np.sin(np.pi * t_pulse / duration) ** 2
    wave[mask] += pulse_wave * env * vol

def _synthesize_sound(sound_type: str, sample_rate: int = 44100) -> pygame.mixer.Sound:
    if sound_type == 'milestone':
        # Quick 2-step mini trill (high-tech feedback click)
        duration = 0.15
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.zeros_like(t)
        _add_trill_pulse(t, wave, sample_rate, 0.00, 0.04, 1200, 1800, 0.4)
        _add_trill_pulse(t, wave, sample_rate, 0.03, 0.08, 1800, 2600, 0.5)
    elif sound_type == 'red_alert':
        # Sweep/Klaxon warning sound (futuristic emergency alarm)
        duration = 1.3
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.zeros_like(t)
        # 3 cycles of a sweep from 450Hz to 850Hz with brief gap
        cycle = 0.4
        for i in range(3):
            t_start = i * cycle
            _add_trill_pulse(t, wave, sample_rate, t_start, 0.35, 450, 850, 0.6)
    elif sound_type in ('reminder', 'alarm'):
        # Ascending cybernetic trill (futuristic HUD notification)
        duration = 0.45
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.zeros_like(t)
        _add_trill_pulse(t, wave, sample_rate, 0.00, 0.04, 600, 900, 0.3)
        _add_trill_pulse(t, wave, sample_rate, 0.03, 0.04, 900, 1300, 0.35)
        _add_trill_pulse(t, wave, sample_rate, 0.06, 0.04, 1300, 1800, 0.4)
        _add_trill_pulse(t, wave, sample_rate, 0.09, 0.04, 1800, 2400, 0.45)
        _add_trill_pulse(t, wave, sample_rate, 0.12, 0.18, 2400, 3000, 0.55)
    else:
        duration = 0.25
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        env = np.exp(-15 * t)
        wave = np.sin(2 * np.pi * 1000.00 * t) * env * 0.5

    # Normalize to prevent clipping
    max_val = np.max(np.abs(wave))
    if max_val > 1e-4:
        wave = wave / max_val * 0.55

    # Convert to 16-bit stereo Sound
    audio_data = (wave * 32767).astype(np.int16)
    audio_stereo = audio_data.reshape(-1, 1).repeat(2, axis=1)
    return pygame.sndarray.make_sound(audio_stereo)

def _get_sound(sound_type: str) -> pygame.mixer.Sound:
    with _lock:
        if sound_type not in _cached_sounds:
            sound = _load_sound_file(sound_type)
            if sound is None:
                mix_init = pygame.mixer.get_init()
                sr = mix_init[0] if mix_init else 44100
                sound = _synthesize_sound(sound_type, sample_rate=sr)
            _cached_sounds[sound_type] = sound
        return _cached_sounds[sound_type]

def play_alert_sound(sound_type: str = 'reminder') -> None:
    """Plays a premium synthesized UI alert sound."""
    try:
        from core.speech.tts import ensure_mixer_init
        ensure_mixer_init()
    except Exception:
        pass

    try:
        if not pygame.mixer.get_init():
            raise RuntimeError("Mixer not initialized")
        
        if sound_type == 'red_alert':
            # Play the sweeping klaxon alarm
            def _play_seq():
                try:
                    sound = _get_sound('red_alert')
                    sound.play()
                except Exception:
                    pass
            threading.Thread(target=_play_seq, daemon=True).start()
        else:
            sound = _get_sound(sound_type)
            sound.play()
    except Exception:
        # Fallback to winsound
        def _fallback():
            try:
                import winsound
                if sound_type == 'alarm':
                    # Gentle descending/ascending melody fallback
                    for freq in (784, 880, 1047):
                        winsound.Beep(freq, 120)
                        time.sleep(0.05)
                elif sound_type == 'red_alert':
                    # Repeat hazard klaxon Beeps
                    for _ in range(3):
                        winsound.Beep(580, 250)
                        time.sleep(0.1)
                elif sound_type == 'milestone':
                    winsound.Beep(1500, 80)
                else:
                    winsound.Beep(1200, 150)
            except Exception:
                pass
        threading.Thread(target=_fallback, daemon=True).start()

