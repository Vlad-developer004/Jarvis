"""data/model_hashes.json: every pin is a file name with a 64-hex SHA-256, and the pinned loader honours it."""
import json
import os
import re

from core import download

PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'model_hashes.json')


def test_pins_are_well_formed():
    pins = json.load(open(PATH, encoding='utf-8'))
    assert pins and all(re.fullmatch(r'[0-9a-f]{64}', v) and os.path.basename(k) == k for k, v in pins.items())


def test_a_mismatching_file_is_refused_and_a_matching_one_passes(tmp_path, monkeypatch):
    f = tmp_path / 'v4_ua.pt'
    f.write_bytes(b'not the model')
    try:
        download.verify_pinned(f)
        raise AssertionError('a wrong file must be refused')
    except ValueError:
        pass
    monkeypatch.setattr(download, 'pinned_hash', lambda name: download.sha256_file(f))
    download.verify_pinned(f)
