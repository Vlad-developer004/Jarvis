"""Silero v5 (Russian) without PyTorch: the community `silero-onnx-tts` package runs the same voices through ONNX Runtime.

`OnnxSileroModel` is the only TTS backend: Russian only, there is no Ukrainian voice for now. Any failure marks the backend as broken for the rest
of the session (Jarvis stays silent). The models (about 300 MB) are downloaded in the background on first use, each file checked against the
SHA-256 pinned in data/model_hashes.json; until then nothing is spoken.
Models: github.com/some1-in-here/silero-tts-onnx (CC BY-NC-SA 4.0; voices by Silero)."""
from __future__ import annotations

import contextlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import re
import sys
import threading
import time

from core.logging_setup import get_logger

_log = get_logger('tts_onnx')

VERSION = 'v5_ru'
RELEASE_URL = 'https://github.com/some1-in-here/silero-tts-onnx/releases/download/v0.3.0/'
FILES = ('acoustic_v5_ru.onnx', 'vocoder_v5_ru.onnx', 'istft_48k.onnx', 'silero_stress.onnx', 'ngram_core.onnx')
_WARMUP = ('Замок на двери старый, а в замке жили короли.', '<speak>Привет<break time="300ms"/>мир</speak>')     # touches the stress, homograph and pause paths

_lock = threading.Lock()
_broken = False
_downloading = False
_ready = False
_last_probe = 0.0


def model_dir() -> str:
    from config_pack.config import get_project_root
    return os.path.join(get_project_root(), 'models', 'silero_onnx')


def files_ready() -> bool:
    """All model files are on disk (probed at most every 30 s while some are missing)."""
    global _ready, _last_probe
    if _ready:
        return True
    now = time.time()
    if now - _last_probe < 30:
        return False
    _last_probe = now
    d = model_dir()
    _ready = all(os.path.isfile(os.path.join(d, f)) and os.path.getsize(os.path.join(d, f)) > 1024 for f in FILES)
    return _ready


def package_available() -> bool:
    return importlib.util.find_spec('silero_onnx') is not None


def usable(lang: str) -> bool:
    """Should this language be spoken by the ONNX backend right now."""
    return lang == 'ru' and not _broken and package_available() and files_ready()


def mark_broken(reason: object) -> None:
    global _broken
    _broken = True
    _log.warning('ONNX voice disabled for this session: %s', reason)


def start_download() -> None:
    """Fetches missing model files on a background thread (once at a time). Nothing happens when the backend is switched off or the package is missing."""
    global _downloading
    if _ready or _broken or not package_available():
        return
    with _lock:
        if _downloading:
            return
        _downloading = True
    threading.Thread(target=_download, name='TTS-OnnxDownload', daemon=True).start()


def _download() -> None:
    global _downloading, _ready
    try:
        import requests
        from core.download import require_https, verify_pinned
        d = model_dir()
        os.makedirs(d, exist_ok=True)
        for name in FILES:
            dest = os.path.join(d, name)
            if os.path.isfile(dest) and os.path.getsize(dest) > 1024:
                continue
            tmp = dest + '.part'
            _log.info('downloading %s', name)
            with requests.get(require_https(RELEASE_URL + name), stream=True, timeout=(10, 60)) as r:
                r.raise_for_status()
                want = int(r.headers.get('Content-Length') or 0)
                with open(tmp, 'wb') as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            if want and os.path.getsize(tmp) != want:
                raise OSError(f'{name}: incomplete download')
            verify_pinned(tmp, name)         # a pinned hash that does not match raises; the file is discarded below
            os.replace(tmp, dest)
        _ready = True
        _log.info('ONNX voice files are in place')
    except Exception as ex:
        _log.warning('ONNX voice download failed: %s', ex)
        for name in FILES:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(model_dir(), name + '.part'))
    finally:
        _downloading = False


_GUARD = '"torch" not in'


class _LiftGuardLoader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):         # no bytecode cache: it would carry the original assert
        data = self.get_data(self.path)
        return compile(data.decode('utf-8').replace(_GUARD, '"torch_guard_lifted" not in'), self.path, 'exec', dont_inherit=True)


class _LiftGuardFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        if name != 'silero_onnx' and not name.startswith('silero_onnx.'):
            return None
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is not None and spec.origin and spec.origin.endswith('.py'):
            spec.loader = _LiftGuardLoader(spec.name, spec.origin)
        return spec


def _import_silero():
    """The package asserts at import that torch is NOT loaded. Jarvis no longer loads torch, but the loader that turns those asserts into no-ops
    stays as a safeguard (some dev tools still import torch). Only names under silero_onnx are touched."""
    if not any(isinstance(f, _LiftGuardFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _LiftGuardFinder())
    import silero_onnx
    return silero_onnx


class _LazyPattern:
    """A regex that compiles on first use. The stress module compiles ~1500 per-word patterns up front (about 3 s); a sentence touches a handful."""
    __slots__ = ('_args', '_pattern')

    def __init__(self, *args):
        self._args, self._pattern = args, None

    def __getattr__(self, name):
        if self._pattern is None:
            self._pattern = re.compile(*self._args)         # two threads may both compile: harmless
        return getattr(self._pattern, name)


class _LazyRe:
    """Stands in for `re` inside silero_onnx.homograph_solver while the model is built: compile() is deferred, everything else is the real module."""
    compile = staticmethod(_LazyPattern)

    def __getattr__(self, name):
        return getattr(re, name)


class OnnxSileroModel:
    """The torch model's `save_wav(text|ssml_text, speaker, sample_rate, audio_path[, speech_rate])` on top of silero_onnx."""
    backend = 'onnx'

    def __init__(self, directory: str | None = None):
        self.broken = False
        self._tts = self._build(directory or model_dir())

    @staticmethod
    def _build(directory: str):
        SileroTTS = _import_silero().SileroTTS

        def make():
            tts = SileroTTS(model_dir=directory, version=VERSION)
            for text in _WARMUP:                                  # sessions are created lazily: make them all now
                tts.synthesize(text, speaker='eugene', ssml=text.startswith('<speak'))
            return tts
        # The graph optimizer is switched off for these sessions: onnxruntime 1.23 fails to load one of the graphs otherwise (a fused kernel without
        # the double type it needs), and with it off the speed is the same or better. SileroTTS builds its sessions lazily, so they are all created
        # by the warm-up inside this block.
        import onnxruntime as ort
        original = ort.SessionOptions

        class _NoOptimize(original):
            def __init__(self):
                super().__init__()
                self.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
                self.enable_cpu_mem_arena = False         # the arena keeps every peak buffer: about 85 MB less resident, same speed
        ort.SessionOptions = _NoOptimize
        import silero_onnx.homograph_solver as solver
        real_re, solver.re = solver.re, _LazyRe()               # the ~1500 homograph patterns compile on first use instead of here
        try:
            return make()
        except SystemExit as ex:                     # the package reports a model that fails to load with SystemExit
            raise RuntimeError(str(ex)) from None
        finally:
            ort.SessionOptions = original
            solver.re = real_re

    @property
    def speakers(self) -> list[str]:
        return list(self._tts.speakers)

    def save_wav(self, text: str | None = None, ssml_text: str | None = None, speaker: str = 'eugene', sample_rate: int = 48000,
                 audio_path: str = '', speech_rate: float | None = None) -> str:
        import numpy as np
        import soundfile as sf
        payload, ssml = ssml_text or text or '', bool(ssml_text)
        if not payload.strip():
            raise ValueError('empty text')
        try:
            if speech_rate and abs(speech_rate - 1.0) >= 0.02:        # speed > 1 is faster, as in the torch model
                body = payload if not ssml else payload.replace('<speak>', '', 1).rsplit('</speak>', 1)[0]
                payload, ssml = f'<speak><prosody rate="{int(round(speech_rate * 100))}%">{body}</prosody></speak>', True
            audio, _ = self._tts.synthesize(payload, speaker=speaker, sample_rate=sample_rate, ssml=ssml)
            sf.write(audio_path, np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0), sample_rate, format='WAV', subtype='PCM_16')      # the cache writes to *.wav.tmp
        except ValueError:
            raise                      # bad SSML or text: the caller retries as plain text, the backend is fine
        except (Exception, SystemExit) as ex:
            self.broken = True
            mark_broken(ex)
            raise RuntimeError(str(ex)) from None
        return audio_path


def load() -> OnnxSileroModel:
    t = time.time()
    model = OnnxSileroModel()
    _log.info('ONNX voice loaded in %.1f s (Russian)', time.time() - t)
    return model


def keep(model: object, lang: str) -> bool:
    """Is the loaded model still usable for `lang`."""
    return not getattr(model, 'broken', False) and usable(lang)
