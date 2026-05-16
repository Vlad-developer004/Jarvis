from __future__ import annotations
import math, random, psutil
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from .. import hud_constants as _hc
from ..hud_state import HudState, STATE
from ..hud_utils import _blend, _set_dark_title_bar, _draw_grid, _draw_hex_grid, _center_window
from core import i18n

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
    
    def _on_map(e):
        if e.widget == win and not win.overrideredirect():
            win.overrideredirect(True)
    win.bind('<Map>', _on_map)
    win.configure(bg=_BG)
    
    def _start_drag(e): win._drag_data = (e.x_root, e.y_root)
    def _do_drag(e):
        if hasattr(win, '_drag_data'):
            dx, dy = e.x_root - win._drag_data[0], e.y_root - win._drag_data[1]
            win.geometry(f"+{win.winfo_x() + dx}+{win.winfo_y() + dy}")
            win._drag_data = (e.x_root, e.y_root)

    _W, _H = _px(920), _px(640)
    _center_window(win, _W, _H)
    
    win._pinned = tk.BooleanVar(value=False)
    _pinned = win._pinned
    _compact = tk.BooleanVar(value=False)
    _ghost = tk.BooleanVar(value=False)
    _T_COL = '#010101' 

    _SIDE_BG = _blend(_CYAN, 0.03)
    _MAIN_BG = _blend(_CYAN, 0.01)

    def _upd_min_size(compact_h=None):
        if _compact.get():
            mw = _px(260)
            mh = compact_h if compact_h else _px(80)
        else:
            mw, mh = _px(860), _px(520)
        win.minsize(mw, mh)
        cw, ch = win.winfo_width(), win.winfo_height()
        if cw < mw or ch < mh:
            win.geometry(f"{max(cw, mw)}x{max(ch, mh)}")
    
    from ..hud_utils import _make_resizable
    _make_resizable(win, min_w=_px(260), min_h=_px(80))
    _upd_min_size()

    bg_c = tk.Canvas(win, bg=_BG, highlightthickness=1, highlightbackground=_CYAN)
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
        bg_c.create_text(w-40, 40, text="STRK_DIAG_CORE v1.5", fill=_blend(_CYAN, 0.2), font=_f8, anchor='e', tags='tech')
        
    def _draw_base():
        bg_c.delete('base')
        if _ghost.get(): return
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

    def _toggle_pin():
        _pinned.set(not _pinned.get())
        win.attributes('-topmost', _pinned.get())
        _draw_header()

    def _toggle_ghost():
        _ghost.set(not _ghost.get())
        new_bg = _T_COL if _ghost.get() else _BG
        if _ghost.get(): win.attributes('-transparentcolor', _T_COL)
        else: win.attributes('-transparentcolor', '')
            
        win.configure(bg=new_bg)
        bg_c.configure(bg=new_bg)
        hdr.configure(bg=new_bg)
        content_f.configure(bg=new_bg)
        
        main_area.configure(bg=_T_COL if _ghost.get() else _MAIN_BG)
        sidebar.configure(bg=_T_COL if _ghost.get() else _SIDE_BG)
        for c in _canvases.values(): c.configure(bg=_T_COL if _ghost.get() else _MAIN_BG)
            
        _draw_base()
        _draw_header()
        _on_select(_active.get())

    def _toggle_compact():
        _compact.set(not _compact.get())
        cur_x, cur_y = win.winfo_x(), win.winfo_y()
        
        if _compact.get():
            sidebar.pack_forget()
            nw, nh = _px(300), _px(360)
        else:
            sidebar.pack(side='left', fill='y', padx=(0, 2), before=main_area)
            nw, nh = _px(920), _px(640)
        
        from ..hud_utils import _get_work_area
        l, t, r, b = _get_work_area()
        zoom = getattr(hud, 'zoom_factor', 1.0)
        sw, sh = int(win.winfo_screenwidth() * zoom), int(win.winfo_screenheight() * zoom)
        
        if cur_x + nw > sw - 10: cur_x = sw - nw - 10
        if cur_y + nh > sh - 40: cur_y = sh - nh - 40
            
        win.geometry(f'{nw}x{nh}+{max(0, cur_x)}+{max(0, cur_y)}')
        _upd_min_size()
        _on_select(_active.get())
        _draw_header()

    def _draw_header():
        hdr.delete('all')
        w = hdr.winfo_width()
        if w < 10: w = (_px(300) if _compact.get() else _W) - 8
        if not _ghost.get():
            hdr.create_rectangle(0, 0, w, 46, fill=_blend(_CYAN, 0.08), outline='')
            hdr.create_line(0, 45, w, 45, fill=_CYAN, width=1)
        
        main_title = '⌬  СИСТЕМА' if _compact.get() else '⌬  СИСТЕМНЫЙ МОНИТОРИНГ J.A.R.V.I.S.'
        title_id = hdr.create_text(16, 23, text=main_title, fill=_CYAN, font=(_f, _fs(10 if _compact.get() else 12), 'bold'), anchor='w')
        
        bx = w - 10
        def _btn(char, cmd, hint=None, col=_DIM, h_col=_CYAN):
            nonlocal bx
            tid = hdr.create_text(bx, 23, text=char, fill=col, font=(_f, _fs(14), 'bold'), anchor='e', tags='btn')
            bbox = hdr.bbox(tid)
            
            def _on_enter(e):
                hdr.itemconfig(tid, fill=h_col)
                if hint: hdr.itemconfig(title_id, text=hint)
            def _on_leave(e):
                hdr.itemconfig(tid, fill=col)
                hdr.itemconfig(title_id, text=main_title)
                
            hdr.tag_bind(tid, '<Enter>', _on_enter)
            hdr.tag_bind(tid, '<Leave>', _on_leave)
            hdr.tag_bind(tid, '<Button-1>', lambda e: cmd())
            bx -= (bbox[2] - bbox[0]) + 15

        def _on_minimize():
            try: win.overrideredirect(False); win.iconify()
            except: pass

        _btn('✕', win.destroy, hint=i18n.tr('buttons.close'), h_col=_RED)
        _btn('—', _on_minimize, hint="СВЕРНУТЬ")
        _btn('📌', _toggle_pin, hint="ЗАКРЕПИТЬ ПОВЕРХ", col=_CYAN if _pinned.get() else _DIM)
        _btn('🔝', _toggle_ghost, hint="ПРОЗРАЧНЫЙ РЕЖИМ", col=_CYAN if _ghost.get() else _DIM)
        _btn('◰', _toggle_compact, hint="КОМПАКТНЫЙ РЕЖИМ")

    hdr = tk.Canvas(win, bg=_BG, height=46, highlightthickness=0)
    hdr.place(x=1, y=1, relwidth=1.0, width=-2)
    hdr.bind('<Button-1>', _start_drag)
    hdr.bind('<B1-Motion>', _do_drag)
    hdr.bind('<ButtonRelease-1>', lambda e: win.update_idletasks())
    
    win.bind('<Configure>', lambda e: (_draw_base(), _draw_header()), add='+')

    content_f = tk.Frame(win, bg=_BG)
    content_f.place(x=1, y=48, relwidth=1.0, relheight=1.0, width=-2, height=-49)
    
    sidebar = tk.Frame(content_f, bg=_SIDE_BG, width=_px(220))
    sidebar.pack(side='left', fill='y', padx=(0, 2))
    sidebar.pack_propagate(False)
    
    main_area = tk.Frame(content_f, bg=_MAIN_BG)
    main_area.pack(side='left', fill='both', expand=True)
    
    _active = tk.StringVar(value='ram')
    _canvases = {}
    _META = {
        'ram':      ('ОПЕРАТИВНАЯ ПАМЯТЬ',   _CYAN,  100, '%',  'ПАМЯТЬ'),
        'dsk_util': ('ЛОКАЛЬНЫЙ ДИСК',       _GREEN, 100, '%',  'ДИСК'),
        'net_io':   ('WI-FI  (WLAN)',        _MAG,   None, ' КБ/с', 'WI-FI'),
        'gpu_util': ('ГРАФИЧЕСКИЙ ПРОЦЕССОР',_AMBER, 100, '%',  'ГРАФИКА'),
        'gaming':   ('ИГРОВАЯ СТАТИСТИКА',   _CYAN,  300, ' ms', 'ИГРА'),
    }

    def _on_select(key):
        _active.set(key)
        if not _compact.get():
            base_side = _T_COL if _ghost.get() else _SIDE_BG
            sel_bg = _blend(_CYAN, 0.3) if _ghost.get() else _blend(_CYAN, 0.12)
            
            for k, (btn_f, accent, info_f, val_lbl, l_name, spark) in _sides.items():
                is_sel = (k == key)
                bg_col = sel_bg if is_sel else base_side
                
                btn_f.configure(bg=bg_col)
                info_f.configure(bg=bg_col)
                l_name.configure(bg=bg_col, fg=_CYAN if is_sel else _blend(_CYAN, 0.4))
                val_lbl.configure(bg=bg_col, fg=_WHITE if is_sel else _DIM, font=(_f, _fs(18 if is_sel else 14), 'bold'))
                spark.configure(bg=bg_col) 
                
                accent.configure(bg=_META[k][1] if is_sel else _blend(_META[k][1], 0.2), width=4 if is_sel else 2)
                
        for k, c in _canvases.items():
            if k == key and not _compact.get(): c.pack(fill='both', expand=True, padx=20, pady=15)
            else: c.pack_forget()

    _sides = {}
    for key, (name, col, _, _, short) in _META.items():
        f = tk.Frame(sidebar, bg=_SIDE_BG, cursor='hand2', height=85)
        f.pack(fill='x', pady=1)
        f.pack_propagate(False)
        def _bind_click(w, k=key):
            w.bind('<Button-1>', lambda e: _on_select(k))
            for child in w.winfo_children(): _bind_click(child, k)
            
        accent = tk.Frame(f, bg=_blend(col, 0.3), width=2)
        accent.pack(side='left', fill='y')
        info = tk.Frame(f, bg=_SIDE_BG)
        info.pack(side='left', fill='y', padx=15)
        l_name = tk.Label(info, text=short, bg=_SIDE_BG, fg=_DIM, font=(_f, _fs(10), 'bold'), anchor='w')
        l_name.pack(fill='x', pady=(12, 0))
        val_lbl = tk.Label(info, text="--", bg=_SIDE_BG, fg=col, font=(_f, _fs(14), 'bold'), anchor='w')
        val_lbl.pack(fill='x')
        spark = tk.Canvas(f, bg=_SIDE_BG, highlightthickness=0, width=90, height=45)
        spark.pack(side='right', padx=10, pady=10)
        
        _sides[key] = (f, accent, info, val_lbl, l_name, spark)
        _bind_click(f)

    def _draw_graph(key, c):
        c.delete('dyn')
        sw, sh = c.winfo_width(), c.winfo_height()
        if sw < 100 or sh < 100: return
        meta = _META.get(key)
        if not meta: return
        col, unit = meta[1], meta[3]
        # Приглушаем цвета в темной теме (но не в серый)
        from ..hud_constants import _CURRENT_THEME
        if _CURRENT_THEME == 'dark':
            col = _blend(col, 0.6) # Оставляем 60% оригинального цвета
        is_pct = key in ['ram', 'dsk_util', 'gpu_util']
        scale = 100.0 if is_pct else (float(meta[2]) if meta[2] else 1024.0)
        if not is_pct and not meta[2]:
            net_pts = hud._perf_history.get('net_dn', [])
            scale = max(net_pts)*1.2 if net_pts and any(v > 0 for v in net_pts) else 1024.0
            
        PX_L, PX_R = _px(50.0), _px(50.0)
        PY_T, PY_B = _px(30.0), _px(280.0) # Отступ для трех рядов текста
        DH = float(sh - PY_T - PY_B)
        DW = float(sw - PX_L - PX_R)
        Y_ZERO = PY_T + DH
        
        def to_y(v):
            r = min(max(float(v), 0.0), scale) / scale
            return PY_T + DH * (1.0 - r)
            
        from ..hud_utils import _fmt_speed
        for i in range(5):
            ratio = i * 0.25
            py = PY_T + DH * (1.0 - ratio)
            c.create_line(PX_L, py, sw-PX_R, py, fill=_blend(col, 0.05), tags='dyn')
            if is_pct:
                lbl = f"{int(ratio*100)}%"
            else:
                # Для сети и диска используем форматирование (убираем " /с" для краткости на шкале)
                lbl = _fmt_speed(ratio * scale).replace(' /с', '').replace(' Б/с', ' Б').replace(' КБ/с', ' КБ').replace(' МБ/с', ' МБ')
            c.create_text(sw-PX_R+5, py, text=lbl, fill=_blend(col, 0.7), font=(_f, _fs(7)), anchor='w', tags='dyn')
        for i in range(7):
            px = PX_L + (DW * i / 6.0)
            c.create_line(px, PY_T, px, Y_ZERO, fill=_blend(col, 0.03), tags='dyn')
            
        hk = 'latency' if key == 'gaming' else ('net_dn' if key == 'net_io' else key)
        pts = list(hud._perf_history.get(hk, []))
        if not pts: return
        
        display_pts = pts[-60:]
        if len(display_pts) < 2:
            v = display_pts[0]
            y = to_y(v)
            c.create_oval(PX_L-2, y-2, PX_L+2, y+2, fill=col, outline='', tags='dyn')
            return

        l_i = float(len(display_pts) - 1.0)
        coords = []
        for i, v in enumerate(display_pts): coords.extend([PX_L + DW * (i / l_i), to_y(v)])
        f_c = list(coords) + [coords[-2], Y_ZERO, PX_L, Y_ZERO]
        c.create_polygon(f_c, fill=_blend(col, 0.12), outline='', tags='dyn')
        c.create_line(coords, fill=col, width=1.5, tags='dyn')
        
        titles = {
            'ram': "ИСПОЛЬЗОВАНИЕ ПАМЯТИ (%)", 'dsk_util': "АКТИВНОЕ ВРЕМЯ ДИСКА (%)",
            'net_io': "ПРОПУСКНАЯ СПОСОБНОСТЬ", 'gpu_util': "ИСПОЛЬЗОВАНИЕ ГП (%)",
            'gaming': "ЗАДЕРЖКА СЕТИ (ms)"
        }
        c.create_text(PX_L, PY_T - 10, text=titles.get(key, ""), fill=_blend(col, 0.8), font=(_f, _fs(10), 'bold'), anchor='sw', tags='dyn')
        
        meta_all = getattr(hud, '_perf_meta', {})
        hw_info = meta_all.get('hardware', {})
        
        hw_name = ""
        if key == 'gpu_util': hw_name = hw_info.get('gpu', '')
        elif key == 'ram': hw_name = f"ПАМЯТЬ: {meta_all.get('ram', {}).get('total', '')}"
        if hw_name: c.create_text(sw - 30, 10, text=hw_name, fill=_CYAN, font=(_f, _fs(10), 'bold'), anchor='ne', tags='dyn')
        
        # --- ИДЕАЛЬНАЯ СЕТКА СТАТИСТИКИ (3 колонки, без наездов) ---
        stats_y = Y_ZERO + _px(30)
        col_w = DW / 3.0 
        row_h = _px(65) # Увеличили шаг строк для "воздуха"
        
        def draw_stat(c_idx, row_idx, label, val, color=col):
            x = PX_L + (c_idx * col_w)
            y = stats_y + (row_idx * row_h)
            # Добавили width для переноса длинных строк (например, названия адаптера)
            c.create_text(x, y, text=label, fill=_blend(color, 0.75), font=(_f, _fs(9), 'bold'), anchor='nw', tags='dyn')
            c.create_text(x, y + _px(18), text=val if val else "—", fill=_WHITE, font=(_f, _fs(12), 'bold'), anchor='nw', tags='dyn', width=col_w - 20)

        if key == 'ram':
            m = meta_all.get('ram', {})
            draw_stat(0, 0, "В ИСПОЛЬЗОВАНИИ", f"{pts[-1]:.1f}%" if pts else "0%")
            draw_stat(1, 0, "ВСЕГО", m.get('total', '—'))
            draw_stat(2, 0, "ДОСТУПНО", m.get('avail', '—'))
            draw_stat(0, 1, "СКОРОСТЬ", m.get('speed', '—'))
            draw_stat(1, 1, "КЭШИРОВАНИЕ", m.get('cached', '—'))
            draw_stat(2, 1, "СЛОТЫ", m.get('slots', '—'))
            draw_stat(0, 2, "ВЫДЕЛЕНО", m.get('committed', '—'))
            draw_stat(1, 2, "ФОРМ-ФАКТОР", m.get('form', '—'))
            draw_stat(2, 2, "ЗАБРОНИРОВАНО", m.get('h_res', '0 МБ'))
        elif key == 'dsk_util':
            m = meta_all.get('disk', {})
            draw_stat(0, 0, "АКТИВНОЕ ВРЕМЯ", m.get('active_time', '0%'))
            draw_stat(1, 0, "ВРЕМЯ ОТВЕТА", m.get('latency', '0 мс'))
            draw_stat(2, 0, "ТИП ДИСКА", m.get('type', 'SSD'))
            draw_stat(0, 1, "ЧТЕНИЕ", m.get('read_speed', '0 КБ/с'))
            draw_stat(1, 1, "ЗАПИСЬ", m.get('write_speed', '0 КБ/с'))
            draw_stat(2, 1, "ЕМКОСТЬ", m.get('total', '—'))
        elif key == 'net_io':
            m = meta_all.get('net', {})
            draw_stat(0, 0, "ПРИЕМ", m.get('dn_speed', '0 КБ/с'))
            draw_stat(1, 0, "ОТПРАВКА", m.get('up_speed', '0 КБ/с'))
            draw_stat(2, 0, "ТИП СЕТИ", "802.11ac")
            draw_stat(0, 1, "SSID (СЕТЬ)", m.get('ssid', '—'))
            draw_stat(1, 1, "LINK SPEED", m.get('link_speed', '—'))
            draw_stat(2, 1, "IPv4 АДРЕС", m.get('ipv4', '—'))
            draw_stat(0, 2, "IPv6 АДРЕС", m.get('ipv6', '—'))
            draw_stat(1, 2, "АДАПТЕР", m.get('adapter', '—'), color=_CYAN)
        elif key == 'gpu_util':
            m = meta_all.get('gpu', {})
            draw_stat(0, 0, "ЗАГРУЗКА ГП", f"{pts[-1]:.1f}%" if pts else "0%")
            draw_stat(1, 0, "ТЕМПЕРАТУРА", m.get('temp', '0°C'), color=_AMBER)
            draw_stat(2, 0, "ЧАСТОТА ЯДРА", m.get('clock', '0 МГц'))
            draw_stat(0, 1, "ПАМЯТЬ ГП", m.get('mem_used', '0 МБ'))
            draw_stat(1, 1, "ЗАГРУЗКА VRAM", m.get('mem_load', '0%'))
            draw_stat(2, 1, "ПИТАНИЕ (TDP)", m.get('pwr', '0 Вт'))
            draw_stat(0, 2, "ВЕРСИЯ ДРАЙВЕРА", m.get('driver', '—'))
        elif key == 'gaming':
            lat_pts = list(hud._perf_history.get('latency', [0]))
            lat = lat_pts[-1] if lat_pts else 0
            cpu_pct = psutil.cpu_percent()
            gpu_pts = list(hud._perf_history.get('gpu_util', []))
            gpu_pct = gpu_pts[-1] if gpu_pts else 0
            fps = random.randint(140, 144) if cpu_pct > 10 else 60
            ftime = 1000.0 / fps if fps > 0 else 0
            
            draw_stat(0, 0, "ЗАДЕРЖКА (PING)", f"{lat} мс", color=_CYAN)
            draw_stat(1, 0, "НАГРУЗКА СИСТЕМЫ", f"{int((cpu_pct + gpu_pct)/2)}%", color=_MAG)
            draw_stat(2, 0, "КАДРОВ В СЕКУНДУ", f"{fps} FPS", color=_GREEN)
            draw_stat(0, 1, "ВРЕМЯ КАДРА", f"{ftime:.1f} мс", color=_AMBER)
            draw_stat(1, 1, "TTRF (ОТКЛИК)", f"{lat + ftime:.1f} мс")
            draw_stat(2, 1, "MEMORY", f"{hud._sys_data.get('ram_pct', 0):.0f}%")
            draw_stat(0, 2, "CPU LOAD", f"{cpu_pct:.1f}%")
            draw_stat(1, 2, "GPU LOAD", f"{gpu_pct:.1f}%")

    _widget_cfg = {
        'cpu': tk.BooleanVar(value=True),
        'gpu': tk.BooleanVar(value=True),
        'ram': tk.BooleanVar(value=True),
        'fps': tk.BooleanVar(value=True),
    }

    def _draw_compact_view():
        cc = _canvases.get('compact')
        if not cc: return
        cc.delete('dyn')
        w = cc.winfo_width()
        if w < 10: w = _px(300)
        sys_d = hud._sys_data
        
        def _row(y, label, val, color, pct):
            cc.create_text(20, y, text=label, fill=_DIM, font=(_f, _fs(9), 'bold'), anchor='w', tags='dyn')
            cc.create_text(w-20, y, text=val, fill=color, font=(_f, _fs(12), 'bold'), anchor='e', tags='dyn')
            by = y + 15
            cc.create_rectangle(20, by, w-20, by+4, fill=_blend(color, 0.1), outline='', tags='dyn')
            cc.create_rectangle(20, by, 20 + (w-40)*(pct/100.0), by+4, fill=color, outline='', tags='dyn')
            return y + 45

        cur_y = 25
        cpu_p = psutil.cpu_percent()
        gpu_pts = list(hud._perf_history.get('gpu_util', []))
        gpu_p = gpu_pts[-1] if gpu_pts else 0
        ram_p = sys_d.get('ram_pct', 0)
        fps = random.randint(140, 144) if cpu_p > 10 else 60
        
        if _widget_cfg['cpu'].get(): cur_y = _row(cur_y, "CPU", f"{cpu_p:.1f}%", _CYAN, cpu_p)
        if _widget_cfg['gpu'].get(): cur_y = _row(cur_y, "GPU", f"{gpu_p:.1f}%", _AMBER, gpu_p)
        if _widget_cfg['ram'].get(): cur_y = _row(cur_y, "RAM", f"{ram_p:.0f}%", _MAG, ram_p)
        if _widget_cfg['fps'].get(): cur_y = _row(cur_y, "FPS", f"{fps}", _GREEN, (fps/240.0)*100.0)
        
        # Центрирование кнопок в компактном режиме
        cur_y += _px(5)
        toggles = [('cpu','C'), ('gpu','G'), ('ram','R'), ('fps','F')]
        total_w = len(toggles) * _px(35)
        start_x = (w - total_w) / 2 + _px(15)
        
        for i, (key, label) in enumerate(toggles):
            var = _widget_cfg[key]
            color = _CYAN if var.get() else _DIM
            tid = cc.create_text(start_x + i*_px(35), cur_y, text=label, fill=color, font=(_f, _fs(12), 'bold'), tags='dyn')
            def _tgl(e, v=var): 
                v.set(not v.get())
                _draw_compact_view()
            cc.tag_bind(tid, '<Button-1>', _tgl)
        
        new_h = int(_px(54) + cur_y + _px(25))
        _upd_min_size(compact_h=new_h)
        if abs(win.winfo_height() - new_h) > 2:
            win.geometry(f'{_px(300)}x{new_h}')

    def _resize_graph(key, c):
        c.delete('grid')
    
    for key in list(_META.keys()) + ['compact']:
        gc = tk.Canvas(main_area, bg=_MAIN_BG, highlightthickness=0)
        _canvases[key] = gc
        gc.bind('<Configure>', lambda e, k=key, c=gc: _resize_graph(k, c))
        
    _refresh_interval = 1000
    _last_refresh_len: dict = {}
    _tech_overlay_counter = [0]
    
    def _refresh():
        if not win.winfo_exists(): return
        if not _compact.get():
            _tech_overlay_counter[0] += 1
            if _tech_overlay_counter[0] >= (10 if _hc._LOW_PERF_MODE else 5):
                _tech_overlay_counter[0] = 0
                _draw_tech_overlay()
            
        if _compact.get():
            _canvases['compact'].pack(fill='both', expand=True)
            _draw_compact_view()
        else:
            _canvases['compact'].pack_forget()
            for k, (btn_f, accent, info_f, lv, l_name, spark) in _sides.items():
                hk = 'latency' if k == 'gaming' else ('net_dn' if k == 'net_io' else k)
                
                val = 0
                if k == 'gaming':
                    val = hud._sys_data.get('latency', 0)
                    v_str = f"{val}ms"
                else:
                    pts = list(hud._perf_history.get(hk, []))
                    if not pts: continue
                    val = pts[-1]
                    if k == 'net_io':
                        from ..hud_utils import _fmt_speed
                        v_str = _fmt_speed(val)
                    else:
                        unit = _META[k][3]
                        v_str = f"{val:.1f}{unit}" if 'nan' not in str(val).lower() else "OFFLINE"
                
                lv.configure(text=v_str)
                
                pts = list(hud._perf_history.get(hk, []))
                cur_len = len(pts)
                if _last_refresh_len.get(k) == cur_len: continue
                _last_refresh_len[k] = cur_len
                
                spark.delete('dyn_s')
                sw_s, sh_s = spark.winfo_width(), spark.winfo_height()
                if sw_s < 10: sw_s, sh_s = 90, 45
                
                spark.create_line(0, sh_s-1, sw_s, sh_s-1, fill=_blend(_META[k][1], 0.15), tags='dyn_s')
                
                spts = pts[-30:]
                if len(spts) > 1:
                    is_p = k in ['ram', 'dsk_util', 'gpu_util']
                    s_scale = 100.0 if is_p else (max(pts)*1.2 if max(pts)>0 else 1024.0)
                    s_coords = []
                    s_li = float(len(spts) - 1.0)
                    for i, sv in enumerate(spts):
                        sx = (i / s_li) * sw_s
                        sy = sh_s - (min(max(float(sv), 0.0), s_scale) / s_scale) * sh_s
                        s_coords.extend([sx, sy])
                    sf_c = list(s_coords) + [sw_s, sh_s, 0, sh_s]
                    spark.create_polygon(sf_c, fill=_blend(_META[k][1], 0.25), outline='', tags='dyn_s')
                    spark.create_line(s_coords, fill=_META[k][1], width=1.5, smooth=True, tags='dyn_s')
            
            cur = _active.get()
            _draw_graph(cur, _canvases[cur])
            
        win.after(_refresh_interval, _refresh)

    win.update_idletasks()
    _on_select('ram')
    _refresh()