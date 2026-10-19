"""core.download: hostile archives cannot write outside their folder, hashes pinned in data/model_hashes.json are enforced."""
import hashlib
import io
import json
import tarfile
import zipfile

import pytest

from core import download as dl


def _tar(entries):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        for name, kind, payload in entries:
            info = tarfile.TarInfo(name)
            if kind == 'file':
                data = payload
                info.size = len(data)
                tf.addfile(info, io.BytesIO(data))
            elif kind == 'symlink':
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tf.addfile(info)
            elif kind == 'dir':
                info.type = tarfile.DIRTYPE
                tf.addfile(info)
    buf.seek(0)
    return tarfile.open(fileobj=buf, mode='r')


def test_normal_tar_is_extracted(tmp_path):
    with _tar([('model', 'dir', None), ('model/tokens.txt', 'file', b'a b')]) as tf:
        dl.safe_extract_tar(tf, tmp_path)
    assert (tmp_path / 'model' / 'tokens.txt').read_bytes() == b'a b'


@pytest.mark.parametrize('entries', [
    [('../evil.txt', 'file', b'x')],
    [('/abs/evil.txt', 'file', b'x')],
    [('ok/../../evil.txt', 'file', b'x')],
    [('link', 'symlink', '../../outside')],
    [('sub/CON', 'file', b'x')],
])
def test_hostile_tar_is_refused_and_nothing_is_written(tmp_path, entries):
    dest = tmp_path / 'dest'
    dest.mkdir()
    with _tar(entries) as tf, pytest.raises(dl.UnsafeArchive):
        dl.safe_extract_tar(tf, dest)
    assert list(dest.iterdir()) == [] and not (tmp_path / 'evil.txt').exists()


def test_hostile_zip_is_refused(tmp_path):
    dest = tmp_path / 'dest'
    dest.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('good.txt', 'ok')
        zf.writestr('..\\..\\evil.txt', 'x')
    with zipfile.ZipFile(buf) as zf, pytest.raises(dl.UnsafeArchive):
        dl.safe_extract_zip(zf, dest)
    assert list(dest.iterdir()) == []


def test_archive_size_caps_are_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, 'MAX_UNPACKED', 10)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('big.bin', b'x' * 100)
    with zipfile.ZipFile(buf) as zf, pytest.raises(dl.UnsafeArchive):
        dl.safe_extract_zip(zf, tmp_path)


def test_only_https_urls_are_downloaded():
    assert dl.require_https('https://huggingface.co/x') == 'https://huggingface.co/x'
    for bad in ('http://x.test/a', 'ftp://x.test/a', 'file:///c:/a', ''):
        with pytest.raises(ValueError):
            dl.require_https(bad)


def _pin(monkeypatch, tmp_path, name, digest):
    (tmp_path / 'data').mkdir(exist_ok=True)
    (tmp_path / 'data' / 'model_hashes.json').write_text(json.dumps({name: digest}), encoding='utf-8')
    import config_pack.config as cfg
    monkeypatch.setattr(cfg, 'get_project_root', lambda: str(tmp_path))


def test_pinned_hash_is_enforced(tmp_path, monkeypatch):
    f = tmp_path / 'model.onnx'
    f.write_bytes(b'weights')
    _pin(monkeypatch, tmp_path, 'model.onnx', hashlib.sha256(b'weights').hexdigest())
    dl.verify_pinned(f)
    f.write_bytes(b'tampered')
    with pytest.raises(ValueError):
        dl.verify_pinned(f)


def test_files_without_a_pin_pass_and_bad_pins_are_ignored(tmp_path, monkeypatch):
    f = tmp_path / 'other.bin'
    f.write_bytes(b'x')
    _pin(monkeypatch, tmp_path, 'model.onnx', 'not-a-hash')
    dl.verify_pinned(f)
    assert dl.pinned_hash('model.onnx') is None


def test_asr_download_removes_the_file_when_the_pinned_hash_does_not_match(tmp_path, monkeypatch):
    from core.speech import asr

    class Resp:
        def __init__(self):
            self._b = io.BytesIO(b'tampered')

        def getheader(self, name):
            return None

        def read(self, n=-1):
            return self._b.read(n)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(asr.urllib.request, 'urlopen', lambda req, timeout=0: Resp())
    _pin(monkeypatch, tmp_path, 'm.onnx', hashlib.sha256(b'weights').hexdigest())
    target = tmp_path / 'm.onnx'
    with pytest.raises(ValueError):
        asr._stream_download('https://x.test/m.onnx', str(target))
    assert not target.exists()


def test_asr_download_refuses_plain_http(tmp_path):
    from core.speech import asr
    with pytest.raises(ValueError):
        asr._stream_download('http://x.test/m.onnx', str(tmp_path / 'm.onnx'))
