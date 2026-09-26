import json
import time
import os
import numpy as np
from pathlib import Path
from config_pack.config import get_data_path

_PROFILE_PATH = Path(get_data_path('mic_profile.json'))
_REQUIRED_SAMPLES = 5
_LISTEN_WINDOW_SEC = 4.0
_MIN_THRESH = 50
_CANDIDATE_RATES = [16000, 8000, 22050, 44100, 48000]
def load_profile() -> dict:
    try:
        return json.loads(_PROFILE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}
def save_profile(threshold: int, gain: float, noise_floor: float = 0.0,
                 sample_rate: int = 16000) -> None:
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _PROFILE_PATH.write_text(
        json.dumps({
            'calibrated': True,
            'threshold': threshold,
            'gain': gain,
            'noise_floor': round(noise_floor, 2),
            'sample_rate': sample_rate,
        }, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
def _wait_tts_done(extra_sec: float = 0.35) -> None:
    try:
        from core.speech.tts import TTSManager
        TTSManager().wait_until_finished(timeout=15.0)
        time.sleep(extra_sec)
    except Exception:
        time.sleep(2.5)
def find_best_rate(pa_instance, chunk_ms: int = 32, device_index=None) -> int:
    from core.audio_utils import rms_int16
    results: dict[int, float] = {}
    for rate in _CANDIDATE_RATES:
        try:
            chunk = max(128, int(rate * chunk_ms / 1000))
            kw: dict = dict(format=8, channels=1, rate=rate, input=True,
                            frames_per_buffer=chunk)
            if device_index is not None:
                kw['input_device_index'] = device_index
            s = pa_instance.open(**kw)
            vals: list[float] = []
            n_frames = max(4, int(0.5 * 1000 / chunk_ms))
            for _ in range(n_frames):
                try:
                    d = s.read(chunk, exception_on_overflow=False)
                    vals.append(rms_int16(d))
                except Exception:
                    pass
            try:
                s.close()
            except Exception:
                pass
            if vals:
                results[rate] = float(np.percentile(vals, 70))
        except Exception:
            pass
    if not results:
        return 16000
    best = min(results, key=results.get)
    if 16000 in results and results[16000] <= results[best] * 1.20:
        return 16000
    return best
def run_calibration(stream, chunk: int, rate: int, chunk_ms: int) -> tuple[int, float]:
    from core.audio_utils import rms_int16
    from config_pack.config import MIN_THRESH, MIC_GAIN
    def _speak(text: str):
        try:
            from core.speech import speak
            speak(text)
        except Exception:
            pass
    def _wait():
        _wait_tts_done(extra_sec=0.4)
    def _beep():
        # An explicit "go" cue instead of relying on the user's own sense of
        # when the spoken prompt has fully ended — people naturally start
        # talking the instant they've heard enough of the phrase to know
        # what's being asked, which is *before* TTS playback (and the
        # measurement window that follows it) actually finishes, clipping
        # the start of what gets recorded.
        try:
            import winsound
            winsound.Beep(950, 150)
        except Exception:
            pass
        time.sleep(0.15)  # let the beep's tail clear the mic before measuring
    import random as _rnd
    _ok_phrases = [
        'Принято!',
        'Отлично, слышу вас хорошо.',
        'Записал.',
        'Хорошо, вас слышно чётко.',
    ]
    _retry_phrases = [
        'Не расслышал — попробуйте ещё раз, чуть громче.',
        'Почти! Говорите чуть ближе к микрофону.',
        'Не уловил — повторите, пожалуйста.',
        'Слабый сигнал — скажите погромче.',
    ]
    def _capture_peak(prompt: str, min_rms: float,
                      max_attempts: int = 5) -> float | None:
        for attempt in range(1, max_attempts + 1):
            _speak(prompt if attempt == 1 else f'Попытка {attempt}.')
            _wait()
            _beep()
            frames_needed = int(_LISTEN_WINDOW_SEC / (chunk_ms / 1000.0))
            rms_vals: list[float] = []
            for _ in range(frames_needed):
                try:
                    data = stream.read(chunk, exception_on_overflow=False)
                    rms_vals.append(rms_int16(data))
                except Exception:
                    pass
            if rms_vals:
                rms_arr = np.array(rms_vals)
                peak_rms = float(np.percentile(rms_arr, 85))
            else:
                peak_rms = 0.0
            if peak_rms > min_rms:
                _speak(_rnd.choice(_ok_phrases))
                _wait()
                return peak_rms
            _speak(_rnd.choice(_retry_phrases))
            _wait()
        return None
    _speak('Запускаю калибровку микрофона. Пожалуйста, помолчите несколько секунд — измеряю фоновый шум.')
    _wait()
    noise_frames = int(3.0 / (chunk_ms / 1000.0))
    noise_vals: list[float] = []
    for _ in range(noise_frames):
        try:
            data = stream.read(chunk, exception_on_overflow=False)
            noise_vals.append(rms_int16(data))
        except Exception:
            pass
    if noise_vals:
        noise_arr = np.array(noise_vals)
        noise_floor = float(np.percentile(noise_arr, 75))
    else:
        noise_floor = float(MIN_THRESH)
    speech_min = max(float(MIN_THRESH), noise_floor * 2.5)
    _speak('Отлично. Сейчас три раза прозвучит сигнал — после каждого сигнала скажите вслух «проверка микрофона», уверенно, в полный голос.')
    _wait()
    _loud_labels = ['Приготовьтесь — первый раз.', 'Второй раз.', 'И третий раз.']
    loud_peaks: list[float] = []
    for i in range(3):
        peak = _capture_peak(_loud_labels[i], speech_min)
        if peak is None:
            _speak('Не смог зафиксировать голос. Проверьте, что микрофон подключён и не заглушён. Использую стандартные настройки.')
            _wait()
            save_profile(int(speech_min * 2), MIC_GAIN,
                         noise_floor=noise_floor, sample_rate=rate)
            return (int(speech_min * 2), MIC_GAIN)
        loud_peaks.append(peak)
    _speak('Хорошо, почти готово. После сигнала скажите то же самое вполголоса или чуть отодвинувшись от микрофона — два раза.')
    _wait()
    _quiet_labels = ['Приготовьтесь — тихо.', 'Ещё раз, негромко.']
    quiet_peaks: list[float] = []
    for i in range(2):
        peak = _capture_peak(_quiet_labels[i], noise_floor * 2.0)
        if peak is not None:
            quiet_peaks.append(peak)
    all_peaks = loud_peaks + quiet_peaks
    min_peak  = float(min(all_peaks))
    loud_med  = float(np.median(loud_peaks))
    target_peak   = 7000.0
    computed_gain = target_peak / max(loud_med, 1.0)
    gain          = max(1.0, min(6.0, round(computed_gain, 2)))
    min_peak_gained   = min_peak * gain
    noise_floor_gained = noise_floor * gain
    gap = max(0.0, min_peak_gained - noise_floor_gained)
    threshold = int(max(MIN_THRESH, noise_floor_gained + gap * 0.40))
    threshold = min(threshold, int(min_peak_gained * 0.65))
    threshold = max(threshold, MIN_THRESH)
    save_profile(threshold, gain, noise_floor=noise_floor, sample_rate=rate)
    _speak(
        f'Калибровка завершена. '
        f'Порог чувствительности — {threshold}, усиление — {gain:.1f}. '
        'Микрофон настроен и готов к работе.'
    )
    return (threshold, gain)
def calibrate_noise_simple(stream, chunk: int, chunk_ms: int) -> int:
    from core.audio_utils import rms_int16
    from config_pack.config import MIN_THRESH, NOISE_MULT
    seconds = 1.5
    frames  = int(seconds / (chunk_ms / 1000.0))
    vals    = []
    for _ in range(frames):
        try:
            data = stream.read(chunk, exception_on_overflow=False)
            vals.append(rms_int16(data))
        except Exception:
            pass
    if not vals:
        return int(MIN_THRESH)
    arr       = np.array(vals)
    noise_est = float(np.percentile(arr, 70))
    return int(max(MIN_THRESH, noise_est * NOISE_MULT))
