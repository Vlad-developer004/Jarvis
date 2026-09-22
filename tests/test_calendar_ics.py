"""Tests for actions/calendar_ics.py — previously untested. Covers plain
VEVENT parsing, the new RRULE/EXDATE recurring-event expansion, and the
_collect_upcoming/next_event_dt/next_events_summary layer on top of it."""
from datetime import datetime, timedelta, timezone

import actions.calendar_ics as cal


# ── plain (non-recurring) events ────────────────────────────────────

def test_parse_single_event():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:20260925T090000Z
SUMMARY:Standup
END:VEVENT
END:VCALENDAR"""
    events = cal.parse_ics_events(ics)
    assert len(events) == 1
    dt, title = events[0]
    assert title == 'Standup'
    assert dt == datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)


def test_parse_event_without_summary_uses_placeholder():
    ics = "BEGIN:VEVENT\nDTSTART:20260925T090000Z\nEND:VEVENT"
    events = cal.parse_ics_events(ics)
    assert events[0][1] == '(без названия)'


def test_parse_events_sorted_by_start_time():
    ics = """BEGIN:VEVENT
DTSTART:20260927T090000Z
SUMMARY:Later
END:VEVENT
BEGIN:VEVENT
DTSTART:20260925T090000Z
SUMMARY:Earlier
END:VEVENT"""
    events = cal.parse_ics_events(ics)
    assert [t for _, t in events] == ['Earlier', 'Later']


def test_parse_events_respects_limit():
    blocks = '\n'.join(
        f"BEGIN:VEVENT\nDTSTART:202609{25+i:02d}T090000Z\nSUMMARY:E{i}\nEND:VEVENT"
        for i in range(5)
    )
    events = cal.parse_ics_events(blocks, limit=2)
    assert len(events) == 2


# ── RRULE expansion ──────────────────────────────────────────────────

def test_daily_rrule_expands_within_horizon():
    ics = """BEGIN:VEVENT
DTSTART:20260101T090000Z
RRULE:FREQ=DAILY;COUNT=5
SUMMARY:Daily standup
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    assert len(events) == 5
    dates = [dt.day for dt, _ in events]
    assert dates == [1, 2, 3, 4, 5]


def test_weekly_rrule_with_byday_expands_matching_weekdays():
    # 2026-01-05 is a Monday.
    ics = """BEGIN:VEVENT
DTSTART:20260105T100000Z
RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT=6
SUMMARY:Gym
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    assert len(events) == 6
    weekdays = {dt.weekday() for dt, _ in events}
    assert weekdays == {0, 2, 4}  # Mon, Wed, Fri


def test_monthly_rrule_advances_by_month():
    ics = """BEGIN:VEVENT
DTSTART:20260131T090000Z
RRULE:FREQ=MONTHLY;COUNT=3
SUMMARY:Rent
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    months = [dt.month for dt, _ in events]
    assert months == [1, 2, 3]


def test_rrule_stops_at_until():
    ics = """BEGIN:VEVENT
DTSTART:20260101T090000Z
RRULE:FREQ=DAILY;UNTIL=20260103T090000Z
SUMMARY:Short series
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    assert len(events) == 3


def test_rrule_respects_horizon_when_no_count_or_until():
    start = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    ics = f"""BEGIN:VEVENT
DTSTART:{start}
RRULE:FREQ=DAILY
SUMMARY:Forever
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=5)
    assert 1 < len(events) <= 6


def test_exdate_removes_a_specific_occurrence():
    ics = """BEGIN:VEVENT
DTSTART:20260101T090000Z
RRULE:FREQ=DAILY;COUNT=3
EXDATE:20260102T090000Z
SUMMARY:With exception
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    days = [dt.day for dt, _ in events]
    assert days == [1, 3]


def test_unsupported_freq_falls_back_to_single_occurrence():
    ics = """BEGIN:VEVENT
DTSTART:20260101T090000Z
RRULE:FREQ=SECONDLY;COUNT=5
SUMMARY:Weird
END:VEVENT"""
    events = cal.parse_ics_events(ics, horizon_days=3650)
    assert len(events) == 1


# ── _collect_upcoming / next_event_dt / next_events_summary ────────

def test_next_events_summary_reports_unconfigured_calendar():
    assert 'не настроен' in cal.next_events_summary({})


def test_next_events_summary_reports_no_events(monkeypatch):
    monkeypatch.setattr(cal, '_fetch_text', lambda ref: (True, 'BEGIN:VCALENDAR\nEND:VCALENDAR'))
    settings = {'calendar_sources': [{'path': 'dummy.ics'}]}
    msg = cal.next_events_summary(settings)
    assert 'Нет ближайших событий' in msg


def test_next_event_dt_returns_soonest_future_event(monkeypatch):
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y%m%dT%H%M%SZ')
    ics = f"BEGIN:VEVENT\nDTSTART:{future}\nSUMMARY:Meeting\nEND:VEVENT"
    monkeypatch.setattr(cal, '_fetch_text', lambda ref: (True, ics))
    settings = {'calendar_sources': [{'path': 'dummy.ics'}]}
    result = cal.next_event_dt(settings)
    assert result is not None
    dt, title = result
    assert title == 'Meeting'


def test_next_event_dt_filters_out_past_events(monkeypatch):
    past = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y%m%dT%H%M%SZ')
    ics = f"BEGIN:VEVENT\nDTSTART:{past}\nSUMMARY:Old\nEND:VEVENT"
    monkeypatch.setattr(cal, '_fetch_text', lambda ref: (True, ics))
    settings = {'calendar_sources': [{'path': 'dummy.ics'}]}
    assert cal.next_event_dt(settings) is None


def test_collect_upcoming_returns_empty_without_sources():
    assert cal._collect_upcoming({}) == []
