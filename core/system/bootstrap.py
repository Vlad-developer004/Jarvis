import sys
import os
import ctypes
import threading
import time
import random
def bootstrap():
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
    os.makedirs('logs', exist_ok=True)
    try:
        import glob
        import pathlib
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
    os.environ.setdefault('OMP_NUM_THREADS', '2')
    os.environ.setdefault('ONNXRUNTIME_NUM_THREADS', '2')
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, 'Global\\JarvisHUDSingleInstance')
    if ctypes.windll.kernel32.GetLastError() == 183:
        with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
            f.write("Single instance mutex detected. Exiting.\n")
        sys.exit(0)
    globals()['__single_instance_mutex'] = _mutex
    from .windows import defender_exclusion_needed, add_defender_exclusion, mark_defender_exclusion_done
    if defender_exclusion_needed():
        def _add_excl():
            if add_defender_exclusion():
                mark_defender_exclusion_done()
        threading.Thread(target=_add_excl, daemon=True).start()
def play_early_greeting(volume=1.0):
    def _task():
        wavs = [f for f in ['audio/Джарвис - приветствие.wav'] if os.path.exists(f)]
        if not wavs: return
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            snd = pygame.mixer.Sound(random.choice(wavs))
            hour = time.localtime().tm_hour
            is_night = (hour >= 22 or hour < 7)
            final_vol = volume * 0.7 if is_night else volume
            if is_night:
                final_vol = max(final_vol, min(volume, 0.2))
            snd.set_volume(final_vol)
            ch = snd.play()
            while ch and ch.get_busy():
                time.sleep(0.1)
        except Exception:
            try:
                import winsound
                winsound.PlaySound(random.choice(wavs), winsound.SND_FILENAME)
            except Exception:
                pass
    threading.Thread(target=_task, daemon=True).start()
