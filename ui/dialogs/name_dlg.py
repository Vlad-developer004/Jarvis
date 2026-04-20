from __future__ import annotations
import threading
import tkinter as tk
from collections.abc import Sequence
import customtkinter as ctk
from pathlib import Path
from ui.hud_constants import _AMBER, _BG, _BRD, _CYAN, _DIM, _PANEL, _SEP, _TEXT, _WHITE, _RED
from ui.hud_utils import _blend
from ui.hud_widgets import _HUDDropdown
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
    hud: any = None,
) -> None:
    _INPUT_BG = "#040508"
    _ACCENT = _CYAN
    width = 760
    F_HDR = ("Consolas", hud._fs(18), "bold")
    F_ENTRY = ("Consolas", hud._fs(22))
    F_EXT_ENTRY = ("Consolas", hud._fs(16))
    F_HINT = ("Segoe UI", hud._fs(11))
    F_TITLE = ("Consolas", hud._fs(11), "bold")
    height = 230 # Base height for header + name + footer
    if initial_path:
        height += 80 # Path field height
        if show_extension_field:
            height += 90 # Extension field height
    ctk.set_appearance_mode("Dark")
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    gw, gh = int(width * hud.zoom_factor), int(height * hud.zoom_factor)
    win.geometry(f"{gw}x{gh}+{(sw - gw) // 2}+{hud._px(60)}")
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
    main_frame = tk.Frame(win, bg=_BG, highlightbackground=_ACCENT, highlightthickness=1)
    main_frame.pack(fill="both", expand=True)
    
    title_bar = tk.Frame(main_frame, bg=_PANEL, height=44)
    title_bar.pack(fill="x")
    title_bar.bind("<Button-1>", start_move)
    title_bar.bind("<B1-Motion>", on_move)
    tk.Frame(main_frame, bg=_blend(_ACCENT, 0.4), height=2).pack(fill="x")
    tk.Label(
        title_bar, text="⬡", font=("Consolas", 16), fg=_ACCENT, bg=_PANEL
    ).pack(side="left", padx=(18, 10))
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
    btn_close.pack(side="right", padx=16)
    btn_close.bind("<Button-1>", lambda e: _cancel())
    btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=_RED))
    btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=_DIM))
    content = tk.Frame(main_frame, bg=_BG)
    content.pack(fill="x", padx=36, pady=(44, 12))
    
    # Sub-header wrapper for animated feel
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
    ).pack(fill="x", pady=(6, 20))
    entry_path = None
    if initial_path is not None:
        tk.Label(content, text="РАСПОЛОЖЕНИЕ:", font=("Consolas", 9, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x")
        path_frame = tk.Frame(content, bg=_BG)
        path_frame.pack(fill="x", pady=(2, 6))
        entry_path = ctk.CTkEntry(
            path_frame,
            height=48,
            font=("Consolas", hud._fs(12)),
            fg_color="#0d0f1e",
            border_color=_blend(_CYAN, 0.3),
            text_color=_CYAN,
            border_width=2,
            corner_radius=10,
        )
        entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_path.insert(0, initial_path)
        def _browse_native():
            from tkinter import filedialog
            selected = filedialog.askdirectory(initialdir=entry_path.get())
            if selected:
                entry_path.delete(0, tk.END)
                entry_path.insert(0, selected)
        ctk.CTkButton(
            path_frame, text="📁", width=48, height=52, fg_color="transparent",
            border_color=_BRD, border_width=1, text_color=_CYAN,
            hover_color="#1a2b3c", font=("Consolas", hud._fs(14)), corner_radius=4, command=_browse_native
        ).pack(side="right")
        nav_wrap = tk.Frame(content, bg=_BG)
        nav_wrap.pack(fill="x", pady=(0, 16))
        nav_scroll = tk.Frame(nav_wrap, bg=_BG)
        nav_scroll.pack() # Remove fill="x" to allow centering via anchor if needed, or just pack center
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
                btn.grid(row=r, column=c, padx=4, pady=4) # Removed sticky="w"
            rows_count = (len(nav_items) + MAX_COLS - 1) // MAX_COLS
            if rows_count > 1:
                try:
                    extra = (rows_count - 1) * int(42 * hud.zoom_factor)
                    old_geom = win.geometry().split('+')
                    coords_part = old_geom[1:] if len(old_geom) > 1 else ["0", "0"]
                    wh = old_geom[0].split('x')
                    new_h = int(wh[1]) + extra
                    win.geometry(f"{wh[0]}x{new_h}+{coords_part[0]}+{coords_part[1]}")
                except: pass
        _refresh_nav()
    entry = None
    entry_name = None
    combo_ext = None
    if initial_path and show_extension_field:
        from actions.programming_extensions import get_programming_extensions
        tk.Label(
            content,
            text="ИМЯ ФАЙЛА (БЕЗ РАСШИРЕНИЯ):",
            font=("Consolas", 12, "bold"),
            fg=_DIM,
            bg=_BG,
            anchor="w",
        ).pack(fill="x", pady=(4, 2))
        _name_ph = (placeholder or "").strip() or "например utils или readme"
        entry_name = ctk.CTkEntry(
            content,
            height=52,
            font=("Consolas", hud._fs(16)),
            fg_color="#0d0f1e",
            border_color=_blend(_CYAN, 0.3),
            text_color=_WHITE,
            placeholder_text=_name_ph,
            placeholder_text_color=_blend(_WHITE, 0.25),
            border_width=2,
            corner_radius=12,
        )
        entry_name.pack(fill="x", pady=(0, 12))
        tk.Label(
            content,
            text="ТИП / РАСШИРЕНИЕ (НАПР. VUE, RS):",
            font=("Consolas", 12, "bold"),
            fg=_DIM,
            bg=_BG,
            anchor="w",
        ).pack(fill="x", pady=(0, 2))
        # --- Restricted System Extension Catalog ---
        # 4 basics requested by user + user current settings
        _CORE_DESC = {
            "docx": "Word Документ  (.docx)",
            "xlsx": "Excel Таблица  (.xlsx)",
            "pptx": "PowerPoint Презентация  (.pptx)",
            "txt":  "Текстовый файл  (.txt)",
            "tsx":  "TypeScript JSX  (.tsx)",
            "ts":   "TypeScript файл  (.ts)",
            "py":   "Python Скрипт  (.py)",
            "js":   "JavaScript Файл  (.js)",
            "html": "Веб-страница  (.html)",
            "md":   "Markdown Документ  (.md)"
        }
        
        vals: list[str] = []
        # 1. Add ONLY the 4 requested basics
        for ext in ["docx", "xlsx", "pptx", "txt"]:
            vals.append(_CORE_DESC[ext])
            
        # 2. Add user-defined extensions from settings with labels if known
        for pe in get_programming_extensions():
            pe = pe.lstrip(".")
            if pe in ["docx", "xlsx", "pptx", "txt"]: continue # Already added
            
            if pe in _CORE_DESC:
                vals.append(_CORE_DESC[pe])
            else:
                vals.append(f"Файл .{pe}  (.{pe})")

        # Set initial value
        ext0 = (default_extension or "txt").strip().lower().lstrip(".") or "txt"
        initial_val = _CORE_DESC.get(ext0, f"Файл .{ext0}  (.{ext0})")
        
        ext_var = tk.StringVar(value=initial_val)
        combo_ext = _HUDDropdown(hud, content, vals, ext_var, accent=_CYAN)
        combo_ext.frame.pack(fill="x", pady=(0, 24))
        
        entry_name.focus_set()
    else:
        if initial_path:
            tk.Label(
                content,
                text="ИМЯ ПАПКИ:",
                font=("Consolas", 12, "bold"),
                fg=_DIM,
                bg=_BG,
                anchor="w",
            ).pack(fill="x", pady=(4, 2))
        _single_ph = (placeholder or "").strip() or "Введите здесь..."
        entry = ctk.CTkEntry(
            content,
            height=60,
            font=("Consolas", hud._fs(22)),
            fg_color=_INPUT_BG,
            border_color=_blend(_CYAN, 0.5),
            text_color=_WHITE,
            placeholder_text=_single_ph,
            placeholder_text_color=_blend(_WHITE, 0.2),
            border_width=2,
            corner_radius=6,
        )
        entry.pack(fill="x", pady=(4, 30))
        entry.focus_set()
    
    # Bottom Button Row layout styling
    btn_wrap = tk.Frame(content, bg=_BG)
    btn_wrap.pack(fill="x", pady=(0, 15)) # Further reduced bottom space
    
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor="center")
    def _confirm():
        nonlocal result
        if initial_path is not None and show_extension_field and entry_name is not None and combo_ext is not None:
            stem = entry_name.get().strip()
            if not stem:
                return
            raw_ext = ext_var.get().strip().lower()
            # Extract extension from "Name  (.ext)" format
            if " (." in raw_ext:
                ext = raw_ext.split(" (.")[-1].split(")")[0]
            elif ". " in raw_ext: # Fallback for "Word  .docx"
                ext = raw_ext.split(". ")[-1]
            elif "." in raw_ext:
                ext = raw_ext.split(".")[-1]
            else:
                ext = raw_ext
            
            # Final safety check for common Russian phonetic typos in extensions
            ext = ext.replace("р", "p").replace("у", "y").replace("к", "k").replace("с", "c").replace("х", "x").replace("а", "a").replace("о", "o")
            
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
        btn_inner,
        text=f"{ok_text.upper()}  ✦",
        width=240,
        height=54,
        fg_color=_blend(_CYAN, 0.15),
        border_color=_CYAN,
        border_width=2,
        text_color=_WHITE,
        hover_color=_blend(_CYAN, 0.4),
        font=("Consolas", hud._fs(12), "bold"),
        corner_radius=15,
        command=_confirm
    )
    btn_ok.pack(side="left", padx=15) 
    btn_cnc = ctk.CTkButton(
        btn_inner,
        text=f"{cancel_text.upper()}  ✕",
        width=240,
        height=54,
        fg_color="transparent",
        border_color="#3a415a",
        border_width=2,
        text_color=_DIM,
        hover_color=_blend(_WHITE, 0.1),
        font=("Consolas", hud._fs(12), "bold"),
        corner_radius=15,
        command=_cancel
    )
    btn_cnc.pack(side="left", padx=15)
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
        _install_modal_content(win, out, hud=hud, **kwargs)
        try: master.wait_window(win)
        finally: done.set()
    hud._hud_queue.put(work)
    done.wait(timeout=600.0)
    return out[0]
def _ask_standalone(**kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out: list[str | tuple[str, str] | None] = [None]
    root = ctk.CTk()
    root.withdraw()
    _install_modal_content(root, out, hud=None, **kwargs)
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
