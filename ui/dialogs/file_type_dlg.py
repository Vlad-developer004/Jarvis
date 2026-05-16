from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import threading
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _BRD, _CYAN, _DIM, _PANEL, _TEXT, _WHITE
from ui.hud_utils import _blend, _set_dark_title_bar, _apply_window_icon
_FONT_UI = ("Segoe UI", 11)
_FONT_UI_SM = ("Segoe UI", 10)
_FONT_TITLE = ("Segoe UI Semibold", 12)
_FONT_HDR = ("Segoe UI Semibold", 13)
def _hud_root():
    try:
        import ui.hud as hud_mod
        hud = getattr(hud_mod, "_hud", None)
        r = getattr(hud, "root", None) if hud is not None else None
        if r is not None and hasattr(r, "winfo_exists"):
            return hud, r
    except Exception:
        pass
    return None, None
def _mount_picker(win: tk.Misc, out: list[str | None], master_wait: tk.Misc | None) -> None:
    from actions.office_documents import CREATE_BY_KIND, LIST_CREATE_KINDS_UI
    _rows: list[tuple[str, str]] = list(LIST_CREATE_KINDS_UI)
    _seen = {k for k, _ in _rows}
    for k in sorted(CREATE_BY_KIND.keys()):
        if k not in _seen:
            _rows.append((k, f".{k}"))
    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    ctk.set_appearance_mode("Light" if _theme == "light" else "Dark")
    
    hud, _ = _hud_root()
    _sf = lambda n: (hud._fs(n) if hud else n)
    _F = (hud._F if hud else "Segoe UI")

    _sw_scr = win.winfo_screenwidth()
    _sh_scr = win.winfo_screenheight()
    # Use underlying tk.Toplevel method to avoid CTK's empty string parsing crash
    tk.Toplevel.geometry(win, "")
    
    def _recenter():
        win.update_idletasks()
        from ui.hud_utils import _center_window
        rw, rh = win.winfo_reqwidth(), win.winfo_reqheight()
        _center_window(win, rw, rh)
    win.configure(bg=_BRD)
    _set_dark_title_bar(win)
    win.title(i18n.tr('file.type'))
    def _force_bounds(event=None):
        if not win.winfo_exists(): return
        if getattr(win, '_placing', True): return
        
        import ctypes
        is_dragging = ctypes.windll.user32.GetKeyState(0x01) < 0
        if is_dragging:
            if not getattr(win, '_snap_pending', False):
                win._snap_pending = True
                win.after(200, _force_bounds)
            return
            
        win._snap_pending = False
        from ui.hud_utils import _constrain_window
        wx, wy = win.winfo_x(), win.winfo_y()
        nx, ny = _constrain_window(win, wx, wy)
        if nx != wx or ny != wy:
            win.geometry(f"+{nx}+{ny}")
    win._placing = True
    win.after(1000, lambda: setattr(win, '_placing', False))
    win.bind('<Configure>', _force_bounds, add='+')
    win.attributes("-alpha", 1.0)
    win.drag_data = {"x": 0, "y": 0}
    def start_move(event):
        win.drag_data["x"] = event.x
        win.drag_data["y"] = event.y
    def on_move(event):
        deltax = event.x - win.drag_data["x"]
        deltay = event.y - win.drag_data["y"]
        x = win.winfo_x() + deltax
        y = win.winfo_y() + deltay
        win.geometry(f"+{x}+{y}")
    outer = tk.Frame(win, bg=_BRD, bd=0)
    outer.pack(fill="both", expand=True)
    inner = tk.Frame(outer, bg=_BG, bd=0)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    title_bar = tk.Frame(inner, bg=_PANEL, height=int(36 * (hud.zoom_factor if hud else 1.0)))
    title_bar.pack(fill="x")
    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", on_move)
    tk.Frame(inner, bg=_CYAN, height=1).pack(fill="x")
    tk.Label(title_bar, text="⬡", font=(_F, _sf(12), "bold"), fg=_CYAN, bg=_PANEL).pack(side="left", padx=(12, 6))
    tk.Label(title_bar, text=i18n.tr('file.type'), font=(_F, _sf(12), "bold"), fg=_TEXT, bg=_PANEL).pack(side="left")
    def _cancel():
        out[0] = None
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
    btn_close = tk.Label(title_bar, text="✕", font=("Segoe UI", 11), fg=_DIM, bg=_PANEL, cursor="hand2")
    btn_close.pack(side="right", padx=10)
    btn_close.bind("<Button-1>", lambda e: _cancel())
    content = tk.Frame(inner, bg=_BG)
    content.pack(fill="both", expand=True, padx=16, pady=(28, 14))
    tk.Label(
        content,
        text=i18n.tr('file.hint'),
        font=(_F, _sf(10)),
        fg=_DIM,
        bg=_BG,
        anchor="w",
    ).pack(fill="x", pady=(0, 8))
    filter_var = tk.StringVar()
    kinds_order: list[str] = [ext for ext, _ in _rows]
    labels_display: list[str] = [lbl for _, lbl in _rows]
    entry = ctk.CTkEntry(
        content,
        textvariable=filter_var,
        placeholder_text=i18n.tr('file.type_hint'),
        height=34,
        font=_FONT_UI,
        fg_color=_BG,
        border_color=_blend(_CYAN, 0.3),
        text_color=_TEXT,
        placeholder_text_color=_DIM,
    )
    entry.pack(fill="x", pady=(0, 8))
    body = tk.Frame(content, bg=_BG, highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
    body.pack(fill="both", expand=True)
    scroll = tk.Scrollbar(body, elementborderwidth=0, bg=_PANEL, troughcolor=_BG, width=12)
    scroll.pack(side="right", fill="y")
    lb = tk.Listbox(
        body,
        font=(_F, _sf(11)),
        fg=_TEXT,
        bg=_BG,
        selectbackground=_blend(_CYAN, 0.3),
        selectforeground=_TEXT,
        activestyle="none",
        borderwidth=0,
        highlightthickness=0,
        yscrollcommand=scroll.set,
    )
    lb.pack(side="left", fill="both", expand=True)
    scroll.config(command=lb.yview)
    def _rebuild_list(_evt=None):
        q = (filter_var.get() or "").strip().casefold()
        lb.delete(0, tk.END)
        for ext, lbl in _rows:
            blob = f"{ext} {lbl}".casefold()
            if not q or q in blob:
                lb.insert(tk.END, lbl)
        if lb.size():
            lb.selection_set(0)
            lb.activate(0)
    for lbl in labels_display:
        lb.insert(tk.END, lbl)
    lb.selection_set(0)
    lb.activate(0)
    filter_var.trace_add("write", lambda *a: _rebuild_list())
    def _confirm_sel():
        sel = lb.curselection()
        if not sel:
            return
        shown = lb.get(sel[0])
        for ext, lbl in _rows:
            if lbl == shown:
                out[0] = ext
                break
        else:
            return
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
    lb.bind("<Double-Button-1>", lambda e: _confirm_sel())
    lb.bind("<Return>", lambda e: _confirm_sel())
    lb.bind("<Escape>", lambda e: _cancel())
    btn_row = tk.Frame(content, bg=_BG)
    btn_row.pack(fill="x", pady=(12, 0))
    ctk.CTkButton(
        btn_row,
        text=i18n.tr('buttons.ok'),
        width=int(140 * (hud.zoom_factor if hud else 1.0)),
        height=int(36 * (hud.zoom_factor if hud else 1.0)),
        fg_color=_blend(_CYAN, 0.15),
        hover_color=_blend(_CYAN, 0.25),
        text_color=_CYAN,
        font=(_F, 11, "bold"),
        corner_radius=JStyle.RAD_BTN,
        command=_confirm_sel,
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        btn_row,
        text=i18n.tr('buttons.cancel'),
        width=int(120 * (hud.zoom_factor if hud else 1.0)),
        height=int(36 * (hud.zoom_factor if hud else 1.0)),
        fg_color="transparent",
        border_color=_DIM,
        border_width=1,
        text_color=_DIM,
        hover_color=_blend(_WHITE, 0.1),
        font=(_F, 11),
        corner_radius=JStyle.RAD_BTN,
        command=_cancel,
    ).pack(side="left")
    def _fade(a=0.0):
        if not win.winfo_exists():
            return
        a = min(a + 0.12, 0.97)
        win.attributes("-alpha", a)
        if a < 0.97:
            win.after(12, lambda: _fade(a))
    win.deiconify()
    win.lift()
    win.focus_force()
    entry.focus_set()
    _recenter()
    _fade()
    if master_wait is not None:
        master_wait.wait_window(win)
    else:
        win.mainloop()
def ask_file_kind() -> str | None:
    out: list[str | None] = [None]
    done = threading.Event()
    hud, master = _hud_root()
    if hud is not None and master is not None:
        def work():
            w = ctk.CTkToplevel(master)
            w.withdraw()
            _mount_picker(w, out, master)
            done.set()
        hud._hud_queue.put(work)
        done.wait(timeout=600.0)
        return out[0]
    root = ctk.CTk()
    root.withdraw()
    _mount_picker(root, out, None)
    return out[0]
