from __future__ import annotations
import os
import sys
import re
import threading
import urllib.request
import tarfile
import zipfile
import json
import shutil
from pathlib import Path
import numpy as np
_CLEANUP_RE = re.compile(r'<\|.*?\|>')
def _get_base_models_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / 'models'
    return Path('models')
def _onnx_threads() -> int:
    try:
        from pathlib import Path
        p = Path('data') / 'jarvis_settings.json'
        if p.exists():
            data = json.loads(p.read_text(encoding='utf-8'))
            val = int(data.get('onnx_threads', 0))
            if val > 0:
                return max(1, min(val, (os.cpu_count() or 2)))
    except Exception:
        pass
    cpus = os.cpu_count() or 2
    if cpus >= 12:
        return 3
    return max(1, min(2, cpus))
def _stream_download(url: str, filepath: str, timeout: int = 60) -> None:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as response, open(filepath, 'wb') as out_file:
        shutil.copyfileobj(response, out_file, length=1024 * 1024)
class ASR:
    def __init__(self, stt_model_path, vad_model_path, rate):
        self.rate = rate
        models_base = _get_base_models_path()
        self.stt_dir = models_base / (os.path.basename(stt_model_path) if stt_model_path else 'sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16')
        self.vad_dir = models_base / 'silero_vad'
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
        for fname in ['model.int8.onnx', 'tokens.txt']:
            if not os.path.exists(os.path.join(self.stt_dir, fname)):
                url = f'https://huggingface.co/csukuangfj/sherpa-onnx-nemo-ctc-giga-am-v3-russian-2025-12-16/resolve/main/{fname}'
                self._download_and_extract(url, self.stt_dir, fname)
        os.makedirs(self.vad_dir, exist_ok=True)
        if not os.path.exists(os.path.join(self.vad_dir, 'silero_vad.onnx')):
            url = 'https://huggingface.co/csukuangfj/vad/resolve/main/silero_vad.onnx'
            self._download_and_extract(url, self.vad_dir, 'silero_vad.onnx')
    def _lazy_load_vad(self):
        if self.vad is not None: return
        with self._vad_lock:
            if self.vad is not None: return
            import sherpa_onnx
            self._ensure_models_downloaded()
            config = sherpa_onnx.VadModelConfig()
            config.silero_vad.model = os.path.join(self.vad_dir, 'silero_vad.onnx')
            config.silero_vad.min_silence_duration = getattr(self, '_vad_min_silence', 0.25)
            config.silero_vad.min_speech_duration = getattr(self, '_vad_min_speech', 0.2)
            config.sample_rate = self.rate
            config.num_threads = _onnx_threads()
            with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                f.write(f"ASR: Loading VAD from {config.silero_vad.model}\n")
            self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)
    def _lazy_load_stt(self):
        if self.recognizer is not None: return
        with self._reload_lock:
            if self.recognizer is not None: return
            import sherpa_onnx
            self._ensure_models_downloaded()
            model_path = os.path.join(self.stt_dir, 'model.int8.onnx')
            tokens_path = os.path.join(self.stt_dir, 'tokens.txt')
            hotwords_file = getattr(self, '_hotwords_file', '')
            use_beam = bool(hotwords_file)
            kwargs = dict(model=model_path, tokens=tokens_path, num_threads=_onnx_threads(), sample_rate=16000, feature_dim=80, decoding_method='modified_beam_search' if use_beam else 'greedy_search', debug=False, provider='cpu')
            if use_beam:
                kwargs['hotwords_file'] = hotwords_file
                kwargs['hotwords_score'] = getattr(self, '_hotwords_score', 2.0)
            try:
                with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                    f.write(f"ASR: Loading STT from {model_path}\n")
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(**kwargs)
                with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                    f.write("ASR: STT Loaded successfully\n")
            except TypeError:
                kwargs.pop('hotwords_file', None); kwargs.pop('hotwords_score', None)
                kwargs['decoding_method'] = 'greedy_search'
                self.recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(**kwargs)
                with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                    f.write("ASR: STT Loaded with greedy fallback\n")
            except Exception as e:
                with open('logs/debug_init.log', 'a', encoding='utf-8') as f:
                    f.write(f"ASR: CRITICAL ERROR loading STT: {e}\n")
                raise
    def set_vad_mode(self, game_mode: bool):
        with self._vad_lock:
            self._vad_min_silence = 0.30 if game_mode else 0.25
            self._vad_min_speech = 0.20 if game_mode else 0.10
            self.vad = None
    def reload_with_hotwords(self, words: list[str], score: float=2.0):
        if not words: return
        import tempfile, pathlib
        hw_path = pathlib.Path(tempfile.gettempdir()) / 'jarvis_hotwords.txt'
        hw_path.write_text('\n'.join(words), encoding='utf-8')
        with self._reload_lock:
            self._hotwords_file = str(hw_path)
            self._hotwords_score = score
            self.recognizer = None
            self._lazy_load_stt()
    def clear_hotwords(self):
        with self._reload_lock:
            self._hotwords_file = ''
            self.recognizer = None
            self._lazy_load_stt()
    def warmup_stt(self):
        threading.Thread(target=self._lazy_load_stt, daemon=True).start()
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
    def reset(self):
        self._audio_buffer.clear()
        with self._vad_lock:
            self._vad_residual_bytes = b''
            if self.vad is not None: self.vad.reset()
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
class ASR_Vosk:
    def __init__(self, rate: int=16000) -> None:
        self.rate = rate
        self._rec, self._model = None, None
        self._lock = threading.Lock()
        self._audio_buffer = bytearray()
        self._vad_thresh = 80
        self._hotwords = None
    def _lazy_load(self) -> None:
        if self._rec is not None: return
        import vosk
        m_dir = _get_base_models_path() / 'vosk-model-small-ru-0.22'
        if not m_dir.exists():
            print(f"ASR-VOSK: Model directory {m_dir} not found. Attempting download...")
            models_parent = m_dir.parent
            models_parent.mkdir(exist_ok=True)
            m_zip = models_parent / 'vosk-model-small-ru-0.22.zip'
            req = urllib.request.Request('https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip', headers={'User-Agent': 'Mozilla/5.0'})
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
                print("ASR-VOSK: Model downloaded and extracted successfully.")
            except Exception as e:
                print(f"ASR-VOSK: CRITICAL ERROR downloading model: {e}")
                if m_zip.exists(): m_zip.unlink()
        try:
            self._model = vosk.Model(str(m_dir))
        except Exception as e:
            print(f"ASR-VOSK: FAILED to load model from {m_dir}: {e}")
            return
        if self._hotwords:
            self._rec = vosk.KaldiRecognizer(self._model, self.rate, json.dumps(self._hotwords + ["[unk]"]))
        else:
            self._rec = vosk.KaldiRecognizer(self._model, self.rate)
        self._rec.SetMaxAlternatives(0); self._rec.SetWords(False)
    def warmup_stt(self) -> None:
        def _warm():
            with self._lock: self._lazy_load()
        threading.Thread(target=_warm, daemon=True).start()
    def vad_check(self, audio_chunk: bytes) -> float:
        if not audio_chunk: return 0.0
        samples = np.frombuffer(audio_chunk, dtype=np.int16)
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        return 1.0 if rms > self._vad_thresh else 0.0
    def set_vad_mode(self, game_mode: bool) -> None:
        self._vad_thresh = 250 if game_mode else 80
    def reload_with_hotwords(self, words: list[str], score: float=2.0) -> None:
        with self._lock:
            self._hotwords = words
            self._rec = None
            self._lazy_load()
    def clear_hotwords(self) -> None:
        with self._lock:
            self._hotwords = None
            self._rec = None
            self._lazy_load()
    def reset(self) -> None: self._audio_buffer.clear()
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
