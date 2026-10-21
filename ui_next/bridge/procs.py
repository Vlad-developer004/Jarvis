"""Task-manager part of the System screen: running processes with their load, ending / priority, and the startup entries (enable, disable).

The screen polls `list` every couple of seconds while its tab is open; nothing runs in the background. CPU and disk rates are deltas between two
`list` calls, so the first answer has zeros. Startup entries are read from the Run keys and the Startup folders; switching one off uses the same
StartupApproved flag Windows' own Task Manager writes, so nothing is deleted and the entry can be switched back on.
"""
from __future__ import annotations

import base64
import ctypes
import getpass
import logging
import os
import struct
import subprocess
import threading
import time
import webbrowser
import zlib
from urllib.parse import quote

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

_GAME_DIRS = (r'\steamapps\common' + '\\', r'\epic games' + '\\', r'\gog galaxy\games' + '\\', r'\riot games' + '\\')
_ICON_CACHE: dict = {}              # exe path (lower) -> base64 PNG, '' when the file has no icon
_SIGN_CACHE: dict = {}              # (exe path, mtime) -> signature answer
_SIGN_PS = ('$s = Get-AuthenticodeSignature -LiteralPath $env:JARVIS_SIGN_PATH; '
            '[pscustomobject]@{st = [string]$s.Status; sub = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { "" }} | ConvertTo-Json -Compress')

_RUN = r'Software\Microsoft\Windows\CurrentVersion\Run'
_RUN32 = r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'
_APPROVED = r'Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved'
_KEYS = {'user_run': ('HKCU', _RUN, 'Run'), 'machine_run': ('HKLM', _RUN, 'Run'), 'machine_run32': ('HKLM', _RUN32, 'Run32')}


def is_protected(pid: int, name: str) -> bool:
    return pid in (0, 4) or name.lower() in _CRITICAL


def _game_exes() -> frozenset:
    try:
        from features.gaming.watcher import _GAME_EXE_MAP
        return frozenset(_GAME_EXE_MAP)
    except Exception:
        return frozenset()


def is_game(name: str, exe: str, known: frozenset) -> bool:
    low = exe.lower()
    return name.lower() in known or any(d in low for d in _GAME_DIRS)


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
        known = _game_exes()
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
                                 'started': int(created), 'prio': prio, 'io': 0.0, 'protected': is_protected(pid, name), 'self': pid == me, 'game': is_game(name, exe, known)})
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
    return {'ok': True, 'procs': rows, 'cores': ncpu, 'ram': {'total': vm.total, 'used': vm.total - vm.available}, 'me': getpass.getuser(), 'ts': int(time.time() * 1000)}


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


def affinity(data: dict) -> dict:
    """Read (no `cores`) or set the CPU cores a process may run on."""
    import psutil
    p = _find(data.get('pid'), data.get('started'))
    if p is None:
        return {'ok': False, 'error': 'gone'}
    total = psutil.cpu_count() or 1
    try:
        if is_protected(p.pid, p.name()):
            return {'ok': False, 'error': 'protected'}
        if 'cores' not in data:
            return {'ok': True, 'cores': p.cpu_affinity(), 'total': total}
        cores = data.get('cores')
        if not isinstance(cores, list) or not cores or not all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c < total for c in cores):
            return {'ok': False, 'error': 'bad_cores'}
        p.cpu_affinity(sorted(set(cores)))
    except psutil.AccessDenied:
        return {'ok': False, 'error': 'denied'}
    except (psutil.Error, AttributeError, OSError):
        return {'ok': False, 'error': 'failed'}
    return {'ok': True}


def search(data: dict) -> dict:
    """Open a web search for what the process is."""
    import psutil
    p = _find(data.get('pid'), data.get('started'))
    try:
        name = p.name() if p else ''
    except psutil.Error:
        name = ''
    if not name:
        return {'ok': False, 'error': 'gone'}
    webbrowser.open('https://www.google.com/search?q=' + quote(f'{name} что это за процесс'))
    return {'ok': True}


def parse_sign(raw: str) -> dict:
    """Get-AuthenticodeSignature answer (JSON) -> {'status': valid|unsigned|invalid|unknown, 'signer': publisher}."""
    import json
    import re
    try:
        d = json.loads(raw)
    except ValueError:
        return {'status': 'unknown', 'signer': ''}
    st = str(d.get('st', ''))
    m = re.search(r'(?:^|, )CN=("[^"]+"|[^,]+)', str(d.get('sub', '')))
    signer = m.group(1).strip('"') if m else ''
    return {'status': 'valid' if st == 'Valid' else 'unsigned' if st == 'NotSigned' else 'unknown' if st in ('', 'UnknownError') else 'invalid', 'signer': signer}


def sign(data: dict) -> dict:
    """Digital signature of the program file, asked on demand for the selected process (PowerShell takes a moment) and cached per file version."""
    import psutil
    p = _find(data.get('pid'), data.get('started'))
    try:
        exe = p.exe() if p else ''
    except psutil.Error:
        exe = ''
    if not exe or not os.path.isfile(exe):
        return {'ok': False, 'error': 'no_path'}
    key = (exe, os.path.getmtime(exe))
    if key not in _SIGN_CACHE:
        try:
            out = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', _SIGN_PS], capture_output=True, text=True, timeout=12,
                                 creationflags=_NO_WINDOW, env={**os.environ, 'JARVIS_SIGN_PATH': exe}).stdout
        except (OSError, subprocess.TimeoutExpired):
            return {'ok': False, 'error': 'timeout'}
        if len(_SIGN_CACHE) > 500:
            _SIGN_CACHE.clear()
        _SIGN_CACHE[key] = parse_sign(out)
    return {'ok': True, **_SIGN_CACHE[key]}


# ---- program icons: the first icon of the exe, as a 32x32 PNG ----

def _png(w: int, h: int, rgba: bytes) -> bytes:
    import struct

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b''.join(b'\x00' + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')


def _icon_png(path: str):
    """PNG bytes of the exe's first icon, or None. Plain user32/gdi32/shell32 calls (no COM), on private DLL handles so the argtypes set here
    do not leak into other users of ctypes.windll."""
    from ctypes import wintypes
    user32, gdi32, shell32 = ctypes.WinDLL('user32'), ctypes.WinDLL('gdi32'), ctypes.WinDLL('shell32')

    class ICONINFO(ctypes.Structure):
        _fields_ = [('fIcon', wintypes.BOOL), ('xHotspot', wintypes.DWORD), ('yHotspot', wintypes.DWORD), ('hbmMask', wintypes.HBITMAP), ('hbmColor', wintypes.HBITMAP)]

    class BITMAP(ctypes.Structure):
        _fields_ = [('bmType', wintypes.LONG), ('bmWidth', wintypes.LONG), ('bmHeight', wintypes.LONG), ('bmWidthBytes', wintypes.LONG), ('bmPlanes', wintypes.WORD),
                    ('bmBitsPixel', wintypes.WORD), ('bmBits', wintypes.LPVOID)]

    class BMIH(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG), ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD),
                    ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                    ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]
    shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON), wintypes.UINT]
    shell32.ExtractIconExW.restype = wintypes.UINT
    user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(ICONINFO)]
    user32.DestroyIcon.argtypes = [wintypes.HICON]
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.GetObjectW.argtypes = [wintypes.HGDIOBJ, ctypes.c_int, ctypes.c_void_p]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(BMIH), wintypes.UINT]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    big = wintypes.HICON()
    if shell32.ExtractIconExW(path, 0, ctypes.byref(big), None, 1) < 1 or not big:
        return None
    info = ICONINFO()
    dc = user32.GetDC(None)
    try:
        if not user32.GetIconInfo(big, ctypes.byref(info)) or not info.hbmColor:
            return None
        bm = BITMAP()
        gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(bm), ctypes.byref(bm))
        w, h = bm.bmWidth, bm.bmHeight
        if not (0 < w <= 256 and 0 < h <= 256):
            return None

        def bits(bitmap):
            hdr = BMIH(ctypes.sizeof(BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)       # negative height: top-down rows
            buf = (ctypes.c_ubyte * (w * h * 4))()
            return bytes(buf) if gdi32.GetDIBits(dc, bitmap, 0, h, buf, ctypes.byref(hdr), 0) else None
        color = bits(info.hbmColor)
        if color is None:
            return None
        px = bytearray(color)                                  # BGRA
        if not any(px[3::4]) and info.hbmMask:                 # old icons have no alpha channel: the 1-bit mask says what is opaque
            mask = bits(info.hbmMask)
            if mask:
                for i in range(w * h):
                    px[i * 4 + 3] = 0 if mask[i * 4] else 255
        px[0::4], px[2::4] = px[2::4], px[0::4]                # -> RGBA
        return _png(w, h, bytes(px))
    finally:
        user32.ReleaseDC(None, dc)
        for hb in (info.hbmColor, info.hbmMask):
            if hb:
                gdi32.DeleteObject(hb)
        user32.DestroyIcon(big)


def _exe_of_path(raw) -> str:
    """The .exe a startup entry or a service points at (a command line with arguments gives just the program), only when it is an existing file."""
    import re
    m = re.match(r'^\s*"?([^"]+?\.exe)(?=[\s"]|$)', os.path.expandvars(str(raw or '')), re.I)
    return m.group(1) if m and os.path.isfile(m.group(1)) else ''


def icons(data: dict) -> dict:
    """{'icons': {key: base64 PNG or ''}, 'desc': {key: short description or ''}} for up to 24 items. An item is {pid, started} (key "pid:started";
    the path is taken from the live process) or {path} (key "p:<path as sent>"; startup entries and services, only an existing .exe is read)."""
    import psutil
    from . import proc_desc
    out, desc = {}, {}
    for item in list(data.get('items') or [])[:24]:
        if not isinstance(item, dict):
            continue
        if 'path' in item:
            key, exe = f"p:{item.get('path')}", _exe_of_path(item.get('path'))
        else:
            key = f"{item.get('pid')}:{item.get('started')}"
            p = _find(item.get('pid'), item.get('started'))
            try:
                exe = p.exe() if p else ''
            except psutil.Error:
                exe = ''
        if not exe or not os.path.isfile(exe):
            out[key] = desc[key] = ''
            continue
        low = exe.lower()
        if low not in _ICON_CACHE:
            try:
                png = _icon_png(exe)
            except Exception:
                _log.debug('icon of %s failed', exe, exc_info=True)
                png = None
            if len(_ICON_CACHE) > 600:
                _ICON_CACHE.clear()
            _ICON_CACHE[low] = base64.b64encode(png).decode('ascii') if png else ''
        out[key] = _ICON_CACHE[low]
        desc[key] = proc_desc.description(exe)
    return {'ok': True, 'icons': out, 'desc': desc}


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
        if op == 'affinity':
            return affinity(data)
        if op == 'search':
            return search(data)
        if op == 'sign':
            return sign(data)
        if op == 'icons':
            return icons(data)
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
