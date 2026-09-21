"""Small tkinter helpers shared by the mail compose and mail client dialogs.
Split out of the old mail_dlg.py purely for file size; no behavior change.
"""
from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _CYAN, _RED, _WHITE
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _place_dialog

def _show_confirm_hud(hud, parent, title, text, ok_cb, danger=True):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=_BG)  # type: ignore[call-arg]
    dlg.transient(parent)
    dlg.grab_set()
    _set_dark_title_bar(dlg)
    _apply_window_icon(dlg, hud)
    _place_dialog(dlg, hud, 540, 180, grab=False)
    dlg.resizable(False, False)
    tk.Frame(dlg, bg=_RED if danger else _CYAN, height=2).pack(fill='x', side='top')
    body = tk.Frame(dlg, bg=_BG)
    body.pack(fill='both', expand=True, padx=24, pady=20)
    tk.Label(
        body, text=text, bg=_BG, fg=_WHITE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        wraplength=540 - 50, justify='center'
    ).pack(pady=(0, 16))
    btn_row = tk.Frame(body, bg=_BG)
    btn_row.pack(anchor='center')
    def _ok():
        dlg.destroy()
        ok_cb()
    ctk.CTkButton(
        btn_row, text='ПОДТВЕРДИТЬ', width=160, height=JStyle.H_NORM,
        font=(hud._F, _sf(10), 'bold'),
        fg_color=_blend(_RED if danger else _CYAN, 0.25),
        hover_color=_blend(_RED if danger else _CYAN, 0.45),
        text_color=_RED if danger else _CYAN,
        command=_ok
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        btn_row, text=i18n.tr('buttons.cancel'), width=120, height=JStyle.H_NORM,
        font=(hud._F, _sf(10), 'bold'),
        fg_color=_blend(_WHITE, 0.08),
        command=dlg.destroy
    ).pack(side='left', padx=10)
def _sf(n, zoom=1.0):
    # Cap the scaling curve for extremely high zoom levels to prevent layout explosion
    effective_zoom = zoom if zoom <= 1.8 else 1.8 + (zoom - 1.8) * 0.4
    return max(8, int((n + 6) * effective_zoom))
def _bind_text_clipboard(win: tk.Toplevel, txt) -> None:
    inner = getattr(txt, '_textbox', txt)
    def _paste(_evt=None):
        try:
            t = win.clipboard_get()
        except Exception:
            return 'break'
        try:
            inner.insert('insert', t)
        except Exception:
            return 'break'
        return 'break'
    def _copy(_evt=None):
        try:
            sel = inner.get('sel.first', 'sel.last')
        except Exception:
            return 'break'
        try:
            win.clipboard_clear()
            win.clipboard_append(sel)
        except Exception:
            pass
        return 'break'
    def _cut(_evt=None):
        _copy()
        try:
            inner.delete('sel.first', 'sel.last')
        except Exception:
            pass
        return 'break'
    inner.bind('<Control-v>', _paste)
    inner.bind('<Control-V>', _paste)
    inner.bind('<Control-c>', _copy)
    inner.bind('<Control-C>', _copy)
    inner.bind('<Control-x>', _cut)
    inner.bind('<Control-X>', _cut)
