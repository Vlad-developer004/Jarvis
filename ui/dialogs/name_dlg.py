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
    initial_value: str | None = None,
) -> None:
    _INPUT_BG = _BG
    _ACCENT = _CYAN
    width = 680
    F_HDR = ("Consolas", hud._fs(18), "bold")
    F_ENTRY = ("Consolas", hud._fs(22))
    F_EXT_ENTRY = ("Consolas", hud._fs(16))
    F_HINT = ("Segoe UI", hud._fs(11))
    F_TITLE = ("Consolas", hud._fs(11), "bold")
    
    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    ctk.set_appearance_mode("Light" if _theme == "light" else "Dark")
    sw = win.winfo_screenwidth()
    
    # Start with empty geometry to allow auto-layout calculation
    # Use underlying tk.Toplevel method to avoid CTK's empty string parsing crash
    tk.Toplevel.geometry(win, "")
    
    if isinstance(win, tk.Toplevel) or isinstance(win, tk.Tk):
        win.overrideredirect(True)
    win.configure(bg=_BG)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 0.0)
    win.drag_data = {"x": 0, "y": 0}

    def _recenter():
        win.update_idletasks()
        # Account for CustomTkinter's window scaling to prevent double-zoom gaps
        zf = hud.zoom_factor if hud else 1.0
        rw = int(main_frame.winfo_reqwidth() / zf)
        rh = int(main_frame.winfo_reqheight() / zf)
        win.geometry(f"{rw}x{rh}+{(sw - rw) // 2}+{hud._px(110) if hud else 110}")

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
    tk.Label(title_bar, text="⬡", font=("Consolas", 16), fg=_ACCENT, bg=_PANEL).pack(side="left", padx=(18, 10))
    tk.Label(title_bar, text=title.upper(), font=F_TITLE, fg=_TEXT, bg=_PANEL).pack(side="left")
    
    def _cancel():
        try: win.grab_release()
        except: pass
        win.destroy()
        
    btn_close = tk.Label(title_bar, text="✕", font=("Consolas", 14), fg=_DIM, bg=_PANEL, cursor="hand2")
    btn_close.pack(side="right", padx=16)
    btn_close.bind("<Button-1>", lambda e: _cancel())
    btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=_RED))
    btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=_DIM))

    content = tk.Frame(main_frame, bg=_BG)
    content.pack(fill="x", padx=32, pady=(32, 10))
    
    tk.Label(content, text=header.upper(), font=F_HDR, fg=_ACCENT, bg=_BG, anchor="w").pack(fill="x")
    tk.Label(content, text=hint_voice, font=F_HINT, fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(2, 8))
    
    is_file_op = "ФАЙЛ" in header.upper() or "ДОКУМЕНТ" in header.upper() or show_extension_field
    entry_path = None
    if initial_path is not None:
        tk.Label(content, text="РАСПОЛОЖЕНИЕ:", font=("Consolas", 9, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x")
        path_frame = tk.Frame(content, bg=_BG)
        path_frame.pack(fill="x", pady=(2, 6))
        entry_path = ctk.CTkEntry(
            path_frame, height=48, font=("Consolas", hud._fs(12)),
            fg_color=_BG, border_color=_blend(_CYAN, 0.3), text_color=_CYAN,
            border_width=2, corner_radius=10,
        )
        entry_path.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry_path.insert(0, initial_path)
        
        def _browse_native():
            from tkinter import filedialog
            selected = filedialog.askdirectory(initialdir=entry_path.get())
            if selected:
                entry_path.delete(0, tk.END)
                entry_path.insert(0, selected)
                _refresh_nav()
                
        ctk.CTkButton(
            path_frame, text="📁", width=48, height=52, fg_color="transparent",
            border_color=_BRD, border_width=1, text_color=_CYAN,
            hover_color=_blend(_CYAN, 0.15), font=("Consolas", hud._fs(14)), corner_radius=4, command=_browse_native
        ).pack(side="right")
        
        nav_wrap = tk.Frame(content, bg=_BG)
        nav_wrap.pack(fill="x", pady=(0, 8))
        nav_scroll = tk.Frame(nav_wrap, bg=_BG)
        nav_scroll.pack()
        
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
            _btn_kw = dict(height=42, fg_color=_blend(_ACCENT, 0.1), text_color=_TEXT,
                           hover_color=_blend(_ACCENT, 0.2), font=("Consolas", 11), corner_radius=12)
            nav_items = [("[ .. ]", curr.parent, False)]
            home = Path.home()
            _std_paths = [("DESKTOP", home / "Desktop"), ("DOCS", home / "Documents"), ("DOWNLOADS", home / "Downloads"), ("PROJECT", Path.cwd())]
            for name, path in _std_paths:
                if path.exists():
                    nav_items.append((name, path, False))
            try:
                subs = sorted([d for d in curr.iterdir() if d.is_dir() and not d.name.startswith('.')], key=lambda x: x.name.lower())
                for d in subs[:12]:
                    nav_items.append((f"📂 {d.name}", d, False))
            except: pass
            
            def _select_item(target, is_file):
                if is_file:
                    fname = Path(target).stem
                    if entry_name:
                        entry_name.delete(0, tk.END); entry_name.insert(0, fname)
                        ext = Path(target).suffix.lstrip('.')
                        if combo_ext and ext:
                            for v in combo_ext.values:
                                if f"(.{ext})" in v.lower() or f".{ext}" in v.lower():
                                    combo_ext._var.set(v); break
                    elif entry:
                        entry.delete(0, tk.END); entry.insert(0, fname)
                else:
                    _nav_to(str(target))

            MAX_COLS = 4
            for i, (label, target, is_file) in enumerate(nav_items):
                r, c = divmod(i, MAX_COLS)
                btn = ctk.CTkButton(nav_scroll, text=label, fg_color=_blend(_ACCENT, 0.1), command=lambda t=target, f=is_file: _select_item(t, f), **{k:v for k,v in _btn_kw.items() if k != 'fg_color'})
                btn.grid(row=r, column=c, padx=3, pady=3)
            _recenter()
            
        _refresh_nav()
    
    entry = None
    entry_name = None
    combo_ext = None
    if initial_path and show_extension_field:
        from actions.programming_extensions import get_programming_extensions
        tk.Label(content, text="ИМЯ ФАЙЛА (БЕЗ РАСШИРЕНИЯ):", font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 2))
        _name_ph = (placeholder or "").strip() or "например utils или readme"
        entry_name = ctk.CTkEntry(
            content, height=52, font=("Consolas", hud._fs(16)),
            fg_color=_BG, border_color=_blend(_CYAN, 0.3), text_color=_TEXT,
            placeholder_text=_name_ph, placeholder_text_color=_blend(_WHITE, 0.25),
            border_width=2, corner_radius=12,
        )
        entry_name.pack(fill="x", pady=(0, 8))
        if initial_value: entry_name.insert(0, initial_value)
        
        tk.Label(content, text="ТИП / РАСШИРЕНИЕ (НАПР. VUE, RS):", font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 2))
        _CORE_DESC = {"docx": "Word Документ  (.docx)", "xlsx": "Excel Таблица  (.xlsx)", "pptx": "PowerPoint Презентация  (.pptx)", "txt":  "Текстовый файл  (.txt)", "tsx":  "TypeScript JSX  (.tsx)", "ts":   "TypeScript файл  (.ts)", "py":   "Python Скрипт  (.py)", "js":   "JavaScript Файл  (.js)", "html": "Веб-страница  (.html)", "md":   "Markdown Документ  (.md)"}
        vals = []
        for ext in ["docx", "xlsx", "pptx", "txt"]: vals.append(_CORE_DESC[ext])
        for pe in get_programming_extensions():
            pe = pe.lstrip(".")
            if pe in ["docx", "xlsx", "pptx", "txt"]: continue
            vals.append(_CORE_DESC.get(pe, f"Файл .{pe}  (.{pe})"))
        ext0 = (default_extension or "txt").strip().lower().lstrip(".") or "txt"
        ext_var = tk.StringVar(value=_CORE_DESC.get(ext0, f"Файл .{ext0}  (.{ext0})"))
        combo_ext = _HUDDropdown(hud, content, vals, ext_var, accent=_CYAN)
        combo_ext.frame.pack(fill="x", pady=(0, 12))
        entry_name.focus_set()
    else:
        if initial_path:
            tk.Label(content, text="ИМЯ ФАЙЛА:" if is_file_op else "ИМЯ ПАПКИ:", font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(4, 2))
        entry = ctk.CTkEntry(content, height=60, font=("Consolas", hud._fs(22)), fg_color=_BG, border_color=_blend(_CYAN, 0.5), text_color=_WHITE, placeholder_text=(placeholder or "").strip() or "Введите здесь...", placeholder_text_color=_blend(_WHITE, 0.2), border_width=2, corner_radius=6)
        entry.pack(fill="x", pady=(4, 30))
        if initial_value: entry.insert(0, initial_value)
        entry.focus_set()
    
    btn_wrap = tk.Frame(content, bg=_BG)
    btn_wrap.pack(fill="x", pady=(10, 20))
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor="center")
    
    def _confirm():
        nonlocal result
        if initial_path is not None and show_extension_field and entry_name is not None and combo_ext is not None:
            stem = entry_name.get().strip()
            if not stem: return
            raw_ext = ext_var.get().strip().lower()
            if " (." in raw_ext: ext = raw_ext.split(" (.")[-1].split(")")[0]
            elif ". " in raw_ext: ext = raw_ext.split(". ")[-1]
            elif "." in raw_ext: ext = raw_ext.split(".")[-1]
            else: ext = raw_ext
            ext = ext.replace("р", "p").replace("у", "y").replace("к", "k").replace("с", "c").replace("х", "x").replace("а", "a").replace("о", "o")
            result[0] = (entry_path.get().strip(), stem, ext)
            _cancel(); return
        msg = entry.get().strip() if entry is not None else ""
        if require_message_to_confirm and not msg: return
        if initial_path is not None: result[0] = (entry_path.get().strip(), msg)
        else: result[0] = msg
        _cancel()

    btn_ok = ctk.CTkButton(btn_inner, text=f"{ok_text.upper()}  ✦", width=220, height=54, fg_color=_blend(_CYAN, 0.15), border_color=_CYAN, border_width=2, text_color=_CYAN, hover_color=_blend(_CYAN, 0.4), font=("Consolas", hud._fs(12), "bold"), corner_radius=15, command=_confirm)
    btn_ok.pack(side="left", padx=10) 
    btn_cnc = ctk.CTkButton(btn_inner, text=f"{cancel_text.upper()}  ✕", width=220, height=54, fg_color="transparent", border_color="#3a415a", border_width=2, text_color=_TEXT, hover_color=_blend(_WHITE, 0.1), font=("Consolas", hud._fs(12), "bold"), corner_radius=15, command=_cancel)
    btn_cnc.pack(side="left", padx=10)

    win.bind("<Destroy>", lambda e: [unregister_voice_prompt(win) for unregister_voice_prompt in [lambda w: None] if False]) # Placeholder
    try:
        from ui.voice_prompt_bridge import register_voice_prompt, unregister_voice_prompt
        def _voice_cleanup(e):
            if e.widget is win: unregister_voice_prompt(win)
        win.bind("<Destroy>", _voice_cleanup)
        register_voice_prompt(win, on_confirm=_confirm, on_cancel=_cancel, confirm_phrases=tuple(voice_confirm), cancel_phrases=tuple(voice_cancel))
    except: pass

    if entry:
        entry.bind("<Return>", lambda e: _confirm()); entry.bind("<Escape>", lambda e: _cancel())
    if entry_name:
        entry_name.bind("<Return>", lambda e: _confirm()); entry_name.bind("<Escape>", lambda e: _cancel())

    def _fade(alpha=0.0):
        if not win.winfo_exists(): return
        alpha = min(alpha + 0.1, 0.98)
        win.attributes("-alpha", alpha)
        if alpha < 0.98: win.after(10, lambda: _fade(alpha))

    win.deiconify(); win.lift(); win.focus_force()
    win.update_idletasks() # Ensure sizes are calculated
    _recenter()
    _fade()

def _ask_via_hud(hud, master: tk.Misc, **kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out = [None]; done = threading.Event()
    def work():
        win = ctk.CTkToplevel(master); win.withdraw()
        _install_modal_content(win, out, hud=hud, **kwargs)
        try: master.wait_window(win)
        finally: done.set()
    hud._hud_queue.put(work); done.wait(timeout=600.0)
    return out[0]

def _ask_standalone(**kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out = [None]; root = ctk.CTk(); root.withdraw()
    _install_modal_content(root, out, hud=None, **kwargs)
    root.mainloop()
    return out[0]

def ask_text(*, title, header, ok_text="ОК", cancel_text="ОТМЕНА", placeholder="", width=640, height=300, hint_voice=_DEFAULT_HINT, voice_confirm_phrases=None, voice_cancel_phrases=None, require_message_to_confirm=False, initial_path=None, show_extension_field=False, default_extension=None, initial_value=None):
    vc = tuple(voice_confirm_phrases) if voice_confirm_phrases is not None else _VOICE_DOC_CONFIRM
    vz = tuple(voice_cancel_phrases) if voice_cancel_phrases is not None else _VOICE_DOC_CANCEL
    hud, master = _hud_root()
    if hud is not None and master is not None:
        try: return _ask_via_hud(hud, master, title=title, header=header, ok_text=ok_text, cancel_text=cancel_text, placeholder=placeholder, height=height, hint_voice=hint_voice, voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm, initial_path=initial_path, show_extension_field=show_extension_field, default_extension=default_extension, initial_value=initial_value)
        except: pass
    return _ask_standalone(title=title, header=header, ok_text=ok_text, cancel_text=cancel_text, placeholder=placeholder, height=height, hint_voice=hint_voice, voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm, initial_path=initial_path, show_extension_field=show_extension_field, default_extension=default_extension, initial_value=initial_value)
