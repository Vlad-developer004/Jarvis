from __future__ import annotations
import math, random
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from .. import hud_constants as _hc
from ..hud_state import HudState, STATE
from ..hud_utils import _blend, _set_dark_title_bar, _draw_grid, _draw_hex_grid
def open_perf_monitor(hud, reopen: bool = False) -> None:
    if not reopen and hud._perf_win and hud._perf_win.winfo_exists():
        hud._perf_win.lift()
        return
    if reopen and hud._perf_win and hud._perf_win.winfo_exists():
        hud._perf_win.destroy()
    _f  = hud._F
    _fs = hud._fs
    _px = hud._px
    win = tk.Toplevel(hud.root)
    hud._perf_win = win
    hud._track_subwin('perf_monitor', win, lambda: open_perf_monitor(hud, reopen=True))
    win.overrideredirect(True)
    win.attributes('-alpha', 0.98)
    win.configure(bg=_BG)
    _sw, _sh = hud.root.winfo_screenwidth(), hud.root.winfo_screenheight()
    _dw, _dh = _px(1160), _px(760)
    _dx, _dy = (_sw - _dw) // 2, (_sh - _dh) // 2
    win.geometry(f'{_dw}x{_dh}+{_dx}+{_dy}')
    _drag_data = {'x': 0, 'y': 0}
    def _start_drag(e):
        _drag_data['x'] = e.x
        _drag_data['y'] = e.y
    def _on_drag(e):
        dx = e.x - _drag_data['x']
        dy = e.y - _drag_data['y']
        win.geometry(f'+{win.winfo_x() + dx}+{win.winfo_y() + dy}')
    bg_c = tk.Canvas(win, bg=_BG, highlightthickness=0)
    bg_c.pack(fill='both', expand=True)
    def _draw_tech_overlay():
        bg_c.delete('tech')
        w, h = win.winfo_width(), win.winfo_height()
        if w < 10: return
        _f8 = (_f, _fs(7))
        for i in range(5):
            _hex = "".join(random.choices("0123456789ABCDEF", k=8))
            bg_c.create_text(20, 60 + i*12, text=f"0x{_hex}  [LINK_STABLE]", fill=_blend(_CYAN, 0.15), font=_f8, anchor='w', tags='tech')
            bg_c.create_text(w-20, h-60 - i*12, text=f"SYS_VAL_0{i}: {random.randint(1000,9999)}", fill=_blend(_CYAN, 0.15), font=_f8, anchor='e', tags='tech')
        bg_c.create_text(w-40, 40, text="STRK_DIAG_CORE v1.4", fill=_blend(_CYAN, 0.2), font=_f8, anchor='e', tags='tech')
    def _draw_base():
        bg_c.delete('base')
        w, h = win.winfo_width(), win.winfo_height()
        if w < 10: return
        _draw_grid(bg_c, w, h, _CYAN)
        bw = _px(24)
        bg_c.create_rectangle(2, 2, w-2, h-2, outline=_blend(_CYAN, 0.2), width=1, tags='base')
        for (x, y, dx, dy) in [(2, 2, 1, 1), (w-2, 2, -1, 1), (2, h-2, 1, -1), (w-2, h-2, -1, -1)]:
            bg_c.create_line(x, y, x + dx * bw, y, fill=_CYAN, width=2, tags='base')
            bg_c.create_line(x, y, x, y + dy * bw, fill=_CYAN, width=2, tags='base')
            bg_c.create_line(x + dx*6, y + dy*6, x + dx*18, y + dy*6, fill=_blend(_CYAN, 0.4), width=1, tags='base')
        _draw_tech_overlay()
    win.bind('<Configure>', lambda e: _draw_base())
    hdr = tk.Frame(win, bg=_blend(_CYAN, 0.08), height=_px(46))
    hdr.place(x=4, y=4, width=_dw-8)
    hdr.bind('<Button-1>', _start_drag)
    hdr.bind('<B1-Motion>', _on_drag)
    tk.Frame(hdr, bg=_CYAN, height=1).pack(fill='x', side='bottom')
    tk.Label(hdr, text='  ⌬  СИСТЕМНЫЙ МОНИТОРИНГ J.A.R.V.I.S.', bg=hdr['bg'], fg=_CYAN, font=(_f, _fs(12), 'bold')).pack(side='left', padx=16)
    btn_close = tk.Canvas(hdr, width=_px(40), height=_px(40), bg=hdr['bg'], highlightthickness=0, cursor='hand2')
    btn_close.pack(side='right', padx=4)
    def _draw_close(col=_DIM):
        btn_close.delete('all')
        btn_close.create_text(20, 20, text='✕', fill=col, font=(_f, _fs(14), 'bold'))
    _draw_close()
    btn_close.bind('<Enter>', lambda e: _draw_close(_RED))
    btn_close.bind('<Leave>', lambda e: _draw_close())
    btn_close.bind('<Button-1>', lambda e: win.destroy())
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    content_f = tk.Frame(win, bg=_BG)
    content_f.place(x=4, y=54, width=_dw-8, height=_dh-58)
    sidebar = tk.Frame(content_f, bg=_blend(_CYAN, 0.03), width=_px(280))
    sidebar.pack(side='left', fill='y', padx=(0, 2))
    sidebar.pack_propagate(False)
    main_area = tk.Frame(content_f, bg=_blend(_CYAN, 0.01))
    main_area.pack(side='left', fill='both', expand=True)
    _active = tk.StringVar(value='ram')
    _canvases = {}
    _f_labels = {}
    _scan_x = [0]
    _META = {
        'ram':      ('ОПЕРАТИВНАЯ ПАМЯТЬ (ОЗУ)',   _MAG,   100, '%',  'ПАМЯТЬ'),
        'dsk_util': ('ЛОКАЛЬНЫЙ ДИСК (C:)',      _GREEN, 100, '%',  'ДИСК'),
        'net_io':   ('WI-FI  (WLAN)',             _CYAN,  None, ' КБ/с', 'WI-FI'),
        'gpu_util': ('ГРАФИЧЕСКИЙ ПРОЦЕССОР',      _AMBER, 100, '%',  'ГРАФИКА'),
    }
    def _on_select(key):
        _active.set(key)
        for k, (btn_f, accent, lv, l_name, spark) in _sides.items():
            is_sel = (k == key)
            btn_f.configure(bg=_blend(_CYAN, 0.12) if is_sel else _BG)
            accent.configure(bg=_META[k][1] if is_sel else _blend(_META[k][1], 0.2), width=4 if is_sel else 2)
            lv.configure(fg=_WHITE if is_sel else _DIM, font=(_f, _fs(18 if is_sel else 14), 'bold'))
            l_name.configure(fg=_CYAN if is_sel else _blend(_CYAN, 0.4), font=(_f, _fs(10), 'bold'))
        for k, c in _canvases.items():
            if k == key: c.pack(fill='both', expand=True, padx=40, pady=30)
            else: c.pack_forget()
    _sides = {}
    for key, (name, col, _, _, short) in _META.items():
        f = tk.Frame(sidebar, bg=_BG, cursor='hand2', height=_px(85))
        f.pack(fill='x', pady=1)
        f.pack_propagate(False)
        def _bind_click(w, k=key):
            w.bind('<Button-1>', lambda e: _on_select(k))
            for child in w.winfo_children():
                _bind_click(child, k)
        accent = tk.Frame(f, bg=_blend(col, 0.3), width=2)
        accent.pack(side='left', fill='y')
        info = tk.Frame(f, bg=f['bg'])
        info.pack(side='left', fill='y', padx=15)
        l_name = tk.Label(info, text=short, bg=f['bg'], fg=_DIM, font=(_f, _fs(10), 'bold'), anchor='w')
        l_name.pack(fill='x', pady=(12, 0))
        val_lbl = tk.Label(info, text="--", bg=f['bg'], fg=col, font=(_f, _fs(14), 'bold'), anchor='w')
        val_lbl.pack(fill='x')
        spark = tk.Canvas(f, bg=f['bg'], highlightthickness=0, width=90, height=45)
        spark.pack(side='right', padx=10, pady=10)
        _sides[key] = (f, accent, val_lbl, l_name, spark)
        _bind_click(f)
    def _draw_graph(key, c):
        c.delete('dyn')
        sw, sh = c.winfo_width(), c.winfo_height()
        if sw < 100 or sh < 100: return
        meta = _META.get(key)
        if not meta: return
        col, unit = meta[1], meta[3]
        is_pct = key in ['ram', 'dsk_util', 'gpu_util']
        scale = 100.0 if is_pct else (float(meta[2]) if meta[2] else 1024.0)
        if not is_pct and not meta[2]:
            net_pts = hud._perf_history.get('net_dn', [])
            scale = max(net_pts)*1.2 if net_pts and any(v > 0 for v in net_pts) else 1024.0
        PX_L, PX_R = 50.0, 50.0
        PY_T, PY_B = 40.0, 195.0
        DH = float(sh - PY_T - PY_B)
        DW = float(sw - PX_L - PX_R)
        Y_ZERO = PY_T + DH
        def to_y(v):
            r = min(max(float(v), 0.0), scale) / scale
            return PY_T + DH * (1.0 - r)
        for i in range(5):
            ratio = i * 0.25
            py = PY_T + DH * (1.0 - ratio)
            c.create_line(PX_L, py, sw-PX_R, py, fill=_blend(col, 0.05), tags='dyn')
            lbl = f"{int(ratio*100)}%" if is_pct else f"{(ratio*scale):.0f}"
            c.create_text(sw-PX_R+5, py, text=lbl, fill=_blend(col, 0.7), font=(_f, _fs(7)), anchor='w', tags='dyn')
        for i in range(7):
            px = PX_L + (DW * i / 6.0)
            c.create_line(px, PY_T, px, Y_ZERO, fill=_blend(col, 0.03), tags='dyn')
        hk = 'net_dn' if key == 'net_io' else key
        pts = list(hud._perf_history.get(hk, []))
        if len(pts) < 2: return
        display_pts = pts[-60:]
        l_i = float(len(display_pts) - 1.0)
        coords = []
        for i, v in enumerate(display_pts):
            coords.extend([PX_L + DW * (i / l_i), to_y(v)])
        f_c = list(coords) + [coords[-2], Y_ZERO, PX_L, Y_ZERO]
        c.create_polygon(f_c, fill=_blend(col, 0.08), outline='', tags='dyn')
        c.create_line(coords, fill=col, width=1.5, tags='dyn')
        titles = {
            'ram': "ИСПОЛЬЗОВАНИЕ ПАМЯТИ (%)",
            'dsk_util': "АКТИВНОЕ ВРЕМЯ ДИСКА (%)",
            'net_io': "ПРОПУСКНАЯ СПОСОБНОСТЬ (%)",
            'gpu_util': "ИСПОЛЬЗОВАНИЕ ГП (%)"
        }
        c.create_text(PX_L, PY_T - 5, text=titles.get(key, ""), fill=_blend(col, 0.8), font=(_f, _fs(10), 'bold'), anchor='sw', tags='dyn')
        meta_all = getattr(hud, '_perf_meta', {})
        hw_info = meta_all.get('hardware', {})
        stats_y = Y_ZERO + 12
        col_w = DW / 4.0
        def draw_stat(c, x, y, label, val, color=col):
            c.create_text(x, y, text=label, fill=_blend(color, 0.75), font=(_f, _fs(10), 'bold'), anchor='nw', tags='dyn')
            c.create_text(x, y + 22, text=val if val else "...", fill=_WHITE, font=(_f, _fs(14), 'bold'), anchor='nw', tags='dyn')
        hw_name = ""
        if key == 'gpu_util': hw_name = hw_info.get('gpu', '')
        elif key == 'ram': hw_name = f"ПАМЯТЬ: {meta_all.get('ram', {}).get('total', '')}"
        if hw_name:
            c.create_text(sw - 30, 10, text=hw_name, fill=_CYAN, font=(_f, _fs(10), 'bold'), anchor='ne', tags='dyn')
        if key == 'ram':
            m = meta_all.get('ram', {})
            draw_stat(c, PX_L, stats_y, "В ИСПОЛЬЗОВАНИИ", f"{pts[-1]:.1f}%")
            draw_stat(c, PX_L + col_w, stats_y, "ВСЕГО", m.get('total', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y, "ДОСТУПНО", m.get('avail', 'Н/Д'))
            draw_stat(c, PX_L + col_w*3, stats_y, "СКОРОСТЬ", m.get('speed', 'Н/Д'))
            draw_stat(c, PX_L, stats_y + 60, "ВЫДЕЛЕНО", m.get('committed', 'Н/Д'))
            draw_stat(c, PX_L + col_w, stats_y + 60, "КЭШИРОВАНИЕ", m.get('cached', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y + 60, "СЛОТЫ", m.get('slots', 'Н/Д'))
            draw_stat(c, PX_L + col_w*3, stats_y + 60, "ФОРМ-ФАКТОР", m.get('form', 'Н/Д'))
            draw_stat(c, PX_L, stats_y + 120, "ВЫГРУЖАЕМЫЙ ПУЛ", m.get('paged','0'))
            draw_stat(c, PX_L + col_w, stats_y + 120, "НЕВЫГРУЖАЕМЫЙ ПУЛ", m.get('nonpaged','0'))
            draw_stat(c, PX_L + col_w*2, stats_y + 120, "ЗАБРОНИРОВАНО", m.get('h_res', '0 МБ'))
        elif key == 'dsk_util':
            m = meta_all.get('disk', {})
            draw_stat(c, PX_L, stats_y, "АКТИВНОЕ ВРЕМЯ", m.get('active', '0%'))
            draw_stat(c, PX_L + col_w, stats_y, "ВРЕМЯ ОТВЕТА", m.get('latency', '0 мс'))
            draw_stat(c, PX_L + col_w*2, stats_y, "ЧТЕНИЕ", m.get('read', '0 КБ/с'))
            draw_stat(c, PX_L + col_w*3, stats_y, "ЗАПИСЬ", m.get('write', '0 КБ/с'))
            draw_stat(c, PX_L, stats_y + 60, "ЕМКОСТЬ", m.get('total', 'Н/Д'))
            draw_stat(c, PX_L + col_w, stats_y + 60, "ТИП", m.get('type', 'SSD'))
            draw_stat(c, PX_L + col_w*2, stats_y + 60, "СИСТЕМНЫЙ ДИСК", "ДА" if m.get('is_sys') else "НЕТ")
            draw_stat(c, PX_L + col_w*3, stats_y + 60, "ФАЙЛ ПОДКАЧКИ", "ДА" if m.get('is_page') else "НЕТ")
        elif key == 'net_io':
            m = meta_all.get('net', {})
            draw_stat(c, PX_L, stats_y, "ПРИЕМ", m.get('dn', '0 Кбит/с'))
            draw_stat(c, PX_L + col_w, stats_y, "ОТПРАВКА", m.get('up', '0 Кбит/с'))
            draw_stat(c, PX_L + col_w*2, stats_y, "ТИП", "802.11ac")
            draw_stat(c, PX_L + col_w*3, stats_y, "КАНАЛ", m.get('link_speed', 'Н/Д'))
            draw_stat(c, PX_L, stats_y + 60, "SSID", m.get('ssid', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y + 60, "IPv4 АДРЕС", m.get('ipv4', 'Н/Д'))
            draw_stat(c, PX_L, stats_y + 120, "IPv6 АДРЕС", m.get('ipv6', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y + 120, "АДАПТЕР", m.get('adapter', 'WLAN'), color=_CYAN)
        elif key == 'gpu_util':
            m = meta_all.get('gpu', {})
            gpu_util_pts = list(hud._perf_history.get('gpu_util', []))
            gpu_temp_pts = list(hud._perf_history.get('gpu_temp', []))
            has_util = gpu_util_pts and not math.isnan(gpu_util_pts[-1])
            has_temp = gpu_temp_pts and not math.isnan(gpu_temp_pts[-1])
            draw_stat(c, PX_L, stats_y, "ЗАГРУЗКА", f"{gpu_util_pts[-1] if has_util else 0:.1f}%")
            draw_stat(c, PX_L + col_w, stats_y, "ПАМЯТЬ ГП", m.get('vram', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y, "ОБЩАЯ ПАМЯТЬ", m.get('shared', 'Н/Д'))
            draw_stat(c, PX_L + col_w*3, stats_y, "ВИДЕОПРОЦЕССОР", "Intel(R) Iris(R) Xe")
            draw_stat(c, PX_L, stats_y + 60, "ВЕРСИЯ ДРАЙВЕРА", m.get('driver', 'Н/Д'))
            draw_stat(c, PX_L + col_w, stats_y + 60, "ДАТА ДРАЙВЕРА", m.get('driver_date', 'Н/Д'))
            draw_stat(c, PX_L + col_w*2, stats_y + 60, "DIRECTX", "12 (FL 12.1)")
            draw_stat(c, PX_L + col_w*3, stats_y + 60, "ТИП", m.get('type', 'Интегрированная'))
            draw_stat(c, PX_L, stats_y + 120, "АДАПТЕР", m.get('name', 'Н/Д'), color=_CYAN)
            draw_stat(c, PX_L + col_w*2, stats_y + 120, "МЕСТО", m.get('location', 'Н/Д'))
    def _resize_graph(key, c):
        c.delete('grid')
        sw, sh = c.winfo_width(), c.winfo_height()
        if sw > 10:
            _draw_hex_grid(c, sw, sh, _META[key][1], size=32)
        c.delete('grid')
        w, h = c.winfo_width(), c.winfo_height()
        if w > 10:
            _draw_hex_grid(c, w, h, _META[key][1], size=32)
    for key in _META:
        gc = tk.Canvas(main_area, bg=_BG, highlightthickness=0)
        _canvases[key] = gc
        gc.bind('<Configure>', lambda e, k=key, c=gc: _resize_graph(k, c))
        _f_labels[key] = {}
    _refresh_interval = 500 if _hc._LOW_PERF_MODE else 250
    _last_refresh_len: dict = {}
    _tech_overlay_counter = [0]
    def _refresh():
        if not win.winfo_exists(): return
        _tech_overlay_counter[0] += 1
        if _tech_overlay_counter[0] >= (10 if _hc._LOW_PERF_MODE else 5):
            _tech_overlay_counter[0] = 0
            _draw_tech_overlay()
        for k, (btn_f, accent, lv, l_name, spark) in _sides.items():
            hk = 'net_dn' if k == 'net_io' else k
            pts = list(hud._perf_history.get(hk, []))
            if not pts: continue
            val = pts[-1]
            unit = _META[k][3]
            v_str = f"{val:.1f}{unit}" if 'nan' not in str(val).lower() else "OFFLINE"
            lv.configure(text=v_str)
            cur_len = len(pts)
            if _last_refresh_len.get(k) == cur_len:
                continue
            _last_refresh_len[k] = cur_len
            spark.delete('dyn_s')
            sw, sh = 80, 35
            spts = pts[-30:]
            if len(spts) > 1:
                is_p = k in ['ram', 'dsk_util', 'gpu_util']
                s_scale = 100.0 if is_p else (max(pts)*1.2 if max(pts)>0 else 1024.0)
                s_coords = []
                s_li = float(len(spts) - 1.0)
                for i, sv in enumerate(spts):
                    sx = (i / s_li) * sw
                    sy = sh - (min(max(float(sv), 0.0), s_scale) / s_scale) * sh
                    s_coords.extend([sx, sy])
                sf_c = list(s_coords) + [sw, sh, 0, sh]
                spark.create_polygon(sf_c, fill=_blend(_META[k][1], 0.1), outline='', tags='dyn_s')
                spark.create_line(s_coords, fill=_blend(_META[k][1], 0.5), width=1.5, smooth=True, tags='dyn_s')
        cur = _active.get()
        _draw_graph(cur, _canvases[cur])
        win.after(_refresh_interval, _refresh)
    win.update_idletasks()
    _on_select('ram')
    _refresh()
