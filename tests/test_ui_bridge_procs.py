"""ui_next/bridge/procs.py: the process list, ending a process safely and the startup entries of the System screen."""
import os
import subprocess
import sys
import time

import pytest

from ui_next import bridge
from ui_next.bridge import procs


def run(**kw):
    return bridge.run_command('procs', kw)


def test_list_has_this_process_marked_as_self():
    r = run(op='list')
    assert r['ok'] and r['cores'] >= 1
    me = next(p for p in r['procs'] if p['pid'] == os.getpid())
    assert me['self'] is True and me['mem'] > 0 and me['started'] > 0


def test_second_list_measures_rates_without_error():
    run(op='list')
    r = run(op='list')
    assert all(p['cpu'] >= 0 and p['io'] >= 0 for p in r['procs'])


@pytest.mark.parametrize('pid,name,expected', [(4, 'System', True), (0, 'System Idle Process', True), (500, 'CSRSS.exe', True), (900, 'chrome.exe', False)])
def test_protected_processes(pid, name, expected):
    assert procs.is_protected(pid, name) is expected


def test_end_refuses_itself_and_unknown_pid():
    assert run(op='end', pid=os.getpid())['error'] == 'self'
    assert run(op='end', pid=2 ** 22 + 7)['error'] == 'gone'


def test_end_refuses_when_start_time_differs():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        assert run(op='end', pid=child.pid, started=1)['error'] == 'gone'
        assert child.poll() is None
    finally:
        child.kill()


def test_end_stops_a_child_process():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    import psutil
    started = int(psutil.Process(child.pid).create_time())
    assert run(op='end', pid=child.pid, started=started) == {'ok': True}
    deadline = time.time() + 3
    while child.poll() is None and time.time() < deadline:
        time.sleep(0.05)
    assert child.poll() is not None


def test_priority_rejects_unknown_level():
    assert run(op='priority', pid=os.getpid(), level='realtime')['error'] == 'bad_level'


def test_priority_changes_a_child():
    import psutil
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        started = int(psutil.Process(child.pid).create_time())
        assert run(op='priority', pid=child.pid, started=started, level='below')['ok']
        assert psutil.Process(child.pid).nice() == psutil.BELOW_NORMAL_PRIORITY_CLASS
    finally:
        child.kill()


@pytest.mark.parametrize('blob,enabled', [(None, True), (b'', True), (b'\x02\x00\x00\x00', True), (b'\x06\x00\x00\x00', True), (b'\x03\x00\x00\x00', False)])
def test_parse_approved(blob, enabled):
    assert procs.parse_approved(blob) is enabled


def test_startup_list_shape():
    r = run(op='startup')
    assert r['ok']
    for e in r['items']:
        assert {'id', 'name', 'path', 'scope', 'enabled'} <= set(e) and '|' in e['id']


def test_startup_set_unknown_entry_is_gone():
    assert run(op='startup_set', id='user_run|__no_such_entry__', enabled=False)['error'] == 'gone'


def test_startup_toggle_roundtrip_on_a_test_value(monkeypatch):
    import winreg
    name = 'JarvisTestEntry'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, procs._RUN) as k:
        winreg.SetValueEx(k, name, 0, winreg.REG_SZ, r'"C:\Windows\notepad.exe"')
    try:
        eid = f'user_run|{name}'
        find = lambda: next(e for e in run(op='startup')['items'] if e['id'] == eid)   # noqa: E731
        assert find()['enabled'] is True and find()['path'] == r'C:\Windows\notepad.exe'
        assert run(op='startup_set', id=eid, enabled=False)['ok'] and find()['enabled'] is False
        assert run(op='startup_set', id=eid, enabled=True)['ok'] and find()['enabled'] is True
    finally:
        for sub in (procs._RUN, procs._APPROVED + r'\Run'):
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_SET_VALUE) as k:
                    winreg.DeleteValue(k, name)
            except OSError:
                pass


def test_bad_op():
    assert run(op='nope')['error'] == 'bad_op'


def test_list_reports_the_ram_the_header_percentage_needs():
    r = run(op='list')
    assert r['ram']['total'] > 0 and 0 < r['ram']['used'] <= r['ram']['total']
