import pytest

from core.engine.recognition import _TIMER_ADD_RE


@pytest.mark.parametrize('text', [
    'добавь одну минуту к таймеру',
    'добавь 5 минут к таймеру',
    'добавь в таймер десять минут',
    'продли таймер на пять минут',
    'добавь минуту на таймере',
])
def test_timer_add_matches_inflected_timer(text):
    assert _TIMER_ADD_RE.search(text)


@pytest.mark.parametrize('text', ['поставь таймер на пять минут', 'добавь громкость', 'отмени таймер'])
def test_timer_add_ignores_other_commands(text):
    assert not _TIMER_ADD_RE.search(text)
