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
import psutil
import json
from core.speech.tts_markup import (  # noqa: F401
    _SSML_TAG_RE, _get_cmudict, _needs_ssml_route, strip_speech_markup,
)
from core.speech.tts_normalize import (  # noqa: F401
    _apply_stress, _get_lang, _get_morph, _normalize_cache, _normalize_cache_lock, normalize_for_tts,
)
from core.speech.tts_cache import (  # noqa: F401
    CACHE_DIR, _apply_wav_speed, _get_night_vol_settings, _get_tts_speed, _invalidate_night_vol_cache, invalidate_tts_speed_cache,
)
from core import native_audio
from core.speech import tts_onnx
from core.speech.tts_audio import apply_audio_devices, ensure_player, wait_for_playback_idle  # noqa: F401

_BIG_STACK_BYTES = 32 * 1024 * 1024  # Silero needs deep call stacks on
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

_SAMPLE_RATE = 48000
_LANG_CONFIG = {
    'ru': {'speaker': 'eugene'},
    'uk': {'speaker': 'mykyta'},     # no Ukrainian voice for now: _generate_cached stays silent for it
}
_UNLOAD_AFTER_SEC = 300.0  # Fallback, overridden by config
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')
_SPLIT_THRESHOLD = 90
_MAX_CHUNK_CHARS = 250









_tts_models = {}  # Cache for models by language
_tts_inference_lock = threading.Lock()  # Silero models are NOT thread-safe; serialise all save_wav calls









_silero_supports_speech_rate: bool | None = None










_MASTER_VOLUME = 1.0
_warmup_started = False
_warmup_lock = threading.Lock()
_text_warmup_started = False
_text_warmup_lock = threading.Lock()




def _get_model_config(lang: str = None) -> dict:
    if lang is None: lang = _get_lang()
    return _LANG_CONFIG.get(lang, _LANG_CONFIG['ru'])

def _get_speaker(lang: str = None) -> str:
    config = _get_model_config(lang)
    return config['speaker']
def _chunk_text(text: str) -> list[str]:
    """Split text into chunks safe for Silero: first by sentence, then by word boundary."""
    raw = _SENTENCE_SPLIT_RE.split(text) if len(text) > _SPLIT_THRESHOLD else [text]
    chunks: list[str] = []
    pending_markup = ''  # markup-only fragment with no chunk to attach to yet
    for s in raw:
        s = s.strip()
        if not s:
            continue
        # Skip chunks that are only punctuation (remnants of "..." separators,
        # or a lone ",..." left over from clause-splitting a streamed LLM
        # answer) — Silero's normalizer raises a bare ValueError on these
        # instead of just producing silence, so they must never reach it.
        if all(c in '.,!?—-:; ' for c in s):
            continue
        # A sentence boundary can land right after a lone <break .../> tag
        # (or *emphasis* marker), leaving a chunk with no speakable text of
        # its own. Generated alone it's a real audio clip of pure silence —
        # the HUD shows "speaking" for its full duration with nothing
        # audible. Fold it into an adjacent real chunk instead.
        if not _SSML_TAG_RE.sub('', s).replace('*', '').strip():
            if chunks:
                chunks[-1] = chunks[-1] + ' ' + s
            else:
                pending_markup = (pending_markup + ' ' + s).strip()
            continue
        if pending_markup:
            s = pending_markup + ' ' + s
            pending_markup = ''
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

    __slots__ = ('_priority', '_base_ts', '_mgr', '_lock', '_buf', '_next', '_watchdog', '_epoch', '_pending', '_persist')

    def __init__(self, priority: int, base_ts: float, mgr: 'TTSManager', epoch: int, persist: bool = True) -> None:
        self._priority = priority
        self._base_ts = base_ts
        self._mgr = mgr
        self._epoch = epoch
        self._persist = persist
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
        self._unload_timer_lock = threading.Lock()
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
        print("[TTS-WORKER] Thread started.", flush=True)
        from actions.volume import duck_volume, force_unduck
        # Safety-net unduck retry, ~2s after idle cleanup, on this worker thread's own polling loop.
        _pending_unduck_retry: list[float | None] = [None]
        _is_ducked = False

        def _do_idle_cleanup():
            nonlocal _is_ducked
            if not _is_ducked:
                return
            _is_ducked = False
            try: force_unduck()
            except Exception: pass
            _pending_unduck_retry[0] = time.time() + 2.0
            self._safe_hud_set_mode('idle')
            self.active_playback = False

        while True:
            try:
                # A stop()-requested unduck is handled here, whether idle or about to process a new item.
                if self._unduck_requested.is_set():
                    self._unduck_requested.clear()
                    try: force_unduck()
                    except Exception: pass

                # Short timeout so idle detection is responsive
                try:
                    pri, ts, item = self.queue.get(timeout=0.05)
                except queue.Empty:
                    # The native player knows exactly when its queue ran dry: idle means nothing playing, nothing generating, nothing queued
                    _drained = self._gen_count == 0 and self.queue.empty()
                    if _drained and not native_audio.is_busy():
                        _do_idle_cleanup()
                    if _pending_unduck_retry[0] is not None and time.time() >= _pending_unduck_retry[0]:
                        _pending_unduck_retry[0] = None
                        try: force_unduck()
                        except Exception: pass
                    continue

                if item is None: break

                now = time.time()
                print(f"[TTS-WORKER] [{now:.3f}] Processing: {item}", flush=True)
                self.active_playback = True
                self.stop_event.clear()

                if not _is_ducked:
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
                _n_enabled, _n_start_h, _n_start_m, _n_end_h, _n_end_m, _night_vol = _get_night_vol_settings()
                start_m = _n_start_h * 60 + _n_start_m
                end_m = _n_end_h * 60 + _n_end_m
                if start_m <= end_m:
                    is_night = (start_m <= current_m < end_m)
                else:
                    is_night = (current_m >= start_m or current_m < end_m)
                is_night = is_night and _n_enabled
                vol = _MASTER_VOLUME * _night_vol if is_night else _MASTER_VOLUME
                if is_night:
                    vol = max(vol, min(_MASTER_VOLUME, 0.2))

                self._safe_hud_set_mode('speaking')
                print(f"[TTS-WORKER] [{time.time():.3f}] Playing: {audio_path}", flush=True)
                # The player reads the whole file before it answers, and consecutive clips play back to back without a gap.
                seconds = native_audio.play(audio_path, vol, 'tts')

                # Ephemeral (non-cached) file: the player has it in memory now, so free the disk copy right away.
                if os.path.basename(audio_path).startswith('silero_tmp_'):
                    try: os.remove(audio_path)
                    except OSError: pass

                if seconds is None:
                    print("[TTS-WORKER] ERROR: the audio player did not take the clip.", flush=True)
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

    def speak(self, text: str, priority: int = 10, wait: bool = False, persist: bool = True):
        # Chunk on the calling thread (cheap, just regex splitting) but defer
        # normalize_for_tts() to the executor pool (see _gen_sentence). The
        # calling thread is often itself a streaming/UI-updating thread (e.g.
        # the AI-answer streaming loop) — normalize_for_tts() can cold-start
        # pymorphy3's MorphAnalyzer (1-3s) or block on _morph_lock if another
        # thread is mid-load, which used to freeze that caller's whole loop
        # (text AND speech) on the very first AI answer of a session.
        text = text.strip()
        if not text: return
        try:  # the window's feed (no-op while the bridge is not running)
            from ui_next import bridge as _ui_bridge
            _ui_bridge.reply(text)
        except Exception:
            pass
        self.active_playback = True
        self.stop_event.clear()
        sentences = _chunk_text(text)
        if not sentences:
            self.active_playback = False
            return
        with self._gen_lock: self._gen_count += len(sentences)
        batch = _OrderedBatch(priority, time.time(), self, self.gen_epoch, persist=persist)
        indexed = list(enumerate(sentences))
        batch._pending = indexed[self._MAX_INFLIGHT:]
        for i, s in indexed[:self._MAX_INFLIGHT]:
            self.executor.submit(self._gen_sentence, s, i, batch)
        self._reset_unload_timer()
        if wait: self.wait_until_finished()

    def put_item(self, priority: int, ts: float, item: str):
        # Defensive dedup, not a symptom fix for a known bug: two independent
        # callers (e.g. a racing dispatch path and a retry, or two feature
        # modules reacting to the same event) can enqueue the identical
        # already-generated wav path within the same instant. A 0.8s window
        # only ever collapses genuine near-simultaneous repeats — normal
        # speech (even fast replies) doesn't reuse the exact same audio path
        # that quickly, so this never swallows a legitimate repeat.
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
            path = _generate_cached(text, speed_pct, persist=batch._persist)
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
        try: native_audio.stop('tts')
        except Exception: pass
        # Don't touch pycaw/COM from this (caller's) thread — just flag it for
        # the TTS worker thread to handle on its own apartment. See
        # _unduck_requested above for why.
        self._unduck_requested.set()
        self._safe_hud_set_mode('idle')
        self.active_playback = False

    def _safe_hud_set_mode(self, mode_name: str):
        try:
            from ui_next import host as _hud
            _hud.STATE.mode = _hud.HudState.IDLE if mode_name == 'idle' else _hud.HudState.SPEAKING     # the state has its own lock
        except Exception:
            pass
    def _reset_unload_timer(self):
        with self._unload_timer_lock:
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
    cached = _tts_models.get(lang)
    if cached is not None and tts_onnx.keep(cached, lang): return cached
    with TTSManager._lock:
        cached = _tts_models.get(lang)
        if cached is not None and tts_onnx.keep(cached, lang): return cached
        tts_onnx.start_download()      # the ONNX voice files arrive in the background; silent until then
        if tts_onnx.usable(lang):
            try:
                model = tts_onnx.load()
                _tts_models.clear()
                gc.collect()
                _tts_models[lang] = model
                return model
            except Exception as e:
                tts_onnx.mark_broken(e)
        raise RuntimeError(f'no TTS voice for {lang!r}: the ONNX voice is not available yet')
def _save_wav_native_speed(model, tmp_path: str, speaker: str, speed: float,
                            want_native_speed: bool, *, text: str = None, ssml_text: str = None) -> None:
    """save_wav wrapper sharing the speech_rate-support probe between the
    plain-text and ssml_text call sites so it isn't duplicated per branch."""
    global _silero_supports_speech_rate
    kwargs = dict(speaker=speaker, sample_rate=_SAMPLE_RATE, audio_path=tmp_path)
    kwargs['text'] = text if ssml_text is None else None
    kwargs['ssml_text'] = ssml_text
    if want_native_speed:
        try:
            model.save_wav(speech_rate=speed, **kwargs)
            _silero_supports_speech_rate = True
            return
        except TypeError:
            _silero_supports_speech_rate = False
    model.save_wav(**kwargs)


def _generate_cached(text: str, _speed_pct: int = 100, persist: bool = True) -> str | None:
    global _silero_supports_speech_rate
    speed = _speed_pct / 100.0
    lang = _get_lang()
    if lang != 'ru':
        return None     # only the Russian ONNX voice exists; other languages are text-only
    speaker = _get_speaker(lang)
    use_ssml = _needs_ssml_route(text)
    # Cache key includes speed so each rate has its own file
    cache_key = f'{text}|{speaker}|{lang}|{_SAMPLE_RATE}|{_speed_pct}'
    h = hashlib.md5(cache_key.encode('utf-8'), usedforsecurity=False).hexdigest()[:12]
    # persist=False (one-off AI/LLM answer text, unlikely to repeat verbatim)
    # gets a distinct filename prefix so the worker frees it right after
    # playback instead of leaving it in the cache dir until eviction — see
    # the silero_tmp_ cleanup in TTSManager._worker.
    prefix = 'silero' if persist else 'silero_tmp'
    path = os.path.join(CACHE_DIR, f'{prefix}_{h}.wav')
    if not os.path.exists(path):
        model = None
        try:
            model = _get_tts()
            tmp_path = path + '.tmp'
            want_native_speed = abs(speed - 1.0) >= 0.02 and _silero_supports_speech_rate is not False
            with _tts_inference_lock:
                if use_ssml:
                    ssml_payload = text if text.lstrip().startswith('<speak') else f'<speak>{text}</speak>'
                    try:
                        _save_wav_native_speed(model, tmp_path, speaker, speed, want_native_speed, ssml_text=ssml_payload)
                    except Exception as ssml_err:
                        # Cloud LLM produced invalid SSML (unbalanced/unknown
                        # tag) — strip markup and speak it as plain text
                        # rather than losing the whole reply.
                        print(f"TTS-GENERATOR: SSML parse failed ({ssml_err}) for '{text[:30]}...', falling back to plain text.", flush=True)
                        plain_text = _SSML_TAG_RE.sub('', text).replace('*', '')
                        _save_wav_native_speed(model, tmp_path, speaker, speed, want_native_speed, text=plain_text)
                else:
                    _save_wav_native_speed(model, tmp_path, speaker, speed, want_native_speed, text=text)
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











# --- normalize_for_tts pipeline -----------------------------------------
#
# Each _expand_*/_fix_* function below is one independent text->text step
# of the pipeline, run in sequence by normalize_for_tts() at the bottom.
# They're pure functions of their arguments (no shared mutable state besides
# the `text` threaded through), so each is independently readable and
# testable instead of being one 280-line function body full of closures
# capturing shared local state.











































def speak(text: str, priority: int = 10, wait: bool = False, persist: bool = True) -> None:
    TTSManager().speak(text, priority, wait, persist=persist)

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
    """Pre-load pymorphy3 dictionaries. Pure-Python, no GPU/audio contact,
    so unlike warmup_tts() this is safe to call immediately at process start
    instead of waiting for the audio engine to be ready."""
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

    def _warm_cmudict():
        # cmudict.dict() parses its bundled ~126k-word data file on first
        # call (~2s) — same cold-start hazard as pymorphy3 above, warmed up
        # in parallel rather than on the first sentence containing a Latin
        # word.
        try:
            _get_cmudict()
        except Exception as e:
            print(f"TTS-WARMUP: cmudict preload failed: {e}")

    threading.Thread(target=_warm_morph, daemon=True, name='TTS-WarmupMorph').start()
    threading.Thread(target=_warm_cmudict, daemon=True, name='TTS-WarmupCmudict').start()
def warmup_tts() -> None:
    global _warmup_started
    with _warmup_lock:
        if _warmup_started:
            return
        _warmup_started = True
    def _warm():
        try:
            try:
                ensure_player()
            except Exception:
                pass
            lang = _get_lang()
            tts_onnx.start_download()
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
    # stack. Text-model warmup (pymorphy3) is pure-Python, no deep PyTorch
    # recursion — started separately via warmup_text_models() so it doesn't
    # have to wait for the audio engine to be ready.
    _spawn_with_big_stack(_warm, name='TTS-WarmupModel')
    warmup_text_models()
def is_speaking() -> bool:
    mgr = TTSManager()
    busy = native_audio.is_busy()
    queue_empty = False
    try:
        if mgr.queue.empty():
            queue_empty = True
    except Exception:
        queue_empty = True
    return mgr.active_playback or (mgr._gen_count > 0) or busy or (not queue_empty)
def is_tts_playing_audio() -> bool:
    return is_speaking()
