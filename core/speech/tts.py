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
_UNLOAD_AFTER_SEC = 15 * 60.0
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_SPLIT_THRESHOLD = 180
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
        self.model = None
        self.queue = queue.PriorityQueue()
        self.stop_event = threading.Event()
        self.active_playback = False
        self._gen_count = 0
        self._gen_lock = threading.Lock()
        self._last_items = {}
        self._last_items_lock = threading.Lock()
        from concurrent.futures import ThreadPoolExecutor
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.unload_timer = None
    def _worker(self):
        pythoncom.CoInitialize()
        try:
            from actions.volume import duck_volume, force_unduck
        except ImportError:
            duck_volume = lambda x: None
            force_unduck = lambda: None
        self.channel = None
        _unduck_timer = {'id': None}
        while True:
            try:
                pri, ts, item = self.queue.get(timeout=0.5)
                if item is None: break
                self.active_playback = True
                self.stop_event.clear()
                try:
                    ensure_mixer_init()
                    if self.channel is None:
                        self.channel = pygame.mixer.Channel(7)
                    duck_volume(True)
                    audio_path = str(item)
                    if not os.path.exists(audio_path):
                        audio_path = _generate_cached(item)
                    if not audio_path:
                        continue
                    h = datetime.now().hour
                    is_night = (h >= 22 or h < 7)
                    vol = _MASTER_VOLUME * 0.7 if is_night else _MASTER_VOLUME
                    if is_night: vol = max(vol, min(_MASTER_VOLUME, 0.2))
                    self.channel.set_volume(vol)
                    try:
                        from ui import hud as _hud
                        if _hud.STATE: _hud.STATE.mode = _hud.HudState.SPEAKING
                    except Exception: pass
                    sound = pygame.mixer.Sound(audio_path)
                    if self.channel.get_busy():
                        while self.channel.get_queue() is not None and not self.stop_event.is_set():
                            time.sleep(0.01)
                        if not self.stop_event.is_set():
                            self.channel.queue(sound)
                    else:
                        self.channel.play(sound)
                    self.active_playback = True
                    while self.channel.get_busy() and self.channel.get_queue() is not None and not self.stop_event.is_set():
                        time.sleep(0.05)
                    if self.queue.empty() and self._gen_count == 0:
                        while self.channel.get_busy() and not self.stop_event.is_set():
                            time.sleep(0.05)
                except Exception as e:
                        print(f"TTS-WORKER: EXCEPTION: {e}")
                finally:
                    if self.queue.empty() and self._gen_count == 0:
                        try:
                            force_unduck()
                        except Exception:
                            pass
                        try:
                            if _unduck_timer['id'] is not None:
                                _unduck_timer['id'].cancel()
                        except Exception:
                            pass
                        try:
                            _unduck_timer['id'] = threading.Timer(2.0, lambda: (force_unduck(),))
                            _unduck_timer['id'].daemon = True
                            _unduck_timer['id'].start()
                        except Exception:
                            pass
                        try:
                            from ui import hud as _hud
                            if _hud.STATE: _hud.STATE.mode = _hud.HudState.IDLE
                        except Exception: pass
                        self.active_playback = False
                    self.queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                pass
    def wait_until_finished(self, timeout: float = 30.0):
        start = time.time()
        while (not self.queue.empty() or self.active_playback) and (time.time() - start < timeout):
            time.sleep(0.05)
    def speak(self, text: str, priority: int = 10, wait: bool = False):
        text = normalize_for_tts(text).strip()
        if not text: return
        wait_for_pygame_mixer_idle(timeout=90.0)
        self.active_playback = True
        self.stop_event.clear()
        sentences = _SENTENCE_SPLIT_RE.split(text) if len(text) > _SPLIT_THRESHOLD else [text]
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            self.active_playback = False
            return
        with self._gen_lock:
            self._gen_count += len(sentences)
        base_ts = time.time()
        for i, s in enumerate(sentences):
            self.executor.submit(self._queue_sentence, s, priority, base_ts + i * 0.001)
        self._reset_unload_timer()
        if wait:
            time.sleep(0.3)
            self.wait_until_finished()
        else:
            time.sleep(0.05)
    def put_item(self, priority: int, ts: float, item: str):
        try:
            if isinstance(item, str) and item.lower().endswith('.wav'):
                wait_for_pygame_mixer_idle(timeout=60.0)
        except Exception:
            pass
        if not hasattr(self, '_last_items_lock'):
            with self._lock:
                if not hasattr(self, '_last_items_lock'):
                    self._last_items = {}
                    self._last_items_lock = threading.Lock()
        now = time.time()
        with self._last_items_lock:
            self._last_items = {k: v for k, v in self._last_items.items() if now - v < 5.0}
            last_ts = self._last_items.get(item)
            if last_ts and (now - last_ts < 2.0):
                return
            self._last_items[item] = now
        self.queue.put((priority, ts, item))
    def _queue_sentence(self, text: str, priority: int, ts: float):
        try:
            path = _generate_cached(text)
            if path:
                self.put_item(priority, ts, path)
        finally:
            with self._gen_lock:
                self._gen_count = max(0, self._gen_count - 1)
    def stop(self):
        self.stop_event.set()
        while not self.queue.empty():
            try: self.queue.get_nowait(); self.queue.task_done()
            except queue.Empty: break
        try:
            if self.channel:
                self.channel.stop()
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception: pass
        try:
            from actions.volume import force_unduck
            force_unduck()
        except Exception:
            pass
        self.active_playback = False
    def _reset_unload_timer(self):
        if self.unload_timer:
            self.unload_timer.cancel()
        self.unload_timer = threading.Timer(_UNLOAD_AFTER_SEC, self._unload_model)
        self.unload_timer.daemon = True
        self.unload_timer.start()
    def _unload_model(self):
        global _tts_engine
        with TTSManager._lock:
            _tts_engine = None
            gc.collect()
def _get_tts():
    global _tts_engine
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
def ensure_mixer_init() -> None:
    try:
        if not pygame.mixer.get_init():
            dev = None
            try:
                import json
                p = os.path.join('data', 'jarvis_settings.json')
                if os.path.exists(p):
                    d = json.loads(open(p, 'r', encoding='utf-8').read())
                    if isinstance(d, dict):
                        dev = d.get('audio_output_device_name')
                        if not isinstance(dev, str) or not dev.strip():
                            dev = None
            except Exception:
                dev = None
            try:
                if dev:
                    pygame.mixer.init(frequency=_SAMPLE_RATE, devicename=dev)
                else:
                    pygame.mixer.init(frequency=_SAMPLE_RATE)
            except TypeError:
                pygame.mixer.init(frequency=_SAMPLE_RATE)
    except Exception: pass
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
    return mgr.active_playback or (mgr._gen_count > 0) or busy or (not mgr.queue.empty())
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
