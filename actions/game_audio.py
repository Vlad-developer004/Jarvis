import numpy as np
import json
from pathlib import Path
_RATE = 16000
_N_MFCC = 13
_N_FILTERS = 26
_NFFT = 512
_HOP = 160
_WIN = 400
_TEMPLATES_DIR = Path('data') / 'game_profiles' / 'audio_templates'
_MIN_SAMPLES = 2
_MATCH_THRESHOLD = 0.82
_MIN_READY_COMMANDS = 3
_MIN_GAP = 0.08
_fbank_cache: dict = {}
def _get_fbank(rate: int) -> np.ndarray:
    if rate in _fbank_cache:
        return _fbank_cache[rate]
    n = _N_FILTERS
    low_mel = 2595 * np.log10(1 + 80.0 / 700)
    high_mel = 2595 * np.log10(1 + rate / 2 / 700)
    mel_pts = np.linspace(low_mel, high_mel, n + 2)
    hz_pts = 700 * (10 ** (mel_pts / 2595) - 1)
    bins = np.floor((_NFFT + 1) * hz_pts / rate).astype(int)
    fbank = np.zeros((n, _NFFT // 2 + 1))
    for m in range(1, n + 1):
        lo, mid, hi = (bins[m - 1], bins[m], bins[m + 1])
        for k in range(lo, mid):
            fbank[m - 1, k] = (k - lo) / (mid - lo + 1e-10)
        for k in range(mid, hi):
            fbank[m - 1, k] = (hi - k) / (hi - mid + 1e-10)
    _fbank_cache[rate] = fbank
    return fbank
def extract_features(audio_bytes: bytes, rate: int=_RATE) -> np.ndarray:
    from scipy.fftpack import dct
    if not audio_bytes or len(audio_bytes) < 2:
        return np.zeros(_N_MFCC * 3, dtype=np.float32)
    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size == 0:
        return np.zeros(_N_MFCC * 3, dtype=np.float32)
    samples = np.append(samples[0], samples[1:] - 0.97 * samples[:-1])
    n_frames = max(1, (len(samples) - _WIN) // _HOP)
    idx = np.arange(_WIN)[None, :] + np.arange(n_frames)[:, None] * _HOP
    idx = np.clip(idx, 0, len(samples) - 1)
    frames = samples[idx] * np.hamming(_WIN)
    mag2 = np.abs(np.fft.rfft(frames, _NFFT)) ** 2
    fb = np.dot(mag2, _get_fbank(rate).T)
    fb = np.where(fb < 1e-10, 1e-10, fb)
    log_fb = 20 * np.log10(fb)
    mfcc = dct(log_fb, type=2, axis=1, norm='ortho')[:, :_N_MFCC]
    mfcc -= np.mean(mfcc, axis=0)
    delta = np.diff(mfcc, axis=0) if len(mfcc) > 1 else np.zeros((1, _N_MFCC))
    vec = np.concatenate([np.mean(mfcc, axis=0), np.std(mfcc, axis=0), np.mean(delta, axis=0)]).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec / (norm + 1e-10)
class GameAudioMatcher:
    def __init__(self):
        self._vecs: dict[str, list[np.ndarray]] = {}
        self._profile: str = ''
    def set_profile(self, profile_name: str):
        self._profile = profile_name
        self._vecs = {}
        path = self._path()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding='utf-8'))
                loaded: dict[str, list[np.ndarray]] = {}
                for name, vectors in raw.items():
                    if not isinstance(name, str) or not isinstance(vectors, list):
                        continue
                    prepared: list[np.ndarray] = []
                    for vec in vectors:
                        arr = np.asarray(vec, dtype=np.float32)
                        if arr.ndim == 1 and arr.size == _N_MFCC * 3:
                            prepared.append(arr)
                    if prepared:
                        loaded[name] = prepared
                self._vecs = loaded
            except Exception as e:
                pass
    def clear(self):
        self._vecs = {}
        self._profile = ''
    def reset_profile(self):
        p = self._path()
        if p.exists():
            p.unlink()
        self._vecs = {}
    def _path(self) -> Path:
        _TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        return _TEMPLATES_DIR / f'{self._profile}.json'
    def add_sample(self, name: str, audio_bytes: bytes):
        vec = extract_features(audio_bytes)
        if name not in self._vecs:
            self._vecs[name] = []
        samples = self._vecs[name]
        samples.append(vec)
        if len(samples) > 5:
            samples.pop(0)
        try:
            payload = {k: [vec.tolist() for vec in vals] for k, vals in self._vecs.items()}
            self._path().write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        except Exception as e:
            pass
        ready = self.ready_count()
    def match(self, audio_bytes: bytes) -> tuple[str, float] | None:
        ready = {n: v for n, v in self._vecs.items() if len(v) >= _MIN_SAMPLES}
        if len(ready) < _MIN_READY_COMMANDS:
            return None
        vec = extract_features(audio_bytes)
        scores: list[tuple[float, str]] = []
        for name, templates in ready.items():
            mean_template = np.mean(templates, axis=0)
            mean_template /= np.linalg.norm(mean_template) + 1e-10
            score = float(np.dot(vec, mean_template))
            scores.append((score, name))
        scores.sort(reverse=True)
        best_score, best_name = scores[0]
        second_score = scores[1][0] if len(scores) > 1 else -1.0
        if best_score >= _MATCH_THRESHOLD and best_score - second_score >= _MIN_GAP:
            return (best_name, best_score)
        return None
    def ready_count(self) -> int:
        return sum((1 for v in self._vecs.values() if len(v) >= _MIN_SAMPLES))
game_matcher = GameAudioMatcher()
