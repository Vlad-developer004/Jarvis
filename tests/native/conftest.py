"""Parity tests for the native parts: they run only when the module is built (`maturin develop`), otherwise they skip."""
import pytest


@pytest.fixture
def native_files():
    return pytest.importorskip('jarvis_files')


@pytest.fixture
def native_win():
    return pytest.importorskip('jarvis_win')
