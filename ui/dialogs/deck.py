from __future__ import annotations
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from typing import Optional
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar
from ..hud_widgets import _HudScrollbar
from ..hud_commands import _COMMANDS
from core.extensions import ExtensionManager
def open_deck(hud, reopen: bool = False) -> None:
    if not reopen and hud._deck_win and hud._deck_win.winfo_exists():
        hud._deck_win.lift()
        return
    if reopen and hud._deck_win and hud._deck_win.winfo_exists():
        hud._deck_win.destroy()
    win = tk.Toplevel(hud.root)
    hud._deck_win = win
    hud._track_subwin('deck', win, lambda: open_deck(hud, reopen=True))
    win.title('COMMAND INDEX — J.A.R.V.I.S.')
    win.configure(bg=_BG)
    _sw = hud.root.winfo_screenwidth()
    _sh = hud.root.winfo_screenheight()
    _dw = int(min(1100, _sw * 0.85 / hud.zoom_factor) * hud.zoom_factor)
    _dh = int(min(780, _sh * 0.85 / hud.zoom_factor) * hud.zoom_factor)
    _dx = max(0, (_sw - _dw) // 2)
    _dy = max(0, (_sh - _dh) // 2)
    win.geometry(f'{_dw}x{_dh}+{_dx}+{_dy}')
    win.attributes('-alpha', 0.98)
    win.minsize(380, 400)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _f11 = hud._fs(11)
    _f12 = hud._fs(12)
    _f9 = hud._fs(9)
    _f10 = hud._fs(10)
    _f13 = hud._fs(13)
    _f14 = hud._fs(14)
    _f16 = hud._fs(16)
    tk.Frame(win, bg=_MAG, height=2).pack(fill='x')
    tk.Label(win, text='БАЗА КОМАНД', bg=_BG, fg=_MAG, font=(hud._F, _f16, 'bold')).pack(pady=(14, 2))
    tk.Label(win, text='Голосовые фразы-триггеры для J.A.R.V.I.S.', bg=_BG, fg=_TEXT, font=(hud._F, _f11)).pack()
    tk.Frame(win, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(8, 4))
    search_f = tk.Frame(win, bg=_BG)
    search_f.pack(fill='x', padx=20, pady=(0, 6))
    tk.Label(search_f, text='⌕', bg=_BG, fg=_CYAN, font=(hud._F, _f14, 'bold')).pack(side='left', padx=(0, 6))
    _search_var = tk.StringVar()
    search_entry = ctk.CTkEntry(search_f, textvariable=_search_var, placeholder_text='Поиск команды...', font=(hud._F, _f11), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=0, height=30)
    search_entry.pack(side='left', fill='x', expand=True)
    tk.Frame(win, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(0, 4))
    scroll_outer = tk.Frame(win, bg=_BG)
    scroll_outer.pack(fill='both', expand=True, padx=10, pady=4)
    canvas = tk.Canvas(scroll_outer, bg=_BG, highlightthickness=0, yscrollincrement=1)
    canvas.pack(side='left', fill='both', expand=True)
    _sb = _HudScrollbar(scroll_outer, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=_sb.set)
    def _on_wheel(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(int(-e.delta / 4), 'units')
    inner = tk.Frame(canvas, bg=_BG)
    _inner_id = canvas.create_window(0, 0, anchor='nw', window=inner)
    def _update_scroll(*_):
        canvas.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()))
    def _on_canvas_resize(e):
        if not canvas.winfo_exists(): return
        canvas.itemconfigure(_inner_id, width=e.width)
        _update_scroll()
        new_cols = _cols_for_width(e.width)
        if new_cols != _last_cols[0]:
            if _resize_after[0]:
                win.after_cancel(_resize_after[0])
            _resize_after[0] = win.after(100, lambda: _build_cards(_search_var.get()))
    inner.bind('<Configure>', _update_scroll)
    canvas.bind('<Configure>', _on_canvas_resize)
    win.bind('<MouseWheel>', _on_wheel)
    _ext_d = ExtensionManager()
    _commands: dict = dict(_COMMANDS)
    _all_items: list[tuple[str, str, str, str]] = [(cat, name, phrase, desc) for cat, items in _commands.items() for name, phrase, desc in items]
    def _cols_for_width(w: int) -> int:
        if w >= int(1150 * hud.zoom_factor):
            return 3
        if w >= int(750 * hud.zoom_factor):
            return 2
        return 1
    def _make_card(parent, name: str, phrase: str, desc: str, cat: str = '', wrap_w: int = 300) -> tk.Frame:
        card = tk.Frame(parent, bg=_PANEL, highlightbackground=_BRD, highlightthickness=1)
        card.grid_columnconfigure(0, weight=1)
        tk.Label(card, text=name, bg=_PANEL, fg=_WHITE, font=(hud._F, _f13, 'bold'), anchor='w', wraplength=wrap_w, justify='left').grid(row=0, column=0, sticky='ew', padx=10, pady=(10, 2))
        tk.Label(card, text=phrase, bg=_PANEL, fg=_CYAN, font=(hud._F, _f12, 'bold'), anchor='w', wraplength=wrap_w, justify='left').grid(row=1, column=0, sticky='ew', padx=10)
        _desc_text = f'{desc}  ·  {cat}' if cat else desc
        tk.Label(card, text=_desc_text, bg=_PANEL, fg=_TEXT, font=(hud._F, _f10), anchor='w', wraplength=wrap_w, justify='left').grid(row=2, column=0, sticky='ew', padx=10, pady=(2, 10))
        return card
    _last_cols = [0]
    _resize_after = [None]
    def _build_cards(query: str = '') -> None:
        for w in inner.winfo_children():
            w.destroy()
        canvas.yview_moveto(0)
        q = query.strip().lower()
        cols = _cols_for_width(canvas.winfo_width() or _dw)
        _last_cols[0] = cols
        def _grid_section(items_with_cat) -> None:
            col_idx = 0
            cur_row_f: Optional[tk.Frame] = None
            cw = canvas.winfo_width() or _dw
            card_wrap = (cw // cols) - 40
            for name, phrase, desc, cat in items_with_cat:
                if col_idx == 0:
                    cur_row_f = tk.Frame(inner, bg=_BG)
                    cur_row_f.pack(fill='x', pady=2)
                    for ci in range(cols):
                        cur_row_f.grid_columnconfigure(ci, weight=1)
                card = _make_card(cur_row_f, name, phrase, desc, cat, wrap_w=card_wrap)
                card.grid(row=0, column=col_idx, sticky='nsew', padx=3)
                col_idx = (col_idx + 1) % cols
        if q:
            matched = [(cat, name, phrase, desc) for cat, name, phrase, desc in _all_items if q in name.lower() or q in phrase.lower() or q in desc.lower()]
            if not matched:
                tk.Label(inner, text='КОМАНДЫ НЕ НАЙДЕНЫ', bg=_BG, fg=_RED, font=(hud._F, _f12, 'bold')).pack(pady=40)
            else:
                _grid_section(matched)
        else:
            for cat, items in _commands.items():
                tk.Label(inner, text=cat, bg=_BG, fg=_MAG, font=(hud._F, _f10, 'bold'), anchor='w').pack(fill='x', padx=10, pady=(20, 5))
                tk.Frame(inner, bg=_MAG, height=1).pack(fill='x', padx=10, pady=(0, 10))
                _grid_section([(cat, name, phrase, desc) for name, phrase, desc in items])
    _build_cards()
    _search_var.trace_add('write', lambda *_: _build_cards(_search_var.get()))
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='bottom')
