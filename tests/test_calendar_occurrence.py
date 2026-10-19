"""Changing, moving, resetting and removing one occurrence of a repeating own event."""
import json
from datetime import date

import pytest

import core.settings_io as sio
from actions import calendar_hub as hub
from actions import calendar_parse as cp
from ui_next import bridge
from ui_next.bridge import calendar as cal


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = tmp_path / 'settings.json'
    settings.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(settings))
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    monkeypatch.setattr(cal, '_enable_module', lambda: None)
    hub._cache.clear()
    return tmp_path


def own(**kw):
    return hub.add_local({'title': 'Dentist', 'date': '2026-10-20', 'time': '15:00', **kw})


def gym(**kw):
    return own(title='Gym', date='2026-10-05', time='07:00', repeat='weekly', weekdays=[0], **kw)       # Mondays: 5, 12, 19, 26 Oct


def day(d0, d1='2026-10-31'):
    return hub.events_between(date.fromisoformat(d0), date.fromisoformat(d1))['events']


def test_one_occurrence_can_change_title_time_and_place(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-12', {'title': 'Gym (with coach)', 'time': '09:00', 'end_time': '10:00', 'location': 'Hall 2'})
    got = {x['date']: x for x in day('2026-10-05')}
    one = got['2026-10-12']
    assert one['title'] == 'Gym (with coach)' and (one['time'], one['end_time'], one['location']) == ('09:00', '10:00', 'Hall 2')
    assert one['changed'] and one['occ'] == '2026-10-12' and one['id'] == f"{e['id']}:2026-10-12"
    assert got['2026-10-19']['title'] == 'Gym' and not got['2026-10-19']['changed'] and got['2026-10-19']['time'] == '07:00'


def test_a_moved_occurrence_keeps_its_original_id_and_shows_on_the_new_day(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-12', {'date': '2026-10-14', 'end_date': '2026-10-14', 'time': '18:00', 'end_time': '19:00'})
    assert [x['date'] for x in day('2026-10-05')] == ['2026-10-05', '2026-10-14', '2026-10-19', '2026-10-26']
    moved = day('2026-10-14', '2026-10-14')[0]
    assert moved['id'] == f"{e['id']}:2026-10-12" and moved['occ'] == '2026-10-12' and day('2026-10-12', '2026-10-12') == []


def test_a_moved_occurrence_is_found_when_only_its_new_day_is_in_the_window(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-26', {'date': '2026-11-03', 'end_date': '2026-11-03'})
    assert [x['date'] for x in day('2026-11-03', '2026-11-03') if x['title'] == 'Gym'] == ['2026-11-03']


def test_changing_a_changed_occurrence_again_and_resetting_it(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-19', {'title': 'A'})
    hub.update_occurrence(e['id'], '2026-10-19', {'title': 'B', 'location': 'X'})
    assert [x['title'] for x in day('2026-10-19', '2026-10-19')] == ['B']
    assert hub.reset_occurrence(e['id'], '2026-10-19') and [x['title'] for x in day('2026-10-19', '2026-10-19')] == ['Gym']
    assert hub.reset_occurrence(e['id'], '2026-10-19') is False


def test_deleting_a_changed_day_removes_it_and_bad_dates_are_refused(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-12', {'title': 'Changed'})
    hub.delete_local(e['id'], only_date='2026-10-12')
    assert [x['date'] for x in day('2026-10-05')] == ['2026-10-05', '2026-10-19', '2026-10-26'] and hub.load_local()[0]['overrides'] == {}
    for bad, code in (('2026-10-13', 'not_an_occurrence'), ('x', 'bad_date')):
        with pytest.raises(hub.CalendarError) as ex:
            hub.update_occurrence(e['id'], bad, {'title': 'z'})
        assert ex.value.code == code
    with pytest.raises(hub.CalendarError) as ex:
        hub.update_occurrence(own()['id'], '2026-10-20', {'title': 'z'})
    assert ex.value.code == 'not_repeating'


def test_changing_the_series_schedule_drops_single_day_changes_but_a_title_does_not(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-12', {'title': 'Changed'})
    hub.update_local(e['id'], {'title': 'Gym 2'})
    assert hub.load_local()[0]['overrides']['2026-10-12']['title'] == 'Changed'
    hub.update_local(e['id'], {'time': '08:00', 'end_time': '09:00'})
    assert hub.load_local()[0]['overrides'] == {}


def test_changed_occurrence_is_exported_with_recurrence_id(env):
    e = gym()
    hub.update_occurrence(e['id'], '2026-10-12', {'title': 'Changed', 'time': '09:00', 'end_time': '10:00'})
    text = (env / 'local_events.ics').read_text(encoding='utf-8')
    assert 'RECURRENCE-ID:20261012T070000' in text and 'SUMMARY:Changed' in text
    got = [(x.local_start().strftime('%m-%d %H:%M'), x.title) for x in cp.parse_events(text, None, None, limit=50) if x.local_start().month == 10 and x.local_start().day < 20]
    assert ('10-12 09:00', 'Changed') in got and ('10-12 07:00', 'Gym') not in got and ('10-05 07:00', 'Gym') in got


def test_an_event_with_a_broken_override_is_skipped_not_half_read(env):
    gym()
    raw = json.loads((env / 'local_events.json').read_text(encoding='utf-8'))
    raw[0]['overrides'] = {'2026-10-19': {'title': ''}}
    (env / 'local_events.json').write_text(json.dumps(raw), encoding='utf-8')
    assert hub.load_local() == []


def run(op, **kw):
    return bridge.run_command('calendar', {'op': op, **kw})


def test_one_occurrence_through_the_command(env):
    e = run('add', title='Gym', date='2026-10-05', time='07:00', repeat='weekly', weekdays=[0])['event']
    r = run('update_one', eid=e['id'], occ='2026-10-12', title='Gym 2', time='09:00', end_time='10:00')
    assert r['ok'] and r['event']['overrides']['2026-10-12']['title'] == 'Gym 2'
    got = run('events', **{'from': '2026-10-12', 'to': '2026-10-12'})['events']
    assert got[0]['title'] == 'Gym 2' and got[0]['changed'] and got[0]['occ'] == '2026-10-12'
    assert run('reset_one', eid=e['id'], occ='2026-10-12') == {'ok': True} and run('reset_one', eid=e['id'], occ='2026-10-12')['error'] == 'unknown_event'
    assert run('update_one', eid=e['id'], occ='2026-10-13', title='x')['error'] == 'not_an_occurrence'
