"""A reminder with a day and a time ("напомни завтра в 10 ...") is stored as a calendar event with a one-minute lead; a relative one stays a timer."""
from datetime import date, datetime, timedelta

import pytest

from actions import calendar_hub as hub
from features import reminder


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))


def test_tomorrow_at_ten_becomes_a_calendar_event():
    ev = reminder.calendar_reminder('напомни завтра в десять купить хлеб')
    assert ev == {'title': 'Купить хлеб', 'date': (date.today() + timedelta(days=1)).isoformat(), 'time': '10:00'}
    saved = hub.load_local()
    assert saved[0]['title'] == 'Купить хлеб' and saved[0]['remind'] == [1] and saved[0]['time'] == '10:00'


def test_a_moment_that_is_gone_is_not_stored(monkeypatch):
    earlier = (datetime.now() - timedelta(hours=1)).strftime('%H:%M')
    if earlier > datetime.now().strftime('%H:%M'):        # just after midnight: yesterday's hour is "later" on the clock
        pytest.skip('clock wraps around midnight')
    assert reminder.calendar_reminder(f'напомни сегодня в {earlier} позвонить') == {'past': True}
    assert hub.load_local() == []


@pytest.mark.parametrize('said', ['напомни купить хлеб', 'напомни через час купить хлеб', 'напомни завтра купить хлеб'])
def test_without_day_and_time_nothing_is_stored(said):
    assert reminder.calendar_reminder(said) is None and hub.load_local() == []


def test_a_clock_time_flattened_by_the_speech_normalizer_still_parses():
    ev = reminder.calendar_reminder('напомни в пятницу в 1800 позвонить маме')
    assert ev and ev['time'] == '18:00' and ev['title'] == 'Позвонить маме'
