"""Local audio fingerprinting — a simplified constellation/landmark hasher in
the same family as Shazam/Dejavu, using only numpy (no scipy/chromaprint).

Used so song recognition has a local, offline-capable cache of previously
recognized songs (actions/song_cache.py) checked before ever calling out to
Shazam/AudD (see actions/song_id.py).

Algorithm, in short:
  1. STFT magnitude spectrogram of the (mono, TARGET_RATE) signal.
  2. Local-maxima peaks along the frequency axis of each time frame ("stars"
     in the constellation), above an adaptive amplitude floor.
  3. Each peak is paired with a handful of nearby-in-time peaks ("fan-out");
     each pair (f1, f2, dt) is packed into one 64-bit int hash. Two clips of
     the same song produce mostly the same hashes at a constant time offset,
     which is what actions/song_cache.py's matching step looks for.
"""
import numpy as np

TARGET_RATE = 11025          # low enough to be cheap, high enough for pop/rock fingerprinting
WINDOW_SIZE = 4096
HOP = 2048                   # 50% overlap
PEAK_FREQ_RADIUS = 10         # bins; a peak must be a local max within +/- this many bins
FAN_VALUE = 5                 # how many later peaks each anchor peak pairs with
MIN_TIME_DELTA = 1            # frames
MAX_TIME_DELTA = 100           # frames (~18s at HOP=2048/TARGET_RATE=11025)
MAX_PEAKS = 6000               # cap per clip so one very loud/dense track doesn't blow up the DB

_FREQ_BITS = 12
_DT_BITS = 10
_FREQ_MASK = (1 << _FREQ_BITS) - 1
_DT_MASK = (1 << _DT_BITS) - 1


def _spectrogram(samples: np.ndarray) -> np.ndarray:
    """samples: float32 mono @ TARGET_RATE. Returns (T, F) magnitude array."""
    n = len(samples)
    if n < WINDOW_SIZE:
        return np.zeros((0, WINDOW_SIZE // 2 + 1), dtype=np.float32)
    window = np.hanning(WINDOW_SIZE).astype(np.float32)
    n_frames = 1 + (n - WINDOW_SIZE) // HOP
    # Build all frames as one strided view instead of a Python loop.
    idx = np.arange(WINDOW_SIZE)[None, :] + (np.arange(n_frames) * HOP)[:, None]
    frames = samples[idx] * window
    spec = np.fft.rfft(frames, axis=1)
    return np.abs(spec).astype(np.float32)


def _find_peaks(spectro: np.ndarray) -> np.ndarray:
    """Returns an (N, 3) array of (time_frame, freq_bin, amplitude), sorted by time."""
    if spectro.shape[0] == 0:
        return np.zeros((0, 3), dtype=np.float64)
    log_spec = np.log1p(spectro)

    # Local-maxima mask along the frequency axis, vectorized (no scipy):
    # compare each column against a running max of its +/- radius neighbors,
    # built via successive np.roll instead of a per-bin Python loop.
    running_max = log_spec.copy()
    for shift in range(1, PEAK_FREQ_RADIUS + 1):
        left = np.roll(log_spec, shift, axis=1)
        left[:, :shift] = -np.inf
        right = np.roll(log_spec, -shift, axis=1)
        right[:, -shift:] = -np.inf
        np.maximum(running_max, left, out=running_max)
        np.maximum(running_max, right, out=running_max)

    is_peak = log_spec >= running_max
    # Adaptive floor: ignore near-silence / noise-floor bins so quiet
    # recordings don't fingerprint mostly noise.
    floor = log_spec.mean() + 0.5 * log_spec.std()
    is_peak &= log_spec > floor

    t_idx, f_idx = np.nonzero(is_peak)
    if t_idx.size == 0:
        return np.zeros((0, 3), dtype=np.float64)
    amps = log_spec[t_idx, f_idx]

    if t_idx.size > MAX_PEAKS:
        keep = np.argpartition(amps, -MAX_PEAKS)[-MAX_PEAKS:]
        t_idx, f_idx, amps = t_idx[keep], f_idx[keep], amps[keep]

    order = np.argsort(t_idx, kind='stable')
    return np.stack([t_idx[order], f_idx[order], amps[order]], axis=1)


def _hash_peaks(peaks: np.ndarray) -> list[tuple[int, int]]:
    """peaks: (N, 3) sorted by time. Returns [(hash, anchor_time_frame), ...]."""
    hashes: list[tuple[int, int]] = []
    n = len(peaks)
    times = peaks[:, 0].astype(np.int64)
    freqs = peaks[:, 1].astype(np.int64)
    for i in range(n):
        t1, f1 = times[i], freqs[i]
        paired = 0
        for j in range(i + 1, n):
            dt = times[j] - t1
            if dt < MIN_TIME_DELTA:
                continue
            if dt > MAX_TIME_DELTA:
                break  # times[] is sorted ascending, nothing further can be in range
            f2 = freqs[j]
            h = ((f1 & _FREQ_MASK) << (_FREQ_BITS + _DT_BITS)) | ((f2 & _FREQ_MASK) << _DT_BITS) | (dt & _DT_MASK)
            hashes.append((int(h), int(t1)))
            paired += 1
            if paired >= FAN_VALUE:
                break
    return hashes


def fingerprint_pcm(raw: bytes, rate: int, channels: int = 1) -> list[tuple[int, int]]:
    """raw: 16-bit PCM bytes at the given rate/channels. Resamples to
    TARGET_RATE mono internally. Returns [(hash, time_frame), ...]."""
    if not raw:
        return []
    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    samples = samples.astype(np.float32) / 32768.0

    if rate != TARGET_RATE:
        import audioop
        pcm16 = (samples * 32768.0).astype(np.int16).tobytes()
        pcm16, _ = audioop.ratecv(pcm16, 2, 1, rate, TARGET_RATE, None)
        samples = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32) / 32768.0

    spectro = _spectrogram(samples)
    peaks = _find_peaks(spectro)
    return _hash_peaks(peaks)
