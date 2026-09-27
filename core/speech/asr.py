from __future__ import annotations
import os
import re
import threading
import urllib.request
import tarfile
import zipfile
import json
import shutil
from pathlib import Path
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('asr')
import numpy as np
_CLEANUP_RE = re.compile(r'<\|.*?\|>')
def _get_base_models_path() -> Path:
    from config_pack.config import get_project_root
    return Path(get_project_root()) / 'models'
def _onnx_threads() -> int:
    try:
        from config_pack.config import get_settings_path
        p_str = get_settings_path()
        if os.path.exists(p_str):
            with open(p_str, 'r', encoding='utf-8') as f:
                data = json.load(f)
            val = int(data.get('onnx_threads', 0))
            if val > 0:
                return max(1, min(val, (os.cpu_count() or 2)))
    except Exception:
        pass
    cpus = os.cpu_count() or 2
    if cpus >= 12:
        return 3
    return max(1, min(2, cpus))
_STT_RETRY_SECONDS = 120  # background retry interval while an STT model is missing

def _notify_model_download(active: bool, failed: bool = False) -> None:
    """Best-effort HUD notice around an STT model download — same rationale
    as core/speech/tts.py's helper of the same name: these models aren't
    bundled in the installer, so a silent download failure would leave
    Jarvis simply not responding to voice with no visible cause. Never
    raises: must not affect ASR loading if the HUD isn't up yet."""
    try:
        from ui import hud as _hud
        from ui.hud_constants import _AMBER, _RED
        if failed:
            _hud.notify('stt_model',
                         f'Не удалось скачать модель распознавания речи — повторю через {_STT_RETRY_SECONDS // 60} мин',
                         _RED, duration=6000)
        elif active:
            _hud.notify('stt_model', 'Скачиваю модель распознавания речи...', _AMBER)
        else:
            _hud.clear_notify('stt_model')
    except Exception:
        pass

def _schedule_retry(instance, retry_fn, *, pending_attr: str = '_retry_pending',
                     seconds: float = _STT_RETRY_SECONDS) -> None:
    """Actually makes good on _notify_model_download's 'повторю через N мин'
    instead of leaving it to the user's next spoken command / next audio
    chunk — that would otherwise re-hit the same multi-second-to-minutes
    download timeout inline, on whatever thread called it. One retry chain
    per (instance, pending_attr) at a time — pending_attr is distinct per
    failure kind (STT model vs VAD model) so they don't block each other on
    the same ASR instance — set/read under whichever lock the caller already
    holds. retry_fn reschedules again on repeat failure via the same
    except-block path, so this keeps retrying at a fixed interval for as
    long as the app runs."""
    if getattr(instance, pending_attr, False):
        return
    setattr(instance, pending_attr, True)
    def _retry():
        setattr(instance, pending_attr, False)
        try:
            retry_fn()
        except Exception:
            pass
    t = threading.Timer(seconds, _retry)
    t.daemon = True
    t.start()
def _stream_download(url: str, filepath: str, timeout: int = 60) -> None:
    """Raises on any failure — but critically also never leaves a partial/
    truncated file behind at `filepath`. A caller that only checks
    os.path.exists(filepath) to decide whether a download is needed (every
    caller here does) would otherwise treat a half-written file as "already
    downloaded" forever, and hand a corrupt model file straight to
    sherpa_onnx/vosk — which, like llama.cpp elsewhere in this codebase, can
    hard-crash the process natively on a malformed model instead of raising
    a catchable Python exception."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content_length = response.getheader('Content-Length')
            expected_size = int(content_length) if content_length else None
            with open(filepath, 'wb') as out_file:
                shutil.copyfileobj(response, out_file, length=1024 * 1024)
            if expected_size is not None:
                actual_size = os.path.getsize(filepath)
                if actual_size < expected_size:
                    raise OSError(f"Download incomplete: got {actual_size} bytes, expected {expected_size} bytes")
    except Exception:
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
        raise
class _SileroVadMixin:
    """Shared Silero VAD (via sherpa-onnx) for any ASR engine.

    Requires the including class's __init__ to set: self.rate, self.vad_dir,
    self.vad = None, self._vad_lock = threading.RLock(), self._vad_residual_bytes = b''.

    Silero VAD v6 is light on CPU/RAM, so there's no real cost to using the
    same neural VAD everywhere — Vosk previously used a crude RMS-loudness
    threshold (vad_check below was the only thing that differed), which is
    far less accurate at telling speech apart from background noise.
    """

    def _ensure_vad_downloaded(self):
        os.makedirs(self.vad_dir, exist_ok=True)
        vad_path = os.path.join(self.vad_dir, 'silero_vad.onnx')
        if not os.path.exists(vad_path):
            url = 'https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx'
            _stream_download(url, vad_path, timeout=90)

    def _lazy_load_vad(self):
        if self.vad is not None: return
        with self._vad_lock:
            if self.vad is not None: return
            # vad_check() calls this on every audio chunk where rms crosses
            # a low threshold — essentially continuously whenever there's any
            # ambient sound. Before this guard, a failed download got
            # retried right here, synchronously, on the live audio-capture
            # thread, with _stream_download's up-to-90s timeout — repeatedly,
            # on every qualifying chunk. That stalls stream.read() for the
            # whole engine, which looks exactly like "says the wake word,
            # Jarvis never responds": the mic loop is stuck retrying a dead
            # download instead of reading audio. Once a download has failed,
            # back off to the scheduled background retry below instead.
            if getattr(self, '_vad_retry_pending', False):
                return
            import sherpa_onnx
            try:
                self._ensure_vad_downloaded()
            except Exception as e:
                _log.error('VAD model download failed: %s', e)
                _notify_model_download(active=False, failed=True)
                _schedule_retry(self, self._lazy_load_vad, pending_attr='_vad_retry_pending')
                return
            config = sherpa_onnx.VadModelConfig()
            config.silero_vad.model = os.path.join(self.vad_dir, 'silero_vad.onnx')
            config.silero_vad.min_silence_duration = getattr(self, '_vad_min_silence', 0.25)
            config.silero_vad.min_speech_duration = getattr(self, '_vad_min_speech', 0.2)
            config.sample_rate = self.rate
            config.num_threads = _onnx_threads()
            _log.info('Loading VAD from %s', config.silero_vad.model)
            try:
                self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
            except Exception as e:
                _log.critical('CRITICAL: failed to construct VAD from %s: %s', config.silero_vad.model, e, exc_info=True)
                # A bad (but present) file won't be re-downloaded by the
                # os.path.exists() check in _ensure_vad_downloaded — remove
                # it so the scheduled retry actually re-fetches instead of
                # hitting this same construction failure forever.
                try:
                    os.remove(config.silero_vad.model)
                except OSError:
                    pass
                _schedule_retry(self, self._lazy_load_vad, pending_attr='_vad_retry_pending')
                raise

    def _warmup_vad_async(self) -> None:
        """Proactively load VAD in the background at startup, same reasoning
        as STT/TTS warmup: without this, the first load attempt happens
        inside vad_check() on the live audio-capture thread on whichever
        chunk first crosses the loudness gate — fine on the (normal) fast
        path, but see _lazy_load_vad's docstring for why a slow/failed first
        attempt there is worse than elsewhere."""
        threading.Thread(target=self._lazy_load_vad, daemon=True, name='VadWarmup').start()

    def set_vad_mode(self, game_mode: bool):
        with self._vad_lock:
            # Game mode used to wait longer (0.30s) than normal mode (0.25s) to
            # avoid engine/ambient game noise triggering false cutoffs. Most users
            # play with headphones, so the mic doesn't pick up game audio — pushed
            # as low as practical for Silero VAD (going much below ~0.10-0.12s
            # risks the model splitting a word on a brief mid-word low-energy gap).
            # Revert toward 0.25-0.30 if speakers (not headphones) cause clipped
            # game commands, or raise toward 0.15-0.18 if words start getting cut.
            # Normal mode (0.16) kept slightly above game mode's floor: it also
            # covers longer AI queries and dictation, where users pause mid-thought
            # more than during short imperative game commands — more cutoff risk.
            self._vad_min_silence = 0.12 if game_mode else 0.16
            self._vad_min_speech = 0.20 if game_mode else 0.10
            self.vad = None

    def vad_check(self, audio_chunk):
        if not audio_chunk: return 0.0
        with self._vad_lock:
            self._lazy_load_vad()
            if self.vad is None:
                return 0.0
            raw = self._vad_residual_bytes + audio_chunk
            frame_samples = 512
            frame_bytes = frame_samples * 2
            processed_bytes = (len(raw) // frame_bytes) * frame_bytes
            if processed_bytes:
                samples = np.frombuffer(raw[:processed_bytes], dtype=np.int16).astype(np.float32) / 32768.0
                for i in range(0, len(samples), frame_samples):
                    self.vad.accept_waveform(samples[i:i + frame_samples])
            self._vad_residual_bytes = raw[processed_bytes:]
            return 1.0 if (self.vad.is_speech_detected() or not self.vad.empty()) else 0.0

    def _vad_reset(self):
        with self._vad_lock:
            self._vad_residual_bytes = b''
            if self.vad is not None: self.vad.reset()


class ASR(_SileroVadMixin):
    def __init__(self, stt_model_path, vad_model_path, rate):
        self.rate = rate
        models_base = _get_base_models_path()
        self.stt_dir = models_base / (os.path.basename(stt_model_path) if stt_model_path else 'sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16')
        # Use vad_model_path if provided and valid, otherwise fall back to default location
        self.vad_dir = Path(vad_model_path) if (vad_model_path and Path(vad_model_path).is_dir()) else models_base / 'silero_vad'
        self.recognizer = None
        self.vad = None
        self._reload_lock = threading.RLock()
        self._vad_lock = threading.RLock()
        self._audio_buffer = bytearray()
        self._max_buffer_bytes = int(rate * 2 * 35)
        self._vad_residual_bytes = b''
    def _download_and_extract(self, url, dest_dir, filename):
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        filepath = os.path.join(dest_dir, filename)
        if not os.path.exists(filepath):
            try:
                _stream_download(url, filepath, timeout=90)
                if filename.endswith('.tar.bz2'):
                    with tarfile.open(filepath, 'r:bz2') as tar:
                        extract_root = _get_base_models_path().resolve()
                        extract_root.mkdir(parents=True, exist_ok=True)
                        def safe_extract(tar_obj, path='.', members=None, *, numeric_owner=False):
                            root = Path(path).resolve()
                            for member in tar_obj.getmembers():
                                member_path = (root / member.name).resolve()
                                try:
                                    member_path.relative_to(root)
                                except ValueError as exc:
                                    raise Exception('Attempted Path Traversal in Tar File') from exc
                            tar_obj.extractall(path, members, numeric_owner=numeric_owner)
                        safe_extract(tar, str(extract_root))
                elif filename.endswith('.zip'):
                    extract_root = _get_base_models_path().resolve()
                    abs_dest = str(extract_root)
                    with zipfile.ZipFile(filepath, 'r') as zip_ref:
                        for member in zip_ref.namelist():
                            if not os.path.abspath(os.path.join(abs_dest, member)).startswith(abs_dest + os.sep):
                                raise Exception(f'Обнаружена попытка path traversal в zip: {member}')
                        zip_ref.extractall(abs_dest)
            except Exception:
                if os.path.exists(filepath): os.remove(filepath)
    def _ensure_models_downloaded(self):
        models_base = _get_base_models_path()
        self.stt_dir = models_base / 'sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16'
        os.makedirs(str(self.stt_dir), exist_ok=True)
        needed = ['model.int8.onnx', 'tokens.txt']
        missing = [f for f in needed if not os.path.exists(os.path.join(self.stt_dir, f))]
        if missing:
            _notify_model_download(active=True)
        for fname in needed:
            if not os.path.exists(os.path.join(self.stt_dir, fname)):
                url = f'https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16/resolve/main/{fname}'
                self._download_and_extract(url, self.stt_dir, fname)
        if missing:
            # _download_and_extract swallows its own exceptions (just deletes
            # the partial file) — re-check on disk rather than relying on it
            # to report failure.
            still_missing = [f for f in needed if not os.path.exists(os.path.join(self.stt_dir, f))]
            _notify_model_download(active=False, failed=bool(still_missing))
        try:
            self._ensure_vad_downloaded()
        except Exception as e:
            # A VAD hiccup must not take STT down with it — this is just an
            # opportunistic pre-fetch; vad_check()'s own _lazy_load_vad()
            # independently retries (with its own cooldown/notify) the next
            # time it's actually needed. Previously this raised unguarded and
            # aborted _lazy_load_stt() before it ever reached the STT model
            # construction below, even though the STT files themselves had
            # already downloaded fine in the loop above.
            _log.warning('VAD pre-fetch failed (STT unaffected, will retry lazily): %s', e)
    def _lazy_load_stt(self):
        if self.recognizer is not None: return
        with self._reload_lock:
            if self.recognizer is not None: return
            import sherpa_onnx
            self._ensure_models_downloaded()
            model_path = os.path.join(self.stt_dir, 'model.int8.onnx')
            tokens_path = os.path.join(self.stt_dir, 'tokens.txt')
            # NeMo CTC models don't support hotwords/context-biasing in sherpa-onnx
            # (that's transducer-only) — always greedy_search, no hotwords_file.
            # See reload_with_hotwords()/clear_hotwords() below, which are no-ops
            # here for the same reason.
            kwargs = dict(model=model_path, tokens=tokens_path, num_threads=_onnx_threads(), sample_rate=16000, feature_dim=80, decoding_method='greedy_search', debug=False, provider='cpu')
            try:
                _log.info('Loading STT from %s', model_path)
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(**kwargs)
                _log.info('STT loaded successfully')
            except Exception as e:
                _log.critical('CRITICAL: failed to load STT: %s', e, exc_info=True)
                _schedule_retry(self, self._lazy_load_stt)
                raise
    def reload_with_hotwords(self, words: list[str], score: float=2.0):
        # No-op: the NeMo CTC model used here has no hotwords/context-biasing
        # support in sherpa-onnx, so there is nothing to reload. (ASR_Vosk's
        # version of this method does work, via Vosk's grammar restriction.)
        pass
    def clear_hotwords(self):
        pass
    def switch_language(self, lang: str) -> None:
        pass
    def warmup_stt(self):
        threading.Thread(target=self._lazy_load_stt, daemon=True).start()
        self._warmup_vad_async()
    def reset(self):
        self._audio_buffer.clear()
        self._vad_reset()
    def accept(self, data):
        if isinstance(data, memoryview): data = bytes(data)
        self._audio_buffer.extend(data)
        if len(self._audio_buffer) > self._max_buffer_bytes:
            overflow = len(self._audio_buffer) - self._max_buffer_bytes
            del self._audio_buffer[:overflow]
        return False
    def result_json(self):
        return {'text': self.transcribe(self._audio_buffer)}
    def partial_json(self):
        return {'partial': ''}
    def transcribe(self, audio_buffer):
        if not audio_buffer: return ''
        if not self._reload_lock.acquire(blocking=True, timeout=15): return ''
        text = ''
        try:
            self._lazy_load_stt()
            samples = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
            stream = self.recognizer.create_stream()
            stream.accept_waveform(self.rate, samples)
            self.recognizer.decode_stream(stream)
            text = stream.result.text.strip()
        finally:
            self._reload_lock.release()
        if text.startswith('<|'): text = _CLEANUP_RE.sub('', text).strip()
        self._audio_buffer.clear()
        return text
    def transcribe_raw(self, audio_bytes: bytes) -> str:
        if not audio_bytes: return ''
        if not self._reload_lock.acquire(blocking=True, timeout=15): return ''
        text = ''
        try:
            self._lazy_load_stt()
            samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            stream = self.recognizer.create_stream()
            stream.accept_waveform(self.rate, samples)
            self.recognizer.decode_stream(stream)
            text = stream.result.text.strip()
        finally:
            self._reload_lock.release()
        if text.startswith('<|'): text = _CLEANUP_RE.sub('', text).strip()
        return text
_VOSK_LANG_MODELS = {
    'ru': {'dir': 'vosk-model-small-ru-0.22', 'url': 'https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip'},
}

class ASR_Vosk(_SileroVadMixin):
    def __init__(self, rate: int=16000) -> None:
        self.rate = rate
        self._rec, self._model = None, None
        self._lock = threading.Lock()
        self._audio_buffer = bytearray()
        self._hotwords = None
        self._lang = 'ru'
        # Silero VAD state (see _SileroVadMixin) — Vosk used to use a crude
        # RMS-loudness threshold instead; v6 is light enough to share the
        # same accurate neural VAD as the GigaAM engine.
        self.vad_dir = _get_base_models_path() / 'silero_vad'
        self.vad = None
        self._vad_lock = threading.RLock()
        self._vad_residual_bytes = b''
    def _lazy_load(self) -> None:
        if self._rec is not None:
            return
        import vosk
        model_cfg = _VOSK_LANG_MODELS.get(self._lang, _VOSK_LANG_MODELS['ru'])
        m_dir = _get_base_models_path() / model_cfg['dir']
        if not m_dir.exists():
            _log.info("Downloading Vosk model '%s'...", model_cfg['dir'])
            _notify_model_download(active=True)
            models_parent = m_dir.parent
            models_parent.mkdir(exist_ok=True)
            m_zip = models_parent / f"{model_cfg['dir']}.zip"
            req = urllib.request.Request(model_cfg['url'], headers={'User-Agent': 'Mozilla/5.0'})
            try:
                with urllib.request.urlopen(req, timeout=120) as r, open(m_zip, 'wb') as f:
                    shutil.copyfileobj(r, f, length=1024 * 1024)
                with zipfile.ZipFile(m_zip, 'r') as z:
                    dest_root = models_parent.resolve()
                    for member in z.infolist():
                        member_path = (dest_root / member.filename).resolve()
                        try:
                            member_path.relative_to(dest_root)
                        except ValueError as exc:
                            raise RuntimeError(f'Blocked zip path traversal: {member.filename}') from exc
                    z.extractall(str(dest_root))
                m_zip.unlink(missing_ok=True)
                _log.info('Vosk model download complete.')
                _notify_model_download(active=False)
            except Exception as e:
                _log.critical('CRITICAL ERROR downloading Vosk model: %s', e, exc_info=True)
                if m_zip.exists():
                    m_zip.unlink()
                _notify_model_download(active=False, failed=True)
                _schedule_retry(self, self._lazy_load)
                return
        try:
            self._model = vosk.Model(str(m_dir))
            _log.info("Vosk model '%s' ready.", self._lang)
        except Exception as e:
            _log.error('Failed to load Vosk model %s: %s', m_dir, e, exc_info=True)
            _schedule_retry(self, self._lazy_load)
            return
        if self._hotwords:
            self._rec = vosk.KaldiRecognizer(self._model, self.rate, json.dumps(self._hotwords + ["[unk]"]))
        else:
            self._rec = vosk.KaldiRecognizer(self._model, self.rate)
        self._rec.SetMaxAlternatives(0); self._rec.SetWords(False)
    def switch_language(self, lang: str) -> None:
        with self._lock:
            if lang not in _VOSK_LANG_MODELS or lang == self._lang:
                return
            self._rec = None
            self._model = None
            self._lang = lang
    def warmup_stt(self) -> None:
        def _warm():
            with self._lock: self._lazy_load()
        threading.Thread(target=_warm, daemon=True).start()
        self._warmup_vad_async()
    def reload_with_hotwords(self, words: list[str], score: float = 2.0) -> None:  # score unused but kept for interface compat
        with self._lock:
            self._hotwords = words
            self._rec = None
            self._lazy_load()
    def clear_hotwords(self) -> None:
        with self._lock:
            self._hotwords = None
            self._rec = None
            self._lazy_load()
    def reset(self) -> None:
        self._audio_buffer.clear()
        self._vad_reset()
    def accept(self, data: bytes) -> bool:
        if isinstance(data, memoryview): data = bytes(data)
        self._audio_buffer.extend(data)
        return False
    def result_json(self) -> dict:
        return {'text': self.transcribe(self._audio_buffer)}
    def partial_json(self) -> dict:
        return {'partial': ''}
    def transcribe(self, audio_buffer) -> str:
        if not audio_buffer: return ''
        result = self.transcribe_raw(bytes(audio_buffer))
        self._audio_buffer.clear()
        return result
    def transcribe_raw(self, audio_bytes: bytes) -> str:
        if not audio_bytes: return ''
        with self._lock:
            self._lazy_load()
            self._rec.AcceptWaveform(audio_bytes)
            res = json.loads(self._rec.FinalResult())
            self._rec.Reset()
        return res.get('text', '').strip()
