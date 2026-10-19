import pytest

from actions import game_timer
from core.engine.recognition import _TIMER_ADD_RE, _TIMER_SUB_RE


@pytest.mark.parametrize('text', ['убавь пять минут от таймера', 'отними минуту от таймера', 'сократи таймер на две минуты', 'убавь на таймере 5 минут'])
def test_timer_sub_phrases(text):
    assert _TIMER_SUB_RE.search(text)
    assert not _TIMER_ADD_RE.search(text)


@pytest.mark.parametrize('text', ['добавь пять минут к таймеру', 'отмени таймер', 'убери таймер', 'убавь громкость'])
def test_timer_sub_ignores_other_commands(text):
    assert not _TIMER_SUB_RE.search(text)


def test_sub_time_keeps_at_least_the_rest(monkeypatch):
    monkeypatch.setattr(game_timer, '_active_timer', None)
    assert game_timer.sub_time(60) is False
    t = game_timer._Timer(600, 'x', lambda s: None)
    monkeypatch.setattr(game_timer, '_active_timer', t)
    try:
        assert game_timer.sub_time(300) is True
        assert 295 <= t.remaining_sec() <= 300 and t.total_sec() == 300
        assert game_timer.sub_time(400) is False       # more than is left: refuse, do not cancel
        assert t.total_sec() == 300
    finally:
        t.cancel()
