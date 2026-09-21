import threading
import time
from collections import OrderedDict
from core.system import app_state
from core.speech import (
    speak, stop_speaking, ensure_mixer_init,
    is_speaking as _is_speaking_check, is_tts_playing_audio as _is_tts_audio_check,
)
from core.responder import Responder
_RESPONDER_MAX = 12
RESPONSES = {
    'wake': ['Д+а, {addr}.', 'Всегд+а к в+ашим усл+угам, {addr}.', 'Сл+ушаю, {addr}.'],
    'confirm': ['Есть.', 'Запр+ос в+ыполнен, {addr}.', 'Как пожелаете.', 'Хорошо.', 'Сделано.'],
    'loading': ['Загруж+аю, {addr}.', 'Минуту.', 'Выполняю.'],
    'created': ['Вы создали новый элемент.', 'Элемент создан.'],
    'shutdown': ['Отключаю питание.', 'Завершаю работу.'],
    'game': ['Как пожелаете.', 'Есть.', 'Конечно.'],
    'praise': ['Всегд+а к в+ашим усл+угам, {addr}.', 'Р+ад стар+аться, {addr}.'],
    'work_prompt': ['Мы раб+отаем над про+ектом, {addr}.', 'В процессе работы.'],
    'work_cancel': ['Ладно, возвращаемся к обычному режиму.', 'Хорошо, отменяю.'],
    'startup': ['Дж+арвис зап+ущен и гот+ов к раб+оте.', 'Прив+етствую, {addr}. Сист+ема гот+ова.'],
    'not_understood': ['Не рассл+ышал, повтор+ите.', 'Не разобр+ал ком+анду.', 'Прост+ите, не п+онял.', 'Уточн+ите, пожалуйста.'],
}
RESPONSES_UK = {
    'wake':    ['Слухаю, {addr}.', 'До ваших послуг, {addr}.', 'Так?'],
    'confirm': ['Є.', 'Зроблено.', 'Як бажаєте.', 'Запит виконано, {addr}.', 'Добре.'],
    'loading': ['Завантажую, {addr}.', 'Хвилинку.'],
    'created': ['Створено.'],
    'shutdown': ['Вимикаю живлення.'],
    'game':    ['Є.', 'Як бажаєте.'],
    'praise':  ['До ваших послуг, {addr}.'],
    'work_prompt': ['Ми працюємо над проектом, {addr}.'],
    'work_cancel': ['Гаразд, повертаємось до звичного.'],
    'startup': ['Дж+арвіс до в+ашої уваги, {addr}.'],
    'not_understood': ['Не розчув, повторіть.', 'Не розібрав команду.', 'Перепрошую, не зрозумів.', 'Уточніть, будь ласка.'],
}
class BaseHandler:
    def __init__(self, pa, rate, chunk, asr):
        self.pa = pa
        self.rate = rate
        self.chunk = chunk
        self.asr = asr
        self.silent_mode = False
        self.interactive_state = None
        self.interactive_data = {}
        self._responders = OrderedDict()
        self._state_lock = threading.Lock()
        self._interactive_timer = None
        self.last_user_hwnd = None
        self.mic_gain = 1.0
        self._last_not_understood_ts = 0.0
    @property
    def is_speaking(self) -> bool:
        return _is_speaking_check()
    @property
    def is_tts_audio_playing(self) -> bool:
        return _is_tts_audio_check()
    def _get_responder(self, wav_path: str) -> Responder:
        if wav_path in self._responders:
            self._responders.move_to_end(wav_path)
            return self._responders[wav_path]
        resp = Responder(self.pa, wav_path)
        self._responders[wav_path] = resp
        if len(self._responders) > _RESPONDER_MAX:
            self._responders.popitem(last=False)
        return resp
    def _set_interactive(self, state, data: dict = None, timeout: float = 60.0):
        if self._interactive_timer:
            self._interactive_timer.cancel()
        self.interactive_state = state
        self.interactive_data = data or {}
        if state is not None:
            from core.system import app_state
            app_state.jarvis_active = True
            app_state.last_command_time = time.time()
            self._interactive_timer = threading.Timer(timeout, self._interactive_timeout)
            self._interactive_timer.daemon = True
            self._interactive_timer.start()
    def _interactive_timeout(self):
        if self.interactive_state is not None:
            self.interactive_state = None
            self._interactive_timer = None
    def _is_night_time(self) -> bool:
        from datetime import datetime
        h = datetime.now().hour
        return h >= 22 or h < 7
    def play_response(self, category: str = 'confirm', override_silent: bool = False):
        if self.silent_mode and not override_silent: return
        stop_speaking()
        from core.i18n import get_speech_language
        from core.address import get_address
        lang = get_speech_language()
        from core.responses import pick_response
        if lang == 'uk':
            phrase = pick_response(f'base.{category}.uk', RESPONSES_UK.get(category, RESPONSES_UK['confirm']))
        else:
            phrase = pick_response(f'base.{category}', RESPONSES.get(category, RESPONSES['confirm']))
        phrase = phrase.format(addr=get_address(lang))
        speak(phrase)
        try:
            from core.speech import warmup_tts
            warmup_tts()
        except Exception:
            pass
        self.asr.reset()
    def speak(self, text: str, wait: bool = False):
        if self.silent_mode: return
        # REMOVED: stop_speaking() - now using natural TTS queue for smooth transitions
        speak(text, wait=wait)
        if not self.interactive_state:
            self.asr.reset()
