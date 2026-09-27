from .hud_utils import _blend, _bar_color, _read_gpu_temp, _read_gpu_util, _uptime, _fmt_speed
from .hud_state import HudState, STATE
from datetime import datetime
import socket
import time
import threading
import psutil
from . import hud_renderer as renderer
from . import hud_constants as _hud_constants
from .hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _RU_MON, _RU_DAYS
import psutil as _ps
import pythoncom
import os
import sys
import subprocess
import json
from core import i18n
from core.system.version import APP_VERSION

def _log_monitor_msg(msg: str):
    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.getcwd()
        log_dir = os.path.join(base_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, 'monitoring.log'), 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now()}] {msg}\n")
    except: pass

_LOW_PERF_MODE = (_ps.cpu_count(logical=False) or 4) <= 2

def start_sys_thread(hud) -> None:
    def _worker() -> None:
        _log_monitor_msg("start_sys_thread: Worker started")
        try: pythoncom.CoInitialize()
        except Exception as e: _log_monitor_msg(f"CoInitialize FAILED: {e}")
            
        wmi_conns = {}
        try:
            import wmi as _wm
            try: wmi_conns['ohm'] = _wm.WMI(namespace='root/OpenHardwareMonitor')
            except: pass
            try: wmi_conns['cim'] = _wm.WMI()
            except: pass
            try: wmi_conns['wmi'] = _wm.WMI(namespace='root/wmi')
            except: pass
        except: pass

        while True:
            d: dict = {}
            try:
                if time.time() - getattr(_worker, '_sys_gpu_t', 0) > (10.0 if _LOW_PERF_MODE else 5.0):
                    _worker._sys_gpu_t = time.time()
                    _worker._sys_gpu_cached = _read_gpu_temp(wmi_conns)
                d['gpu_temp'] = getattr(_worker, '_sys_gpu_cached', None)
                
                vm = psutil.virtual_memory()
                d['ram_pct'] = vm.percent
                gb = 1024 ** 3
                d['ram_used'] = vm.used / gb
                d['ram_tot'] = vm.total / gb
                
                if time.time() - getattr(hud, '_last_disk_t', 0) > 60:
                    try:
                        du = psutil.disk_usage('C:\\')
                        d['dsk_pct'] = du.percent
                        d['dsk_used'] = du.used / gb
                        d['dsk_tot'] = du.total / gb
                    except: pass
                    hud._last_disk_t = time.time()
                
                bat = psutil.sensors_battery()
                if bat:
                    d['bat_pct'] = bat.percent
                    d['bat_plug'] = bat.power_plugged
                    
                d['uptime'] = _uptime()
                
                _worker._ping_cached = getattr(_worker, '_ping_cached', 0)
                if time.time() - getattr(_worker, '_ping_t', 0) > 2.0:
                    _worker._ping_t = time.time()
                    def _ping_job():
                        try:
                            cmd = ['ping', '-n', '1', '-w', '1000', 'google.com']
                            out = subprocess.check_output(cmd, creationflags=0x08000000).decode('cp866', errors='ignore')
                            if 'ms' in out.lower():
                                import re
                                ms = re.findall(r'=(\d+)ms', out.lower()) or re.findall(r'[\s=<](\d+)ms', out.lower())
                                if ms: _worker._ping_cached = int(ms[-1])
                        except: pass
                    threading.Thread(target=_ping_job, daemon=True).start()
                d['latency'] = _worker._ping_cached
                
            except Exception as e:
                _log_monitor_msg(f"start_sys_thread loop error: {e}")
                
            with hud._sys_lock:
                hud._sys_data.update(d)
                
            hud.root.after(0, lambda: update_sys_widgets(hud))
            time.sleep(3.0 if _LOW_PERF_MODE else 2.0)
            
    threading.Thread(target=_worker, daemon=True).start()

def update_sys_widgets(hud) -> None:
    # Live "does the mic actually hear me" readout — independent of the
    # hud._sys_data dict below (early-returns if empty), and read straight
    # from core.system.state.app_state rather than through that dict since
    # the engine's audio loop already writes it there every frame; this is
    # just the periodic UI-thread read side of that same safe hand-off.
    try:
        lbl = getattr(hud, '_mic_activity_lbl', None)
        if lbl is not None and lbl.winfo_exists():
            from core.system.state import app_state
            last_ts = app_state.last_speech_ts
            if last_ts <= 0:
                lbl.configure(text=i18n.tr('hud.mic_activity_none'), fg=_DIM)
            else:
                elapsed = time.time() - last_ts
                if elapsed < 2.0:
                    lbl.configure(text=i18n.tr('hud.mic_activity_hearing'), fg=_GREEN)
                else:
                    secs = int(elapsed)
                    unit = i18n.tr('hud.mic_activity_ago')
                    col = _AMBER if elapsed < 120 else _RED
                    lbl.configure(text=f'● {secs} {unit}', fg=col)
    except Exception: pass

    with hud._sys_lock:
        d = dict(hud._sys_data)
    if not d: return

    def _set(bar, lbl, pct, text, col=None):
        try:
            bar.set(min(pct / 100.0, 1.0))
            lbl.configure(text=text)
            if col:
                bar.configure(progress_color=col, fg_color=_blend(col, 0.15))
                lbl.configure(text_color=col)
        except: pass

    # --- UPDATE TOP STRIP (Sun Cycle) ---
    try:
        from datetime import datetime, timedelta
        now = datetime.now()
        now_m = now.hour * 60 + now.minute
        
        def _pt(s):
            try: hh, mm = map(int, s.split(':')); return hh * 60 + mm
            except: return None
            
        rise_m = _pt(getattr(hud, '_top_rise', ''))
        set_m = _pt(getattr(hud, '_top_set', ''))
        
        if rise_m is not None and set_m is not None:
            if rise_m <= now_m < set_m:
                hud._top_week = i18n.tr('hud.daylight_cycle')
                hud._top_day = i18n.tr('hud.until_sunset')
                total = set_m - rise_m
                passed = now_m - rise_m
                pct = (passed / total) if total > 0 else 0
            else:
                hud._top_week = i18n.tr('hud.night_cycle')
                hud._top_day = i18n.tr('hud.until_sunrise')
                if now_m >= set_m:
                    total = (1440 - set_m) + rise_m
                    passed = now_m - set_m
                else:
                    total = (1440 - set_m) + rise_m
                    passed = (1440 - set_m) + now_m
                pct = (passed / total) if total > 0 else 0
            
            hud._top_pct = max(0.0, min(1.0, pct))
            hud._top_pct_str = f"{int(hud._top_pct * 100)}%"
            
            hud._top_wday_str = i18n.tr(f'day.{now.weekday()}').upper()
            hud._top_yday_str = i18n.tr('hud.day_format').format(now.timetuple().tm_yday)
            hud._top_week_str = i18n.tr('hud.week_format').format(now.isocalendar()[1])
            
            renderer.draw_top_strip(hud)
    except: pass

    gput = d.get('gpu_temp')
    if gput is None and hasattr(hud, '_perf_meta'):
        try:
            cpu_t_str = hud._perf_meta.get('hw_temps', {}).get('cpu')
            if cpu_t_str and cpu_t_str != '—':
                gput = float(cpu_t_str.replace('°C', ''))
        except: pass

    if gput is not None:
        if not getattr(hud, '_gpu_bar_visible', False):
            try:
                for child in hud._gpu_container.winfo_children():
                    child.pack(fill='x', padx=16, pady=(4, 6))
                hud._gpu_bar_visible = True
            except: pass
        _set(hud._gpu_bar, hud._gpu_val, min(gput, 110), f'{gput:.0f}°C', _bar_color(gput * 0.9))
    elif getattr(hud, '_gpu_bar_visible', False):
        try:
            for child in hud._gpu_container.winfo_children():
                child.pack_forget()
            hud._gpu_bar_visible = False
        except: pass

    bat = d.get('bat_pct')
    if bat is not None:
        if not getattr(hud, '_bat_visible', False):
            try:
                hud._bat_section.pack(fill='x', after=hud._gpu_container)
                hud._bat_visible = True
            except: pass
        _set(hud._bat_bar, hud._bat_val, bat, f'{bat:.0f}%', _RED if bat < 20 else _AMBER if bat < 40 else _GREEN)
        try: hud._bat_lbl.configure(text=i18n.tr('hud.charging') if d.get('bat_plug') else i18n.tr('hud.battery_mode'))
        except: pass
    else:
        if getattr(hud, '_bat_visible', False):
            try:
                hud._bat_section.pack_forget()
                hud._bat_visible = False
            except: pass

    # --- UPDATE NETWORK LABELS ---
    try:
        nm = hud._perf_meta.get('net', {})
        if hasattr(hud, '_ssid_v'):
            hud._ssid_v.configure(text=nm.get('ssid', '—'))
        if hasattr(hud, '_ls_v'):
            hud._ls_v.configure(text=nm.get('link_speed', '—'))
    except: pass

    ram = d.get('ram_pct', 0)
    ru, rt = (d.get('ram_used', 0), d.get('ram_tot', 0))
    _set(hud._ram_bar, hud._ram_val, ram, f'{ram:.0f}%')
    try: hud._ram_det.configure(text=f'{ru:.1f} / {rt:.1f} ' + i18n.tr('hud.gb'))
    except: pass

    dsk = d.get('dsk_pct', 0)
    du2, dt = (d.get('dsk_used', 0), d.get('dsk_tot', 0))
    _set(hud._dsk_bar, hud._dsk_val, dsk, f'{dsk:.0f}%')
    try: hud._dsk_det.configure(text=f'{du2:.0f} ' + i18n.tr('hud.gb') + f' / {dt:.0f} ' + i18n.tr('hud.gb') if dt < 1000 else f'{du2 / 1000:.1f} / {dt / 1000:.1f} ' + i18n.tr('hud.tb'))
    except: pass
    
    try: hud._uptime_lbl.configure(text=i18n.tr('hud.uptime').format(d.get("uptime", "—")))
    except: pass

def start_perf_collector(hud) -> None:
    def _worker():
        _log_monitor_msg("PerfCollector: Worker started")
        try: pythoncom.CoInitialize()
        except: pass
        _wc = {}

        def _ps_query_local(query, ns='root/cimv2'):
            for tool in ['Get-CimInstance', 'Get-WmiObject']:
                try:
                    cmd = ['powershell', '-NoProfile', '-Command', f'{tool} -Namespace {ns} -ClassName {query} -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2']
                    raw = subprocess.check_output(cmd, creationflags=0x08000000, stderr=subprocess.DEVNULL, timeout=12)
                    out = raw.decode('utf-8', errors='ignore').strip()
                    if not out: continue
                    start = out.find('{')
                    if start == -1 or (out.find('[') != -1 and out.find('[') < start): start = out.find('[')
                    if start != -1: return json.loads(out[start:])
                except: continue
            return None

        # Статика
        _hw = {'cpu': '...', 'gpu': '...'}
        _gpu_meta = {'name': 'Intel / AMD Graphics', 'vram_total': 0.0, 'driver': '—', 'type': 'iGPU'}
        _ram_static = {'speed': 0, 'slots_used': 0, 'slots_total': 0, 'form': '—', 'installed_mb': 0}
        _cpu_static = {'l1': 0, 'l2': 0, 'l3': 0, 'virt': False, 'sockets': 1}
        _disk_static = {'total': '—', 'type': 'SSD', 'is_sys': True, 'is_page': True}
        _wifi_static = {'ssid': '—', 'adapter': '—', 'link_speed': '—'}
        
        _nvml_handle = None
        try:
            import pynvml as _pynvml
            _pynvml.nvmlInit()
            _nvml_handle = _pynvml.nvmlDeviceGetHandleByIndex(0)
        except: _pynvml = None

        def _init_static_hw():
            nonlocal _gpu_meta, _ram_static, _cpu_static, _hw, _disk_static, _wifi_static
            # 1. GPU static
            try:
                gpu_data = _ps_query_local('Win32_VideoController')
                if isinstance(gpu_data, list): gpu_data = gpu_data[0]
                if gpu_data and 'Name' in gpu_data:
                    _gpu_meta['name'] = gpu_data['Name']
                    _gpu_meta['driver'] = gpu_data.get('DriverVersion', '—')
                    _hw['gpu'] = gpu_data['Name']
                    if 'AdapterRAM' in gpu_data and gpu_data['AdapterRAM']:
                        _gpu_meta['vram_total'] = abs(float(gpu_data['AdapterRAM'])) / (1024**3)
                if any(x in _gpu_meta['name'].lower() for x in ['nvidia', 'geforce', 'rtx', 'gtx', 'radeon pro']): _gpu_meta['type'] = 'dGPU'
            except: pass

            # 2. CPU static
            try:
                cpu_data = _ps_query_local('Win32_Processor')
                if isinstance(cpu_data, list): cpu_data = cpu_data[0]
                if cpu_data and 'Name' in cpu_data:
                    _hw['cpu'] = cpu_data['Name']
                    _cpu_static['l2'] = int(cpu_data.get('L2CacheSize', 0) or 0)
                    _cpu_static['l3'] = int(cpu_data.get('L3CacheSize', 0) or 0)
                    _cpu_static['sockets'] = int(cpu_data.get('NumberOfSockets', 1) or 1)
            except: pass

            # 3. RAM static
            try:
                ram_data = _ps_query_local("Win32_PhysicalMemory")
                if ram_data:
                    sticks = ram_data if isinstance(ram_data, list) else [ram_data]
                    _ram_static['slots_used'] = len(sticks)
                    _ram_static['speed'] = max(int(orig_s.get('Speed', 0) or 0) for orig_s in sticks)
                    ff = int(sticks[0].get('FormFactor', 0) or 0)
                    _ram_static['form'] = {8:'DIMM', 12:'SODIMM', 24:'DDR4'}.get(ff, 'DIMM' if ff else '—')
                    _ram_static['installed_mb'] = sum(int(orig_s.get('Capacity', 0) or 0) for orig_s in sticks) // (1024**2)
            except: pass

            # 4. Network/Disk static
            try:
                _disk_static['total'] = f"{psutil.disk_usage('C:\\').total / (1024**3):.0f} ГБ"
                na = _ps_query_local("MSFT_NetAdapter", "root/StandardCimv2")
                if na:
                    items = na if isinstance(na, list) else [na]
                    w_item = next((x for x in items if 'WI-FI' in str(x.get('InterfaceDescription', '')).upper() or x.get('MediaType') == 71), None)
                    if w_item:
                        _wifi_static['adapter'] = w_item.get('InterfaceDescription', 'WLAN')
            except: pass

        threading.Thread(target=_init_static_hw, daemon=True, name='HW-Static-Init').start()

        def _read_adv_memory_info():
            try:
                import ctypes as _ct
                from ctypes import Structure as _Struct, c_size_t as _csz, wintypes as _wt
                class _PERF_INFO(_Struct):
                    _fields_ = [('cb', _wt.DWORD), ('CommitTotal', _csz), ('CommitLimit', _csz), ('CommitPeak', _csz), ('PhysicalTotal', _csz), ('PhysicalAvailable', _csz), ('SystemCache', _csz), ('KernelTotal', _csz), ('KernelPaged', _csz), ('KernelNonpaged', _csz), ('PageSize', _csz), ('HandleCount', _wt.DWORD), ('ProcessCount', _wt.DWORD), ('ThreadCount', _wt.DWORD)]
                pi = _PERF_INFO(); pi.cb = _ct.sizeof(_PERF_INFO)
                if _ct.windll.psapi.GetPerformanceInfo(_ct.byref(pi), pi.cb):
                    ps = pi.PageSize
                    return {'committed_mb': (pi.CommitTotal * ps) // (1024**2), 'cached_mb': (pi.SystemCache * ps) // (1024**2), 'paged_mb': (pi.KernelPaged * ps) // (1024**2), 'nonpaged_mb': (pi.KernelNonpaged * ps) // (1024**2), 'physical_total_mb': (pi.PhysicalTotal * ps) // (1024**2)}
            except: pass
            return {'committed_mb': 0, 'cached_mb': 0, 'paged_mb': 0, 'nonpaged_mb': 0, 'physical_total_mb': 0}

        try:
            cpu_const = {'phys_cores': psutil.cpu_count(logical=False), 'log_cores': psutil.cpu_count(logical=True), 'max_freq': f"{psutil.cpu_freq().max/1000:.2f} ГГц" if psutil.cpu_freq() else "—"}
        except: cpu_const = {'phys_cores': 0, 'log_cores': 0, 'max_freq': "—"}
        
        class DummyIO: read_bytes = 0; write_bytes = 0; bytes_recv = 0; bytes_sent = 0
        _t_prev = time.time()
        _gpu_ema = 0.0
        
        while True:
            t0 = time.time()
            ct = None 
            try:
                # Базовый чистый шаблон (чтобы никогда не было KeyError в perf_monitor)
                _pm = {
                    'uptime': _uptime(), 'hw': _hw, 'hw_temps': {'cpu': '—', 'gpu': '—'},
                    'cpu': {**cpu_const, 'current_freq': '—', 'procs': 0, 'l1': '—', 'l2': '—', 'l3': '—', 'virt': '—', 'sockets': '1'},
                    'ram': {'total': '—', 'avail': '—', 'cached': '—', 'used': '—', 'paged': '—', 'nonpaged': '—', 'speed': '—', 'slots': '—', 'form': '—', 'hardware_reserved': '—', 'committed': '—'},
                    'gpu': {**_gpu_meta, 'mem_used': '—', 'mem_load': '0%', 'temp': '—', 'clock': '—', 'pwr': '—', 'shared_mem': '—'},
                    'disk': {**_disk_static, 'active_time': '0%', 'latency': '0 мс', 'read_speed': '0 КБ/с', 'write_speed': '0 КБ/с'},
                    'net': {**_wifi_static, 'dn_speed': '0 КБ/с', 'up_speed': '0 КБ/с', 'ipv4': '—', 'ipv6': '—', 'ssid': '—', 'link_speed': '—'}
                }

                dt = time.time() - _t_prev
                if dt <= 0: dt = 0.1

                # Heavy per-field detail below only feeds the optional Perf Monitor
                # dialog (charts/tables) - skip computing it while that window is closed.
                # hw_temps.cpu / net.ssid / net.link_speed are the only fields the
                # always-visible HUD widgets read, those stay computed unconditionally below.
                _dlg = getattr(hud, '_perf_dialog_open', False)
                vm = psutil.virtual_memory()

                if _dlg:
                    # --- 1. RAM ---
                    adv_mem = _read_adv_memory_info()
                    h_res = max(0, _ram_static['installed_mb'] - adv_mem['physical_total_mb'])
                    _pm['ram'].update({'total': f"{vm.total/(1024**3):.1f} ГБ", 'avail': f"{vm.available/(1024**3):.1f} ГБ", 'cached': f"{adv_mem['cached_mb']/1024:.1f} ГБ", 'used': f"{vm.used/(1024**3):.1f} ГБ", 'paged': f"{adv_mem['paged_mb']:.0f} МБ", 'nonpaged': f"{adv_mem['nonpaged_mb']:.0f} МБ", 'speed': f"{_ram_static['speed']} МГц" if _ram_static['speed'] else "—", 'slots': f"{_ram_static['slots_used']} из {_ram_static['slots_total']}" if _ram_static['slots_total'] else "Впаяна", 'form': _ram_static['form'], 'hardware_reserved': f"{h_res} МБ", 'committed': f"{adv_mem['committed_mb']/1024:.1f} ГБ"})

                    # --- 2. DISK IO (СКОРОСТЬ И АКТИВНОСТЬ) ---
                    d_io = psutil.disk_io_counters() or DummyIO()
                    d_r_sec = (d_io.read_bytes - getattr(_worker, '_last_d_r', 0)) / dt if hasattr(_worker, '_last_d_r') else 0
                    d_w_sec = (d_io.write_bytes - getattr(_worker, '_last_d_w', 0)) / dt if hasattr(_worker, '_last_d_w') else 0
                    _worker._last_d_r, _worker._last_d_w = d_io.read_bytes, d_io.write_bytes

                    _disk_active = getattr(_worker, '_disk_active_cached', 0)
                    _disk_latency = getattr(_worker, '_disk_latency_cached', 0.0)
                    if time.time() - getattr(_worker, '_disk_ps_t', 0) > 12.0:
                        try:
                            dp = _ps_query_local("Win32_PerfFormattedData_PerfDisk_PhysicalDisk")
                            if dp:
                                d_list = dp if isinstance(dp, list) else [dp]
                                d_item = next((x for x in d_list if x.get('Name') == '_Total'), d_list[0])
                                _disk_active = int(d_item.get('PercentDiskTime', 0))
                                _disk_latency = float(d_item.get('AvgDisksecPerTransfer', 0)) * 1000
                                _worker._disk_active_cached = _disk_active
                                _worker._disk_latency_cached = _disk_latency
                        except: pass
                        _worker._disk_ps_t = time.time()

                    _pm['disk'].update({'active_time': f"{_disk_active}%", 'latency': f"{_disk_latency:.1f} мс", 'read_speed': _fmt_speed(d_r_sec), 'write_speed': _fmt_speed(d_w_sec)})

                    # --- 3. NETWORK IO (ЗАГРУЗКА И ОТДАЧА) ---
                    n_io = psutil.net_io_counters() or DummyIO()
                    n_r_sec = (n_io.bytes_recv - getattr(_worker, '_last_n_r', 0)) / dt if hasattr(_worker, '_last_n_r') else 0
                    n_s_sec = (n_io.bytes_sent - getattr(_worker, '_last_n_s', 0)) / dt if hasattr(_worker, '_last_n_s') else 0
                    _worker._last_n_r, _worker._last_n_s = n_io.bytes_recv, n_io.bytes_sent

                    _pm['net']['dn_speed'] = _fmt_speed(n_r_sec)
                    _pm['net']['up_speed'] = _fmt_speed(n_s_sec)
                else:
                    n_r_sec = 0

                # --- 4. CPU + Temp ---
                try:
                    # net_addrs_cached feeds the always-visible SSID/link-speed widgets below,
                    # so it's refreshed regardless of the dialog; procs/cpu_freq are dialog-only.
                    if time.time() - getattr(_worker, '_slow_t', 0) > 10.0:
                        _worker._slow_t = time.time()
                        _worker._net_addrs_cached = psutil.net_if_addrs()
                        if _dlg:
                            _worker._procs_cached = len(psutil.pids())
                            _worker._cpu_freq_cached = psutil.cpu_freq()

                    if _dlg:
                        _cpu_freq = getattr(_worker, '_cpu_freq_cached', None)
                        _pm['cpu'].update({'current_freq': f"{_cpu_freq.current/1000:.2f} ГГц" if _cpu_freq else "—", 'procs': getattr(_worker, '_procs_cached', 0), 'l1': f"{_cpu_static['l1']} КБ", 'l2': f"{_cpu_static['l2']} КБ", 'l3': f"{_cpu_static['l3']} КБ", 'virt': "ВКЛ" if _cpu_static['virt'] else "ВЫКЛ", 'sockets': str(_cpu_static['sockets'])})

                    try:
                        if 'ohm' in _wc:
                            for s in _wc['ohm'].Sensor():
                                if s.SensorType == 'Temperature' and 'CPU' in s.Name: ct = float(s.Value); break
                        elif time.time() - getattr(_worker, '_ct_t', 0) > 10.0:
                            _worker._ct_t = time.time()
                            try:
                                cmd_t = ['powershell', '-NoProfile', '-Command', "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace 'root/wmi' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentTemperature"]
                                raw_t = subprocess.check_output(cmd_t, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                                if raw_t: ct = (float(raw_t) - 2732) / 10.0
                            except: pass
                            if ct is None:
                                try:
                                    cmd_t2 = ['powershell', '-NoProfile', '-Command', "Get-WmiObject -Query 'SELECT Temperature FROM Win32_PerfFormattedData_Counters_ThermalZoneInformation' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Temperature"]
                                    raw_t2 = subprocess.check_output(cmd_t2, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                                    if raw_t2:
                                        val = float(raw_t2)
                                        ct = val if val < 150 else (val - 273.15)
                                except: pass
                            _worker._ct_cached = ct
                        else:
                            ct = getattr(_worker, '_ct_cached', None)
                    except: pass
                    if ct is not None:
                        _pm['cpu']['temp'] = f"{ct:.0f}°C"
                        _pm['hw_temps']['cpu'] = f"{ct:.0f}°C"
                except: pass

                # --- 5. GPU (dialog-only: HUD widgets never show GPU util/mem/power/clock) ---
                try:
                  if _dlg:
                    v_tot = max(_gpu_meta.get('vram_total', 1.0), 0.1)
                    vram_used_gb, gu = 0.0, 0.0
                    pwr = "—"

                    if _gpu_meta.get('type') == 'dGPU' and _nvml_handle:
                        try:
                            _nvml_mem = _pynvml.nvmlDeviceGetMemoryInfo(_nvml_handle)
                            vram_used_gb = _nvml_mem.used / (1024 ** 3)
                            gu = float(_pynvml.nvmlDeviceGetUtilizationRates(_nvml_handle).gpu)
                            pwr = f"{_pynvml.nvmlDeviceGetPowerUsage(_nvml_handle) / 1000.0:.0f} Вт"
                        except: pass
                    else:
                        if time.time() - getattr(_worker, '_igpu_t', 0) > 8.0:
                            _worker._igpu_t = time.time()
                            try:
                                cmd_util = ['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | Where-Object { $_.Name -like '*3D*' } | ConvertTo-Json"]
                                raw_util = subprocess.check_output(cmd_util, creationflags=0x08000000).decode('utf-8', errors='ignore')
                                if raw_util:
                                    data_u = json.loads(raw_util)
                                    items_u = data_u if isinstance(data_u, list) else [data_u]
                                    if items_u: gu = max((float(x.get('UtilizationPercentage', 0)) for x in items_u), default=0.0)

                                cmd_mem = ['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory | ConvertTo-Json"]
                                raw_mem = subprocess.check_output(cmd_mem, creationflags=0x08000000).decode('utf-8')
                                if raw_mem:
                                    data_m = json.loads(raw_mem)
                                    items_m = data_m if isinstance(data_m, list) else [data_m]
                                    vram_used_gb = sum(int(x.get('DedicatedUsage', 0)) + int(x.get('SharedUsage', 0)) for x in items_m) / (1024**3)

                                if _gpu_meta.get('type') == 'iGPU' and 'vm' in locals():
                                    v_tot = vm.total / (1024**3) * 0.5
                                    _gpu_meta['vram_total'] = v_tot
                                    pwr = "Shared"
                            except: pass
                            _worker._igpu_cached = (gu, vram_used_gb, v_tot, pwr)
                        else:
                            gu, vram_used_gb, v_tot, pwr = getattr(_worker, '_igpu_cached', (gu, vram_used_gb, v_tot, pwr))
                    
                    _gpu_ema = 0.4 * gu + 0.6 * _gpu_ema
                    gt = getattr(_worker, '_gt_cached', None)
                    if gt is None and _gpu_meta.get('type') == 'iGPU': gt = ct
                    
                    gc = getattr(_worker, '_gc_cached', "—")
                    if _gpu_meta.get('type') == 'iGPU' and time.time() - getattr(_worker, '_gc_t', 0) > 10.0:
                        _worker._gc_t = time.time()
                        try:
                            cmd_gc = ['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentClockSpeed"]
                            raw_gc = subprocess.check_output(cmd_gc, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                            if not raw_gc:
                                cmd_gc = ['powershell', '-NoProfile', '-Command', "Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Select-Object -ExpandProperty MaxClockSpeed"]
                                raw_gc = subprocess.check_output(cmd_gc, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                            if raw_gc: gc = f"{raw_gc} МГц"
                        except: pass
                        _worker._gc_cached = gc

                    _pm['gpu'].update({'mem_used': f"{max(vram_used_gb, 0.01):.1f} / {v_tot:.1f} ГБ", 'mem_load': f"{(vram_used_gb / v_tot * 100):.1f}%", 'temp': f"{gt:.0f}°C" if gt is not None else "—", 'clock': gc, 'pwr': pwr, 'shared_mem': f"{(vm.used*0.15)/(1024**3):.1f} / {(vm.total*0.5)/(1024**3):.1f} ГБ"})
                except: pass

                # --- 6. NETWORK IPs ---
                try:
                    addrs = getattr(_worker, '_net_addrs_cached', {})
                    found_ip = False
                    for iface, props in addrs.items():
                        if any(x in iface.lower() for x in ['hamachi', 'vbox', 'virtual', 'vmware', 'vpn']): continue
                        
                        for a in props:
                            if a.family == socket.AF_INET:
                                ip = a.address
                                if not ip.startswith('127.') and not ip.startswith('169.254'):
                                    _pm['net']['ipv4'] = ip
                                    _pm['net']['ipv6'] = next((addr.address for addr in props if addr.family == socket.AF_INET6), '—')
                                    _pm['net']['adapter'] = iface
                                    
                                    if not found_ip:
                                        if time.time() - getattr(_worker, '_wifi_t', 0) > 20.0:
                                            _worker._wifi_t = time.time()
                                            try:
                                                # Используем PowerShell (т.к. netsh на системе пользователя не работает)
                                                cmd_ssid = ['powershell', '-NoProfile', '-Command', "Get-NetConnectionProfile -InterfaceAlias 'WLAN' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"]
                                                raw_ssid = subprocess.check_output(cmd_ssid, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                                                if raw_ssid: _pm['net']['ssid'] = raw_ssid.splitlines()[0]

                                                cmd_ls = ['powershell', '-NoProfile', '-Command', "Get-NetAdapter -InterfaceAlias 'WLAN' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty LinkSpeed"]
                                                raw_ls = subprocess.check_output(cmd_ls, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                                                if raw_ls: _pm['net']['link_speed'] = raw_ls.splitlines()[0]

                                                if _pm['net']['ssid'] == '—':
                                                    cmd_ps = ['powershell', '-NoProfile', '-Command', "Get-NetConnectionProfile -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name"]
                                                    raw_ps = subprocess.check_output(cmd_ps, creationflags=0x08000000, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                                                    if raw_ps: _pm['net']['ssid'] = raw_ps.splitlines()[0]
                                            except: pass
                                            _worker._wifi_cached = (_pm['net']['ssid'], _pm['net']['link_speed'])
                                        else:
                                            _wc_ssid, _wc_ls = getattr(_worker, '_wifi_cached', (_pm['net']['ssid'], _pm['net']['link_speed']))
                                            _pm['net']['ssid'], _pm['net']['link_speed'] = _wc_ssid, _wc_ls
                                    found_ip = True
                                    break
                        if found_ip: break
                except: pass

                # --- 7. HISTORY ARRAYS (dialog-only: charts in Perf Monitor) ---
                if _dlg:
                    h = hud._perf_history
                    h.setdefault('cpu', []).append(psutil.cpu_percent())
                    h.setdefault('ram', []).append(vm.percent)
                    h.setdefault('gpu_util', []).append(_gpu_ema)
                    h.setdefault('latency', []).append(hud._sys_data.get('latency', 0))
                    h.setdefault('net_dn', []).append(n_r_sec / 1024)

                    dsk_arr = h.setdefault('dsk_util', [])
                    if len(dsk_arr) == 0 or time.time() - getattr(_worker, '_dsk_util_h', 0) > 3.0:
                        try: dsk_arr.append(psutil.disk_usage('C:\\').percent)
                        except: dsk_arr.append(0.0)
                        _worker._dsk_util_h = time.time()
                    else:
                        dsk_arr.append(dsk_arr[-1])

                hud._perf_meta = _pm
                _t_prev = time.time()
            except Exception as e: _log_monitor_msg(f"Loop error: {e}")
            elapsed = time.time() - t0
            time.sleep(max(0.1, (4.0 if _LOW_PERF_MODE else 2.0) - elapsed))
            
    threading.Thread(target=_worker, daemon=True, name='PerfCollector').start()

def clock_tick(hud) -> None:
    n = datetime.now()
    t_str = n.strftime('%H:%M:%S'); d_str = n.strftime('%d ') + i18n.tr(f'mon.{n.month}').upper() + n.strftime(' %Y')
    try: hud._clock_lbl.configure(text=t_str); hud._date_lbl.configure(text=d_str)
    except: pass
    try:
        w = hud.root.winfo_width()
        if w < 900:
            hud._hdr_time.configure(text=f'{t_str}  ')
            if hasattr(hud, '_hdr_os_lbl'): hud._hdr_os_lbl.configure(text=f'  OS v{APP_VERSION}')
        else:
            hud._hdr_time.configure(text=f'{d_str}  {t_str}  ')
            if hasattr(hud, '_hdr_os_lbl'): hud._hdr_os_lbl.configure(text=f'  JARVIS OS  v{APP_VERSION}')
    except: pass
    hud.root.after(1000, lambda: clock_tick(hud))

def net_tick(hud) -> None:
    try:
        now = psutil.net_io_counters(); dt = time.time() - hud._net_t
        if dt > 0:
            hud._up_v.configure(text=_fmt_speed((now.bytes_sent - hud._net_prev.bytes_sent) / dt))
            hud._dn_v.configure(text=_fmt_speed((now.bytes_recv - hud._net_prev.bytes_recv) / dt))
        hud._net_prev = now; hud._net_t = time.time()
    except: pass
    hud.root.after(1000, lambda: net_tick(hud))

def refresh_ip(hud) -> None:
    def _do():
        try: ip = socket.gethostbyname(socket.gethostname())
        except: ip = '—'
        try: hud.root.after(0, lambda: hud._ip_v.configure(text=ip))
        except: pass
    threading.Thread(target=_do, daemon=True).start()
    hud.root.after(30000, refresh_ip, hud)

def state_tick(hud) -> None:
    _state_interval = 300 if _LOW_PERF_MODE else 150
    if not hasattr(hud, '_bot_canvas') or not hud._bot_items:
        hud.root.after(_state_interval, lambda: state_tick(hud)); return
    mode = STATE.mode
    if getattr(hud, '_last_state_mode', None) == mode:
        hud.root.after(_state_interval, lambda: state_tick(hud)); return
    hud._last_state_mode = mode
    for item in hud._bot_items:
        state, is_active, col = item['state'], item['state'] == mode, item['col']
        bc, tc, dot_c, thick, bg_col = (col if is_active else _blend(col, 0.3)), (_WHITE if is_active else _DIM), (col if is_active else _DIM), (2 if is_active else 1), _blend(col, 0.1)
        ids = item['ids']
        try:
            hud._bot_canvas.itemconfig(ids[0], fill=bg_col if is_active else '')
            for i in range(1, 5): hud._bot_canvas.itemconfig(ids[i], fill=bc if is_active else '', width=thick)
            hud._bot_canvas.itemconfig(ids[5], fill=dot_c); hud._bot_canvas.itemconfig(ids[6], fill=tc)
        except: pass
    hud.root.after(_state_interval, lambda: state_tick(hud))