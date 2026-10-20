"""Builds data/optional_packages.json: for each optional feature the wheels (URL + SHA-256 from PyPI) that core/optional_pkgs.py downloads on first use.

    python tools/make_optional_manifest.py

pip resolves the full dependency set for Windows / CPython 3.12. Only numpy is left out (the installer always carries it); everything else stays in the
list even when the installer happens to hold a copy, because that cannot be told reliably from outside the archive: a bundled copy wins at import time
anyway, and a missing one is then served by the download. Run it again when a requirement below changes, and commit the result: the hashes are the
trust anchor of the download."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

# feature -> (requirement lines, module whose import proves the set is usable, whether pip may add the dependencies itself)
# vosk lists its few dependencies by hand: `srt` has no wheel on PyPI, so it ships inside the installer (jarvis.spec hidden import)
FEATURES = {
    'gemini': (['google-generativeai==0.8.6'], 'google.generativeai', True),
    'opencv': (['opencv-contrib-python-headless==4.11.0.86'], 'cv2', True),
    'vosk': (['vosk==0.3.45', 'cffi==2.0.0', 'pycparser==2.23', 'tqdm==4.67.1'], 'vosk', False),
}


BUNDLED = {'numpy'}
# Libraries that the installer carries too (jarvis.spec collects them whole). A bundled copy always wins at import time, so the downloaded sets are
# pinned to the versions installed next to the build: both sides then agree.
SHARED = ['tqdm', 'cryptography', 'requests', 'urllib3', 'idna', 'certifi', 'charset-normalizer', 'typing-extensions', 'pydantic', 'pydantic-core',
          'colorama', 'cffi', 'pycparser', 'annotated-types', 'typing-inspection']


def _constraints(path: str) -> None:
    import importlib.metadata as md
    with open(path, 'w', encoding='utf-8') as f:
        for name in SHARED:
            try:
                f.write(f'{name}=={md.version(name)}\n')
            except md.PackageNotFoundError:
                pass


def _pypi_file(name: str, version: str, filename: str) -> dict:
    with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as r:
        for f in json.load(r)['urls']:
            if f['filename'] == filename:
                return f
    raise SystemExit(f'{filename} not found on PyPI')


def build() -> dict:
    out = {}
    for feature, (reqs, module, with_deps) in FEATURES.items():
        with tempfile.TemporaryDirectory() as tmp:
            cons = os.path.join(tmp, 'constraints.txt')
            _constraints(cons)
            subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--python-version', '3.12', '--platform', 'win_amd64',
                            '--implementation', 'cp', '--abi', 'cp312', '-c', cons, '-d', tmp, *([] if with_deps else ['--no-deps']), *reqs], check=True, capture_output=True)
            wheels = []
            for fn in sorted(os.listdir(tmp)):
                if not fn.endswith('.whl'):
                    continue
                if fn.split('-')[0].lower().replace('_', '-') in BUNDLED:
                    continue
                name, version = fn.split('-')[:2]
                info = _pypi_file(name, version, fn)
                wheels.append({'file': fn, 'url': info['url'], 'sha256': info['digests']['sha256'], 'size': info['size']})
            out[feature] = {'import': module, 'wheels': wheels}
            print(f"{feature}: {len(wheels)} wheels, {sum(w['size'] for w in wheels) >> 20} MB")
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'data', 'optional_packages.json'))
    a = ap.parse_args()
    manifest = build()
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=1)
