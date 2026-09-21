"""
ASRManager — smart language-aware ASR engine switcher.

Russian: uses preferred engine (vosk or gigaam, from settings).
Ukrainian: no dedicated model yet (Whisper was removed) — falls back to
whatever engine is selected, using its Russian model in the meantime.

Exposes the same interface as ASR / ASR_Vosk so callers never see the switch.

Thread-safety note:
  switch_language() uses a lock for the rebuild.
  All hot-path methods (vad_check, transcribe_raw, accept, reset) read self._asr
  directly without a lock — Python GIL makes the reference read atomic, and the
  worst case is one extra call on the old ASR object, which is harmless.
"""
from __future__ import annotations
import threading
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('asr')


class ASRManager:
    def __init__(self, preferred_engine: str, rate: int, model_path: str, vad_path: str):
        self._preferred_engine = preferred_engine
        self._rate = rate
        self._model_path = model_path
        self._vad_path = vad_path
        self._switch_lock = threading.Lock()   # only held during rebuild
        self._asr = None
        self._current_lang: str | None = None
        self._current_engine: str | None = None

    # ------------------------------------------------------------------ #
    # Engine selection
    # ------------------------------------------------------------------ #

    def _engine_for(self, lang: str) -> str:
        # Whisper (Ukrainian's only engine) has been removed. Until a proper
        # Ukrainian model is added, fall back to whatever the user has
        # selected — gigaam/vosk will just keep using their Russian model
        # for 'uk' (degraded, not a crash).
        if self._preferred_engine == 'whisper':
            return 'gigaam'  # stale setting from before whisper removal
        return self._preferred_engine   # gigaam / vosk

    def _build_asr(self, engine: str):
        if engine == 'vosk':
            from core.speech.asr import ASR_Vosk
            return ASR_Vosk(self._rate)
        from core.speech.asr import ASR
        return ASR(self._model_path, self._vad_path, self._rate)

    # ------------------------------------------------------------------ #
    # Language switching  (called from i18n.set_language, background thread)
    # ------------------------------------------------------------------ #

    def switch_language(self, lang: str) -> None:
        wanted_engine = self._engine_for(lang)
        with self._switch_lock:
            if lang == self._current_lang and self._asr is not None:
                return
            if wanted_engine == self._current_engine and self._asr is not None:
                # Same engine — just switch its internal language model
                if hasattr(self._asr, 'switch_language'):
                    self._asr.switch_language(lang)
                self._current_lang = lang
                return
            _log.info('Switching: lang=%s, engine %s → %s', lang, self._current_engine, wanted_engine)
            try:
                new_asr = self._build_asr(wanted_engine)
                if hasattr(new_asr, 'switch_language'):
                    new_asr.switch_language(lang)
                # Atomic swap — hot-path readers get old or new, both are valid
                self._asr = new_asr
                self._current_engine = wanted_engine
                self._current_lang = lang
                _log.info('Ready: engine=%s, lang=%s', wanted_engine, lang)
            except Exception as e:
                _log.error('ERROR building ASR: %s', e, exc_info=True)

    def ensure_initialized(self) -> None:
        if self._asr is None:
            from core.i18n import get_speech_language
            self.switch_language(get_speech_language())

    # ------------------------------------------------------------------ #
    # Hot-path methods — NO lock, direct read of self._asr (atomic by GIL)
    # ------------------------------------------------------------------ #

    def vad_check(self, audio_chunk: bytes) -> float:
        asr = self._asr
        return asr.vad_check(audio_chunk) if asr else 0.0

    def reset(self) -> None:
        asr = self._asr
        if asr: asr.reset()

    def accept(self, data: bytes) -> bool:
        asr = self._asr
        return asr.accept(data) if asr else False

    def transcribe_raw(self, audio_bytes: bytes) -> str:
        asr = self._asr
        return asr.transcribe_raw(audio_bytes) if asr else ''

    def transcribe(self, audio_buffer) -> str:
        asr = self._asr
        return asr.transcribe(audio_buffer) if asr else ''

    def result_json(self) -> dict:
        asr = self._asr
        return asr.result_json() if asr else {'text': ''}

    def partial_json(self) -> dict:
        asr = self._asr
        return asr.partial_json() if asr else {'partial': ''}

    # ------------------------------------------------------------------ #
    # Infrequent methods — also lock-free, safe
    # ------------------------------------------------------------------ #

    def set_vad_mode(self, game_mode: bool) -> None:
        asr = self._asr
        if asr: asr.set_vad_mode(game_mode)

    def reload_with_hotwords(self, words: list[str], score: float = 2.0) -> None:
        asr = self._asr
        if asr: asr.reload_with_hotwords(words, score)

    def clear_hotwords(self) -> None:
        asr = self._asr
        if asr: asr.clear_hotwords()

    def warmup_stt(self) -> None:
        asr = self._asr
        if asr: asr.warmup_stt()

    @property
    def _audio_buffer(self):
        asr = self._asr
        return asr._audio_buffer if asr else bytearray()
