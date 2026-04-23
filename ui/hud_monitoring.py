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
    except:
        pass

_LOW_PERF_MODE = (_ps.cpu_count(logical=False) or 4) <= 2
def start_sys_thread(hud) -> None:
    def _worker() -> None:
        _log_monitor_msg("start_sys_thread: Worker started")
        try:
            pythoncom.CoInitialize()
            _log_monitor_msg("start_sys_thread: CoInitialize OK")
        except Exception as e:
            _log_monitor_msg(f"start_sys_thread: CoInitialize FAILED: {e}")
        wmi_conns = {}
        try:
            import wmi as _wm
            try:
                wmi_conns['ohm'] = _wm.WMI(namespace='root/OpenHardwareMonitor')
            except Exception:
                pass
            try:
                wmi_conns['cim'] = _wm.WMI()
            except Exception:
                pass
            try:
                wmi_conns['wmi'] = _wm.WMI(namespace='root/wmi')
            except Exception:
                pass
        except Exception:
            pass
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
                    du = psutil.disk_usage('C:\\')
                    d['dsk_pct'] = du.percent
                    d['dsk_used'] = du.used / gb
                    d['dsk_tot'] = du.total / gb
                    hud._last_disk_t = time.time()
                bat = psutil.sensors_battery()
                if bat:
                    d['bat_pct'] = bat.percent
                    d['bat_plug'] = bat.power_plugged
                d['uptime'] = _uptime()
            except Exception as e:
                _log_monitor_msg(f"start_sys_thread loop error: {e}")
            with hud._sys_lock:
                hud._sys_data.update(d)
                _log_monitor_msg(f"start_sys_thread: Data updated: {list(d.keys())}")
            hud.root.after(0, lambda: update_sys_widgets(hud))
            time.sleep(3.0 if _LOW_PERF_MODE else 2.0)
    threading.Thread(target=_worker, daemon=True).start()
def update_sys_widgets(hud) -> None:
    with hud._sys_lock:
        d = dict(hud._sys_data)
    if not d:
        return
    def _set(bar, lbl, pct, text, col=None):
        try:
            bar.set(min(pct / 100.0, 1.0))
            lbl.configure(text=text)
            if col:
                bar.configure(progress_color=col, fg_color=_blend(col, 0.15))
                lbl.configure(text_color=col)
        except Exception:
            pass
    gput = d.get('gpu_temp')
    if gput is not None:
        if not hud._gpu_bar_visible:
            for child in hud._gpu_container.winfo_children():
                child.pack(fill='x', padx=16, pady=(4, 6))
            hud._gpu_bar_visible = True
        _set(hud._gpu_bar, hud._gpu_val, min(gput, 110), f'{gput:.0f}°C', _bar_color(gput * 0.9))
    elif hud._gpu_bar_visible:
        for child in hud._gpu_container.winfo_children():
            child.pack_forget()
        hud._gpu_bar_visible = False
    bat = d.get('bat_pct')
    if bat is not None:
        _set(hud._bat_bar, hud._bat_val, bat, f'{bat:.0f}%', _RED if bat < 20 else _AMBER if bat < 40 else _GREEN)
        hud._bat_lbl.configure(text='⚡ ЗАРЯЖАЕТСЯ' if d.get('bat_plug') else '🔋 РАБОТА ОТ БАТАРЕИ')
    else:
        hud._bat_val.configure(text='N/A')
        hud._bat_lbl.configure(text='НАСТОЛЬНЫЙ КОМПЬЮТЕР / ПЕРЕМЕННЫЙ ТОК')
    ram = d.get('ram_pct', 0)
    ru, rt = (d.get('ram_used', 0), d.get('ram_tot', 0))
    _set(hud._ram_bar, hud._ram_val, ram, f'{ram:.0f}%')
    hud._ram_det.configure(text=f'{ru:.1f} / {rt:.1f} ГБ')
    dsk = d.get('dsk_pct', 0)
    du2, dt = (d.get('dsk_used', 0), d.get('dsk_tot', 0))
    _set(hud._dsk_bar, hud._dsk_val, dsk, f'{dsk:.0f}%')
    hud._dsk_det.configure(text=f'{du2:.0f} ГБ / {dt:.0f} ГБ' if dt < 1000 else f'{du2 / 1000:.1f} / {dt / 1000:.1f} ТБ')
    hud._uptime_lbl.configure(text=f'ВРЕМЯ РАБОТЫ: {d.get("uptime", "—")}')
def start_perf_collector(hud) -> None:
    def _worker():
        _log_monitor_msg("PerfCollector: Worker started")
        try:
            pythoncom.CoInitialize()
        except: pass
        _wc = {}
        def _ps_query_local(query, ns='root/cimv2'):
            import subprocess
            for tool in ['Get-CimInstance', 'Get-WmiObject']:
                try:
                    cmd = ['powershell', '-NoProfile', '-Command', f'{tool} -Namespace {ns} -ClassName {query} -ErrorAction SilentlyContinue | ConvertTo-Json -Depth 2']
                    raw = subprocess.check_output(cmd, creationflags=0x08000000, stderr=subprocess.DEVNULL, timeout=12)
                    out = raw.decode('utf-8', errors='ignore').strip()
                    if not out: continue
                    start = out.find('{')
                    if start == -1 or (out.find('[') != -1 and out.find('[') < start):
                        start = out.find('[')
                    if start != -1:
                        import json
                        return json.loads(out[start:])
                except: continue
            return None
        _hw = {'cpu': 'N/A', 'gpu': 'N/A'}
        _gpu_meta = {'name': 'Н/Д', 'vram_total': 0, 'driver': 'Н/Д', 'driver_date': 'Н/Д', 'location': 'Н/Д', 'type': 'интегрированный'}
        _ram_static = {'speed': 0, 'slots_used': 0, 'slots_total': 0, 'form': 'N/A', 'installed_mb': 0}
        _cpu_static = {'l1': 0, 'l2': 0, 'l3': 0, 'virt': False, 'sockets': 1}
        _disk_static = {'total': 'Н/Д', 'type': 'SSD', 'is_sys': True, 'is_page': True}
        _wifi_static = {'ssid': 'Н/Д', 'adapter': 'Intel(R) Wi-Fi 6 AX201', 'link_speed': 'Н/Д'}
        _nvml_handle = None
        try:
            import pynvml as _pynvml
            _pynvml.nvmlInit()
            _nvml_handle = _pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            _pynvml = None
        def _init_static_hw():
            import subprocess
            nonlocal _gpu_meta, _ram_static, _cpu_static, _hw
            try:
                out = subprocess.check_output(['nvidia-smi', '--query-gpu=gpu_name,memory.total,driver_version', '--format=csv,noheader,nounits'], creationflags=0x08000000, timeout=1).decode('utf-8').strip()
                if out:
                    parts = out.split(', ')
                    _gpu_meta = {'name': parts[0], 'vram_total': float(parts[1]) / 1024.0, 'driver': parts[2], 'type': 'nvidia'}
                    _hw['gpu'] = _gpu_meta['name']
            except: pass
            try:
                data = _ps_query_local("Win32_VideoController")
                if data:
                    gpus = data if isinstance(data, list) else [data]
                    best_g = None
                    for g in gpus:
                        name = str(g.get('Name', '') or g.get('Caption', ''))
                        if not name: continue
                        ram = abs(int(g.get('AdapterRAM', 0) or 0))
                        if any(x in name.lower() for x in ['virtual', 'iddcx', 'mirror', 'remote', 'basicsplay']):
                            if len(gpus) > 1: continue
                        if not best_g or ram > abs(int(best_g.get('AdapterRAM', 0) or 0)):
                            best_g = g
                    if best_g:
                        name = str(best_g.get('Name', '') or best_g.get('Caption', 'Н/Д'))
                        ram_bytes = abs(int(best_g.get('AdapterRAM', 0) or 0))
                        vram_gb = ram_bytes / (1024**3)
                        total_ram_gb = psutil.virtual_memory().total / (1024**3)
                        if any(x in name.lower() for x in ['intel', 'amd', 'graphics', 'xe']) or vram_gb < 1.1:
                            vram_gb = total_ram_gb * 0.5
                            _gpu_meta['type'] = 'интегрированный'
                        else:
                            _gpu_meta['type'] = 'дискретный'
                        _gpu_meta['name'] = name
                        _gpu_meta['vram_total'] = vram_gb
                        _gpu_meta['driver'] = str(best_g.get('DriverVersion', 'Н/Д'))
                        _hw['gpu'] = _gpu_meta['name']
                        try:
                            gcim = _ps_query_local("Win32_VideoController")
                            if gcim:
                                g_list = gcim if isinstance(gcim, list) else [gcim]
                                t_gpu = next((x for x in g_list if name in str(x.get('Name',''))), g_list[0])
                                dr_date = str(t_gpu.get('DriverDate', ''))
                                if 'Date(' in dr_date:
                                    import datetime
                                    ms = int(dr_date.split('(')[1].split(')')[0])
                                    _gpu_meta['driver_date'] = datetime.datetime.fromtimestamp(ms/1000.0).strftime('%d.%m.%Y')
                                if 'PCI\\' in str(t_gpu.get('PNPDeviceID', '')):
                                    _gpu_meta['location'] = "PCI bus 0, device 2, function 0"
                        except: pass
            except: pass
            try:
                ram_data = _ps_query_local("Win32_PhysicalMemory")
                if ram_data:
                    sticks = ram_data if isinstance(ram_data, list) else [ram_data]
                    _ram_static['slots_used'] = len(sticks)
                    _ram_static['speed'] = max(int(orig_s.get('Speed', 0) or 0) for orig_s in sticks)
                    ff = int(sticks[0].get('FormFactor', 0) or 0)
                    _ram_static['form'] = {8:'DIMM', 12:'SODIMM', 24:'DDR4'}.get(ff, 'DIMM' if ff else 'N/A')
                    _ram_static['installed_mb'] = sum(int(orig_s.get('Capacity', 0) or 0) for orig_s in sticks) // (1024**2)
                array_data = _ps_query_local("Win32_PhysicalMemoryArray")
                if array_data:
                    a = array_data[0] if isinstance(array_data, list) else array_data
                    _ram_static['slots_total'] = int(a.get('MemoryDevices', 0) or 0)
            except Exception as e:
                with open('gpu_error.log', 'a', encoding='utf-8') as f:
                    f.write(f"RAM Detection Error: {e}\n")
            try:
                cpu_ext = _ps_query_local("Win32_Processor")
                if cpu_ext:
                    c_list = cpu_ext if isinstance(cpu_ext, list) else [cpu_ext]
                    c = c_list[0]
                    _cpu_static['l2'] = int(c.get('L2CacheSize', 0) or 0)
                    _cpu_static['l3'] = int(c.get('L3CacheSize', 0) or 0)
                    v_on = c.get('VirtualizationFirmwareEnabled')
                    if v_on is None or v_on is False:
                        try:
                            hv = _ps_query_local("Win32_ComputerSystem")
                            if hv:
                                h_list = hv if isinstance(hv, list) else [hv]
                                v_on = bool(h_list[0].get('HypervisorPresent', False))
                        except: pass
                    _cpu_static['virt'] = bool(v_on)
                    _cpu_static['sockets'] = int(c.get('NumberOfSockets', 1) or 1)
                    _hw['cpu'] = str(c.get('Name', 'N/A')).strip()
                cm = _ps_query_local("Win32_CacheMemory")
                if cm:
                    c_list = cm if isinstance(cm, list) else [cm]
                    l1_total = sum(int(x.get('InstalledSize', 0) or 0) for x in c_list if int(x.get('Level', 0) or 0) == 3)
                    if l1_total > 0:
                        _cpu_static['l1'] = l1_total
                _disk_static['total'] = f"{psutil.disk_usage('C:\\').total / (1024**3):.0f} ГБ"
                try:
                    dd = _ps_query_local("Win32_DiskDrive")
                    if dd:
                        d = dd if isinstance(dd, dict) else dd[0]
                        _disk_static['type'] = "SSD (RAID)" if "RAID" in str(d).upper() else ("SSD (NVMe)" if "NVME" in str(d).upper() else "SSD")
                except: pass
                try:
                    pf = _ps_query_local("Win32_PageFileUsage")
                    _disk_static['is_page'] = bool(pf)
                except: pass
                try:
                    na = _ps_query_local("MSFT_NetAdapter", "root/StandardCimv2")
                    if na:
                        w_item = next((x for x in (na if isinstance(na, list) else [na]) if 'WI-FI' in str(x.get('InterfaceDescription', '')).upper()), None)
                        if w_item:
                            _wifi_static['adapter'] = w_item.get('InterfaceDescription', 'WLAN')
                            _wifi_static['link_speed'] = f"{int(w_item.get('LinkSpeed', 0))/1000000:.0f} Mbps"
                    cp = _ps_query_local("MSFT_NetConnectionProfile", "root/StandardCimv2")
                    if cp:
                        w_prof = next((x for x in (cp if isinstance(cp, list) else [cp]) if x.get('InterfaceAlias') == 'WLAN'), None)
                        if w_prof:
                            _wifi_static['ssid'] = w_prof.get('Name', 'Н/Д')
                except: pass
            except Exception as e:
                with open('gpu_error.log', 'a', encoding='utf-8') as f:
                    f.write(f"CPU Detection Error: {e}\n")
            try:
                import subprocess
                cmd_name = 'powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController | Sort-Object AdapterRAM -Descending | Select-Object -First 1).Name"'
                name = subprocess.check_output(cmd_name, creationflags=0x08000000, timeout=8).decode('utf-8', errors='ignore').strip()
                if name:
                    _gpu_meta['name'] = name
                    _gpu_meta['type'] = 'integrated'
                    _gpu_meta['vram_total'] = (psutil.virtual_memory().total / (1024**3)) * 0.5
                    _hw['gpu'] = name
                    cmd_drv = 'powershell -NoProfile -Command "(Get-CimInstance Win32_VideoController | Sort-Object AdapterRAM -Descending | Select-Object -First 1).DriverVersion"'
                    drv = subprocess.check_output(cmd_drv, creationflags=0x08000000, timeout=5).decode('utf-8', errors='ignore').strip()
                    if drv: _gpu_meta['driver'] = drv
            except: pass
        import threading as _hw_threading
        _hw_threading.Thread(target=_init_static_hw, daemon=True, name='HW-Static-Init').start()
        def _read_adv_memory_info():
            try:
                import ctypes as _ct
                from ctypes import Structure as _Struct, c_size_t as _csz, wintypes as _wt
                class _PERF_INFO(_Struct):
                    _fields_ = [
                        ('cb', _wt.DWORD), ('CommitTotal', _csz), ('CommitLimit', _csz),
                        ('CommitPeak', _csz), ('PhysicalTotal', _csz), ('PhysicalAvailable', _csz),
                        ('SystemCache', _csz), ('KernelTotal', _csz), ('KernelPaged', _csz),
                        ('KernelNonpaged', _csz), ('PageSize', _csz),
                        ('HandleCount', _wt.DWORD), ('ProcessCount', _wt.DWORD), ('ThreadCount', _wt.DWORD)
                    ]
                pi = _PERF_INFO()
                pi.cb = _ct.sizeof(_PERF_INFO)
                if _ct.windll.psapi.GetPerformanceInfo(_ct.byref(pi), pi.cb):
                    ps = pi.PageSize
                    return {
                        'cached_mb': (pi.SystemCache * ps) // (1024**2),
                        'paged_mb': (pi.KernelPaged * ps) // (1024**2),
                        'nonpaged_mb': (pi.KernelNonpaged * ps) // (1024**2),
                        'physical_total_mb': (pi.PhysicalTotal * ps) // (1024**2)
                    }
            except: pass
            return {'cached_mb': 0, 'paged_mb': 0, 'nonpaged_mb': 0, 'physical_total_mb': 0}
        cpu_info = {
            'phys_cores': psutil.cpu_count(logical=False),
            'log_cores': psutil.cpu_count(logical=True),
            'max_freq': f"{psutil.cpu_freq().max/1000:.2f} ГГц" if psutil.cpu_freq() else "Н/Д"
        }
        _disk_prev = psutil.disk_io_counters()
        _net_all_prev = psutil.net_io_counters(pernic=True)
        _t_prev = time.time()
        _gpu_ema = 0.0
        from .hud_utils import _read_temp, _fmt_speed
        import socket
        while True:
            t0 = time.time()
            try:
                vm = psutil.virtual_memory()
                d_io = psutil.disk_io_counters()
                dt = time.time() - _t_prev
                n_io_all = psutil.net_io_counters(pernic=True)
                wlan_io = n_io_all.get('WLAN') or n_io_all.get('Wi-Fi') or next(iter(n_io_all.values()))
                wlan_io_prev = _net_all_prev.get('WLAN') or _net_all_prev.get('Wi-Fi') or next(iter(_net_all_prev.values()))
                n_dn = (wlan_io.bytes_recv - wlan_io_prev.bytes_recv) / dt if dt > 0 else 0
                n_up = (wlan_io.bytes_sent - wlan_io_prev.bytes_sent) / dt if dt > 0 else 0
                _hw_interval = 10.0 if _LOW_PERF_MODE else 5.0
                _now_hw = time.time()
                if _now_hw - getattr(_worker, '_hw_t', 0) > _hw_interval:
                    _worker._hw_t = _now_hw
                    _worker._gt_cached = _read_gpu_temp(_wc)
                    _worker._gu_cached = _read_gpu_util(_wc)
                    _worker._ct_cached = _read_temp(_wc)
                gt = getattr(_worker, '_gt_cached', None)
                gu = getattr(_worker, '_gu_cached', None)
                ct = getattr(_worker, '_ct_cached', None)
                _gpu_ema = 0.4 * (gu if gu is not None else 0.0) + 0.6 * _gpu_ema if _gpu_ema > 0 else (gu if gu is not None else 0.0)
                h = hud._perf_history
                h['ram'].append(vm.percent)
                if len(h['dsk_util']) == 0 or time.time() - getattr(_worker, '_dsk_util_t', 0) > (5.0 if _LOW_PERF_MODE else 2.0):
                    h['dsk_util'].append(psutil.disk_usage('C:\\').percent)
                    _worker._dsk_util_t = time.time()
                elif h['dsk_util']:
                    h['dsk_util'].append(h['dsk_util'][-1])
                h['net_dn'].append(n_dn / 1024)
                h['gpu_util'].append(_gpu_ema)
                h['gpu_temp'].append(gt if gt is not None else 0.0)
                h['cpu_temp'].append(ct if ct is not None else 0.0)
                _disk_active = getattr(_worker, '_disk_active_cached', 0)
                _disk_latency = getattr(_worker, '_disk_latency_cached', 0)
                _disk_ps_interval = 12.0 if _LOW_PERF_MODE else 8.0
                if time.time() - getattr(_worker, '_disk_ps_t', 0) > _disk_ps_interval:
                    try:
                        dp = _ps_query_local("Win32_PerfFormattedData_PerfDisk_PhysicalDisk", "root/cimv2")
                        if dp:
                            d_list = dp if isinstance(dp, list) else [dp]
                            d_item = next((x for x in d_list if x.get('Name') == '_Total'), d_list[0])
                            _disk_active = int(d_item.get('PercentDiskTime', 0))
                            _disk_latency = float(d_item.get('AvgDisksecPerTransfer', 0)) * 1000
                            _worker._disk_active_cached = _disk_active
                            _worker._disk_latency_cached = _disk_latency
                    except: pass
                    _worker._disk_ps_t = time.time()
                d_r_sec = (d_io.read_bytes - _disk_prev.read_bytes) / dt if dt > 0 else 0
                d_w_sec = (d_io.write_bytes - _disk_prev.write_bytes) / dt if dt > 0 else 0
                vram_used_gb = 0
                if _gpu_meta['type'] == 'nvidia':
                    if _nvml_handle is not None:
                        try:
                            _nvml_mem = _pynvml.nvmlDeviceGetMemoryInfo(_nvml_handle)
                            vram_used_gb = _nvml_mem.used / (1024 ** 3)
                        except Exception:
                            pass
                    else:
                        if time.time() - getattr(_worker, '_nvsmi_t', 0) > 12.0:
                            try:
                                import subprocess
                                v_out = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'], creationflags=0x08000000, timeout=0.5).decode('utf-8').strip()
                                _worker._nvsmi_cached = float(v_out) / 1024.0
                                _worker._nvsmi_t = time.time()
                            except Exception:
                                pass
                        vram_used_gb = getattr(_worker, '_nvsmi_cached', 0.0)
                elif _gpu_meta['type'] == 'integrated':
                    try:
                        data = _ps_query_local("Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory")
                        if data:
                            items = data if isinstance(data, list) else [data]
                            ram_bytes = sum(int(item.get('SharedUsage', 0) or 0) + int(item.get('DedicatedUsage', 0) or 0) for item in items)
                            vram_used_gb = ram_bytes / (1024**3)
                    except: pass
                adv_mem = _read_adv_memory_info()
                h_res = max(0, _ram_static['installed_mb'] - adv_mem['physical_total_mb'])
                _slow_interval = 15.0 if _LOW_PERF_MODE else 10.0
                _now = time.time()
                if _now - getattr(_worker, '_slow_t', 0) > _slow_interval:
                    _worker._slow_t = _now
                    _worker._procs_cached = len(psutil.pids())
                    _worker._net_addrs_cached = psutil.net_if_addrs()
                    _worker._cpu_freq_cached = psutil.cpu_freq()
                _procs = getattr(_worker, '_procs_cached', 0)
                _net_addrs = getattr(_worker, '_net_addrs_cached', {})
                _cpu_freq = getattr(_worker, '_cpu_freq_cached', None)
                hud._perf_meta = {
                    'uptime': _uptime(),
                    'hw': _hw,
                    'cpu': {
                        **cpu_info,
                        'current_freq': f"{_cpu_freq.current/1000:.2f} ГГц" if _cpu_freq else "Н/Д",
                        'procs': _procs,
                        'l1': f"{_cpu_static['l1']} КБ",
                        'l2': f"{_cpu_static['l2']} КБ",
                        'l3': f"{_cpu_static['l3']} КБ",
                        'virt': "ВКЛ" if _cpu_static['virt'] else "ВЫКЛ",
                        'sockets': str(_cpu_static['sockets'])
                    },
                    'ram': {
                        'total': f"{vm.total/1024/1024/1024:.1f} ГБ",
                        'avail': f"{vm.available/1024/1024/1024:.1f} ГБ",
                        'cached': f"{adv_mem['cached_mb']/1024:.1f} ГБ",
                        'used': f"{vm.used/1024/1024/1024:.1f} ГБ",
                        'paged': f"{adv_mem['paged_mb']:.0f} МБ",
                        'nonpaged': f"{adv_mem['nonpaged_mb']:.0f} МБ",
                        'speed': f"{_ram_static['speed']} МГц",
                        'slots': f"{_ram_static['slots_used']} из {_ram_static['slots_total']}",
                        'form': _ram_static['form'],
                        'hardware_reserved': f"{h_res} МБ"
                    },
                    'gpu': {
                        **_gpu_meta,
                        'vram_used': f"{max(vram_used_gb, 0.01):.1f} / {_gpu_meta['vram_total']:.1f} ГБ",
                        'shared_mem': f"{(vm.used*0.2)/(1024**3):.1f} / {(vm.total*0.5)/(1024**3):.1f} ГБ"
                    },
                    'disk': {
                        **_disk_static,
                        'active_time': f"{_disk_active}%",
                        'latency': f"{_disk_latency:.1f} мс",
                        'read_speed': _fmt_speed(d_r_sec),
                        'write_speed': _fmt_speed(d_w_sec)
                    },
                    'net': {
                        **_wifi_static,
                        'dn_speed': _fmt_speed(n_dn),
                        'up_speed': _fmt_speed(n_up),
                        'ipv4': next((a.address for a in _net_addrs.get('WLAN', []) if a.family == socket.AF_INET), 'Н/Д'),
                        'ipv6': next((a.address for a in _net_addrs.get('WLAN', []) if a.family == socket.AF_INET6), 'Н/Д')
                    }
                }
                _log_monitor_msg("PerfCollector: Loop success")
                _disk_prev, _net_all_prev, _t_prev = d_io, n_io_all, time.time()
            except Exception as e:
                _log_monitor_msg(f"PerfCollector loop error: {e}")
            elapsed = time.time() - t0
            _interval = 4.0 if _LOW_PERF_MODE else 3.0
            time.sleep(max(0.1, _interval - elapsed))
    threading.Thread(target=_worker, daemon=True, name='PerfCollector').start()
def clock_tick(hud) -> None:
    n = datetime.now()
    t_str = n.strftime('%H:%M:%S')
    d_str = n.strftime('%d ') + _RU_MON[n.month] + n.strftime(' %Y')
    hud._clock_lbl.configure(text=t_str)
    hud._date_lbl.configure(text=d_str)
    try:
        w = hud.root.winfo_width()
        if w < 900:
            hud._hdr_time.configure(text=f'{t_str}  ')
            if hasattr(hud, '_hdr_os_lbl'):
                hud._hdr_os_lbl.configure(text='  OS v1.5')
        else:
            hud._hdr_time.configure(text=f'{d_str}  {t_str}  ')
            if hasattr(hud, '_hdr_os_lbl'):
                hud._hdr_os_lbl.configure(text='  JARVIS OS  v1.5')
    except Exception:
        pass
    try:
        def _p(s):
            try:
                hh, mm = map(int, s.split(':'))
                return hh * 60 + mm
            except:
                return None
        mr, ms = (_p(hud._top_rise), _p(hud._top_set))
        mc = n.hour * 60 + n.minute
        if mr is not None and ms is not None:
            if mr <= mc <= ms:
                pct = (mc - mr) / (ms - mr)
                hud._top_week = 'СВЕТОВОЙ ДЕНЬ'
                hud._top_day = 'ДО ЗАКАТА'
            else:
                if mc > ms:
                    pct = (mc - ms) / (1440 - ms + mr)
                else:
                    pct = (1440 - ms + mc) / (1440 - ms + mr)
                hud._top_week = 'НОЧНОЙ ЦИКЛ'
                hud._top_day = 'ДО РАССВЕТА'
            hud._top_pct = pct
            hud._top_pct_str = f'{int(pct * 100)}%'
        else:
            hud._top_pct = 0.0
            hud._top_pct_str = '0%'
            hud._top_week = 'ОЖИДАНИЕ ДАННЫХ'
            hud._top_day = '...'
        yday = n.timetuple().tm_yday
        week = int(n.strftime('%V'))
        wday = _RU_DAYS.get(n.weekday(), '')
        total = 366 if n.year % 4 == 0 and (n.year % 100 != 0 or n.year % 400 == 0) else 365
        hud._top_yday_str = f'ДЕНЬ {yday} / {total}'
        hud._top_week_str = f'НЕДЕЛЯ {week}'
        hud._top_wday_str = wday
        renderer.draw_top_strip(hud)
    except Exception:
        pass
    hud.root.after(1000, lambda: clock_tick(hud))
def net_tick(hud) -> None:
    try:
        now = psutil.net_io_counters()
        dt = time.time() - hud._net_t
        if dt > 0:
            hud._up_v.configure(text=_fmt_speed((now.bytes_sent - hud._net_prev.bytes_sent) / dt))
            hud._dn_v.configure(text=_fmt_speed((now.bytes_recv - hud._net_prev.bytes_recv) / dt))
        hud._net_prev = now
        hud._net_t = time.time()
    except Exception:
        pass
    hud.root.after(1000, lambda: net_tick(hud))
def refresh_ip(hud) -> None:
    def _do():
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '—'
        try:
            hud.root.after(0, lambda: hud._ip_v.configure(text=ip))
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()
    hud.root.after(30000, refresh_ip, hud)
def state_tick(hud) -> None:
    _state_interval = 300 if _LOW_PERF_MODE else 150
    if not hasattr(hud, '_bot_canvas') or not hud._bot_items:
        hud.root.after(_state_interval, lambda: state_tick(hud))
        return
    mode = STATE.mode
    if getattr(hud, '_last_state_mode', None) == mode:
        hud.root.after(_state_interval, lambda: state_tick(hud))
        return
    hud._last_state_mode = mode
    for item in hud._bot_items:
        state = item['state']
        is_active = state == mode
        col = item['col']
        bc = col if is_active else _blend(col, 0.3)
        tc = _WHITE if is_active else _DIM
        dot_c = col if is_active else _DIM
        thick = 2 if is_active else 1
        bg_col = _blend(col, 0.1)
        ids = item['ids']
        hud._bot_canvas.itemconfig(ids[0], fill=bg_col if is_active else '')
        for i in range(1, 5):
            hud._bot_canvas.itemconfig(ids[i], fill=bc if is_active else '', width=thick)
        hud._bot_canvas.itemconfig(ids[5], fill=dot_c)
        hud._bot_canvas.itemconfig(ids[6], fill=tc)
    hud.root.after(_state_interval, lambda: state_tick(hud))
