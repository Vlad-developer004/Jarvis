import os, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar
from ui.hud_widgets import _HudScrollbar, _HUDDropdown

def _add_context_menu(win, entry, hud, _sf):
    menu = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, _sf(9)))
    def _paste():
        try:
            import pyperclip
            txt = pyperclip.paste()
            if txt:
                if entry.selection_present(): entry.delete('sel.first', 'sel.last')
                entry.insert(tk.INSERT, txt)
        except Exception: pass
    def _copy():
        try:
            if entry.selection_present():
                win.clipboard_clear(); win.clipboard_append(entry.selection_get())
        except Exception: pass
    def _select_all():
        entry.select_range(0, 'end'); entry.icursor('end')
    menu.add_command(label='Вставить (Ctrl+V)', command=_paste)
    menu.add_command(label='Копировать (Ctrl+C)', command=_copy)
    menu.add_separator()
    menu.add_command(label='Выделить всё (Ctrl+A)', command=_select_all)
    entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    entry.bind('<Control-v>', lambda e: (_paste(), 'break'))
    entry.bind('<Control-V>', lambda e: (_paste(), 'break'))
    entry.bind('<Control-a>', lambda e: (_select_all(), 'break'))
    entry.bind('<Control-A>', lambda e: (_select_all(), 'break'))

def _card(parent, icon: str, title: str, accent: str, hud):
    _sf = lambda n: hud._fs(n + 6)
    outer = tk.Frame(parent, bg=_PANEL, highlightbackground=_blend(accent, 0.2), highlightthickness=1)
    outer.pack(fill='x', padx=20, pady=(14, 0))
    tk.Frame(outer, bg=accent, width=3).pack(side='left', fill='y')
    body = tk.Frame(outer, bg=_PANEL)
    body.pack(side='left', fill='both', expand=True, padx=(16, 18), pady=(14, 14))
    head = tk.Frame(body, bg=_PANEL)
    head.pack(fill='x', pady=(0, 6))
    tk.Label(head, text=icon, bg=_PANEL, fg=accent, font=(hud._F, _sf(16))).pack(side='left', padx=(0, 10))
    tk.Label(head, text=title, bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='w').pack(side='left')
    return body

def _hint(parent, text: str, hud):
    _sf = lambda n: hud._fs(n + 6)
    lbl = tk.Label(parent, text=text, bg=_PANEL, fg=_blend(_TEXT, 0.72), font=(hud._F, _sf(10)), anchor='w', justify='left')
    lbl.pack(fill='x', pady=(0, 8))
    def _upd_hint(e, l=lbl):
        new_wl = max(hud._px(100), e.width - hud._px(8))
        l.configure(wraplength=new_wl)
    parent.bind('<Configure>', _upd_hint, add='+')
    def _try_init_wrap(tries_left: int = 10):
        try: w = int(parent.winfo_width() or 0)
        except Exception: w = 0
        if w > 1: _upd_hint(type('E', (), {'width': w})()); return
        if tries_left > 0: parent.after(30, lambda: _try_init_wrap(tries_left - 1))
    parent.after(10, _try_init_wrap)

def _label_row(parent, label: str, accent: str, hud):
    _sf = lambda n: hud._fs(n + 6)
    row = tk.Frame(parent, bg=_PANEL)
    row.pack(fill='x', pady=(6, 0))
    
    lbl = tk.Label(row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11), 'bold'), anchor='w', justify='left')
    lbl.pack(side='left', fill='x', expand=True, anchor='nw')
    
    val_lbl = tk.Label(row, text='', bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='e', justify='right')
    val_lbl.pack(side='right', padx=(10, 0), anchor='ne')
    
    _last_row_w = [0]
    def _upd_row(e, l=lbl, v=val_lbl):
        try:
            if abs(e.width - _last_row_w[0]) < 10: return
            _last_row_w[0] = e.width
            v_req = v.winfo_reqwidth()
            l.configure(wraplength=max(100, e.width - (v_req + 20)))
            if v_req > e.width * 0.6:
                v.configure(wraplength=int(e.width * 0.4))
            else:
                v.configure(wraplength=0)
        except Exception: pass
            
    row.bind('<Configure>', _upd_row, add='+')
    return val_lbl

def _slider(parent, from_, to, steps, accent, init_val, callback, hud):
    s = ctk.CTkSlider(parent, from_=from_, to=to, number_of_steps=steps, progress_color=accent, button_color=accent, button_hover_color=_blend(accent, 0.7), fg_color=_BRD_I, height=hud._px(16))
    s.set(init_val)
    s.pack(fill='x', pady=(10, 4))
    s.configure(command=callback)
    return s

def _std_action_btn(parent, text: str, command, accent: str, hud, **grid_kw):
    _sf = lambda n: hud._fs(n + 6)
    b = ctk.CTkButton(parent, text=text, command=command, height=hud._px(44), font=(hud._F, _sf(10), 'bold'), fg_color=_blend(accent, 0.08), hover_color=_blend(accent, 0.18), text_color=accent, border_color=_blend(accent, 0.32), border_width=1, corner_radius=10)
    if grid_kw:
        b.grid(**grid_kw)
    return b

def _hero_btn(parent, text: str, command, accent: str, hud, **grid_kw):
    _sf = lambda n: hud._fs(n + 6)
    # More prominent button with stronger borders and solid-ish accent on hover
    b = ctk.CTkButton(parent, text=text, command=command, height=hud._px(50), 
                      font=(hud._F, _sf(11), 'bold'), 
                      fg_color=_blend(accent, 0.12), 
                      hover_color=_blend(accent, 0.25), 
                      text_color=accent, 
                      border_color=accent, 
                      border_width=2, 
                      corner_radius=12)
    if grid_kw:
        b.grid(**grid_kw)
    return b

def _pick_app_dialog(win, hud, on_selected):
    from core.system.windows import get_installed_apps
    _sf = lambda n: hud._fs(n + 6)
    apps = get_installed_apps()
    pick_win = ctk.CTkToplevel(win); pick_win.title("ВЫБОР ПРИЛОЖЕНИЯ"); pick_win.geometry(f"{hud._px(600)}x{hud._px(700)}")
    pick_win.configure(bg=_BG); _set_dark_title_bar(pick_win); pick_win.attributes("-topmost", True); pick_win.lift()
    top_bar = tk.Frame(pick_win, bg=_BG); top_bar.pack(fill='x', padx=20, pady=(20, 10))
    tk.Label(top_bar, text="ВЫБЕРИТЕ ПРИЛОЖЕНИЕ", bg=_BG, fg=_CYAN, font=(hud._F, _sf(14), 'bold')).pack(anchor='w')
    tk.Label(top_bar, text="Выберите программу для добавления в список", bg=_BG, fg=_DIM, font=(hud._F, _sf(10))).pack(anchor='w')
    ctrl_f = tk.Frame(pick_win, bg=_BG); ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
    ent_search = ctk.CTkEntry(ctrl_f, placeholder_text='Поиск...', font=(hud._F, _sf(11)), fg_color='#0c121c', border_color=_blend(_CYAN, 0.3), height=hud._px(44), corner_radius=10)
    ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
    _show_all_var = tk.BooleanVar(value=False)
    sw_all = ctk.CTkSwitch(ctrl_f, text='Системные', variable=_show_all_var, font=(hud._F, _sf(10), 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=hud._px(36), switch_height=hud._px(18))
    sw_all.pack(side='right')
    lb_frame = tk.Frame(pick_win, bg='#070a10', highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1); lb_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
    lb = tk.Listbox(lb_frame, bg='#0c121c', fg=_TEXT, font=(hud._F, _sf(11)), borderwidth=0, highlightthickness=0, selectbackground=_blend(_CYAN, 0.3), activestyle='none')
    sb = _HudScrollbar(lb_frame, lb, color=_CYAN); lb.config(yscrollcommand=sb.set); lb.pack(side='left', fill='both', expand=True, padx=8, pady=8)
    _f_data = []
    def _refresh(*_):
        lb.delete(0, tk.END); search = ent_search.get().lower().strip(); show_all = _show_all_var.get(); _f_data.clear()
        ides = [a for a in apps if a.get('is_ide')]; others = [a for a in apps if not a.get('is_ide')]
        for app in ides + others:
            if app.get('is_noise') and not show_all: continue
            if search and search not in app['name'].lower() and search not in (app.get('exe') or '').lower(): continue
            prefix = "✦ " if app.get('is_ide') else "  "; exe_part = f" — {app['exe']}" if app.get('exe') else ""
            lb.insert(tk.END, f"{prefix}{app['name']}{exe_part}"); _f_data.append(app)
    ent_search.bind('<KeyRelease>', _refresh); sw_all.configure(command=_refresh); _refresh()
    def _on_pick(_e=None):
        sel = lb.curselection()
        if sel:
            app = _f_data[sel[0]]; on_selected(app.get('exe') or app['name']); pick_win.destroy()
    lb.bind('<Double-Button-1>', _on_pick)
    ctk.CTkButton(pick_win, text="ВЫБРАТЬ ПРИЛОЖЕНИЕ", command=_on_pick, height=hud._px(50), font=(hud._F, _sf(12), 'bold'), fg_color=_CYAN, text_color=_BG).pack(fill='x', padx=20, pady=(0, 20))
