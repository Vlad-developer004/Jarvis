import os as _os
import sys as _sys
import types as _types

# NOTE: the 32 MB stack size needed for PyTorch/Silero's deep call stacks
# (default 1 MB causes STATUS_STACK_OVERFLOW / 0xC00000FD on Windows) is no
# longer set globally here. It used to apply to *every* thread the process
# ever creates (timers, reminders, background checks, ...), reserving 32 MB
# of address space each for no reason. It's now applied selectively, only to
# the few threads that actually run Silero/PyTorch inference — see
# core/speech/tts.py's _spawn_with_big_stack().

# Disable CUDA globally before any native DLL imports (pygame, pyaudio, torch, pynvml).
# torch.cuda initialisation with pynvml causes 0xC0000005 on Windows.
# CUDA_VISIBLE_DEVICES='' prevents CUDA runtime init but NOT pynvml.nvmlInit(),
# so we also stub pynvml entirely — torch only uses it for GPU enumeration which
# is irrelevant on this CPU-only setup.
_os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')
if 'pynvml' not in _sys.modules:
    _pynvml_stub = _types.ModuleType('pynvml')
    class _NVMLError(Exception): pass
    _pynvml_stub.NVMLError = _NVMLError
    _pynvml_stub.NVMLError_DriverNotLoaded = _NVMLError
    _pynvml_stub.nvmlInit = lambda: None
    _pynvml_stub.nvmlShutdown = lambda: None
    _pynvml_stub.nvmlDeviceGetCount = lambda: 0
    _pynvml_stub.nvmlSystemGetDriverVersion = lambda: b'0.0'
    _sys.modules['pynvml'] = _pynvml_stub
    del _pynvml_stub, _NVMLError

# g2p_en (warmed up in core/speech/tts.py's warmup_text_models(), right after
# the PyTorch DLL preload below) imports nltk for tokenization, but nltk's
# nltk.tag package eagerly pulls in nltk.tag.sequential -> nltk.classify ->
# nltk.classify.scikitlearn -> sklearn -> pandas -> pyarrow as an unused
# optional-classifier import. pyarrow's native extension loading DLL-conflicts
# with the already-loaded torch/sherpa-onnx DLLs and crashes the whole process
# with STATUS_ACCESS_VIOLATION (0xC0000005) — not a Python ImportError, so the
# try/except ImportError already in pandas/sklearn's own code can't catch it.
# Nothing in this project uses pyarrow or sklearn directly, so stub pyarrow
# out before nltk gets a chance to import the real one.
if 'pyarrow' not in _sys.modules:
    _pyarrow_stub = _types.ModuleType('pyarrow')
    _pyarrow_stub.__version__ = '0.0.0'
    _sys.modules['pyarrow'] = _pyarrow_stub
    del _pyarrow_stub

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='pkg_resources')
import multiprocessing as _mp_mod
import sys
import threading as _threading
import time

# Dump the Python-level call stack of every thread to a file on fatal native
# crashes (e.g. 0xC0000005 access violations). Without this, a native crash
# kills the process silently with only an exit code and no indication of
# which Python code (or which thread) was running at the time.
import faulthandler as _faulthandler
try:
    _crash_log_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'logs', 'crash_dump.log')
    _os.makedirs(_os.path.dirname(_crash_log_path), exist_ok=True)
    _crash_log_file = open(_crash_log_path, 'a', encoding='utf-8')
    _faulthandler.enable(file=_crash_log_file, all_threads=True)
except Exception:
    pass

# 1. First, bootstrap the system paths and CWD - MUST be before any internal imports
from core.system.bootstrap import bootstrap

bootstrap()

from core.logging_setup import get_logger as _get_logger
_log = _get_logger('init')

# 2. Now safe to import other internal modules
from config_pack.config import (
    AUTO_UPDATE_ENABLED,
    CHUNK_MS,
    JARVIS_VOLUME,
    MODEL_PATH,
    RATE,
    SILERO_VAD_PATH,
    STT_ENGINE,
    TTS_WARMUP,
)
from core.audio_utils import open_input_stream
from core.system import (
    active_module_profile,
    app_state,
    module_enabled,
    play_early_greeting,
)

engine = None
handler = None
asr = None
pa = None
stream = None

# Event signalled when engine is fully constructed and ready.
_engine_ready = _threading.Event()

from core import i18n
from core.speech.asr_manager import ASRManager

asr = ASRManager(STT_ENGINE, RATE, MODEL_PATH, SILERO_VAD_PATH)
i18n.register_asr(asr)
_hud = None

def _run_hud():
    global _hud
    from ui.hud_themes import apply_theme
    apply_theme()
    from ui import hud as _m
    _hud = _m
    def _delayed_bind():
        try:
            from ui.hud_state import STATE, HudState
            STATE.mode = HudState.LOADING
            _engine_ready.wait()
            STATE.mode = HudState.IDLE
            _m._UPDATE_ASR_CALLBACK = engine.update_params
            from config_pack.config import JARVIS_VOLUME
            from core.system import play_early_greeting
            play_early_greeting(JARVIS_VOLUME)
        except Exception as e:
            _log.critical('HUD_BIND error: %s', e, exc_info=True)
    _threading.Thread(target=_delayed_bind, daemon=True).start()
    _m.start()

def _background_init():
    global engine, handler, asr, pa, stream
    import pyaudio as _pyaudio
    try:
        # CRITICAL: PyTorch DLLs MUST be loaded before sherpa-onnx on Windows
        # to prevent DLL symbol conflicts (0xC0000005 Access Violation).
        # Phase 1 — import only (fast ~2s): satisfies the DLL ordering constraint.
        # Phase 2 — model weights (slow): runs in background, does not block startup.
        try:
            from core.nlp.semantic import preload_pytorch as _preload_pt
            _preload_pt()
        except Exception as e:
            _log.error('Preload PyTorch error: %s', e, exc_info=True)
        app_state.pytorch_loaded.set()

        # Pure-Python TTS text-model warmup (pymorphy3/g2p_en dictionaries) has
        # no GPU/audio hardware contention, so start it immediately instead of
        # waiting for the audio engine — shaves 1-3s off first-response latency.
        if TTS_WARMUP:
            try:
                from core.speech import warmup_text_models
                warmup_text_models()
            except Exception as e:
                _log.error('TTS text-model warmup error: %s', e, exc_info=True)

        # Start loading model weights asynchronously so engine can start immediately.
        app_state.nlp_loading = True
        def _on_nlp_done():
            app_state.nlp_loading = False
            print('[INIT] Semantic model ready.', flush=True)
            try:
                if app_state.hud is not None:
                    app_state.hud.root.after(0, app_state.hud._draw_bot_strip)
            except Exception:
                pass
        try:
            from core.nlp.semantic import warmup_async as _sem_warmup_async
            _sem_warmup_async(on_done=_on_nlp_done)
        except Exception as e:
            app_state.nlp_loading = False
            _log.error('Semantic warmup async error: %s', e, exc_info=True)

        # Local LLM chat fallback — lazy anyway (loads on first llm_chat
        # dispatch if this warmup hasn't finished), so failure here is never
        # fatal to startup.
        try:
            from core.speech.llm_chat import warmup_async as _llm_warmup_async
            _llm_warmup_async()
        except Exception as e:
            _log.error('LLM chat warmup async error: %s', e, exc_info=True)

        # Start TTS warmup after engine is ready to avoid hardware contention.
        if TTS_WARMUP:
            def _delayed_warmup():
                _engine_ready.wait()
                try:
                    from core.speech import warmup_tts
                    warmup_tts()
                except Exception:
                    pass
            _threading.Thread(target=_delayed_warmup, daemon=True).start()

        pa = _pyaudio.PyAudio()
        chunk = int(RATE * CHUNK_MS / 1000)
        try:
            stream = open_input_stream(pa, RATE, chunk)
        except Exception as e:
            _log.critical('Cannot open audio input stream: %s', e, exc_info=True)
            return
        asr.ensure_initialized()
        from core.engine import JarvisEngine
        from core.handler import CommandHandler
        handler = CommandHandler(pa, RATE, chunk, asr)
        engine = JarvisEngine(pa, asr, handler)
        # Signal all waiters that the engine is ready.
        _engine_ready.set()
        from core.mic_calibration import calibrate_noise_simple, run_calibration
        from core.mic_calibration import load_profile as _load_mic_profile
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
                    _log.error('Delayed mic calibration failed: %s', e, exc_info=True)
            _threading.Thread(target=_delayed_calibration, daemon=True).start()
        def _start_features():
            if module_enabled('battery_monitor'):
                try:
                    from features.battery import start_battery_monitor
                    start_battery_monitor()
                except Exception as e:
                    _log.error('battery_monitor failed: %s', e, exc_info=True)
            if module_enabled('lag_hunter'):
                try:
                    from features.lag_hunter import start_lag_hunter
                    start_lag_hunter(handler)
                except Exception as e:
                    _log.error('lag_hunter failed: %s', e, exc_info=True)
            if module_enabled('games'):
                try:
                    from features.gaming import scan_all_games, start_game_watcher
                    _threading.Thread(target=scan_all_games, daemon=True).start()
                    start_game_watcher(handler)
                except Exception as e:
                    _log.error('games failed: %s', e, exc_info=True)
            if module_enabled('morning_briefing'):
                try:
                    from features.morning_briefing import try_morning_briefing, try_evening_summary
                    from features.weather_alerts import start_weather_alerts
                    try_morning_briefing(handler)
                    try_evening_summary(handler)
                    start_weather_alerts(handler)
                except Exception as e:
                    _log.error('morning_briefing failed: %s', e, exc_info=True)
            if module_enabled('calendar_ics'):
                try:
                    from features.calendar_reminders import start_calendar_reminders
                    start_calendar_reminders(handler)
                except Exception as e:
                    _log.error('calendar_ics failed: %s', e, exc_info=True)
            if module_enabled('updater'):
                try:
                    from core.system import start_updater
                    _threading.Thread(target=start_updater, daemon=True).start()
                except Exception as e:
                    _log.error('updater failed: %s', e, exc_info=True)
            if AUTO_UPDATE_ENABLED and getattr(sys, 'frozen', False):
                try:
                    from core.system import app_updater
                    _threading.Thread(target=app_updater.start, daemon=True).start()
                except Exception as e:
                    _log.error('app_updater failed: %s', e, exc_info=True)
            if module_enabled('remote_control'):
                try:
                    from features.remote_control import start_remote_control
                    start_remote_control(handler)
                except Exception as e:
                    _log.error('remote_control failed: %s', e, exc_info=True)
            if module_enabled('push_to_talk'):
                try:
                    from actions.system_parts.push_to_talk import start_push_to_talk
                    start_push_to_talk()
                except Exception as e:
                    _log.error('push_to_talk failed: %s', e, exc_info=True)
        _threading.Thread(target=_start_features, daemon=True).start()
        def _delayed_trim():
            time.sleep(20.0)
            try:
                from core.system.bootstrap import trim_memory
                trim_memory()
                print('[INIT] Startup memory trim completed.', flush=True)
            except Exception:
                pass
        _threading.Thread(target=_delayed_trim, daemon=True).start()
    except Exception as e:
        _log.critical('Background init failed: %s', e, exc_info=True)
        _engine_ready.set()  # Unblock waiters even on failure so they don't hang.

if __name__ == '__main__':
    _mp_mod.freeze_support()
    _threading.Thread(target=_run_hud, daemon=True).start()

    init_thread = _threading.Thread(target=_background_init, daemon=True)
    init_thread.start()
    try:
        _engine_ready.wait()
        if engine is not None:
            engine.run()
    except KeyboardInterrupt:
        pass
    finally:
        if stream:
            stream.close()
        if pa:
            pa.terminate()
