import sys
import os
import ctypes
import threading
import time
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('init')
def bootstrap():
    # Enable DPI awareness for sharp UI and to prevent Windows double-scaling
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    # cwd must be settled BEFORE anything resolves a relative 'logs' path below —
    # otherwise the stdout/stderr log file and the age/size cleanup loop can
    # end up looking at two different 'logs' directories (e.g. when launched
    # from a shortcut with a different "Start in" folder), and jarvis.log
    # would never be cleaned up since the cleanup runs in the post-chdir dir.
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        try:
            entry = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ''
            base = os.path.dirname(entry) if entry else ''
            if base and os.path.isdir(base):
                os.chdir(base)
        except Exception:
            pass

    # Clean up old/oversized log files BEFORE opening the current session's log
    # file below — otherwise this loop can truncate jarvis.log while it's
    # already open (append mode) on the new _Logger handle, corrupting it.
    os.makedirs('logs', exist_ok=True)
    try:
        import glob
        now = time.time()
        max_age_days = int(os.environ.get('JARVIS_LOG_MAX_AGE_DAYS', '7') or 7)
        max_bytes = int(os.environ.get('JARVIS_LOG_MAX_BYTES', str(2 * 1024 * 1024)) or (2 * 1024 * 1024))
        max_age_sec = max(1, max_age_days) * 86400
        for p in glob.glob(os.path.join('logs', '*.log')):
            try:
                if os.path.basename(p).startswith('.'):
                    continue
                st = os.stat(p)
                if (now - st.st_mtime) > max_age_sec:
                    os.remove(p)
                    continue
                if st.st_size > max_bytes:
                    keep = max_bytes // 2
                    with open(p, 'rb') as rf:
                        rf.seek(-keep, 2)
                        tail = rf.read()
                    with open(p, 'wb') as wf:
                        wf.write(b'...log truncated...\n')
                        wf.write(tail)
            except Exception:
                pass
    except Exception:
        pass

    # --- GLOBAL LOGGING SYSTEM ---
    class _Logger:
        def __init__(self, filename, original_stream):
            self.terminal = original_stream
            self.log = open(filename, "a", encoding="utf-8")
        def write(self, message):
            # sys.stdout/stderr are None in a windowed (no-console) frozen
            # build launched by double-click — only the file half applies then.
            if self.terminal is not None:
                self.terminal.write(message)
            if message.strip(): # Avoid double timestamps on empty lines
                ts = time.strftime("[%Y-%m-%d %H:%M:%S] ")
                self.log.write(ts + message)
            else:
                self.log.write(message)
            self.log.flush()
        def flush(self):
            if self.terminal is not None:
                self.terminal.flush()
            self.log.flush()

    log_file = os.path.join('logs', 'jarvis.log')
    sys.stdout = _Logger(log_file, sys.stdout)
    sys.stderr = _Logger(log_file, sys.stderr)
    os.environ.setdefault('OMP_NUM_THREADS', '2')
    os.environ.setdefault('ONNXRUNTIME_NUM_THREADS', '2')
    # Cap oneDNN primitive cache — TTS text length varies per sentence, so an
    # unbounded cache grows RAM over a long session (one primitive per unique shape).
    os.environ.setdefault('LRU_CACHE_CAPACITY', '4')
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, 'Global\\JarvisHUDSingleInstance')
    if ctypes.windll.kernel32.GetLastError() == 183:
        _log.warning('Single instance mutex detected — another instance is running. Exiting.')
        sys.exit(0)
    globals()['__single_instance_mutex'] = _mutex
    from .windows import defender_exclusion_needed, add_defender_exclusion, mark_defender_exclusion_done
    if defender_exclusion_needed():
        def _add_excl():
            if add_defender_exclusion():
                mark_defender_exclusion_done()
        threading.Thread(target=_add_excl, daemon=True).start()

    try:
        from config_pack.config import get_settings_path
        from core import i18n
        import json
        settings_path = get_settings_path()
        if os.path.exists(settings_path):
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            lang = settings.get('language', 'ru')
            i18n.set_language(lang)
    except Exception:
        pass
def play_early_greeting(volume=1.0):
    def _task():
        try:
            # Wait for TTS engine to be ready
            time.sleep(1.0)
            from core.speech import speak
            from core.i18n import get_language
            lang = get_language()
            from core.address import get_address
            addr = get_address(lang)
            if lang == 'uk':
                speak(f"Джарвіс до вашої уваги, {addr}. Всі системи готові.")
            else:
                speak(f"Приветствую, {addr}. Я запущен и готов к работе.")
        except Exception as e:
            _log.error('Early greeting TTS error: %s', e, exc_info=True)
    threading.Thread(target=_task, daemon=True).start()


def trim_memory():
    """Request Windows to empty the working set of the current process, freeing unused RAM."""
    try:
        import gc
        gc.collect()
        import ctypes
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.psapi.EmptyWorkingSet(handle)
    except Exception:
        pass

