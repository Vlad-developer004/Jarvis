from __future__ import annotations
import threading
import tkinter as tk
from collections.abc import Sequence
import customtkinter as ctk
from pathlib import Path
from ui.hud_constants import _AMBER, _BG, _BRD, _CYAN, _DIM, _PANEL, _SEP, _TEXT, _WHITE
_DEFAULT_HINT = "Голосом: «создай» / «отмена»  ·  Enter / Esc"
_VOICE_DOC_CONFIRM: tuple[str, ...] = (
    "создай", "создать", "створи", "create", "сделай", "подтверди", "готово", "отправь", "да", "окей", "okay", "ok"
)
_VOICE_DOC_CANCEL: tuple[str, ...] = (
    "отмена", "отменить", "нет", "закрой", "закрыть", "cancel", "хватит", "стоп"
)
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
def _install_modal_content(
    win: tk.Misc,
    result: list,
    *,
    title: str,
    header: str,
    ok_text: str,
    cancel_text: str,
    placeholder: str,
    height: int,
    hint_voice: str,
    voice_confirm: Sequence[str],
    voice_cancel: Sequence[str],
    require_message_to_confirm: bool,
    initial_path: str | None = None,
    show_extension_field: bool = False,
    default_extension: str | None = None,
) -> None:
    _INPUT_BG = "#0a0b14"
    _ACCENT = _CYAN
    width = 720
    F_HDR = ("Consolas", 15, "bold")
    F_ENTRY = ("Consolas", 18)
    F_HINT = ("Consolas", 11)
    F_BTN = ("Consolas", 12, "bold")
    F_TITLE = ("Consolas", 10, "bold")
    if initial_path:
        height += 130
        if show_extension_field:
            height += 140
    ctk.set_appearance_mode("Dark")
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{width}x{height}+{(sw - width) // 2}+{(sh - height) // 2}")
    if isinstance(win, tk.Toplevel) or isinstance(win, tk.Tk):
        win.overrideredirect(True)
    win.configure(bg=_BG)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.0)
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
    outer.place(x=0, y=0, width=width, height=height)
    inner = tk.Frame(outer, bg=_BG, bd=0)
    inner.place(x=1, y=1, width=width - 2, height=height - 2)
    title_bar = tk.Frame(inner, bg=_PANEL, height=38)
    title_bar.pack(fill="x")
    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", on_move)
    tk.Frame(inner, bg=_ACCENT, height=2).pack(fill="x")
    tk.Label(
        title_bar, text="⬡", font=("Consolas", 15), fg=_ACCENT, bg=_PANEL
    ).pack(side="left", padx=(14, 6))
    tk.Label(
        title_bar, text=title.upper(), font=F_TITLE, fg=_TEXT, bg=_PANEL
    ).pack(side="left")
    def _cancel():
        try: win.grab_release()
        except: pass
        win.destroy()
    btn_close = tk.Label(
        title_bar, text="✕", font=("Consolas", 14), fg=_DIM, bg=_PANEL, cursor="hand2"
    )
    btn_close.pack(side="right", padx=12)
    btn_close.bind("<Button-1>", lambda e: _cancel())
    btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=_WHITE))
    btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=_DIM))
    content = tk.Frame(inner, bg=_BG)
    content.pack(fill="both", expand=True, padx=28, pady=(22, 0))
    tk.Label(
        content,
        text=header.upper(),
        font=F_HDR,
        fg=_ACCENT,
        bg=_BG,
        anchor="w",
    ).pack(fill="x")
    tk.Label(
        content,
        text=hint_voice,
        font=F_HINT,
        fg=_DIM,
        bg=_BG,
        anchor="w",
    ).pack(fill="x", pady=(4, 12))
    entry_path = None
    if initial_path is not None:
        tk.Label(content, text="РАСПОЛОЖЕНИЕ:", font=("Consolas", 9, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x")
        path_frame = tk.Frame(content, bg=_BG)
        path_frame.pack(fill="x", pady=(2, 6))
        entry_path = ctk.CTkEntry(
            path_frame,
            height=40,
            font=("Consolas", 14),
            fg_color=_INPUT_BG,
            border_color=_BRD,
            text_color=_CYAN,
            border_width=1,
            corner_radius=4,
        )
        entry_path.pack(side="left", fill="x", expand=True, padx=(0, 6))
        entry_path.insert(0, initial_path)
        def _browse_native():
            from tkinter import filedialog
            selected = filedialog.askdirectory(initialdir=entry_path.get())
            if selected:
                entry_path.delete(0, tk.END)
                entry_path.insert(0, selected)
        ctk.CTkButton(
            path_frame, text="📁", width=46, height=44, fg_color="transparent",
            border_color=_BRD, border_width=1, text_color=_CYAN,
            hover_color="#1a2b3c", font=("Consolas", 14), corner_radius=4, command=_browse_native
        ).pack(side="right")
        nav_wrap = tk.Frame(content, bg=_BG)
        nav_wrap.pack(fill="x", pady=(0, 16))
        nav_scroll = tk.Frame(nav_wrap, bg=_BG)
        nav_scroll.pack(fill="x")
        def _nav_to(p: str):
            entry_path.delete(0, tk.END)
            entry_path.insert(0, str(Path(p).resolve()))
            _refresh_nav()
        def _refresh_nav():
            for w in nav_scroll.winfo_children():
                w.destroy()
            p_str = entry_path.get().strip()
            try:
                curr = Path(p_str).resolve()
            except:
                return
            _btn_kw = dict(height=34, fg_color="#1a1c2e", text_color=_TEXT,
                           hover_color="#2a2d45", font=("Consolas", 11), corner_radius=12)
            nav_items: list[tuple[str, str | Path]] = []
            nav_items.append(("[ .. ]", curr.parent))
            home = Path.home()
            for name, path in [("DESKTOP", home / "Desktop"), ("DOCS", home / "Documents")]:
                if path.exists():
                    nav_items.append((name, path))
            try:
                subs = sorted([d for d in curr.iterdir() if d.is_dir() and not d.name.startswith('.')], key=lambda x: x.name.lower())
                for d in subs[:10]:
                    nav_items.append((f"📂 {d.name}", d))
            except:
                pass
            MAX_COLS = 5
            for i, (label, target) in enumerate(nav_items):
                r, c = divmod(i, MAX_COLS)
                btn = ctk.CTkButton(
                    nav_scroll, text=label, width=120,
                    command=lambda pt=target: _nav_to(str(pt)), **_btn_kw
                )
                btn.grid(row=r, column=c, padx=4, pady=4, sticky="w")
            rows_count = (len(nav_items) + MAX_COLS - 1) // MAX_COLS
            if rows_count > 1:
                try:
                    extra = (rows_count - 1) * 42
                    old_geom = win.geometry().split('+')
                    wh = old_geom[0].split('x')
                    new_h = int(wh[1]) + extra
                except: pass
        _refresh_nav()
    entry = None
    entry_name = None
    combo_ext = None
    if initial_path and show_extension_field:
        from actions.programming_extensions import get_programming_extensions
        tk.Label(
            content,
            text="ИМЯ ФАЙЛА (без расширения):",
            font=("Consolas", 11, "bold"),
            fg=_DIM,
            bg=_BG,
            anchor="w",
        ).pack(fill="x", pady=(4, 2))
        _name_ph = (placeholder or "").strip() or "например utils или readme"
        entry_name = ctk.CTkEntry(
            content,
            height=48,
            font=F_ENTRY,
            fg_color=_INPUT_BG,
            border_color=_BRD,
            text_color=_AMBER,
            placeholder_text=_name_ph,
            placeholder_text_color=_DIM,
            border_width=1,
            corner_radius=4,
        )
        entry_name.pack(fill="x", pady=(0, 10))
        tk.Label(
            content,
            text="ТИП / РАСШИРЕНИЕ (выберите или введите, напр. vue, rs):",
            font=("Consolas", 11, "bold"),
            fg=_DIM,
            bg=_BG,
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        vals = list(get_programming_extensions())
        ext0 = (default_extension or "txt").strip().lower().lstrip(".") or "txt"
        if ext0 not in vals:
            vals.append(ext0)
        combo_ext = ctk.CTkComboBox(
            content,
            values=vals,
            height=48,
            font=F_ENTRY,
            dropdown_font=F_ENTRY,
            fg_color=_INPUT_BG,
            border_color=_BRD,
            text_color=_TEXT,
            border_width=1,
            corner_radius=4,
            button_color="#1e2540",
            button_hover_color="#2a3358",
            dropdown_fg_color=_PANEL,
            dropdown_text_color=_TEXT,
            dropdown_hover_color="#1a2060",
            state="normal",
        )
        combo_ext.pack(fill="x", pady=(0, 20))
        combo_ext.set(ext0 if ext0 in vals else vals[0])
        entry_name.focus_set()
    else:
        if initial_path:
            tk.Label(
                content,
                text="ИМЯ ПАПКИ:",
                font=("Segoe UI", 10, "bold"),
                fg=_DIM,
                bg=_BG,
                anchor="w",
            ).pack(fill="x", pady=(4, 2))
        _single_ph = (placeholder or "").strip() or "Введите здесь..."
        entry = ctk.CTkEntry(
            content,
            height=52,
            font=F_ENTRY,
            fg_color=_INPUT_BG,
            border_color=_BRD,
            text_color=_AMBER,
            placeholder_text=_single_ph,
            placeholder_text_color=_DIM,
            border_width=1,
            corner_radius=4,
        )
        entry.pack(fill="x", pady=(4, 24))
        entry.focus_set()
    btn_row = tk.Frame(content, bg=_BG)
    btn_row.pack(fill="x", pady=(0, 24))
    def _confirm():
        nonlocal result
        if initial_path is not None and show_extension_field and entry_name is not None and combo_ext is not None:
            stem = entry_name.get().strip()
            if not stem:
                return
            ext = combo_ext.get().strip().lower().lstrip(".")
            result[0] = (entry_path.get().strip(), stem, ext)
            _cancel()
            return
        msg = entry.get().strip() if entry is not None else ""
        if require_message_to_confirm and not msg:
            return
        if initial_path is not None:
            result[0] = (entry_path.get().strip(), msg)
        else:
            result[0] = msg
        if not require_message_to_confirm or msg:
            _cancel()
    btn_ok = ctk.CTkButton(
        btn_row,
        text=ok_text.upper(),
        width=160,
        height=42,
        fg_color="transparent",
        border_color=_ACCENT,
        border_width=1,
        text_color=_ACCENT,
        hover_color="#1a2b3c",
        font=F_BTN,
        corner_radius=4,
        command=_confirm
    )
    btn_ok.pack(side="left", padx=(0, 14))
    btn_cnc = ctk.CTkButton(
        btn_row,
        text=cancel_text.upper(),
        width=160,
        height=42,
        fg_color="transparent",
        border_color=_DIM,
        border_width=1,
        text_color=_DIM,
        hover_color="#1a1c25",
        font=F_BTN,
        corner_radius=4,
        command=_cancel
    )
    btn_cnc.pack(side="left")
    def _destroy_voice(event):
        if event.widget is win:
            try:
                from ui.voice_prompt_bridge import unregister_voice_prompt
                unregister_voice_prompt(win)
            except: pass
    win.bind("<Destroy>", _destroy_voice)
    try:
        from ui.voice_prompt_bridge import register_voice_prompt
        register_voice_prompt(
            win,
            on_confirm=_confirm,
            on_cancel=_cancel,
            confirm_phrases=tuple(voice_confirm),
            cancel_phrases=tuple(voice_cancel),
        )
    except: pass
    if entry is not None:
        entry.bind("<Return>", lambda e: _confirm())
        entry.bind("<Escape>", lambda e: _cancel())
    if entry_name is not None:
        entry_name.bind("<Return>", lambda e: _confirm())
        entry_name.bind("<Escape>", lambda e: _cancel())
    if combo_ext is not None:
        _ce = getattr(combo_ext, "_entry", None)
        if _ce is not None:
            _ce.bind("<Return>", lambda e: _confirm())
            _ce.bind("<Escape>", lambda e: _cancel())
    def _fade(alpha=0.0):
        if not win.winfo_exists(): return
        alpha = min(alpha + 0.1, 0.98)
        win.attributes("-alpha", alpha)
        if alpha < 0.98:
            win.after(10, lambda: _fade(alpha))
    win.deiconify()
    win.lift()
    win.focus_force()
    _fade()
def _ask_via_hud(hud, master: tk.Misc, **kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out: list[str | tuple[str, str] | None] = [None]
    done = threading.Event()
    def work():
        win = ctk.CTkToplevel(master)
        win.withdraw()
        _install_modal_content(win, out, **kwargs)
        try: master.wait_window(win)
        finally: done.set()
    hud._hud_queue.put(work)
    done.wait(timeout=600.0)
    return out[0]
def _ask_standalone(**kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out: list[str | tuple[str, str] | None] = [None]
    root = ctk.CTk()
    root.withdraw()
    _install_modal_content(root, out, **kwargs)
    root.mainloop()
    return out[0]
def ask_text(
    *,
    title: str,
    header: str,
    ok_text: str = "ОК",
    cancel_text: str = "ОТМЕНА",
    placeholder: str = "",
    width: int = 640,
    height: int = 300,
    hint_voice: str = _DEFAULT_HINT,
    voice_confirm_phrases: Sequence[str] | None = None,
    voice_cancel_phrases: Sequence[str] | None = None,
    require_message_to_confirm: bool = False,
    initial_path: str | None = None,
    show_extension_field: bool = False,
    default_extension: str | None = None,
) -> str | tuple[str, str] | tuple[str, str, str] | None:
    vc = tuple(voice_confirm_phrases) if voice_confirm_phrases is not None else _VOICE_DOC_CONFIRM
    vz = tuple(voice_cancel_phrases) if voice_cancel_phrases is not None else _VOICE_DOC_CANCEL
    hud, master = _hud_root()
    if hud is not None and master is not None:
        try:
            return _ask_via_hud(
                hud, master,
                title=title, header=header, ok_text=ok_text, cancel_text=cancel_text,
                placeholder=placeholder, height=height, hint_voice=hint_voice,
                voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm,
                initial_path=initial_path,
                show_extension_field=show_extension_field,
                default_extension=default_extension,
            )
        except: pass
    return _ask_standalone(
        title=title, header=header, ok_text=ok_text, cancel_text=cancel_text,
        placeholder=placeholder, height=height, hint_voice=hint_voice,
        voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm,
        initial_path=initial_path,
        show_extension_field=show_extension_field,
        default_extension=default_extension,
    )
