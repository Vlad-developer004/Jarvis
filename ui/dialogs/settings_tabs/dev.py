from ui.hud_style import JStyle
import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
from ui.hud_widgets import _HudScrollbar

def build_dev_tab(inner, win, hud, _save_hud_settings):
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
        s = ctk.CTkSlider(parent, from_=from_, to=to, number_of_steps=steps, progress_color=accent, button_color=accent, button_hover_color=_blend(accent, 0.7), fg_color=_BRD_I, height=16)
        s.set(init_val)
        s.pack(fill='x', pady=(10, 4))
        s.configure(command=callback)
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
        pick_win.title("ВЫБОР ПРИЛОЖЕНИЯ")
        pick_win.geometry(f"{hud._px(820)}x{hud._px(740)}")
        from ui.hud_utils import _center_window
        _center_window(pick_win, 820, 740, hud.zoom_factor)
        pick_win.configure(bg=_BG)
        _set_dark_title_bar(pick_win)
        pick_win.attributes("-topmost", True)
        _apply_window_icon(pick_win, hud)
        pick_win.lift()
        top_bar = tk.Frame(pick_win, bg=_BG)
        top_bar.pack(fill='x', padx=20, pady=(20, 10))
        tk.Label(top_bar, text="ВЫБЕРИТЕ ПРИЛОЖЕНИЕ", bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H1, 'bold')).pack(anchor='w')
        h_lbl = tk.Label(top_bar, text="Выберите программу для добавления в список", bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL), justify='left', anchor='w')
        h_lbl.pack(fill='x', anchor='w')
        def _upd_p_wrap(e, l=h_lbl): l.configure(wraplength=e.width)
        top_bar.bind('<Configure>', _upd_p_wrap, add='+')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text='Поиск...', font=(hud._F, JStyle.TEXT_BODY), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=JStyle.H_LARGE, corner_radius=JStyle.RAD_PANEL)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        sw_all = ctk.CTkSwitch(ctrl_f, text='Системные', variable=_show_all_var, font=(hud._F, JStyle.TEXT_BODY, 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=36, switch_height=18)
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
        ctk.CTkButton(pick_win, text="ВЫБРАТЬ ПРИЛОЖЕНИЕ", command=_on_pick, height=JStyle.H_LARGE, width=280, font=(hud._F, JStyle.TEXT_BODY, 'bold'), fg_color=_CYAN, text_color=_BG).pack(anchor='center', pady=(0, 20))

    c_context = _card('⬡', 'РАБОЧЕЕ ОКРУЖЕНИЕ (IDE)', _CYAN)
    _hint(c_context, 'Джарвис будет нацелен на папку проекта, когда одно из этих приложений в фокусе.')
    
    _ctx_apps_lb_shell = tk.Frame(c_context, bg=_BG, highlightbackground=_blend(_CYAN, 0.15), highlightthickness=1)
    _ctx_apps_lb_shell.pack(fill='x', pady=(6, 10))
    lb_ctx_apps = tk.Listbox(
        _ctx_apps_lb_shell, font=(hud._F, _sf(11)), bg=_BG, fg=_TEXT,
        selectbackground=_blend(_CYAN, 0.3), height=1, borderwidth=0, highlightthickness=0, activestyle='none'
    )
    lb_ctx_apps.pack(fill='x', padx=6, pady=6)

    _enabled_apps = hud._settings.get('context_apps', ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe'])
    if not isinstance(_enabled_apps, list): _enabled_apps = []
    
    # Neural Placeholder for IDE Context Apps
    _ctx_empty_lbl = tk.Label(
        c_context, text='◎  ОЖИДАНИЕ ДАННЫХ\nДобавьте ваши IDE или редакторы выше',
        bg=_PANEL, fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=14
    )

    def _refresh_apps_list():
        lb_ctx_apps.delete(0, tk.END)
        if not _enabled_apps:
            _ctx_apps_lb_shell.pack_forget()
            _ctx_empty_lbl.pack(fill='x', pady=(6, 10), padx=4)
        else:
            _ctx_empty_lbl.pack_forget()
            _ctx_apps_lb_shell.pack(fill='x', pady=(6, 10), padx=4)
            for app in sorted(_enabled_apps):
                lb_ctx_apps.insert(tk.END, f"  ✓ {app}")
            lb_ctx_apps.config(height=max(1, len(_enabled_apps)))
            
    _refresh_apps_list()

    _add_app_row = tk.Frame(c_context, bg=_PANEL)
    _add_app_row.pack(fill='x', pady=(4, 8))
    ent_app_exe = ctk.CTkEntry(
        _add_app_row, placeholder_text='Имя процесса (например: notepad.exe)',
        font=(hud._F, _sf(10)), fg_color=_BG, border_color=_blend(_CYAN, 0.35),
        height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL # Reduced from 44
    )
    ent_app_exe.pack(fill='x', padx=4) # Reduced from 12
    
    def _ctx_add(val):
        if val and val.lower() not in [a.lower() for a in _enabled_apps]:
            _enabled_apps.append(val.lower())
            hud._settings['context_apps'] = _enabled_apps
            _save_hud_settings(hud._settings)
            _refresh_apps_list()

    _ctx_btn_row = tk.Frame(c_context, bg=_PANEL)
    _ctx_btn_row.pack(fill='x')
    _ctx_btn_l = tk.Frame(_ctx_btn_row, bg=_PANEL)
    _ctx_btn_l.pack(side='left', fill='x', expand=True)
    _ctx_btn_r = tk.Frame(_ctx_btn_row, bg=_PANEL)
    _ctx_btn_r.pack(side='right', fill='x', expand=True)

    _btn_k = dict(height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), corner_radius=JStyle.RAD_PANEL, border_width=2)
    
    ctk.CTkButton(_ctx_btn_l, text='➕  ДОБАВИТЬ', command=lambda: _ctx_add(ent_app_exe.get().strip()), 
                  fg_color='transparent', hover_color=_blend(_CYAN, 0.25), text_color=_WHITE, 
                  border_color=_blend(_CYAN, 0.8), **_btn_k).pack(fill='x', padx=(0, 4), pady=4)
    
    ctk.CTkButton(_ctx_btn_l, text='📂  ИЗ УСТАНОВЛЕННЫХ', command=lambda: _pick_app_dialog(_ctx_add), 
                  fg_color='transparent', hover_color=_blend(_CYAN, 0.2), text_color=_WHITE, 
                  border_color=_blend(_CYAN, 0.5), **_btn_k).pack(fill='x', padx=(0, 4), pady=4)
    
    ctk.CTkButton(_ctx_btn_r, text='🎯  АКТИВНОЕ ОКНО', command=lambda: ent_app_exe.delete(0, tk.END) or ent_app_exe.insert(0, os.path.basename(__import__('core.system.windows', fromlist=['get_foreground_process_exe']).get_foreground_process_exe() or '').lower()), 
                  fg_color='transparent', hover_color=_blend(_AMBER, 0.25), text_color=_WHITE, 
                  border_color=_blend(_AMBER, 0.8), **_btn_k).pack(fill='x', padx=(4, 0), pady=4)
    
    ctk.CTkButton(_ctx_btn_r, text='🗑  УДАЛИТЬ', command=lambda: (_enabled_apps.remove(lb_ctx_apps.get(lb_ctx_apps.curselection()[0]).replace('  ✓ ', '').strip()), hud._settings.update({'context_apps': _enabled_apps}), _save_hud_settings(hud._settings), _refresh_apps_list()) if lb_ctx_apps.curselection() else None, 
                  fg_color='transparent', hover_color=_blend(_RED, 0.25), text_color=_WHITE, 
                  border_color=_blend(_RED, 0.8), **_btn_k).pack(fill='x', padx=(4, 0), pady=4)

    _parent_search_var = tk.BooleanVar(value=hud._settings.get('allow_parent_search', False))
    ctk.CTkSwitch(
        c_context, text='Разрешить поиск в родительских папках', variable=_parent_search_var,
        command=lambda: (hud._settings.update({'allow_parent_search': _parent_search_var.get()}), _save_hud_settings(hud._settings)),
        font=(hud._F, _sf(10)), progress_color=_CYAN,
        switch_width=48, switch_height=24 # Enlarged
    ).pack(anchor='w', pady=(14, 0), padx=4) 
    
    _hint(c_context, 'Рекурсивный поиск «назад при необходимости.')

    c_code_ext = _card('📄', 'НОВЫЙ ФАЙЛ — РАСШИРЕНИЯ', _CYAN)
    _hint(
        c_code_ext,
        'Подсказки для списка при создании файла (py, .tsx и т.д.). Пока список пуст — '
        'остаётся только расширение из команды и ручной ввод в поле.',
    )
    from actions.programming_extensions import (
        SETTINGS_JSON_KEY as _PROG_EXT_KEY,
        get_programming_extensions as _g_prog_ext,
        normalize_extension as _norm_prog_ext,
        set_programming_extensions as _set_prog_ext,
    )
    _ext_well = tk.Frame(
        c_code_ext,
        bg=_blend(_CYAN, 0.05),
        highlightbackground=_blend(_CYAN, 0.22),
        highlightthickness=1,
    )
    _ext_well.pack(fill='both', expand=True, pady=(2, 10))
    
    # Neural Placeholder for empty list
    _ext_empty_lbl = tk.Label(
        _ext_well, text='◎  ОЖИДАНИЕ ДАННЫХ\nДобавьте расширения ниже для быстрого доступа',
        bg=_blend(_CYAN, 0.05), fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=20
    )

    tk.Label(
        _ext_well,
        text='Список подсказок',
        bg=_blend(_CYAN, 0.05),
        fg=_blend(_CYAN, 0.9),
        font=(hud._F, _sf(9), 'bold'),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(10, 6))
    _ext_lb_shell = tk.Frame(_ext_well, bg=_BG, highlightbackground=_blend(_CYAN, 0.15), highlightthickness=1)
    _ext_lb_shell.pack(fill='x', pady=(0, 10), padx=4) # Added padx=4
    lb_code_ext = tk.Listbox(
        _ext_lb_shell, font=(hud._F, _sf(11)), bg=_BG, fg=_TEXT,
        selectbackground=_blend(_CYAN, 0.3), height=1, borderwidth=0, highlightthickness=0, activestyle='none'
    )
    lb_code_ext.pack(fill='x', padx=6, pady=6)

    def _refresh_prog_ext_lb():
        lb_code_ext.delete(0, tk.END)
        exts = list(_g_prog_ext())
        if not exts:
            _ext_lb_shell.pack_forget()
            _ext_empty_lbl.pack(fill='x', padx=12, pady=(0, 10))
        else:
            _ext_empty_lbl.pack_forget()
            _ext_lb_shell.pack(fill='x', pady=(0, 10))
            for e in exts: lb_code_ext.insert(tk.END, f'  .{e}')
            lb_code_ext.config(height=max(1, len(exts)))
    _refresh_prog_ext_lb()

    def _sync_prog_ext_to_hud(cur: list[str]):
        if isinstance(hud._settings, dict):
            hud._settings[_PROG_EXT_KEY] = list(cur)
            _save_hud_settings(hud._settings)

    def _on_add_prog_ext():
        n = _norm_prog_ext(ent_code_ext.get())
        if n:
            cur = list(_g_prog_ext())
            if n not in cur:
                cur.append(n)
                _set_prog_ext(cur)
                _sync_prog_ext_to_hud(cur)
                _refresh_prog_ext_lb()
            ent_code_ext.delete(0, tk.END)

    def _on_del_prog_ext():
        sel = lb_code_ext.curselection()
        if sel:
            lines = [lb_code_ext.get(i).strip() for i in range(lb_code_ext.size())]
            del lines[sel[0]]
            cur = [_norm_prog_ext(x) for x in lines if _norm_prog_ext(x)]
            _set_prog_ext(cur)
            _sync_prog_ext_to_hud(cur)
            _refresh_prog_ext_lb()
    ent_code_ext = ctk.CTkEntry(
        _ext_well, placeholder_text='py, tsx, rs или .py',
        font=(hud._F, _sf(10)), fg_color=_BG, border_color=_blend(_CYAN, 0.35),
        height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL # Reduced from 44
    )
    ent_code_ext.pack(fill='x', pady=(4, 8), padx=4) # Reduced from 12
    ent_code_ext.bind('<Return>', lambda e: _on_add_prog_ext())
    _ext_btn_row = tk.Frame(c_code_ext, bg=_PANEL)
    _ext_btn_row.pack(fill='x')
    _ext_btn_l = tk.Frame(_ext_btn_row, bg=_PANEL)
    _ext_btn_l.pack(side='left', fill='x', expand=True)
    _ext_btn_r = tk.Frame(_ext_btn_row, bg=_PANEL)
    _ext_btn_r.pack(side='right', fill='x', expand=True)

    _e_btn_k = dict(height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), corner_radius=JStyle.RAD_PANEL, border_width=2)
    ctk.CTkButton(_ext_btn_l, text='➕  ДОБАВИТЬ', command=_on_add_prog_ext, 
                  fg_color='transparent', hover_color=_blend(_CYAN, 0.25), text_color=_WHITE, 
                  border_color=_blend(_CYAN, 0.8), **_e_btn_k).pack(fill='x', padx=(0, 4), pady=4)
    
    ctk.CTkButton(_ext_btn_r, text='🗑  УДАЛИТЬ', command=_on_del_prog_ext, 
                  fg_color='transparent', hover_color=_blend(_RED, 0.25), text_color=_WHITE, 
                  border_color=_blend(_RED, 0.8), **_e_btn_k).pack(fill='x', padx=(4, 0), pady=4)
