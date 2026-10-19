import json
from datetime import date

import pytest

import core.settings_io as sio
from actions import calendar_hub as hub
from actions import calendar_ics as ics
from ui_next import bridge
from ui_next.bridge import calendar as cal

ICS = 'BEGIN:VEVENT\nUID:s1\nDTSTART:20261020T090000\nDTEND:20261020T100000\nSUMMARY:Standup\nEND:VEVENT\n'


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = tmp_path / 'settings.json'
    settings.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(settings))
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    monkeypatch.setattr(cal, '_enable_module', lambda: sio.update({'enabled_called': True}))
    hub._cache.clear()
    hub._errors.clear()
    return tmp_path


def run(op, **kw):
    return bridge.run_command('calendar', {'op': op, **kw})


def test_add_update_delete_through_the_command(env):
    r = run('add', title='Dentist', date='2026-10-22', time='15:30', location='Clinic', repeat='weekly', weekdays=[3])
    assert r['ok'] and r['event']['end_time'] == '16:30' and json.loads((env / 'settings.json').read_text(encoding='utf-8'))['enabled_called'] is True
    eid = r['event']['id']
    assert run('update', eid=eid, title='Dentist 2', time='16:00', end_time='17:00')['event']['title'] == 'Dentist 2'
    got = run('events', **{'from': '2026-10-20', 'to': '2026-10-31'})['events']
    assert [e['date'] for e in got] == ['2026-10-22', '2026-10-29'] and got[0]['location'] == 'Clinic'
    assert run('delete', eid=eid, only_date='2026-10-29') == {'ok': True}
    assert [e['date'] for e in run('events', **{'from': '2026-10-20', 'to': '2026-10-31'})['events']] == ['2026-10-22']
    assert run('delete', eid=eid) == {'ok': True} and run('delete', eid=eid)['error'] == 'unknown_event'


def test_errors_come_back_as_codes(env):
    assert run('add', title=' ', date='2026-10-22', time='10:00')['error'] == 'no_title'
    assert run('add', title='x', date='2026-10-22', time='10:00', end_time='09:00')['error'] == 'bad_range'
    assert run('update', eid='nope', title='x')['error'] == 'unknown_event'
    assert run('events', **{'from': '2026-10-10', 'to': '2026-10-01'})['error'] == 'bad_range'
    assert run('events', **{'from': '2026-01-01', 'to': '2026-12-31'})['error'] == 'bad_range'
    assert run('events', **{'from': 'x', 'to': 'y'})['error'] == 'bad_range'
    assert run('zzz')['error'] == 'bad_op'


def test_fields_the_ui_may_send_are_whitelisted(env):
    r = run('add', title='x', date='2026-10-22', time='10:00', id='hijack', exceptions=['2026-10-22'])
    assert r['event']['id'] != 'hijack' and r['event']['exceptions'] == []


def test_sources_names_colours_visibility_and_failures(env, monkeypatch):
    assert run('add_source', ref='https://x.example/a.ics', name='Work')['ok']
    assert run('add_source', ref='https://x.example/a.ics')['error'] == 'exists' and run('add_source', ref='')['error'] == 'bad_source'
    src = run('state')['sources'][0]
    assert (src['name'], src['hidden'], src['status']) == ('Work', False, 'unknown')
    assert run('source_set', ref='https://x.example/a.ics', name='Job', color='#4c8dff', hidden=True)['state']['sources'][0] | {} == {**src, 'name': 'Job', 'color': '#4c8dff', 'hidden': True}
    assert run('source_set', ref='https://x.example/a.ics', color='blue')['error'] == 'bad_color' and run('source_set', ref='nope', name='x')['error'] == 'unknown_source'
    assert run('remove_source', ref='https://x.example/a.ics')['state']['sources'] == []


def test_ics_file_import_copies_the_file_next_to_the_settings(env, monkeypatch):
    src = env / 'my cal.ics'
    src.write_text(ICS, encoding='utf-8')
    monkeypatch.setattr(cal, '_pick_paths', lambda: [str(src)])
    r = run('import_file')
    dest = r['state']['sources'][0]['ref']
    assert r['ok'] and dest.startswith(str(env / 'calendars')) and open(dest, encoding='utf-8').read() == ICS and r['state']['sources'][0]['name'] == 'my cal'
    assert run('import_file')['ok'] and run('state')['sources'][1]['ref'].endswith('(2).ics')
    monkeypatch.setattr(cal, '_pick_paths', lambda: [])
    assert run('import_file')['error'] == 'cancelled'
    bad = env / 'x.txt'
    bad.write_text('x')
    monkeypatch.setattr(cal, '_pick_paths', lambda: [str(bad)])
    assert run('import_file')['error'] == 'bad_file'


def test_events_of_a_source_and_search(env, monkeypatch):
    sio.update({'calendar_sources': [{'path': 'good.ics', 'name': 'Work'}]})
    monkeypatch.setattr(ics, '_fetch_text', lambda ref: (True, ICS))
    r = run('events', **{'from': '2026-10-19', 'to': '2026-10-25'})
    assert [(e['title'], e['source'], e['local']) for e in r['events']] == [('Standup', 'Work', False)] and r['status'] == [{'ref': 'good.ics', 'ok': True, 'stale': False}]
    assert run('state')['sources'][0]['status'] == 'ok'
    assert run('search', q='x') == {'ok': True, 'events': []}


def test_reminder_settings(env):
    assert run('remind', enabled=False, minutes=30)['state']['remind'] == {'enabled': False, 'minutes': 30}
    assert run('remind', enabled=True, minutes=500)['error'] == 'bad_minutes' and run('remind', enabled=True, minutes='x')['error'] == 'bad_minutes'
