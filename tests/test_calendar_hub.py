"""actions/calendar_hub.py: own events (validation, repeat, exceptions, the old file format), the download cache, one query for all sources,
search, and which spoken reminders are due."""
import json
from datetime import date, datetime, timedelta

import pytest

import core.settings_io as sio
from actions import calendar_hub as hub
from actions import calendar_ics as ics


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = tmp_path / 'settings.json'
    settings.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(settings))
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    hub._cache.clear()
    hub._errors.clear()
    return tmp_path


def own(**kw):
    base = {'title': 'Dentist', 'date': '2026-10-20', 'time': '15:00'}
    return hub.add_local({**base, **kw})


# ---- own events ----

def test_defaults_and_a_one_hour_end(env):
    e = own()
    assert (e['end_date'], e['end_time'], e['all_day'], e['repeat'], e['remind']) == ('2026-10-20', '16:00', False, 'none', None)
    day = own(title='Trip', time='', end_date='2026-10-22')
    assert day['all_day'] and day['end_date'] == '2026-10-22' and day['time'] == ''


def test_default_end_rolls_into_the_next_day_after_2300(env):
    e = own(time='23:30')
    assert (e['end_date'], e['end_time']) == ('2026-10-21', '00:30')
    assert own(time='20:00', end_date='2026-10-22')['end_time'] == '20:00'                 # an end date without a time keeps the start time


@pytest.mark.parametrize('bad,code', [({'title': '  '}, 'no_title'), ({'date': '20.10.2026'}, 'bad_date'), ({'time': '25:00'}, 'bad_time'), ({'end_time': '14:00'}, 'bad_range'),
                                      ({'repeat': 'hourly'}, 'bad_repeat'), ({'until': '2026-10-01'}, 'bad_until'), ({'color': 'red'}, 'bad_color'),
                                      ({'remind': [0]}, 'bad_remind'), ({'remind': ['x']}, 'bad_remind'), ({'time': '', 'all_day': False}, 'bad_time')])
def test_validation(env, bad, code):
    with pytest.raises(hub.CalendarError) as ex:
        own(**bad)
    assert ex.value.code == code


def test_update_keeps_what_is_not_mentioned(env):
    e = own(location='Clinic', color='#22d3ee')
    u = hub.update_local(e['id'], {'title': 'Dentist 2', 'time': '16:00', 'end_time': '17:00'})
    assert (u['title'], u['time'], u['location'], u['color']) == ('Dentist 2', '16:00', 'Clinic', '#22d3ee')
    with pytest.raises(hub.CalendarError):
        hub.update_local('nope', {})


def test_the_first_version_of_the_file_is_still_read(env):
    (env / 'local_events.json').write_text(json.dumps([{'id': 'a1', 'title': 'Old', 'date': '2026-10-20', 'time': '', 'repeat': 'weekly'},
                                                      {'id': 'a2', 'title': 'Old timed', 'date': '2026-10-21', 'time': '08:30', 'repeat': 'none'}, {'broken': 1}]), encoding='utf-8')
    got = {e['id']: e for e in hub.load_local()}
    assert got['a1']['all_day'] and got['a1']['repeat'] == 'weekly' and got['a2']['end_time'] == '09:30' and len(got) == 2


def test_repeat_expansion_and_exceptions(env):
    e = own(title='Gym', date='2026-10-05', time='07:00', repeat='weekly', weekdays=[0, 3])
    got = hub.events_between(date(2026, 10, 5), date(2026, 10, 18))['events']
    assert [x['date'] for x in got] == ['2026-10-05', '2026-10-08', '2026-10-12', '2026-10-15']
    hub.delete_local(e['id'], only_date='2026-10-08')
    got = hub.events_between(date(2026, 10, 5), date(2026, 10, 18))['events']
    assert [x['date'] for x in got] == ['2026-10-05', '2026-10-12', '2026-10-15']
    assert got[0]['id'] == f"{e['id']}:2026-10-05" and got[0]['eid'] == e['id'] and got[0]['local']
    assert hub.delete_local(e['id']) and hub.events_between(date(2026, 10, 5), date(2026, 10, 18))['events'] == []
    assert hub.delete_local(e['id']) is False


def test_interval_until_and_month_end(env):
    own(title='Every 2 days', date='2026-10-01', time='09:00', repeat='daily', interval=2, until='2026-10-07')
    own(title='Rent', date='2026-01-31', time='', repeat='monthly')
    got = hub.events_between(date(2026, 10, 1), date(2026, 10, 31))['events']
    assert [x['date'] for x in got if x['title'] == 'Every 2 days'] == ['2026-10-01', '2026-10-03', '2026-10-05', '2026-10-07']
    feb = hub.events_between(date(2026, 2, 1), date(2026, 2, 28))['events']
    assert [x['date'] for x in feb if x['title'] == 'Rent'] == ['2026-02-28']


def test_multi_day_all_day_event_is_reported_with_its_last_day(env):
    own(title='Trip', date='2026-10-24', time='', end_date='2026-10-26')
    got = hub.events_between(date(2026, 10, 25), date(2026, 10, 25))['events']
    assert len(got) == 1 and (got[0]['date'], got[0]['end_date'], got[0]['all_day']) == ('2026-10-24', '2026-10-26', True)


def test_export_file_has_end_place_and_rule(env):
    own(title='Talk, one', location='Room; 5', repeat='weekly', weekdays=[1], until='2026-12-01')
    text = (env / 'local_events.ics').read_text(encoding='utf-8')
    assert 'DTEND:20261020T160000' in text and 'LOCATION:Room\\; 5' in text and 'SUMMARY:Talk\\, one' in text
    assert 'RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=TU;UNTIL=20261201' in text


# ---- sources, cache, one query ----

ICS = 'BEGIN:VEVENT\nUID:x1\nDTSTART:20261020T090000\nDTEND:20261020T100000\nSUMMARY:Standup\nLOCATION:Zoom\nEND:VEVENT\n'


def test_sources_are_named_coloured_and_hidden_on_request(env):
    sio.update({'calendar_sources': [{'url': 'https://x.example/work.ics', 'name': 'Work', 'color': '#ff6b6b'}, {'path': 'C:/cals/home.ics', 'hidden': True},
                                     {'path': hub.ics_path()}]})
    info = hub.sources_info()
    assert [(i['name'], i['color'], i['hidden']) for i in info][0] == ('Work', '#ff6b6b', False)
    assert info[1]['name'] == 'home.ics' and info[1]['hidden'] is True and len(info) == 2             # the old own-events registration is dropped


def test_query_merges_sources_and_own_events_and_marks_failures(env, monkeypatch):
    sio.update({'calendar_sources': [{'path': 'good.ics', 'name': 'Work'}, {'path': 'bad.ics'}, {'path': 'hid.ics', 'hidden': True}]})

    def fake(ref):
        if ref == 'good.ics':
            return True, ICS
        if ref == 'bad.ics':
            raise OSError('down')
        pytest.fail('a hidden source was fetched')
    monkeypatch.setattr(ics, '_fetch_text', fake)
    own(title='Dentist')
    res = hub.events_between(date(2026, 10, 20), date(2026, 10, 20))
    assert [(e['title'], e['source'], e['time'], e['end_time'], e['location']) for e in res['events']] == [('Standup', 'Work', '09:00', '10:00', 'Zoom'), ('Dentist', 'Мои события', '15:00', '16:00', '')]
    assert res['status'] == [{'ref': 'good.ics', 'ok': True, 'stale': False}, {'ref': 'bad.ics', 'ok': False, 'stale': False}]


def test_download_cache_serves_stale_text_when_the_source_goes_down(env, monkeypatch):
    calls = []
    state = {'up': True}

    def fake(ref):
        calls.append(ref)
        if not state['up']:
            raise OSError('down')
        return True, ICS
    monkeypatch.setattr(ics, '_fetch_text', fake)
    assert hub.fetch('a.ics').status == 'ok' and hub.fetch('a.ics').status == 'ok' and len(calls) == 1     # cached
    state['up'] = False
    f = hub.fetch('a.ics', force=True)
    assert f.status == 'stale' and 'Standup' in f.text and hub.status_of('a.ics') == 'ok'
    assert hub.fetch('never.ics').status == 'error' and hub.status_of('never.ics') == 'error'


def test_search_looks_in_title_place_and_notes_both_ways_in_time(env):
    own(title='Dentist', date=(date.today() + timedelta(days=3)).isoformat(), notes='bring the card')
    own(title='Old lunch', date=(date.today() - timedelta(days=100)).isoformat(), location='Cafe Dentista')
    own(title='Else', date=date.today().isoformat())
    assert [e['title'] for e in hub.search('dentist')] == ['Dentist', 'Old lunch']
    assert [e['title'] for e in hub.search('bring')] == ['Dentist'] and hub.search('d') == []


# ---- reminders ----

def at(minutes: int):
    t = (datetime.now() + timedelta(minutes=minutes)).replace(second=0, microsecond=0)
    return t, t.strftime('%H:%M')


def test_default_lead_applies_to_timed_events_only(env):
    t, hm = at(10)
    own(title='Soon', date=t.date().isoformat(), time=hm, end_time='')
    own(title='All day', date=t.date().isoformat(), time='')
    got = hub.due_reminders(datetime.now(), 15)
    assert [g[2] for g in got] == ['Soon'] and 9 <= got[0][1] <= 10
    assert hub.due_reminders(datetime.now(), 5) == []                                  # not within 5 minutes yet
    assert hub.due_reminders(datetime.now(), 15, enabled=False) == []                  # reminders off


def test_own_event_can_set_its_own_lead_times_or_none(env):
    t, hm = at(50)
    own(title='Two leads', date=t.date().isoformat(), time=hm, end_time='', remind=[30, 60])
    own(title='Quiet', date=t.date().isoformat(), time=hm, end_time='', remind=[])
    got = hub.due_reminders(datetime.now(), 15)
    assert [(g[2], g[0].rsplit('|', 1)[1]) for g in got] == [('Two leads', '60')]
    assert [g[2] for g in hub.due_reminders(datetime.now() + timedelta(minutes=25), 15)] == ['Two leads', 'Two leads']
    assert [g[2] for g in hub.due_reminders(datetime.now(), 15, enabled=False)] == ['Two leads']      # the event's own list works with the global switch off


def test_the_loop_says_each_reminder_once(env, monkeypatch):
    from features import calendar_reminders as cr
    monkeypatch.setattr(cr, '_path', lambda: str(env / 'said.json'))
    monkeypatch.setattr(cr, 'load_briefing_prefs', lambda: {'calendar_reminders_enabled': True, 'calendar_reminder_minutes': 15})
    cr._announced.clear()
    t, hm = at(12)
    own(title='Standup', date=t.date().isoformat(), time=hm, end_time='')
    first = cr.check_once()
    assert len(first) == 1 and first[0].endswith('Standup.') and first[0].startswith('Через ')
    assert cr.check_once() == []
    assert json.loads((env / 'said.json').read_text(encoding='utf-8'))
    assert cr.when_phrase(1) == '1 минуту' and cr.when_phrase(5) == '5 минут' and cr.when_phrase(21) == '21 минуту' and cr.when_phrase(120) == '2 часа' and cr.when_phrase(60) == '1 час'


def test_voice_summary_includes_own_events(env, monkeypatch):
    t, hm = at(90)
    own(title='Dentist', date=t.date().isoformat(), time=hm, end_time='')
    monkeypatch.setattr(ics, '_load_settings', lambda: {})
    assert 'Dentist (источник: Мои события)' in ics.next_events_summary(None)
    assert ics.next_event_dt(None)[1] == 'Dentist'
