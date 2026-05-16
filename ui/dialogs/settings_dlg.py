from __future__ import annotations
from ui.hud_style import JStyle
from core import i18n
import json, os, threading, time, sys, subprocess
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _make_resizable, _get_work_area
from ..hud_widgets import _HudScrollbar

def open_settings(hud, reopen: bool = False) -> None:
    from pathlib import Path
    import importlib
    _hud_mod = importlib.import_module('ui.hud')
    _save_hud_settings = _hud_mod._save_hud_settings
    
    if not reopen and hasattr(hud, '_settings_win') and hud._settings_win and hud._settings_win.winfo_exists():
        hud._settings_win.lift()
        return
    if reopen and hasattr(hud, '_settings_win') and hud._settings_win and hud._settings_win.winfo_exists():
        hud._settings_win.destroy()
        
    win = tk.Toplevel(hud.root)
    hud._settings_win = win
    win.title(i18n.tr('settings.title'))
    hud._track_subwin('settings', win, lambda: open_settings(hud, reopen=True))
    
    win.configure(bg=_BG)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)

    l, t, r, b = _get_work_area()
    work_w = r - l
    work_h = b - t
    _W = int(min(1120 * hud.zoom_factor, work_w * 0.95))
    _H = int(min(800 * hud.zoom_factor, work_h * 0.90))
    _center_window(win, _W, _H)
    
    # Минимальный порог, чтобы вкладки и настройки не «схлопнулись»
    win.minsize(hud._px(850), hud._px(550))
    
    win.resizable(True, True)

    _sf = lambda n: hud._fs(n + 6)
    _sfc = lambda n: n + 6
    _hdr_bg = _BG
    
    # THE FAMOUS CYAN LINE
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')
    
    hdr_outer = tk.Frame(win, bg=_hdr_bg)
    hdr_outer.pack(fill='x')

    hdr = tk.Frame(hdr_outer, bg=_hdr_bg)
    hdr.pack(fill='x', padx=28, pady=(18, 14))
    
    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.12), highlightbackground=_blend(_CYAN, 0.35), highlightthickness=1)
    badge.pack(side='left', padx=(0, 14), anchor='nw')
    tk.Label(badge, text='⚙', bg=_blend(_CYAN, 0.12), fg=_CYAN, font=(hud._F, _sf(22))).pack(padx=10, pady=6)
    
    hdr_text = tk.Frame(hdr, bg=_hdr_bg)
    hdr_text.pack(side='left', fill='x', expand=True, anchor='nw')
    
    title_lbl = tk.Label(hdr_text, text=i18n.tr('settings.header'), bg=_hdr_bg, fg=_CYAN, font=(hud._F, _sf(16), 'bold'), anchor='w', justify='left')
    title_lbl.pack(anchor='w', fill='x')

    sub_lbl = tk.Label(hdr_text, text=i18n.tr('settings.subtitle'), bg=_hdr_bg, fg=_DIM, font=(hud._F, _sf(10)), anchor='w', justify='left')
    sub_lbl.pack(anchor='w', fill='x')

    def _upd_hdr_wrap(e, t=title_lbl, s=sub_lbl):
        t.configure(wraplength=max(hud._px(100), e.width - 20))
        s.configure(wraplength=max(hud._px(100), e.width - 20))
    hdr_text.bind('<Configure>', _upd_hdr_wrap, add='+')
    tk.Frame(win, bg=_BRD_I, height=1).pack(fill='x')

    # --- Навигация вкладок (Динамичная и центрированная) ---
    tab_bar_outer = tk.Frame(win, bg=_BG)
    tab_bar_outer.pack(fill='x', padx=20, pady=0)
    
    tab_canvas = tk.Canvas(tab_bar_outer, bg=_BG, highlightthickness=0)
    tab_canvas.pack(fill='x', expand=True)
    
    tk.Frame(tab_bar_outer, bg=_BRD_I, height=1).pack(fill='x', pady=(0, 0))
    
    hsb = _HudScrollbar(tab_bar_outer, tab_canvas, color=_CYAN, orient='horizontal')
    tab_canvas.configure(xscrollcommand=hsb.set)
    
    tab_bar = tk.Frame(tab_canvas, bg=_BG)
    tcw = tab_canvas.create_window((0, 0), window=tab_bar, anchor='nw')

    def _upd_tab_scroll(_e=None):
        try:
            tab_bar.update_idletasks()
            total_w = tab_bar.winfo_reqwidth()
            total_h = tab_bar.winfo_reqheight()
            canvas_w = tab_canvas.winfo_width()
            
            v_pad = int(12 * hud.zoom_factor)
            dynamic_h = total_h + (v_pad * 2)
            tab_canvas.configure(height=dynamic_h)

            if total_w < canvas_w:
                tab_canvas.itemconfig(tcw, anchor='center')
                tab_canvas.coords(tcw, canvas_w // 2, dynamic_h // 2)
            else:
                tab_canvas.itemconfig(tcw, anchor='w')
                tab_canvas.coords(tcw, 0, dynamic_h // 2)
                
            tab_canvas.configure(scrollregion=tab_canvas.bbox('all'))
        except Exception: pass

    tab_bar.bind('<Configure>', _upd_tab_scroll)
    tab_canvas.bind('<Configure>', _upd_tab_scroll)

    def _on_tab_mousewheel(e):
        try:
            total_w = tab_bar.winfo_width()
            canvas_w = tab_canvas.winfo_width()
            if total_w > canvas_w:
                tab_canvas.xview_scroll(int(-1 * (e.delta / 120)), 'units')
            else:
                for frame in tab_frames.values():
                    if frame.winfo_viewable():
                        for child in frame.winfo_children():
                            if isinstance(child, tk.Canvas):
                                child.yview_scroll(int(-1 * (e.delta / 120)), 'units')
                                break
                        break
        except Exception: pass
    
    tab_canvas.bind('<MouseWheel>', _on_tab_mousewheel)
    tab_bar.bind('<MouseWheel>', _on_tab_mousewheel)

    tab_content = tk.Frame(win, bg=_BG)
    tab_content.pack(fill='both', expand=True)

    tab_frames: dict[str, tk.Frame] = {}
    tab_btns: dict[str, ctk.CTkButton] = {}
    built_tabs = set()

    def switch_tab(name: str):
        for k, f in tab_frames.items():
            f.pack_forget()
            tab_btns[k].configure(fg_color='transparent', text_color=_DIM)
        
        if name not in built_tabs:
            _build_tab_content(name)
            built_tabs.add(name)

        tab_frames[name].pack(fill='both', expand=True)
        tab_btns[name].configure(fg_color=_blend(_CYAN, 0.1), text_color=_CYAN)
        _ensure_active_visible(name)

    def _build_tab_content(name: str):
        import importlib
        try:
            inner_scroll = make_scrollable(tab_frames[name])
            mod_path = f'ui.dialogs.settings_tabs.{name}'
            mod = importlib.import_module(mod_path)
            build_func = getattr(mod, f'build_{name}_tab')
            build_func(inner_scroll, win, hud, _save_hud_settings)
        except Exception as e:
            tk.Label(tab_frames[name], text=i18n.tr('settings.tab_error').format(e=e), fg=_RED, bg=_BG).pack(expand=True)

    def make_scrollable(parent):
        scroll_canvas = tk.Canvas(parent, bg=_BG, highlightthickness=0, borderwidth=0)
        scroll_canvas.pack(side='left', fill='both', expand=True)
        inner_f = tk.Frame(scroll_canvas, bg=_BG)
        cw = scroll_canvas.create_window((0, 0), window=inner_f, anchor='nw')
        vsb = _HudScrollbar(parent, scroll_canvas, color=_CYAN)
        scroll_canvas.configure(yscrollcommand=vsb.set)

        def _upd_scroll(*_):
            if not scroll_canvas.winfo_exists(): return
            inner_f.update_idletasks()
            h = inner_f.winfo_reqheight()
            cw_w = scroll_canvas.winfo_width()
            ch = scroll_canvas.winfo_height()
            if cw_w > 10:
                scroll_canvas.itemconfig(cw, width=cw_w)
            scroll_canvas.configure(scrollregion=(0, 0, cw_w, max(h, ch)))
            scroll_canvas.yview_scroll(0, 'units')

        _last_w = [0]
        def _on_cfg(e):
            if not scroll_canvas.winfo_exists(): return
            if abs(e.width - _last_w[0]) < 2: return
            _last_w[0] = e.width
            scroll_canvas.itemconfig(cw, width=e.width)
            # Aggressive updates
            scroll_canvas.after(50, _upd_scroll)
            scroll_canvas.after(350, _upd_scroll)
            scroll_canvas.after(800, _upd_scroll)

        inner_f.bind('<Configure>', lambda e: (
            scroll_canvas.after(50, _upd_scroll),
            scroll_canvas.after(350, _upd_scroll),
            scroll_canvas.after(800, _upd_scroll)
        ))
        scroll_canvas.bind('<Configure>', _on_cfg)

        def _bind_mw(w):
            try:
                if w.winfo_class() not in ('Listbox', 'Text'):
                    w.bind('<MouseWheel>', lambda e: scroll_canvas.yview_scroll(-1*(e.delta//120), 'units'), add='+')
            except: pass
            for child in w.winfo_children(): _bind_mw(child)
        win.after(600, lambda: _bind_mw(inner_f))
        return inner_f

    tab_meta = [
        ('appearance', i18n.tr('tab.appearance'), _CYAN),
        ('voice', i18n.tr('tab.voice'), _CYAN),
        ('modules', i18n.tr('tab.modules'), _CYAN),
        ('dev', i18n.tr('tab.dev'), _CYAN),
        ('tools', i18n.tr('tab.tools'), _CYAN)
    ]

    for key, label, col in tab_meta:
        btn = ctk.CTkButton(
            tab_bar, text=label, command=lambda k=key: switch_tab(k),
            height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY),
            fg_color='transparent', text_color=_DIM, hover_color=_blend(_CYAN, 0.15),
            corner_radius=JStyle.RAD_PANEL, border_spacing=8
        )
        btn.pack(side='left', padx=2)
        btn.bind('<MouseWheel>', _on_tab_mousewheel)
        tab_btns[key] = btn
        tab_frames[key] = tk.Frame(tab_content, bg=_BG)
    
    def _ensure_active_visible(name):
        def _do():
            try:
                if not win.winfo_exists(): return
                btn = tab_btns[name]
                bx, bw = btn.winfo_x(), btn.winfo_width()
                tw, cw = tab_bar.winfo_width(), tab_canvas.winfo_width()
                if tw <= cw: return
                tx = bx - (cw - bw) / 2
                tab_canvas.xview_moveto(max(0, tx / tw))
            except: pass
        win.after(150, _do)

    switch_tab('appearance')