import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar
from ui.hud_widgets import _HudScrollbar

def build_appearance_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
    def _add_context_menu(entry):
        menu = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, _sf(9)))
        def _paste():
            try:
                import pyperclip
                txt = pyperclip.paste()
                if txt:
                    if entry.selection_present():
                        entry.delete('sel.first', 'sel.last')
                    entry.insert(tk.INSERT, txt)
            except Exception: pass
        def _copy():
            try:
                if entry.selection_present():
                    win.clipboard_clear()
                    win.clipboard_append(entry.selection_get())
            except Exception: pass
        def _select_all():
            entry.select_range(0, 'end')
            entry.icursor('end')
        menu.add_command(label='Вставить (Ctrl+V)', command=_paste)
        menu.add_command(label='Копировать (Ctrl+C)', command=_copy)
        menu.add_separator()
        menu.add_command(label='Выделить всё (Ctrl+A)', command=_select_all)
        def _show_menu(e):
            menu.tk_popup(e.x_root, e.y_root)
        entry.bind('<Button-3>', _show_menu)
        entry.bind('<Control-v>', lambda e: (_paste(), 'break'))
        entry.bind('<Control-V>', lambda e: (_paste(), 'break'))
        entry.bind('<Control-a>', lambda e: (_select_all(), 'break'))
        entry.bind('<Control-A>', lambda e: (_select_all(), 'break'))
    def _card(icon: str, title: str, accent: str):
        outer = tk.Frame(inner, bg=_PANEL, highlightbackground=_blend(accent, 0.2), highlightthickness=1)
        outer.pack(fill='x', padx=20, pady=(14, 0))
        tk.Frame(outer, bg=accent, width=3).pack(side='left', fill='y')
        body = tk.Frame(outer, bg=_PANEL)
        body.pack(side='left', fill='both', expand=True, padx=(16, 18), pady=(14, 14))
        head = tk.Frame(body, bg=_PANEL)
        head.pack(fill='x', pady=(0, 6))
        tk.Label(head, text=icon, bg=_PANEL, fg=accent, font=(hud._F, _sf(16))).pack(side='left', padx=(0, 10))
        tk.Label(head, text=title, bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='w').pack(side='left')
        return body
    def _hint(parent, text: str):
        lbl = tk.Label(
            parent,
            text=text,
            bg=_PANEL,
            fg=_blend(_TEXT, 0.72),
            font=(hud._F, _sf(10)),
            anchor='w',
            justify='left',
        )
        lbl.pack(fill='x', pady=(0, 8))
        def _upd_hint(e, l=lbl):
            new_wl = max(hud._px(100), e.width - hud._px(8))
            l.configure(wraplength=new_wl)
        parent.bind('<Configure>', _upd_hint, add='+')
        def _try_init_wrap(tries_left: int = 10):
            try:
                w = int(parent.winfo_width() or 0)
            except Exception:
                w = 0
            if w > 1:
                _upd_hint(type('E', (), {'width': w})())
                return
            if tries_left > 0:
                parent.after(30, lambda: _try_init_wrap(tries_left - 1))
        parent.after(10, _try_init_wrap)
    def _label_row(parent, label: str, accent: str):
        row = tk.Frame(parent, bg=_PANEL)
        row.pack(fill='x', pady=(6, 0))
        
        lbl = tk.Label(row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11), 'bold'), anchor='w', justify='left')
        lbl.pack(side='left', fill='x', expand=True, anchor='nw')
        
        val_lbl = tk.Label(row, text='', bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='e', justify='right')
        val_lbl.pack(side='right', padx=(10, 0), anchor='ne')
        
        _last_row_w = [0]
        def _upd_row(e, l=lbl, v=val_lbl):
            if abs(e.width - _last_row_w[0]) < 10: return
            _last_row_w[0] = e.width
            # Dynamic wrap based on value width
            v_req = v.winfo_reqwidth()
            l.configure(wraplength=max(100, e.width - (v_req + 20)))
            if v_req > e.width * 0.6:
                v.configure(wraplength=int(e.width * 0.4))
            else:
                v.configure(wraplength=0)
                
        row.bind('<Configure>', _upd_row, add='+')
        return val_lbl
    def _slider(parent, from_, to, steps, accent, init_val, callback):
        container = tk.Frame(parent, bg=_PANEL)
        container.pack(fill='x', pady=(10, 4))
        
        # Neural Scale (Ticks) - Defined first to use in callback
        scale_canvas = tk.Canvas(container, height=10, bg=_PANEL, highlightthickness=0)
        scale_canvas.pack(side='bottom', fill='x', pady=(2, 0))

        def _draw_ticks(current_val=None):
            scale_canvas.delete('all')
            w = scale_canvas.winfo_width()
            if w <= 1: return
            
            num_ticks = steps if steps and steps < 30 else 20
            progress = (current_val - from_) / (to - from_) if current_val is not None else (init_val - from_) / (to - from_)
            
            for i in range(num_ticks + 1):
                f = i / num_ticks
                x = f * (w - 20) + 10
                is_milestone = i in (0, num_ticks // 2, num_ticks)
                h = 6 if is_milestone else 3
                is_active = f <= (progress + 0.01)
                color = accent if is_active else _blend(accent, 0.25)
                width = 2 if is_milestone and is_active else 1
                scale_canvas.create_line(x, 0, x, h, fill=color, width=width)
        
        def _on_change(v):
            _draw_ticks(float(v))
            callback(v)

        s = ctk.CTkSlider(
            container, from_=from_, to=to, number_of_steps=steps,
            progress_color=accent, button_color=_WHITE, button_hover_color=accent,
            fg_color=_blend(accent, 0.1), height=hud._px(12),
            border_width=hud._px(2), border_color=_blend(accent, 0.2),
            command=_on_change
        )
        s.set(init_val)
        s.pack(side='top', fill='x')
        scale_canvas.bind('<Configure>', lambda e: _draw_ticks(s.get()))
        return s
    def _std_action_btn(parent, *, text: str, command, accent: str, **grid_kw):
        b = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=hud._px(44),
            font=(hud._F, _sf(10), 'bold'),
            fg_color=_blend(accent, 0.08),
            hover_color=_blend(accent, 0.18),
            text_color=accent,
            border_color=_blend(accent, 0.32),
            border_width=1,
            corner_radius=10,
        )
        b.grid(**grid_kw)
        return b
    def _pick_app_dialog(on_selected):
        """Reusable premium app picker dialog."""
        from core.system.windows import get_installed_apps
        apps = get_installed_apps()
        pick_win = ctk.CTkToplevel(win)
        pick_win.title("ВЫБОР ПРИЛОЖЕНИЯ")
        pick_win.geometry(f"{hud._px(600)}x{hud._px(700)}")
        pick_win.configure(bg=_BG)
        _set_dark_title_bar(pick_win)
        pick_win.attributes("-topmost", True)
        pick_win.lift()
        top_bar = tk.Frame(pick_win, bg=_BG)
        top_bar.pack(fill='x', padx=20, pady=(20, 10))
        tk.Label(top_bar, text="ВЫБЕРИТЕ ПРИЛОЖЕНИЕ", bg=_BG, fg=_CYAN, font=(hud._F, _sf(14), 'bold')).pack(anchor='w')
        tk.Label(top_bar, text="Выберите программу для добавления в список", bg=_BG, fg=_DIM, font=(hud._F, _sf(10))).pack(anchor='w')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text='Поиск...', font=(hud._F, _sf(11)), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=hud._px(44), corner_radius=10)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        sw_all = ctk.CTkSwitch(ctrl_f, text='Системные', variable=_show_all_var, font=(hud._F, _sf(10), 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=hud._px(36), switch_height=hud._px(18))
        sw_all.pack(side='right')
        lb_frame = tk.Frame(pick_win, bg=_BG, highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
        lb_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
        lb = tk.Listbox(lb_frame, bg=_BG, fg=_TEXT, font=(hud._F, _sf(11)), borderwidth=0, highlightthickness=0, selectbackground=_blend(_CYAN, 0.3), activestyle='none')
        sb = _HudScrollbar(lb_frame, lb, color=_CYAN)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        _f_data = []
        def _refresh(*_):
            lb.delete(0, tk.END)
            search = ent_search.get().lower().strip()
            show_all = _show_all_var.get()
            _f_data.clear()
            ides = [a for a in apps if a.get('is_ide')]
            others = [a for a in apps if not a.get('is_ide')]
            for app in ides + others:
                if app.get('is_noise') and not show_all: continue
                if search and search not in app['name'].lower() and search not in (app.get('exe') or '').lower(): continue
                prefix = "✦ " if app.get('is_ide') else "  "
                exe_part = f" — {app['exe']}" if app.get('exe') else ""
                lb.insert(tk.END, f"{prefix}{app['name']}{exe_part}")
                _f_data.append(app)
        ent_search.bind('<KeyRelease>', _refresh)
        sw_all.configure(command=_refresh)
        _refresh()
        def _on_pick(_e=None):
            sel = lb.curselection()
            if sel:
                app = _f_data[sel[0]]
                on_selected(app.get('exe') or app['name'])
                pick_win.destroy()
        lb.bind('<Double-Button-1>', _on_pick)
        ctk.CTkButton(pick_win, text="ВЫБРАТЬ ПРИЛОЖЕНИЕ", command=_on_pick, height=hud._px(50), font=(hud._F, _sf(12), 'bold'), fg_color=_CYAN, text_color=_BG).pack(fill='x', padx=20, pady=(0, 20))

    def _on_theme_change(name):
        from ui.hud_themes import save_theme_name
        save_theme_name(name)
        # Also update hud settings
        hud._settings['theme'] = name
        _save_hud_settings(hud._settings)
        _show_restart_notice(name)

    def _show_restart_notice(name):
        # Show a restart notice banner
        for w in restart_f.winfo_children():
            w.destroy()
        names = {'cyber': 'CYBER NEON', 'dark': 'PURE DARK', 'light': 'PURE LIGHT'}
        tk.Label(
            restart_f,
            text=f'✓  Тема «{names.get(name, name)}» збережена. Потрібен перезапуск.',
            bg=_blend(_GREEN, 0.08), fg=_GREEN,
            font=(hud._F, _sf(9), 'bold'), anchor='w'
        ).pack(side='left', fill='x', expand=True, padx=12, pady=8)
        def _restart():
            import subprocess, sys
            subprocess.Popen([sys.executable] + sys.argv)
            win.after(200, lambda: __import__('os')._exit(0))
        ctk.CTkButton(
            restart_f, text='↺  ПЕРЕЗАПУСТИТИ', command=_restart,
            height=hud._px(34), font=(hud._F, _sf(9), 'bold'),
            fg_color=_blend(_GREEN, 0.15), hover_color=_blend(_GREEN, 0.25),
            text_color=_GREEN, border_color=_blend(_GREEN, 0.5),
            border_width=1, corner_radius=8, width=hud._px(160)
        ).pack(side='right', padx=8, pady=6)
        restart_f.pack(fill='x', pady=(6, 0))

    c0 = _card('◐', 'ЦВЕТ. ТЕМА (перезапуск)', _CYAN)
    _hint(c0, 'Тема застосовується повністю після перезапуску. Обрана зберігається автоматично.')

    curr_theme = hud._settings.get('theme', 'cyber')

    theme_f = tk.Frame(c0, bg=_PANEL)
    theme_f.pack(fill='x', pady=(5, 4))
    for i in range(3):
        theme_f.columnconfigure(i, weight=1)

    # Theme definitions: (id, label, accent_color, bg_preview, text_preview)
    _theme_defs = [
        ('cyber', '⬡  CYBER\nNEON',  '#00ffff', '#0a0b10', '#00ffff'),
        ('dark',  '◼  PURE\nDARK',   '#4da6ff', '#0d0d0d', '#e8e8e8'),
        ('light', '◻  PURE\nLIGHT',  '#0055cc', '#f4f6fa', '#1a1a2e'),
    ]

    def _blend_hex(c1, c2, alpha):
        r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
        r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
        return '#{:02x}{:02x}{:02x}'.format(
            int(r1 + (r2 - r1) * alpha),
            int(g1 + (g2 - g1) * alpha),
            int(b1 + (b2 - b1) * alpha)
        )

    for i, (tid, tname, accent, tbg, tfg) in enumerate(_theme_defs):
        is_sel = (tid == curr_theme)
        padx = (0, 4) if i == 0 else (4, 4) if i == 1 else (4, 0)
        t_btn = ctk.CTkButton(
            theme_f, text=tname,
            command=lambda n=tid: _on_theme_change(n),
            height=hud._px(64),
            font=(hud._F, _sf(8), 'bold'),
            fg_color=tbg,
            hover_color=_blend_hex(tbg, accent, 0.25),
            text_color=tfg if not is_sel else accent,
            border_color=accent if is_sel else '#333333',
            border_width=2 if is_sel else 1,
            corner_radius=10
        )
        t_btn.grid(row=0, column=i, padx=padx, sticky='ew')

    # Restart notice frame (hidden until needed)
    restart_f = tk.Frame(c0, bg=_blend(_GREEN, 0.08),
                         highlightbackground=_blend(_GREEN, 0.3), highlightthickness=1)


    c1 = _card('◈', 'ОТОБРАЖЕНИЕ', _CYAN)
    _zoom_val_lbl = _label_row(c1, 'Масштаб интерфейса', _CYAN)
    _zoom_val_lbl.configure(text=f'{hud.zoom_factor:.1f}×')
    _hint(c1, 'Ctrl + +/−  быстро  •  Ctrl+0 сброс  •  ✦ Авто определит масштаб по экрану')
    _zoom_timer_id = [None]
    def _apply_zoom(z: float) -> None:
        ctk.set_widget_scaling(z)
        hud.zoom_factor = z
        hud._settings['zoom_factor'] = z
        _save_hud_settings(hud._settings)
        zoom_slider.set(z)
        hud._apply_zoom_rebuild()

    def _on_zoom_slide(v):
        z = round(float(v), 1)
        _zoom_val_lbl.configure(text=f'{z:.1f}×')
        if _zoom_timer_id[0]:
            win.after_cancel(_zoom_timer_id[0])
        def _trigger():
            if abs(z - hud.zoom_factor) >= 0.05:
                _apply_zoom(z)
            _zoom_timer_id[0] = None
        _zoom_timer_id[0] = win.after(300, _trigger)
    
    # Slider comes first now
    zoom_slider = _slider(c1, 0.6, 2.5, 19, _CYAN, hud.zoom_factor, _on_zoom_slide)

    _max_var = tk.BooleanVar(value=hud._settings.get('start_maximized', True))
    def _on_max():
        hud._settings['start_maximized'] = _max_var.get()
        _save_hud_settings(hud._settings)
    _max_row = tk.Frame(c1, bg=_BG, highlightthickness=1, highlightbackground=_blend(_CYAN, 0.2))
    _max_row.pack(fill='x', pady=(8, 12))
    _max_sw = ctk.CTkSwitch(
        _max_row,
        text='',
        variable=_max_var,
        command=_on_max,
        progress_color=_CYAN,
        fg_color=_BRD_I,
        button_color=_WHITE,
        switch_width=hud._px(48),
        switch_height=hud._px(24),
    )
    _max_sw.pack(side='right', padx=16, pady=12)
    _max_lbl = tk.Label(
        _max_row,
        text='Запуск во весь экран  ·  Автоматическое открытие HUD на весь основной монитор при старте системы',
        bg=_BG,
        fg=_TEXT,
        font=(hud._F, _sf(10), 'bold'),
        anchor='nw',
        justify='left',
    )
    _max_lbl.pack(side='left', fill='both', expand=True, padx=(16, 12), pady=12)
    def _upd_max_wrap(e, l=_max_lbl):
        margin = hud._px(160)
        avail = e.width - margin
        if avail > 100:
            l.configure(wraplength=avail)
    _max_row.bind('<Configure>', _upd_max_wrap, add='+')
    _max_lbl.bind('<Button-1>', lambda e: (_max_var.set(not _max_var.get()), _on_max()))
    btns_row = tk.Frame(c1, bg=_PANEL)
    btns_row.pack(fill='x', pady=(8, 12))
    z_btns = tk.Frame(btns_row, bg=_PANEL)
    z_btns.pack(anchor='center', fill='x')
    for zi in range(4):
        z_btns.columnconfigure(zi, weight=1, uniform='zoom_btns')
    
    _Z_OPTS = (
        ('−', -0.1, _CYAN),
        ('+', +0.1, _CYAN),
        ('↺ СБРОС', 1.0, _MAG),
        ('✦ АВТО', 0.0, _GREEN)
    )
    for col, (lbl, delta, color) in enumerate(_Z_OPTS):
        def _cb(d=delta):
            if d == 0.0:
                z = hud._auto_detect_zoom()
                hud._settings['zoom_factor'] = 0.0
                _save_hud_settings(hud._settings)
            else:
                z = round(hud.zoom_factor + d, 1) if d != 1.0 else 1.0
                z = max(0.6, min(2.5, z))
            _apply_zoom(z)
        
        padx_z = ((0, 6), (6, 6), (6, 6), (6, 0))[col]
        _std_action_btn(
            z_btns,
            text=lbl,
            command=_cb,
            accent=color,
            row=0,
            column=col,
            sticky='ew',
            padx=padx_z,
        )
    c2 = _card('◉', 'МОДУЛИ ИНТЕРФЕЙСА', _MAG)
    _hint(c2, 'Скрытые модули убираются из панели автоматически.')
    _vis_icons = {'sunrise': '☀', 'sysinfo': '◈', 'storage': '📊', 'network': '⟳', 'weather': '≋', 'clock': '🕐', 'camera': '📷', 'gamemode': '✦', 'meetings_btn': '🔗', 'videos_btn': '▶'}
    _vis_map = {'sunrise': 'Восход / Закат  (верхняя полоса)', 'sysinfo': 'Системные профили (Батарея / Мик)', 'storage': 'Аналитика хранилища (RAM / Диск)', 'network': 'Сетевая статистика', 'weather': 'Погода — Атмосфера', 'clock': 'Часы, дата и аптайм', 'camera': 'Видеосенсор (камера)', 'gamemode': 'Игровой режим', 'meetings_btn': 'Быстрые ссылки (кнопка в HUD)', 'videos_btn': 'Сохранённые видео (кнопка в HUD)'}
    _vis_vars: dict[str, tk.BooleanVar] = {}
    for key, label in _vis_map.items():
        var = tk.BooleanVar(value=hud._widget_vis.get(key, True))
        _vis_vars[key] = var
        sw_row = tk.Frame(c2, bg=_PANEL)
        sw_row.pack(fill='x', pady=4)
        icon_f = tk.Frame(sw_row, bg=_PANEL, width=hud._px(36), height=hud._px(36))
        icon_f.pack_propagate(False)
        icon_f.pack(side='left')
        tk.Label(icon_f, text=_vis_icons[key], bg=_PANEL, fg=_MAG, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
        sw = ctk.CTkSwitch(sw_row, text='', variable=var, onvalue=True, offvalue=False, fg_color=_BRD_I, progress_color=_MAG, button_color=_WHITE, switch_width=hud._px(48), switch_height=hud._px(24), width=0)
        sw.pack(side='left', padx=(4, 5))
        lbl = tk.Label(sw_row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(12), 'bold'), anchor='w', justify='left')
        lbl.pack(side='left', fill='x', expand=True, padx=(2, 0))
        def _upd_sw_wrap(e, l=lbl):
            # Safe margin for icons and switch
            avail = e.width - hud._px(120)
            l.configure(wraplength=max(60, avail))
        sw_row.bind('<Configure>', _upd_sw_wrap, add='+')
        def _on_vis_change(k=key, v=var):
            hud._widget_vis[k] = v.get()
            hud._settings['widget_vis'] = hud._widget_vis
            _save_hud_settings(hud._settings)
            if k in ('camera', 'sysinfo', 'gamemode', 'meetings_btn', 'videos_btn'):
                hud._rebuild_left()
            else:
                hud._rebuild_right()
            if k == 'sunrise':
                hud._apply_widget_visibility()
            if k == 'weather' and v.get():
                hud._weather_tick()
        sw.configure(command=lambda k=key, v=var: _on_vis_change(k, v))
        lbl.bind('<Button-1>', lambda e, k=key, v=var: (v.set(not v.get()), _on_vis_change(k, v)))
