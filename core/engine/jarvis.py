import time
import threading
import queue as _queue_mod
import numpy as _np
import collections as _collections
import win32gui
import ctypes
import pyaudio
from core.audio_utils import open_input_stream, rms_int16
from core.system import app_state
from core.voice_debug_log import voice_event, voice_heartbeat, voice_session_banner
from .recognition import handle_recognized_text, flush_final
from config_pack.config import (
    RATE, CHUNK_MS, MIN_THRESH,
    VAD_CONFIDENCE_THRESHOLD, VAD_SILENCE_MS, GAME_SILENCE_MS
)
_engine_singleton = None
def get_engine():
    return _engine_singleton
class JarvisEngine:
    def __init__(self, pa: pyaudio.PyAudio, asr, handler):
        self.pa = pa
        self.asr = asr
        self.handler = handler
        self.chunk = int(RATE * CHUNK_MS / 1000)
        self.silence_frames = max(1, VAD_SILENCE_MS // CHUNK_MS)
        self.game_silence_frames = max(1, GAME_SILENCE_MS // CHUNK_MS)
        self.transcribe_queue = _queue_mod.Queue(maxsize=64)
        self.stream = open_input_stream(self.pa, RATE, self.chunk)
        self.speaking = False
        self.had_voice = False
        self.silence_cnt = 0
        self.voiced_frames = 0
        self.noise_ema = float(MIN_THRESH)
        self.energy_thresh = MIN_THRESH
        self.voice_on = self.energy_thresh
        self.voice_off = int(self.energy_thresh * 0.7)
        self.active_timeout_sec = 30
        self._calibrating = False
        prebuf_frames = max(1, 350 // CHUNK_MS)
        self.pre_buf = _collections.deque(maxlen=prebuf_frames)
        self.last_game_audio = b''
        self.console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        self._last_fg_poll = 0.0
        self._NOISE_ALPHA = 0.015
        self._ADAPT_MULT = 2.2
        self._ADAPT_MULT_OFF = 1.3
        self._ADAPT_MIN = float(MIN_THRESH)
        self._last_tts_skip_log = 0.0
    def update_params(self, new_thresh: int, new_gain: float, new_vol: float):
        self.energy_thresh = new_thresh
        self.voice_on = self.energy_thresh
        self.voice_off = int(self.energy_thresh * 0.7)
        from config_pack import config
        config.MIC_GAIN = new_gain
        try:
            from core.speech import tts
            tts._MASTER_VOLUME = new_vol
        except Exception: pass
    def _reopen_stream(self):
        for attempt in range(5):
            try:
                try: self.stream.close()
                except Exception: pass
                time.sleep(1.0 + attempt * 0.5)
                self.stream = open_input_stream(self.pa, RATE, self.chunk)
                return True
            except Exception: pass
        return False
    def _transcription_worker(self):
        while True:
            audio_bytes, handler_ref = self.transcribe_queue.get()
            try:
                if audio_bytes:
                    text = self.asr.transcribe_raw(audio_bytes)
                    if text:
                        handle_recognized_text(text, handler_ref)
            except Exception as _e:
                voice_event(f'STT error {type(_e).__name__}: {_e!r}')
            finally: self.transcribe_queue.task_done()
    def drain_transcribe_queue(self, keep: int = 2) -> int:
        q = self.transcribe_queue
        dropped = 0
        while True:
            try:
                n = q.qsize()
            except Exception:
                break
            if n <= keep:
                break
            try:
                q.get_nowait()
                dropped += 1
                try:
                    q.task_done()
                except Exception:
                    pass
            except _queue_mod.Empty:
                break
        return dropped
    def run(self):
        global _engine_singleton
        _engine_singleton = self
        threading.Thread(target=self._transcription_worker, daemon=True, name='ASR-Worker').start()
        threading.Thread(target=self.asr.warmup_stt, daemon=True).start()
        from config_pack.config import MIC_GAIN, STT_ENGINE
        try:
            while True:
                now_ts = time.time()
                if now_ts - self._last_fg_poll >= 0.2:
                    self._last_fg_poll = now_ts
                    fg = win32gui.GetForegroundWindow()
                    if fg and fg != self.console_hwnd:
                        self.handler.last_user_hwnd = fg
                if self._calibrating:
                    time.sleep(0.01); continue
                try:
                    data = self.stream.read(self.chunk, exception_on_overflow=False)
                except OSError:
                    if not self._reopen_stream(): break
                    continue
                _tts_blocks = self.handler.is_tts_audio_playing
                if _tts_blocks and (not self.handler.interactive_state):
                    from core.audio_utils import is_jarvis_output_headphones
                    if not is_jarvis_output_headphones() and not app_state.game_mode:
                        try:
                            from ui import hud as _hud
                            if _hud.STATE and _hud.STATE.mode != _hud.HudState.SPEAKING:
                                _hud.STATE.mode = _hud.HudState.SPEAKING
                        except Exception: pass
                        if now_ts - self._last_tts_skip_log >= 4.0:
                            self._last_tts_skip_log = now_ts
                        continue
                gain = getattr(self.handler, 'mic_gain', MIC_GAIN)
                if gain != 1.0:
                    arr = _np.frombuffer(data, dtype=_np.int16)
                    arr = _np.clip(arr * gain, -32768, 32767).astype(_np.int16)
                    data = arr.tobytes()
                rms = rms_int16(data)
                if (
                    app_state.jarvis_active
                    and (not app_state.game_mode)
                    and time.time() - app_state.last_command_time > self.active_timeout_sec
                ):
                    if not self.speaking and (not app_state.dictation_mode) and (not self.handler.interactive_state) and (not self.handler.is_speaking):
                        app_state.jarvis_active = False
                        try:
                            from ui import hud as _hud
                            if _hud.STATE: _hud.STATE.mode = _hud.HudState.IDLE
                        except Exception: pass
                if not self.speaking and not self.handler.is_speaking:
                    if app_state.game_mode:
                        et = float(self.energy_thresh)
                        self.voice_on  = max(self._ADAPT_MIN * 1.15, int(et * 0.92))
                        self.voice_off = max(self._ADAPT_MIN, int(et * 0.58))
                    else:
                        self.noise_ema = self.noise_ema * (1 - self._NOISE_ALPHA) + rms * self._NOISE_ALPHA
                        self.voice_on  = max(self._ADAPT_MIN * 1.5,
                                              int(self.noise_ema * self._ADAPT_MULT))
                        self.voice_off = max(self._ADAPT_MIN,
                                              int(self.noise_ema * self._ADAPT_MULT_OFF))
                vad_prob = 0.0
                if rms > self.voice_off:
                    try:
                        vad_prob = self.asr.vad_check(data)
                    except Exception:
                        vad_prob = 0.0
                _vad_thresh = VAD_CONFIDENCE_THRESHOLD
                if not self.speaking:
                    self.pre_buf.append(data)
                    start_trigger = (rms > self.voice_on) or (vad_prob > _vad_thresh)
                    if start_trigger:
                        if app_state.game_mode:
                            try:
                                _qs = self.transcribe_queue.qsize()
                            except Exception:
                                _qs = 0
                            if _qs > 2:
                                self.drain_transcribe_queue(keep=0)
                        self.speaking, self.had_voice, self.silence_cnt, self.voiced_frames = (True, True, 0, 1)
                        self.asr.reset()
                        for _pb in self.pre_buf: self.asr.accept(_pb)
                        self.asr.accept(data); self.pre_buf.clear()
                        try:
                            from ui import hud as _hud
                            if _hud.STATE and not self.handler.is_tts_audio_playing:
                                _hud.STATE.mode = _hud.HudState.LISTENING
                        except Exception: pass
                else:
                    self.asr.accept(data)
                    if rms > self.voice_off or vad_prob > _vad_thresh:
                        self.voiced_frames += 1; self.silence_cnt = 0
                    elif self.had_voice:
                        self.silence_cnt += 1
                        _sf = self.game_silence_frames if app_state.game_mode else self.silence_frames
                        if self.silence_cnt >= _sf:
                            try:
                                if app_state.game_mode and self.voiced_frames < 3:
                                    self.asr.reset()
                                    self.speaking, self.had_voice, self.silence_cnt, self.voiced_frames = (False, False, 0, 0)
                                    continue
                                if app_state.game_mode:
                                    audio = bytes(self.asr._audio_buffer)
                                    if len(audio) / 2 / RATE <= 1.2:
                                        from actions.game_audio import game_matcher
                                        audio_res = game_matcher.match(audio)
                                        if audio_res:
                                            from actions.game_input import execute_by_name
                                            if execute_by_name(audio_res[0]):
                                                self.asr.reset()
                                                self.speaking, self.had_voice, self.silence_cnt, self.voiced_frames = (False, False, 0, 0)
                                                continue
                                _abuf = bytes(self.asr._audio_buffer)
                                flush_final(self.asr, self.handler, self.transcribe_queue)
                                self.speaking, self.had_voice, self.silence_cnt, self.voiced_frames = (False, False, 0, 0)
                            except Exception: pass
        except KeyboardInterrupt: pass
        finally: self.stream.close()
