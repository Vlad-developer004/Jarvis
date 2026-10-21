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


def test_parse_sign_reads_status_and_publisher():
    ok = procs.parse_sign('{"st":"Valid","sub":"CN=Microsoft Windows, O=Microsoft Corporation"}')
    assert ok == {'status': 'valid', 'signer': 'Microsoft Windows'}
    assert procs.parse_sign('{"st":"Valid","sub":"CN=\\"Acme, Inc.\\", O=Acme"}')['signer'] == 'Acme, Inc.'
    assert procs.parse_sign('{"st":"NotSigned","sub":""}')['status'] == 'unsigned'
    assert procs.parse_sign('{"st":"HashMismatch","sub":"CN=X"}')['status'] == 'invalid'
    assert procs.parse_sign('not json')['status'] == 'unknown'


@pytest.mark.parametrize('name,exe,expected', [('eurotrucks2.exe', '', True), ('x.exe', r'D:\SteamLibrary\steamapps\common\G\g.exe', True), ('chrome.exe', r'C:\Program Files\Google\chrome.exe', False)])
def test_is_game(name, exe, expected):
    assert procs.is_game(name, exe, frozenset({'eurotrucks2.exe'})) is expected


def test_affinity_reads_own_cores_and_rejects_bad_sets():
    r = run(op='affinity', pid=os.getpid())
    assert r['ok'] and r['cores'] and r['total'] >= len(r['cores'])
    for bad in ([], [-1], [10 ** 6], ['0'], [True], 'all'):
        assert run(op='affinity', pid=os.getpid(), cores=bad)['error'] == 'bad_cores'
    assert run(op='affinity', pid=2 ** 22 + 7)['error'] == 'gone'


def test_snapshot_rows_carry_game_flag_and_current_user():
    r = run(op='list')
    assert r['me'] and all(isinstance(p['game'], bool) for p in r['procs'])


def test_search_opens_browser_for_a_live_process(monkeypatch):
    seen = []
    monkeypatch.setattr(procs.webbrowser, 'open', seen.append)
    assert run(op='search', pid=os.getpid())['ok'] and seen and seen[0].startswith('https://www.google.com/search?q=')
    assert run(op='search', pid=2 ** 22 + 7)['error'] == 'gone'


def test_png_encoder_makes_a_decodable_image():
    import io
    from PIL import Image
    px = bytes([255, 0, 0, 255]) * 4 + bytes([0, 0, 255, 128]) * 4
    im = Image.open(io.BytesIO(procs._png(4, 2, px))).convert('RGBA')
    assert im.size == (4, 2) and im.getpixel((0, 0)) == (255, 0, 0, 255) and im.getpixel((0, 1)) == (0, 0, 255, 128)


@pytest.mark.skipif(sys.platform != 'win32', reason='icons come from Win32')
def test_icons_for_a_live_program_and_for_nothing():
    import base64
    me = next(p for p in run(op='list')['procs'] if p['pid'] == os.getpid())
    r = run(op='icons', items=[{'pid': os.getpid(), 'started': me['started']}, {'pid': 2 ** 22 + 7, 'started': 1}, 'junk'])
    assert r['ok']
    own = r['icons'][f"{os.getpid()}:{me['started']}"]
    assert base64.b64decode(own)[:8] == b'\x89PNG\r\n\x1a\n'
    assert r['icons'][f'{2 ** 22 + 7}:1'] == ''


def test_icons_batch_is_capped():
    items = [{'pid': 2 ** 22 + i, 'started': 1} for i in range(40)]
    assert len(run(op='icons', items=items)['icons']) == 24


def test_exe_of_path_takes_the_program_from_a_command_line():
    assert procs._exe_of_path(f'"{sys.executable}" -k netsvcs -p') == sys.executable
    assert procs._exe_of_path(__file__) == '' and procs._exe_of_path('') == '' and procs._exe_of_path(None) == ''
    assert procs._exe_of_path('Z:/no/such/program.exe /x') == ''


@pytest.mark.skipif(sys.platform != 'win32', reason='icons come from Win32')
def test_icons_by_path_read_only_an_existing_exe():
    import base64
    r = run(op='icons', items=[{'path': sys.executable}, {'path': 'Z:/no/such/program.exe'}, {'path': __file__}])
    assert base64.b64decode(r['icons'][f'p:{sys.executable}'])[:4] == b'\x89PNG'
    assert r['icons']['p:Z:/no/such/program.exe'] == '' and r['icons'][f'p:{__file__}'] == ''


@pytest.mark.skipif(sys.platform != 'win32', reason='version resources are a Windows thing')
def test_icons_carry_a_description_from_the_exe_version_info():
    from ui_next.bridge import proc_desc
    assert proc_desc.description(sys.executable) == 'Python'
    assert proc_desc.description('Z:/no/such/program.exe') == '' and proc_desc.description(__file__) == ''
    r = run(op='icons', items=[{'path': sys.executable}, {'path': 'Z:/no/such/program.exe'}])
    assert r['desc'][f'p:{sys.executable}'] == 'Python' and r['desc']['p:Z:/no/such/program.exe'] == ''
