"""Shared pytest setup.

Mirrors the crash-sensitive stub block at the top of main.py (see
CLAUDE.md's "Startup order is crash-sensitive" rule): CUDA_VISIBLE_DEVICES
must be set and pynvml/pyarrow stubbed out *before* anything imports
torch/nltk/pandas, or a 0xC0000005 native crash can take down the whole
test run on this CPU-only setup. This must run at collection time, before
any test module has a chance to import project code — hence doing it here
in conftest.py rather than in a fixture.
"""
import os
import sys
import types

os.environ.setdefault('CUDA_VISIBLE_DEVICES', '')

if 'pynvml' not in sys.modules:
    _pynvml_stub = types.ModuleType('pynvml')

    class _NVMLError(Exception):
        pass

    _pynvml_stub.NVMLError = _NVMLError
    _pynvml_stub.NVMLError_DriverNotLoaded = _NVMLError
    _pynvml_stub.nvmlInit = lambda: None
    _pynvml_stub.nvmlShutdown = lambda: None
    _pynvml_stub.nvmlDeviceGetCount = lambda: 0
    _pynvml_stub.nvmlSystemGetDriverVersion = lambda: b'0.0'
    sys.modules['pynvml'] = _pynvml_stub

if 'pyarrow' not in sys.modules:
    _pyarrow_stub = types.ModuleType('pyarrow')
    _pyarrow_stub.__version__ = '0.0.0'
    sys.modules['pyarrow'] = _pyarrow_stub

import pytest


@pytest.fixture(autouse=True)
def _reset_i18n_language():
    """Every test starts on 'ru' regardless of what a previous test left
    set_language() at — core.i18n's _language is a bare module global."""
    from core import i18n
    i18n.set_language('ru')
    yield
    i18n.set_language('ru')


@pytest.fixture(autouse=True)
def _clear_command_match_cache():
    """match_command() caches results in a plain dict keyed only by text,
    not by language — without clearing it, a test that checks the same
    phrase under both languages would read back a stale answer."""
    from core.nlp import commands
    commands._match_cache.clear()
    yield
    commands._match_cache.clear()
