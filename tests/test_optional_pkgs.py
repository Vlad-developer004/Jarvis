"""core/optional_pkgs.py: packages that are fetched on first use, checked against a pinned hash, and made importable."""
import hashlib
import io
import sys
import zipfile

import pytest

from core import optional_pkgs

MOD = 'jarvis_fake_optional_pkg'


def _wheel_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr(f'{MOD}/__init__.py', 'VALUE = 42\n')
        zf.writestr(f'{MOD}-1.0.dist-info/METADATA', 'Name: x\n')
    return buf.getvalue()


class _Resp:
    def __init__(self, data):
        self._data = data

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def raise_for_status(self): pass
    def iter_content(self, n): yield self._data


@pytest.fixture
def env(tmp_path, monkeypatch):
    data = _wheel_bytes()
    spec = {'import': MOD, 'wheels': [{'file': f'{MOD}-1.0-py3-none-any.whl', 'url': 'https://files.example/x.whl', 'sha256': hashlib.sha256(data).hexdigest()}]}
    monkeypatch.setattr(optional_pkgs, '_manifest', lambda: {'fake': spec})
    monkeypatch.setattr(optional_pkgs, 'packages_dir', lambda: tmp_path / 'packages')
    monkeypatch.setattr(optional_pkgs, '_notify', lambda *a, **k: None)
    monkeypatch.setattr(optional_pkgs, '_ready', set())
    monkeypatch.setattr(optional_pkgs, '_failed', {})
    import requests
    calls = []
    monkeypatch.setattr(requests, 'get', lambda url, **k: calls.append(url) or _Resp(data))
    saved = list(sys.path)
    yield tmp_path, spec, data, calls
    sys.path[:] = saved
    sys.modules.pop(MOD, None)


def test_downloads_verifies_and_makes_the_package_importable(env):
    tmp_path, spec, data, calls = env
    assert optional_pkgs.ensure('fake') is True
    assert calls == ['https://files.example/x.whl']
    import importlib
    assert importlib.import_module(MOD).VALUE == 42
    assert (tmp_path / 'packages' / 'fake' / '.complete').is_file()
    assert optional_pkgs.ensure('fake') is True and len(calls) == 1          # no second download


def test_a_wheel_with_the_wrong_hash_is_rejected_and_leaves_nothing(env):
    tmp_path, spec, data, calls = env
    spec['wheels'][0]['sha256'] = '0' * 64
    assert optional_pkgs.ensure('fake') is False
    assert not (tmp_path / 'packages' / 'fake').exists() and not (tmp_path / 'packages' / 'fake.part').exists()
    assert optional_pkgs.ensure('fake') is False and len(calls) == 1         # a failed download waits before the next try


def test_http_urls_are_refused(env):
    tmp_path, spec, data, calls = env
    spec['wheels'][0]['url'] = 'http://files.example/x.whl'
    assert optional_pkgs.ensure('fake') is False and calls == []


def test_an_already_importable_package_is_not_downloaded(env, monkeypatch):
    tmp_path, spec, data, calls = env
    monkeypatch.setattr(optional_pkgs, '_importable', lambda m: True)
    assert optional_pkgs.ensure('fake') is True and calls == []


def test_an_unknown_feature_is_false(env):
    assert optional_pkgs.ensure('nope') is False


def test_every_feature_in_the_shipped_manifest_has_pinned_https_wheels():
    import json
    import os
    m = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'data', 'optional_packages.json'), encoding='utf-8'))
    for feature, spec in m.items():
        assert spec['import'] and spec['wheels'], feature
        for w in spec['wheels']:
            assert w['url'].startswith('https://') and len(w['sha256']) == 64 and w['file'].endswith('.whl'), (feature, w['file'])


def test_pins_and_manifest_are_found_inside_a_frozen_bundle(tmp_path, monkeypatch):
    """PyInstaller keeps data files in <exe dir>/_internal; build.bat clears the JSON files next to the exe, so the lookup must reach the bundle folder."""
    import json
    from core import download
    exe_dir, bundle = tmp_path / 'app', tmp_path / 'app' / '_internal'
    (bundle / 'data').mkdir(parents=True)
    (exe_dir / 'data').mkdir()
    (bundle / 'data' / 'model_hashes.json').write_text(json.dumps({'m.onnx': 'a' * 64}), encoding='utf-8')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.setattr(sys, 'executable', str(exe_dir / 'Jarvis.exe'))
    assert download.pinned_hash('m.onnx') == 'a' * 64
    with pytest.raises(OSError):
        download.bundled_data_file('missing.json')


def test_a_stalled_connection_is_retried_inside_one_download(env, monkeypatch):
    import requests
    tmp_path, spec, data, calls = env
    state = {'n': 0}

    def flaky(url, **k):
        state['n'] += 1
        if state['n'] < 3:
            raise requests.Timeout('read timed out')
        return _Resp(data)
    monkeypatch.setattr(requests, 'get', flaky)
    assert optional_pkgs.ensure('fake') is True and state['n'] == 3


def test_three_failed_tries_give_up_and_leave_nothing(env, monkeypatch):
    import requests
    tmp_path, spec, data, calls = env
    monkeypatch.setattr(requests, 'get', lambda url, **k: (_ for _ in ()).throw(requests.ConnectionError('down')))
    assert optional_pkgs.ensure('fake') is False
    assert not (tmp_path / 'packages' / 'fake').exists() and not (tmp_path / 'packages' / 'fake.part').exists()
