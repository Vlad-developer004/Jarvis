import os
import re
import hashlib
import tempfile
import threading
import time
import queue
import gc
from datetime import datetime
import pygame
import psutil
import pythoncom
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'jarvis_tts_cache')
os.makedirs(CACHE_DIR, exist_ok=True)
_MODEL_DIR  = os.path.join('models', 'silero_tts')
_MODEL_FILE = os.path.join(_MODEL_DIR, 'v4_ru.pt')
_MODEL_URL  = 'https://models.silero.ai/models/tts/ru/v4_ru.pt'
_SPEAKER    = 'eugene'
_SAMPLE_RATE = 48000
_UNLOAD_AFTER_SEC = 300.0  # Fallback, overridden by config
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_SPLIT_THRESHOLD = 90
_CYR_LETTERS = {'А': 'а', 'Б': 'бэ', 'В': 'вэ', 'Г': 'гэ', 'Д': 'дэ', 'Е': 'е', 'Ё': 'ё', 'Ж': 'жэ', 'З': 'зэ', 'И': 'и', 'Й': 'й', 'К': 'ка', 'Л': 'эл', 'М': 'эм', 'Н': 'эн', 'О': 'о', 'П': 'пэ', 'Р': 'эр', 'С': 'эс', 'Т': 'тэ', 'У': 'у', 'Ф': 'эф', 'Х': 'ха', 'Ц': 'цэ', 'Ч': 'чэ', 'Ш': 'ша', 'Щ': 'ща', 'Э': 'э', 'Ю': 'ю', 'Я': 'я'}
_CYR_ABBREV  = {'США': 'сешеа', 'РФ': 'эрэф', 'ООН': 'оон', 'НАТО': 'нато', 'ТАСС': 'тасс', 'МВД': 'эмвэдэ', 'ФСБ': 'эфэсбэ', 'КГБ': 'кэгэбэ', 'ЦРУ': 'цээру', 'ФБР': 'эфбэр', 'МИД': 'мид', 'ВВП': 'вэвэпэ', 'ВВС': 'вэвээс', 'ФНС': 'фээнэс', 'МЧС': 'эмчээс', 'ДТП': 'дэтэпэ', 'СМИ': 'сми', 'НЛО': 'энэло', 'ПК': 'пэка', 'ОС': 'оэс', 'ИП': 'ип', 'ООО': 'ооо', 'ЧС': 'чээс', 'ВМФ': 'вэмэ эф', 'ФСО': 'эфэсэ', 'ГРУ': 'гэрэу', 'СВР': 'эсвээр', 'МГУ': 'эм гэ у', 'РАН': 'ран', 'ВЦИОМ': 'вциом', 'ЦБ': 'цэ бэ', 'ЕС': 'е эс', 'СНГ': 'эс эн гэ', 'БРИКС': 'брикс', 'СССР': 'эс эс эс эр', 'ТВ': 'тэ вэ', 'ДНР': 'дэ эн эр', 'ЛНР': 'эл эн эр'}
_LETTER_NAMES = {'A': 'эй', 'B': 'би', 'C': 'си', 'D': 'ди', 'E': 'и', 'F': 'эф', 'G': 'джи', 'H': 'эйч', 'I': 'ай', 'J': 'джей', 'K': 'кей', 'L': 'эл', 'M': 'эм', 'N': 'эн', 'O': 'оу', 'P': 'пи', 'Q': 'кью', 'R': 'ар', 'S': 'эс', 'T': 'ти', 'U': 'ю', 'V': 'ви', 'W': 'дабл-ю', 'X': 'экс', 'Y': 'вай', 'Z': 'зет'}
_PHONETIC_DRIVES = {k: _LETTER_NAMES.get(k, k).capitalize() for k in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'}
_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'
_EXCEPTIONS = {'openai': 'опен эй ай', 'chatgpt': 'чат джи пи ти', 'gpt': 'джи пи ти', 'youtube': 'ютуб', 'discord': 'дискорд', 'twitch': 'твич', 'telegram': 'телеграм', 'whatsapp': 'вотсап', 'instagram': 'инстаграм', 'tiktok': 'тик ток', 'twitter': 'твиттер', 'facebook': 'фейсбук', 'netflix': 'нетфликс', 'spotify': 'спотифай', 'google': 'гугл', 'amazon': 'амазон', 'apple': 'эппл', 'iphone': 'айфон', 'ipad': 'айпэд', 'imac': 'аймак', 'android': 'андроид', 'windows': 'виндовс', 'microsoft': 'майкрософт', 'github': 'гитхаб', 'gitlab': 'гитлаб', 'chrome': 'хром', 'firefox': 'файерфокс', 'safari': 'сафари', 'nvidia': 'энвидиа', 'amd': 'амд', 'intel': 'интел', 'xbox': 'иксбокс', 'playstation': 'плейстейшн', 'nintendo': 'нинтендо', 'steam': 'стим', 'epic': 'эпик', 'games': 'геймс', 'launcher': 'лаунчер', 'euro': 'евро', 'truck': 'трак', 'simulator': 'симулятор', 'ets': 'е т с', 'minecraft': 'майнкрафт', 'cyberpunk': 'киберпанк', 'witcher': 'ведьмак', 'valorant': 'валорант', 'fortnite': 'фортнайт', 'overwatch': 'оверватч', 'hearthstone': 'хёртстон', 'dota': 'дота', 'counter': 'кантер', 'strike': 'страйк', 'planetbase': 'планет бэйс', 'iv': 'четыре', 'iii': 'три', 'ii': 'два', 'v': 'пять', 'exe': 'экзэ', 'dll': 'диэлэл', 'bat': 'бат', 'cmd': 'цээмдэ', 'zip': 'зип', 'rar': 'рар', 'mp3': 'эмпэ три', 'mp4': 'эмпэ четыре', 'pdf': 'пэдээф', 'jpg': 'джыпег', 'jpeg': 'джыпег', 'png': 'пээнг', 'antigravity': 'антигравити', 'gravity': 'гравити', 'anti': 'анти', 'python': 'питон', 'java': 'джава', 'javascript': 'джаваскрипт', 'typescript': 'тайпскрипт', 'react': 'реакт', 'docker': 'докер', 'linux': 'линукс', 'ubuntu': 'убунту', 'bluetooth': 'блютус', 'wifi': 'вайфай', 'wi-fi': 'вайфай', 'browser': 'браузер', 'nuclear': 'нуклеар', 'option': 'опшн', 'iron': 'айрон', 'hearts': 'хёртс', 'c': 'Ц', 'd': 'Д', 'e': 'Е', 'f': 'эф'}
_ABBREV = {'vlc': 'вэ эл си', 'cpu': 'си пи ю', 'gpu': 'джи пи ю', 'ram': 'рэм', 'rom': 'ром', 'ssd': 'эс эс ди', 'hdd': 'эйч ди ди', 'usb': 'ю эс би', 'hdmi': 'эйч ди эм ай', 'fps': 'эф пи эс', 'api': 'эй пи ай', 'url': 'ю эр эл', 'gui': 'джи ю ай', 'ai': 'эй ай', 'pc': 'пи си', 'os': 'оу эс', 'ok': 'окей', 'vpn': 'вэ пэ эн', 'ip': 'ай пи', 'id': 'ай ди', 'vs': 'версус', 'gta': 'гта', 'rpg': 'эрпэгэ', 'ui': 'юай', 'ux': 'юикс', 'tv': 'тиви'}
_UNIT_EXPANSIONS = {'gb': 'гигабайт', 'mb': 'мегабайт', 'kb': 'килобайт', 'km/h': 'километров в час', 'км/ч': 'километров в час', 'kg': 'килограмм', 'cm': 'сантиметров', 'mm': 'миллиметров'}
_ARB = {'AA': 'а', 'AE': 'э', 'AH': 'а', 'AO': 'о', 'AW': 'ау', 'AY': 'ай', 'EH': 'э', 'ER': 'ер', 'EY': 'эй', 'IH': 'и', 'IY': 'и', 'OW': 'оу', 'OY': 'ой', 'UH': 'у', 'UW': 'у', 'B': 'б', 'CH': 'ч', 'D': 'д', 'DH': 'з', 'F': 'ф', 'G': 'г', 'HH': 'х', 'JH': 'дж', 'K': 'к', 'L': 'л', 'M': 'м', 'N': 'н', 'NG': 'нг', 'P': 'п', 'R': 'р', 'S': 'с', 'SH': 'ш', 'T': 'т', 'TH': 'т', 'V': 'в', 'W': 'в', 'Y': 'й', 'Z': 'з', 'ZH': 'ж'}
_tts_engine = None
_g2p, _g2p_lock = None, threading.Lock()
_MASTER_VOLUME = 1.0
_warmup_started = False
_warmup_lock = threading.Lock()
_mixer_lock = threading.RLock()
try:
    if not pygame.mixer.get_init():
        pygame.mixer.pre_init(48000, -16, 2, 2048)
except Exception: pass

class TTSManager:
    _instance = None
    _lock = threading.Lock()
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        print("[TTS] Initializing Manager...", flush=True)
        self.model = None
        self.queue = queue.PriorityQueue()
        self.stop_event = threading.Event()
        self.active_playback = False
        self._gen_count = 0
        self._gen_lock = threading.Lock()
        self._last_items = {}
        self._last_items_lock = threading.Lock()
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=2)
        print("[TTS] Starting Worker thread...", flush=True)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True, name='TTS-Worker')
        self.worker_thread.start()
        self.unload_timer = None

    def _worker(self):
        pythoncom.CoInitialize()
        print("[TTS-WORKER] Thread started.", flush=True)
        try:
            from actions.volume import duck_volume, force_unduck
        except ImportError:
            duck_volume = lambda x: None
            force_unduck = lambda: None
        self.channel = None
        _unduck_timer = {'id': None}
        while True:
            try:
                # Wait for task
                pri, ts, item = self.queue.get(timeout=0.5)
                if item is None: break
                
                print(f"[TTS-WORKER] Processing: {item}", flush=True)
                self.active_playback = True
                self.stop_event.clear()
                
                with _mixer_lock:
                    try:
                        ensure_mixer_init()
                        self.active_playback = True
                        
                        try:
                            self.channel = pygame.mixer.find_channel(force=True)
                            if self.channel is None:
                                self.channel = pygame.mixer.Channel(7)
                        except Exception:
                            try: pygame.mixer.quit()
                            except: pass
                            ensure_mixer_init()
                            self.channel = pygame.mixer.find_channel(force=True) or pygame.mixer.Channel(7)

                        if self.channel is None:
                            print("[TTS-WORKER] ERROR: Could not acquire audio channel.", flush=True)
                            self.active_playback = False
                            self.queue.task_done()
                            continue

                        duck_volume(True)
                        audio_path = str(item)
                        if not os.path.exists(audio_path):
                            print(f"[TTS-WORKER] Generating audio for: {item[:20]}...", flush=True)
                            audio_path = _generate_cached(item)
                        
                        if not audio_path or not os.path.exists(audio_path):
                            print(f"[TTS-WORKER] ERROR: Audio path invalid: {audio_path}", flush=True)
                            self.active_playback = False
                            self.queue.task_done()
                            continue

                        h = datetime.now().hour
                        is_night = (h >= 22 or h < 7)
                        vol = _MASTER_VOLUME * 0.7 if is_night else _MASTER_VOLUME
                        if is_night: vol = max(vol, min(_MASTER_VOLUME, 0.2))
                        
                        self.channel.set_volume(vol)
                        self._safe_hud_set_mode('speaking')
                        
                        print(f"[TTS-WORKER] Playing: {audio_path}", flush=True)
                        try:
                            sound = pygame.mixer.Sound(audio_path)
                        except Exception as e:
                            print(f"[TTS-WORKER] Sound creation error: {e}", flush=True)
                            if "device hasn't been opened" in str(e).lower():
                                try: pygame.mixer.quit()
                                except: pass
                            self.active_playback = False
                            self.queue.task_done()
                            continue

                        if self.channel.get_busy():
                            while self.channel.get_queue() is not None and not self.stop_event.is_set():
                                with _mixer_lock:
                                    if not pygame.mixer.get_init(): break
                                time.sleep(0.01)
                            if not self.stop_event.is_set() and pygame.mixer.get_init():
                                self.channel.queue(sound)
                        else:
                            self.channel.play(sound)
                    except Exception as e:
                        err_str = str(e)
                        print(f"TTS-WORKER: EXCEPTION inside lock: {err_str}", flush=True)
                        if "Audio device hasn't been opened" in err_str or "not initialized" in err_str:
                            try: pygame.mixer.quit()
                            except: pass
                        self.active_playback = False
                        self.queue.task_done()
                        continue

                # Playback loop
                while not self.stop_event.is_set():
                    busy = False
                    with _mixer_lock:
                        try:
                            if pygame.mixer.get_init() and self.channel and (self.channel.get_busy() or self.channel.get_queue()):
                                busy = True
                        except: pass
                    if not busy: break
                    time.sleep(0.05)
                
                # Cleanup if queue is finally empty
                if self.queue.empty() and self._gen_count == 0:
                    try: force_unduck()
                    except: pass
                    try:
                        if _unduck_timer['id'] is not None:
                            _unduck_timer['id'].cancel()
                    except: pass
                    try:
                        _unduck_timer['id'] = threading.Timer(2.0, lambda: (force_unduck(),))
                        _unduck_timer['id'].daemon = True
                        _unduck_timer['id'].start()
                    except: pass
                    self._safe_hud_set_mode('idle')
                    self.active_playback = False
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"TTS-WORKER: Loop Exception: {e}", flush=True)

    def wait_until_finished(self, timeout: float = 30.0):
        start = time.time()
        while (not self.queue.empty() or self.active_playback) and (time.time() - start < timeout):
            time.sleep(0.05)

    def speak(self, text: str, priority: int = 10, wait: bool = False):
        text = normalize_for_tts(text).strip()
        if not text: return
        self.active_playback = True
        self.stop_event.clear()
        sentences = _SENTENCE_SPLIT_RE.split(text) if len(text) > _SPLIT_THRESHOLD else [text]
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            self.active_playback = False
            return
        with self._gen_lock: self._gen_count += len(sentences)
        base_ts = time.time()
        for i, s in enumerate(sentences): self.executor.submit(self._queue_sentence, s, priority, base_ts + i * 0.001)
        self._reset_unload_timer()
        if wait: self.wait_until_finished()
        else: time.sleep(0.02)

    def put_item(self, priority: int, ts: float, item: str):
        if not hasattr(self, '_last_items_lock'):
            with self._lock:
                if not hasattr(self, '_last_items_lock'):
                    self._last_items = {}
                    self._last_items_lock = threading.Lock()
        now = time.time()
        with self._last_items_lock:
            self._last_items = {k: v for k, v in self._last_items.items() if now - v < 5.0}
            last_ts = self._last_items.get(item)
            if last_ts and (now - last_ts < 2.0): return
            self._last_items[item] = now
        self.queue.put((priority, ts, item))
        self.active_playback = True # Signal active immediately

    def _queue_sentence(self, text: str, priority: int, ts: float):
        try:
            path = _generate_cached(text)
            if path: self.put_item(priority, ts, path)
        finally:
            with self._gen_lock:
                self._gen_count = max(0, self._gen_count - 1)

    def stop(self):
        self.stop_event.set()
        while not self.queue.empty():
            try: self.queue.get_nowait(); self.queue.task_done()
            except queue.Empty: break
        with _mixer_lock:
            try:
                if self.channel:
                    self.channel.stop()
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception: pass
        try:
            from actions.volume import force_unduck
            force_unduck()
        except: pass
        self._safe_hud_set_mode('idle')
        self.active_playback = False

    def _safe_hud_set_mode(self, mode_name: str):
        try:
            from ui import hud as _hud
            # Thread-safe access to HUD root
            if not _hud or not hasattr(_hud, '_hud') or not _hud._hud or not _hud._hud.root: 
                return
            def _apply():
                try:
                    target = _hud.HudState.IDLE if mode_name == 'idle' else _hud.HudState.SPEAKING
                    if _hud.STATE: _hud.STATE.mode = target
                except: pass
            _hud._hud.root.after(0, _apply)
        except Exception:
            pass
    def _reset_unload_timer(self):
        if self.unload_timer:
            self.unload_timer.cancel()
        
        # Load timeout from config
        try:
            from config_pack.config import TTS_UNLOAD_TIMEOUT as _tout
            tout = _tout
        except Exception:
            tout = 300.0
            
        if tout <= 0:
            return

        self.unload_timer = threading.Timer(tout, self._unload_model)
        self.unload_timer.daemon = True
        self.unload_timer.start()
    def _unload_model(self):
        global _tts_engine
        
        # Prevent unloading in Game Mode
        from core.system import app_state as _as
        if getattr(_as, 'game_mode', False):
            print("[TTS] Skipping unload: Game Mode active.", flush=True)
            self._reset_unload_timer() # Check again later
            return

        with TTSManager._lock:
            if _tts_engine is not None:
                print("[TTS] Unloading model to free memory...", flush=True)
                _tts_engine = None
                gc.collect()
def _get_tts():
    global _tts_engine
    if _tts_engine is not None: return _tts_engine
    with TTSManager._lock:
        if _tts_engine is not None: return _tts_engine
        import torch
        _ensure_model()
        phys = psutil.cpu_count(logical=False) or 2
        torch_threads = 1 if phys <= 4 else 2
        torch.set_num_threads(torch_threads)
        try:
            torch.set_num_interop_threads(1)
        except Exception:
            pass
        model = torch.package.PackageImporter(_MODEL_FILE).load_pickle('tts_models', 'model')
        model.to(torch.device('cpu'))
        _tts_engine = model
        return _tts_engine
def _ensure_model() -> None:
    if os.path.exists(_MODEL_FILE): return
    import torch
    os.makedirs(_MODEL_DIR, exist_ok=True)
    torch.hub.download_url_to_file(_MODEL_URL, _MODEL_FILE)
def _generate_cached(text: str) -> str | None:
    key = f'{text}|{_SPEAKER}|{_SAMPLE_RATE}'
    h = hashlib.md5(key.encode('utf-8')).hexdigest()[:12]
    path = os.path.join(CACHE_DIR, f'silero_{h}.wav')
    if os.path.exists(path): return path
    try:
        model = _get_tts()
        tmp_path = path + '.tmp'
        model.save_wav(text=text, speaker=_SPEAKER, sample_rate=_SAMPLE_RATE, audio_path=tmp_path)
        if os.path.exists(tmp_path):
            os.replace(tmp_path, path)
            return path
    except Exception as e:
            print(f"TTS-GENERATOR: Error generating audio for '{text[:30]}...': {e}")
            import traceback
            traceback.print_exc()
    return None
def _resolve_sdl_device_name(preferred_name: str | None) -> str | None:
    """Find the exact SDL2 device name that best matches *preferred_name*.
    pygame.mixer uses SDL2 device strings which can differ from PyAudio/WASAPI names.
    Returns None if no match found (callers should fall back to system default).
    """
    if not preferred_name:
        return None
    try:
        import ctypes, ctypes.util
        # Try SDL2 directly to enumerate output devices
        sdl2 = None
        for lib in ('SDL2', 'SDL2-2.0', 'SDL2.dll'):
            try:
                sdl2 = ctypes.CDLL(ctypes.util.find_library(lib) or lib)
                break
            except Exception:
                pass
        if sdl2:
            try:
                sdl2.SDL_GetNumAudioDevices.restype = ctypes.c_int
                sdl2.SDL_GetAudioDeviceName.restype = ctypes.c_char_p
                # Must init SDL audio subsystem first to get real device list
                try:
                    sdl2.SDL_Init(ctypes.c_uint32(0x00000010))  # SDL_INIT_AUDIO
                except Exception:
                    pass
                n = sdl2.SDL_GetNumAudioDevices(ctypes.c_int(0))  # 0 = output
                needle = preferred_name.lower()
                best = None
                best_score = 0
                for i in range(n):
                    raw = sdl2.SDL_GetAudioDeviceName(ctypes.c_int(i), ctypes.c_int(0))
                    if not raw:
                        continue
                    sdl_name = raw.decode('utf-8', errors='replace')
                    sdl_low = sdl_name.lower()
                    # exact match
                    if sdl_low == needle:
                        return sdl_name
                    # score by common substrings
                    score = sum(1 for word in needle.split() if word in sdl_low)
                    if score > best_score:
                        best_score = score
                        best = sdl_name
                if best and best_score > 0:
                    return best
            except Exception:
                pass
    except Exception:
        pass
    # Fallback: return None if no match found. 
    # Passing a WASAPI/PyAudio name directly to pygame.mixer.init(devicename=...) 
    # often leads to "Audio device hasn't been opened".
    return None




def ensure_mixer_init() -> None:
    with _mixer_lock:
        try:
            # Check if initialized. If so, try a test call to ensure device is open.
            init_data = pygame.mixer.get_init()
            if init_data:
                try:
                    pygame.mixer.set_num_channels(24)
                    return
                except Exception:
                    # Device might be "init" but not actually open
                    try: pygame.mixer.quit()
                    except: pass
            
            dev = None
            try:
                import json
                p = os.path.join('data', 'jarvis_settings.json')
                if os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        d = json.load(f)
                        if isinstance(d, dict):
                            dev = d.get('audio_output_device_name')
                            if not isinstance(dev, str) or not dev.strip():
                                dev = None
            except Exception:
                dev = None
            
            # Use System Default by default! (None)
            # 48000 matching pre_init is safer
            def _try_init(dname=None, freq=48000):
                try:
                    pygame.mixer.init(frequency=freq, devicename=dname, buffer=2048)
                    pygame.mixer.set_num_channels(24)
                    return True
                except Exception:
                    try: pygame.mixer.quit()
                    except: pass
                    return False

            success = False
            # Try order: 1. Default (None) 48k, 2. Default 44.1k
            if _try_init(None, 48000): success = True
            elif _try_init(None, 44100): success = True
            
            if not success:
                print("[TTS] CRITICAL: All mixer init attempts failed.", flush=True)

        except Exception as e: 
            print(f"[TTS] ensure_mixer_init crash: {e}", flush=True)

def apply_audio_devices(output_device_name: str | None = None, input_device_index: int | None = None) -> tuple[bool, str]:
    """Live-apply audio device changes without restarting Jarvis."""
    msgs = []
    ok = True

    # --- Output (TTS) ---
    with _mixer_lock:
        try:
            mgr = TTSManager()
            mgr.stop()
            time.sleep(0.15)
            try:
                pygame.mixer.quit()
            except Exception: pass
            time.sleep(0.1)
            
            sdl_dev = _resolve_sdl_device_name(output_device_name)
            
            def _try_init_local(dname=None):
                try:
                    if dname:
                        pygame.mixer.init(frequency=_SAMPLE_RATE, devicename=dname)
                    else:
                        pygame.mixer.init(frequency=_SAMPLE_RATE)
                    pygame.mixer.set_num_channels(24)
                    return True
                except Exception:
                    return False

            if sdl_dev:
                if _try_init_local(sdl_dev):
                    msgs.append(f'✓ Вывод переключён → {sdl_dev}')
                else:
                    if _try_init_local(None):
                        msgs.append(f'⚠ Устройство {sdl_dev!r} недоступно — сброшено на по умолчанию')
                        ok = False
                    else:
                        msgs.append('⚠ Критическая ошибка вывода')
                        ok = False
            else:
                if _try_init_local(None):
                    msgs.append('✓ Вывод сброшен на системный')
                else:
                    msgs.append('⚠ Не удалось инициализировать вывод')
                    ok = False

            mgr.channel = None
            try:
                import core.audio_utils as _au
                _au._last_jarvis_hp_check = 0.0
            except Exception: pass
        except Exception as e:
            msgs.append(f'⚠ Ошибка вывода: {e}')
            ok = False

    # --- Input (Microphone) ---
    try:
        from core.engine.jarvis import get_engine
        eng = get_engine()
        if eng is not None:
            import pyaudio
            from config_pack.config import RATE, CHUNK_MS
            from core.audio_utils import open_input_stream
            chunk = int(RATE * CHUNK_MS / 1000)
            try:
                eng.stream.close()
            except Exception:
                pass
            try:
                eng.stream = open_input_stream(eng.pa, RATE, chunk, device_index=input_device_index)
                msgs.append('✓ Микрофон переключён (активен немедленно)')
            except Exception as e:
                # Try fallback to default
                try:
                    eng.stream = open_input_stream(eng.pa, RATE, chunk)
                    msgs.append('⚠ Не удалось переключить микрофон, восстановлен системный')
                except Exception as e2:
                    msgs.append(f'⚠ Критическая ошибка микрофона: {e2}')
                    ok = False
        else:
            msgs.append('ℹ Движок не запущен — микрофон применится при следующем старте')
    except Exception as e:
        msgs.append(f'⚠ Ошибка входа: {e}')

    return ok, '  •  '.join(msgs)
def wait_for_pygame_mixer_idle(timeout: float = 90.0, poll: float = 0.08) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if not pygame.mixer.get_init():
                return
            if not pygame.mixer.get_busy():
                return
        except Exception:
            return
        time.sleep(poll)
def normalize_for_tts(text: str) -> str:
    if not text: return ''
    if not hasattr(normalize_for_tts, '_nlp_cache'):
        from core.nlp import format_time_russian, get_russian_plural
        from num2words import num2words
        normalize_for_tts._nlp_cache = (format_time_russian, get_russian_plural, num2words)
    format_time_russian, get_russian_plural, num2words = normalize_for_tts._nlp_cache
    text = re.sub(r'\b([A-Za-z]):\\', lambda m: f'диск {_PHONETIC_DRIVES.get(m.group(1).upper(), m.group(1).upper())} ', text)
    text = re.sub(r'\b(ГБ|МБ|КБ|км/ч|км/час|кг|см|мм)\b', lambda m: _UNIT_EXPANSIONS.get(m.group(0).lower(), m.group(0)), text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+)\s*%', lambda m: f"{num2words(int(m.group(1)), lang='ru')} {get_russian_plural(int(m.group(1)), ['процент', 'процента', 'процентов'])}", text)
    def _ru_genitive_ordinal(phrase: str) -> str:
        p = phrase.strip()
        for suf, rep in (('ый', 'ого'), ('ий', 'его'), ('ой', 'ого')):
            if p.endswith(suf):
                return p[:-2] + rep
        return p
    def _year_repl(m: re.Match) -> str:
        try:
            y = int(m.group(1))
            ordy = num2words(y, lang='ru', to='ordinal')
            return _ru_genitive_ordinal(ordy) + ' года'
        except Exception:
            return m.group(0)
    text = re.sub(r'\b(19\d{2}|20\d{2})\s*(?:года|год)\b', _year_repl, text, flags=re.IGNORECASE)
    text = re.sub(r'(?<![А-ЯЁа-яёa-zA-Z])[А-ЯЁ]{2,6}(?![А-ЯЁа-яёa-zA-Z])', lambda m: _CYR_ABBREV.get(m.group(0), ' '.join((_CYR_LETTERS.get(c, c) for c in m.group(0)))), text)
    text = re.sub(r"[a-zA-Z]+(?:['-][a-zA-Z]+)*", _transliterate_word, text)
    text = re.sub(r'(?<!\w)(\d+)(?!\w)', lambda m: num2words(int(m.group(1)), lang='ru'), text)
    text = re.sub(r'^(Сэр|Джарвис)\s+([а-яёА-ЯЁ])', r'\1, \2', text, flags=re.IGNORECASE)
    text = re.sub(r'([.!?])\s+(Сэр|Джарвис)\s+([а-яёА-ЯЁ])', r'\1 \2, \3', text, flags=re.IGNORECASE)
    return text.strip()
def _transliterate_word(m: re.Match) -> str:
    word = m.group(0); lower = word.lower()
    if lower in _EXCEPTIONS:
        val = _EXCEPTIONS[lower]
        return val.capitalize() if word[0].isupper() and (not word.isupper()) else val
    if word.isupper():
        if lower in _ABBREV: return _ABBREV[lower]
        if len(word) <= 6: return ' '.join((_LETTER_NAMES.get(c, c) for c in word))
    parts = re.sub('([a-z])([A-Z])', '\\1 \\2', word)
    parts = re.sub('([A-Z]+)([A-Z][a-z])', '\\1 \\2', parts).split()
    if len(parts) > 1:
        result = []
        for p in parts:
            pl = p.lower()
            if pl in _EXCEPTIONS: result.append(_EXCEPTIONS[pl])
            elif p.isupper() and pl in _ABBREV: result.append(_ABBREV[pl])
            elif p.isupper() and len(p) <= 4: result.append(' '.join((_LETTER_NAMES.get(c, c) for c in p)))
            else: result.append(_g2p_word(p))
        return ' '.join(result)
    return _g2p_word(word)
def _g2p_word(word: str) -> str:
    global _g2p
    if _g2p is None:
        with _g2p_lock:
            try:
                from g2p_en import G2p
                _g2p = G2p()
            except Exception: _g2p = False
    if not _g2p: return word
    try:
        phonemes = _g2p(word)
        res = ''.join((_ARB.get(p.rstrip('012'), '') for p in phonemes))
        return res if res else word
    except Exception: return word
def speak(text: str, priority: int = 10, wait: bool = False) -> None:
    TTSManager().speak(text, priority, wait)
def speak_async(text: str) -> threading.Thread:
    speak(text)
    return threading.Thread(target=lambda: None)
def stop_speaking() -> None:
    TTSManager().stop()
def warmup_tts() -> None:
    global _warmup_started
    with _warmup_lock:
        if _warmup_started:
            return
        _warmup_started = True
    def _warm():
        try:
            try:
                ensure_mixer_init()
            except Exception:
                pass
            _ensure_model()
            _generate_cached("Прогрев системы.")
            phrases = [
                'Слушаю.',
                'Принято.',
                'Дайте нормальный запрос.',
                'Начнём заново?',
                'Я всё помню.',
                'По делу?',
            ]
            for p in phrases:
                _generate_cached(normalize_for_tts(p))
        except Exception as e:
            print(f"TTS-WARMUP: Failed: {e}")
    threading.Thread(target=_warm, daemon=True).start()
def is_speaking() -> bool:
    mgr = TTSManager()
    busy = False
    try:
        if mgr.channel:
            if mgr.channel.get_busy() or mgr.channel.get_queue() is not None:
                busy = True
    except Exception: pass
    if not busy:
        try:
            if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                busy = True
        except Exception: pass
    queue_empty = False
    try:
        if mgr.queue.empty():
            queue_empty = True
    except Exception:
        queue_empty = True
    return mgr.active_playback or (mgr._gen_count > 0) or busy or (not queue_empty)
def is_tts_playing_audio() -> bool:
    mgr = TTSManager()
    try:
        if mgr.channel and (mgr.channel.get_busy() or mgr.channel.get_queue() is not None):
            return True
    except Exception:
        pass
    try:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            return True
    except Exception:
        pass
    return False
