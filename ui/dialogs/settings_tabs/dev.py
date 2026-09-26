from ui.hud_style import JStyle
from core import i18n
import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
from ui.hud_widgets import _HudScrollbar, _HUDDropdown
from ui.dialogs.settings_tabs.modules.base import _slider as _base_slider

def build_dev_tab(inner, win, hud, _save_hud_settings):
    # Уменьшаем базовый масштаб для более компактного вида
    _sf = lambda n: hud._fs(n + 3)
    
    def _add_context_menu(entry):
        menu = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, _sf(10)))
        def _paste():
            try:
                import pyperclip; txt = pyperclip.paste()
                if txt:
                    if entry.selection_present(): entry.delete('sel.first', 'sel.last')
                    entry.insert(tk.INSERT, txt)
            except Exception: pass
        def _select_all(): entry.select_range(0, 'end'); entry.icursor('end')
        menu.add_command(label=i18n.tr('context_menu.paste'), command=_paste); menu.add_command(label=i18n.tr('context_menu.select_all'), command=_select_all)
        entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    
    def _card(icon: str, title: str, accent: str):
        outer = tk.Frame(inner, bg=_PANEL, highlightbackground=_blend(accent, 0.15), highlightthickness=1)
        outer.pack(fill='x', padx=20, pady=(12, 0))
        tk.Frame(outer, bg=accent, width=3).pack(side='left', fill='y')
        body = tk.Frame(outer, bg=_PANEL); body.pack(side='left', fill='both', expand=True, padx=14, pady=12)
        head = tk.Frame(body, bg=_PANEL); head.pack(fill='x', pady=(0, 4))
        tk.Label(head, text=icon, bg=_PANEL, fg=accent, font=(hud._F, _sf(14))).pack(side='left', padx=(0, 8))
        tk.Label(head, text=title, bg=_PANEL, fg=accent, font=(hud._F, _sf(11), 'bold'), anchor='w').pack(side='left')
        return body

    def _hint(parent, text: str):
        lbl = tk.Label(parent, text=text, bg=_PANEL, fg=_blend(_TEXT, 0.65), font=(hud._F, _sf(10)), anchor='w', justify='left')
        lbl.pack(fill='x', pady=(0, 10))
        def _upd_hint(e, l=lbl): l.configure(wraplength=max(hud._px(100), e.width - hud._px(10)))
        parent.bind('<Configure>', _upd_hint, add='+')

    # Async save — file may be on OneDrive/network, never block the UI thread
    def _save_async():
        threading.Thread(target=lambda: _save_hud_settings(hud._settings), daemon=True).start()

    # ── Shared app picker dialog (used by IDE context AND editors) ────────
    def _show_app_picker(accent: str, on_select):
        """
        accent    — color theme for the dialog
        on_select — callback(exe_path, display_name)
        """
        from actions.dev_projects import get_available_apps
        _dlg = tk.Toplevel(win)
        _dlg.title(i18n.tr('dev.pick_app_title'))
        _dlg.configure(bg=_BG); _dlg.geometry('480x530')
        _dlg.resizable(False, True)
        _set_dark_title_bar(_dlg); _dlg.transient(win)

        tk.Frame(_dlg, bg=accent, height=2).pack(fill='x')
        _hdr = tk.Frame(_dlg, bg=_BG); _hdr.pack(fill='x', padx=14, pady=(12, 4))
        tk.Label(_hdr, text='◈', bg=_BG, fg=accent,
                 font=(hud._F, _sf(13))).pack(side='left', padx=(0, 8))
        _hc = tk.Frame(_hdr, bg=_BG); _hc.pack(side='left')
        tk.Label(_hc, text=i18n.tr('dev.pick_app_hint'), bg=_BG, fg=_TEXT,
                 font=(hud._F, _sf(10), 'bold')).pack(anchor='w')
        _sub = ('Запущенные и найденные приложения' if i18n.get_language() == 'ru'
                else 'Запущені та знайдені застосунки')
        tk.Label(_hc, text=_sub, bg=_BG, fg=_DIM,
                 font=(hud._F, _sf(8))).pack(anchor='w')

        _sch_row = tk.Frame(_dlg, bg=_BG); _sch_row.pack(fill='x', padx=14, pady=(0, 6))
        tk.Label(_sch_row, text='⌕', bg=_BG, fg=_blend(accent, 0.6),
                 font=(hud._F, _sf(12))).pack(side='left', padx=(0, 4))
        _sch_e = ctk.CTkEntry(_sch_row, placeholder_text=i18n.tr('dev.search'),
                              fg_color=_BG, border_color=_blend(accent, 0.3),
                              height=28, corner_radius=6, font=(hud._F, _sf(10)))
        _sch_e.pack(side='left', fill='x', expand=True)

        _shell = tk.Frame(_dlg, bg=_BG,
                          highlightbackground=_blend(accent, 0.18), highlightthickness=1)
        _shell.pack(fill='both', expand=True, padx=14, pady=(0, 8))
        _cv = tk.Canvas(_shell, bg=_BG, highlightthickness=0, borderwidth=0)
        _cv.pack(side='left', fill='both', expand=True)
        _sb = _HudScrollbar(_shell, _cv, color=accent)
        _cv.configure(yscrollcommand=_sb.set)

        _rf = tk.Frame(_cv, bg=_BG)
        _cw = _cv.create_window((0, 0), window=_rf, anchor='nw', tags='rf')
        _cv.bind('<Configure>', lambda e: (
            _cv.itemconfig('rf', width=e.width),
            _cv.configure(scrollregion=_cv.bbox('all')) if _cv.bbox('all') else None
        ))
        _cv.bind('<MouseWheel>', lambda e: _cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))

        _loading = tk.Label(_rf, text=i18n.tr('dev.editor_detecting'), bg=_BG,
                             fg=_blend(accent, 0.35), font=(hud._F, _sf(10)), pady=20)
        _loading.pack(fill='x')

        _all: list = []; _filt: list = []; _sel: list[int] = [-1]; _rows: list = []

        def _desel():
            _sel[0] = -1
            for r in _rows:
                for w in r['w']:
                    try: w.configure(bg=_BG)
                    except Exception: pass
                try: r['a'].configure(bg=_blend(accent, 0.18))
                except Exception: pass

        def _pick(idx):
            _desel(); _sel[0] = idx
            if 0 <= idx < len(_rows):
                for w in _rows[idx]['w']:
                    try: w.configure(bg=_blend(accent, 0.09))
                    except Exception: pass
                try: _rows[idx]['a'].configure(bg=accent)
                except Exception: pass

        def _fill(q=''):
            for w in _rf.winfo_children(): w.destroy()
            _rows.clear(); _filt.clear(); _sel[0] = -1
            ql = q.lower()
            for exe, nm in _all:
                if not ql or ql in nm.lower() or ql in exe.lower():
                    _filt.append((exe, nm)); idx = len(_filt) - 1
                    row = tk.Frame(_rf, bg=_BG, cursor='hand2')
                    row.pack(fill='x', pady=(0, 1))
                    acc = tk.Frame(row, bg=_blend(accent, 0.18), width=3)
                    acc.pack(side='left', fill='y')
                    body = tk.Frame(row, bg=_BG)
                    body.pack(side='left', fill='both', expand=True, padx=(10, 8), pady=(5, 5))
                    lbl_n = tk.Label(body, text=nm, bg=_BG, fg=_WHITE,
                                     font=(hud._F, _sf(10), 'bold'), anchor='w')
                    lbl_n.pack(anchor='w')
                    lbl_e = tk.Label(body, text=os.path.basename(exe), bg=_BG, fg=_DIM,
                                     font=(hud._F, _sf(8)), anchor='w')
                    lbl_e.pack(anchor='w')
                    all_w = [row, body, lbl_n, lbl_e]
                    _rows.append({'w': all_w, 'a': acc})
                    def _on_click(e=None, i=idx): _pick(i)
                    def _on_dbl(e=None, i=idx): _pick(i); _confirm()
                    for w in all_w:
                        w.bind('<Button-1>', _on_click)
                        w.bind('<Double-Button-1>', _on_dbl)
                        w.bind('<MouseWheel>', lambda e: _cv.yview_scroll(-1 if e.delta > 0 else 1, 'units'))
            _rf.update_idletasks()
            if _cv.bbox('all'): _cv.configure(scrollregion=_cv.bbox('all'))

        def _confirm():
            s = _sel[0]
            if s < 0 or s >= len(_filt): return
            on_select(*_filt[s])
            _dlg.destroy()

        def _loaded(apps):
            _all.extend(apps); _loading.pack_forget(); _fill()

        _after: list = [None]
        def _sched(e=None):
            if _after[0]:
                try: _dlg.after_cancel(_after[0])
                except Exception: pass
            _after[0] = _dlg.after(160, lambda: _fill(_sch_e.get()))
        _sch_e.bind('<KeyRelease>', _sched)

        threading.Thread(target=lambda: _dlg.after(0, lambda: _loaded(get_available_apps())),
                         daemon=True).start()

        tk.Frame(_dlg, bg=_blend(accent, 0.15), height=1).pack(fill='x')
        _br = tk.Frame(_dlg, bg=_BG); _br.pack(fill='x', padx=14, pady=10)
        _bk = dict(height=32, corner_radius=7, border_width=1, font=(hud._F, hud._fsc(9), 'bold'))
        ctk.CTkButton(_br, text=i18n.tr('dev.pick_btn'), command=_confirm,
                      fg_color=_blend(accent, 0.1), hover_color=_blend(accent, 0.22),
                      text_color=_WHITE, border_color=_blend(accent, 0.5),
                      **_bk).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ctk.CTkButton(_br, text=i18n.tr('dev.cancel_btn'), command=_dlg.destroy,
                      fg_color='transparent', hover_color=_blend(_RED, 0.12),
                      text_color=_DIM, border_color=_blend(_DIM, 0.25),
                      **_bk).pack(side='left', fill='x', expand=True)
        _dlg.grab_set()

    # --- 1. IDE CONTEXT ---
    c_context = _card('⬡', i18n.tr('dev.ide_title'), _CYAN)
    c_context.master.pack_forget()
    c_context.master.pack(fill='x', padx=20, pady=(0, 0))
    _hint(c_context, i18n.tr('dev.ide_hint'))

    _enabled_apps = hud._settings.get('context_apps', ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe'])

    # hud._fsc(), not _sf()/hud._fs() — CTk widgets are already scaled by
    # ctk.set_widget_scaling(zoom_factor) (see hud.py), so a font size that
    # also multiplies by zoom_factor itself (as _fs() does, for plain
    # tk widgets) gets scaled twice — at zoom_factor=2.0 (4K@200% Windows)
    # that made these buttons ~2x too wide and pushed the whole row (entry +
    # buttons, packed side='left' with no wrap) off the visible window edge.
    _btn_k = dict(height=30, font=(hud._F, hud._fsc(9), 'bold'), corner_radius=7, border_width=1)

    _ctx_rows_frame = tk.Frame(c_context, bg=_PANEL)
    _ctx_rows_frame.pack(fill='x', pady=(0, 8))

    def _ctx_save():
        hud._settings['context_apps'] = _enabled_apps
        _save_async()

    def _refresh_apps_list():
        for w in _ctx_rows_frame.winfo_children():
            w.destroy()
        if not _enabled_apps:
            tk.Label(_ctx_rows_frame, text=i18n.tr('dev.waiting_data'), bg=_PANEL,
                     fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=10).pack(fill='x')
            return
        for _app in sorted(_enabled_apps):
            _row = ctk.CTkFrame(
                _ctx_rows_frame, fg_color=_blend(_CYAN, 0.05), border_color=_blend(_CYAN, 0.15),
                border_width=1, corner_radius=6, height=28
            )
            _row.pack(fill='x', pady=2)

            _dot = tk.Label(_row, text="◈", bg=_blend(_CYAN, 0.05), fg=_CYAN, font=(hud._F, _sf(9)))
            _dot.pack(side='left', padx=(8, 4))

            _lbl = tk.Label(_row, text=_app, bg=_blend(_CYAN, 0.05), fg=_WHITE,
                            font=(hud._F, _sf(9), 'bold'), anchor='w')
            _lbl.pack(side='left', fill='x', expand=True, padx=(2, 8))

            def _make_remove(_a=_app):
                def _do(e=None):
                    if _a in _enabled_apps:
                        _enabled_apps.remove(_a)
                        _ctx_save()
                        _refresh_apps_list()
                return _do

            _db = ctk.CTkButton(
                _row, text="✕", width=14, height=14, corner_radius=4,
                fg_color="transparent", hover_color=_blend(_RED, 0.25),
                text_color=_blend(_CYAN, 0.5), font=(hud._F, _sf(8), 'bold'),
                command=_make_remove(_app)
            )
            _db.pack(side='right', padx=6, pady=2)

    _refresh_apps_list()

    def _ctx_add(val):
        if val and val.lower() not in [a.lower() for a in _enabled_apps]:
            _enabled_apps.append(val.lower())
            _ctx_save()
            _refresh_apps_list()

    # ── Input row: manual entry + shared picker ───────────────────────────
    _ctx_input_row = tk.Frame(c_context, bg=_PANEL)
    _ctx_input_row.pack(fill='x', pady=(0, 6))
    
    ent_app_exe = ctk.CTkEntry(_ctx_input_row, placeholder_text=i18n.tr('dev.process_name'),
                                placeholder_text_color=_blend(_WHITE, 0.3),
                                font=(hud._F, hud._fsc(10)), fg_color=_BG,
                                border_color=_blend(_CYAN, 0.3), height=30, corner_radius=7)
    ent_app_exe.pack(side='left', fill='x', expand=True, padx=(0, 6))
    _add_context_menu(ent_app_exe)
    
    _from_apps_btn = ctk.CTkButton(_ctx_input_row, text=i18n.tr('dev.from_apps_btn'),
                  command=lambda: _show_app_picker(
                      _AMBER,
                      lambda exe, name: _ctx_add(os.path.basename(exe).lower())
                  ),
                  fg_color=_blend(_AMBER, 0.05), hover_color=_blend(_AMBER, 0.15),
                  text_color=_blend(_AMBER, 0.8), border_color=_blend(_AMBER, 0.35),
                  **_btn_k)
    _from_apps_btn.pack(side='left', padx=(0, 6))

    def _ctx_do_add():
        _ctx_add(ent_app_exe.get().strip())
        ent_app_exe.delete(0, tk.END)

    _add_btn = ctk.CTkButton(_ctx_input_row, text=i18n.tr('dev.add_btn'), command=_ctx_do_add,
                  fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.2),
                  text_color=_WHITE, border_color=_blend(_CYAN, 0.4),
                  **_btn_k)
    _add_btn.pack(side='left')
    ent_app_exe.bind('<Return>', lambda e: _ctx_do_add())

    _sw_row = tk.Frame(c_context, bg=_PANEL)
    _sw_row.pack(fill='x', pady=(6, 0), padx=4)
    
    _sw_var = tk.BooleanVar(value=hud._settings.get('allow_parent_search', False))
    _sw = ctk.CTkSwitch(
        _sw_row, text="",
        variable=_sw_var,
        command=lambda: (hud._settings.update({'allow_parent_search': _sw_var.get()}),
                        _save_async()),
        progress_color=_CYAN,
        switch_width=40, switch_height=18
    )
    _sw.pack(side='left', anchor='n')
    
    _sw_lbl = tk.Label(
        _sw_row, text=i18n.tr('dev.parent_search'), bg=_PANEL, fg=_blend(_TEXT, 0.85),
        font=(hud._F, _sf(9)), justify='left', anchor='w'
    )
    _sw_lbl.pack(side='left', fill='x', expand=True, padx=(8, 0))
    _sw_lbl.bind('<Button-1>', lambda e: _sw.toggle())

    def _on_sw_row_configure(e):
        # Subtract width of switch (40) and paddings
        new_w = max(100, e.width - 55)
        _sw_lbl.configure(wraplength=new_w)
    _sw_row.bind('<Configure>', _on_sw_row_configure)

    # Folder search depth
    _depth_lbl_row = tk.Frame(c_context, bg=_PANEL)
    _depth_lbl_row.pack(fill='x', pady=(8, 0), padx=4)
    _depth_title = tk.Label(_depth_lbl_row, text=i18n.tr('dev.folder_depth'), bg=_PANEL,
                            fg=_blend(_TEXT, 0.85), font=(hud._F, _sf(9)))
    _depth_title.pack(side='left')
    _depth_val_lbl = tk.Label(_depth_lbl_row, text=str(int(hud._settings.get('folder_search_depth', 4))),
                              bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(9), 'bold'))
    _depth_val_lbl.pack(side='right')
    def _on_depth_change(val):
        v = int(float(val))
        hud._settings['folder_search_depth'] = v
        _depth_val_lbl.configure(text=str(v))
        _save_async()
    _base_slider(c_context, 1, 10, 9, _CYAN, int(hud._settings.get('folder_search_depth', 4)), _on_depth_change, hud)

    # --- 2. FILE EXTENSIONS ---
    c_code_ext = _card('📄', i18n.tr('dev.extensions_title'), _CYAN)
    _hint(c_code_ext, i18n.tr('dev.extensions_hint'))

    from actions.programming_extensions import SETTINGS_JSON_KEY as _PROG_EXT_KEY, get_programming_extensions as _g_prog_ext, normalize_extension as _norm_prog_ext, set_programming_extensions as _set_prog_ext

    _ext_chips_shell = tk.Frame(c_code_ext, bg=_PANEL)
    _ext_chips_shell.pack(fill='x', pady=(0, 6))

    def _ext_save(cur):
        def _worker():
            _set_prog_ext(cur)
            hud._settings[_PROG_EXT_KEY] = list(cur)
            _save_hud_settings(hud._settings)
        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_prog_ext_lb():
        for w in _ext_chips_shell.winfo_children():
            w.destroy()
        exts = list(_g_prog_ext())
        if not exts:
            tk.Label(_ext_chips_shell, text=i18n.tr('dev.empty'), bg=_PANEL,
                     fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=8).pack(fill='x')
            return
        _wrap = tk.Frame(_ext_chips_shell, bg=_PANEL)
        _wrap.pack(fill='x', padx=2, pady=2)
        for _ext in exts:
            _chip = ctk.CTkFrame(
                _wrap, fg_color=_blend(_CYAN, 0.05), border_color=_blend(_CYAN, 0.15),
                border_width=1, corner_radius=6, height=24
            )
            _chip.pack(side='left', padx=(0, 6), pady=2)

            _lbl = tk.Label(_chip, text=f'.{_ext}', bg=_blend(_CYAN, 0.05), fg=_CYAN,
                            font=(hud._F, _sf(9), 'bold'))
            _lbl.pack(side='left', padx=(6, 2), pady=2)

            def _del_ext(_e=_ext):
                cur = list(_g_prog_ext())
                if _e in cur: cur.remove(_e)
                _ext_save(cur)
                _refresh_prog_ext_lb()

            _db = ctk.CTkButton(
                _chip, text="✕", width=14, height=14, corner_radius=4,
                fg_color="transparent", hover_color=_blend(_RED, 0.25),
                text_color=_blend(_CYAN, 0.5), font=(hud._F, _sf(8), 'bold'),
                command=_del_ext
            )
            _db.pack(side='left', padx=(2, 4), pady=2)

    _refresh_prog_ext_lb()

    _ext_add_row = tk.Frame(c_code_ext, bg=_PANEL)
    _ext_add_row.pack(fill='x', pady=(0, 4))
    ent_code_ext = ctk.CTkEntry(_ext_add_row, placeholder_text=i18n.tr('dev.ext_placeholder'),
                                 placeholder_text_color=_blend(_WHITE, 0.3),
                                 font=(hud._F, hud._fsc(10)), fg_color=_BG,
                                 border_color=_blend(_CYAN, 0.3), height=30, corner_radius=7)
    ent_code_ext.pack(side='left', fill='x', expand=True, padx=(0, 6))
    _add_context_menu(ent_code_ext)

    def _on_add_prog_ext():
        n = _norm_prog_ext(ent_code_ext.get())
        if n:
            cur = list(_g_prog_ext())
            if n not in cur:
                cur.append(n)
                _ext_save(cur)
                _refresh_prog_ext_lb()
            ent_code_ext.delete(0, tk.END)

    ctk.CTkButton(_ext_add_row, text=i18n.tr('dev.add_btn'), command=_on_add_prog_ext,
                  fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.2),
                  text_color=_WHITE, border_color=_blend(_CYAN, 0.4), **_btn_k).pack(side='left')
    ent_code_ext.bind('<Return>', lambda e: _on_add_prog_ext())

    # --- 3. DEV PROJECTS ---
    from actions.dev_projects import (
        detect_installed_editors, get_available_apps,
        get_projects, get_default_editor, set_default_editor,
        get_editor_display_names, save_editor_display_name,
        get_custom_editors, add_custom_editor, remove_custom_editor,
        add_project, update_project_at, remove_project
    )

    c_proj = _card('◈', i18n.tr('dev.projects_title'), _GREEN)
    _hint(c_proj, i18n.tr('dev.projects_hint'))

    # Detect editors in background — avoid UI freeze on tab open
    _installed: list[tuple[str, str]] = []
    _inst_keys:  list[str] = []
    _inst_names: list[str] = []

    # ── Default editor ────────────────────────────────────────────────────
    _ed_hdr = tk.Frame(c_proj, bg=_PANEL)
    _ed_hdr.pack(fill='x', pady=(0, 5))
    tk.Label(_ed_hdr, text=i18n.tr('dev.default_editor'), bg=_PANEL, fg=_DIM,
             font=(hud._F, _sf(9))).pack(side='left')
    _cur_ed_lbl = tk.Label(_ed_hdr, text='', bg=_PANEL,
                             fg=_blend(_GREEN, 0.85), font=(hud._F, _sf(9), 'bold'))
    _cur_ed_lbl.pack(side='right')

    _cur_def = get_default_editor()
    _def_ed_var = tk.StringVar(value='')
    _def_ed_var.trace_add('write', lambda *_: _cur_ed_lbl.configure(text=_def_ed_var.get()))

    _ed_container = tk.Frame(c_proj, bg=_BG,
                              highlightbackground=_blend(_GREEN, 0.2), highlightthickness=1)
    _ed_container.pack(fill='x', pady=(0, 10))
    _chips_inner = tk.Frame(_ed_container, bg=_BG)
    _chips_inner.pack(fill='x', padx=6, pady=6)

    _chip_widgets: list = []
    _chip_btns:    list[ctk.CTkButton] = []
    _chip_keys:    list[str] = []

    _detecting_lbl = tk.Label(_chips_inner, text=i18n.tr('dev.editor_detecting'),
                               bg=_BG, fg=_blend(_GREEN, 0.35),
                               font=(hud._F, _sf(9)), pady=2)
    _detecting_lbl.pack(side='left', padx=2)

    def _rebuild_chips():
        nonlocal _cur_def
        _cur_def = get_default_editor()
        for w in _chip_widgets:
            try: w.destroy()
            except Exception: pass
        _chip_widgets.clear(); _chip_btns.clear(); _chip_keys.clear()
        _def_ed_var.set('')
        _detecting_lbl.pack(side='left', padx=2)
        threading.Thread(target=_detect_thread, daemon=True).start()

    def _on_editors_detected(result: list[tuple[str, str]]):
        _installed.clear(); _installed.extend(result)
        _inst_keys.clear();  _inst_keys.extend(k for k, _ in result)
        _inst_names.clear(); _inst_names.extend(n for _, n in result)

        # Add ALL user-saved custom editors (not just the current default)
        for _ce in get_custom_editors():
            _ck, _cn = _ce.get('key', ''), _ce.get('name', '')
            if _ck and _ck not in _inst_keys:
                _installed.append((_ck, _cn))
                _inst_keys.append(_ck)
                _inst_names.append(_cn)

        _detecting_lbl.pack_forget()
        cur_name = next((n for k, n in _installed if k == _cur_def),
                        _inst_names[0] if _inst_names else '')
        _def_ed_var.set(cur_name)

        for k, n in _installed:
            is_active = (k == _cur_def)
            _cb = ctk.CTkButton(
                _chips_inner, text=n, width=0, height=28,
                corner_radius=7, border_width=1,
                fg_color=_blend(_GREEN, 0.18) if is_active else _BG,
                border_color=_GREEN if is_active else _blend(_GREEN, 0.22),
                text_color=_WHITE if is_active else _blend(_TEXT, 0.5),
                hover_color=_blend(_GREEN, 0.14),
                font=(hud._F, _sf(9), 'bold'),
                command=lambda kk=k, nn=n: _select_editor_chip(kk, nn)
            )
            _cb.pack(side='left', padx=(0, 4))
            _chip_widgets.append(_cb)
            _chip_btns.append(_cb)
            _chip_keys.append(k)

            if k.startswith('custom:'):
                def _show_chip_menu(e, key=k, btn=_cb):
                    _m = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE,
                                 activebackground=_GREEN, activeforeground=_BG,
                                 font=(hud._F, _sf(10)))
                    _lang = i18n.get_language()
                    def _set_default():
                        _select_editor_chip(key, btn.cget('text'))
                    def _remove():
                        remove_custom_editor(key)
                        _rebuild_chips()
                    if get_default_editor() != key:
                        _m.add_command(
                            label='По умолчанию' if _lang == 'ru' else 'За замовчуванням' if _lang == 'uk' else 'Set as default',
                            command=_set_default)
                    _m.add_command(
                        label='Удалить' if _lang == 'ru' else 'Видалити' if _lang == 'uk' else 'Remove',
                        command=_remove)
                    _m.tk_popup(e.x_root, e.y_root)
                _cb.bind('<Button-3>', _show_chip_menu)

        # Update per-project editor dropdown
        _ped_values_new = [i18n.tr('dev.editor_default')] + _inst_names
        try:
            _ped_menu.configure(values=_ped_values_new)
        except Exception:
            pass

        # Compact "+" button for adding custom editor
        _plus_btn = ctk.CTkButton(
            _chips_inner, text='+', width=28, height=28,
            corner_radius=7, border_width=1,
            fg_color=_BG, border_color=_blend(_AMBER, 0.32),
            text_color=_blend(_AMBER, 0.7), hover_color=_blend(_AMBER, 0.12),
            font=(hud._F, _sf(12), 'bold'),
            command=lambda: _open_app_picker('editor')
        )
        _plus_btn.pack(side='left', padx=(4, 0))
        _chip_widgets.append(_plus_btn)

    def _detect_thread():
        result = detect_installed_editors()
        try:
            win.after(0, lambda: _on_editors_detected(result))
        except Exception:
            pass

    threading.Thread(target=_detect_thread, daemon=True).start()

    def _select_editor_chip(key: str, name: str):
        set_default_editor(key)
        _def_ed_var.set(name)
        for b, k in zip(_chip_btns, _chip_keys):
            active = (k == key)
            b.configure(
                fg_color=_blend(_GREEN, 0.18) if active else _BG,
                border_color=_GREEN if active else _blend(_GREEN, 0.22),
                text_color=_WHITE if active else _blend(_TEXT, 0.5),
            )

    def _open_app_picker(target: str = 'editor'):
        def _on_select(exe, name):
            if target == 'editor':
                ck = f'custom:{exe}'
                add_custom_editor(ck, name)
                set_default_editor(ck)
                _rebuild_chips()
        _show_app_picker(_GREEN, _on_select)

    # ── Saved projects list ───────────────────────────────────────────────
    tk.Frame(c_proj, bg=_blend(_GREEN, 0.12), height=1).pack(fill='x', pady=(2, 8))

    _proj_shell = tk.Frame(c_proj, bg=_BG,
                            highlightbackground=_blend(_GREEN, 0.15), highlightthickness=1)
    _proj_shell.pack(fill='x', pady=(0, 8))
    _proj_empty = tk.Label(_proj_shell, text=i18n.tr('dev.projects_empty'), bg=_BG,
                            fg=_blend(_GREEN, 0.3), font=(hud._F, _sf(10)), pady=10)
    _proj_rows_frame = tk.Frame(_proj_shell, bg=_BG)
    _proj_selected: list[int] = [-1]
    _proj_row_refs: list[dict] = []

    def _deselect_rows():
        _proj_selected[0] = -1
        for ref in _proj_row_refs:
            for w in ref['widgets']:
                try: w.configure(bg=_BG)
                except Exception: pass
            try: ref['acc'].configure(bg=_blend(_GREEN, 0.2))
            except Exception: pass
        _update_add_btn()

    def _select_row(idx):
        _deselect_rows()
        _proj_selected[0] = idx
        if 0 <= idx < len(_proj_row_refs):
            ref = _proj_row_refs[idx]
            for w in ref['widgets']:
                try: w.configure(bg=_blend(_GREEN, 0.07))
                except Exception: pass
            try: ref['acc'].configure(bg=_GREEN)
            except Exception: pass
        # Fill form with selected project data
        projects = get_projects()
        if 0 <= idx < len(projects):
            p = projects[idx]
            _pname_e.delete(0, tk.END)
            _pname_e.insert(0, p.get('name', ''))
            _ppath_e.delete(0, tk.END)
            _ppath_e.insert(0, p.get('path', ''))
            _hide_results()
            ed = p.get('editor', '')
            if ed:
                if ed.startswith('custom:'):
                    _sn = get_editor_display_names()
                    ed_disp = (_sn.get(ed)
                               or next((n for k, n in _installed if k == ed), None)
                               or os.path.splitext(os.path.basename(ed[7:]))[0])
                else:
                    ed_disp = next((n for k, n in _installed if k == ed), '')
                _ped_var.set(ed_disp if ed_disp in _inst_names else i18n.tr('dev.editor_default'))
            else:
                _ped_var.set(i18n.tr('dev.editor_default'))
            _update_add_btn()

    def _refresh_proj_lb():
        for w in _proj_rows_frame.winfo_children():
            w.destroy()
        _proj_row_refs.clear()
        _proj_selected[0] = -1
        projects = get_projects()

        if not projects:
            _proj_rows_frame.pack_forget()
            _proj_empty.pack(fill='x')
            return

        _proj_empty.pack_forget()
        _proj_rows_frame.pack(fill='x')

        for i, p in enumerate(projects):
            ed = p.get('editor', '')
            if ed.startswith('custom:'):
                ed_lbl = os.path.splitext(os.path.basename(ed[7:]))[0]
            else:
                ed_lbl = next((n for k, n in _installed if k == ed), ed)

            row = tk.Frame(_proj_rows_frame, bg=_BG, cursor='hand2')
            row.pack(fill='x', pady=(0, 1))

            acc = tk.Frame(row, bg=_blend(_GREEN, 0.2), width=3)
            acc.pack(side='left', fill='y')

            body = tk.Frame(row, bg=_BG)
            body.pack(side='left', fill='both', expand=True, padx=(10, 8), pady=(5, 5))

            top = tk.Frame(body, bg=_BG); top.pack(fill='x')
            lbl_n = tk.Label(top, text=p['name'], bg=_BG, fg=_WHITE,
                             font=(hud._F, _sf(10), 'bold'), anchor='w')
            lbl_n.pack(side='left')

            all_w = [row, body, top, lbl_n]

            if ed_lbl:
                lbl_e = tk.Label(top, text=f'[{ed_lbl}]', bg=_BG,
                                 fg=_blend(_GREEN, 0.65), font=(hud._F, _sf(8)), anchor='w')
                lbl_e.pack(side='left', padx=(6, 0))
                all_w.append(lbl_e)

            lbl_p = tk.Label(body, text=p['path'], bg=_BG, fg=_DIM,
                             font=(hud._F, _sf(9)), anchor='w')
            lbl_p.pack(fill='x')
            all_w.append(lbl_p)

            _proj_row_refs.append({'widgets': all_w, 'acc': acc})
            def _on_click(e=None, _i=i): _select_row(_i)
            for w in all_w: w.bind('<Button-1>', _on_click)

    _refresh_proj_lb()

    # ── Add project form ──────────────────────────────────────────────────
    _search_results: list[str] = []

    def _deselect_rows(e=None):
        _proj_selected[0] = -1
        for ref in _proj_row_refs:
            for w in ref['widgets']:
                try: w.configure(bg=_BG)
                except Exception: pass
            try: ref['acc'].configure(bg=_blend(_GREEN, 0.2))
            except Exception: pass
        _pname_e.delete(0, tk.END)
        _ppath_e.delete(0, tk.END)
        _ped_var.set(i18n.tr('dev.editor_default'))
        _hide_results()
        _add_btn.configure(text=i18n.tr('dev.add_btn'), fg_color=_blend(_GREEN, 0.1), border_color=_blend(_GREEN, 0.5))

    win.bind('<Escape>', _deselect_rows)

    _fkw = dict(fg_color=_BG, border_color=_blend(_GREEN, 0.28), height=30,
                corner_radius=7, font=(hud._F, hud._fsc(10)), placeholder_text_color=_blend(_WHITE, 0.35))

    # Mini-header above the form
    _form_hdr = tk.Frame(c_proj, bg=_PANEL)
    _form_hdr.pack(fill='x', pady=(4, 4))
    tk.Label(_form_hdr, text='◈', bg=_PANEL, fg=_blend(_GREEN, 0.5),
             font=(hud._F, _sf(9))).pack(side='left', padx=(0, 5))
    tk.Label(_form_hdr, text=i18n.tr('dev.proj_name').upper(), bg=_PANEL,
             fg=_blend(_GREEN, 0.45), font=(hud._F, _sf(8))).pack(side='left')

    # Form container — dark bg, subtle green border
    _form_shell = tk.Frame(c_proj, bg=_BG,
                            highlightbackground=_blend(_GREEN, 0.18), highlightthickness=1)
    _form_shell.pack(fill='x', pady=(0, 6))
    _fi = tk.Frame(_form_shell, bg=_BG)
    _fi.pack(fill='x', padx=10, pady=8)

    # ── Name row ──
    _name_row = tk.Frame(_fi, bg=_BG); _name_row.pack(fill='x', pady=(0, 5))
    _pname_e = ctk.CTkEntry(_name_row,
                              placeholder_text=i18n.tr('dev.proj_name_ph'), **_fkw)
    _pname_e.pack(side='left', fill='x', expand=True, padx=(0, 6))

    def _on_name_change(e=None):
        if not _pname_e.get().strip():
            _hide_results()
    _pname_e.bind('<KeyRelease>', _on_name_change)

    _search_status = tk.StringVar(value='')
    _find_btn = ctk.CTkButton(_name_row, text=i18n.tr('dev.find_btn'), width=0, height=30,
                               corner_radius=7, border_width=1,
                               fg_color=_blend(_GREEN, 0.07), hover_color=_blend(_GREEN, 0.2),
                               text_color=_WHITE, border_color=_blend(_GREEN, 0.35),
                               font=(hud._F, hud._fsc(9), 'bold'))
    _find_btn.pack(side='left')

    # ── Search results (always pre-packed here, between name and path) ──
    _res_shell = tk.Frame(_fi, bg=_BG,
                           highlightbackground=_blend(_GREEN, 0.28), highlightthickness=0)
    _res_shell.pack(fill='x')
    _res_content = tk.Frame(_res_shell, bg=_BG)
    _status_lbl = tk.Label(_res_content, textvariable=_search_status, bg=_BG,
                            fg=_blend(_GREEN, 0.6), font=(hud._F, _sf(9)), anchor='w')
    _status_lbl.pack(fill='x', padx=4, pady=(4, 2))
    _res_lb = tk.Listbox(_res_content, font=(hud._F, _sf(10)), bg=_BG, fg=_GREEN,
                          selectbackground=_blend(_GREEN, 0.22), highlightcolor=_GREEN,
                          borderwidth=0, highlightthickness=0, activestyle='none')
    _res_lb.pack(fill='x', padx=4, pady=(0, 4))

    def _hide_results():
        _res_content.pack_forget()
        _res_shell.configure(highlightthickness=0)

    def _do_search():
        query = _pname_e.get().strip()
        if not query: return
        _search_status.set(i18n.tr('dev.searching'))
        _res_shell.configure(highlightthickness=1)
        _res_content.pack(fill='x')
        _res_lb.delete(0, 'end')
        _search_results.clear()
        _find_btn.configure(state='disabled')

        def _worker():
            from actions.dev_projects import search_projects_on_disk
            results = search_projects_on_disk(query)
            win.after(0, lambda r=results: _show_results(r))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_results(results: list[str]):
        _find_btn.configure(state='normal')
        _search_results.clear()
        _search_results.extend(results)
        _res_lb.delete(0, 'end')
        if not results:
            _search_status.set(i18n.tr('dev.not_found'))
        else:
            _search_status.set(i18n.tr('dev.found_count').replace('{n}', str(len(results))))
            for r in results:
                _res_lb.insert('end', f'  {r}')

    def _pick_result(evt=None):
        sel = _res_lb.curselection()
        if not sel: return
        path = _search_results[sel[0]]
        _ppath_e.delete(0, tk.END)
        _ppath_e.insert(0, path)
        if not _pname_e.get().strip():
            _pname_e.delete(0, tk.END)
            base = os.path.basename(path)
            base = base[0].upper() + base[1:] if base else base
            _pname_e.insert(0, base)
        _hide_results()

    _res_lb.bind('<Double-Button-1>', _pick_result)
    _res_lb.bind('<Return>', _pick_result)
    _find_btn.configure(command=_do_search)

    # ── Path row ──
    _path_row = tk.Frame(_fi, bg=_BG); _path_row.pack(fill='x', pady=(0, 5))
    _ppath_e = ctk.CTkEntry(_path_row,
                              placeholder_text=i18n.tr('dev.proj_path_ph'), **_fkw)
    _ppath_e.pack(side='left', fill='x', expand=True, padx=(0, 6))

    def _browse_proj():
        from tkinter import filedialog
        path = filedialog.askdirectory(title=i18n.tr('dev.browse_title'), parent=win)
        if path:
            _ppath_e.delete(0, tk.END)
            _ppath_e.insert(0, path.replace('/', '\\'))
            if not _pname_e.get().strip():
                _pname_e.delete(0, tk.END)
                base = os.path.basename(path)
                base = base[0].upper() + base[1:] if base else base
                _pname_e.insert(0, base)

    ctk.CTkButton(_path_row, text='📁', width=30, height=30, corner_radius=7, border_width=1,
                  fg_color=_blend(_GREEN, 0.07), hover_color=_blend(_GREEN, 0.2),
                  text_color=_WHITE, border_color=_blend(_GREEN, 0.35),
                  font=(hud._F, hud._fsc(10)), command=_browse_proj).pack(side='left')

    # ── Editor row ──
    _ped_row = tk.Frame(_fi, bg=_BG); _ped_row.pack(fill='x')
    _ped_values = [i18n.tr('dev.editor_default')] + _inst_names
    _ped_var = tk.StringVar(value=i18n.tr('dev.editor_default'))
    _ped_menu = _HUDDropdown(hud, _ped_row, _ped_values, _ped_var, accent=_GREEN)
    _ped_menu.configure(height=30)
    _ped_menu.frame.pack(fill='x')

    # Action buttons
    def _clear_form():
        _pname_e.delete(0, tk.END); _ppath_e.delete(0, tk.END)
        _ped_var.set(i18n.tr('dev.editor_default'))
        _hide_results()
        _deselect_rows()

    def _update_add_btn():
        if _proj_selected[0] >= 0:
            try: _add_btn.configure(text='✎  ' + i18n.tr('dev.update_btn'),
                                    fg_color=_blend(_CYAN, 0.1),
                                    border_color=_blend(_CYAN, 0.5),
                                    hover_color=_blend(_CYAN, 0.22))
            except Exception: pass
        else:
            try: _add_btn.configure(text='+ ' + i18n.tr('dev.add_btn'),
                                    fg_color=_blend(_GREEN, 0.1),
                                    border_color=_blend(_GREEN, 0.5),
                                    hover_color=_blend(_GREEN, 0.22))
            except Exception: pass

    def _add_proj():
        n, p = _pname_e.get().strip(), _ppath_e.get().strip()
        if not n or not p: return
        n = n[0].upper() + n[1:] if n else n
        ed_label = _ped_var.get()
        if ed_label == i18n.tr('dev.editor_default') or ed_label not in _inst_names:
            ed_key = ''
        else:
            idx_ed = _inst_names.index(ed_label)
            ed_key = _inst_keys[idx_ed] if idx_ed < len(_inst_keys) else ''
        sel_idx = _proj_selected[0]
        if sel_idx >= 0:
            update_project_at(sel_idx, n, p, ed_key)
        else:
            add_project(n, p, ed_key)
        _clear_form()
        _refresh_proj_lb()

    def _del_proj():
        idx = _proj_selected[0]
        if idx < 0: return
        projects = get_projects()
        if idx < len(projects):
            remove_project(projects[idx]['name'])
        _clear_form()
        _refresh_proj_lb()

    _btn_row = tk.Frame(c_proj, bg=_PANEL); _btn_row.pack(fill='x', pady=(2, 0))

    _add_btn = ctk.CTkButton(_btn_row, text='+ ' + i18n.tr('dev.add_btn'), command=_add_proj,
                  fg_color=_blend(_GREEN, 0.1), hover_color=_blend(_GREEN, 0.22),
                  text_color=_WHITE, border_color=_blend(_GREEN, 0.5), **_btn_k)
    _add_btn.pack(side='left', fill='x', expand=True, padx=(0, 2))

    _del_btn = ctk.CTkButton(_btn_row, text=i18n.tr('dev.delete_btn'), command=_del_proj,
                  fg_color=_blend(_RED, 0.08), hover_color=_blend(_RED, 0.2),
                  text_color=_WHITE, border_color=_blend(_RED, 0.4), **_btn_k)
    _del_btn.pack(side='left', fill='x', expand=True, padx=(2, 0))

    # Bind select/deselect helper to select row function
    _orig_select_row = _select_row
    def _select_row_wrapper(idx):
        _orig_select_row(idx)
        # Update Add/Save button visual when a project is selected
        _add_btn.configure(text=i18n.tr('buttons.save'), fg_color=_blend(_AMBER, 0.15), border_color=_blend(_AMBER, 0.5))
    _select_row = _select_row_wrapper

    # Bind deselect when clicking on empty background
    c_proj.bind('<Button-1>', lambda e: _deselect_rows(), add='+')
    inner.bind('<Button-1>', lambda e: _deselect_rows(), add='+')
