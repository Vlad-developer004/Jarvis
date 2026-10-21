import os as _os

# NOTE: the 32 MB stack size needed for Silero's deep call stacks (default
# 1 MB causes STATUS_STACK_OVERFLOW / 0xC00000FD on Windows) is applied only to
# the few threads that run TTS inference, not process-wide — see
# core/speech/tts.py's _spawn_with_big_stack().

# CPU-only: keep any CUDA runtime from initialising before the native DLL imports.
_os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')

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
from core.audio_utils import open_input_resilient
from core.system import (
    active_module_profile,
    app_state,
    module_enabled,
    play_early_greeting,
)

engine = None
handler = None
asr = None
stream = None

# Event signalled when engine is fully constructed and ready.
_engine_ready = _threading.Event()

from core import i18n
from core.speech.asr_manager import ASRManager

asr = ASRManager(STT_ENGINE, RATE, MODEL_PATH, SILERO_VAD_PATH)
i18n.register_asr(asr)
def _run_ui():
    """The window is a separate process (ui_next/shell.py): the core only feeds it through the bridge. The bridge starts at once, so the
    window shows the loading state while the models load; the handler is given to it when the engine is ready."""
    from ui_next import bridge as _ui_bridge, host as _host, shell as _shell
    _host.STATE.mode = _host.HudState.LOADING
    try:
        _ui_bridge.start(None)
        if _os.environ.get('JARVIS_NO_WINDOW') != '1':
            if _shell.launch():
                _shell.watch(lambda: _host.exit_now(0))       # the tray menu's Quit ends the assistant too
    except Exception as e:
        _log.critical('UI start error: %s', e, exc_info=True)
    _engine_ready.wait()
    try:
        _host.STATE.mode = _host.HudState.IDLE
        _ui_bridge.set_handler(handler)
        play_early_greeting(JARVIS_VOLUME)
    except Exception as e:
        _log.critical('UI bind error: %s', e, exc_info=True)

def _background_init():
    global engine, handler, asr, stream
    try:
        # Pure-Python TTS text-model warmup (pymorphy3 dictionaries) has no
        # GPU/audio hardware contention, so start it immediately instead of
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
            from core.nlp.semantic import warmup_async as _sem_warmup_async
            _sem_warmup_async(on_done=_on_nlp_done)
        except Exception as e:
            app_state.nlp_loading = False
            _log.error('Semantic warmup async error: %s', e, exc_info=True)

        # Local LLM chat fallback — lazy anyway (loads on first llm_chat
        # dispatch if this warmup hasn't finished), so failure here is never
        # fatal to startup. Skipped while the module is off: the model is ~1 GB.
        try:
            from core.system import module_enabled
            if module_enabled('llm_chat_fallback'):
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

        # Cloud QA client (library import ~1 s) built once the engine is up; no-op without a key.
        def _delayed_qa_prewarm():
            _engine_ready.wait()
            try:
                from features.qa.llm_processor import prewarm
                prewarm()
            except Exception:
                pass
        _threading.Thread(target=_delayed_qa_prewarm, daemon=True, name='QaPrewarm').start()

        chunk = int(RATE * CHUNK_MS / 1000)
        try:
            stream = open_input_resilient(RATE, chunk)
        except Exception as e:
            _log.critical('Cannot open audio input stream after retries: %s', e, exc_info=True)
            # Previously this just returned here — the whole background init
            # (ASR, engine, everything) silently aborted with zero indication
            # to the user, HUD stuck in LOADING forever, mutex still held so
            # even relaunching just said "already running". At least tell
            # them something is wrong instead of infinite silence.
            try:
                from ui_next import host as _hud
                _hud.notify('mic_open_failed',
                             'Не удалось открыть микрофон — проверьте устройство в Настройках и перезапустите Jarvis',
                             _hud.RED)
            except Exception:
                pass
            return
        asr.ensure_initialized()
        from core.engine import JarvisEngine
        from core.handler import CommandHandler
        handler = CommandHandler(RATE, chunk, asr)
        engine = JarvisEngine(asr, handler)
        # Signal all waiters that the engine is ready.
        _engine_ready.set()
        # STT model/VAD are downloaded lazily on first load (core/speech/asr.py) —
        # without this warmup that first load only starts on the user's first
        # spoken command, hanging mid-conversation with zero feedback instead of
        # during startup. warmup_stt() itself backgrounds the actual load/download,
        # so this call returns immediately. Mirrors TTS's warmup above.
        try:
            asr.warmup_stt()
        except Exception as e:
            _log.error('STT warmup error: %s', e, exc_info=True)
        from core.mic_calibration import calibrate_noise_simple, run_calibration
        from core.mic_calibration import load_profile as _load_mic_profile
        def _close_calibration_stream():
            # The engine opened its own capture; this one only served calibration and would keep a second capture process busy.
            global stream
            s, stream = stream, None
            if s:
                try: s.close()
                except Exception: pass
        mic_profile = _load_mic_profile()
        if mic_profile.get('calibrated'):
            engine.energy_thresh = max(50, int(mic_profile.get('threshold', 100)))
            engine.noise_ema = float(mic_profile.get('noise_floor', engine.energy_thresh / 2.2))
            _close_calibration_stream()
        else:
            engine.energy_thresh = calibrate_noise_simple(stream, chunk, CHUNK_MS)
            def _delayed_calibration():
                time.sleep(10.0)
                try:
                    new_thresh, new_gain = run_calibration(stream, chunk, RATE, CHUNK_MS)
                    engine.update_params(new_thresh, new_gain, JARVIS_VOLUME)
                except Exception as e:
                    _log.error('Delayed mic calibration failed: %s', e, exc_info=True)
                finally:
                    _close_calibration_stream()
            # The spoken calibration talks and listens for about a minute. While the first-run wizard is still to be finished its microphone step
            # does this, on the microphone picked there; running it here too would speak over the wizard and measure the default microphone.
            from core import settings_io
            if settings_io.read().get('ui_wizard_done'):
                _threading.Thread(target=_delayed_calibration, daemon=True).start()
            else:
                _close_calibration_stream()
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
            try:
                from ui_next.bridge.mail_watch import start_mail_watch
                start_mail_watch()
            except Exception as e:
                _log.error('mail_watch failed: %s', e, exc_info=True)
            if AUTO_UPDATE_ENABLED and module_enabled('updater') and getattr(sys, 'frozen', False):
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
    _threading.Thread(target=_run_ui, daemon=True).start()

    init_thread = _threading.Thread(target=_background_init, daemon=True)
    init_thread.start()
    try:
        _engine_ready.wait()
        if engine is not None:
            engine.run()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            from ui_next import shell as _shell
            _shell.stop()
        except Exception:
            pass
        if stream:
            stream.close()
