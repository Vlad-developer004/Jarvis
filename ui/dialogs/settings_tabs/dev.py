from ui.hud_style import JStyle
from core import i18n
import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
from ui.hud_widgets import _HudScrollbar

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

    def _refresh_apps_list():
        lb_ctx_apps.delete(0, tk.END)
        if not _enabled_apps: _ctx_apps_lb_shell.pack_forget(); _ctx_empty_lbl.pack(fill='x', pady=6, padx=4)
        else: _ctx_empty_lbl.pack_forget(); _ctx_apps_lb_shell.pack(fill='x', pady=6, padx=4); [lb_ctx_apps.insert(tk.END, f"  ✓ {app}") for app in sorted(_enabled_apps)]; lb_ctx_apps.config(height=max(1, len(_enabled_apps)))

    # --- 1. IDE CONTEXT ---
    c_context = _card('⬡', i18n.tr('dev.ide_title'), _CYAN)
    c_context.master.pack_forget()
    c_context.master.pack(fill='x', padx=20, pady=(0, 0))
    _hint(c_context, i18n.tr('dev.ide_hint'))

    _ctx_apps_lb_shell = tk.Frame(c_context, bg=_BG, highlightbackground=_blend(_CYAN, 0.1), highlightthickness=1)
    _ctx_apps_lb_shell.pack(fill='x', pady=(4, 8))
    lb_ctx_apps = tk.Listbox(_ctx_apps_lb_shell, font=(hud._F, _sf(10)), bg=_BG, fg=_TEXT, selectbackground=_blend(_CYAN, 0.25), height=1, borderwidth=0, highlightthickness=0, activestyle='none')
    lb_ctx_apps.pack(fill='x', padx=6, pady=6)

    _enabled_apps = hud._settings.get('context_apps', ['code.exe', 'pycharm64.exe', 'phpstorm64.exe', 'antigravity.exe'])
    _ctx_empty_lbl = tk.Label(c_context, text=i18n.tr('dev.waiting_data'), bg=_PANEL, fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=10)
    _refresh_apps_list()

    ent_app_exe = ctk.CTkEntry(c_context, placeholder_text=i18n.tr('dev.process_name'), font=(hud._F, _sf(10)), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=32, corner_radius=8)
    ent_app_exe.pack(fill='x', padx=4, pady=(0, 8)); _add_context_menu(ent_app_exe)
    
    _ctx_btn_row = tk.Frame(c_context, bg=_PANEL); _ctx_btn_row.pack(fill='x')
    _btn_k = dict(height=32, font=(hud._F, _sf(9), 'bold'), corner_radius=8, border_width=1)

    def _ctx_add(val):
        if val and val.lower() not in [a.lower() for a in _enabled_apps]:
            _enabled_apps.append(val.lower()); hud._settings['context_apps'] = _enabled_apps; _save_hud_settings(hud._settings); _refresh_apps_list()

    ctk.CTkButton(_ctx_btn_row, text=i18n.tr('dev.add_btn'), command=lambda: _ctx_add(ent_app_exe.get().strip()), fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.2), text_color=_WHITE, border_color=_blend(_CYAN, 0.4), **_btn_k).pack(side='left', fill='x', expand=True, padx=2)
    ctk.CTkButton(_ctx_btn_row, text=i18n.tr('dev.active_btn'), command=lambda: ent_app_exe.delete(0, tk.END) or ent_app_exe.insert(0, os.path.basename(__import__('core.system.windows', fromlist=['get_foreground_process_exe']).get_foreground_process_exe() or '').lower()), fg_color=_blend(_AMBER, 0.08), hover_color=_blend(_AMBER, 0.2), text_color=_WHITE, border_color=_blend(_AMBER, 0.4), **_btn_k).pack(side='left', fill='x', expand=True, padx=2)
    ctk.CTkButton(_ctx_btn_row, text=i18n.tr('dev.delete_btn'), command=lambda: (_enabled_apps.remove(lb_ctx_apps.get(lb_ctx_apps.curselection()[0]).replace('  ✓ ', '').strip()), hud._settings.update({'context_apps': _enabled_apps}), _save_hud_settings(hud._settings), _refresh_apps_list()) if lb_ctx_apps.curselection() else None, fg_color=_blend(_RED, 0.08), hover_color=_blend(_RED, 0.2), text_color=_WHITE, border_color=_blend(_RED, 0.4), **_btn_k).pack(side='left', fill='x', expand=True, padx=2)

    ctk.CTkSwitch(c_context, text=i18n.tr('dev.parent_search'), variable=tk.BooleanVar(value=hud._settings.get('allow_parent_search', False)), command=lambda: (hud._settings.update({'allow_parent_search': not hud._settings.get('allow_parent_search')}), _save_hud_settings(hud._settings)), font=(hud._F, _sf(10)), progress_color=_CYAN, switch_width=40, switch_height=18).pack(anchor='w', pady=(12, 0), padx=4)

    # --- 2. FILE EXTENSIONS ---
    c_code_ext = _card('📄', i18n.tr('dev.extensions_title'), _CYAN)
    _hint(c_code_ext, i18n.tr('dev.extensions_hint'))
    
    from actions.programming_extensions import SETTINGS_JSON_KEY as _PROG_EXT_KEY, get_programming_extensions as _g_prog_ext, normalize_extension as _norm_prog_ext, set_programming_extensions as _set_prog_ext
    
    _ext_well = tk.Frame(c_code_ext, bg=_blend(_CYAN, 0.05), highlightbackground=_blend(_CYAN, 0.15), highlightthickness=1); _ext_well.pack(fill='both', expand=True, pady=(2, 8))
    _ext_empty_lbl = tk.Label(_ext_well, text=i18n.tr('dev.empty'), bg=_blend(_CYAN, 0.05), fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(10)), pady=10)
    lb_code_ext = tk.Listbox(_ext_well, font=(hud._F, _sf(10)), bg=_BG, fg=_TEXT, selectbackground=_blend(_CYAN, 0.25), height=1, borderwidth=0, highlightthickness=0, activestyle='none')

    def _refresh_prog_ext_lb():
        lb_code_ext.delete(0, tk.END); exts = list(_g_prog_ext())
        if not exts: lb_code_ext.pack_forget(); _ext_empty_lbl.pack(fill='x', pady=10)
        else: _ext_empty_lbl.pack_forget(); lb_code_ext.pack(fill='x', padx=6, pady=6); [lb_code_ext.insert(tk.END, f'  .{e}') for e in exts]; lb_code_ext.config(height=max(1, min(6, len(exts))))
    _refresh_prog_ext_lb()

    def _on_add_prog_ext():
        n = _norm_prog_ext(ent_code_ext.get())
        if n:
            cur = list(_g_prog_ext())
            if n not in cur: cur.append(n); _set_prog_ext(cur); hud._settings[_PROG_EXT_KEY] = list(cur); _save_hud_settings(hud._settings); _refresh_prog_ext_lb()
            ent_code_ext.delete(0, tk.END)

    ent_code_ext = ctk.CTkEntry(c_code_ext, placeholder_text=i18n.tr('dev.ext_placeholder'), font=(hud._F, _sf(10)), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=32, corner_radius=8); ent_code_ext.pack(fill='x', pady=(0, 8), padx=4)

    _ext_btn_row = tk.Frame(c_code_ext, bg=_PANEL); _ext_btn_row.pack(fill='x')
    ctk.CTkButton(_ext_btn_row, text=i18n.tr('dev.add_btn'), command=_on_add_prog_ext, fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.2), text_color=_WHITE, border_color=_blend(_CYAN, 0.4), **_btn_k).pack(side='left', fill='x', expand=True, padx=2)
    ctk.CTkButton(_ext_btn_row, text=i18n.tr('dev.delete_btn'), command=lambda: (_on_del_prog_ext(), _refresh_prog_ext_lb()) if lb_code_ext.curselection() else None, fg_color=_blend(_RED, 0.08), hover_color=_blend(_RED, 0.2), text_color=_WHITE, border_color=_blend(_RED, 0.4), **_btn_k).pack(side='left', fill='x', expand=True, padx=2)
    
    def _on_del_prog_ext():
        sel = lb_code_ext.curselection()
        if sel:
            lines = [lb_code_ext.get(i).strip() for i in range(lb_code_ext.size())]; del lines[sel[0]]
            cur = [_norm_prog_ext(x) for x in lines if _norm_prog_ext(x)]; _set_prog_ext(cur); hud._settings[_PROG_EXT_KEY] = list(cur); _save_hud_settings(hud._settings)
