import os
import re
import wave
import hashlib
import tempfile
import threading
import time
import queue
import gc
from collections import OrderedDict
from datetime import datetime
import pygame
import psutil
import pythoncom
import json
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = 'hide'
CACHE_DIR = os.path.join(tempfile.gettempdir(), 'jarvis_tts_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

_BIG_STACK_BYTES = 32 * 1024 * 1024  # PyTorch/Silero need deep call stacks on
# Windows — the default 1 MB causes STATUS_STACK_OVERFLOW (0xC00000FD). This
# used to be set globally for the whole process (every thread, forever); now
# it's only applied for the few thread-creation sites below that actually run
# Silero inference, then immediately reverted so unrelated threads (timers,
# reminders, ...) keep the normal small stack.
_stack_size_lock = threading.Lock()

def _spawn_with_big_stack(target, *, name: str | None = None, daemon: bool = True) -> threading.Thread:
    """Create+start a thread with the enlarged stack, then restore the
    process-wide default for whoever creates a thread next. Locked because
    threading.stack_size() is a single global setting, not per-thread."""
    with _stack_size_lock:
        old = threading.stack_size(_BIG_STACK_BYTES)
        try:
            t = threading.Thread(target=target, name=name, daemon=daemon)
            t.start()
            return t
        finally:
            threading.stack_size(old)
def _get_project_root() -> str:
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_MODEL_DIR = os.path.join(_get_project_root(), 'models', 'silero_tts')
_SAMPLE_RATE = 48000
_LANG_CONFIG = {
    'ru': {'model': 'v5_5_ru.pt', 'url': 'https://models.silero.ai/models/tts/ru/v5_5_ru.pt', 'speaker': 'eugene'},
    'uk': {'model': 'v4_ua.pt', 'url': 'https://models.silero.ai/models/tts/ua/v4_ua.pt', 'speaker': 'mykyta'}
}
_UNLOAD_AFTER_SEC = 300.0  # Fallback, overridden by config
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_SPLIT_THRESHOLD = 90
_MAX_CHUNK_CHARS = 250
_CYR_LETTERS = {'А': 'а', 'Б': 'бэ', 'В': 'вэ', 'Г': 'гэ', 'Д': 'дэ', 'Е': 'е', 'Ё': 'ё', 'Ж': 'жэ', 'З': 'зэ', 'И': 'и', 'Й': 'й', 'К': 'ка', 'Л': 'эл', 'М': 'эм', 'Н': 'эн', 'О': 'о', 'П': 'пэ', 'Р': 'эр', 'С': 'эс', 'Т': 'тэ', 'У': 'у', 'Ф': 'эф', 'Х': 'ха', 'Ц': 'цэ', 'Ч': 'чэ', 'Ш': 'ша', 'Щ': 'ща', 'Э': 'э', 'Ю': 'ю', 'Я': 'я'}
_CYR_ABBREV  = {'США': 'сешеа', 'РФ': 'эрэф', 'ООН': 'оон', 'НАТО': 'нато', 'ТАСС': 'тасс', 'МВД': 'эмвэдэ', 'ФСБ': 'эфэсбэ', 'КГБ': 'кэгэбэ', 'ЦРУ': 'цээру', 'ФБР': 'эфбэр', 'МИД': 'мид', 'ВВП': 'вэвэпэ', 'ВВС': 'вэвээс', 'ФНС': 'фээнэс', 'МЧС': 'эмчээс', 'ДТП': 'дэтэпэ', 'СМИ': 'сми', 'НЛО': 'энэло', 'ПК': 'пэка', 'ОС': 'оэс', 'ИП': 'ип', 'ООО': 'ооо', 'ЧС': 'чээс', 'ВМФ': 'вэмэ эф', 'ФСО': 'эфэсэ', 'ГРУ': 'гэрэу', 'СВР': 'эсвээр', 'МГУ': 'эм гэ у', 'РАН': 'ран', 'ВЦИОМ': 'вциом', 'ЦБ': 'цэ бэ', 'ЕС': 'е эс', 'СНГ': 'эс эн гэ', 'БРИКС': 'брикс', 'СССР': 'эс эс эс эр', 'ТВ': 'тэ вэ', 'ДНР': 'дэ эн эр', 'ЛНР': 'эл эн эр'}
_LETTER_NAMES = {'A': 'эй', 'B': 'би', 'C': 'си', 'D': 'ди', 'E': 'и', 'F': 'эф', 'G': 'джи', 'H': 'эйч', 'I': 'ай', 'J': 'джей', 'K': 'кей', 'L': 'эл', 'M': 'эм', 'N': 'эн', 'O': 'оу', 'P': 'пи', 'Q': 'кью', 'R': 'ар', 'S': 'эс', 'T': 'ти', 'U': 'ю', 'V': 'ви', 'W': 'дабл-ю', 'X': 'экс', 'Y': 'вай', 'Z': 'зет'}
_PHONETIC_DRIVES = {k: _LETTER_NAMES.get(k, k).capitalize() for k in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'}
_PHONETIC_DRIVES['C'] = 'Цэ'; _PHONETIC_DRIVES['K'] = 'Ка'; _PHONETIC_DRIVES['X'] = 'Икс'; _PHONETIC_DRIVES['Y'] = 'Игрек'
_EXCEPTIONS = {'openai': 'опен эй ай', 'chatgpt': 'чат джи пи ти', 'gpt': 'джи пи ти', 'youtube': 'ютуб', 'discord': 'дискорд', 'twitch': 'твич', 'telegram': 'телеграм', 'whatsapp': 'вотсап', 'instagram': 'инстаграм', 'tiktok': 'тик ток', 'twitter': 'твиттер', 'facebook': 'фейсбук', 'netflix': 'нетфликс', 'spotify': 'спотифай', 'google': 'гугл', 'amazon': 'амазон', 'apple': 'эппл', 'iphone': 'айфон', 'ipad': 'айпэд', 'imac': 'аймак', 'android': 'андроид', 'windows': 'виндовс', 'microsoft': 'майкрософт', 'github': 'гитхаб', 'gitlab': 'гитлаб', 'chrome': 'хром', 'firefox': 'файерфокс', 'safari': 'сафари', 'nvidia': 'энвидиа', 'amd': 'амд', 'intel': 'интел', 'xbox': 'иксбокс', 'playstation': 'плейстейшн', 'nintendo': 'нинтендо', 'steam': 'стим', 'epic': 'эпик', 'games': 'геймс', 'launcher': 'лаунчер', 'euro': 'евро', 'truck': 'трак', 'simulator': 'симулятор', 'ets': 'е т с', 'minecraft': 'майнкрафт', 'cyberpunk': 'киберпанк', 'witcher': 'ведьмак', 'valorant': 'валорант', 'fortnite': 'фортнайт', 'overwatch': 'оверватч', 'hearthstone': 'хёртстон', 'dota': 'дота', 'counter': 'кантер', 'strike': 'страйк', 'planetbase': 'планет бэйс', 'iv': 'четыре', 'iii': 'три', 'ii': 'два', 'v': 'пять', 'exe': 'экзэ', 'dll': 'диэлэл', 'bat': 'бат', 'cmd': 'цээмдэ', 'zip': 'зип', 'rar': 'рар', 'mp3': 'эмпэ три', 'mp4': 'эмпэ четыре', 'pdf': 'пэдээф', 'jpg': 'джыпег', 'jpeg': 'джыпег', 'png': 'пээнг', 'antigravity': 'антигравити', 'gravity': 'гравити', 'anti': 'анти', 'python': 'питон', 'java': 'джава', 'javascript': 'джаваскрипт', 'typescript': 'тайпскрипт', 'react': 'реакт', 'docker': 'докер', 'linux': 'линукс', 'ubuntu': 'убунту', 'bluetooth': 'блютус', 'wifi': 'вайфай', 'wi-fi': 'вайфай', 'browser': 'браузер', 'nuclear': 'нуклеар', 'option': 'опшн', 'iron': 'айрон', 'hearts': 'хёртс', 'c': 'Ц', 'd': 'Д', 'e': 'Е', 'f': 'эф'}
_ABBREV = {'vlc': 'вэ эл си', 'cpu': 'си пи ю', 'gpu': 'джи пи ю', 'ram': 'рэм', 'rom': 'ром', 'ssd': 'эс эс ди', 'hdd': 'эйч ди ди', 'usb': 'ю эс би', 'hdmi': 'эйч ди эм ай', 'fps': 'эф пи эс', 'api': 'эй пи ай', 'url': 'ю эр эл', 'gui': 'джи ю ай', 'ai': 'эй ай', 'pc': 'пи си', 'os': 'оу эс', 'ok': 'окей', 'vpn': 'вэ пэ эн', 'ip': 'ай пи', 'id': 'ай ди', 'vs': 'версус', 'gta': 'гта', 'rpg': 'эрпэгэ', 'ui': 'юай', 'ux': 'юикс', 'tv': 'тиви'}
_UNIT_EXPANSIONS = {'gb': 'гигабайт', 'mb': 'мегабайт', 'kb': 'килобайт', 'km/h': 'километров в час', 'км/ч': 'километров в час', 'kg': 'килограмм', 'cm': 'сантиметров', 'mm': 'миллиметров'}
_ARB = {'AA': 'а', 'AE': 'э', 'AH': 'а', 'AO': 'о', 'AW': 'ау', 'AY': 'ай', 'EH': 'э', 'ER': 'ер', 'EY': 'эй', 'IH': 'и', 'IY': 'и', 'OW': 'оу', 'OY': 'ой', 'UH': 'у', 'UW': 'у', 'B': 'б', 'CH': 'ч', 'D': 'д', 'DH': 'з', 'F': 'ф', 'G': 'г', 'HH': 'х', 'JH': 'дж', 'K': 'к', 'L': 'л', 'M': 'м', 'N': 'н', 'NG': 'нг', 'P': 'п', 'R': 'р', 'S': 'с', 'SH': 'ш', 'T': 'т', 'TH': 'т', 'V': 'в', 'W': 'в', 'Y': 'й', 'Z': 'з', 'ZH': 'ж'}
_tts_models = {}  # Cache for models by language
_tts_inference_lock = threading.Lock()  # Silero models are NOT thread-safe; serialise all save_wav calls
_g2p, _g2p_lock = None, threading.Lock()
_morph_ru = None
_morph_uk = None
_morph_lock = threading.Lock()
_normalize_cache: 'OrderedDict[tuple[str, str], str]' = OrderedDict()
_NORMALIZE_CACHE_MAX = 512
_normalize_cache_lock = threading.Lock()
_silero_supports_speech_rate: bool | None = None

# --- TTS speed cache ---------------------------------------------------
_tts_speed_cache: float | None = None
_tts_speed_lock = threading.Lock()

def invalidate_tts_speed_cache() -> None:
    global _tts_speed_cache
    with _tts_speed_lock:
        _tts_speed_cache = None

# --- Night volume cache ------------------------------------------------
_night_vol_cache: tuple[int, int, int, int, float] | None = None
_night_vol_lock = threading.Lock()

def _invalidate_night_vol_cache() -> None:
    global _night_vol_cache
    with _night_vol_lock:
        _night_vol_cache = None

def _get_night_vol_settings() -> tuple[int, int, int, int, float]:
    global _night_vol_cache
    with _night_vol_lock:
        if _night_vol_cache is not None:
            return _night_vol_cache
        try:
            from config_pack.config import get_settings_path as _gsp
            _s = json.load(open(_gsp(), encoding='utf-8'))
            result: tuple[int, int, int, int, float] = (
                int(_s.get('tts_night_start', 22)),
                int(_s.get('tts_night_start_min', 0)),
                int(_s.get('tts_night_end', 7)),
                int(_s.get('tts_night_end_min', 0)),
                float(_s.get('tts_night_volume', 0.7)),
            )
        except Exception:
            result = (22, 0, 7, 0, 0.7)
        _night_vol_cache = result
        return result

# --- WAV cache eviction ------------------------------------------------
_CACHE_MAX_FILES = 300  # Keep newest N files; extras are deleted.
_CACHE_EVICT_INTERVAL = 1800  # Seconds between automatic eviction runs.

def _evict_wav_cache() -> None:
    try:
        files = sorted(
            (f for f in os.scandir(CACHE_DIR) if f.name.endswith('.wav')),
            key=lambda e: e.stat().st_mtime,
            reverse=True,
        )
        for entry in files[_CACHE_MAX_FILES:]:
            try:
                os.remove(entry.path)
            except OSError:
                pass
    except Exception:
        pass

def _schedule_cache_eviction() -> None:
    _evict_wav_cache()
    t = threading.Timer(_CACHE_EVICT_INTERVAL, _schedule_cache_eviction)
    t.daemon = True
    t.start()

# Run once at import time and then on a recurring timer.
threading.Thread(target=_schedule_cache_eviction, daemon=True).start()

def _get_morph(lang: str = 'ru'):
    global _morph_ru, _morph_uk
    try:
        import pymorphy3 as _pm3
        if lang == 'uk':
            if _morph_uk is None:
                with _morph_lock:
                    if _morph_uk is None:
                        _morph_uk = _pm3.MorphAnalyzer(lang='uk')
            return _morph_uk
        else:
            if _morph_ru is None:
                with _morph_lock:
                    if _morph_ru is None:
                        _morph_ru = _pm3.MorphAnalyzer()
            return _morph_ru
    except Exception:
        return None
_MASTER_VOLUME = 1.0
_warmup_started = False
_warmup_lock = threading.Lock()
_text_warmup_started = False
_text_warmup_lock = threading.Lock()
_mixer_lock = threading.RLock()
_cached_audio_device: str | None = None
_cached_audio_device_loaded: bool = False

def _get_lang() -> str:
    # Voice/model language — deliberately get_speech_language(), not
    # get_language() (on-screen UI text). See core.i18n.get_speech_language.
    try:
        from core.i18n import get_speech_language
        return get_speech_language()
    except Exception:
        return 'ru'

def _get_tts_speed() -> float:
    global _tts_speed_cache
    with _tts_speed_lock:
        if _tts_speed_cache is not None:
            return _tts_speed_cache
        try:
            from config_pack.config import get_settings_path
            with open(get_settings_path(), 'r', encoding='utf-8') as _f:
                val = max(0.6, min(1.4, float(json.load(_f).get('tts_speed', 1.0))))
        except Exception:
            val = 1.0
        _tts_speed_cache = val
        return val

def _apply_wav_speed(src: str, speed: float) -> str:
    """Return path to WAV with modified framerate for playback speed control.
    speed < 1.0 → slower (lower pitch); speed > 1.0 → faster (higher pitch)."""
    if abs(speed - 1.0) < 0.02:
        return src
    spct = int(round(speed * 100))
    dst = src.replace('.wav', f'_sp{spct}.wav')
    if os.path.exists(dst):
        return dst
    try:
        with wave.open(src, 'rb') as r:
            p = r.getparams()
            data = r.readframes(p.nframes)
        with wave.open(dst, 'wb') as w:
            w.setnchannels(p.nchannels)
            w.setsampwidth(p.sampwidth)
            w.setframerate(max(1, int(p.framerate * speed)))
            w.writeframes(data)
        return dst
    except Exception:
        return src

def _get_model_config(lang: str = None) -> dict:
    if lang is None: lang = _get_lang()
    return _LANG_CONFIG.get(lang, _LANG_CONFIG['ru'])

def _get_model_file(lang: str = None) -> str:
    config = _get_model_config(lang)
    return os.path.join(_MODEL_DIR, config['model'])

def _get_model_url(lang: str = None) -> str:
    config = _get_model_config(lang)
    return config['url']

def _get_speaker(lang: str = None) -> str:
    config = _get_model_config(lang)
    return config['speaker']
try:
    if not pygame.mixer.get_init():
        # Buffer of 4096 samples (~85ms @ 48kHz) gives the audio thread enough
        # headroom to survive CPU spikes from concurrent Silero inference without
        # underrunning — a too-small buffer here is the classic cause of crackle.
        pygame.mixer.pre_init(48000, -16, 2, 4096)
except Exception: pass

def _chunk_text(text: str) -> list[str]:
    """Split text into chunks safe for Silero: first by sentence, then by word boundary."""
    raw = _SENTENCE_SPLIT_RE.split(text) if len(text) > _SPLIT_THRESHOLD else [text]
    chunks: list[str] = []
    for s in raw:
        s = s.strip()
        if not s:
            continue
        # Skip chunks that are only punctuation (remnants of "..." separators)
        if all(c in '.!?—- ' for c in s):
            continue
        if len(s) <= _MAX_CHUNK_CHARS:
            chunks.append(s)
            continue
        words = s.split()
        current: list[str] = []
        current_len = 0
        for word in words:
            added = len(word) + (1 if current else 0)
            if current_len + added > _MAX_CHUNK_CHARS and current:
                chunks.append(' '.join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += added
        if current:
            chunks.append(' '.join(current))
    return chunks


class _OrderedBatch:
    """Parallel generation with guaranteed in-order release to the playback queue.

    Each sentence gets an index. When generation finishes (in any order),
    finished() is called. Items are only released to the queue once all
    earlier indices have also finished — so the worker always plays in order.
    Gaps from failed generation (path=None) are skipped so later sentences
    are never blocked.

    A watchdog timer fires after _BATCH_TIMEOUT seconds and forcibly flushes
    any remaining buffered items so a single hung generation cannot block the
    entire batch indefinitely.
    """
    _BATCH_TIMEOUT = 15.0  # seconds before watchdog flushes stuck batch

    __slots__ = ('_priority', '_base_ts', '_mgr', '_lock', '_buf', '_next', '_watchdog', '_epoch', '_pending')

    def __init__(self, priority: int, base_ts: float, mgr: 'TTSManager', epoch: int) -> None:
        self._priority = priority
        self._base_ts = base_ts
        self._mgr = mgr
        self._epoch = epoch
        self._lock = threading.Lock()
        self._buf: dict[int, str | None] = {}
        self._next = 0
        self._pending: list[tuple[str, int]] = []
        self._watchdog = threading.Timer(self._BATCH_TIMEOUT, self._flush_remaining)
        self._watchdog.daemon = True
        self._watchdog.start()

    def _pop_pending(self) -> tuple[str, int] | None:
        # Self-throttling queue depth: speak() only submits the first
        # _MAX_INFLIGHT sentences to the executor up front; each finished
        # generation pulls the next one instead of all sentences sitting as
        # submitted tasks at once (matters for long AI answers, ~20 sentences,
        # with only 2 workers).
        with self._lock:
            if self._pending:
                return self._pending.pop(0)
            return None

    def _stale(self) -> bool:
        # True if stop() was called (a new epoch started) after this batch began —
        # discard results instead of queuing leftover audio from a cancelled answer.
        return self._mgr.gen_epoch != self._epoch

    def _flush_remaining(self) -> None:
        with self._lock:
            if not self._buf:
                return
            # Hold the manager's gen_lock across the stale-check + put_item so
            # this can't race with stop() bumping gen_epoch and draining the
            # queue from another thread (e.g. a rapid second "Джарвис" while
            # this batch's audio is still generating) — without this, a check
            # that passes just before stop()'s epoch bump could still enqueue
            # its item just after stop()'s drain loop already finished,
            # leaving stale audio to play alongside/over the new response.
            with self._mgr._gen_lock:
                if not self._stale():
                    for idx in sorted(self._buf):
                        item = self._buf[idx]
                        if item:
                            self._mgr.put_item(self._priority, self._base_ts + idx * 0.001, item)
            self._buf.clear()

    def finished(self, index: int, path: str | None) -> None:
        with self._lock:
            self._buf[index] = path
            while self._next in self._buf:
                item = self._buf.pop(self._next)
                idx = self._next
                self._next += 1
                if item:
                    # See _flush_remaining() above for why this needs gen_lock.
                    with self._mgr._gen_lock:
                        if not self._stale():
                            self._mgr.put_item(self._priority, self._base_ts + idx * 0.001, item)
        if not self._buf:
            self._watchdog.cancel()


class TTSManager:
    _instance = None
    _lock = threading.Lock()
    _MAX_INFLIGHT = 4  # cap on sentences submitted to the executor at once per speak() batch
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TTSManager, cls).__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self):
        print("[TTS] Initializing Manager...", flush=True)
        self.queue = queue.PriorityQueue()
        self.stop_event = threading.Event()
        self.active_playback = False
        self._gen_count = 0
        self._gen_lock = threading.Lock()
        self.gen_epoch = 0  # bumped by stop() so in-flight generations from a
                             # cancelled answer know to discard their result
        # pycaw/comtypes COM objects are apartment-bound — even non-concurrent
        # use from a different thread than where they were created is unsafe.
        # stop() can be called from the recognition thread, not just the TTS
        # worker thread, so it only raises this flag; only the worker thread
        # itself ever actually calls force_unduck()/duck_volume().
        self._unduck_requested = threading.Event()
        self._last_items = {}
        self._last_items_lock = threading.Lock()
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=2)
        # ThreadPoolExecutor spawns its worker threads lazily on first submit(),
        # and a thread's stack size can't change after creation — so force both
        # workers to spawn right now, while the big stack is active, instead of
        # whenever the first real TTS request happens to arrive. A plain
        # submit() x2 doesn't *guarantee* 2 distinct threads (a fast first
        # worker can become idle again before the second submit() lands, so
        # the pool just reuses it) — a 2-party barrier forces both submitted
        # jobs to be in flight *simultaneously*, which only 2 real threads can
        # satisfy.
        with _stack_size_lock:
            _old_stack = threading.stack_size(_BIG_STACK_BYTES)
            try:
                _barrier = threading.Barrier(2, timeout=5)
                def _rendezvous():
                    # Lower OS priority of the inference worker so the audio
                    # playback thread wins CPU contention during generation
                    # spikes — underruns there are what cause audible crackle.
                    try:
                        import ctypes
                        THREAD_PRIORITY_BELOW_NORMAL = -1
                        ctypes.windll.kernel32.SetThreadPriority(
                            ctypes.windll.kernel32.GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL)
                    except Exception:
                        pass
                    try: _barrier.wait()
                    except Exception: pass
                futures = [self.executor.submit(_rendezvous) for _ in range(2)]
                for f in futures:
                    try: f.result(timeout=5)
                    except Exception: pass
            finally:
                threading.stack_size(_old_stack)
        print("[TTS] Starting Worker thread...", flush=True)
        self.worker_thread = _spawn_with_big_stack(self._worker, name='TTS-Worker')
        self.unload_timer = None
        try:
            from core.i18n import register_refresh
            register_refresh(self._on_language_change)
        except Exception:
            pass

    def _on_language_change(self):
        global _tts_models
        _tts_models.clear()
        invalidate_tts_caches()
        print("[TTS] Language changed, clearing model and speed cache.", flush=True)

    def _worker(self):
        pythoncom.CoInitialize()
        print("[TTS-WORKER] Thread started.", flush=True)
        try:
            from actions.volume import duck_volume, force_unduck
        except ImportError:
            duck_volume = lambda x: None
            force_unduck = lambda: None
        self.channel = None
        # Safety-net unduck retry, ~2s after idle cleanup, deliberately run on
        # THIS worker thread's own polling loop instead of a separate
        # threading.Timer thread. A second OS thread meant a second COM
        # apartment touching the same Windows Core Audio objects as
        # duck_volume() — that cross-thread race crashed combase.dll under
        # rapid-fire AI-streaming TTS even with locking around each call.
        _pending_unduck_retry: list[float | None] = [None]
        _is_ducked = False

        def _do_idle_cleanup():
            nonlocal _is_ducked
            if not _is_ducked:
                return
            _is_ducked = False
            try: force_unduck()
            except: pass
            _pending_unduck_retry[0] = time.time() + 2.0
            self._safe_hud_set_mode('idle')
            self.active_playback = False

        while True:
            try:
                # Handle any stop()-requested unduck here, on this thread's own
                # COM apartment, regardless of whether we're idle or about to
                # process a new item.
                if self._unduck_requested.is_set():
                    self._unduck_requested.clear()
                    try: force_unduck()
                    except: pass

                # Short timeout so idle detection is responsive
                try:
                    pri, ts, item = self.queue.get(timeout=0.05)
                except queue.Empty:
                    # Check if the channel finished playing and nothing is pending
                    ch_busy = False
                    with _mixer_lock:
                        try:
                            if pygame.mixer.get_init() and self.channel:
                                ch_busy = bool(self.channel.get_busy() or self.channel.get_queue() is not None)
                        except: pass
                    if not ch_busy and self._gen_count == 0 and self.queue.empty():
                        _do_idle_cleanup()
                    if _pending_unduck_retry[0] is not None and time.time() >= _pending_unduck_retry[0]:
                        _pending_unduck_retry[0] = None
                        try: force_unduck()
                        except: pass
                    continue

                if item is None: break

                now = time.time()
                print(f"[TTS-WORKER] [{now:.3f}] Processing: {item}", flush=True)
                self.active_playback = True
                self.stop_event.clear()

                # ---------------------------------------------------------------
                # Prepare audio file and acquire channel inside mixer lock
                # ---------------------------------------------------------------
                _sound = None
                _need_queue = False  # True when channel is busy → use channel.queue()
                with _mixer_lock:
                    try:
                        ensure_mixer_init()
                        self.active_playback = True

                        # Reuse the existing channel while it is still playing so that
                        # consecutive chunks go to channel.queue() rather than a second
                        # free channel (which would make two voices play simultaneously).
                        ch_occupied = (
                            self.channel is not None
                            and pygame.mixer.get_init()
                            and (self.channel.get_busy() or self.channel.get_queue() is not None)
                        )
                        if not ch_occupied:
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
                        _is_ducked = True
                        _pending_unduck_retry[0] = None  # cancel any stale retry from a previous idle cycle
                        audio_path = str(item)
                        if not os.path.exists(audio_path):
                            print(f"[TTS-WORKER] Generating audio for: {item[:20]}...", flush=True)
                            audio_path = _generate_cached(item)

                        if not audio_path or not os.path.exists(audio_path):
                            print(f"[TTS-WORKER] ERROR: Audio path invalid: {audio_path}", flush=True)
                            self.active_playback = False
                            self.queue.task_done()
                            continue

                        now_dt = datetime.now()
                        current_m = now_dt.hour * 60 + now_dt.minute
                        _n_start_h, _n_start_m, _n_end_h, _n_end_m, _night_vol = _get_night_vol_settings()
                        start_m = _n_start_h * 60 + _n_start_m
                        end_m = _n_end_h * 60 + _n_end_m
                        if start_m <= end_m:
                            is_night = (start_m <= current_m < end_m)
                        else:
                            is_night = (current_m >= start_m or current_m < end_m)
                        vol = _MASTER_VOLUME * _night_vol if is_night else _MASTER_VOLUME
                        if is_night:
                            vol = max(vol, min(_MASTER_VOLUME, 0.2))

                        self.channel.set_volume(vol)
                        self._safe_hud_set_mode('speaking')

                        now = time.time()
                        print(f"[TTS-WORKER] [{now:.3f}] Playing: {audio_path}", flush=True)
                        try:
                            _sound = pygame.mixer.Sound(audio_path)
                        except Exception as e:
                            print(f"[TTS-WORKER] Sound creation error: {e}", flush=True)
                            if "device hasn't been opened" in str(e).lower():
                                try: pygame.mixer.quit()
                                except: pass
                            self.active_playback = False
                            self.queue.task_done()
                            continue

                        if self.channel.get_busy():
                            _need_queue = True  # Queue after releasing lock
                        else:
                            self.channel.play(_sound)

                    except Exception as e:
                        err_str = str(e)
                        print(f"TTS-WORKER: EXCEPTION inside lock: {err_str}", flush=True)
                        if "Audio device hasn't been opened" in err_str or "not initialized" in err_str:
                            try: pygame.mixer.quit()
                            except: pass
                        self.active_playback = False
                        self.queue.task_done()
                        continue

                # ---------------------------------------------------------------
                # Seamless queuing: wait for channel queue slot, then hand off
                # ---------------------------------------------------------------
                if _need_queue and _sound is not None:
                    while not self.stop_event.is_set():
                        with _mixer_lock:
                            if not pygame.mixer.get_init(): break
                            ch = self.channel
                            if ch is None: break
                            if ch.get_queue() is None:
                                if ch.get_busy():
                                    ch.queue(_sound)
                                else:
                                    ch.play(_sound)
                                break
                        time.sleep(0.005)

                # Mark done immediately — worker fetches next item without waiting
                # for current sound to finish.  Idle detection happens in the
                # queue.Empty branch above once the channel goes silent.
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
        # Chunk on the calling thread (cheap, just regex splitting) but defer
        # normalize_for_tts() to the executor pool (see _gen_sentence). The
        # calling thread is often itself a streaming/UI-updating thread (e.g.
        # the AI-answer streaming loop) — normalize_for_tts() can cold-start
        # pymorphy3's MorphAnalyzer (1-3s) or block on _morph_lock if another
        # thread is mid-load, which used to freeze that caller's whole loop
        # (text AND speech) on the very first AI answer of a session.
        text = text.strip()
        if not text: return
        self.active_playback = True
        self.stop_event.clear()
        sentences = _chunk_text(text)
        if not sentences:
            self.active_playback = False
            return
        with self._gen_lock: self._gen_count += len(sentences)
        batch = _OrderedBatch(priority, time.time(), self, self.gen_epoch)
        indexed = list(enumerate(sentences))
        batch._pending = indexed[self._MAX_INFLIGHT:]
        for i, s in indexed[:self._MAX_INFLIGHT]:
            self.executor.submit(self._gen_sentence, s, i, batch)
        self._reset_unload_timer()
        if wait: self.wait_until_finished()

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
            if last_ts and (now - last_ts < 0.8):
                print(f"[TTS] Skipped duplicate item within 0.8s: {item}", flush=True)
                return
            self._last_items[item] = now
        self.queue.put((priority, ts, item))
        self.active_playback = True # Signal active immediately

    def _gen_sentence(self, text: str, index: int, batch: _OrderedBatch) -> None:
        try:
            text = normalize_for_tts(text).strip()
            if not text:
                batch.finished(index, None)
                return
            speed_pct = int(round(_get_tts_speed() * 100))
            path = _generate_cached(text, speed_pct)
            batch.finished(index, path)
        finally:
            # _gen_count was already incremented for every sentence in the
            # batch up front (in speak()), including ones still sitting in
            # _pending — only decrement here, don't re-add when resubmitting
            # the next pending one below, or _gen_count never reaches 0 for
            # batches bigger than _MAX_INFLIGHT and the HUD stays stuck on
            # "speaking" forever (idle cleanup gates on _gen_count == 0).
            with self._gen_lock:
                self._gen_count = max(0, self._gen_count - 1)
            nxt = batch._pop_pending()
            if nxt is not None:
                next_idx, next_text = nxt
                self.executor.submit(self._gen_sentence, next_text, next_idx, batch)

    def stop(self):
        self.stop_event.set()
        cleared = 0
        # gen_epoch bump and the queue drain share gen_lock with
        # _OrderedBatch.finished()/_flush_remaining()'s stale-check + put_item,
        # so a batch from just before this stop() can't slip an item into the
        # queue after the drain loop below has already finished (see the
        # comment in _OrderedBatch._flush_remaining() for the failure mode).
        with self._gen_lock:
            self.gen_epoch += 1  # any batch created before this point is now stale
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                    self.queue.task_done()
                    cleared += 1
                except queue.Empty: break
        if cleared:
            print(f"[TTS] Stopped: cleared {cleared} items from queue", flush=True)
        with _mixer_lock:
            try:
                if self.channel:
                    self.channel.stop()
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
            except Exception: pass
        # Don't touch pycaw/COM from this (caller's) thread — just flag it for
        # the TTS worker thread to handle on its own apartment. See
        # _unduck_requested above for why.
        self._unduck_requested.set()
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
        with TTSManager._lock:
            if self.unload_timer:
                self.unload_timer.cancel()
                self.unload_timer = None

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
        global _tts_models, _warmup_started

        # Prevent unloading in Game Mode
        from core.system import app_state as _as
        if getattr(_as, 'game_mode', False):
            print("[TTS] Skipping unload: Game Mode active.", flush=True)
            self._reset_unload_timer() # Check again later
            return

        with TTSManager._lock:
            if _tts_models:
                print("[TTS] Unloading model to free memory...", flush=True)
                _tts_models.clear()
                # Allow warmup_tts() to reload on next AI query
                with _warmup_lock:
                    _warmup_started = False
                gc.collect()
                try:
                    from core.system.bootstrap import trim_memory
                    trim_memory()
                except Exception:
                    pass
def _get_tts():
    lang = _get_lang()
    if lang in _tts_models: return _tts_models[lang]
    with TTSManager._lock:
        if lang in _tts_models: return _tts_models[lang]
        import torch
        _ensure_model(lang)
        phys = psutil.cpu_count(logical=False) or 2
        # Give Silero enough intra-op threads to finish generation before playback ends.
        # 1 thread was the original conservative setting but causes 15-20s generation
        # times on 4-core CPUs, producing audible gaps between TTS chunks.
        torch_threads = min(phys, max(2, phys // 2))
        torch.set_num_threads(torch_threads)
        # Inference-only: no backward pass ever happens, so disable the JIT
        # profiling executor to avoid it caching per-shape execution graphs.
        try:
            torch._C._jit_set_profiling_mode(False)
        except Exception:
            pass
        try:
            torch.set_num_interop_threads(max(1, phys // 4))
        except Exception:
            pass
        # Evict any other language model before loading new one — keep only 1 in RAM
        if _tts_models:
            _tts_models.clear()
            gc.collect()
        model_file = _get_model_file(lang)
        model = torch.package.PackageImporter(model_file).load_pickle('tts_models', 'model')
        model.to(torch.device('cpu'))
        _tts_models[lang] = model
        return model
_MODEL_MIN_BYTES = 30 * 1024 * 1024  # Silero models are >30 MB; smaller = corrupt download

def _ensure_model(lang: str = None) -> None:
    if lang is None:
        lang = _get_lang()
    model_file = _get_model_file(lang)

    # Validate existing file — delete if suspiciously small (interrupted download).
    if os.path.exists(model_file):
        if os.path.getsize(model_file) >= _MODEL_MIN_BYTES:
            return
        print(f'[TTS] Model file {model_file} is too small — re-downloading.', flush=True)
        os.remove(model_file)

    import torch
    os.makedirs(_MODEL_DIR, exist_ok=True)
    tmp_file = model_file + '.tmp'
    try:
        torch.hub.download_url_to_file(_get_model_url(lang), tmp_file)
        if not os.path.exists(tmp_file):
            raise RuntimeError('Download produced no output file')
        if os.path.getsize(tmp_file) < _MODEL_MIN_BYTES:
            os.remove(tmp_file)
            raise RuntimeError(
                f'Downloaded model is too small ({os.path.getsize(tmp_file) if os.path.exists(tmp_file) else 0} bytes) — likely a corrupt or incomplete download'
            )
        os.replace(tmp_file, model_file)
        print(f'[TTS] Model {lang} downloaded OK ({os.path.getsize(model_file) // 1024 // 1024} MB).', flush=True)
    except Exception:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        raise
def _generate_cached(text: str, _speed_pct: int = 100) -> str | None:
    global _silero_supports_speech_rate
    speed = _speed_pct / 100.0
    lang = _get_lang()
    speaker = _get_speaker(lang)
    # Cache key includes speed so each rate has its own file
    cache_key = f'{text}|{speaker}|{lang}|{_SAMPLE_RATE}|{_speed_pct}'
    h = hashlib.md5(cache_key.encode('utf-8')).hexdigest()[:12]
    path = os.path.join(CACHE_DIR, f'silero_{h}.wav')
    if not os.path.exists(path):
        try:
            model = _get_tts()
            tmp_path = path + '.tmp'
            want_native_speed = abs(speed - 1.0) >= 0.02 and _silero_supports_speech_rate is not False
            import torch
            with _tts_inference_lock, torch.inference_mode():
                if want_native_speed:
                    try:
                        model.save_wav(text=text, speaker=speaker, sample_rate=_SAMPLE_RATE, audio_path=tmp_path, speech_rate=speed)
                        _silero_supports_speech_rate = True
                    except TypeError:
                        _silero_supports_speech_rate = False
                        model.save_wav(text=text, speaker=speaker, sample_rate=_SAMPLE_RATE, audio_path=tmp_path)
                else:
                    model.save_wav(text=text, speaker=speaker, sample_rate=_SAMPLE_RATE, audio_path=tmp_path)
            if os.path.exists(tmp_path):
                os.replace(tmp_path, path)
        except Exception as e:
            print(f"TTS-GENERATOR: Error generating audio for '{text[:30]}...': {e}")
            import traceback
            traceback.print_exc()
            return None
    if not os.path.exists(path):
        return None
    # Framerate fallback when Silero doesn't support speech_rate (changes pitch slightly)
    if _silero_supports_speech_rate is False and abs(speed - 1.0) >= 0.02:
        return _apply_wav_speed(path, speed)
    return path
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




def _get_audio_device_name() -> str | None:
    """Read audio device from settings once and cache. Reset by apply_audio_devices()."""
    global _cached_audio_device, _cached_audio_device_loaded
    if _cached_audio_device_loaded:
        return _cached_audio_device
    try:
        from config_pack.config import get_settings_path
        p = get_settings_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if isinstance(d, dict):
                    dev = d.get('audio_output_device_name')
                    _cached_audio_device = dev if (isinstance(dev, str) and dev.strip()) else None
    except Exception:
        _cached_audio_device = None
    _cached_audio_device_loaded = True
    return _cached_audio_device

def ensure_mixer_init() -> None:
    with _mixer_lock:
        try:
            # Fast path: if already initialized, just ensure channels are set
            init_data = pygame.mixer.get_init()
            if init_data:
                try:
                    pygame.mixer.set_num_channels(24)
                    return
                except Exception:
                    # Device might be "init" but not actually open
                    try: pygame.mixer.quit()
                    except: pass
            
            def _try_init(dname=None, freq=48000):
                try:
                    # buffer=4096 (~85ms @ 48kHz) avoids underrun crackle while
                    # Silero inference competes for CPU with the audio thread.
                    pygame.mixer.init(frequency=freq, devicename=dname, buffer=4096)
                    pygame.mixer.set_num_channels(24)
                    return True
                except Exception:
                    try: pygame.mixer.quit()
                    except: pass
                    return False

            # NOTE: deliberately not resolving/passing the user's configured output
            # device here. Doing so previously called _resolve_sdl_device_name(),
            # which talks to SDL2 directly via ctypes — racing with pygame's own
            # SDL audio subsystem on this hot reinit path crashed the process
            # (0xC0000005) immediately on the very first chunk. The configured
            # device is still applied correctly via apply_audio_devices(), which
            # does a single controlled quit+reinit instead of this fast path.
            success = False
            if _try_init(None, 48000): success = True
            elif _try_init(None, 44100): success = True
            
            if not success:
                print("[TTS] CRITICAL: All mixer init attempts failed.", flush=True)

        except Exception as e: 
            print(f"[TTS] ensure_mixer_init crash: {e}", flush=True)

def apply_audio_devices(output_device_name: str | None = None, input_device_index: int | None = None) -> tuple[bool, str]:
    # Reset device cache so next ensure_mixer_init() picks up the new device
    global _cached_audio_device, _cached_audio_device_loaded
    _cached_audio_device = None
    _cached_audio_device_loaded = False
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
                        pygame.mixer.init(frequency=_SAMPLE_RATE, devicename=dname, buffer=4096)
                    else:
                        pygame.mixer.init(frequency=_SAMPLE_RATE, buffer=4096)
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
# ---------------------------------------------------------------------------
# Stress-mark dictionary for Silero v5.
# Format: 'word_lowercase' → 'wо+rd'  where + precedes the stressed vowel.
# Applied case-insensitively; original capitalisation is preserved.
# Add any proper noun or word the model mis-stresses here.
# ---------------------------------------------------------------------------
_STRESS_MAP: dict[str, str] = {
    # Assistant name — stress on А (ДжА́рвис, not ДжарвИ́с)
    'джарвис':  'Дж+арвис',
    'джарвіс':  'Дж+арвіс',
    # Common words that Silero v5 sometimes mis-stresses
    'интерфейс':    'интерф+ейс',
    'центр':        'ц+ентр',
    'включить':     'включ+ить',
    'включи':       'включ+и',
    'включите':     'включ+ите',
    'открыть':      'откр+ыть',
    'открой':       'откр+ой',
    'закрой':       'закр+ой',
    'закрыть':      'закр+ыть',
    'запусти':      'запуст+и',
    'запустить':    'запуст+ить',
    'перезапусти':  'перезапуст+и',
    'выключи':      'выключ+и',
    'выключить':    'выключ+ить',
    'скачать':      'скач+ать',
    'скачай':       'скач+ай',
    'найди':        'найд+и',
    'поищи':        'поищ+и',
    'покажи':       'покаж+и',
    'сорок':        'с+орок',
    # Ukrainian
    'джарвіс':      'Дж+арвіс',
    'інтерфейс':    'інтерф+ейс',
    'увімкни':      'увімкн+и',
    'увімкнути':    'увімкн+ути',
    'вимкни':       'вимкн+и',
    'вимкнути':     'вимкн+ути',
    'відкрий':      'відкр+ий',
    'відкрити':     'відкр+ити',
    'закрий':       'закр+ий',
    'закрити':      'закр+ити',
    'запустити':    'запуст+ити',
    'знайди':       'знайд+и',
    'покажи':       'покаж+и',
    'скачати':      'скач+ати',
}

# Precompile pattern — whole-word, case-insensitive
_STRESS_PAT = re.compile(
    r'\b(' + '|'.join(re.escape(w) for w in _STRESS_MAP) + r')\b',
    re.IGNORECASE,
)

def _apply_stress(text: str) -> str:
    """Replace known mis-stressed words with stress-marked variants."""
    def _repl(m: re.Match) -> str:
        word = m.group(0)
        key  = word.lower()
        replacement = _STRESS_MAP.get(key, word)
        # Preserve original capitalisation (first letter)
        if word[0].isupper() and not replacement[0].isupper():
            replacement = replacement[0].upper() + replacement[1:]
        return replacement
    return _STRESS_PAT.sub(_repl, text)


def normalize_for_tts(text: str) -> str:
    if not text:
        return ''
    lang = _get_lang()
    key = (text, lang)
    with _normalize_cache_lock:
        cached = _normalize_cache.get(key)
        if cached is not None:
            _normalize_cache.move_to_end(key)
            return cached
    text = _apply_stress(text)
    # Convert phrase pause markers to sentence boundaries so Silero pauses naturally
    text = re.sub(r'\s+\.\.\.\s+', '. ', text)
    if not hasattr(normalize_for_tts, '_nlp_cache'):
        from core.nlp import format_time_russian, get_russian_plural
        from num2words import num2words
        normalize_for_tts._nlp_cache = (format_time_russian, get_russian_plural, num2words)
    format_time_russian, get_russian_plural, num2words = normalize_for_tts._nlp_cache
    text = re.sub(r'\b([A-Za-z]):\\', lambda m: f'диск {_PHONETIC_DRIVES.get(m.group(1).upper(), m.group(1).upper())} ', text)
    nw_lang = 'uk' if lang == 'uk' else 'ru'
    _km_word = 'кілометрів' if lang == 'uk' else 'километров'
    _all_units = {**_UNIT_EXPANSIONS, 'км': _km_word}
    text = re.sub(r'\b(ГБ|МБ|КБ|км/ч|км/час|кг|см|мм|км)\b', lambda m: _all_units.get(m.group(0).lower(), m.group(0)), text, flags=re.IGNORECASE)
    text = text.replace('€', 'євро' if lang == 'uk' else 'евро')

    # --- Minus sign: -5 → минус 5 (before any number conversion) ---
    _minus = 'мінус ' if nw_lang == 'uk' else 'минус '
    text = re.sub(r'(?<!\d)(?<!\w)-(\d)', lambda m: _minus + m.group(1), text)

    # --- Degree symbols: 20°C, -5°, 20° → spoken form with proper pluralization ---
    def _degree_repl(m: re.Match) -> str:
        n = int(m.group(1))
        abs_n = abs(n)
        sign = _minus if n < 0 else ''
        last2, last1 = abs_n % 100, abs_n % 10
        if 11 <= last2 <= 19:   form = 'градусів' if nw_lang == 'uk' else 'градусов'
        elif last1 == 1:         form = 'градус'
        elif 2 <= last1 <= 4:   form = 'градуси' if nw_lang == 'uk' else 'градуса'
        else:                    form = 'градусів' if nw_lang == 'uk' else 'градусов'
        return f"{sign}{abs_n} {form}"
    text = re.sub(r'(-?\d+)\s*°[CcFfСс]?', _degree_repl, text)

    # --- Percentages ---
    def _uk_pct_word(n: int) -> str:
        last2, last1 = n % 100, n % 10
        if 11 <= last2 <= 19: return 'відсотків'
        if last1 == 1: return 'відсоток'
        if 2 <= last1 <= 4: return 'відсотки'
        return 'відсотків'
    if lang == 'uk':
        text = re.sub(r'(\d+)\s*%', lambda m: f"{num2words(int(m.group(1)), lang='uk')} {_uk_pct_word(int(m.group(1)))}", text)
    else:
        text = re.sub(r'(\d+)\s*%', lambda m: f"{num2words(int(m.group(1)), lang='ru')} {get_russian_plural(int(m.group(1)), ['процент', 'процента', 'процентов'])}", text)

    # --- Ordinal case helpers (pymorphy3-powered) ---
    morph = _get_morph(nw_lang)
    _CASE_TAG = {'gen': 'gent', 'prep': 'loct', 'nom': 'nomn', 'dat': 'datv', 'acc': 'accs'}

    def _inflect_last(phrase: str, tags: set) -> str:
        """Inflect the last word of a phrase to given morphological tags."""
        if morph is None: return phrase
        words = phrase.strip().split()
        if not words: return phrase
        last = words[-1]
        parses = morph.parse(last)
        # Build fallback tag sets: try most-specific first, then relax constraints
        tag_variants = []
        for drop in (set(), {'sing'}, {'masc','femn','neut'}, {'masc','femn','neut','sing'}):
            t = tags - drop
            if t and t not in tag_variants:
                tag_variants.append(t)
        for strict in (True, False):
            for p in parses:
                ts = str(p.tag)
                if strict and 'Anum' not in ts and 'ADJF' not in ts:
                    continue
                for tv in tag_variants:
                    infl = p.inflect(tv)
                    if infl:
                        return (' '.join(words[:-1]) + ' ' + infl.word).strip()
        return phrase

    def _ordinal_case(phrase: str, case: str, gender: str = 'masc') -> str:
        """Inflect ordinal phrase to requested case and gender."""
        if case == 'nom': return phrase
        ct = _CASE_TAG.get(case, 'gent')
        # Ukrainian loct: prefer dative form — same meaning, more common than archaic '-ім'
        if nw_lang == 'uk' and ct == 'loct':
            r = _inflect_last(phrase, {'datv', gender, 'sing'})
            if r != phrase: return r
        return _inflect_last(phrase, {ct, gender, 'sing'})

    # --- Year patterns ---
    _YEAR_PAT = r'\b(?P<y1>19\d{2}|20\d{2})'
    if lang == 'uk':
        # Ukrainian: рік (nom), року (gen/date), році (prep), -го, -му, -й
        def _year_uk(m: re.Match) -> str:
            try:
                y = int(m.group('year'))
                suf = (m.group('suf') or '').strip().rstrip('.').lower()
                ordy = num2words(y, lang='uk', to='ordinal')
                if suf in ('року', 'р'):    return _ordinal_case(ordy, 'gen') + ' року'
                if suf == 'році':           return _ordinal_case(ordy, 'prep') + ' році'
                if suf in ('рік', 'р.'):    return ordy + ' рік'
                if suf == '-го':            return _ordinal_case(ordy, 'gen')
                if suf in ('-му', '-м'):    return _ordinal_case(ordy, 'prep')
                return num2words(y, lang='uk')
            except Exception: return m.group(0)
        text = re.sub(
            r'\b(?P<year>19\d{2}|20\d{2})\s*(?P<suf>року|році|рік|р\.|р\b|-го|-му|-м\b)',
            _year_uk, text, flags=re.IGNORECASE)
        # Standalone years in Ukrainian year range "2020-2023" → cardinal both
        text = re.sub(
            r'\b(19\d{2}|20\d{2})\s*[-–]\s*(19\d{2}|20\d{2})\b',
            lambda m: f"{num2words(int(m.group(1)), lang='uk')} — {num2words(int(m.group(2)), lang='uk')}",
            text)
    else:
        # Russian: год (nom), года (gen), году (prep), -го, -м, -й
        def _year_ru(m: re.Match) -> str:
            try:
                y = int(m.group('year'))
                suf = (m.group('suf') or '').strip().rstrip('.').lower()
                ordy = num2words(y, lang='ru', to='ordinal')
                if suf == 'года':           return _ordinal_case(ordy, 'gen') + ' года'
                if suf == 'году':           return _ordinal_case(ordy, 'prep') + ' году'
                if suf in ('год', 'г'):     return ordy + ' год'
                if suf in ('-го', 'го'):    return _ordinal_case(ordy, 'gen')
                if suf in ('-м', 'м', '-й'): return _ordinal_case(ordy, 'prep')
                return num2words(y, lang='ru')
            except Exception: return m.group(0)
        text = re.sub(
            r'\b(?P<year>19\d{2}|20\d{2})\s*(?P<suf>года\b|году\b|год\b|г\.|г\b|-го\b|(?<!\w)го\b|-м\b|-й\b)',
            _year_ru, text, flags=re.IGNORECASE)
        # Year range "2020-2023"
        text = re.sub(
            r'\b(19\d{2}|20\d{2})\s*[-–]\s*(19\d{2}|20\d{2})\b',
            lambda m: f"{num2words(int(m.group(1)), lang='ru')} — {num2words(int(m.group(2)), lang='ru')}",
            text)

    # --- Dates (day + month) ---
    if lang == 'uk':
        text = re.sub(
            r'\b(\d{1,2})\s+(січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\b',
            lambda m: _ordinal_case(num2words(int(m.group(1)), lang='uk', to='ordinal'), 'gen') + ' ' + m.group(2),
            text, flags=re.IGNORECASE)
    else:
        text = re.sub(
            r'\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\b',
            lambda m: _ordinal_case(num2words(int(m.group(1)), lang='ru', to='ordinal'), 'gen') + ' ' + m.group(2),
            text, flags=re.IGNORECASE)

    # --- Ordinal shorthand: 1-й, 2-й, 3-го, 2-му etc. ---
    # Optional capture of following Cyrillic word for gender/case agreement
    def _ordinal_short(m: re.Match) -> str:
        try:
            n = int(m.group(1))
            suf = m.group(2).lower().lstrip('-')
            following_ws = m.group(3) or ''
            following = following_ws.strip()
            ordy = num2words(n, lang=nw_lang, to='ordinal')
            if suf in ('го', 'ого', 'його', 'его'):
                return _ordinal_case(ordy, 'gen') + following_ws
            if suf in ('м', 'ом', 'ем', 'му', 'ому'):
                return _ordinal_case(ordy, 'prep') + following_ws
            # Ambiguous suffix (-й/-ій/-я/-е/-є): agree with following noun
            if following and morph is not None:
                parses = morph.parse(following.lower())
                if parses:
                    cmap = {'nomn': 'nom', 'gent': 'gen', 'datv': 'dat',
                            'accs': 'acc', 'ablt': 'prep', 'loct': 'prep'}
                    # Prefer loct > datv > gent > ablt over nomn/accs (ordinals
                    # before nouns are usually in oblique context, not nom-plural)
                    _OBLIQUE_PREF = ('loct', 'datv', 'gent', 'ablt')
                    best = next(
                        (p for pref in _OBLIQUE_PREF
                         for p in parses if str(p.tag.case) == pref),
                        parses[0]
                    )
                    gender = str(best.tag.gender) if best.tag.gender else 'masc'
                    case = cmap.get(str(best.tag.case) if best.tag.case else 'nomn', 'nom')
                    return _ordinal_case(ordy, case, gender) + following_ws
            return ordy + following_ws
        except Exception:
            return m.group(0)
    text = re.sub(
        r'\b(\d+)(-?(?:й|ій|я|є|е|го|ого|його|его|му|ому|м|ом|ем))(\s+[А-Яа-яЁёІіЇїЄє]+)?',
        _ordinal_short, text, flags=re.IGNORECASE)

    # --- Year ranges without suffix: "с 1939 по 1945" / "від 1939 до 1945" ---
    _prep_start = r'(?:с|от|із|з|від|за)\s+'
    _prep_end   = r'\s+(?:по|до|—|-)\s+'
    def _year_range_repl(m: re.Match) -> str:
        try:
            y = int(m.group('ry'))
            return m.group('pre') + _ordinal_case(num2words(y, lang=nw_lang, to='ordinal'), 'gen') + m.group('sep')
        except Exception: return m.group(0)
    text = re.sub(
        r'(?P<pre>' + _prep_start + r')(?P<ry>19\d{2}|20\d{2})(?P<sep>' + _prep_end + r')',
        _year_range_repl, text, flags=re.IGNORECASE)

    # --- Number-noun agreement: fix "5 метр" → "5 метров" etc. using pymorphy3 ---
    if morph is not None:
        def _fix_noun(m: re.Match) -> str:
            try:
                n = int(m.group(1))
                noun = m.group(2)
                parses = morph.parse(noun.lower())
                noun_p = next((p for p in parses if 'NOUN' in str(p.tag)), None)
                if noun_p is None: return m.group(0)
                abs_n = abs(n)
                last2, last1 = abs_n % 100, abs_n % 10
                if 11 <= last2 <= 19:   req = ('gent', 'plur')
                elif last1 == 1:         req = ('nomn', 'sing')
                elif 2 <= last1 <= 4:   req = ('gent', 'sing')
                else:                    req = ('gent', 'plur')
                cur_case = str(noun_p.tag.case) if noun_p.tag.case else ''
                cur_num  = str(noun_p.tag.number) if noun_p.tag.number else ''
                if cur_case == req[0] and cur_num == req[1]:
                    return m.group(0)  # already correct
                infl = noun_p.inflect({req[0], req[1]})
                if infl:
                    return m.group(1) + ' ' + infl.word
            except Exception:
                pass
            return m.group(0)
        text = re.sub(r'\b(\d+)\s+([А-Яа-яЁёІіЇїЄє]{3,})\b', _fix_noun, text)

    # --- Abbreviations and transliteration ---
    text = re.sub(r'(?<![А-ЯЁа-яёa-zA-Z])[А-ЯЁ]{2,6}(?![А-ЯЁа-яёa-zA-Z])', lambda m: _CYR_ABBREV.get(m.group(0), ' '.join((_CYR_LETTERS.get(c, c) for c in m.group(0)))), text)
    text = re.sub(r"[a-zA-Z]+(?:['-][a-zA-Z]+)*", _transliterate_word, text)

    # --- Remaining standalone numbers ---
    text = re.sub(r'(?<!\w)(\d+)(?!\w)', lambda m: num2words(int(m.group(1)), lang=nw_lang), text)

    # --- Replace hardcoded "сэр"/"сер" with the user-configured address form ---
    try:
        from core.address import get_address as _ga
        _addr_value = _ga()
        if _addr_value.lower() not in ('сэр', 'сер'):
            text = re.sub(r'\bсэр\b', _addr_value, text, flags=re.IGNORECASE)
            text = re.sub(r'\bсер\b', _addr_value, text, flags=re.IGNORECASE)
    except Exception:
        pass

    # --- Comma after address form (Сэр/Джарвис/Леди/custom) for TTS prosody ---
    try:
        from core.address import get_address as _ga
        _addr_esc = re.escape(_ga())
        _cyr = r'[а-яёА-ЯЁіїєІЇЄ]'
        text = re.sub(rf'^({_addr_esc})\s+({_cyr})', r'\1, \2', text, flags=re.IGNORECASE)
        text = re.sub(rf'([.!?])\s+({_addr_esc})\s+({_cyr})', r'\1 \2, \3', text, flags=re.IGNORECASE)
    except Exception:
        pass

    result = text.strip()
    with _normalize_cache_lock:
        _normalize_cache[key] = result
        _normalize_cache.move_to_end(key)
        while len(_normalize_cache) > _NORMALIZE_CACHE_MAX:
            _normalize_cache.popitem(last=False)  # evict oldest, not everything
    return result
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
    """Enqueue text for TTS and return a daemon Thread that exits when playback finishes.

    Callers that don't need to synchronise can ignore the return value — the
    text will play regardless.  Callers that need to wait can call .join()
    (with an optional timeout) on the returned thread.

    Example::
        t = speak_async("Готово.")
        do_other_work()
        t.join(timeout=10)   # wait up to 10 s for TTS to finish
    """
    t = threading.Thread(
        target=lambda: speak(text, wait=True),
        daemon=True,
        name='TTS-async',
    )
    t.start()
    return t

def stop_speaking() -> None:
    TTSManager().stop()

def invalidate_tts_caches() -> None:
    """Call after changing language, address name, or TTS speed in settings."""
    invalidate_tts_speed_cache()
    _invalidate_night_vol_cache()
    with _normalize_cache_lock:
        _normalize_cache.clear()
def warmup_text_models() -> None:
    """Pre-load pymorphy3/g2p_en dictionaries. Pure-Python, no GPU/audio
    contact, so unlike warmup_tts() this is safe to call immediately at
    process start instead of waiting for the audio engine to be ready."""
    global _text_warmup_started
    with _text_warmup_lock:
        if _text_warmup_started:
            return
        _text_warmup_started = True

    def _warm_morph():
        # pymorphy3's MorphAnalyzer takes 1-3s to load its dictionaries on first
        # use. Previously this only happened as a side effect of normalize_for_tts()
        # inside _warm() above, queued AFTER Silero model loading — if the user
        # spoke before that point was reached, the cold load blocked their first
        # real request instead. Load it in parallel, right away, on its own thread.
        try:
            _get_morph(_get_lang())
        except Exception as e:
            print(f"TTS-WARMUP: Morph preload failed: {e}")

    def _warm_g2p():
        # g2p_en.G2p() (used to transliterate Latin words like "Tesla"/"SpaceX"
        # into Cyrillic phonetics) loads NLTK data on first use — another cold
        # start that otherwise hits whichever response first mentions a Latin
        # proper noun, regardless of how many sessions-old the model warmup is.
        try:
            _g2p_word('test')
        except Exception as e:
            print(f"TTS-WARMUP: G2p preload failed: {e}")

    threading.Thread(target=_warm_morph, daemon=True, name='TTS-WarmupMorph').start()
    threading.Thread(target=_warm_g2p, daemon=True, name='TTS-WarmupG2p').start()
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
            lang = _get_lang()
            _ensure_model(lang)
            _generate_cached('Прогрев системы.' if lang == 'ru' else 'Прогрів системи.')
            phrases = {
                'ru': ['Слушаю.', 'Принято.', 'Дайте нормальный запрос.', 'Начнём заново?', 'Я всё помню.', 'По делу?'],
                'uk': ["Слухаю.", "Прийнято.", "Дайте нормальний запит.", "Почнемо спочатку?", "Я все пам'ятаю.", "По справі?"],
            }
            for p in phrases.get(lang, phrases['ru']):
                _generate_cached(normalize_for_tts(p))
        except Exception as e:
            print(f"TTS-WARMUP: Failed: {e}")

    # _warm runs real Silero inference (model load + save_wav) — needs the big
    # stack. Text-model warmup (pymorphy3/g2p_en) is pure-Python, no deep
    # PyTorch recursion — started separately via warmup_text_models() so it
    # doesn't have to wait for the audio engine to be ready.
    _spawn_with_big_stack(_warm, name='TTS-WarmupModel')
    warmup_text_models()
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
    return is_speaking()
