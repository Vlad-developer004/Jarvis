"""actions/now_playing.py: session picking, labels, time formatting and the position that moves on while playing (the Windows API itself is faked)."""
import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from actions import now_playing as np


def sess(i, status='paused', current=False, seek=True):
    return {'id': i, 'status': status, 'current': current, 'can': {'seek': seek}}


def test_pick_prefers_the_session_that_is_playing():
    a, b, c = sess('a', 'paused', True), sess('b', 'playing'), sess('c', 'paused')
    assert np.pick([a, b, c])['id'] == 'b'
    assert np.pick([a, c])['id'] == 'a'                        # nothing playing: the one Windows calls current
    assert np.pick([sess('x'), sess('y')])['id'] == 'x'        # else the first
    assert np.pick([a, b], 'c') is None and np.pick([a, b], 'a')['id'] == 'a'
    assert np.pick([]) is None


@pytest.mark.parametrize('app,name', [('Brave._crx_agimnkij', 'Brave'), ('chrome.exe', 'Chrome'), ('VLC.exe', 'VLC'), ('Spotify.exe', 'Spotify'),
                                       ('Microsoft.ZuneMusic_8wekyb3d8bbwe!Microsoft.ZuneMusic', 'Медиаплеер'), ('Some.Player_1!App', 'Some'), ('', 'Приложение')])
def test_app_label(app, name):
    assert np.app_label(app) == name


@pytest.mark.parametrize('sec,text', [(0, '0:00'), (59.9, '0:59'), (75, '1:15'), (3600, '1:00:00'), (4570, '1:16:10'), (-5, '0:00')])
def test_fmt_time(sec, text):
    assert np.fmt_time(sec) == text


def td(s):
    return timedelta(seconds=s)


def test_position_moves_on_only_while_playing():
    upd = datetime.now(timezone.utc) - timedelta(seconds=10)
    tl = NS(position=td(100), start_time=td(0), last_updated_time=upd)
    assert 109 <= np._position(tl, 'playing', 1.0) <= 112
    assert np._position(tl, 'paused', 1.0) == 100
    assert 119 <= np._position(tl, 'playing', 2.0) <= 124       # a faster rate moves it faster


class FakeSession:
    def __init__(self, app, title, status=4, pos=30, end=120, seek=True):
        self.source_app_user_model_id = app
        c = NS(is_play_enabled=status != 4, is_pause_enabled=status == 4, is_next_enabled=False, is_previous_enabled=False, is_playback_position_enabled=seek)
        self._pb = NS(playback_status=status, playback_rate=None, controls=c)
        self._tl = NS(position=td(pos), start_time=td(0), end_time=td(end), last_updated_time=datetime(1601, 1, 1, tzinfo=timezone.utc))
        self._title = title

    def get_playback_info(self): return self._pb
    def get_timeline_properties(self): return self._tl

    async def try_get_media_properties_async(self):
        return NS(title=self._title, artist='A', album_title='')


def test_describe_builds_the_row_and_numbers_duplicates():
    async def go():
        idx = {}
        a = await np._describe(FakeSession('VLC.exe', 'Film'), idx, 'VLC.exe')
        b = await np._describe(FakeSession('VLC.exe', 'Film 2', status=5), idx, 'VLC.exe')
        return a, b
    a, b = asyncio.run(go())
    assert a['id'] == 'VLC.exe#0' and b['id'] == 'VLC.exe#1' and a['current'] is True and b['current'] is False
    assert (a['app_name'], a['title'], a['status'], a['pos'], a['dur']) == ('VLC', 'Film', 'playing', 30.0, 120.0)
    assert a['can'] == {'play': False, 'pause': True, 'next': False, 'prev': False, 'seek': True} and b['status'] == 'paused'


def test_control_rejects_unknown_actions_without_touching_windows():
    assert np.control('explode')['error'] == 'bad_action'
