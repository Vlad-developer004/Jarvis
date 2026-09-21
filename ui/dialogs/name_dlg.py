from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import threading
import tkinter as tk
from collections.abc import Sequence
import customtkinter as ctk
from pathlib import Path
from ui.hud_constants import _AMBER, _BG, _BRD, _CYAN, _DIM, _PANEL, _SEP, _TEXT, _WHITE, _RED
from ui.hud_utils import _blend, _set_dark_title_bar, _apply_window_icon
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
    F_HDR = ("Consolas", JStyle.TEXT_H2, "bold")
    F_ENTRY = ("Consolas", 15) # Positive points for CTK
    F_EXT_ENTRY = ("Consolas", 12)
    F_HINT = ("Segoe UI", JStyle.TEXT_SMALL)
    F_TITLE = ("Consolas", JStyle.TEXT_SMALL, "bold")
    
    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    ctk.set_appearance_mode("Light" if _theme == "light" else "Dark")
    sw = win.winfo_screenwidth()
    
    # Start with empty geometry to allow auto-layout calculation
    # Use underlying tk.Toplevel method to avoid CTK's empty string parsing crash
    tk.Toplevel.geometry(win, "")
    
    win.configure(fg_color=_BG)  # type: ignore[call-arg]
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)

    win.title(title.upper())

    _centered_once = [False]

    def _recenter(force_collapse: bool = False):
        # Collapse to content size only on the FIRST show (avoid flicker on nav updates)
        win.update_idletasks()
        if force_collapse or not _centered_once[0]:
            tk.Toplevel.geometry(win, "")
            win.update_idletasks()

        rw = win.winfo_width()
        rh = win.winfo_height()
        if rw < 10:
            rw = main_frame.winfo_reqwidth()
            rh = main_frame.winfo_reqheight()

        from ui.hud_utils import _get_work_area
        l, t, r, b = _get_work_area()
        x = l + (r - l) // 2 - rw // 2
        y = t + (b - t) // 2 - rh // 2
        x = max(l, min(x, r - rw))
        y = max(t, min(y, b - rh))

        tk.Toplevel.geometry(win, f'+{x}+{y}')
        _centered_once[0] = True

        # minsize: bypass CTK to avoid double-scaling (CTK window_scaling already enlarges widgets)
        tk.Toplevel.minsize(win, 550, 250)

    main_frame = tk.Frame(win, bg=_BG, bd=0)
    main_frame.pack(fill="both") # Removed expand=True to prevent bottom stretching
    
    # THE FAMOUS CYAN LINE
    tk.Frame(main_frame, bg=_ACCENT, height=2).pack(fill="x")

    def _cancel():
        try: win.grab_release()
        except: pass
        win.destroy()

    content = tk.Frame(main_frame, bg=_BG)
    content.pack(fill="x", padx=32, pady=(28, 0))
    
    header_f = tk.Frame(content, bg=_BG)
    header_f.pack(fill="x")
    
    icon_char = "📁" if "ПАПК" in header.upper() else "📄"
    tk.Label(header_f, text=icon_char, font=("Consolas", JStyle.TEXT_H1), fg=_ACCENT, bg=_BG).pack(side="left", padx=(0, 10))
    tk.Label(header_f, text=header.upper(), font=F_HDR, fg=_ACCENT, bg=_BG, anchor="w").pack(side="left")
    
    tk.Label(content, text=hint_voice, font=F_HINT, fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 8))
    
    is_file_op = "ФАЙЛ" in header.upper() or "ДОКУМЕНТ" in header.upper() or show_extension_field
    entry_path = None
    if initial_path is not None:
        tk.Label(content, text=i18n.tr('file.location'), font=("Consolas", 9, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x")
        path_frame = tk.Frame(content, bg=_BG)
        path_frame.pack(fill="x", pady=(2, 6))
        entry_path = ctk.CTkEntry(
            path_frame, height=JStyle.H_NORM, font=("Consolas", 12),
            fg_color=_PANEL, border_color=_blend(_CYAN, 0.3), text_color=_CYAN,
            border_width=2, corner_radius=JStyle.RAD_PANEL,
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
            path_frame, text="📁", width=36, height=JStyle.H_NORM, fg_color="transparent",
            border_color=_BRD, border_width=1, text_color=_CYAN,
            hover_color=_blend(_CYAN, 0.15), font=("Consolas", 12), corner_radius=4, command=_browse_native
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
            _btn_kw = dict(height=JStyle.H_TOOL, fg_color=_blend(_ACCENT, 0.1), text_color=_TEXT,
                           hover_color=_blend(_ACCENT, 0.2), font=("Consolas", 9), corner_radius=JStyle.RAD_BTN)
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
                btn = ctk.CTkButton(nav_scroll, text=label, fg_color=_blend(_ACCENT, 0.1), command=lambda t=target, f=is_file: _select_item(t, f), **{k:v for k,v in _btn_kw.items() if k != 'fg_color'})  # type: ignore
                btn.grid(row=r, column=c, padx=3, pady=3)
            _recenter()
            
        _refresh_nav()
    
    entry = None
    entry_name = None
    combo_ext = None
    ext_var = None
    if initial_path and show_extension_field:
        from actions.programming_extensions import get_programming_extensions
        tk.Label(content, text=i18n.tr('file.name_no_ext'), font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 2))
        _name_ph = (placeholder or "").strip() or ("наприклад utils або readme" if i18n.get_language() == "uk" else "например utils или readme")
        entry_name = ctk.CTkEntry(
            content, height=JStyle.H_NORM, font=("Consolas", 13),
            fg_color=_PANEL, border_color=_blend(_CYAN, 0.3), text_color=_TEXT,
            placeholder_text=_name_ph, placeholder_text_color=_blend(_WHITE, 0.25),
            border_width=2, corner_radius=JStyle.RAD_PANEL,
        )
        entry_name.pack(fill="x", pady=(0, 8))
        if initial_value: entry_name.insert(0, initial_value)
        
        tk.Label(content, text=i18n.tr('file.type_label'), font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 2))
        is_uk = (i18n.get_language() == 'uk')
        if is_uk:
            _CORE_DESC = {
                "docx": "Word Документ  (.docx)",
                "xlsx": "Excel Таблиця  (.xlsx)",
                "pptx": "PowerPoint Презентація  (.pptx)",
                "txt":  "Текстовий файл  (.txt)",
                "tsx":  "TypeScript JSX  (.tsx)",
                "ts":   "TypeScript файл  (.ts)",
                "py":   "Python Скрипт  (.py)",
                "js":   "JavaScript Файл  (.js)",
                "html": "Веб-сторінка  (.html)",
                "md":   "Markdown Документ  (.md)"
            }
        else:
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
            tk.Label(content, text=i18n.tr('file.name') if is_file_op else i18n.tr('name_dlg.folder_name'), font=("Consolas", 12, "bold"), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(4, 2))
        entry = ctk.CTkEntry(
            content, height=JStyle.H_NORM, font=("Consolas", 14),
            fg_color=_PANEL, border_color=_blend(_CYAN, 0.5), text_color=_WHITE,
            placeholder_text=(placeholder or "").strip() or i18n.tr('name_dlg.type_here'),
            placeholder_text_color=_blend(_WHITE, 0.2), border_width=2, corner_radius=JStyle.RAD_PANEL
        )
        entry.pack(fill="x", pady=(4, 15))
        if initial_value: entry.insert(0, initial_value)
        entry.focus_set()
    
    btn_wrap = tk.Frame(content, bg=_BG)
    btn_wrap.pack(fill="x", pady=(12, 20))
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor="center")
    
    def _confirm():
        nonlocal result
        if initial_path is not None and show_extension_field and entry_name is not None and combo_ext is not None and ext_var is not None and entry_path is not None:
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
        if initial_path is not None and entry_path is not None: result[0] = (entry_path.get().strip(), msg)
        else: result[0] = msg
        _cancel()

    btn_ok = ctk.CTkButton(btn_inner, text=f"{ok_text.upper()}  ✦", width=140, height=JStyle.H_NORM, fg_color=_blend(_CYAN, 0.15), border_color=_CYAN, border_width=2, text_color=_CYAN, hover_color=_blend(_CYAN, 0.4), font=("Consolas", 11, "bold"), corner_radius=JStyle.RAD_PANEL, command=_confirm)
    btn_ok.pack(side="left", padx=10) 
    btn_cnc = ctk.CTkButton(btn_inner, text=f"{cancel_text.upper()}  ✕", width=140, height=JStyle.H_NORM, fg_color="transparent", border_color="#3a415a", border_width=2, text_color=_TEXT, hover_color=_blend(_WHITE, 0.1), font=("Consolas", 11, "bold"), corner_radius=JStyle.RAD_PANEL, command=_cancel)
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

    win.deiconify(); win.lift(); win.focus_force()  # type: ignore[attr-defined]
    try: win.grab_set()
    except: pass
    win.update_idletasks() # Ensure sizes are calculated
    _recenter()
    from ui.hud_utils import _make_resizable
    _make_resizable(win)  # type: ignore[arg-type]

def _ask_via_hud(hud, master: tk.Misc, **kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out = [None]; done = threading.Event()
    def work():
        try:
            win = ctk.CTkToplevel(master); win.withdraw()
            _install_modal_content(win, out, hud=hud, **kwargs)
            master.wait_window(win)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            done.set()
    hud._hud_queue.put(work); done.wait()
    return out[0]

def _ask_standalone(**kwargs) -> str | tuple[str, str] | tuple[str, str, str] | None:
    out = [None]; root = ctk.CTk(); root.withdraw()
    _install_modal_content(root, out, hud=None, **kwargs)
    root.mainloop()
    return out[0]

def ask_text(*, title, header, ok_text=None, cancel_text=None, placeholder="", width=640, height=JStyle.H_TOOL, hint_voice=None, voice_confirm_phrases=None, voice_cancel_phrases=None, require_message_to_confirm=False, initial_path=None, show_extension_field=False, default_extension=None, initial_value=None):
    if ok_text is None:
        ok_text = i18n.tr('buttons.ok') or "ОК"
    if cancel_text is None:
        cancel_text = i18n.tr('buttons.cancel')
    if hint_voice is None:
        hint_voice = i18n.tr('name_dlg.default_hint')
    vc = tuple(voice_confirm_phrases) if voice_confirm_phrases is not None else _VOICE_DOC_CONFIRM
    vz = tuple(voice_cancel_phrases) if voice_cancel_phrases is not None else _VOICE_DOC_CANCEL
    hud, master = _hud_root()
    if hud is not None and master is not None:
        try: return _ask_via_hud(hud, master, title=title, header=header, ok_text=ok_text, cancel_text=cancel_text, placeholder=placeholder, height=height, hint_voice=hint_voice, voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm, initial_path=initial_path, show_extension_field=show_extension_field, default_extension=default_extension, initial_value=initial_value)
        except: pass
    return _ask_standalone(title=title, header=header, ok_text=ok_text, cancel_text=cancel_text, placeholder=placeholder, height=height, hint_voice=hint_voice, voice_confirm=vc, voice_cancel=vz, require_message_to_confirm=require_message_to_confirm, initial_path=initial_path, show_extension_field=show_extension_field, default_extension=default_extension, initial_value=initial_value)
