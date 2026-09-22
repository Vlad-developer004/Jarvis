"""Visual security alert for features/guard.py — a HUD popup with the
captured intruder photo, replacing "beep and hope you're at your desk" as
the only signal. The audio cue (red_alert sound + spoken line) stays; this
adds the visual half so the alert is visible if you weren't listening.
"""
from __future__ import annotations
import os
import tkinter as tk
import customtkinter as ctk
from core import i18n
from ui.hud_style import JStyle
from ui.hud_constants import _BG, _PANEL, _RED, _DIM
from ui.hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _center_window


def show_guard_alert(hud, image_path: str | None) -> None:
    """Must run on the Tk UI thread — schedule via hud._hud_queue.put(...)."""
    if not hud or not hud.root or not hud.root.winfo_exists():
        return
    win = tk.Toplevel(hud.root)
    win.title(i18n.tr('guard.alert_title'))
    win.configure(bg=_BG)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)
    win.attributes('-topmost', True)
    win.resizable(False, False)

    tk.Frame(win, bg=_RED, height=2).pack(fill='x')
    tk.Label(
        win, text=i18n.tr('guard.alert_title'), bg=_BG, fg=_RED,
        font=('Consolas', JStyle.TEXT_BODY, 'bold'),
    ).pack(pady=(18, 6), padx=28)

    photo_w, photo_h = 320, 240
    img_box = tk.Frame(win, bg=_PANEL, width=photo_w, height=photo_h,
                        highlightbackground=_blend(_RED, 0.4), highlightthickness=1)
    img_box.pack(padx=28, pady=(0, 12))
    img_box.pack_propagate(False)
    img_lbl = tk.Label(img_box, bg=_PANEL, text='···', fg=_DIM, font=('Consolas', JStyle.TEXT_BODY))
    img_lbl.pack(fill='both', expand=True)

    if image_path and os.path.exists(image_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(image_path)
            img.thumbnail((photo_w - 4, photo_h - 4), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            img_lbl.configure(image=photo, text='')
            img_lbl.image = photo  # keep alive — see ui/dialogs/yt_picker_dlg.py's _apply()
        except Exception:
            pass

    tk.Label(
        win, text=i18n.tr('guard.alert_hint'),
        bg=_BG, fg=_DIM, font=('Consolas', JStyle.TEXT_TINY),
    ).pack(pady=(0, 16))

    ctk.CTkButton(
        win, text=i18n.tr('guard.alert_dismiss'), command=win.destroy,
        height=JStyle.H_LARGE, font=('Consolas', 13, 'bold'),
        fg_color=_blend(_RED, 0.18), hover_color=_blend(_RED, 0.28),
        text_color=_RED, border_color=_blend(_RED, 0.65),
        border_width=2, corner_radius=JStyle.RAD_PANEL,
    ).pack(pady=(0, 18))

    win.update_idletasks()
    _center_window(win, win.winfo_reqwidth(), win.winfo_reqheight())
