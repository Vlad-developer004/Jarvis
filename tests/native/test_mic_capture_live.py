"""The real capture program on the real microphone: chunk sizes, pace and level. Skipped without the sidecar or a working microphone."""
import time

import numpy as np
import pytest

from core import native, native_audio

pytestmark = [pytest.mark.skipif(native.sidecar_path('audio') is None, reason='jarvis_audio.exe is not built'), pytest.mark.timeout(60)]


@pytest.fixture
def mic():
    try:
        m = native_audio.open_mic(16000, 512)
    except OSError as e:
        pytest.skip(f'no usable microphone: {e}')
    yield m
    m.close()


def test_chunks_are_exact_and_arrive_at_the_chunk_rate(mic):
    stamps, sizes = [], set()
    for _ in range(64):   # about two seconds
        stamps.append(time.perf_counter())
        sizes.add(len(mic.read(512)))
    assert sizes == {1024}
    span = stamps[-1] - stamps[8]
    assert 0.9 * 0.032 * 55 < span < 1.3 * 0.032 * 55
    assert mic.device


def test_the_signal_is_real_audio_not_zeros_or_garbage(mic):
    data = np.frombuffer(b''.join(mic.read(512) for _ in range(40)), dtype=np.int16).astype(np.float64)
    assert np.isfinite(data).all() and data.std() > 0.0 and abs(data.mean()) < 2000


def test_a_named_device_that_does_not_exist_falls_back_to_the_default():
    m = native_audio.open_mic(16000, 512, 'definitely not a microphone name')
    try:
        assert m.device and len(m.read(512)) == 1024
    finally:
        m.close()


def test_the_device_listing_has_the_default_marked():
    found = native_audio.list_devices()
    assert found and found['inputs'] and any(d['default'] for d in found['inputs'])
    assert all(d['name'] for d in found['inputs'] + found['outputs'])
