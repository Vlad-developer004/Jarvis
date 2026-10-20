"""ui_next/bridge/services.py: Windows services and scheduled logon tasks of the System screen (nothing here changes a real service)."""
import json

import pytest

from ui_next import bridge
from ui_next.bridge import services as sv


def run(**kw):
    return bridge.run_command('services', kw)


def test_list_has_services_with_expected_fields():
    r = run(op='list')
    assert r['ok'] and r['items']
    s = r['items'][0]
    assert {'name', 'display', 'status', 'start', 'pid', 'path', 'critical'} <= set(s)
    assert any(x['status'] == 'running' for x in r['items'])


def test_critical_services_are_flagged():
    items = {x['name'].lower(): x for x in run(op='list')['items']}
    if 'rpcss' in items:
        assert items['rpcss']['critical'] is True


@pytest.mark.parametrize('act', ['stop', 'restart', 'disabled'])
def test_critical_service_cannot_be_stopped_or_disabled(act):
    name = next((x['name'] for x in run(op='list')['items'] if x['critical']), None)
    if name is None:
        pytest.skip('no critical service on this machine')
    assert run(op='action', name=name, act=act)['error'] == 'protected'


def test_action_rejects_unknown_act_and_unknown_service():
    assert run(op='action', name='x', act='explode')['error'] == 'bad_act'
    assert run(op='action', name='__no_such_service__', act='start')['error'] == 'gone'


def test_task_list_parses_single_and_many(monkeypatch):
    one = {'name': 'Up', 'path': '\\', 'enabled': True, 'run': 'a.exe -x', 'user': 'me'}
    monkeypatch.setattr(sv, '_ps', lambda *a, **k: json.dumps(one))
    assert sv.task_list() == [{'id': '\\Up', 'name': 'Up', 'path': 'a.exe -x', 'enabled': True, 'user': 'me'}]
    monkeypatch.setattr(sv, '_ps', lambda *a, **k: json.dumps([one, {**one, 'name': 'B', 'enabled': False}]))
    assert [t['enabled'] for t in sv.task_list()] == [True, False]
    monkeypatch.setattr(sv, '_ps', lambda *a, **k: '')
    assert sv.task_list() == []
    monkeypatch.setattr(sv, '_ps', lambda *a, **k: None)
    assert sv.task_list() is None


def test_task_set_passes_name_through_environment_not_script(monkeypatch):
    seen = {}
    odd = "\\Odd'; calc; '"
    monkeypatch.setattr(sv, 'task_list', lambda: [{'id': odd, 'name': '', 'path': '', 'enabled': True, 'user': ''}])

    def fake(script, timeout=25, env=None):
        seen.update(script=script, env=env)
        return 'ok'
    monkeypatch.setattr(sv, '_ps', fake)
    assert run(op='task_set', id=odd, enabled=False) == {'ok': True}
    assert 'calc' not in seen['script'] and 'Disable-ScheduledTask' in seen['script']
    assert seen['env'] == {'JV_PATH': '\\', 'JV_NAME': "Odd'; calc; '"}


def test_task_set_unknown_task_is_gone(monkeypatch):
    monkeypatch.setattr(sv, 'task_list', lambda: [])
    assert run(op='task_set', id='\\Nope', enabled=True)['error'] == 'gone'
