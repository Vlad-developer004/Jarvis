"""The startup summary is spoken first and the readiness line comes after it; without a summary the greeting plays as before."""
import importlib
import threading

import pytest

import core.speech as speech
from features import morning_briefing as mb

bootstrap = importlib.import_module('core.system.bootstrap')     # the package re-exports a function of the same name


@pytest.fixture
def spoken(monkeypatch):
    said = []
    monkeypatch.setattr(speech, 'speak', lambda text, *a, **kw: said.append(text))
    monkeypatch.setattr('core.i18n.get_language', lambda: 'ru')
    monkeypatch.setattr('core.address.get_address', lambda lang=None: 'сэр')
    return said


def test_ready_line_after_a_summary_has_no_second_greeting(spoken):
    bootstrap.speak_ready(after_summary=True)
    assert spoken == ['Я запущен и готов к работе.']


def test_plain_greeting_keeps_its_wording(spoken):
    bootstrap.speak_ready()
    assert spoken == ['Приветствую, сэр. Я запущен и готов к работе.']


def test_early_greeting_is_skipped_when_a_summary_is_due(spoken, monkeypatch):
    monkeypatch.setattr(mb, 'summary_due', lambda: True)
    started = []
    monkeypatch.setattr(threading.Thread, 'start', lambda self: started.append(self))
    bootstrap.play_early_greeting()
    assert not started and not spoken


def test_early_greeting_plays_when_no_summary_is_due(spoken, monkeypatch):
    monkeypatch.setattr(mb, 'summary_due', lambda: False)
    monkeypatch.setattr(bootstrap.time, 'sleep', lambda s: None)
    monkeypatch.setattr(threading.Thread, 'start', lambda self: self.run())       # run the greeting task inline
    bootstrap.play_early_greeting()
    assert spoken == ['Приветствую, сэр. Я запущен и готов к работе.']


@pytest.mark.parametrize('runner,name', [('_run_briefing', '_do_briefing'), ('_run_evening_summary', '_do_evening_summary')])
def test_the_summary_is_followed_by_the_ready_line_even_when_it_fails(spoken, monkeypatch, runner, name):
    order = []
    monkeypatch.setattr(mb, runner, lambda handler: order.append('summary'))
    monkeypatch.setattr(mb, '_say_ready_after_summary', lambda: order.append('ready'))
    getattr(mb, name)(None)
    assert order == ['summary', 'ready']
    order.clear()

    def boom(handler):
        raise RuntimeError('network down')
    monkeypatch.setattr(mb, runner, boom)
    with pytest.raises(RuntimeError):
        getattr(mb, name)(None)
    assert order == ['ready']


def test_summary_due_follows_the_windows_and_the_last_date(monkeypatch):
    class Clock:
        hour = 8
    import datetime as dt
    monkeypatch.setattr(mb, 'module_enabled', lambda name: True)
    monkeypatch.setattr(mb, 'datetime', type('D', (), {'now': staticmethod(lambda: dt.datetime(2026, 10, 21, Clock.hour, 0))}))
    today = dt.date.today().isoformat()
    monkeypatch.setattr(mb, '_read_last_date', lambda: '2000-01-01')
    monkeypatch.setattr(mb, '_read_last_evening_date', lambda: today)
    assert mb.summary_due() is True                       # morning, not yet given today
    monkeypatch.setattr(mb, '_read_last_date', lambda: today)
    assert mb.summary_due() is False                      # morning, already given
    Clock.hour = 20
    assert mb.summary_due() is False                      # evening, already given
    monkeypatch.setattr(mb, '_read_last_evening_date', lambda: '2000-01-01')
    assert mb.summary_due() is True
    Clock.hour = 3
    assert mb.summary_due() is False                      # night: no summary
    monkeypatch.setattr(mb, 'module_enabled', lambda name: False)
    Clock.hour = 8
    assert mb.summary_due() is False
