import ctypes
import ctypes.wintypes as wt
import re
import threading
import time
_radio_cache: ctypes.c_void_p | None = None
_devices_cache: list[dict] = []
_devices_cache_ts: float = 0.0
_DEVICES_TTL = 60.0
try:
    _bth = ctypes.WinDLL('BluetoothAPIs.dll', use_last_error=True)
    _bth.BluetoothFindFirstRadio.restype = ctypes.c_void_p
    _bth.BluetoothFindRadioClose.restype = ctypes.c_int
    _bth.BluetoothFindFirstDevice.restype = ctypes.c_void_p
    _bth.BluetoothFindNextDevice.restype = ctypes.c_int
    _bth.BluetoothFindDeviceClose.restype = ctypes.c_int
    _bth.BluetoothSetServiceState.restype = ctypes.c_uint32
except OSError:
    _bth = None
BLUETOOTH_SERVICE_ENABLE = 1
BLUETOOTH_SERVICE_DISABLE = 0
class GUID(ctypes.Structure):
    _fields_ = [('Data1', ctypes.c_uint32), ('Data2', ctypes.c_uint16), ('Data3', ctypes.c_uint16), ('Data4', ctypes.c_uint8 * 8)]
def _guid(s: str) -> GUID:
    p = s.replace('-', '')
    return GUID(int(p[0:8], 16), int(p[8:12], 16), int(p[12:16], 16), (ctypes.c_uint8 * 8)(*bytes.fromhex(p[16:])))
GUID_A2DP_SINK = _guid('0000110b-0000-1000-8000-00805f9b34fb')
GUID_HFP_HF = _guid('0000111e-0000-1000-8000-00805f9b34fb')
GUID_HID = _guid('00001124-0000-1000-8000-00805f9b34fb')
_ALL_GUIDS = [GUID_A2DP_SINK, GUID_HFP_HF, GUID_HID]
class SYSTEMTIME(ctypes.Structure):
    _fields_ = [(f, ctypes.c_uint16) for f in ('wYear', 'wMonth', 'wDayOfWeek', 'wDay', 'wHour', 'wMinute', 'wSecond', 'wMilliseconds')]
class _BT_ADDRESS_UNION(ctypes.Union):
    _fields_ = [('ullLong', ctypes.c_uint64), ('rgBytes', ctypes.c_uint8 * 6)]
class BLUETOOTH_DEVICE_INFO(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_uint32), ('Address', _BT_ADDRESS_UNION), ('ulClassofDevice', ctypes.c_uint32), ('fConnected', ctypes.c_int32), ('fRemembered', ctypes.c_int32), ('fAuthenticated', ctypes.c_int32), ('stLastSeen', SYSTEMTIME), ('stLastUsed', SYSTEMTIME), ('szName', ctypes.c_wchar * 248)]
    def __init__(self):
        super().__init__()
        self.dwSize = ctypes.sizeof(self)
class BLUETOOTH_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_uint32)]
class BLUETOOTH_DEVICE_SEARCH_PARAMS(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_uint32), ('fReturnAuthenticated', ctypes.c_int32), ('fReturnRemembered', ctypes.c_int32), ('fReturnUnknown', ctypes.c_int32), ('fReturnConnected', ctypes.c_int32), ('fIssueInquiry', ctypes.c_int32), ('cTimeoutMultiplier', ctypes.c_uint8), ('hRadio', ctypes.c_void_p)]
    def __init__(self, radio_value=None):
        super().__init__()
        self.dwSize = ctypes.sizeof(self)
        self.fReturnAuthenticated = 1
        self.fReturnRemembered = 1
        self.fIssueInquiry = 0
        self.cTimeoutMultiplier = 0
        if radio_value is not None:
            self.hRadio = radio_value
_CATEGORY_ALIASES: list[tuple[re.Pattern, list[str]]] = [(re.compile('наушник|ушах|ушник|headphone|headset|гарнитур|уши\\b', re.IGNORECASE), ['jbl', 'sony', 'beats', 'bose', 'sennheiser', 'jabra', 'tune', 'qc', 'wh-', 'wf-', 'airpod', 'buds', 'earphone', 'headphone', 'headset', 'galaxy buds', 'momentum', 'elite', 'evolve', 'anc', 'noise']), (re.compile('колонк|динамик|speaker|акустик', re.IGNORECASE), ['speaker', 'soundbar', 'soundlink', 'charge', 'flip', 'boom', 'xtreme', 'pulse', 'go ', 'mini', 'party', 'harman']), (re.compile('клавиатур|keyboard', re.IGNORECASE), ['keyboard', 'keychron', 'keys', 'key', 'mx keys', 'k380', 'k780', 'k800', 'pebble']), (re.compile('мышь|мышка|mouse', re.IGNORECASE), ['mouse', 'mx master', 'anywhere', 'pebble', 'm750', 'm650']), (re.compile('геймпад|контроллер|джойстик|gamepad|controller', re.IGNORECASE), ['controller', 'gamepad', 'dualshock', 'dualsense', 'xbox', 'joystick']), (re.compile('монитор|экран|дисплей|monitor|display', re.IGNORECASE), ['monitor', 'display', 'lg ', 'samsung', 'dell ', 'asus ', 'acer ', 'benq', 'viewsonic', 'philips', 'lenovo', 'aoc '])]
def _get_radio() -> ctypes.c_void_p | None:
    global _radio_cache
    if _radio_cache is not None:
        return _radio_cache
    if not _bth:
        return None
    params = BLUETOOTH_FIND_RADIO_PARAMS()
    params.dwSize = ctypes.sizeof(params)
    radio = ctypes.c_void_p()
    hfind = _bth.BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(radio))
    if hfind:
        _bth.BluetoothFindRadioClose(ctypes.c_void_p(hfind))
        _radio_cache = radio
        return radio
    return None
def get_paired_devices(force: bool=False) -> list[dict]:
    global _devices_cache, _devices_cache_ts
    if not force and _devices_cache and (time.time() - _devices_cache_ts < _DEVICES_TTL):
        return _devices_cache
    if not _bth:
        result = _get_paired_devices_ps()
        _devices_cache, _devices_cache_ts = (result, time.time())
        return result
    radio_val = _get_radio()
    sp = BLUETOOTH_DEVICE_SEARCH_PARAMS(radio_val)
    di = BLUETOOTH_DEVICE_INFO()
    hfind_raw = _bth.BluetoothFindFirstDevice(ctypes.byref(sp), ctypes.byref(di))
    if not hfind_raw:
        return []
    hfind = ctypes.c_void_p(hfind_raw)
    devices = []
    seen = set()
    try:
        while True:
            name = di.szName.strip()
            if name and name not in seen:
                seen.add(name)
                devices.append({'name': name, 'address': di.Address.ullLong, 'connected': bool(di.fConnected)})
            di = BLUETOOTH_DEVICE_INFO()
            if not _bth.BluetoothFindNextDevice(hfind, ctypes.byref(di)):
                break
    finally:
        _bth.BluetoothFindDeviceClose(hfind)
    _devices_cache, _devices_cache_ts = (devices, time.time())
    return devices
def _get_paired_devices_ps() -> list[dict]:
    import subprocess, json
    raw = subprocess.run(['powershell', '-NoProfile', '-Command', 'Get-PnpDevice -Class Bluetooth | Select-Object Status,FriendlyName,InstanceId | ConvertTo-Json -Depth 2'], capture_output=True, text=True, encoding='utf-8', creationflags=134217728).stdout.strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except Exception:
        return []
    if isinstance(items, dict):
        items = [items]
    _sys = re.compile('enumerator|protocol|tdi|intel|microsoft|rfcomm|bthle|avrcp|hands.free|audio gateway|hid service', re.I)
    seen, out = (set(), [])
    for it in items:
        name = (it.get('FriendlyName') or '').strip()
        if name and (not _sys.search(name)) and (name not in seen):
            seen.add(name)
            out.append({'name': name, 'address': None, 'connected': it.get('Status') == 'OK'})
    return out
def _fuzzy_find_device(devices: list[dict], query: str) -> tuple[dict | None, int]:
    from features.gaming import transliterate_cyrillic_to_latin
    from rapidfuzz import fuzz as _fuzz
    q = query.lower().strip()
    qt = transliterate_cyrillic_to_latin(q)
    best, best_score = (None, 0)
    for dev in devices:
        nl = dev['name'].lower()
        score = max(_fuzz.partial_ratio(q, nl), _fuzz.partial_ratio(qt, nl), _fuzz.token_set_ratio(qt, nl))
        if score > best_score:
            best_score, best = (score, dev)
    return (best, best_score) if best_score >= 45 else (None, 0)
def _category_find_all(devices: list[dict], query: str) -> list[dict]:
    ql = query.lower()
    for pattern, keywords in _CATEGORY_ALIASES:
        if pattern.search(ql):
            return [d for d in devices if any((k in d['name'].lower() for k in keywords))]
    return []
def _resolve_device(devices: list[dict], query: str) -> 'dict | list[dict] | None':
    dev, _ = _fuzzy_find_device(devices, query)
    if dev is not None:
        return dev
    candidates = _category_find_all(devices, query)
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return candidates
    return None
def _set_service(address: int, radio: ctypes.c_void_p | None, enable: bool) -> bool:
    flag = BLUETOOTH_SERVICE_ENABLE if enable else BLUETOOTH_SERVICE_DISABLE
    di = BLUETOOTH_DEVICE_INFO()
    di.Address.ullLong = address
    h_radio = radio if radio is not None else ctypes.c_void_p(None)
    results = [False] * len(_ALL_GUIDS)
    def _call(idx, guid):
        di_local = BLUETOOTH_DEVICE_INFO()
        di_local.Address.ullLong = address
        ret = _bth.BluetoothSetServiceState(h_radio, ctypes.byref(di_local), ctypes.byref(guid), ctypes.c_uint32(flag))
        if ret == 0:
            results[idx] = True
        else:
            pass
    threads = [threading.Thread(target=_call, args=(i, g), daemon=True) for i, g in enumerate(_ALL_GUIDS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    return any(results)
def bt_connect(device_query: str) -> tuple:
    devices = get_paired_devices()
    if not devices:
        return (False, 'Спаренные Bluetooth-устройства не найдены.')
    dev = _resolve_device(devices, device_query)
    if dev is None:
        names = ', '.join((d['name'] for d in devices[:5]))
        return (False, f'Устройство «{device_query}» не найдено. Доступные: {names}.')
    if isinstance(dev, list):
        return (None, dev)
    name = dev['name']
    address = dev.get('address')
    if _bth and address:
        radio = _get_radio()
        ok = _set_service(address, radio, enable=True)
        if not ok or any(k in name.lower() for k in ['keyboard', 'mouse', 'key', 'клавиату', 'мышь', 'мышка']):
            _pnp_reconnect(name)
    else:
        _pnp_reconnect(name)
    global _devices_cache_ts
    _devices_cache_ts = 0.0
    return (True, name)
def bt_disconnect(device_query: str) -> tuple:
    devices = get_paired_devices()
    if not devices:
        return (False, 'Спаренные Bluetooth-устройства не найдены.')
    dev = _resolve_device(devices, device_query)
    if dev is None:
        return (False, f'Устройство «{device_query}» не найдено.')
    if isinstance(dev, list):
        return (None, dev)
    name = dev['name']
    address = dev.get('address')
    if _bth and address:
        radio = _get_radio()
        _set_service(address, radio, enable=False)
    else:
        _pnp_disable(name)
    global _devices_cache_ts
    _devices_cache_ts = 0.0
    return (True, name)
def bt_list() -> list[str]:
    return [d['name'] for d in get_paired_devices()]
def _run_ps(cmd: str) -> str:
    import subprocess
    return subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, text=True, encoding='utf-8', creationflags=134217728).stdout.strip()
def _pnp_get_iid(name: str) -> str | None:
    import json
    raw = _run_ps('Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,InstanceId | ConvertTo-Json -Depth 2')
    try:
        items = json.loads(raw)
        if isinstance(items, dict):
            items = [items]
        for it in items:
            if (it.get('FriendlyName') or '').strip().lower() == name.lower():
                return it.get('InstanceId', '').replace('\\', '\\\\')
    except Exception:
        pass
    return None
def _pnp_reconnect(name: str) -> None:
    iid = _pnp_get_iid(name)
    if not iid:
        return
    _run_ps(f'Disable-PnpDevice -InstanceId "{iid}" -Confirm:$false 2>$null')
    _run_ps('Start-Sleep -Milliseconds 1200')
    _run_ps(f'Enable-PnpDevice  -InstanceId "{iid}" -Confirm:$false 2>$null')
def _pnp_disable(name: str) -> None:
    iid = _pnp_get_iid(name)
    if not iid:
        return
    _run_ps(f'Disable-PnpDevice -InstanceId "{iid}" -Confirm:$false 2>$null')
def _bt_exec(action: str, dev: dict, speak) -> None:
    import actions.bluetooth as _btmod
    name = dev['name']
    address = dev.get('address')
    enable = action == 'connect'
    if _bth and address:
        radio = _get_radio()
        ok = _set_service(address, radio, enable=enable)
        if enable and (not ok or any(k in name.lower() for k in ['keyboard', 'mouse', 'key', 'клавиату', 'мышь'])):
            _pnp_reconnect(name)
        elif not enable and not ok:
            _pnp_disable(name)
    elif enable:
        _pnp_reconnect(name)
    else:
        _pnp_disable(name)
    global _devices_cache_ts
    _devices_cache_ts = 0.0
    verb = 'подключён' if enable else 'отключён'
    speak(f'{name} {verb}.')
def _bt_handle_result(ok, result, action: str, speak, handler=None) -> None:
    if ok is True:
        verb = 'подключён' if action == 'connect' else 'отключён'
        speak(f'{result} {verb}.')
    elif ok is False:
        speak(result)
    else:
        candidates = result
        names_str = ' или '.join((d['name'] for d in candidates))
        verb = 'подключить' if action == 'connect' else 'отключить'
        if handler is not None:
            handler._bt_pending = {'action': action, 'candidates': candidates}
        speak(f'У вас несколько устройств: {names_str}. Какое {verb}?')
