"""System monitor for the Performance screen: CPU, memory, disk, network, video card and the connection delay, with a short history of each.

The old HUD kept its own collector inside hud_monitoring.py and only ran it while its Tk dialog was open; this one does the same for the new
screen. The screen sends `watch` every few seconds; the collector samples once a second while a watch is fresh and goes idle on its own
after it ends, so a closed screen costs nothing. The slow sources (PowerShell counters, nvidia-smi, SMBIOS data) run in their own short
threads and never delay the one-second tick.
"""
from __future__ import annotations

import collections
import json
import logging
import shutil
import socket
import subprocess
import threading
import time

_log = logging.getLogger(__name__)
_WATCH_TTL = 12.0
_SLOW_EVERY = 10.0
_HIST = 120
_NO_WINDOW = 0x08000000
_SERIES = ('cpu', 'ram', 'disk', 'dio', 'dn', 'up', 'gpu', 'ping')
_VIRTUAL_NICS = ('hamachi', 'vbox', 'virtual', 'vmware', 'vpn', 'loopback', 'vethernet')
_MEM_TYPES = {20: 'DDR', 21: 'DDR2', 24: 'DDR3', 26: 'DDR4', 34: 'DDR5', 29: 'LPDDR3', 30: 'LPDDR4', 35: 'LPDDR5'}
_FORMS = {8: 'DIMM', 12: 'SODIMM'}

_lock = threading.Lock()
_publish = lambda topic, payload, sticky=True: None            # noqa: E731  (bound by bind())
_hist = {k: collections.deque(maxlen=_HIST) for k in _SERIES}
_static: dict = {}
_slow: dict = {}
_ping_ms = None
_last = None
_watch_at = 0.0
_running = False
_busy = {'static': False, 'slow': False, 'ping': False}
_prev: dict = {}

_STATIC_PS = r"""
$ErrorActionPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.Encoding]::UTF8
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name,L2CacheSize,L3CacheSize,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,VirtualizationFirmwareEnabled,SocketDesignation
$gpu = @(Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM)
$ram = @(Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity,Speed,ConfiguredClockSpeed,FormFactor,SMBIOSMemoryType)
$arr = Get-CimInstance Win32_PhysicalMemoryArray | Select-Object -First 1 MemoryDevices
$disk = Get-PhysicalDisk | Select-Object -First 1 MediaType
$nic = Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Select-Object -First 1 Name,InterfaceDescription,LinkSpeed
$prof = Get-NetConnectionProfile | Select-Object -First 1 -ExpandProperty Name
[pscustomobject]@{cpu=$cpu;gpu=$gpu;ram=$ram;slots=$arr.MemoryDevices;disk=$disk.MediaType;nic=$nic;profile=$prof} | ConvertTo-Json -Depth 4 -Compress
"""
_SLOW_PS = r"""
$ErrorActionPreference='SilentlyContinue'
$d = Get-CimInstance Win32_PerfFormattedData_PerfDisk_PhysicalDisk | Where-Object Name -eq '_Total' | Select-Object -First 1 PercentDiskTime,AvgDisksecPerTransfer
$g = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | Where-Object { $_.Name -like '*engtype_3D*' } | Measure-Object UtilizationPercentage -Sum
$gd = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Measure-Object DedicatedUsage -Sum
$gs = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | Measure-Object SharedUsage -Sum
$t = Get-CimInstance -Namespace root/wmi MSAcpi_ThermalZoneTemperature | Select-Object -First 1 -ExpandProperty CurrentTemperature
[pscustomobject]@{disk=$d;gpu3d=$g.Sum;gpudedicated=$gd.Sum;gpushared=$gs.Sum;temp=$t} | ConvertTo-Json -Depth 3 -Compress
"""


def bind(publish) -> None:
    global _publish
    _publish = publish


def _ps_json(script: str, timeout: float):
    try:
        raw = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, timeout=timeout, creationflags=_NO_WINDOW).stdout
        text = raw.decode('utf-8', errors='ignore').strip()
        return json.loads(text[text.find('{'):]) if '{' in text else None
    except Exception:
        _log.debug('powershell query failed', exc_info=True)
        return None


def _list(v) -> list:
    return v if isinstance(v, list) else ([] if v is None else [v])


def _num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_static(raw: dict) -> dict:
    """The hardware that never changes while Jarvis runs, from the SMBIOS / WMI answer of _STATIC_PS."""
    cpu = raw.get('cpu') or {}
    gpus = [g for g in _list(raw.get('gpu')) if g.get('Name')]
    gpu = next((g for g in gpus if any(w in g['Name'].lower() for w in ('nvidia', 'geforce', 'rtx', 'gtx', 'radeon'))), gpus[0] if gpus else {})
    sticks = _list(raw.get('ram'))
    nic = raw.get('nic') or {}
    ff = int((sticks[0].get('FormFactor') or 0)) if sticks else 0
    mt = int((sticks[0].get('SMBIOSMemoryType') or 0)) if sticks else 0
    return {
        'cpu': {'name': str(cpu.get('Name') or '').strip(), 'cores': int(_num(cpu.get('NumberOfCores'))), 'threads': int(_num(cpu.get('NumberOfLogicalProcessors'))),
                'max_mhz': _num(cpu.get('MaxClockSpeed')), 'l2_kb': int(_num(cpu.get('L2CacheSize'))), 'l3_kb': int(_num(cpu.get('L3CacheSize'))),
                'virt': cpu.get('VirtualizationFirmwareEnabled') if isinstance(cpu.get('VirtualizationFirmwareEnabled'), bool) else None},
        'gpu': {'name': str(gpu.get('Name') or ''), 'driver': str(gpu.get('DriverVersion') or ''), 'vram': abs(_num(gpu.get('AdapterRAM'))),
                'discrete': any(w in str(gpu.get('Name') or '').lower() for w in ('nvidia', 'geforce', 'rtx', 'gtx', 'radeon rx', 'radeon pro'))},
        'ram': {'speed': int(max((_num(s.get('ConfiguredClockSpeed')) or _num(s.get('Speed')) for s in sticks), default=0)), 'sticks': len(sticks),
                'slots': int(_num(raw.get('slots'))), 'form': _FORMS.get(ff, ''), 'kind': _MEM_TYPES.get(mt, '')},
        'disk': {'kind': str(raw.get('disk') or '')},
        'net': {'adapter': str(nic.get('InterfaceDescription') or ''), 'link': str(nic.get('LinkSpeed') or ''), 'profile': str(raw.get('profile') or '')},
    }


def parse_nvidia_smi(text: str) -> dict:
    """`nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,clocks.gr,power.draw,memory.used,memory.total --format=csv,noheader,nounits`, first card."""
    try:
        util, temp, clock, power, used, total = [x.strip() for x in text.strip().splitlines()[0].split(',')]
        return {'util': _num(util), 'temp': _num(temp), 'clock': _num(clock), 'power': _num(power), 'mem_used': _num(used) * 1048576, 'mem_total': _num(total) * 1048576}
    except Exception:
        return {}


def _nvidia() -> dict:
    exe = shutil.which('nvidia-smi')
    if not exe:
        return {}
    try:
        out = subprocess.run([exe, '--query-gpu=utilization.gpu,temperature.gpu,clocks.gr,power.draw,memory.used,memory.total', '--format=csv,noheader,nounits'],
                             capture_output=True, timeout=6, creationflags=_NO_WINDOW).stdout.decode('utf-8', errors='ignore')
        return parse_nvidia_smi(out)
    except Exception:
        return {}


def _run_once(flag: str, fn) -> None:
    """Start fn in its own thread unless the previous run of the same kind is still going."""
    with _lock:
        if _busy[flag]:
            return
        _busy[flag] = True

    def work():
        try:
            fn()
        except Exception:
            _log.debug('perf %s failed', flag, exc_info=True)
        finally:
            with _lock:
                _busy[flag] = False
    threading.Thread(target=work, name='ui-bridge-perf-' + flag, daemon=True).start()


def _load_static() -> None:
    raw = _ps_json(_STATIC_PS, 25)
    if raw:
        with _lock:
            _static.update(parse_static(raw))


def _load_slow() -> None:
    raw = _ps_json(_SLOW_PS, 20) or {}
    d = raw.get('disk') or {}
    temp = _num(raw.get('temp'), None)
    gpu = _nvidia()
    if not gpu:
        gpu = {'util': min(100.0, _num(raw.get('gpu3d'))), 'mem_used': _num(raw.get('gpudedicated')) + _num(raw.get('gpushared'))}
    with _lock:
        _slow.update({'active': min(100.0, _num(d.get('PercentDiskTime'))) if d else None, 'latency_ms': _num(d.get('AvgDisksecPerTransfer')) * 1000 if d else None,
                      'cpu_temp': (temp - 2732) / 10 if temp and temp > 1000 else (temp if temp and temp < 150 else None), 'gpu': gpu})


def _load_ping() -> None:
    global _ping_ms
    t0 = time.perf_counter()
    try:
        with socket.create_connection(('1.1.1.1', 443), timeout=1.0):
            _ping_ms = round((time.perf_counter() - t0) * 1000)
    except OSError:
        _ping_ms = None


def _memory_extra() -> dict:
    try:
        import ctypes
        from ctypes import wintypes as wt

        class PerfInfo(ctypes.Structure):
            _fields_ = [('cb', wt.DWORD), ('CommitTotal', ctypes.c_size_t), ('CommitLimit', ctypes.c_size_t), ('CommitPeak', ctypes.c_size_t), ('PhysicalTotal', ctypes.c_size_t),
                        ('PhysicalAvailable', ctypes.c_size_t), ('SystemCache', ctypes.c_size_t), ('KernelTotal', ctypes.c_size_t), ('KernelPaged', ctypes.c_size_t),
                        ('KernelNonpaged', ctypes.c_size_t), ('PageSize', ctypes.c_size_t), ('HandleCount', wt.DWORD), ('ProcessCount', wt.DWORD), ('ThreadCount', wt.DWORD)]
        pi = PerfInfo()
        pi.cb = ctypes.sizeof(PerfInfo)
        if ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb):
            ps = pi.PageSize
            return {'cached': pi.SystemCache * ps, 'committed': pi.CommitTotal * ps, 'commit_limit': pi.CommitLimit * ps, 'paged': pi.KernelPaged * ps, 'nonpaged': pi.KernelNonpaged * ps}
    except Exception:
        pass
    return {}


def _addresses() -> tuple[str, str, str]:
    """IPv4, IPv6 and name of the first real network adapter."""
    import psutil
    try:
        up = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            if any(w in name.lower() for w in _VIRTUAL_NICS) or not up.get(name) or not up[name].isup:
                continue
            v4 = next((a.address for a in addrs if a.family == socket.AF_INET and not a.address.startswith(('127.', '169.254'))), '')
            if v4:
                return v4, next((a.address.split('%')[0] for a in addrs if a.family == socket.AF_INET6), ''), name
    except Exception:
        pass
    return '', '', ''


def _tick() -> dict:
    """One sample: fast psutil numbers plus whatever the slow threads have delivered so far."""
    import psutil
    now = time.monotonic()
    dt = max(0.2, now - _prev['t']) if _prev else 1.0
    vm = psutil.virtual_memory()
    dio, nio = psutil.disk_io_counters(), psutil.net_io_counters()
    dr = (dio.read_bytes - _prev['dr']) / dt if dio and _prev else 0.0
    dw = (dio.write_bytes - _prev['dw']) / dt if dio and _prev else 0.0
    dn = (nio.bytes_recv - _prev['dn']) / dt if nio and _prev else 0.0
    up = (nio.bytes_sent - _prev['up']) / dt if nio and _prev else 0.0
    _prev.update({'t': now, 'dr': dio.read_bytes if dio else 0, 'dw': dio.write_bytes if dio else 0, 'dn': nio.bytes_recv if nio else 0, 'up': nio.bytes_sent if nio else 0})
    cpu = psutil.cpu_percent(None)
    try:
        freq = psutil.cpu_freq()
    except Exception:
        freq = None
    try:
        du = psutil.disk_usage('C:\\')
    except Exception:
        du = None
    with _lock:
        st, sl = dict(_static), dict(_slow)
    gpu = {**(st.get('gpu') or {}), **(sl.get('gpu') or {})}
    gpu.setdefault('util', None)
    v4, v6, nic = _addresses()
    snap = {
        'ts': int(time.time() * 1000), 'uptime': int(time.time() - psutil.boot_time()), 'ping': _ping_ms,
        'cpu': {**(st.get('cpu') or {}), 'pct': cpu, 'mhz': freq.current if freq else None, 'procs': len(psutil.pids()), 'temp': sl.get('cpu_temp')},
        'ram': {**(st.get('ram') or {}), 'pct': vm.percent, 'used': vm.used, 'total': vm.total, 'avail': vm.available, **_memory_extra()},
        'disk': {**(st.get('disk') or {}), 'active': sl.get('active'), 'latency_ms': sl.get('latency_ms'), 'read': dr, 'write': dw,
                 'used': du.used if du else None, 'total': du.total if du else None, 'pct': du.percent if du else None},
        'net': {**(st.get('net') or {}), 'dn': dn, 'up': up, 'ipv4': v4, 'ipv6': v6, 'name': nic},
        'gpu': gpu,
    }
    for k, v in (('cpu', cpu), ('ram', vm.percent), ('disk', sl.get('active') if sl.get('active') is not None else 0.0), ('dio', dr + dw), ('dn', dn), ('up', up),
                 ('gpu', gpu.get('util') or 0.0), ('ping', _ping_ms if _ping_ms is not None else 0)):
        _hist[k].append(round(float(v), 1))
    snap['hist'] = {k: list(v) for k, v in _hist.items()}
    return snap


def _loop() -> None:
    global _running, _last
    import psutil
    psutil.cpu_percent(None)                               # the first reading is meaningless; the next tick measures a full second
    next_slow = 0.0
    while time.monotonic() - _watch_at < _WATCH_TTL:
        t0 = time.monotonic()
        if not _static:
            _run_once('static', _load_static)
        if t0 >= next_slow:
            next_slow = t0 + _SLOW_EVERY
            _run_once('slow', _load_slow)
        _run_once('ping', _load_ping)
        try:
            _last = _tick()
            _publish('perf', _last, sticky=False)
        except Exception:
            _log.debug('perf tick failed', exc_info=True)
        time.sleep(max(0.1, 1.0 - (time.monotonic() - t0)))
    with _lock:
        _running = False


def watch() -> dict:
    """Keep the collector going for another few seconds; returns the last sample so the screen has something to draw at once."""
    global _watch_at, _running
    _watch_at = time.monotonic()
    with _lock:
        start = not _running
        _running = True
    if start:
        threading.Thread(target=_loop, name='ui-bridge-perf', daemon=True).start()
    return {'ok': True, 'snapshot': _last}


def run(data: dict) -> dict:
    op = str(data.get('op', ''))
    if op == 'watch':
        return watch()
    return {'ok': False, 'error': 'bad_op'}
