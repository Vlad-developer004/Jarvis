"""core/nlp/clock_time.py: a time of day in a timer phrase."""
from datetime import datetime

import pytest

from core.nlp.clock_time import parse_clock, seconds_until


@pytest.mark.parametrize('said,want', [
    ('поставь таймер на 13 15', (13, 15)), ('поставь таймер на тринадцать пятнадцать', (13, 15)), ('таймер до 13:15', (13, 15)),
    ('таймер на тринадцать ноль пять', (13, 5)), ('таймер на двенадцать ноль ноль', (12, 0)), ('таймер на 13 0', (13, 0)),
    ('таймер на восемь тридцать вечера', (20, 30)), ('таймер на двенадцать тридцать ночи', (0, 30)),
    ('таймер на двадцать три пятьдесят девять', (23, 59))])
def test_clock_times(said, want):
    assert parse_clock(said) == want


@pytest.mark.parametrize('said', ['таймер на 13 часов 15 минут', 'таймер на 15 минут', 'таймер на 25 70', 'таймер на 24 10', 'поставь таймер на семь', 'поставь таймер'])
def test_lengths_and_nonsense_are_not_clock_times(said):
    assert parse_clock(said) is None


def test_seconds_until_today_or_tomorrow():
    now = datetime(2026, 10, 21, 11, 0, 30)
    assert seconds_until((13, 15), now) == 2 * 3600 + 15 * 60 - 30
    assert seconds_until((9, 0), now) == 22 * 3600 - 30
    assert seconds_until((11, 0), now) == 24 * 3600 - 30      # exactly passed: tomorrow
