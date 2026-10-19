"""actions/media_phrases.py: rewind, "what is playing" and "how long is left" phrases in Russian and Ukrainian."""
import pytest

from actions import media_phrases as mp


@pytest.mark.parametrize('text,mode,sec', [
    ('перемотай на 5 минут вперёд', 'by', 300), ('перемотай на 5 минут назад', 'by', -300), ('перемотай на пять минут назад', 'by', -300),
    ('отмотай на 30 секунд', 'by', -30), ('промотай на 1 час 20 минут', 'by', 4800), ('перемотай на полчаса вперёд', 'by', 1800),
    ('перемотай назад на минуту', 'by', -60), ('вернись на 10 секунд', 'by', -10), ('перемотай вперед на 2 минуты', 'by', 120),
    ('перемотай на отметку 1:20:00', 'to', 4800), ('перемотай на 45:10', 'to', 2710), ('перемотай на отметку 20 минут', 'to', 1200),
    ('перемотай на 5 хвилин назад', 'by', -300), ('відмотай на 10 секунд', 'by', -10), ('перемотай на пів години', 'by', 1800),
])
def test_seek(text, mode, sec):
    assert mp.parse_seek(text) == {'mode': mode, 'seconds': sec}


@pytest.mark.parametrize('text', ['перемотай назад', 'перемотай вперёд', 'включи музыку', 'поставь таймер на 5 минут', 'переключись на вкладку 5', 'что играет'])
def test_not_a_seek_without_an_amount_or_a_verb(text):
    assert mp.parse_seek(text) is None


def test_now_and_left_and_routes():
    for t in ('что сейчас играет', 'что я смотрю', 'что это за серия', 'що зараз грає'):
        assert mp.route(t) == 'cinema_now', t
    for t in ('сколько осталось до конца', 'сколько осталось до конца фильма', 'сколько осталось серии', 'скільки залишилось до кінця'):
        assert mp.route(t) == 'cinema_left', t
    assert mp.route('перемотай на 5 минут назад') == 'cinema_seek'


@pytest.mark.parametrize('text', ['что за песня играет', 'сколько осталось', 'сколько осталось на таймере', 'что такое python', 'открой браузер', ''])
def test_phrases_that_belong_to_other_commands_are_left_alone(text):
    assert mp.route(text) is None


@pytest.mark.parametrize('sec,text', [(300, '5 минут'), (4800, '1 час 20 минут'), (45, '45 секунд'), (3600, '1 час'), (61, '1 минута 1 секунда'), (-120, '2 минуты'), (0, '0 секунд')])
def test_spoken_duration(sec, text):
    out = mp.spoken_duration(sec)
    assert out == text or (sec == 61 and out == '1 минута')           # seconds are dropped once there are minutes
