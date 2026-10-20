"""core/native.py: the native parts are required, and a missing one fails loudly with NativeUnavailable."""
import sys
import types

import pytest

from core import native


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(native, '_loaded', {})


def _fake_module(monkeypatch, name='jarvis_files', broken=False):
    mod = types.ModuleType(name)
    def version():
        if broken:
            raise RuntimeError('stub')
        return '0.1.0'
    mod.version = version
    monkeypatch.setitem(sys.modules, name, mod)
    return mod


def test_missing_module_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, 'jarvis_files', None)   # import raises ImportError
    with pytest.raises(native.NativeUnavailable, match='jarvis_files'):
        native.require('files')


def test_loaded_module_is_returned_and_cached(monkeypatch):
    mod = _fake_module(monkeypatch)
    assert native.require('files') is mod
    monkeypatch.setitem(sys.modules, 'jarvis_files', None)
    assert native.require('files') is mod   # already loaded: no second import


def test_a_module_that_cannot_run_counts_as_missing(monkeypatch):
    _fake_module(monkeypatch, broken=True)
    with pytest.raises(native.NativeUnavailable):
        native.require('files')


def test_unknown_names_are_rejected():
    with pytest.raises(native.NativeUnavailable):
        native.require('nope')
    assert native.sidecar_path('nope') is None
    with pytest.raises(native.NativeUnavailable):
        native.require_sidecar('nope')


def test_sidecar_is_required_when_absent(monkeypatch):
    monkeypatch.setattr(native, 'sidecar_path', lambda name: None)
    with pytest.raises(native.NativeUnavailable, match='not built'):
        native.require_sidecar('audio')
    monkeypatch.setattr(native, 'sidecar_path', lambda name: 'C:/x/jarvis_audio.exe')
    assert native.require_sidecar('audio') == 'C:/x/jarvis_audio.exe'


def test_status_lists_every_part(monkeypatch):
    monkeypatch.setitem(sys.modules, 'jarvis_files', None)
    monkeypatch.setitem(sys.modules, 'jarvis_win', None)
    st = native.status()
    assert set(st) == {'files', 'windows', 'audio'}
    assert st['files']['present'] is False and st['windows']['present'] is False
