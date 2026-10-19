"""A small CalDAV client (RFC 4791) so calendars that allow it can be changed from Jarvis, not only read: find the user's calendars, read the events of
a time range, create, change and delete them. Works with servers that accept a login and an app password (Yandex, iCloud, Nextcloud, Fastmail and
most self-hosted ones). Google and Outlook need an OAuth application for CalDAV, so they stay read-only through their secret .ics link.

Nothing here knows about the screen: actions/calendar_hub.py builds the events and the UI on top of it.
"""
from __future__ import annotations

import uuid
from defusedxml import ElementTree as ET     # the server is not trusted: no entity-expansion tricks
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import requests
from core.safe import swallow as _swallow

TIMEOUT = 15
MAX_BODY = 8 * 1024 * 1024
PRESETS = {'yandex': 'https://caldav.yandex.ru', 'icloud': 'https://caldav.icloud.com', 'fastmail': 'https://caldav.fastmail.com'}
_NS = {'d': 'DAV:', 'c': 'urn:ietf:params:xml:ns:caldav', 'ic': 'http://apple.com/ns/ical/'}
_PROPFIND_PRINCIPAL = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
_PROPFIND_HOME = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><c:calendar-home-set/></d:prop></d:propfind>'
_PROPFIND_CALS = ('<?xml version="1.0"?><d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav" xmlns:ic="http://apple.com/ns/ical/"><d:prop><d:displayname/><d:resourcetype/>'
                  '<c:supported-calendar-component-set/><ic:calendar-color/></d:prop></d:propfind>')


class CalDavError(Exception):
    def __init__(self, code: str, message: str = ''):
        super().__init__(message or code)
        self.code, self.message = code, message or code


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ') if dt.tzinfo else dt.astimezone().astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def _xml(text: str):
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        raise CalDavError('bad_response', 'Сервер ответил не так, как ожидалось')


class Client:
    def __init__(self, base_url: str, user: str, password: str):
        u = urlsplit(base_url if '://' in base_url else f'https://{base_url}')
        if u.scheme not in ('https', 'http') or not u.hostname:
            raise CalDavError('bad_url', 'Неверный адрес сервера')
        if u.scheme == 'http' and u.hostname not in ('localhost', '127.0.0.1'):
            raise CalDavError('bad_url', 'Для подключения нужен адрес https')
        self.base = f'{u.scheme}://{u.netloc}{u.path or "/"}'
        self.s = requests.Session()
        self.s.auth = (user, password)
        self.s.headers['User-Agent'] = 'JARVIS-Calendar/1.0'

    def _req(self, method: str, url: str, body: str | bytes | None = None, headers: dict | None = None, depth: str | None = None):
        h = {'Content-Type': 'application/xml; charset=utf-8', **(headers or {})}
        if depth is not None:
            h['Depth'] = depth
        data = body.encode('utf-8') if isinstance(body, str) else body
        try:
            for _ in range(4):                                                       # redirects keep the method and the body (requests would turn them into GET)
                r = self.s.request(method, url, data=data, headers=h, timeout=TIMEOUT, allow_redirects=False, stream=True)
                if r.status_code in (301, 302, 307, 308) and r.headers.get('Location'):
                    url = urljoin(url, r.headers['Location'])
                    r.close()
                    continue
                break
            content = r.raw.read(MAX_BODY + 1, decode_content=True)
        except requests.RequestException as ex:
            raise CalDavError('network', f'Не удалось подключиться к серверу: {ex.__class__.__name__}')
        finally:
            try:
                r.close()
            except Exception:
                _swallow()
        if r.status_code == 401:
            raise CalDavError('auth', 'Сервер не принял логин или пароль приложения')
        if len(content) > MAX_BODY:
            raise CalDavError('too_big', 'Ответ сервера слишком большой')
        r.text_ = content.decode('utf-8', errors='replace')
        return r

    def _multi(self, method: str, url: str, body: str, depth: str = '0', headers: dict | None = None):
        r = self._req(method, url, body, headers, depth)
        if r.status_code not in (200, 207):
            raise CalDavError('failed', f'Сервер ответил кодом {r.status_code}')
        return _xml(r.text_), r.url

    # ---- discovery ----
    def home(self) -> str:
        """URL of the folder that holds the user's calendars."""
        for start in (self.base, urljoin(self.base, '/.well-known/caldav')):
            try:
                root, url = self._multi('PROPFIND', start, _PROPFIND_PRINCIPAL)
            except CalDavError as ex:
                if ex.code in ('auth', 'network'):
                    raise
                continue
            el = root.find('.//d:current-user-principal/d:href', _NS)
            principal = urljoin(url, el.text.strip()) if el is not None and el.text else url
            try:
                r2, u2 = self._multi('PROPFIND', principal, _PROPFIND_HOME)
            except CalDavError:
                continue
            h = r2.find('.//c:calendar-home-set/d:href', _NS)
            if h is not None and h.text:
                return urljoin(u2, h.text.strip())
        raise CalDavError('no_home', 'Не удалось найти календари на сервере')

    def calendars(self) -> list[dict]:
        root, url = self._multi('PROPFIND', self.home(), _PROPFIND_CALS, depth='1')
        out = []
        for resp in root.findall('d:response', _NS):
            if resp.find('.//d:resourcetype/c:calendar', _NS) is None:
                continue
            comps = [c.get('name', '').upper() for c in resp.findall('.//c:supported-calendar-component-set/c:comp', _NS)]
            if comps and 'VEVENT' not in comps:
                continue
            href = resp.find('d:href', _NS)
            name = resp.find('.//d:displayname', _NS)
            color = resp.find('.//ic:calendar-color', _NS)
            out.append({'href': urljoin(url, href.text.strip()), 'name': (name.text or '').strip() if name is not None and name.text else 'Календарь',
                        'color': (color.text or '').strip()[:7] if color is not None and color.text else ''})
        if not out:
            raise CalDavError('no_calendars', 'На сервере нет календарей с событиями')
        return out

    # ---- events ----
    def objects(self, cal_url: str, start: datetime, end: datetime) -> list[dict]:
        """Calendar objects (an event with its changed occurrences) that touch [start, end]: [{href, etag, ics}]."""
        body = ('<?xml version="1.0"?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><d:getetag/><c:calendar-data/></d:prop>'
                f'<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="{_utc(start)}" end="{_utc(end)}"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>')
        root, url = self._multi('REPORT', cal_url, body, depth='1')
        out = []
        for resp in root.findall('d:response', _NS):
            data = resp.find('.//c:calendar-data', _NS)
            href = resp.find('d:href', _NS)
            if data is None or not data.text or href is None:
                continue
            etag = resp.find('.//d:getetag', _NS)
            out.append({'href': urljoin(url, href.text.strip()), 'etag': (etag.text or '').strip() if etag is not None and etag.text else '', 'ics': data.text})
        return out

    def get(self, href: str) -> tuple[str, str]:
        r = self._req('GET', href, headers={'Accept': 'text/calendar'})
        if r.status_code != 200:
            raise CalDavError('failed', f'Сервер ответил кодом {r.status_code}')
        return r.headers.get('ETag', '').strip(), r.text_

    def put(self, href: str, ics: str, etag: str = '', create: bool = False) -> str:
        headers = {'Content-Type': 'text/calendar; charset=utf-8'}
        if create:
            headers['If-None-Match'] = '*'
        elif etag:
            headers['If-Match'] = etag
        r = self._req('PUT', href, ics, headers)
        if r.status_code == 412:
            raise CalDavError('changed', 'Событие изменилось на сервере, обновите календарь')
        if r.status_code not in (200, 201, 204):
            raise CalDavError('failed', f'Сервер не принял событие (код {r.status_code})')
        return r.headers.get('ETag', '').strip()

    def delete(self, href: str, etag: str = '') -> None:
        r = self._req('DELETE', href, headers={'If-Match': etag} if etag else None)
        if r.status_code == 412:
            raise CalDavError('changed', 'Событие изменилось на сервере, обновите календарь')
        if r.status_code not in (200, 204, 404):
            raise CalDavError('failed', f'Сервер не удалил событие (код {r.status_code})')

    @staticmethod
    def new_href(cal_url: str) -> tuple[str, str]:
        uid = uuid.uuid4().hex
        return urljoin(cal_url if cal_url.endswith('/') else cal_url + '/', f'{uid}.ics'), uid
