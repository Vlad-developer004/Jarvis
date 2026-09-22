"""Tests for core/speech/safe_task.py — the reusable background-thread
wrapper meant to close off the "silent thread death" bug class found twice
today (actions/weather.py's forecast lookups, and the pre-existing 2026-09
ETS2 _monitor_loop regression documented in tests/test_ets2_monitor.py)."""
import time

from core.speech.safe_task import run_speaking_task


def _join(threads, timeout=1.0):
    for t in threads:
        t.join(timeout)


def test_run_speaking_task_runs_fn_to_completion():
    calls = []
    t = run_speaking_task(lambda: calls.append('ran'))
    t.join(1.0)
    assert calls == ['ran']


def test_run_speaking_task_speaks_fallback_on_exception(monkeypatch):
    spoken = []

    def _boom():
        raise RuntimeError('boom')

    t = run_speaking_task(_boom, error_message='что-то пошло не так', speak_fn=lambda text: spoken.append(text))
    t.join(1.0)
    assert spoken == ['что-то пошло не так']


def test_run_speaking_task_swallows_exception_without_error_message():
    # No error_message given — must not raise out of the thread or crash
    # the test process; there's simply nothing spoken.
    def _boom():
        raise RuntimeError('boom')

    t = run_speaking_task(_boom)
    t.join(1.0)
    assert not t.is_alive()


def test_run_speaking_task_falls_back_to_core_speak_when_no_speak_fn_given(monkeypatch):
    import core.speech.tts as tts

    spoken = []
    monkeypatch.setattr(tts, 'speak', lambda text: spoken.append(text))

    def _boom():
        raise RuntimeError('boom')

    t = run_speaking_task(_boom, error_message='fallback message')
    t.join(1.0)
    assert spoken == ['fallback message']


def test_run_speaking_task_does_not_speak_when_fn_succeeds():
    spoken = []
    t = run_speaking_task(lambda: None, error_message='should not be heard', speak_fn=lambda text: spoken.append(text))
    t.join(1.0)
    assert spoken == []


def test_run_speaking_task_passes_args_and_kwargs_through():
    received = {}

    def _fn(a, b, c=None):
        received['a'] = a
        received['b'] = b
        received['c'] = c

    t = run_speaking_task(_fn, 1, 2, c=3)
    t.join(1.0)
    assert received == {'a': 1, 'b': 2, 'c': 3}
