import sys
import multiprocessing as _mp_mod
import threading as _threading
import time
import pyaudio
from typing import Optional

# 1. First, bootstrap the system paths and CWD - MUST be before any internal imports
from core.system.bootstrap import bootstrap
bootstrap()

# 2. Now safe to import other internal modules
from core.system import play_early_greeting, app_state, module_enabled, active_module_profile
from core.audio_utils import open_input_stream
from config_pack.config import (
    MODEL_PATH, SILERO_VAD_PATH, RATE, CHUNK_MS,
    CALIBRATION_SEC, STT_ENGINE, JARVIS_VOLUME, TTS_WARMUP
)
engine = None
handler = None
asr = None
pa = None
stream = None
_hud = None
def _run_hud():
    global _hud
    from ui import hud as _m
    _hud = _m
    def _delayed_bind():
        try:
            while engine is None:
                time.sleep(0.5)
            _m._UPDATE_ASR_CALLBACK = engine.update_params
            from core.system import play_early_greeting
            from config_pack.config import JARVIS_VOLUME
            play_early_greeting(JARVIS_VOLUME)
        except Exception as e:
            with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                f.write(f"HUD_BIND: CRITICAL ERROR: {e}\n")
    _threading.Thread(target=_delayed_bind, daemon=True).start()
    _m.start()
def _background_init():
    global engine, handler, asr, pa, stream
    try:
        # Start TTS warmup with a delay to avoid hardware contention
        if TTS_WARMUP:
            def _delayed_warmup():
                time.sleep(2.0)
                try:
                    from core.speech import warmup_tts
                    warmup_tts()
                except Exception: pass
            _threading.Thread(target=_delayed_warmup, daemon=True).start()

        pa = pyaudio.PyAudio()
        chunk = int(RATE * CHUNK_MS / 1000)
        try:
            stream = open_input_stream(pa, RATE, chunk)
        except Exception as e:
            with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                f.write(f"MAIN: CRITICAL ERROR opening stream: {e}\n")
            return
        time.sleep(0.5)
        if STT_ENGINE == 'vosk':
            from core.speech import ASR_Vosk as asr_cls
        else:
            from core.speech import ASR as asr_cls
        asr = asr_cls(MODEL_PATH, SILERO_VAD_PATH, RATE) if STT_ENGINE != 'vosk' else asr_cls(RATE)
        from core.handler import CommandHandler
        from core.engine import JarvisEngine
        handler = CommandHandler(pa, RATE, chunk, asr)
        engine = JarvisEngine(pa, asr, handler)
        from core.mic_calibration import load_profile as _load_mic_profile, run_calibration, calibrate_noise_simple
        mic_profile = _load_mic_profile()
        if mic_profile.get('calibrated'):
            engine.energy_thresh = max(50, int(mic_profile.get('threshold', 100)))
            engine.noise_ema = float(mic_profile.get('noise_floor', engine.energy_thresh / 2.2))
        else:
            engine.energy_thresh = calibrate_noise_simple(stream, chunk, CHUNK_MS)
            def _delayed_calibration():
                time.sleep(10.0)
                try:
                    new_thresh, new_gain = run_calibration(stream, chunk, RATE, CHUNK_MS)
                    engine.update_params(new_thresh, new_gain, JARVIS_VOLUME)
                except Exception as e:
                    with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                        f.write(f"MAIN: delayed calibration failed: {e}\n")
            _threading.Thread(target=_delayed_calibration, daemon=True).start()
        def _start_features():
            if module_enabled('battery_monitor'):
                from features.battery import start_battery_monitor
                start_battery_monitor()
            if module_enabled('lag_hunter'):
                from features.lag_hunter import start_lag_hunter
                start_lag_hunter(handler)
            if module_enabled('games'):
                from features.gaming import start_game_watcher, scan_all_games
                _threading.Thread(target=scan_all_games, daemon=True).start()
                start_game_watcher(handler)
            if module_enabled('morning_briefing'):
                from features.morning_briefing import try_morning_briefing
                try_morning_briefing(handler)
            if module_enabled('calendar_ics'):
                from features.calendar_reminders import start_calendar_reminders
                start_calendar_reminders(handler)
            if module_enabled('updater'):
                from core.system import start_updater
                _threading.Thread(target=start_updater, daemon=True).start()
        _threading.Thread(target=_start_features, daemon=True).start()
    except Exception as e:
        import traceback
        with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
            f.write(f"MAIN_INIT: CRITICAL ERROR: {e}\n{traceback.format_exc()}\n")
_mp_mod.freeze_support()
_threading.Thread(target=_run_hud, daemon=True).start()
init_thread = _threading.Thread(target=_background_init, daemon=True)
init_thread.start()
try:
    while engine is None:
        time.sleep(0.5)
    engine.run()
except KeyboardInterrupt:
    pass
finally:
    if stream:
        stream.close()
    if pa:
        pa.terminate()
