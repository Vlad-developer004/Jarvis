import json
from pathlib import Path
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('i18n')

_language = 'ru'
_translations = {}
_refresh_callbacks = []
_asr_ref = None

# Инициализируем локализацию при импорте
def _init():
    global _translations
    _translations = _load_locale(_language)

def _load_locale(lang: str) -> dict:
    locale_dir = Path(__file__).parent.parent / 'data' / 'locales'
    locale_file = locale_dir / f'{lang}.json'
    if not locale_file.exists():
        return {}
    with open(locale_file, 'r', encoding='utf-8') as f:
        return json.load(f)

_init()

def tr(key: str) -> str:
    return _translations.get(key, key)

def register_asr(asr) -> None:
    global _asr_ref
    _asr_ref = asr

def set_language(lang: str) -> None:
    """Switch the on-screen UI text language only. Deliberately does NOT
    touch ASR/TTS anymore — see get_speech_language()."""
    global _language, _translations
    _language = lang
    _translations = _load_locale(lang)
    _log.info("set_language('%s')", lang)
    for callback in _refresh_callbacks:
        try:
            callback()
        except Exception as e:
            _log.warning('refresh callback error: %s', e)

def get_language() -> str:
    """On-screen UI text language (dialogs, labels, the command deck) —
    freely switchable by the user in Settings."""
    return _language

def get_speech_language() -> str:
    """Language JARVIS listens in (ASR model) and speaks in (TTS voice, and
    every RU/UK spoken-phrase picker: core.responses.spk, core.handler.base's
    RESPONSES, features.ets2.phrases_common._r, core.address.get_address,
    core.nlp.commands' CANON_SIMPLE selection, etc).

    Deliberately independent from get_language(): there is no quality
    Ukrainian STT/TTS model yet (Vosk/sherpa-onnx recognition and Silero's
    v4_ua voice are both noticeably worse than the Russian ones), so
    switching the interface to Ukrainian must not also switch voice I/O to
    a worse-sounding one. Pinned to 'ru' until that changes — revisit this
    when a good UK model is actually available, at which point this can
    become its own user-facing setting instead of a constant.
    """
    return 'ru'

def register_refresh(callback) -> None:
    _refresh_callbacks.append(callback)
