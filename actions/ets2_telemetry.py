import threading
import time
import os
from typing import Optional
try:
    import truck_telemetry as _tt
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
_lock = threading.Lock()
_cache: Optional[dict] = None
_last_read: float = 0.0
_CACHE_TTL = 0.25
_poll_thread: Optional[threading.Thread] = None
_poll_stop = threading.Event()
_POLL_INTERVAL = 0.25
def is_available() -> bool:
    return _AVAILABLE
_initialized = False
_TRUCK_DATA_KEYS = {"fuel", "speed", "engineEnabled", "fuelRange", "routeDistance", "speedLimit"}
_LOG_PATH = "logs/telemetry_debug.log"
_DEBUG_TELEMETRY = str(os.environ.get('JARVIS_DEBUG_TELEMETRY', '')).strip().lower() in ('1', 'true', 'yes', 'on')
def _tlog(msg: str) -> None:
    if _DEBUG_TELEMETRY:
        print(f"[TELEMETRY] {msg}", flush=True)
    try:
        import os as _os
        _os.makedirs("logs", exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as _f:
            _f.write(f"{msg}\n")
    except Exception:
        pass
def _force_init() -> bool:
    try:
        from multiprocessing.shared_memory import SharedMemory as _SM
        import struct as _struct
        import truck_telemetry.truck_telemetry as _tti
        from truck_telemetry.telemetry_version import v1_12, v1_10
        mem = _SM(name="Local\\SCSTelemetry", create=False)
        try:
            rev = _struct.unpack_from('<I', mem.buf, 40)[0]
        except Exception:
            rev = 0
        if rev >= 12:
            preferred = v1_12
            fallback = v1_10
        else:
            preferred = v1_10
            fallback = v1_12
        for ver in (preferred, fallback):
            try:
                test = ver.parse_data(mem.buf)
                if test and isinstance(test, dict):
                    _tti._mem = mem
                    _tti._telemetry_sdk_version = ver
                    return True
            except Exception as _ve:
                pass
        _tti._mem = mem
        _tti._telemetry_sdk_version = v1_12
        return True
    except Exception as _e:
        _tlog(f"Force-init failed: {_e}")
        return False
def _read_raw() -> Optional[dict]:
    global _initialized
    if not _AVAILABLE:
        return None
    try:
        if not _initialized:
            try:
                _tt.init()
                _initialized = True
            except Exception as _init_err:
                err_msg = str(_init_err)
                if "Not support" in err_msg or "version" in err_msg.lower():
                    if _force_init():
                        _initialized = True
                    else:
                        _tlog(f"All parsers failed. Raw error: {_init_err}")
                        return None
                elif ("No such file" in err_msg or "FileNotFoundError" in err_msg or "not found" in err_msg.lower()
                      or "WinError 2" in err_msg or "SCSTelemetry" in err_msg):
                    return None
                else:
                    _tlog(f"Init error (unexpected): {_init_err}")
                    return None
        data = _tt.get_data()
        if not data:
            return None
        sdk_flag = data.get("sdkActive")
        if sdk_flag is None:
            sdk_flag = data.get("sdk_active") or data.get("connected")
        if sdk_flag is None:
            sdk_flag = any(k in data for k in _TRUCK_DATA_KEYS)
        if not sdk_flag:
            return None
        return data
    except Exception as e:
        em = str(e)
        if "WinError 2" in em or "SCSTelemetry" in em:
            return None
        _tlog(f"_read_raw error: {e}")
        return None
def get() -> Optional[dict]:
    global _cache, _last_read
    now = time.monotonic()
    with _lock:
        if now - _last_read < _CACHE_TTL and _cache is not None:
            return _cache
    data = _read_raw()
    with _lock:
        _cache = data
        _last_read = now
    return data
def start_background_poll():
    global _poll_thread
    if not _AVAILABLE:
        return
    if _poll_thread and _poll_thread.is_alive():
        return
    _poll_stop.clear()
    def _loop():
        while not _poll_stop.is_set():
            _read_raw_into_cache()
            _poll_stop.wait(_POLL_INTERVAL)
    _poll_thread = threading.Thread(target=_loop, daemon=True, name="ets2_telem_poll")
    _poll_thread.start()
def stop_background_poll():
    _poll_stop.set()
def _read_raw_into_cache():
    global _cache, _last_read
    data = _read_raw()
    with _lock:
        _cache = data
        _last_read = time.monotonic()
def get_fuel() -> Optional[float]:
    d = get()
    return float(d["fuel"]) if d else None
def get_fuel_range() -> Optional[float]:
    d = get()
    return float(d["fuelRange"]) if d else None
def get_speed_kmh() -> Optional[float]:
    d = get()
    if d is None:
        return None
    return float(d["speed"]) * 3.6
def get_speed_limit_kmh() -> Optional[float]:
    d = get()
    if d is None:
        return None
    return float(d["speedLimit"]) * 3.6
def get_wipers() -> Optional[bool]:
    d = get()
    return bool(d["wipers"]) if d else None
def get_lights_low() -> Optional[bool]:
    d = get()
    return bool(d["lightsBeamLow"]) if d else None
def get_lights_high() -> Optional[bool]:
    d = get()
    return bool(d["lightsBeamHigh"]) if d else None
def get_engine_on() -> Optional[bool]:
    d = get()
    return bool(d["engineEnabled"]) if d else None
def get_park_brake() -> Optional[bool]:
    d = get()
    return bool(d["parkBrake"]) if d else None
def get_lights_aux_front() -> Optional[int]:
    d = get()
    return int(d["lightsAuxFront"]) if d else None
def get_lights_aux_roof() -> Optional[int]:
    d = get()
    return int(d["lightsAuxRoof"]) if d else None
def get_lights_parking() -> Optional[bool]:
    d = get()
    return bool(d["lightsParking"]) if d else None
def get_position() -> Optional[tuple[float, float, float]]:
    d = get()
    if d is None:
        return None
    return (float(d["coordinateX"]), float(d["coordinateY"]), float(d["coordinateZ"]))
def get_game_time() -> Optional[int]:
    d = get()
    return int(d.get("time", 0)) if d else None
def get_heading_deg() -> Optional[float]:
    d = get()
    if d is None:
        return None
    return float(d["rotationY"]) * 360.0 % 360.0
def get_cruise_active() -> Optional[bool]:
    d = get()
    if d is None:
        return None
    for field in ("cruiseControl", "cruise_control", "cruiseControlOn", "cruiseControlEnabled"):
        v = d.get(field)
        if v is not None:
            return bool(v)
    return None
def get_cruise_speed_kmh() -> Optional[float]:
    d = get()
    if d is None:
        return None
    for field in ("cruiseControlSpeed", "cruise_control_speed", "cruiseSpeed"):
        v = d.get(field)
        if v is not None:
            kmh = float(v) * 3.6
            return round(kmh / 5.0) * 5.0
    return None
def get_gear() -> Optional[int]:
    d = get()
    if d is None:
        return None
    for field in ("gear", "gearDashboard", "gearDash", "gearSelected", "truckGear", "currentGear"):
        v = d.get(field)
        if v is None:
            continue
        try:
            gv = int(v)
            return gv
        except Exception:
            continue
    try:
        if bool(d.get("reverse", False)) is True:
            return -1
    except Exception:
        pass
    return None
