"""actions/calendar_quick.py: phrases to events (quick add on the calendar screen and the voice command)."""
from datetime import date

import pytest

from actions.calendar_quick import parse_phrase

TODAY = date(2026, 10, 18)          # a Sunday


def p(text, **kw):
    return parse_phrase(text, TODAY, **kw)


@pytest.mark.parametrize('text,title,day,time', [
    ('завтра в 15:00 встреча с Аней', 'Встреча с Аней', '2026-10-19', '15:00'),
    ('послезавтра в 9 утра планёрка', 'Планёрка', '2026-10-20', '09:00'),
    ('сегодня в 7 вечера ужин', 'Ужин', '2026-10-18', '19:00'),
    ('в пятницу в 18 30 футбол', 'Футбол', '2026-10-23', '18:30'),
    ('12 ноября в 7 вечера ужин', 'Ужин', '2026-11-12', '19:00'),
    ('25.12 день рождения Максима', 'День рождения Максима', '2026-12-25', ''),
    ('1 января праздник', 'Праздник', '2027-01-01', ''),
    ('через 2 дня стоматолог', 'Стоматолог', '2026-10-20', ''),
    ('через неделю отчёт', 'Отчёт', '2026-10-25', ''),
    ('через две недели отпуск', 'Отпуск', '2026-11-01', ''),
    ('в воскресенье обед у бабушки', 'Обед у бабушки', '2026-10-25', ''),              # today is Sunday: the next one
    ('на 3 часа дня созвон завтра', 'Созвон', '2026-10-19', '15:00'),
])
def test_dates_times_and_titles(text, title, day, time):
    r = p(text)
    assert (r['title'], r['date'], r['time']) == (title, day, time)


def test_time_range_and_end():
    r = p('сегодня с 14:00 до 15:30 созвон')
    assert (r['title'], r['date'], r['time'], r['end_time']) == ('Созвон', '2026-10-18', '14:00', '15:30')


@pytest.mark.parametrize('text,repeat,weekdays', [('каждый день зарядка в 7:30', 'daily', []), ('планёрка каждую неделю в пятницу в 9 утра', 'weekly', []), ('ежемесячно оплатить аренду', 'monthly', []),
                                                    ('каждый год день рождения мамы 3 мая', 'yearly', []), ('каждый понедельник спортзал в 19:00', 'weekly', [0]), ('щотижня зустріч у п\'ятницю', 'weekly', [])])
def test_repeats(text, repeat, weekdays):
    r = p(text)
    assert r['repeat'] == repeat and r['weekdays'] == weekdays and r['title']


def test_a_weekday_repeat_starts_on_the_next_such_day():
    r = p('каждый понедельник спортзал в 19:00')
    assert r['date'] == '2026-10-19' and r['time'] == '19:00' and r['title'] == 'Спортзал'


def test_only_a_time_or_a_repeat_uses_the_default_day():
    assert p('в 15:00 позвонить', default_date=date(2026, 10, 22))['date'] == '2026-10-22'
    assert p('позвонить')['date'] == '' and p('позвонить')['title'] == 'Позвонить'
    assert p('')['title'] == ''


def test_ukrainian():
    r = p('завтра о 15:00 зустріч з Аней')
    assert (r['title'], r['date'], r['time']) == ('Зустріч з Аней', '2026-10-19', '15:00')
    assert p('післязавтра стоматолог')['date'] == '2026-10-20' and p('12 листопада вечеря')['date'] == '2026-11-12'


def test_bad_dates_and_hours_are_ignored():
    r = p('31.02 что-то в 25:00')
    assert r['date'] == '' and r['time'] == ''


def test_the_bridge_parses_a_phrase_with_a_default_day():
    from ui_next import bridge
    r = bridge.run_command('calendar', {'op': 'quick', 'text': 'в 15:00 позвонить', 'date': '2026-10-22'})
    assert r['ok'] and (r['title'], r['date'], r['time']) == ('Позвонить', '2026-10-22', '15:00')
    assert bridge.run_command('calendar', {'op': 'quick', 'text': 'x', 'date': 'garbage'})['date'] == ''
