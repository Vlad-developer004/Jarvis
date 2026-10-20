"""The torch-free Russian voice (core/speech/tts_onnx.py): the adapter's surface, the download check, and the import guard."""
import os
import sys
import types

import numpy as np
import pytest
import soundfile as sf

from core.speech import tts, tts_onnx


class FakeEngine:
    """Stands in for silero_onnx.SileroTTS."""
    speakers = ['eugene']

    def __init__(self, fail=None):
        self.calls, self.fail = [], fail

    def synthesize(self, text, speaker='eugene', sample_rate=48000, ssml=False):
        self.calls.append((text, speaker, sample_rate, ssml))
        if self.fail:
            raise self.fail
        return np.full(4800, 0.25, dtype=np.float32), None


def make(engine):
    m = tts_onnx.OnnxSileroModel.__new__(tts_onnx.OnnxSileroModel)
    m.broken, m._tts = False, engine
    return m


@pytest.fixture(autouse=True)
def _reset():
    tts_onnx._broken = False
    tts_onnx._setting_cache = (0.0, 'auto')
    yield
    tts_onnx._broken = False
    tts_onnx._setting_cache = (0.0, 'auto')


def test_save_wav_writes_a_wav_even_for_a_tmp_name_and_passes_the_speaker(tmp_path):
    eng = FakeEngine()
    path = str(tmp_path / 'x.wav.tmp')
    make(eng).save_wav(text='Привет', speaker='eugene', sample_rate=48000, audio_path=path)
    info = sf.info(path)
    assert info.format == 'WAV' and info.samplerate == 48000 and info.subtype == 'PCM_16' and abs(info.duration - 0.1) < 0.01
    assert eng.calls == [('Привет', 'eugene', 48000, False)]


def test_speech_rate_becomes_an_ssml_prosody_and_ssml_input_is_kept(tmp_path):
    eng = FakeEngine()
    m = make(eng)
    m.save_wav(text='Привет', audio_path=str(tmp_path / 'a.wav'), speech_rate=1.2)
    m.save_wav(ssml_text='<speak>Раз<break time="300ms"/>два</speak>', audio_path=str(tmp_path / 'b.wav'), speech_rate=0.8)
    m.save_wav(text='Привет', audio_path=str(tmp_path / 'c.wav'), speech_rate=1.0)
    assert eng.calls[0][0] == '<speak><prosody rate="120%">Привет</prosody></speak>' and eng.calls[0][3] is True
    assert eng.calls[1][0] == '<speak><prosody rate="80%">Раз<break time="300ms"/>два</prosody></speak>'
    assert eng.calls[2] == ('Привет', 'eugene', 48000, False)


def test_bad_text_does_not_disable_the_backend_but_a_runtime_failure_does(tmp_path):
    m = make(FakeEngine(fail=ValueError('Invalid <prosody> tag')))
    with pytest.raises(ValueError):
        m.save_wav(ssml_text='<speak>x</speak>', audio_path=str(tmp_path / 'a.wav'))
    assert not m.broken and not tts_onnx._broken
    with pytest.raises(ValueError):
        make(FakeEngine()).save_wav(text='   ', audio_path=str(tmp_path / 'a.wav'))
    m2 = make(FakeEngine(fail=SystemExit('silero-onnx: error: cannot load x.onnx')))
    with pytest.raises(RuntimeError):
        m2.save_wav(text='Привет', audio_path=str(tmp_path / 'a.wav'))
    assert m2.broken and tts_onnx._broken


def test_usable_follows_files_language_and_breakage(monkeypatch):
    monkeypatch.setattr(tts_onnx, 'package_available', lambda: True)
    monkeypatch.setattr(tts_onnx, 'files_ready', lambda: True)
    assert tts_onnx.usable('ru') and not tts_onnx.usable('uk')
    monkeypatch.setattr(tts_onnx, 'files_ready', lambda: False)
    assert not tts_onnx.usable('ru')
    monkeypatch.setattr(tts_onnx, 'files_ready', lambda: True)
    tts_onnx.mark_broken('test')
    assert not tts_onnx.usable('ru')


def test_keep_drops_a_broken_model_or_one_for_an_unsupported_language(monkeypatch):
    onnx = make(FakeEngine())
    monkeypatch.setattr(tts_onnx, 'usable', lambda lang: lang == 'ru')
    assert tts_onnx.keep(onnx, 'ru') and not tts_onnx.keep(onnx, 'uk')
    onnx.broken = True
    assert not tts_onnx.keep(onnx, 'ru')


def test_a_failing_onnx_voice_yields_no_audio_and_no_torch_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(tts, '_get_lang', lambda: 'ru')
    monkeypatch.setattr(tts, '_get_tts', lambda: make(FakeEngine(fail=RuntimeError('ORT crashed'))))
    assert tts._generate_cached('Уникальная фраза для проверки отказа голоса', 100, persist=False) is None


def test_ukrainian_is_text_only(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, 'CACHE_DIR', str(tmp_path))
    monkeypatch.setattr(tts, '_get_lang', lambda: 'uk')
    monkeypatch.setattr(tts, '_get_tts', lambda: pytest.fail('no model must be loaded for uk'))
    assert tts._generate_cached('Привіт', 100, persist=False) is None


def test_download_discards_a_file_whose_hash_does_not_match(monkeypatch, tmp_path):
    monkeypatch.setattr(tts_onnx, 'model_dir', lambda: str(tmp_path))
    monkeypatch.setattr(tts_onnx, 'FILES', ('a.onnx',))
    monkeypatch.setattr(tts_onnx, '_ready', False)
    monkeypatch.setattr('core.download.pinned_hash', lambda name: '0' * 64)

    class Resp:
        headers = {'Content-Length': '5'}

        def __enter__(self): return self
        def __exit__(self, *a): return False
        def raise_for_status(self): pass
        def iter_content(self, n): yield b'12345'
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **k: Resp())
    tts_onnx._downloading = True
    tts_onnx._download()
    assert os.listdir(tmp_path) == [] and tts_onnx._downloading is False and tts_onnx._ready is False


def test_download_url_is_https_and_every_file_has_a_pin():
    import json
    pins = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'model_hashes.json'), encoding='utf-8'))
    assert tts_onnx.RELEASE_URL.startswith('https://') and all(f in pins for f in tts_onnx.FILES)


@pytest.mark.skipif(not tts_onnx.package_available(), reason='silero-onnx-tts is not installed')
def test_the_package_imports_while_torch_is_loaded(monkeypatch):
    saved = {k: v for k, v in sys.modules.items() if k == 'silero_onnx' or k.startswith('silero_onnx.')}
    for k in saved:
        del sys.modules[k]
    monkeypatch.setitem(sys.modules, 'torch', types.ModuleType('torch'))
    try:
        assert tts_onnx._import_silero().SileroTTS
    finally:
        for k in [k for k in sys.modules if k == 'silero_onnx' or k.startswith('silero_onnx.')]:
            del sys.modules[k]
        sys.modules.update(saved)


@pytest.mark.skipif(not (tts_onnx.package_available() and all(os.path.isfile(os.path.join(tts_onnx.model_dir(), f)) for f in tts_onnx.FILES)),
                    reason='ONNX voice files are not downloaded')
def test_real_voice_speaks_russian(tmp_path):
    m = tts_onnx.load()
    out = str(tmp_path / 'say.wav')
    m.save_wav(text='Замок на двери старый.', speaker='eugene', sample_rate=48000, audio_path=out)
    info = sf.info(out)
    assert info.samplerate == 48000 and 1.0 < info.duration < 4.0
    data, _ = sf.read(out)
    assert float(np.abs(data).max()) > 0.05
