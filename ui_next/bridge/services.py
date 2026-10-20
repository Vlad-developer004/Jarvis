"""Windows services and scheduled logon tasks for the System screen (tabs "Службы" and "Автозапуск").

Services are listed on demand (the screen has a refresh button and reloads after every action); start, stop, restart and the start type go through
the Service Control Manager and need administrator rights for most services, which comes back as `denied`. A few services the system cannot run
without are never touched. Tasks are read and switched with the ScheduledTasks PowerShell module; the task is always looked up in the fresh list
first, so the name from the window is never pasted into a script.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import time

_log = logging.getLogger(__name__)
_NO_WINDOW = 0x08000000
_START_TYPES = {'auto': 2, 'manual': 3, 'disabled': 4}

# Stopping or disabling these takes Windows down or logs the user out.
_CRITICAL = frozenset({'rpcss', 'rpceptmapper', 'dcomlaunch', 'lsm', 'samss', 'eventlog', 'plugplay', 'power', 'brokerinfrastructure', 'coremessagingregistrar',
                       'gpsvc', 'profsvc', 'usermanager', 'systemeventsbroker', 'cryptsvc', 'bfe', 'mpssvc', 'nsi'})

_TASKS_PS = r"""
$ErrorActionPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8
$all = Get-ScheduledTask | Where-Object { $_.TaskPath -notlike '\Microsoft\*' -and ($_.Triggers | Where-Object { $_.CimClass.CimClassName -in 'MSFT_TaskLogonTrigger','MSFT_TaskBootTrigger' }) }
@($all | ForEach-Object { [pscustomobject]@{name=$_.TaskName; path=$_.TaskPath; enabled=($_.State -ne 'Disabled'); run=(($_.Actions | Select-Object -First 1 | ForEach-Object { ($_.Execute + ' ' + $_.Arguments).Trim() })); user=$_.Principal.UserId} }) | ConvertTo-Json -Compress
"""


def is_critical(name: str) -> bool:
    return name.lower() in _CRITICAL


def _item(s) -> dict:
    d = s.as_dict()
    name = d.get('name', '')
    return {'name': name, 'display': d.get('display_name') or name, 'status': d.get('status', ''), 'start': d.get('start_type', ''), 'pid': int(d.get('pid') or 0),
            'path': d.get('binpath') or '', 'desc': (d.get('description') or '')[:300], 'user': d.get('username') or '', 'critical': is_critical(name)}


def service_list() -> list:
    import psutil
    out = []
    for s in psutil.win_service_iter():
        try:
            out.append(_item(s))
        except Exception:
            _log.debug('service skipped', exc_info=True)
    return out


def _status(scm_service) -> int:
    import win32service
    return win32service.QueryServiceStatus(scm_service)[1]


def _wait(svc, want: int, seconds: float = 8.0) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if _status(svc) == want:
            return True
        time.sleep(0.25)
    return _status(svc) == want


def service_action(data: dict) -> dict:
    import pywintypes
    import win32service as w
    name, act = str(data.get('name', '')), str(data.get('act', ''))
    if act not in ('start', 'stop', 'restart', 'auto', 'manual', 'disabled'):
        return {'ok': False, 'error': 'bad_act'}
    if name not in {s['name'] for s in service_list()}:
        return {'ok': False, 'error': 'gone'}
    if is_critical(name) and act in ('stop', 'restart', 'disabled'):
        return {'ok': False, 'error': 'protected'}
    scm = svc = None
    try:
        scm = w.OpenSCManager(None, None, w.SC_MANAGER_CONNECT)
        svc = w.OpenService(scm, name, w.SERVICE_START | w.SERVICE_STOP | w.SERVICE_QUERY_STATUS | w.SERVICE_CHANGE_CONFIG)
        if act in _START_TYPES:
            w.ChangeServiceConfig(svc, w.SERVICE_NO_CHANGE, _START_TYPES[act], w.SERVICE_NO_CHANGE, None, None, 0, None, None, None, None)
            return {'ok': True}
        if act in ('stop', 'restart') and _status(svc) != w.SERVICE_STOPPED:
            w.ControlService(svc, w.SERVICE_CONTROL_STOP)
            if not _wait(svc, w.SERVICE_STOPPED):
                return {'ok': False, 'error': 'timeout'}
        if act in ('start', 'restart') and _status(svc) != w.SERVICE_RUNNING:
            w.StartService(svc, None)
            if not _wait(svc, w.SERVICE_RUNNING):
                return {'ok': False, 'error': 'timeout'}
        return {'ok': True}
    except pywintypes.error as e:
        _log.info('service %s %s: %s', name, act, e)
        return {'ok': False, 'error': 'denied' if e.winerror == 5 else 'disabled' if e.winerror == 1058 else 'failed'}
    finally:
        for h in (svc, scm):
            if h is not None:
                w.CloseServiceHandle(h)


def _ps(script: str, timeout: float = 25, env: dict | None = None):
    try:
        raw = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, timeout=timeout, creationflags=_NO_WINDOW,
                             env={**os.environ, **(env or {})}).stdout
        return raw.decode('utf-8', errors='ignore').strip()
    except Exception:
        _log.debug('powershell failed', exc_info=True)
        return None


def task_list() -> list | None:
    """Scheduled tasks that start at logon or boot, apart from Windows' own; None when PowerShell did not answer."""
    text = _ps(_TASKS_PS)
    if text is None:
        return None
    if not text:
        return []
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return [{'id': t['path'] + t['name'], 'name': t['name'], 'path': t['run'] or '', 'enabled': bool(t['enabled']), 'user': t.get('user') or ''}
            for t in (data if isinstance(data, list) else [data])]


def task_set(data: dict) -> dict:
    tid = str(data.get('id', ''))
    task = next((t for t in task_list() or [] if t['id'] == tid), None)
    if task is None:
        return {'ok': False, 'error': 'gone'}
    cmd = 'Enable' if data.get('enabled') else 'Disable'
    split = tid.rfind('\\') + 1
    out = _ps(f"$ErrorActionPreference='Stop'; try {{ {cmd}-ScheduledTask -TaskPath $env:JV_PATH -TaskName $env:JV_NAME | Out-Null; 'ok' }} catch {{ $_.Exception.GetType().Name }}",
              env={'JV_PATH': tid[:split], 'JV_NAME': tid[split:]})
    if out == 'ok':
        return {'ok': True}
    return {'ok': False, 'error': 'denied' if out and 'Unauthorized' in out else 'failed'}


def run(data: dict) -> dict:
    op = str(data.get('op', ''))
    try:
        if op == 'list':
            return {'ok': True, 'items': service_list()}
        if op == 'action':
            return service_action(data)
        if op == 'tasks':
            items = task_list()
            return {'ok': items is not None, 'items': items or []}
        if op == 'task_set':
            return task_set(data)
    except Exception:
        _log.warning('services op %s failed', op, exc_info=True)
        return {'ok': False, 'error': 'failed'}
    return {'ok': False, 'error': 'bad_op'}
