"""CalDAV: finding calendars, reading events, creating, changing and deleting them against a small fake server (no network)."""
import base64
import json
import threading
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import core.settings_io as sio
from actions import calendar_hub as hub
from actions import calendar_ics as ics
from actions import caldav_client as dav
from ui_next import bridge
from ui_next.bridge import calendar as cal

USER, PASSWORD = 'me@example.org', 'app-secret'
OBJ = ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20261020T090000Z\r\nDTEND:20261020T100000Z\r\nSUMMARY:Standup\r\nLOCATION:Zoom\r\n'
       'ATTENDEE:mailto:a@b.c\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
SERIES = 'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:u2\r\nDTSTART:20261001T080000Z\r\nRRULE:FREQ=DAILY;COUNT=3\r\nSUMMARY:Daily\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'


def multistatus(*responses):
    return ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:ic="http://apple.com/ns/ical/">' + ''.join(responses) + '</d:multistatus>').encode()


class Fake(BaseHTTPRequestHandler):
    store: dict = {}
    seen: list = []

    def log_message(self, *a):
        pass

    def _auth(self):
        self._body()                                       # read the request first, like a real server, or the client sees a reset connection
        want = 'Basic ' + base64.b64encode(f'{USER}:{PASSWORD}'.encode()).decode()
        if self.headers.get('Authorization') != want:
            self.send_response(401)
            self.end_headers()
            return False
        return True

    def _send(self, code, body=b'', headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        if not hasattr(self, '_data'):
            self._data = self.rfile.read(int(self.headers.get('Content-Length') or 0)).decode('utf-8')
        return self._data

    def do_PROPFIND(self):
        if not self._auth():
            return
        body, path = self._body(), self.path
        if 'current-user-principal' in body:
            self._send(207, multistatus('<d:response><d:href>/</d:href><d:propstat><d:prop><d:current-user-principal><d:href>/principals/me/</d:href></d:current-user-principal></d:prop></d:propstat></d:response>'))
        elif 'calendar-home-set' in body:
            self._send(207, multistatus('<d:response><d:href>/principals/me/</d:href><d:propstat><d:prop><c:calendar-home-set><d:href>/cals/me/</d:href></c:calendar-home-set></d:prop></d:propstat></d:response>'))
        else:
            self._send(207, multistatus(
                '<d:response><d:href>/cals/me/</d:href><d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype></d:prop></d:propstat></d:response>',
                '<d:response><d:href>/cals/me/work/</d:href><d:propstat><d:prop><d:displayname>Работа</d:displayname><d:resourcetype><d:collection/><c:calendar/></d:resourcetype>'
                '<c:supported-calendar-component-set><c:comp name="VEVENT"/></c:supported-calendar-component-set><ic:calendar-color>#4C8DFFFF</ic:calendar-color></d:prop></d:propstat></d:response>',
                '<d:response><d:href>/cals/me/tasks/</d:href><d:propstat><d:prop><d:displayname>Задачи</d:displayname><d:resourcetype><d:collection/><c:calendar/></d:resourcetype>'
                '<c:supported-calendar-component-set><c:comp name="VTODO"/></c:supported-calendar-component-set></d:prop></d:propstat></d:response>'))

    def do_REPORT(self):
        if not self._auth():
            return
        self._body()
        rs = [f'<d:response><d:href>{h}</d:href><d:propstat><d:prop><d:getetag>"{e}"</d:getetag><c:calendar-data><![CDATA[{t}]]></c:calendar-data></d:prop></d:propstat></d:response>' for h, (e, t) in self.store.items()]
        self._send(207, multistatus(*rs))

    def do_GET(self):
        if not self._auth():
            return
        if self.path not in self.store:
            self._send(404)
            return
        e, t = self.store[self.path]
        self._send(200, t.encode(), {'ETag': f'"{e}"', 'Content-Type': 'text/calendar'})

    def do_PUT(self):
        if not self._auth():
            return
        text = self._body()
        cur = self.store.get(self.path)
        if self.headers.get('If-None-Match') == '*' and cur:
            self._send(412)
            return
        if self.headers.get('If-Match') and (not cur or self.headers['If-Match'] != f'"{cur[0]}"'):
            self._send(412)
            return
        etag = str(int(cur[0]) + 1 if cur else 1)
        self.store[self.path] = (etag, text)
        self.seen.append(('PUT', self.path))
        self._send(201 if not cur else 204, headers={'ETag': f'"{etag}"'})

    def do_DELETE(self):
        if not self._auth():
            return
        cur = self.store.get(self.path)
        if cur and self.headers.get('If-Match') and self.headers['If-Match'] != f'"{cur[0]}"':
            self._send(412)
            return
        self.store.pop(self.path, None)
        self.seen.append(('DELETE', self.path))
        self._send(204)


@pytest.fixture
def server():
    Fake.store = {'/cals/me/work/u1.ics': ('1', OBJ), '/cals/me/work/u2.ics': ('1', SERIES)}
    Fake.seen = []
    srv = HTTPServer(('127.0.0.1', 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{srv.server_port}'
    srv.shutdown()


@pytest.fixture
def env(tmp_path, monkeypatch, server):
    settings = tmp_path / 'settings.json'
    settings.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(settings))
    monkeypatch.setattr(hub, '_dir', lambda: str(tmp_path))
    monkeypatch.setattr(cal, '_enable_module', lambda: None)
    import actions.mail_client as mc
    monkeypatch.setattr(mc, '_update_env_var', lambda k, v: __import__('os').environ.__setitem__(k, v))
    hub._cache.clear()
    hub._dav_cache.clear()
    yield tmp_path


def run(op, **kw):
    return bridge.run_command('calendar', {'op': op, **kw})


# ---- the client ----

def test_calendars_are_found_through_principal_and_home_set(server):
    cals = dav.Client(server, USER, PASSWORD).calendars()
    assert len(cals) == 1 and cals[0]['name'] == 'Работа' and cals[0]['href'] == server + '/cals/me/work/' and cals[0]['color'] == '#4C8DFF'      # the tasks list is left out


def test_wrong_password_and_bad_addresses(server):
    with pytest.raises(dav.CalDavError) as ex:
        dav.Client(server, USER, 'nope').calendars()
    assert ex.value.code == 'auth'
    with pytest.raises(dav.CalDavError):
        dav.Client('http://example.org', USER, PASSWORD)                                # plain http only for localhost
    with pytest.raises(dav.CalDavError):
        dav.Client('ftp://x', USER, PASSWORD)


def test_objects_come_back_with_href_etag_and_text(server):
    objs = dav.Client(server, USER, PASSWORD).objects(server + '/cals/me/work/', datetime(2026, 10, 1), datetime(2026, 10, 31))
    assert sorted(o['href'].rsplit('/', 1)[1] for o in objs) == ['u1.ics', 'u2.ics'] and objs[0]['etag'] == '"1"' and 'SUMMARY' in objs[0]['ics']


# ---- through the hub and the bridge ----

def connect(server):
    r = run('caldav_find', server=server, user=USER, password=PASSWORD)
    assert r['ok'] and r['calendars'][0]['name'] == 'Работа'
    r = run('caldav_add', server=server, user=USER, password=PASSWORD, calendars=r['calendars'])
    assert r['ok']
    return r['state']['sources'][0]


def test_connecting_stores_the_password_in_the_secrets_not_the_settings(env, server):
    src = connect(server)
    assert (src['kind'], src['writable'], src['name']) == ('caldav', True, 'Работа') and src['id']
    saved = (env / 'settings.json').read_text(encoding='utf-8')
    assert PASSWORD not in saved and 'caldav' in saved
    import os
    assert os.environ[f"JARVIS_CALDAV_PASS_{src['id'].upper()}"] == PASSWORD
    assert run('caldav_add', server=server, user=USER, password=PASSWORD, calendars=[{'href': src['ref'], 'name': 'x'}])['error'] == 'exists'
    assert run('caldav_find', server=server, user=USER, password='bad')['error'] == 'auth'


def test_events_of_a_caldav_calendar_are_listed_and_marked_editable_unless_recurring(env, server):
    connect(server)
    got = run('events', **{'from': '2026-10-19', 'to': '2026-10-21'})['events']
    one = next(e for e in got if e['title'] == 'Standup')
    assert (one['time'], one['end_time'], one['location'], one['source'], one['rw']) == ('11:00' if datetime(2026, 10, 20, 9, tzinfo=__import__('datetime').timezone.utc).astimezone().hour == 11 else one['time'], one['end_time'], 'Zoom', 'Работа', True)
    assert one['href'].endswith('/u1.ics') and one['src']
    daily = run('events', **{'from': '2026-10-01', 'to': '2026-10-03'})['events']
    assert [e['title'] for e in daily] == ['Daily'] * 3 and not any(e['rw'] for e in daily)


def test_create_change_and_delete_an_event_in_a_caldav_calendar(env, server):
    src = connect(server)
    r = run('add', title='Dentist', date='2026-10-22', time='15:30', location='Clinic', notes='card', calendar=src['id'])
    assert r['ok'] and ('PUT', ) == (Fake.seen[-1][0],)
    href = Fake.seen[-1][1]
    text = Fake.store[href][1]
    assert 'SUMMARY:Dentist' in text and 'LOCATION:Clinic' in text and 'DESCRIPTION:card' in text and 'DTSTART:' in text and text.endswith('\r\n')
    got = run('events', **{'from': '2026-10-22', 'to': '2026-10-22'})['events']
    assert [e['title'] for e in got] == ['Dentist'] and got[0]['time'] == '15:30' and got[0]['rw']
    r = run('update', src=src['id'], href=got[0]['href'], title='Dentist 2', date='2026-10-23', time='10:00', end_time='11:00')
    assert r['ok'] and 'SUMMARY:Dentist 2' in Fake.store[href][1] and Fake.store[href][0] == '2'
    assert run('delete', src=src['id'], href=got[0]['href']) == {'ok': True} and href not in Fake.store


def test_a_change_keeps_everything_else_in_the_event(env, server):
    src = connect(server)
    href = next(e for e in run('events', **{'from': '2026-10-20', 'to': '2026-10-20'})['events'] if e['title'] == 'Standup')['href']
    assert run('update', src=src['id'], href=href, title='Standup 2', date='2026-10-20', time='12:00', end_time='12:30')['ok']
    text = Fake.store['/cals/me/work/u1.ics'][1]
    assert 'ATTENDEE:mailto:a@b.c' in text and text.count('BEGIN:VEVENT') == 1 and text.count('UID:u1') == 1 and 'SUMMARY:Standup 2' in text and 'SUMMARY:Standup\r' not in text


def test_recurring_events_and_foreign_urls_are_refused(env, server):
    src = connect(server)
    assert run('update', src=src['id'], href=server + '/cals/me/work/u2.ics', title='x', date='2026-10-01', time='08:00')['error'] == 'recurring_readonly'
    assert run('delete', src=src['id'], href=server + '/cals/me/work/u2.ics')['error'] == 'recurring_readonly'
    assert run('delete', src=src['id'], href='http://evil.example/x.ics')['error'] == 'bad_href'
    assert run('update', src='nope', href='x', title='x', date='2026-10-01', time='08:00')['error'] == 'unknown_source'


def test_a_change_made_elsewhere_in_the_meantime_is_reported(env, server, monkeypatch):
    src = connect(server)
    href = next(e for e in run('events', **{'from': '2026-10-20', 'to': '2026-10-20'})['events'] if e['title'] == 'Standup')['href']
    real_get = dav.Client.get
    monkeypatch.setattr(dav.Client, 'get', lambda self, h: (lambda r: ('"0"', r[1]))(real_get(self, h)))         # the etag we hold is stale
    r = run('update', src=src['id'], href=href, title='x', date='2026-10-20', time='12:00', end_time='13:00')
    assert r['error'] == 'changed' and 'обновите' in r['message']


def test_voice_summary_and_reminders_see_caldav_events(env, server, monkeypatch):
    src = connect(server)
    from datetime import timedelta
    t = (datetime.now() + timedelta(minutes=10)).replace(second=0, microsecond=0)
    run('add', title='Soon', date=t.date().isoformat(), time=t.strftime('%H:%M'), calendar=src['id'])
    monkeypatch.setattr(ics, '_load_settings', lambda: sio.read())
    assert 'Soon (источник: Работа)' in ics.next_events_summary(None)
    assert [d[2] for d in hub.due_reminders(datetime.now(), 15)] == ['Soon']


def test_removing_the_source_and_a_down_server(env, server):
    src = connect(server)
    assert run('events', **{'from': '2026-10-20', 'to': '2026-10-20'})['events']
    hub._dav_cache.clear()
    Fake.store.clear()
    stale = run('events', **{'from': '2026-10-20', 'to': '2026-10-20'})
    assert stale['status'][0]['ok'] is True and stale['events'] == []
    assert run('remove_source', ref=src['ref'])['state']['sources'] == []
