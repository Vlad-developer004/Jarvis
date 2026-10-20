"""Task-manager part of the System screen: running processes with their load, ending / priority, and the startup entries (enable, disable).

The screen polls `list` every couple of seconds while its tab is open; nothing runs in the background. CPU and disk rates are deltas between two
`list` calls, so the first answer has zeros. Startup entries are read from the Run keys and the Startup folders; switching one off uses the same
StartupApproved flag Windows' own Task Manager writes, so nothing is deleted and the entry can be switched back on.
"""
from __future__ import annotations

import logging
import os
import struct
import subprocess
import threading
import time

_log = logging.getLogger(__name__)
_lock = threading.Lock()
_prev: dict = {}                    # pid -> (create_time, read+write bytes, monotonic time)
_last_t = 0.0
_NO_WINDOW = 0x08000000

# Ending any of these crashes or logs out Windows.
_CRITICAL = frozenset({'system', 'registry', 'smss.exe', 'csrss.exe', 'wininit.exe', 'winlogon.exe', 'services.exe', 'lsass.exe', 'memory compression',
                       'secure system', 'fontdrvhost.exe', 'dwm.exe', 'lsaiso.exe'})
_LEVELS = {'low': 'IDLE_PRIORITY_CLASS', 'below': 'BELOW_NORMAL_PRIORITY_CLASS', 'normal': 'NORMAL_PRIORITY_CLASS',
           'above': 'ABOVE_NORMAL_PRIORITY_CLASS', 'high': 'HIGH_PRIORITY_CLASS'}
_LEVEL_OF = {v: k for k, v in _LEVELS.items()}

_RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
_RUN32 = r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'
_APPROVED = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved'
_KEYS = {'user_run': ('HKCU', _RUN, 'Run'), 'machine_run': ('HKLM', _RUN, 'Run'), 'machine_run32': ('HKLM', _RUN32, 'Run32')}


def is_protected(pid: int, name: str) -> bool:
    return pid in (0, 4) or name.lower() in _CRITICAL


def _descendants(pid: int) -> list:
    import psutil
    try:
        return psutil.Process(pid).children(recursive=True)
    except psutil.Error:
        return []


def snapshot() -> dict:
    """Every process with load numbers. Rates are measured since the previous call."""
    import psutil
    global _last_t
    with _lock:
        now = time.monotonic()
        dt = max(0.3, now - _last_t) if _last_t else 0.0
        _last_t = now
        ncpu = psutil.cpu_count() or 1
        me = os.getpid()
        rows, seen = [], set()
        for p in psutil.process_iter():
            try:
                with p.oneshot():
                    pid = p.pid
                    name = p.name()
                    created = p.create_time()
                    try:
                        mem = p.memory_info().rss
                    except psutil.Error:
                        mem = 0
                    try:
                        io = p.io_counters()
                        total = io.read_bytes + io.write_bytes
                    except (psutil.Error, AttributeError):
                        total = None
                    try:
                        user = p.username().split('\\')[-1]
                    except psutil.Error:
                        user = ''
                    try:
                        exe = p.exe()
                    except psutil.Error:
                        exe = ''
                    try:
                        prio = _LEVEL_OF.get(next((n for n in _LEVELS.values() if getattr(psutil, n) == p.nice()), ''), '')  # unknown classes (realtime) show as empty
                    except psutil.Error:
                        prio = ''
                    cpu = p.cpu_percent(None) / ncpu if pid else 0.0
                    rows.append({'pid': pid, 'ppid': p.ppid(), 'name': name, 'exe': exe, 'user': user, 'mem': mem, 'cpu': round(cpu, 1), 'threads': p.num_threads(),
                                 'started': int(created), 'prio': prio, 'io': 0.0, 'protected': is_protected(pid, name), 'self': pid == me})
                    seen.add(pid)
                    if total is not None:
                        old = _prev.get(pid)
                        if old and old[0] == created and dt:
                            rows[-1]['io'] = max(0.0, (total - old[1]) / (now - old[2]))
                        _prev[pid] = (created, total, now)
            except psutil.Error:
                continue
        for pid in [k for k in _prev if k not in seen]:
            del _prev[pid]
    vm = psutil.virtual_memory()
    return {'ok': True, 'procs': rows, 'cores': ncpu, 'ram': {'total': vm.total, 'used': vm.total - vm.available}, 'ts': int(time.time() * 1000)}


def _find(pid, started):
    """The live process, only when it is still the one the screen showed (a pid can be reused after the process ends)."""
    import psutil
    try:
        p = psutil.Process(int(pid))
        if started is not None and int(p.create_time()) != int(started):
            return None
        return p
    except (psutil.Error, TypeError, ValueError):
        return None


def end(data: dict) -> dict:
    import psutil
    p = _find(data.get('pid'), data.get('started'))
    if p is None:
        return {'ok': False, 'error': 'gone'}
    try:
        name = p.name()
    except psutil.Error:
        return {'ok': False, 'error': 'gone'}
    if is_protected(p.pid, name):
        return {'ok': False, 'error': 'protected'}
    victims = (_descendants(p.pid) if data.get('tree') else []) + [p]
    me = os.getpid()
    if any(v.pid == me for v in victims):
        return {'ok': False, 'error': 'self'}
    victims = [v for v in victims if not _is_critical(v)]
    for v in victims:
        try:
            v.terminate()
        except psutil.AccessDenied:
            return {'ok': False, 'error': 'denied'}
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(victims, timeout=1.5)
    for v in alive:
        try:
            v.kill()
        except psutil.AccessDenied:
            return {'ok': False, 'error': 'denied'}
        except psutil.Error:
            pass
    _log.info('ended %s (%s), tree=%s', name, p.pid, bool(data.get('tree')))
    return {'ok': True}


def _is_critical(p) -> bool:
    import psutil
    try:
        return is_protected(p.pid, p.name())
    except psutil.Error:
        return False


def priority(data: dict) -> dict:
    import psutil
    level = _LEVELS.get(str(data.get('level', '')))
    p = _find(data.get('pid'), data.get('started'))
    if level is None:
        return {'ok': False, 'error': 'bad_level'}
    if p is None:
        return {'ok': False, 'error': 'gone'}
    try:
        p.nice(getattr(psutil, level))
    except psutil.AccessDenied:
        return {'ok': False, 'error': 'denied'}
    except psutil.Error:
        return {'ok': False, 'error': 'gone'}
    return {'ok': True}


def folder(data: dict) -> dict:
    """Show the program file in Explorer."""
    import psutil
    p = _find(data.get('pid'), data.get('started'))
    try:
        exe = p.exe() if p else ''
    except psutil.Error:
        exe = ''
    if not exe or not os.path.isfile(exe):
        return {'ok': False, 'error': 'no_path'}
    subprocess.Popen(['explorer', '/select,', os.path.normpath(exe)], creationflags=_NO_WINDOW)
    return {'ok': True}


# ---- startup entries ----

def _startup_dirs() -> dict:
    return {'user_folder': os.path.join(os.environ.get('APPDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup'),
            'machine_folder': os.path.join(os.environ.get('PROGRAMDATA', ''), r'Microsoft\Windows\Start Menu\Programs\Startup')}


def parse_approved(blob) -> bool:
    """StartupApproved value: even first byte (02, 06) = enabled, odd (03) = disabled; no value at all = enabled."""
    if not blob:
        return True
    return (blob[0] & 1) == 0


def _hive(name):
    import winreg
    return winreg.HKEY_CURRENT_USER if name == 'HKCU' else winreg.HKEY_LOCAL_MACHINE


def _approved(hive: str, sub: str, name: str) -> bool:
    import winreg
    try:
        with winreg.OpenKey(_hive(hive), _APPROVED + '\\' + sub, 0, winreg.KEY_READ) as k:
            return parse_approved(winreg.QueryValueEx(k, name)[0])
    except OSError:
        return True


def _short_cmd(cmd: str) -> str:
    cmd = os.path.expandvars(cmd.strip())
    return cmd[1:cmd.find('"', 1)] if cmd.startswith('"') and cmd.find('"', 1) > 0 else cmd.split(' -')[0].split(' /')[0]


def startup_list() -> list:
    import winreg
    out = []
    for src, (hive, sub, appr) in _KEYS.items():
        try:
            with winreg.OpenKey(_hive(hive), sub, 0, winreg.KEY_READ) as k:
                i = 0
                while True:
                    try:
                        name, val, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    i += 1
                    out.append({'id': f'{src}|{name}', 'name': name, 'cmd': str(val), 'path': _short_cmd(str(val)), 'scope': 'user' if hive == 'HKCU' else 'machine',
                                'enabled': _approved(hive, appr, name)})
        except OSError:
            continue
    for src, folder_path in _startup_dirs().items():
        if not os.path.isdir(folder_path):
            continue
        for f in sorted(os.listdir(folder_path)):
            if f.lower() == 'desktop.ini':
                continue
            hive = 'HKCU' if src == 'user_folder' else 'HKLM'
            out.append({'id': f'{src}|{f}', 'name': os.path.splitext(f)[0], 'cmd': os.path.join(folder_path, f), 'path': os.path.join(folder_path, f),
                        'scope': 'user' if hive == 'HKCU' else 'machine', 'enabled': _approved(hive, 'StartupFolder', f)})
    return out


def _approved_target(entry_id: str):
    src, _, name = entry_id.partition('|')
    if src in _KEYS:
        hive, _, appr = _KEYS[src]
        return hive, appr, name
    if src in ('user_folder', 'machine_folder'):
        return ('HKCU' if src == 'user_folder' else 'HKLM'), 'StartupFolder', name
    return None


def startup_set(data: dict) -> dict:
    import winreg
    entry_id = str(data.get('id', ''))
    if entry_id not in {e['id'] for e in startup_list()}:
        return {'ok': False, 'error': 'gone'}
    hive, sub, name = _approved_target(entry_id)
    flag = 2 if data.get('enabled') else 3
    ft = int((time.time() + 11644473600) * 10_000_000) if flag == 3 else 0
    blob = struct.pack('<IQ', flag, ft)
    try:
        with winreg.CreateKeyEx(_hive(hive), _APPROVED + '\\' + sub, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_BINARY, blob)
    except PermissionError:
        return {'ok': False, 'error': 'denied'}
    except OSError:
        _log.debug('startup flag write failed', exc_info=True)
        return {'ok': False, 'error': 'failed'}
    return {'ok': True}


def startup_folder(data: dict) -> dict:
    entry = next((e for e in startup_list() if e['id'] == str(data.get('id', ''))), None)
    if not entry or not entry['path'] or not os.path.exists(os.path.expandvars(entry['path'])):
        return {'ok': False, 'error': 'no_path'}
    subprocess.Popen(['explorer', '/select,', os.path.normpath(os.path.expandvars(entry['path']))], creationflags=_NO_WINDOW)
    return {'ok': True}


def run(data: dict) -> dict:
    op = str(data.get('op', ''))
    try:
        if op == 'list':
            return snapshot()
        if op == 'end':
            return end(data)
        if op == 'priority':
            return priority(data)
        if op == 'folder':
            return folder(data)
        if op == 'startup':
            return {'ok': True, 'items': startup_list()}
        if op == 'startup_set':
            return startup_set(data)
        if op == 'startup_folder':
            return startup_folder(data)
    except Exception:
        _log.warning('procs op %s failed', op, exc_info=True)
        return {'ok': False, 'error': 'failed'}
    return {'ok': False, 'error': 'bad_op'}
