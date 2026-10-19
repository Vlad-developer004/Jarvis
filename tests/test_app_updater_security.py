"""The self-updater installs nothing that is not signed by our key, matches the signed hash and unpacks safely."""
import base64
import hashlib
import io
import json
import zipfile

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import core.system.app_updater as up

PREFIX = up._DOWNLOAD_PREFIX


def _zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class Release:
    """A fake GitHub release: serves assets from memory and signs the checksum list."""

    def __init__(self, monkeypatch, tmp_path, files=None, zip_name='Jarvis.zip'):
        self.key = Ed25519PrivateKey.generate()
        self.pub = self.key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
        self.zip_name = zip_name
        self.zip = _zip_bytes(files or {'Jarvis.exe': b'new build'})
        self.sums = f'{hashlib.sha256(self.zip).hexdigest()}  {zip_name}\n'.encode()
        self.sig = base64.b64encode(self.key.sign(self.sums))
        self.urls = {}
        self.assets = []
        for name, data in ((zip_name, self.zip), (up.SUMS_NAME, self.sums), (up.SIG_NAME, self.sig)):
            self.add(name, data)
        monkeypatch.setattr(up, 'UPDATE_DIR', tmp_path / 'app_update')
        monkeypatch.setattr(up, 'UPDATE_READY', tmp_path / 'app_update' / 'ready.json')
        monkeypatch.setattr(up, '_load_pubkey', lambda: self.pub)
        monkeypatch.setattr(up, '_download_small', lambda url: self.urls.get(url))
        monkeypatch.setattr(up, '_download', self._download)

    def add(self, name, data):
        url = f'{PREFIX}v9.9.9/{name}'
        self.urls[url] = data
        self.assets = [a for a in self.assets if a['name'] != name] + [{'name': name, 'browser_download_url': url}]

    def _download(self, url, dest):
        data = self.urls.get(url)
        if data is None:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def stage(self):
        return up._stage_update(next(a for a in self.assets if a['name'] == self.zip_name), 'v9.9.9', self.assets)


def test_a_properly_signed_release_is_staged(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    assert r.stage() is True
    info = json.loads(up.UPDATE_READY.read_text(encoding='utf-8'))
    assert info['version'] == 'v9.9.9' and (tmp_path / 'app_update' / 'staged' / 'Jarvis.exe').read_bytes() == b'new build'
    assert not list((tmp_path / 'app_update').glob('*.zip'))


def test_a_swapped_archive_is_rejected(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    r.add('Jarvis.zip', _zip_bytes({'Jarvis.exe': b'malware'}))       # the list still names the original hash
    assert r.stage() is False and not up.UPDATE_READY.exists()
    assert not (tmp_path / 'app_update' / 'staged').exists() and not list((tmp_path / 'app_update').glob('*.zip'))


def test_a_signature_from_another_key_is_rejected(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    evil = Ed25519PrivateKey.generate()
    r.add(up.SIG_NAME, base64.b64encode(evil.sign(r.sums)))
    assert r.stage() is False and not up.UPDATE_READY.exists()


def test_a_tampered_checksum_list_is_rejected(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    r.add(up.SUMS_NAME, r.sums.replace(b'Jarvis.zip', b'Jarvis.zip ') + b'\n' + b'0' * 64 + b'  Jarvis.zip\n')
    assert r.stage() is False


@pytest.mark.parametrize('missing', [up.SUMS_NAME, up.SIG_NAME])
def test_a_release_without_signature_files_is_rejected(monkeypatch, tmp_path, missing):
    r = Release(monkeypatch, tmp_path)
    r.assets = [a for a in r.assets if a['name'] != missing]
    assert r.stage() is False


def test_no_public_key_in_the_build_means_nothing_is_installed(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    monkeypatch.setattr(up, '_load_pubkey', lambda: None)
    assert r.stage() is False and not up.UPDATE_READY.exists()


def test_a_zip_with_path_traversal_is_rejected_even_when_signed(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path, files={'../evil.dll': b'x', 'Jarvis.exe': b'y'})
    assert r.stage() is False and not up.UPDATE_READY.exists()
    assert not (tmp_path / 'evil.dll').exists() and not (tmp_path / 'app_update' / 'staged').exists()


@pytest.mark.parametrize('name', ['/abs.txt', 'C:/Windows/x.dll', 'a/../../b', 'sub/CON.txt', 'x\\..\\..\\y'])
def test_unsafe_archive_names_are_rejected(name):
    with pytest.raises(RuntimeError):
        up._check_member_name(name)


def test_normal_archive_names_pass():
    for name in ('Jarvis.exe', '_internal/torch/lib/x.dll', 'data/locales/ru.json'):
        up._check_member_name(name)


def test_download_urls_outside_the_repo_release_path_are_refused():
    assert up._allowed_url(PREFIX + 'v1/Jarvis.zip')
    for url in ('http://github.com/' + up.GITHUB_REPO + '/releases/download/v1/a.zip', 'https://evil.test/Jarvis.zip',
                'https://github.com/other/repo/releases/download/v1/a.zip', '', None):
        assert not up._allowed_url(url)


def test_a_staged_release_is_not_downloaded_twice(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    assert r.stage() is True
    calls = []
    monkeypatch.setattr(up, '_download', lambda url, dest: calls.append(url))
    assert r.stage() is True and calls == []


def test_a_bad_tag_is_not_staged(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path)
    assert up._stage_update(r.assets[0], '../../x', r.assets) is False


def test_asset_name_cannot_escape_the_update_folder(monkeypatch, tmp_path):
    r = Release(monkeypatch, tmp_path, zip_name='..\\..\\evil.zip')
    assert r.stage() is False
    assert not (tmp_path / 'evil.zip').exists()


def test_signature_check_accepts_only_the_exact_message(monkeypatch):
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    sig = base64.b64encode(key.sign(b'abc'))
    assert up._verify_signature(b'abc', sig, pub) is True
    assert up._verify_signature(b'abcd', sig, pub) is False
    assert up._verify_signature(b'abc', b'not base64!!', pub) is False
    assert up._verify_signature(b'abc', sig, b'short') is False


def test_the_checksum_list_parser():
    h = 'a' * 64
    assert up._parse_sums(f'{h}  Jarvis.zip\n{h.upper()} *Other.zip\nnonsense\n') == {'Jarvis.zip': h, 'Other.zip': h}


def test_apply_script_checks_robocopy_and_escapes_percent(monkeypatch, tmp_path):
    staged = tmp_path / 'st%aged'
    staged.mkdir()
    ready = tmp_path / 'ready.json'
    ready.write_text(json.dumps({'version': '9', 'staged_dir': str(staged)}), encoding='utf-8')
    monkeypatch.setattr(up, 'UPDATE_READY', ready)
    monkeypatch.setattr(up, 'UPDATE_DIR', tmp_path)
    monkeypatch.setattr(up.sys, 'frozen', True, raising=False)
    monkeypatch.setattr(up.sys, 'executable', str(tmp_path / 'Jarvis.exe'))
    import subprocess
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: None)
    assert up.apply_and_restart() is True
    bat = (tmp_path / 'apply_update.bat').read_text(encoding='utf-8')
    assert 'st%%aged' in bat and 'if errorlevel 8 exit /b 1' in bat
    assert bat.index('if errorlevel 8') < bat.index('rmdir')


def test_the_release_signing_tool_produces_what_the_updater_verifies(tmp_path):
    from tools import sign_release
    keyfile = tmp_path / 'key'
    sign_release.genkey(keyfile)
    archive = tmp_path / 'Jarvis.zip'
    archive.write_bytes(_zip_bytes({'a': b'b'}))
    sign_release.sign(keyfile, archive)
    seed = base64.b64decode(keyfile.read_text().strip())
    pub = Ed25519PrivateKey.from_private_bytes(seed).public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    sums, sig = (tmp_path / 'SHA256SUMS').read_bytes(), (tmp_path / 'SHA256SUMS.sig').read_bytes()
    assert up._verify_signature(sums, sig, pub)
    assert up._parse_sums(sums.decode())['Jarvis.zip'] == hashlib.sha256(archive.read_bytes()).hexdigest()
