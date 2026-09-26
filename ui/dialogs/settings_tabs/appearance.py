from ui.hud_style import JStyle
from core import i18n
import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
from ui.hud_widgets import _HudScrollbar
from ui.dialogs.extensions_common import _hud_popup_menu

def build_appearance_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
    _sfc = lambda n: n + 6
    def _add_context_menu(entry):
        def _paste() -> bool:
            try:
                import pyperclip
                txt = pyperclip.paste()
                if txt:
                    if entry.selection_present():
                        entry.delete('sel.first', 'sel.last')
                    entry.insert(tk.INSERT, txt)
                    return True
            except Exception:
                pass
            return False
        def _copy() -> bool:
            try:
                if entry.selection_present():
                    win.clipboard_clear()
                    win.clipboard_append(entry.selection_get())
                    return True
            except Exception:
                pass
            return False
        def _select_all() -> bool:
            try:
                entry.select_range(0, 'end')
                entry.icursor('end')
                return True
            except Exception:
                return False
        def _show_menu(e):
            _hud_popup_menu(win, e.x_root, e.y_root, hud, [
                (i18n.tr('context_menu.paste'), _paste),
                (i18n.tr('context_menu.copy'), _copy),
                None,
                (i18n.tr('context_menu.select_all'), _select_all),
            ])
        # Only 'break' when we actually handled it — otherwise Tk's native
        # <<Paste>>/<<SelectAll>> class bindings (Ctrl+V/Ctrl+A already work
        # by default on a plain Entry) get a chance to run instead of being
        # silently swallowed by our own failed attempt.
        entry.bind('<Button-3>', _show_menu)
        entry.bind('<Control-v>', lambda e: 'break' if _paste() else None)
        entry.bind('<Control-V>', lambda e: 'break' if _paste() else None)
        entry.bind('<Control-a>', lambda e: 'break' if _select_all() else None)
        entry.bind('<Control-A>', lambda e: 'break' if _select_all() else None)
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
            fg_color=_blend(accent, 0.1), height=12,
            border_width=2, border_color=_blend(accent, 0.2),
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
            height=JStyle.H_LARGE,
            font=(hud._F, JStyle.TEXT_BODY, 'bold'),
            fg_color=_blend(accent, 0.08),
            hover_color=_blend(accent, 0.18),
            text_color=_TEXT,
            border_color=_blend(accent, 0.32),
            border_width=1,
            corner_radius=JStyle.RAD_PANEL,
        )
        b.grid(**grid_kw)
        return b
    def _pick_app_dialog(on_selected):
        """Reusable premium app picker dialog."""
        from core.system.windows import get_installed_apps
        apps = get_installed_apps()
        pick_win = ctk.CTkToplevel(win)
        pick_win.title(i18n.tr('app_picker.title'))
        from ui.hud_utils import _center_window
        _center_window(pick_win, 820, 740, hud.zoom_factor)
        pick_win.configure(fg_color=_BG)  # type: ignore[call-arg]
        _set_dark_title_bar(pick_win)
        pick_win.attributes("-topmost", True)
        _apply_window_icon(pick_win, hud)
        pick_win.lift()
        top_bar = tk.Frame(pick_win, bg=_BG)
        top_bar.pack(fill='x', padx=20, pady=(20, 10))
        tk.Label(top_bar, text=i18n.tr('app_picker.header'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H1, 'bold')).pack(anchor='w')
        h_lbl = tk.Label(top_bar, text=i18n.tr('app_picker.hint'), bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL), justify='left', anchor='w')
        h_lbl.pack(fill='x', anchor='w')
        def _upd_p_wrap(e, l=h_lbl): l.configure(wraplength=e.width)
        top_bar.bind('<Configure>', _upd_p_wrap, add='+')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text=i18n.tr('app_picker.search_placeholder'), font=(hud._F, JStyle.TEXT_BODY), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=JStyle.H_LARGE, corner_radius=JStyle.RAD_PANEL)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        # switch_width/height=36/18, not hud._px(...) — CTk widgets are
        # already scaled by ctk.set_widget_scaling(zoom_factor) globally, so
        # pre-multiplying by zoom_factor here scales it twice at high DPI.
        sw_all = ctk.CTkSwitch(ctrl_f, text=i18n.tr('app_picker.system_apps'), variable=_show_all_var, font=(hud._F, 16, 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=36, switch_height=18)
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
        ctk.CTkButton(pick_win, text=i18n.tr('app_picker.select_btn'), command=_on_pick, height=JStyle.H_LARGE, width=280, font=(hud._F, JStyle.TEXT_BODY, 'bold'), fg_color=_CYAN, text_color=_BG).pack(anchor='center', pady=(0, 20))

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
        names = {'cyber': 'CYBER NEON', 'dark': 'PURE DARK', 'neon_white': 'NEON WHITE', 'minimal': 'MINIMAL'}
        lbl = tk.Label(
            restart_f,
            text=i18n.tr('theme.saved').format(name=names.get(name, name)),
            bg=_blend(_GREEN, 0.08), fg=_GREEN,
            font=(hud._F, _sf(9), 'bold'), anchor='w', justify='left'
        )
        lbl.pack(side='left', fill='x', expand=True, padx=12, pady=8)
        
        def _upd_restart_wrap(e, l=lbl):
            # Leave space for the button (160px + padding)
            l.configure(wraplength=max(100, e.width - hud._px(190)))
        restart_f.bind('<Configure>', _upd_restart_wrap, add='+')
        def _restart():
            import subprocess, sys, os as _os
            subprocess.Popen([sys.executable] + sys.argv)
            win.after(200, lambda: _os._exit(0))
        ctk.CTkButton(
            restart_f, text=i18n.tr('theme.restart_btn'), command=_restart,
            height=34, font=(hud._F, _sfc(9), 'bold'),
            fg_color=_blend(_GREEN, 0.15), hover_color=_blend(_GREEN, 0.25),
            text_color=_GREEN, border_color=_blend(_GREEN, 0.5),
            border_width=1, corner_radius=JStyle.RAD_BTN, width=160
        ).pack(side='right', padx=8, pady=6)
        restart_f.pack(fill='x', pady=(6, 0))

    c0 = _card('◐', i18n.tr('theme.label'), _CYAN)
    c0.master.pack_forget()
    c0.master.pack(fill='x', padx=20, pady=(0, 0))
    _hint(c0, i18n.tr('theme.hint'))

    curr_theme = hud._settings.get('theme', 'cyber')

    theme_f = tk.Frame(c0, bg=_PANEL)
    theme_f.pack(fill='x', pady=(5, 4))
    theme_f.columnconfigure(0, weight=1)
    theme_f.columnconfigure(1, weight=1)

    # Theme definitions: (id, label, accent, bg_preview, text_preview)
    _theme_defs = [
        ('cyber',      i18n.tr('theme.cyber'),      '#00ffff', '#0a0b10', '#00ffff'),
        ('dark',       i18n.tr('theme.dark'),        '#5b9cf6', '#0a0a0a', '#ffffff'),
        ('neon_white', i18n.tr('theme.neon_white'),  '#0077cc', '#f4f4f6', '#111111'),
        ('minimal',    i18n.tr('theme.minimal'),     '#1a56db', '#fafafa', '#111111'),
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
        row, col = divmod(i, 2)
        padx = (0, 4) if col == 0 else (4, 0)
        pady = (0, 4) if row == 0 else (4, 0)
        t_btn = ctk.CTkButton(
            theme_f, text=tname,
            command=lambda n=tid: _on_theme_change(n),
            height=JStyle.H_HUGE,
            font=(hud._F, JStyle.TEXT_BODY, 'bold'),
            fg_color=tbg,
            hover_color=_blend_hex(tbg, accent, 0.25),
            text_color=tfg if not is_sel else accent,
            border_color=accent if is_sel else _blend_hex(tbg, '#888888', 0.3),
            border_width=2 if is_sel else 1,
            corner_radius=JStyle.RAD_PANEL
        )
        t_btn.grid(row=row, column=col, padx=padx, pady=pady, sticky='ew')

    # Restart notice frame (hidden until needed)
    restart_f = tk.Frame(c0, bg=_blend(_GREEN, 0.08),
                         highlightbackground=_blend(_GREEN, 0.3), highlightthickness=1)


    c1 = _card('◈', i18n.tr('display.label'), _CYAN)
    _zoom_val_lbl = _label_row(c1, i18n.tr('display.zoom'), _CYAN)
    _zoom_val_lbl.configure(text=f'{hud.zoom_factor:.1f}×')
    _hint(c1, i18n.tr('display.zoom_hint'))
    _zoom_timer_id = [None]
    def _apply_zoom(z: float) -> None:
        z = round(z, 1)
        _zoom_val_lbl.configure(text=f'{z:.1f}×')
        hud.zoom_factor = z
        hud._settings['zoom_factor'] = z
        _save_hud_settings(hud._settings)
        zoom_slider.set(z)
        ctk.set_widget_scaling(z)
        ctk.set_window_scaling(z)
        hud._apply_zoom_rebuild(force_auto=True)
        
        # Force settings window to update its own scaling context
        win.update()

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

    _sb_val_lbl = _label_row(c1, i18n.tr('display.scrollbar'), _CYAN)
    _sb_width = hud._settings.get('scrollbar_width', 10)
    _sb_val_lbl.configure(text=f'{_sb_width} px')
    
    _sb_timer_id = [None]
    def _on_sb_slide(v):
        w = int(float(v))
        _sb_val_lbl.configure(text=f'{w} px')
        hud._settings['scrollbar_width'] = w
        _save_hud_settings(hud._settings)
        
        # Задержка перед ребилдом для предотвращения рекурсии и лагов
        if _sb_timer_id[0]:
            win.after_cancel(_sb_timer_id[0])
            
        def _apply():
            from ui import hud_constants as _hc
            _hc._SCROLLBAR_WIDTH = w
            hud._apply_zoom_rebuild()
            _sb_timer_id[0] = None
            
        _sb_timer_id[0] = win.after(300, _apply)

    _slider(c1, 4, 30, 26, _CYAN, _sb_width, _on_sb_slide)

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
        switch_width=48,
        switch_height=24,
    )
    _max_sw.pack(side='right', padx=16, pady=12)
    _max_lbl = tk.Label(
        _max_row,
        text=i18n.tr('display.fullscreen'),
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
        (i18n.tr('display.zoom_minus'), -0.1, _CYAN),
        (i18n.tr('display.zoom_plus'), +0.1, _CYAN),
        (i18n.tr('display.zoom_reset'), 1.0, _MAG),
        (i18n.tr('display.zoom_auto'), 0.0, _GREEN)
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

    c2 = _card('◉', i18n.tr('modules.label'), _MAG)
    _hint(c2, i18n.tr('modules.hint'))
    _vis_icons = {
        'sunrise': '☀', 'sysinfo': '◈', 'storage': '📊', 'network': '⟳', 'weather': '≋',
        'clock': '🕐', 'camera': '📷', 'gamemode': '✦', 'meetings_btn': '🔗', 'videos_btn': '▶',
        'network_ip': '◈', 'network_ssid': '◈', 'network_traffic': '◈', 'network_ls': '◈', 'sysinfo_mic': '◈'
    }
    _vis_map = {
        'sunrise': i18n.tr('modules.sunrise'),
        'sysinfo': i18n.tr('modules.sysinfo'),
        'sysinfo_mic': i18n.tr('modules.sysinfo_mic'),
        'storage': i18n.tr('modules.storage'),
        'network': i18n.tr('modules.network'),
        'network_ip': i18n.tr('modules.network_ip'),
        'network_ssid': i18n.tr('modules.network_ssid'),
        'network_ls': i18n.tr('modules.network_ls'),
        'network_traffic': i18n.tr('modules.network_traffic'),
        'weather': i18n.tr('modules.weather'),
        'clock': i18n.tr('modules.clock'),
        'camera': i18n.tr('modules.camera'),
        'gamemode': i18n.tr('modules.gamemode'),
        'meetings_btn': i18n.tr('modules.meetings_btn'),
        'videos_btn': i18n.tr('modules.videos_btn')
    }

    c_mon = _card('▦', i18n.tr('modules.monitoring'), _GREEN)
    _hint(c_mon, i18n.tr('modules.monitoring_hint'))
    mon_row = tk.Frame(c_mon, bg=_PANEL)
    mon_row.pack(fill='x', pady=4)
    icon_mon = tk.Frame(mon_row, bg=_PANEL, width=hud._px(36), height=hud._px(36))
    icon_mon.pack_propagate(False)
    icon_mon.pack(side='left')
    tk.Label(icon_mon, text='▦', bg=_PANEL, fg=_GREEN, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
    mon_var = tk.BooleanVar(value=getattr(hud, '_monitoring_enabled', True))
    sw_mon = ctk.CTkSwitch(mon_row, text='', variable=mon_var, onvalue=True, offvalue=False,
                           fg_color=_BRD_I, progress_color=_GREEN, button_color=_WHITE,
                           switch_width=48, switch_height=24, width=0)
    sw_mon.pack(side='left', padx=(4, 5))
    lbl_mon = tk.Label(mon_row, text=i18n.tr('modules.monitoring_text'), bg=_PANEL,
                       fg=_TEXT, font=(hud._F, _sf(12), 'bold'), anchor='w', justify='left')
    lbl_mon.pack(side='left', fill='x', expand=True, padx=(2, 0))
    def _upd_mon_wrap(e, l=lbl_mon):
        avail = e.width - hud._px(120)
        l.configure(wraplength=max(60, avail))
    mon_row.bind('<Configure>', _upd_mon_wrap, add='+')
    def _on_mon_change():
        hud._monitoring_enabled = mon_var.get()
        hud._settings['monitoring_enabled'] = hud._monitoring_enabled
        _save_hud_settings(hud._settings)
    sw_mon.configure(command=_on_mon_change)
    lbl_mon.bind('<Button-1>', lambda e: (mon_var.set(not mon_var.get()), _on_mon_change()))
    _vis_vars: dict[str, tk.BooleanVar] = {}
    for key, label in _vis_map.items():
        var = tk.BooleanVar(value=hud._widget_vis.get(key, True))
        _vis_vars[key] = var
        
        # Индексация подпунктов
        is_sub = key.startswith(('network_', 'sysinfo_'))
        sw_row = tk.Frame(c2, bg=_PANEL)
        sw_row.pack(fill='x', pady=4, padx=(hud._px(28) if is_sub else 0, 0))

        if is_sub:
            # A tree-branch glyph so the indent reads as "this belongs to
            # the module above" instead of looking like a random offset.
            conn_f = tk.Frame(sw_row, bg=_PANEL, width=hud._px(18), height=hud._px(36))
            conn_f.pack_propagate(False)
            conn_f.pack(side='left')
            tk.Label(conn_f, text='└', bg=_PANEL, fg=_blend(_MAG, 0.45),
                     font=(hud._F, _sf(13))).place(relx=0.5, rely=0.45, anchor='center')

        icon_f = tk.Frame(sw_row, bg=_PANEL, width=hud._px(36), height=hud._px(36))
        icon_f.pack_propagate(False)
        icon_f.pack(side='left')
        tk.Label(icon_f, text=_vis_icons.get(key, ' '), bg=_PANEL, fg=_MAG, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
        sw = ctk.CTkSwitch(sw_row, text='', variable=var, onvalue=True, offvalue=False, fg_color=_BRD_I, progress_color=_MAG, button_color=_WHITE, switch_width=48, switch_height=24, width=0)
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
            
            # Синхронизация подпунктов с родительским модулем
            if k == 'network':
                for subk in ['network_ip', 'network_ssid', 'network_ls', 'network_traffic']:
                    if subk in _vis_vars:
                        _vis_vars[subk].set(v.get())
                        hud._widget_vis[subk] = v.get()
            if k == 'sysinfo':
                if 'sysinfo_mic' in _vis_vars:
                    _vis_vars['sysinfo_mic'].set(v.get())
                    hud._widget_vis['sysinfo_mic'] = v.get()

            hud._settings['widget_vis'] = hud._widget_vis
            _save_hud_settings(hud._settings)
            
            if k in ('camera', 'sysinfo', 'sysinfo_mic', 'gamemode', 'meetings_btn', 'videos_btn'):
                hud._rebuild_left()
            else:
                hud._rebuild_right()
            if k == 'sunrise':
                hud._apply_widget_visibility()
            if k == 'weather' and v.get():
                hud._weather_tick()
                
        sw.configure(command=lambda k=key, v=var: _on_vis_change(k, v))
        lbl.bind('<Button-1>', lambda e, k=key, v=var: (v.set(not v.get()), _on_vis_change(k, v)))

    c3 = _card('🌐', i18n.tr('language.label'), _CYAN)
    _hint(c3, i18n.tr('language.apply_note'))

    lang_row = tk.Frame(c3, bg=_PANEL)
    lang_row.pack(fill='x', pady=(8, 12))

    curr_lang = hud._settings.get('language', 'ru')
    lang_var = tk.StringVar(value=curr_lang)

    def _on_lang_change(val):
        if val != curr_lang:
            hud._settings['language'] = val
            _save_hud_settings(hud._settings)
            i18n.set_language(val)
            from ui.dialogs.settings_dlg import open_settings
            open_settings(hud, reopen=True)

    for col, (code, label) in enumerate([('ru', i18n.tr('language.ru')), ('uk', i18n.tr('language.uk'))]):
        lang_row.columnconfigure(col, weight=1)
        btn = ctk.CTkButton(
            lang_row,
            text=label,
            command=lambda c=code: _on_lang_change(c),
            height=JStyle.H_LARGE,
            font=(hud._F, JStyle.TEXT_BODY),
            fg_color=_blend(_CYAN, 0.15) if code == curr_lang else 'transparent',
            text_color=_CYAN if code == curr_lang else _DIM,
            hover_color=_blend(_CYAN, 0.2),
            border_color=_CYAN if code == curr_lang else _blend(_CYAN, 0.3),
            border_width=2 if code == curr_lang else 1,
            corner_radius=JStyle.RAD_PANEL
        )
        btn.grid(row=0, column=col, sticky='ew', padx=(0, 6) if col == 0 else (0, 0))
