import time
import numpy as np
from typing import Optional
def rms_int16(data_bytes: bytes) -> float:
    if not data_bytes:
        return 0.0
    s = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(s * s)))
def _load_audio_settings() -> dict:
    try:
        import json, os
        p = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}
def open_input_stream(pa, rate: int, chunk_frames: int, device_index: int | None = None):
    if device_index is None:
        s = _load_audio_settings()
        di = s.get('audio_input_device_index')
        if isinstance(di, int):
            device_index = di
    kw = dict(format=8, channels=1, rate=rate, input=True, frames_per_buffer=chunk_frames)
    if isinstance(device_index, int):
        kw['input_device_index'] = device_index
    return pa.open(**kw)
def now() -> float:
    return time.perf_counter()
