"""actions/volume.py works only through the native audio service: ducking, master volume, mute and per-app volume (service mocked)."""
import inspect

import pytest

from actions import volume
from core import native_audio


class _Svc:
    """A stand-in for the sidecar service with one master volume and a few sessions."""

    def __init__(self):
        self.level, self.muted, self.calls = 0.5, False, []
        self.sessions = [
            {'pid': 10, 'id': 'a', 'name': 'spotify.exe', 'volume': 0.6, 'muted': False, 'system': False},
            {'pid': 11, 'id': 'b', 'name': 'brave.exe', 'volume': 1.0, 'muted': False, 'system': False},
            {'pid': 0, 'id': 'c', 'name': '', 'volume': 1.0, 'muted': False, 'system': True},
        ]

    def request(self, **req):
        self.calls.append(req)
        op = req['op']
        if op == 'sessions':
            return {'ok': True, 'sessions': self.sessions}
        if op == 'set_session':
            row = next(s for s in self.sessions if s['id'] == req['session'])
            row['volume'] = req['level']
            return {'ok': True, 'volume': row['volume']}
        if op == 'master_set':
            self.level = req.get('level', self.level)
            self.muted = req.get('muted', self.muted)
        return {'ok': True, 'level': self.level, 'muted': self.muted}


class _Dead:
    def request(self, **req):
        return None


@pytest.fixture
def svc(monkeypatch):
    s = _Svc()
    monkeypatch.setattr(native_audio, '_service', s)
    monkeypatch.setattr(volume, 'send_hardware_key', lambda vk: s.calls.append({'key': vk}))
    monkeypatch.setattr(volume.time, 'sleep', lambda t: None)
    return s


@pytest.fixture
def dead(monkeypatch):
    monkeypatch.setattr(native_audio, '_service', _Dead())
    monkeypatch.setattr(volume, 'send_hardware_key', lambda vk: pytest.fail('key pressed without a service'))


def test_duck_and_unduck_go_to_the_service(monkeypatch):
    seen = []
    monkeypatch.setattr(native_audio, 'duck', lambda enable: seen.append(('duck', enable)) or True)
    s = _Svc()
    monkeypatch.setattr(native_audio, '_service', s)
    volume.duck_volume(True)
    volume.duck_volume(False)
    volume.force_unduck()
    assert seen == [('duck', True), ('duck', False)] and s.calls == [{'op': 'unduck'}]


def test_ducking_never_raises_even_when_the_service_is_gone(dead):
    volume.duck_volume(True)
    volume.duck_volume(False)
    volume.force_unduck()


@pytest.mark.parametrize('direction,amount,expected', [('up', 20, 80), ('down', 20, 40), ('set', 30, 30), ('up', 90, 100), ('down', 90, 0)])
def test_app_volume_arithmetic_and_label(svc, direction, amount, expected):
    ok, msg = volume.set_app_volume('spotify', direction, amount)
    assert ok and msg == f'Громкость spotify: {expected} процентов'


def test_app_volume_picks_the_right_session_and_reports_a_missing_app(svc):
    volume.set_app_volume('brave', 'down', 50)
    assert [s['volume'] for s in svc.sessions if s['name'] == 'brave.exe'] == [0.5]
    assert svc.sessions[0]['volume'] == 0.6   # spotify untouched
    ok, msg = volume.set_app_volume('zzzzqqq', 'up', 10)
    assert not ok and 'не найдено' in msg


def test_cyrillic_app_names_still_match(svc):
    ok, msg = volume.set_app_volume('спотифай', 'set', 10)
    assert ok and 'spotify' in msg


def test_set_volume_level_unmutes_sets_pokes_the_osd_and_sets_again(svc):
    svc.muted = True
    ok, msg = volume.set_volume_level(0.3)
    assert ok and msg == 'Громкость 30%'
    seq = [(c.get('op'), c.get('level'), c.get('muted'), c.get('key')) for c in svc.calls]
    assert seq == [('master_set', 0.3, False, None), (None, None, None, 174), (None, None, None, 175), ('master_set', 0.3, None, None)]
    assert svc.muted is False and svc.level == 0.3


def test_set_volume_level_clamps(svc):
    assert volume.set_volume_level(1.7)[1] == 'Громкость 170%'   # the label keeps the spoken value, as before
    assert svc.level == 1.0


@pytest.mark.parametrize('start,mute,presses', [(False, True, 1), (True, True, 0), (True, False, 1), (False, False, 0)])
def test_mute_presses_the_key_only_when_the_state_differs(svc, start, mute, presses):
    svc.muted = start
    ok, msg = volume.mute_volume(mute)
    assert ok and msg == ('Звук выключен' if mute else 'Звук включён')
    assert sum(1 for c in svc.calls if c.get('key') == 173) == presses


def test_without_the_service_everything_reports_it_and_touches_nothing(dead):
    assert volume.set_app_volume('spotify', 'up', 10) == (False, volume._UNAVAILABLE)
    assert volume.mute_volume(True) == (False, volume._UNAVAILABLE)
    assert volume.set_volume_level(0.4) == (False, volume._UNAVAILABLE)


def test_the_volume_module_has_no_com_path_left():
    code = [ln for ln in inspect.getsource(volume).splitlines() if not ln.lstrip().startswith('#')]
    text = '\n'.join(code)
    assert 'pycaw' not in text and 'pythoncom' not in text
