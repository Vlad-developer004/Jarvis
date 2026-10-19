"""ICS parsing: the bugs found in the calendar audit (upcoming events lost behind a long history, recurring series stopping after 200
occurrences, time zones ignored) plus end times, all-day events, place and notes, RECURRENCE-ID and the richer recurrence rules."""
from datetime import datetime, timedelta, timezone

import pytest

import actions.calendar_ics as ics
from actions import calendar_parse as cp


def ev(body: str) -> str:
    return f'BEGIN:VCALENDAR\nBEGIN:VEVENT\n{body}\nEND:VEVENT\nEND:VCALENDAR'


def window(raw, a, b, **kw):
    return cp.parse_events(raw, a, b, **kw)


# ---- the audit bugs ----

def test_upcoming_event_is_not_lost_behind_a_long_history():
    old = ''.join(f'BEGIN:VEVENT\nDTSTART:2024{(i % 12) + 1:02d}{(i % 27) + 1:02d}T090000Z\nSUMMARY:old{i}\nEND:VEVENT\n' for i in range(150))
    soon = (datetime.now(timezone.utc) + timedelta(days=2)).strftime('%Y%m%dT%H%M%SZ')
    raw = old + f'BEGIN:VEVENT\nDTSTART:{soon}\nSUMMARY:UPCOMING\nEND:VEVENT\n'
    found = ics._collect_upcoming({'calendar_sources': [{'path': 'x'}]}) if False else None
    now = datetime.now()
    got = cp.parse_events(raw, now, now + timedelta(days=60))
    assert [e.title for e in got] == ['UPCOMING'] and found is None


def test_daily_series_from_years_ago_reaches_today():
    raw = ev('UID:d\nDTSTART:20200101T090000Z\nRRULE:FREQ=DAILY\nSUMMARY:Daily')
    now = datetime.now()
    got = window(raw, now, now + timedelta(days=3))
    assert 3 <= len(got) <= 4 and all(e.title == 'Daily' for e in got)


def test_count_is_counted_from_the_first_occurrence_not_from_the_window():
    raw = ev('UID:c\nDTSTART:20260101T090000Z\nRRULE:FREQ=DAILY;COUNT=10\nSUMMARY:Ten')
    got = window(raw, datetime(2026, 1, 8), datetime(2026, 2, 1))
    assert [cp.local(e.start).day for e in got] == [8, 9, 10]


def test_tzid_is_converted_to_local_time():
    raw = ev('DTSTART;TZID=America/New_York:20261020T090000\nDTEND;TZID=America/New_York:20261020T100000\nSUMMARY:NY')
    e = window(raw, None, None)[0]
    assert e.start.tzinfo is not None and e.end - e.start == timedelta(hours=1)
    assert e.start.astimezone(timezone.utc).hour in (13, 14)                      # 9:00 in New York is 13:00 or 14:00 UTC
    assert cp.local(e.start) == e.start.astimezone().replace(tzinfo=None)


# ---- fields ----

def test_end_duration_location_notes_and_escapes():
    raw = ev('DTSTART:20261020T090000\nDURATION:PT1H30M\nSUMMARY:Talk\\, part 1\nLOCATION:Room\\; 5\nDESCRIPTION:Line one\\nLine two')
    e = window(raw, None, None)[0]
    assert e.title == 'Talk, part 1' and e.location == 'Room; 5' and e.notes == 'Line one\nLine two'
    assert e.end - e.start == timedelta(minutes=90) and not e.all_day


def test_all_day_events_have_an_exclusive_end_and_overlap_by_day():
    raw = ev('DTSTART;VALUE=DATE:20261024\nDTEND;VALUE=DATE:20261027\nSUMMARY:Trip')
    e = window(raw, None, None)[0]
    assert e.all_day and e.local_start() == datetime(2026, 10, 24) and e.local_end() == datetime(2026, 10, 27)
    assert window(raw, datetime(2026, 10, 26), datetime(2026, 10, 26, 23, 59))
    assert not window(raw, datetime(2026, 10, 27), datetime(2026, 10, 27, 23, 59))
    assert not window(raw, datetime(2026, 10, 23), datetime(2026, 10, 23, 23, 59))


def test_event_without_summary_and_status_cancelled():
    assert window(ev('DTSTART:20261020T090000'), None, None)[0].title == '(без названия)'
    assert window(ev('DTSTART:20261020T090000\nSTATUS:CANCELLED\nSUMMARY:No'), None, None) == []


# ---- recurrence ----

def test_exdate_and_interval():
    raw = ev('UID:e\nDTSTART:20261001T090000\nRRULE:FREQ=DAILY;INTERVAL=2;COUNT=4\nEXDATE:20261003T090000\nSUMMARY:E')
    assert [e.local_start().day for e in window(raw, None, None)] == [1, 5, 7]


def test_weekly_byday_with_interval():
    raw = ev('UID:w\nDTSTART:20261005T100000\nRRULE:FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,TH;COUNT=4\nSUMMARY:W')   # 2026-10-05 is a Monday
    assert [e.local_start().strftime('%m-%d') for e in window(raw, None, None)] == ['10-05', '10-08', '10-19', '10-22']


def test_monthly_nth_weekday_and_last_weekday():
    second_mon = ev('UID:m\nDTSTART:20261012T090000\nRRULE:FREQ=MONTHLY;BYDAY=2MO;COUNT=3\nSUMMARY:M')
    assert [e.local_start().strftime('%m-%d') for e in window(second_mon, None, None)] == ['10-12', '11-09', '12-14']
    last_fri = ev('UID:l\nDTSTART:20261030T090000\nRRULE:FREQ=MONTHLY;BYDAY=-1FR;COUNT=3\nSUMMARY:L')
    assert [e.local_start().strftime('%m-%d') for e in window(last_fri, None, None)] == ['10-30', '11-27', '12-25']


def test_monthly_bymonthday_and_end_of_month_clamp():
    raw = ev('UID:b\nDTSTART:20260115T090000\nRRULE:FREQ=MONTHLY;BYMONTHDAY=15,-1;COUNT=4\nSUMMARY:B')
    assert [e.local_start().strftime('%m-%d') for e in window(raw, None, None)] == ['01-15', '01-31', '02-15', '02-28']
    clamp = ev('UID:k\nDTSTART:20260131T090000\nRRULE:FREQ=MONTHLY;COUNT=3\nSUMMARY:K')
    assert [e.local_start().month for e in window(clamp, None, None)] == [1, 2, 3]


def test_until_date_only_includes_that_day():
    raw = ev('UID:u\nDTSTART:20261001T090000\nRRULE:FREQ=DAILY;UNTIL=20261003\nSUMMARY:U')
    assert len(window(raw, None, None)) == 3


def test_moved_and_cancelled_instances():
    raw = ('BEGIN:VEVENT\nUID:s\nDTSTART:20261001T090000\nRRULE:FREQ=DAILY;COUNT=4\nSUMMARY:Series\nEND:VEVENT\n'
           'BEGIN:VEVENT\nUID:s\nRECURRENCE-ID:20261002T090000\nDTSTART:20261002T150000\nSUMMARY:Series (moved)\nEND:VEVENT\n'
           'BEGIN:VEVENT\nUID:s\nRECURRENCE-ID:20261003T090000\nDTSTART:20261003T090000\nSTATUS:CANCELLED\nSUMMARY:x\nEND:VEVENT\n')
    got = [(e.local_start().strftime('%d %H'), e.title) for e in window(raw, None, None)]
    assert got == [('01 09', 'Series'), ('02 15', 'Series (moved)'), ('04 09', 'Series')]


def test_instance_moved_into_the_window_from_outside_it():
    raw = ('BEGIN:VEVENT\nUID:s\nDTSTART:20261001T090000\nRRULE:FREQ=DAILY;COUNT=10\nSUMMARY:Series\nEND:VEVENT\n'
           'BEGIN:VEVENT\nUID:s\nRECURRENCE-ID:20261002T090000\nDTSTART:20261120T090000\nSUMMARY:Moved far\nEND:VEVENT\n')
    got = window(raw, datetime(2026, 11, 19), datetime(2026, 11, 21))
    assert [e.title for e in got] == ['Moved far']


def test_unsupported_freq_is_a_single_occurrence():
    assert len(window(ev('DTSTART:20260101T090000\nRRULE:FREQ=SECONDLY;COUNT=5\nSUMMARY:W'), None, None)) == 1


def test_limit_and_sort():
    raw = ''.join(f'BEGIN:VEVENT\nDTSTART:202610{20 - i:02d}T090000\nSUMMARY:E{i}\nEND:VEVENT\n' for i in range(5))
    got = window(raw, None, None, limit=3)
    assert [e.local_start().day for e in got] == [16, 17, 18]


# ---- the settings-driven layer ----

def test_collect_upcoming_sees_events_behind_a_long_history(monkeypatch):
    old = ''.join(f'BEGIN:VEVENT\nDTSTART:2024{(i % 12) + 1:02d}{(i % 27) + 1:02d}T090000Z\nSUMMARY:old{i}\nEND:VEVENT\n' for i in range(150))
    soon = (datetime.now(timezone.utc) + timedelta(days=2)).strftime('%Y%m%dT%H%M%SZ')
    monkeypatch.setattr(ics, '_fetch_text', lambda ref: (True, old + f'BEGIN:VEVENT\nDTSTART:{soon}\nSUMMARY:UPCOMING\nEND:VEVENT\n'))
    got = ics._collect_upcoming({'calendar_sources': [{'path': 'x'}]})
    assert [t for _, t, _ in got] == ['UPCOMING']


def test_all_day_event_counts_today_and_is_said_as_all_day(monkeypatch):
    day = datetime.now().strftime('%Y%m%d')
    monkeypatch.setattr(ics, '_fetch_text', lambda ref: (True, f'BEGIN:VEVENT\nDTSTART;VALUE=DATE:{day}\nSUMMARY:Holiday\nEND:VEVENT'))
    s = {'calendar_sources': [{'path': 'x', 'name': 'Work'}]}
    assert 'весь день — Holiday (источник: Work)' in ics.next_events_summary(s)
    assert ics.next_event_dt(s) is None                                            # the weather cross-check wants a timed event


def test_hidden_source_is_not_read(monkeypatch):
    monkeypatch.setattr(ics, '_fetch_text', lambda ref: pytest.fail('hidden source was fetched'))
    assert ics._collect_upcoming({'calendar_sources': [{'path': 'x', 'hidden': True}]}) == []
