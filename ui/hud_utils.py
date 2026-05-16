from __future__ import annotations
from core import i18n
import math, subprocess, time, os, sys, json
from datetime import datetime
from functools import lru_cache
from typing import Optional, Union
import tkinter as tk
from . import hud_constants as _hud_c
from .hud_constants import _BG, _CYAN, _GREEN, _AMBER, _RED, _DYN
try:
    import cv2 as _cv2
    _CV2_OK = True
except ImportError:
    _cv2 = None
    _CV2_OK = False
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
from config_pack.config import get_settings_path
_SETTINGS_PATH = get_settings_path()
def _load_hud_settings():
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}
def _save_hud_settings(settings):
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
def _make_sun_icon(size: int, rising: bool) -> 'ImageTk.PhotoImage | None':
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx, cy = (size // 2, size * 58 // 100)
        r = size * 22 // 100
        sun_color = '#ffcc00'
        horizon_color = '#ffaa00' if rising else '#cc44ff'
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=sun_color)
        ray_inner = r + size * 6 // 100
        ray_outer = r + size * 14 // 100
        for i in range(8):
            angle = math.radians(i * 45)
            if rising and math.sin(angle) > 0.1:
                continue
            if not rising and math.sin(angle) < -0.1:
                continue
            x1 = cx + ray_inner * math.cos(angle)
            y1 = cy - ray_inner * math.sin(angle)
            x2 = cx + ray_outer * math.cos(angle)
            y2 = cy - ray_outer * math.sin(angle)
            d.line([x1, y1, x2, y2], fill=sun_color, width=max(1, size // 20))
        hx0, hx1 = (size * 10 // 100, size * 90 // 100)
        hy = cy + r // 2
        d.line([hx0, hy, hx1, hy], fill=horizon_color, width=max(1, size // 18))
        aw = size * 8 // 100
        ay = hy - size * 14 // 100 if rising else hy + size * 14 // 100
        tip_y = hy - size * 22 // 100 if rising else hy + size * 22 // 100
        d.polygon([(cx, tip_y), (cx - aw, ay), (cx + aw, ay)], fill=horizon_color)
        from PIL import ImageTk as _ITK
        return _ITK.PhotoImage(img)
    except Exception:
        return None
def _calc_sun(lat: float, lon: float) -> tuple[str, str]:
    try:
        now = datetime.now()
        jd = now.toordinal() - 719162 + 2440587.5
        jc = (jd - 2451545.0) / 36525.0
        gml = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
        gma = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
        ec = math.sin(math.radians(gma)) * (1.914602 - jc * (0.004817 + 1.4e-05 * jc)) + math.sin(math.radians(2 * gma)) * (0.019993 - 0.000101 * jc) + math.sin(math.radians(3 * gma)) * 0.000289
        stl = gml + ec
        sal = stl - 0.00569 - 0.00478 * math.sin(math.radians(125.04 - 1934.136 * jc))
        moe = 23 + (26 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60) / 60
        oc = moe + 0.00256 * math.cos(math.radians(125.04 - 1934.136 * jc))
        dec = math.degrees(math.asin(math.sin(math.radians(oc)) * math.sin(math.radians(sal))))
        gml_r = math.radians(gml)
        gma_r = math.radians(gma)
        y = math.tan(math.radians(oc / 2)) ** 2
        eot = y * math.sin(2 * gml_r) - 2 * 0.016708634 * math.sin(gma_r) + 4 * 0.016708634 * y * math.sin(gma_r) * math.cos(2 * gml_r) - 0.5 * y * y * math.sin(4 * gml_r) - 1.25 * 0.016708634 ** 2 * math.sin(2 * gma_r)
        eot_min = 4 * math.degrees(eot)
        lat_r = math.radians(lat)
        dec_r = math.radians(dec)
        cos_ha = math.cos(math.radians(90.833)) / (math.cos(lat_r) * math.cos(dec_r)) - math.tan(lat_r) * math.tan(dec_r)
        if abs(cos_ha) > 1:
            return ('—:—', '—:—')
        ha = math.degrees(math.acos(cos_ha))
        utc_offset = -time.timezone / 3600 if not time.daylight else -(time.timezone - 3600) / 3600
        noon_utc_min = 720 - 4 * lon - eot_min
        rise_utc_min = noon_utc_min - ha * 4
        set_utc_min = noon_utc_min + ha * 4
        def fmt(minutes_utc):
            total = minutes_utc + utc_offset * 60
            total = total % 1440
            hh = int(total // 60)
            mm = int(total % 60)
            return f'{hh:02d}:{mm:02d}'
        return (fmt(rise_utc_min), fmt(set_utc_min))
    except Exception:
        return ('—:—', '—:—')
@lru_cache(maxsize=512)
def _bar_color(pct: float) -> str:
    pct = max(0.0, min(100.0, round(float(pct), 1)))
    if pct <= 50:
        t = pct / 50.0
        r = int(0x00 + (0xff - 0x00) * t)
        g = 0xff
        b = int(0x88 * (1.0 - t))
    elif pct <= 80:
        t = (pct - 50.0) / 30.0
        r = 0xff
        g = int(0xff - (0xff - 0xcc) * t)
        b = 0x00
    else:
        t = (pct - 80.0) / 20.0
        r = 0xff
        g = int(0xcc * (1.0 - t))
        b = 0x00
    return f'#{r:02x}{g:02x}{b:02x}'
@lru_cache(maxsize=256)
def _blend(hex_col: str, alpha: float) -> str:
    alpha = round(alpha, 2)
    r, g, b = (int(hex_col[1:3], 16), int(hex_col[3:5], 16), int(hex_col[5:7], 16))
    # Read live BG from module object so theme changes propagate instantly
    bg_col = _hud_c._BG
    br, bg_, bb = (int(bg_col[1:3], 16), int(bg_col[3:5], 16), int(bg_col[5:7], 16))
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(br + (r - br) * alpha))),
        max(0, min(255, int(bg_ + (g - bg_) * alpha))),
        max(0, min(255, int(bb + (b - bb) * alpha)))
    )
def _glow_arc(c: tk.Canvas, x0, y0, x1, y1, start, extent, color, width=2) -> None:
    _layers = ((14, 0.03), (6, 0.15), (0, 1.0)) if _hud_c._LOW_PERF_MODE else ((14, 0.03), (10, 0.07), (6, 0.15), (3, 0.3), (1, 0.6), (0, 1.0))
    for dw, a in _layers:
        c.create_arc(x0, y0, x1, y1, start=start, extent=extent, style='arc', outline=_blend(color, a), width=width + dw, tags=_DYN)
def _glow_oval(c: tk.Canvas, px, py, r, color) -> None:
    _layers = ((3, 0.3), (0, 1.0)) if _hud_c._LOW_PERF_MODE else ((7, 0.05), (5, 0.12), (3, 0.3), (1, 0.75), (0, 1.0))
    for ds, a in _layers:
        s = r + ds
        c.create_oval(px - s, py - s, px + s, py + s, fill=_blend(color, a), outline='', tags=_DYN)
def _glow_text(c: tk.Canvas, x, y, text, font, color) -> None:
    c.create_text(x + 1, y + 1, text=text, font=font, fill=_blend(color, 0.25), tags=_DYN)
    c.create_text(x, y, text=text, font=font, fill=color, tags=_DYN)
def _fmt_speed(bps: float) -> str:
    """Форматирует скорость из Байт/с в КБ/с, МБ/с или ГБ/с."""
    if bps < 0: bps = 0
    if bps < 1024:
        return f'{bps:.0f} Б/с'
    elif bps < 1048576: # < 1 МБ
        return f'{bps / 1024:.1f} КБ/с'
    elif bps < 1073741824: # < 1 ГБ
        return f'{bps / 1048576:.1f} МБ/с'
    else:
        return f'{bps / 1073741824:.2f} ГБ/с'
def _uptime() -> str:
    import psutil as _psutil
    s = int(time.time() - _psutil.boot_time())
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f'{h}ч {m:02d}м'
def _read_gpu_temp(wmi_conns: dict=None) -> Optional[float]:
    try:
        out = subprocess.check_output(['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader'], creationflags=subprocess.CREATE_NO_WINDOW, timeout=1).decode('utf-8').strip()
        v = float(out)
        if 10 < v < 120:
            return v
    except Exception:
        pass
    if wmi_conns and 'ohm' in wmi_conns:
        try:
            for s in wmi_conns['ohm'].Sensor():
                if s.SensorType == 'Temperature' and 'GPU' in s.Name:
                    return round(float(s.Value), 1)
        except Exception:
            pass
    return None
def _ps_query(query: str, ns: str = "root/cimv2") -> Optional[Union[list, dict]]:
    try:
        import subprocess, json
        cmd = f'powershell -NoProfile -Command "Get-CimInstance -Namespace {ns} -ClassName {query} -ErrorAction SilentlyContinue | ConvertTo-Json"'
        out = subprocess.check_output(cmd, creationflags=0x08000000, stderr=subprocess.DEVNULL, timeout=1).decode('utf-8', errors='ignore')
        if not out: return None
        data = json.loads(out)
        return data if isinstance(data, (list, dict)) else [data]
    except Exception: return None
def _read_gpu_util(wmi_conns: dict=None) -> Optional[float]:
    try:
        out = subprocess.check_output(
            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
            creationflags=0x08000000, timeout=1
        ).decode('utf-8').strip()
        v = float(out)
        if 0 <= v <= 100: return v
    except Exception: pass
    data = _ps_query("Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine")
    if data:
        items = data if isinstance(data, list) else [data]
        utils = [float(item.get('UtilizationPercentage', 0)) for item in items]
        if utils: return min(round(max(utils), 1), 100.0)
        return 0.0
    if wmi_conns and 'ohm' in wmi_conns:
        try:
            for s in wmi_conns['ohm'].Sensor():
                if s.SensorType == 'Load' and 'GPU' in s.Name:
                    return round(float(s.Value), 1)
        except Exception: pass
    return None
def _read_temp(wmi_conns: dict) -> Optional[float]:
    for query, ns in [("Win32_PerfFormattedData_Counters_ThermalZoneInformation", "root/cimv2"),
                      ("MSAcpi_ThermalZoneTemperature", "root/wmi")]:
        data = _ps_query(query, ns)
        if data:
            items = data if isinstance(data, list) else [data]
            for item in items:
                raw = item.get('Temperature') or item.get('CurrentTemperature')
                if raw:
                    c = (float(raw) - 273.15) if 'ThermalZoneInformation' in query else (float(raw) / 10.0 - 273.15)
                    if 10 < c < 120 and abs(c - 27.85) > 0.1:
                        return round(c, 1)
    if wmi_conns and 'ohm' in wmi_conns:
        try:
            for s in wmi_conns['ohm'].Sensor():
                if s.SensorType == 'Temperature' and 'CPU' in s.Name:
                    return round(float(s.Value), 1)
        except Exception: pass
    try:
        import json
        with open('data/temp_bridge.json', 'r') as f:
            data = json.load(f)
            val = data.get('cpu_temp')
            if val is not None: return round(float(val), 1)
    except Exception: pass
    return None
def _draw_grid(c: tk.Canvas, w: int, h: int, col: str, step: int = 60, tags='grid'):
    c.delete(tags)
    _col = _blend(col, 0.04)
    for x in range(0, w, step):
        c.create_line(x, 0, x, h, fill=_col, width=1, tags=tags)
    for y in range(0, h, step):
        c.create_line(0, y, w, y, fill=_col, width=1, tags=tags)
def _set_dark_title_bar(window: tk.Toplevel | tk.Tk) -> None:
    try:
        import ctypes
        window.update()
        hwnd_tk = window.winfo_id()
        hwnd = ctypes.windll.user32.GetAncestor(hwnd_tk, 2)
        if not hwnd: hwnd = hwnd_tk
        
        # Check current theme
        from .hud_themes import get_current_theme_name
        is_light = get_current_theme_name() == 'light'
        
        on = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(on), 4)
        
        if is_light:
            # Light theme: Light grey/white title bar, dark text
            caption_col = ctypes.c_int(0x00FAFAF4) # BGR: f4fafc -> f4fafc
            text_col = ctypes.c_int(0x002E1A1A)    # BGR: 1a1a2e -> 2e1a1a
        else:
            # Dark theme: Deep dark title bar, white text
            caption_col = ctypes.c_int(0x00100B0A) # BGR for #0a0b10
            text_col = ctypes.c_int(0x00FFFFFF)
            
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_col), 4)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_col), 4)
    except Exception:
        pass

def _apply_window_icon(window: tk.Toplevel | tk.Tk, hud) -> None:
    """Applies the Jarvis icon to a window with a delay for reliability on Windows."""
    def _apply():
        try:
            _p = getattr(hud, '_ico_path', None)
            if not _p:
                import sys as _sys
                if getattr(_sys, 'frozen', False):
                    _bp = os.path.dirname(_sys.executable)
                else:
                    _bp = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                _p = os.path.join(_bp, 'assets', 'icon.ico')
            
            if _p and os.path.exists(_p):
                # Try iconbitmap first (classic)
                try:
                    window.iconbitmap(_p)
                except:
                    pass
                # Backup: set iconphoto for better compatibility
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(_p)
                    photo = ImageTk.PhotoImage(img)
                    window.wm_iconphoto(True, photo)
                    # Keep a reference to prevent garbage collection
                    window._icon_photo = photo
                except:
                    pass
        except Exception:
            pass
    window.after(250, _apply)
def _draw_hex_grid(c: tk.Canvas, w: int, h: int, col: str, size: int = 32, tags='grid'):
    c.delete(tags)
    _col = _blend(col, 0.05)
    _w_step = int(size * 1.732)
    _h_step = int(size * 1.5)
    for y in range(-size, h + size*2, _h_step):
        _off = (_w_step // 2) if (y // _h_step) % 2 else 0
        for x in range(-size, w + size*2, _w_step):
            _pts = []
            for i in range(6):
                ang = math.radians(i * 60 + 30)
                _pts.extend([x + _off + size * math.cos(ang), y + size * math.sin(ang)])
            c.create_polygon(_pts, outline=_col, fill='', width=1, tags=tags)
def autostart_enabled() -> bool:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, 'JarvisHUD')
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False
def autostart_set(enabled: bool) -> None:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
    if enabled:
        path = sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(sys.argv[0])
        winreg.SetValueEx(key, 'JarvisHUD', 0, winreg.REG_SZ, f'"{path}" --minimized')
    else:
        try:
            winreg.DeleteValue(key, 'JarvisHUD')
        except FileNotFoundError:
            pass
    winreg.CloseKey(key)

def _get_work_area() -> tuple[int, int, int, int]:
    """Returns (left, top, right, bottom) of the Windows work area in LOGICAL pixels."""
    try:
        import ctypes
        from ctypes import wintypes
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(rect), 0):
            pl, pt, pr, pb = rect.left, rect.top, rect.right, rect.bottom
            
            # Get DPI scale factor (Logical / Physical)
            import tkinter as tk
            root = tk._default_root
            if root:
                sw_log = root.winfo_screenwidth()
                sw_phys = ctypes.windll.user32.GetSystemMetrics(0) # SM_CXSCREEN
                scale = sw_log / sw_phys if sw_phys > 0 else 1.0
                return (int(pl*scale), int(pt*scale), int(pr*scale), int(pb*scale))
            return (pl, pt, pr, pb)
    except Exception: pass
    
    # Fallback to logical screen size if API fails
    import tkinter as tk
    try:
        _r = tk._default_root or tk.Tk()
        sw, sh = _r.winfo_screenwidth(), _r.winfo_screenheight()
        if not tk._default_root: _r.destroy()
        return (0, 0, sw, sh - 40)
    except: return (0, 0, 1920, 1040)

def _center_window(window: tk.Toplevel | tk.Tk, width: int, height: int, zoom: float = 1.0) -> None:
    """Centers the window within the usable Work Area (avoiding taskbars)."""
    window.update_idletasks()
    l, t, r, b = _get_work_area()
    aw, ah = (r - l), (b - t)
    
    x = l + (aw // 2) - (width // 2)
    y = t + (ah // 2) - (height // 2)
    
    # Ensure it's not off-screen even if work area is weird
    x = max(l, min(x, r - width))
    y = max(t, min(y, b - height))
    
    window.geometry(f'{width}x{height}+{x}+{y}')

def _constrain_window(win: tk.Toplevel | tk.Tk, x: int, y: int) -> tuple[int, int]:
    """Constrains coordinates with jitter protection and DPI awareness."""
    l, t, r, b = _get_work_area() 
    
    try:
        title_h = win.winfo_rooty() - win.winfo_y()
        border_w = win.winfo_rootx() - win.winfo_x()
        th = win.winfo_height() + title_h + border_w 
        tw = win.winfo_width() + (border_w * 2)
        if th < 50: raise Exception() 
    except:
        tw, th = win.winfo_reqwidth(), win.winfo_reqheight()

    nx = max(l, min(x, r - tw))
    ny = max(t, min(y, b - th))
    
    if abs(nx - x) < 2: nx = x
    if abs(ny - y) < 2: ny = y
    
    return nx, ny
def _make_resizable(win: tk.Toplevel | tk.Tk, min_w: int = 400, min_h: int = 300):
    """Adds native resizability to a borderless window without visible grips using Windows API."""
    import ctypes
    
    # Применяем пороги сразу, если они переданы
    try:
        win.minsize(min_w, min_h)
    except: pass
    
    zoom = 1.0
    if hasattr(win, '_hud_zoom'): zoom = win._hud_zoom
    elif hasattr(win, 'master') and hasattr(win.master, 'zoom_factor'): zoom = win.master.zoom_factor
    
    border = int(6 * zoom)
    _state = {'cursor': ''}
    
    def _get_ht(e):
        try:
            w, h = win.winfo_width(), win.winfo_height()
            x = e.x_root - win.winfo_rootx()
            y = e.y_root - win.winfo_rooty()
        except: return 0, ''
        
        # HTLEFT=10, HTRIGHT=11, HTTOP=12, HTTOPLEFT=13, HTTOPRIGHT=14, HTBOTTOM=15, HTBOTTOMLEFT=16, HTBOTTOMRIGHT=17
        if y < border:
            if x < border: return 13, 'size_nw_se'
            if x > w - border: return 14, 'size_ne_sw'
            return 12, 'size_ns'
        elif y > h - border:
            if x < border: return 16, 'size_ne_sw'
            if x > w - border: return 17, 'size_nw_se'
            return 15, 'size_ns'
        else:
            if x < border: return 10, 'size_we'
            if x > w - border: return 11, 'size_we'
        return 0, ''

    def _motion(e):
        ht, cursor = _get_ht(e)
        if _state['cursor'] != cursor:
            _state['cursor'] = cursor
            win.configure(cursor=cursor)

    def _press(e):
        ht, _ = _get_ht(e)
        if ht:
            # We are on a border! Trigger native resize
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            if not hwnd: hwnd = win.winfo_id()
            
            # Release Tkinter's mouse grab and hand over to Windows DWM
            ctypes.windll.user32.ReleaseCapture()
            import threading
            threading.Thread(target=lambda: ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, ht, 0), daemon=True).start()
            return "break"

    # Bind to Toplevel so it catches events bubbling from any child canvas/frame
    win.bind('<Motion>', _motion, add='+')
    win.bind('<ButtonPress-1>', _press, add='+')

