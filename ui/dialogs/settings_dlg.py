from __future__ import annotations
import json, os, threading, time, sys, subprocess
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
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
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    hud._track_subwin('settings', win, lambda: open_settings(hud, reopen=True))
    win.title('НАСТРОЙКИ — J.A.R.V.I.S.')
    _apply_window_icon(win, hud)
    win.configure(bg=_BG)
    win.update_idletasks()
    _sw_scr = win.winfo_screenwidth()
    _sh_scr = win.winfo_screenheight()
    # Calculate a comfortable "full height" (screen height minus some margin for taskbar/header)
    _target_h = _sh_scr - int(100 * hud.zoom_factor)
    win.minsize(int(850 * hud.zoom_factor), int(450 * hud.zoom_factor))
    win.geometry(f"{int(850 * hud.zoom_factor)}x{_target_h}")
    win.resizable(True, True)
    
    def _recenter():
        win.update_idletasks()
        rw, rh = win.winfo_width(), win.winfo_height()
        # Position at the top with a small margin
        win.geometry(f"{rw}x{rh}+{(_sw_scr-rw)//2}+20")
    win._recenter = _recenter
    win.lift()
    win.focus_force()
    _sf = lambda n: hud._fs(n + 6)
    _hdr_bg = _BG  # theme-aware header background
    hdr_outer = tk.Frame(win, bg=_hdr_bg)
    hdr_outer.pack(fill='x')
    hdr = tk.Frame(hdr_outer, bg=_hdr_bg)
    hdr.pack(fill='x', padx=28, pady=(18, 14))
    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.12), highlightbackground=_blend(_CYAN, 0.35), highlightthickness=1)
    badge.pack(side='left', padx=(0, 14), anchor='nw')
    tk.Label(badge, text='⚙', bg=_blend(_CYAN, 0.12), fg=_CYAN, font=(hud._F, _sf(22))).pack(padx=10, pady=6)
    
    hdr_text = tk.Frame(hdr, bg=_hdr_bg)
    hdr_text.pack(side='left', fill='x', expand=True, anchor='nw')
    
    title_lbl = tk.Label(hdr_text, text='НАСТРОЙКИ СИСТЕМЫ', bg=_hdr_bg, fg=_CYAN, font=(hud._F, _sf(16), 'bold'), anchor='w', justify='left')
    title_lbl.pack(anchor='w', fill='x')
    
    sub_lbl = tk.Label(hdr_text, text='Конфигурация интерфейса, голоса и микрофона', bg=_hdr_bg, fg=_DIM, font=(hud._F, _sf(10)), anchor='w', justify='left')
    sub_lbl.pack(anchor='w', fill='x')

    _last_hdr_w = [0]
    def _upd_hdr_wrap(e, t=title_lbl, s=sub_lbl):
        if abs(e.width - _last_hdr_w[0]) < 10: return
        _last_hdr_w[0] = e.width
        t.configure(wraplength=e.width - 20)
        s.configure(wraplength=e.width - 20)
    hdr_text.bind('<Configure>', _upd_hdr_wrap, add='+')
    tk.Frame(hdr, bg=_hdr_bg).pack(side='right', padx=10)
    tk.Frame(win, bg=_BRD_I, height=1).pack(fill='x')

    # Tab Navigation
    tab_bar_outer = tk.Frame(win, bg=_BG)
    tab_bar_outer.pack(fill='x', padx=20, pady=(0, 0)) # pady(0,0) to keep it tight
    
    tab_canvas = tk.Canvas(tab_bar_outer, bg=_BG, highlightthickness=0, height=int(58 * hud.zoom_factor))
    tab_canvas.pack(fill='x', expand=True)
    
    # Underline placeholder inside the canvas content
    # (We'll create it after the buttons)
    
    hsb = _HudScrollbar(tab_bar_outer, tab_canvas, color=_CYAN, orient='horizontal')
    tab_canvas.configure(xscrollcommand=hsb.set)
    
    tab_bar = tk.Frame(tab_canvas, bg=_BG)
    tcw = tab_canvas.create_window((0, 0), window=tab_bar, anchor='nw')

    # Indicator Frame (Neural Underline)
    indicator = tk.Frame(tab_bar, bg=_CYAN, height=2)

    def _upd_tab_scroll(_e=None):
        try:
            tab_bar.update_idletasks()
            total_w = tab_bar.winfo_width()
            canvas_w = tab_canvas.winfo_width()
            
            if total_w < canvas_w:
                # Center tabs if they fit, but add some deadzone to prevent jitter
                tab_canvas.itemconfig(tcw, anchor='n')
                tab_canvas.coords(tcw, canvas_w // 2, 0)
            else:
                # Align left for scrolling if they overflow
                tab_canvas.itemconfig(tcw, anchor='nw')
                tab_canvas.coords(tcw, 0, 0)
                
            tab_canvas.configure(scrollregion=tab_canvas.bbox('all'))
        except Exception: pass

    tab_bar.bind('<Configure>', _upd_tab_scroll)
    tab_canvas.bind('<Configure>', _upd_tab_scroll)

    def _on_tab_mousewheel(e):
        # Check if tabs actually overflow. If they fit, scroll the vertical content instead.
        try:
            total_w = tab_bar.winfo_width()
            canvas_w = tab_canvas.winfo_width()
            if total_w > canvas_w:
                tab_canvas.xview_scroll(int(-1 * (e.delta / 120)), 'units')
            else:
                # Redirect to active tab's vertical scroll
                for frame in tab_frames.values():
                    if frame.winfo_viewable():
                        # Find the canvas inside this frame
                        for child in frame.winfo_children():
                            if isinstance(child, tk.Canvas):
                                child.yview_scroll(int(-1 * (e.delta / 120)), 'units')
                                break
                        break
        except Exception: pass
    
    tab_canvas.bind('<MouseWheel>', _on_tab_mousewheel)
    tab_bar.bind('<MouseWheel>', _on_tab_mousewheel)
    indicator.bind('<MouseWheel>', _on_tab_mousewheel)

    tab_content = tk.Frame(win, bg=_BG)
    tab_content.pack(fill='both', expand=True)

    tab_frames: dict[str, tk.Frame] = {}
    tab_btns: dict[str, ctk.CTkButton] = {}
    built_tabs = set()

    def switch_tab(name: str):
        # Hide all, show selected
        for k, f in tab_frames.items():
            f.pack_forget()
            tab_btns[k].configure(
                fg_color='transparent',
                text_color=_DIM,
                border_width=0
            )
        
        # Lazy Loading
        if name not in built_tabs:
            _build_tab_content(name)
            built_tabs.add(name)

        tab_frames[name].pack(fill='both', expand=True)
        tab_btns[name].configure(
            fg_color='transparent', # Removed background tint
            text_color=_CYAN,
            border_width=0
        )
        
        # Animate/Move Indicator
        def _move_indicator():
            try:
                btn = tab_btns[name]
                win.update_idletasks()
                bx = btn.winfo_x()
                bw = btn.winfo_width()
                # Place indicator at the bottom of the active button, lower it to avoid overlap
                indicator.place(x=bx + 6, y=int(46 * hud.zoom_factor), width=bw - 12)
                indicator.lift()
            except Exception: pass
        
        win.after(10, _move_indicator)
        _ensure_active_visible(name)

    def _build_tab_content(name: str):
        import importlib
        try:
            inner = make_scrollable(tab_frames[name])
            
            if name == 'appearance':
                mod = importlib.import_module('ui.dialogs.settings_tabs.appearance')
                mod.build_appearance_tab(inner, win, hud, _save_hud_settings)
            elif name == 'voice':
                mod = importlib.import_module('ui.dialogs.settings_tabs.voice')
                mod.build_voice_tab(inner, win, hud, _save_hud_settings)
            elif name == 'modules':
                mod = importlib.import_module('ui.dialogs.settings_tabs.modules')
                mod.build_modules_tab(inner, win, hud, _save_hud_settings)
            elif name == 'dev':
                mod = importlib.import_module('ui.dialogs.settings_tabs.dev')
                mod.build_dev_tab(inner, win, hud, _save_hud_settings)
            elif name == 'tools':
                mod = importlib.import_module('ui.dialogs.settings_tabs.tools')
                mod.build_tools_tab(inner, win, hud, _save_hud_settings)
        except Exception as e:
            import traceback
            with open('logs/settings_err.log', 'a', encoding='utf-8') as f:
                f.write(f"[{time.ctime()}] Error building tab {name}: {e}\n{traceback.format_exc()}\n")
            tk.Label(tab_frames[name], text=f"Ошибка загрузки вкладки: {name}\n{e}", fg=_RED, bg=_BG).pack(expand=True)

    def make_scrollable(parent):
        scroll_canvas = tk.Canvas(parent, bg=_BG, highlightthickness=0, borderwidth=0)
        scroll_canvas.pack(side='left', fill='both', expand=True)
        
        inner = tk.Frame(scroll_canvas, bg=_BG)
        cw = scroll_canvas.create_window((0, 0), window=inner, anchor='nw')
        
        vsb = _HudScrollbar(parent, scroll_canvas, color=_CYAN)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        
        def _upd_scroll(*_):
            scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))
            
        def _on_cfg(e):
            scroll_canvas.itemconfig(cw, width=e.width)
            _upd_scroll()
            
        inner.bind('<Configure>', _upd_scroll)
        scroll_canvas.bind('<Configure>', _on_cfg)
        
        def _bind_mousewheel(w):
            try:
                cl = w.winfo_class()
                if cl in ('Listbox', 'Text'):
                    return
            except Exception:
                pass
            try:
                w.bind('<MouseWheel>', lambda e: scroll_canvas.yview_scroll(-1 * (e.delta // 120), 'units'), add='+')
            except (tk.TclError, NotImplementedError, AttributeError):
                pass
            for child in w.winfo_children():
                _bind_mousewheel(child)
                
        win.after(600, lambda: _bind_mousewheel(inner))
        return inner

    tab_meta = [
        ('appearance', '◈ ИНТЕРФЕЙС', _CYAN),
        ('voice', '🎙 ГОЛОС', _CYAN),
        ('modules', '🧩 МОДУЛИ', _CYAN),
        ('dev', '⬡ РАЗРАБОТКА', _CYAN),
        ('tools', '🛠 ИНСТРУМЕНТЫ', _CYAN)
    ]

    # Create Button Shells
    for i, (key, label, col) in enumerate(tab_meta):
        btn = ctk.CTkButton(
            tab_bar,
            text=label,
            command=lambda k=key: switch_tab(k),
            height=int(38 * hud.zoom_factor), # Reduced from 44
            font=(hud._F, _sf(9)), # Reduced from 10
            fg_color='transparent',
            text_color=_DIM,
            hover_color=_blend(_CYAN, 0.15),
            corner_radius=8,
            border_spacing=4
        )
        btn.pack(side='left', padx=1) # Reduced from 2
        btn.bind('<MouseWheel>', _on_tab_mousewheel) # Propagate scroll to canvas
        tab_btns[key] = btn
        tab_frames[key] = tk.Frame(tab_content, bg=_BG)
    
    def _ensure_active_visible(name):
        def _do():
            try:
                if not win.winfo_exists(): return
                btn = tab_btns[name]
                bx = btn.winfo_x()
                bw = btn.winfo_width()
                
                total_w = tab_bar.winfo_width()
                canvas_w = tab_canvas.winfo_width()
                if total_w <= 0 or canvas_w <= 0: return
                
                # If everything fits, don't scroll/move at all, let _upd_tab_scroll handle centering
                if total_w < canvas_w: 
                    return

                if bw >= canvas_w: 
                    tab_canvas.xview_moveto(bx / total_w)
                    return

                # Center the button
                target_x = bx - (canvas_w - bw) / 2
                tab_canvas.xview_moveto(max(0, target_x / total_w))
            except Exception: pass
        win.after(150, _do)

    # Initial tab
    switch_tab('appearance')
    _recenter()
