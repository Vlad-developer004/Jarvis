from ui.hud_style import JStyle
from core import i18n
import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
from ui.hud_widgets import _HudScrollbar
from ui.dialogs.extensions_common import _hud_popup_menu

def build_tools_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
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
        # <<Paste>>/<<SelectAll>> class bindings get a chance to run instead
        # of being silently swallowed by our own failed attempt.
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
            # Normalize current_val to 0-1 range
            progress = (current_val - from_) / (to - from_) if current_val is not None else (init_val - from_) / (to - from_)
            
            for i in range(num_ticks + 1):
                f = i / num_ticks
                x = f * (w - 20) + 10
                
                # Milestone logic
                is_milestone = i in (0, num_ticks // 2, num_ticks)
                h = 6 if is_milestone else 3
                
                # Glow logic: ticks behind the handle are brighter
                is_active = f <= (progress + 0.01)
                color = accent if is_active else _blend(accent, 0.25)
                width = 2 if is_milestone and is_active else 1
                
                scale_canvas.create_line(x, 0, x, h, fill=color, width=width)
        
        def _on_change(v):
            _draw_ticks(float(v))
            callback(v)

        s = ctk.CTkSlider(
            container, from_=from_, to=to, number_of_steps=steps,
            progress_color=accent, 
            button_color=_WHITE, 
            button_hover_color=accent,
            fg_color=_blend(accent, 0.1),
            height=12,
            border_width=2,
            border_color=_blend(accent, 0.2),
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
            height=JStyle.H_NORM, # Reduced from 44
            font=(hud._F, JStyle.TEXT_BODY, 'bold'),
            fg_color=_blend(accent, 0.12),
            hover_color=_blend(accent, 0.22),
            text_color=_TEXT,
            border_color=_blend(accent, 0.45),
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
        tk.Label(top_bar, text=i18n.tr('app_picker.header'), bg=_BG, fg=_CYAN, font=(hud._F, _sf(14), 'bold')).pack(anchor='w')
        h_lbl = tk.Label(top_bar, text=i18n.tr('app_picker.hint'), bg=_BG, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w')
        h_lbl.pack(fill='x', anchor='w')
        def _upd_p_wrap(e, l=h_lbl): l.configure(wraplength=e.width)
        top_bar.bind('<Configure>', _upd_p_wrap, add='+')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text=i18n.tr('app_picker.search_placeholder'), font=(hud._F, JStyle.TEXT_BODY), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=JStyle.H_LARGE, corner_radius=JStyle.RAD_PANEL)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        sw_all = ctk.CTkSwitch(ctrl_f, text=i18n.tr('app_picker.system_apps'), variable=_show_all_var, font=(hud._F, JStyle.TEXT_BODY, 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=36, switch_height=18)
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

    c_yt = _card('▶', i18n.tr('tools.youtube_title'), _CYAN)
    c_yt.master.pack_forget()
    c_yt.master.pack(fill='x', padx=20, pady=(0, 0))
    _cur_max_saved = int(hud._settings.get('max_saved_videos', 10))
    _max_saved_lbl = _label_row(c_yt, i18n.tr('tools.max_videos'), _CYAN)
    _max_saved_lbl.configure(text=str(_cur_max_saved))
    _hint(c_yt, i18n.tr('tools.max_videos_hint'))
    _max_saved_save_after = [None]
    def _on_max_saved(v):
        val = int(float(v))
        _max_saved_lbl.configure(text=str(val))
        if _max_saved_save_after[0]:
            win.after_cancel(_max_saved_save_after[0])
        def _save():
            hud._settings['max_saved_videos'] = val
            _save_hud_settings(hud._settings)
        _max_saved_save_after[0] = win.after(600, _save)
    _slider(c_yt, 1, 50, 49, _CYAN, _cur_max_saved, _on_max_saved)
    
    _v_row = tk.Frame(c_yt, bg=_PANEL)
    _v_row.pack(fill='x', pady=(14, 0))
    def _open_videos_mgr():
        from ui.dialogs.manage_dlg import open_videos_manager
        open_videos_manager(hud)

    ctk.CTkButton(
        _v_row, text=i18n.tr('tools.view_videos'),
        command=_open_videos_mgr,
        height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'),
        fg_color='transparent', hover_color=_blend(_CYAN, 0.25),
        text_color=_WHITE, border_color=_blend(_CYAN, 0.8),
        border_width=2, corner_radius=JStyle.RAD_PANEL
    ).pack(anchor='center', fill='x', padx=12, pady=(0, 4))

    c_mtg = _card('🔗', i18n.tr('tools.meetings_title'), _GREEN)
    _hint(c_mtg, i18n.tr('tools.meetings_hint'))
    from actions.meetings import get_meetings, save_meetings as _save_meetings
    _meetings_list: list[dict] = list(get_meetings())
    _mtg_count_lbl = tk.Label(c_mtg, text=i18n.tr('tools.meetings_saved').format(n=len(_meetings_list)), bg=_PANEL, fg=_DIM,
                                font=(hud._F, _sf(9)))
    _mtg_count_lbl.pack(anchor='w', pady=(4, 0))
    _entry_kw = dict(font=(hud._F, _sf(10), 'bold'), fg_color=_BG, text_color=_WHITE,
                     border_color=_blend(_GREEN, 0.35), border_width=1,
                     corner_radius=JStyle.RAD_PANEL, height=JStyle.H_NORM, # Reduced from 44
                     placeholder_text_color=_blend(_WHITE, 0.25))
    _lkw_mtg = dict(bg=_PANEL, fg=_blend(_GREEN, 0.8), font=(hud._F, _sf(9), 'bold'), anchor='w')
    tk.Label(c_mtg, text=i18n.tr('tools.voice_phrase'), **_lkw_mtg).pack(fill='x', pady=(10, 0), padx=4) # Reduced from 12
    _mtg_phrase_entry = ctk.CTkEntry(c_mtg, placeholder_text=i18n.tr('tools.phrase_example'), **_entry_kw)
    _mtg_phrase_entry.pack(fill='x', pady=(2, 8), padx=4) # Reduced from 12
    tk.Label(c_mtg, text=i18n.tr('tools.link'), **_lkw_mtg).pack(fill='x', padx=4)
    _mtg_url_entry = ctk.CTkEntry(c_mtg, placeholder_text='https://zoom.us/j/123...', **_entry_kw)
    _mtg_url_entry.pack(fill='x', pady=(2, 8), padx=4)
    tk.Label(c_mtg, text=i18n.tr('tools.name_optional'), **_lkw_mtg).pack(fill='x', padx=4)
    _mtg_name_entry = ctk.CTkEntry(c_mtg, placeholder_text=i18n.tr('tools.name_example'), **_entry_kw)
    _mtg_name_entry.pack(fill='x', pady=(2, 12), padx=4)
    _add_context_menu(_mtg_phrase_entry)
    _add_context_menu(_mtg_url_entry)
    _add_context_menu(_mtg_name_entry)
    _mtg_status = tk.Label(c_mtg, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), padx=14)
    # Don't pack status by default to save space
    def _add_meeting():
        phrase = _mtg_phrase_entry.get().strip().lower()
        url = _mtg_url_entry.get().strip()
        name = _mtg_name_entry.get().strip()
        if not phrase or not url:
            _mtg_status.pack(anchor='w', pady=(0, 6))
            _mtg_status.configure(text=i18n.tr('tools.mtg_required'), fg=_AMBER)
            return
        if not name:
            name = phrase
        _meetings_list.append({'name': name, 'phrase': phrase, 'url': url})
        _save_meetings(_meetings_list)
        _mtg_phrase_entry.delete(0, 'end')
        _mtg_url_entry.delete(0, 'end')
        _mtg_name_entry.delete(0, 'end')
        _mtg_status.pack(anchor='w', pady=(0, 6))
        _mtg_status.configure(text=i18n.tr('tools.mtg_added').format(p=phrase), fg=_GREEN)
        _mtg_count_lbl.configure(text=i18n.tr('tools.meetings_saved').format(n=len(_meetings_list)))
    btn_row_mtg = tk.Frame(c_mtg, bg=_PANEL)
    btn_row_mtg.pack(fill='x', pady=(4, 2), padx=0) # Removed padx=8, body handles it
    btn_row_mtg.columnconfigure(0, weight=1)
    btn_row_mtg.columnconfigure(1, weight=1)

    _m_btn_k = dict(height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), corner_radius=JStyle.RAD_PANEL, border_width=2)
    ctk.CTkButton(
        btn_row_mtg, text=i18n.tr('tools.add_link'), command=_add_meeting,
        fg_color='transparent', hover_color=_blend(_GREEN, 0.25),
        text_color=_WHITE, border_color=_blend(_GREEN, 0.8),
        **_m_btn_k
    ).grid(row=0, column=0, padx=4, sticky='ew')

    def _open_meetings_mgr():
        from ui.dialogs.manage_dlg import open_meetings_manager
        open_meetings_manager(hud)

    ctk.CTkButton(
        btn_row_mtg, text=i18n.tr('tools.manage_links'),
        command=_open_meetings_mgr,
        fg_color='transparent', hover_color=_blend(_CYAN, 0.25),
        text_color=_WHITE, border_color=_blend(_CYAN, 0.8),
        **_m_btn_k
    ).grid(row=0, column=1, padx=4, sticky='ew')

    c_gm = _card('✦', i18n.tr('tools.gamemode_title'), _AMBER)
    _hint(c_gm, i18n.tr('tools.gamemode_hint'))
    
    def _load_gm_prefs() -> dict:
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'game_mode_prefs.json'
            return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        except Exception: return {}

    def _save_gm_prefs(d: dict):
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'game_mode_prefs.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception: pass

    _gm_status = tk.Label(c_gm, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w')
    _gm_status.pack(anchor='w', pady=(0, 4))

    _gm_prefs = _load_gm_prefs()
    _keep_titles = [str(x) for x in _gm_prefs.get('keep_titles', []) if str(x).strip()]

    _gm_lb_shell = tk.Frame(c_gm, bg=_BG, highlightbackground=_blend(_AMBER, 0.18), highlightthickness=1)
    _gm_lb_shell.pack(fill='x', pady=(6, 10))
    _gm_lb = tk.Listbox(
        _gm_lb_shell, font=(hud._F, _sf(11), 'bold'), bg=_BG, fg=_TEXT,
        selectbackground=_blend(_AMBER, 0.3), height=1, borderwidth=0, highlightthickness=0, activestyle='none'
    )
    _gm_lb.pack(fill='x', padx=6, pady=6)

    # Neural Placeholder for Game Mode
    _gm_empty_lbl = tk.Label(
        c_gm, text=i18n.tr('tools.gamemode_empty'),
        bg=_PANEL, fg=_blend(_AMBER, 0.4), font=(hud._F, _sf(10)), pady=14
    )

    def _refresh_gm_lb():
        _gm_lb.delete('0', 'end')
        if not _keep_titles:
            _gm_lb_shell.pack_forget()
            _gm_empty_lbl.pack(fill='x', pady=(6, 10))
        else:
            _gm_empty_lbl.pack_forget()
            _gm_lb_shell.pack(fill='x', pady=(6, 10))
            for s in sorted(_keep_titles): _gm_lb.insert('end', f'  {s}')
            _gm_lb.config(height=max(1, len(_keep_titles)))

    def _save_gm_now():
        _save_gm_prefs({'keep_titles': list(_keep_titles)})
        _gm_status.configure(text=i18n.tr('tools.gamemode_saved'), fg=_GREEN)

    def _gm_add(s):
        s = s.strip().lower()
        if s and s not in _keep_titles:
            _keep_titles.append(s)
            _refresh_gm_lb()
            _save_gm_now()

    _refresh_gm_lb()

    _gm_entry = ctk.CTkEntry(
        c_gm, placeholder_text=i18n.tr('tools.gamemode_placeholder'),
        font=(hud._F, _sf(10)), fg_color=_BG, border_color=_blend(_AMBER, 0.35),
        height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL # Reduced from 44
    )
    _gm_entry.pack(fill='x', pady=(4, 8), padx=4) # Reduced from 12
    _gm_entry.bind('<Return>', lambda e: (_gm_add(_gm_entry.get()), _gm_entry.delete('0', 'end')))

    _gm_btn_row = tk.Frame(c_gm, bg=_PANEL)
    _gm_btn_row.pack(fill='x', padx=0) # Body handles padding

    _gm_btn_k = dict(height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), corner_radius=JStyle.RAD_PANEL, border_width=2)
    ctk.CTkButton(_gm_btn_row, text=i18n.tr('dev.add_btn'), command=lambda: (_gm_add(_gm_entry.get()), _gm_entry.delete('0', 'end')),
                  fg_color='transparent', hover_color=_blend(_AMBER, 0.25), text_color=_WHITE,
                  border_color=_blend(_AMBER, 0.8), **_gm_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)

    ctk.CTkButton(_gm_btn_row, text=i18n.tr('tools.from_installed'), command=lambda: _pick_app_dialog(_gm_add),
                  fg_color='transparent', hover_color=_blend(_AMBER, 0.2), text_color=_WHITE,
                  border_color=_blend(_AMBER, 0.5), **_gm_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)

    ctk.CTkButton(_gm_btn_row, text=i18n.tr('dev.delete_btn'), command=lambda: (_keep_titles.remove(_gm_lb.get(_gm_lb.curselection()[0]).strip()), _refresh_gm_lb(), _save_gm_now()) if _gm_lb.curselection() else None,
                  fg_color='transparent', hover_color=_blend(_RED, 0.25), text_color=_WHITE,
                  border_color=_blend(_RED, 0.8), **_gm_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)
    _refresh_gm_lb()

    c_launch = _card('🚀', i18n.tr('tools.launch_title'), _CYAN)
    _hint(c_launch, i18n.tr('tools.launch_hint'))
    
    _launch_rules = hud._settings.get('app_launch_rules', {})
    if not isinstance(_launch_rules, dict): _launch_rules = {}

    _launch_status = tk.Label(c_launch, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w')
    _launch_status.pack(anchor='w', pady=(0, 4))

    _lb_shell = tk.Frame(c_launch, bg=_BG, highlightbackground=_blend(_CYAN, 0.18), highlightthickness=1)
    _lb_shell.pack(fill='x', pady=(6, 10))
    _launch_lb = tk.Listbox(
        _lb_shell, font=(hud._F, _sf(10), 'bold'), bg=_BG, fg=_TEXT,
        selectbackground=_blend(_CYAN, 0.3), height=5, borderwidth=0, highlightthickness=0, activestyle='none'
    )
    _launch_lb.pack(fill='x', padx=6, pady=6)

    def _refresh_launch_lb():
        _launch_lb.delete('0', 'end')
        for app, behavior in sorted(_launch_rules.items()):
            b_text = i18n.tr('tools.launch_new') if behavior == 'new' else i18n.tr('tools.launch_switch')
            _launch_lb.insert('end', f'  {app.upper():<20} ◈ {b_text}')
        _launch_lb.config(height=max(3, min(8, len(_launch_rules))))

    def _save_launch_now():
        hud._settings['app_launch_rules'] = _launch_rules
        _save_hud_settings(hud._settings)
        _launch_status.configure(text=i18n.tr('tools.launch_saved'), fg=_GREEN)

    def _toggle_launch_rule():
        sel = _launch_lb.curselection()
        if not sel: return
        app_item = _launch_lb.get(sel[0]).strip()
        app_name = app_item.split(' ◈ ')[0].strip().lower()
        
        # We need to find the original key because we displayed it in uppercase
        actual_key = next((k for k in _launch_rules if k.lower() == app_name), None)
        if actual_key:
            _launch_rules[actual_key] = 'new' if _launch_rules[actual_key] == 'switch' else 'switch'
            _refresh_launch_lb()
            _save_launch_now()

    def _add_launch_rule(app_path):
        app_name = os.path.basename(app_path).replace('.exe', '').replace('.lnk', '').lower()
        if app_name not in _launch_rules:
            _launch_rules[app_name] = 'switch'
            _refresh_launch_lb()
            _save_launch_now()

    _refresh_launch_lb()

    _l_btn_row = tk.Frame(c_launch, bg=_PANEL)
    _l_btn_row.pack(fill='x')

    _l_btn_k = dict(height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), corner_radius=JStyle.RAD_PANEL, border_width=2)
    ctk.CTkButton(_l_btn_row, text=i18n.tr('dev.add_btn'), command=lambda: _pick_app_dialog(_add_launch_rule),
                  fg_color='transparent', hover_color=_blend(_CYAN, 0.25), text_color=_WHITE,
                  border_color=_blend(_CYAN, 0.8), **_l_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)

    ctk.CTkButton(_l_btn_row, text=i18n.tr('tools.toggle_mode'), command=_toggle_launch_rule,
                  fg_color='transparent', hover_color=_blend(_AMBER, 0.2), text_color=_WHITE,
                  border_color=_blend(_AMBER, 0.5), **_l_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)

    ctk.CTkButton(_l_btn_row, text=i18n.tr('dev.delete_btn'),
                  command=lambda: (_launch_rules.pop(next(k for k in _launch_rules if k.lower() == _launch_lb.get(_launch_lb.curselection()[0]).strip().split(' ◈ ')[0].strip().lower())), _refresh_launch_lb(), _save_launch_now()) if _launch_lb.curselection() else None,
                  fg_color='transparent', hover_color=_blend(_RED, 0.25), text_color=_WHITE,
                  border_color=_blend(_RED, 0.8), **_l_btn_k).pack(side='left', fill='x', expand=True, padx=4, pady=4)

    c_remote = _card('📲', i18n.tr('tools.remote_title'), _CYAN)
    _hint(c_remote, i18n.tr('tools.remote_hint'))
    from ui.dialogs.settings_tabs.tools_remote import build_remote_card
    build_remote_card(c_remote, hud, _add_context_menu)

    c_update = _card('⟳', i18n.tr('tools.update_title'), _GREEN)
    _hint(c_update, i18n.tr('tools.update_hint'))

    def _load_settings_json_u() -> dict:
        try:
            from config_pack.config import get_settings_path
            p = get_settings_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            pass
        return {}

    def _save_settings_json_u(d: dict) -> None:
        try:
            from config_pack.config import get_settings_path
            p = get_settings_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    _upd_row = tk.Frame(c_update, bg=_PANEL)
    _upd_row.pack(fill='x')
    tk.Label(_upd_row, text=i18n.tr('tools.update_toggle_label'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10)), anchor='w').pack(side='left')
    _upd_var = tk.BooleanVar(value=bool(_load_settings_json_u().get('auto_update_enabled', True)))

    def _on_upd_toggle():
        sj = _load_settings_json_u()
        sj['auto_update_enabled'] = _upd_var.get()
        _save_settings_json_u(sj)

    ctk.CTkSwitch(
        _upd_row, text='', variable=_upd_var, command=_on_upd_toggle,
        progress_color=_GREEN, fg_color=_BRD_I, button_color=_WHITE,
        switch_width=46, switch_height=24,
    ).pack(side='right')

    _upd_status = tk.Label(c_update, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), anchor='w', justify='left')
    _upd_status.pack(fill='x', pady=(8, 0))
    _upd_btn_row = tk.Frame(c_update, bg=_PANEL)

    def _do_install_now():
        try:
            from core.system import app_updater
            if app_updater.apply_and_restart():
                win.destroy()
                os._exit(0)
        except Exception:
            pass

    def _refresh_update_status():
        try:
            from core.system.version import APP_VERSION
            from core.system import app_updater
            avail = app_updater.get_available_version()
            if app_updater.is_update_staged() and avail:
                _upd_status.configure(text=i18n.tr('tools.update_status_ready').format(v=avail), fg=_GREEN)
                _upd_btn_row.pack(fill='x', pady=(6, 0))
            elif avail:
                _upd_status.configure(text=i18n.tr('tools.update_status_available').format(v=avail), fg=_AMBER)
                _upd_btn_row.pack_forget()
            else:
                _upd_status.configure(text=i18n.tr('tools.update_status_current').format(v=APP_VERSION), fg=_DIM)
                _upd_btn_row.pack_forget()
        except Exception:
            pass

    ctk.CTkButton(
        _upd_btn_row, text=i18n.tr('tools.update_install_btn'), command=_do_install_now,
        fg_color='transparent', hover_color=_blend(_GREEN, 0.2), text_color=_WHITE,
        border_color=_blend(_GREEN, 0.8), corner_radius=JStyle.RAD_BTN, height=hud._px(30),
    ).pack(fill='x')

    _refresh_update_status()

    _refresh_launch_lb()
