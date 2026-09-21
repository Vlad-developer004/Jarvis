"""First-run setup wizards for extensions that need external config
(Telegram chat id, Google Calendar, mail, ETS2 AI narrator). Split out of
the old extensions.py purely for file size; no behavior change.
"""
from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _place_dialog
from ..hud_widgets import _HudScrollbar
from core.extensions import ExtensionManager
from .extensions_common import _load_settings, _save_settings, _bind_ctk_entry_clipboard

def _ask_chat_id(parent, hud, on_confirm):
    dlg = tk.Toplevel(parent); dlg.title(i18n.tr('camera.title')); dlg.configure(bg=_BG)  # type: ignore[call-arg]
    _set_dark_title_bar(dlg)
    dlg.after(100, lambda: _set_dark_title_bar(dlg))
    _apply_window_icon(dlg, hud)
    _place_dialog(dlg, hud, 500, 380); dlg.resizable(False, False)
    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(dlg, text=i18n.tr('camera.title'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H2, 'bold')).pack(pady=(16, 4))
    tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(0, 10))
    lines = [
        i18n.tr('camera.telegram_note'),
        '',
        i18n.tr('camera.how_to'),
        i18n.tr('camera.step1'),
        i18n.tr('camera.step2')
    ]
    for line in lines:
        col = _CYAN if ':' in line else _TEXT if line else _BG
        tk.Label(dlg, text=line, bg=_BG, fg=col, font=(hud._F, JStyle.TEXT_SMALL, 'bold' if ':' in line else '')).pack(anchor='w', padx=28)
    tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(12, 10))
    entry_var = tk.StringVar(); entry = ctk.CTkEntry(dlg, textvariable=entry_var, placeholder_text='Chat ID', font=(hud._F, JStyle.TEXT_BODY), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=JStyle.H_NORM)
    entry.pack(fill='x', padx=28, pady=(0, 15)); _bind_ctk_entry_clipboard(dlg, entry, hud); entry.focus_set()
    def _confirm():
        cid = entry_var.get().strip()
        if not cid.lstrip('-').isdigit(): entry.configure(border_color=_RED); return
        on_confirm(cid); dlg.destroy()
    ctk.CTkButton(dlg, text=i18n.tr('buttons.save'), font=(hud._F, JStyle.TEXT_BODY, 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=28, pady=(0, 6))
    ctk.CTkButton(dlg, text=i18n.tr('buttons.cancel'), font=(hud._F, JStyle.TEXT_SMALL), height=JStyle.H_TOOL, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=28)
    dlg.bind('<Return>', lambda _: _confirm())

def _ask_calendar_setup(parent, hud, on_done=None):
    dlg = tk.Toplevel(parent); dlg.title(i18n.tr('calendar.setup')); dlg.configure(bg=_BG)  # type: ignore[call-arg]
    _set_dark_title_bar(dlg)
    dlg.after(100, lambda: _set_dark_title_bar(dlg))
    _apply_window_icon(dlg, hud)
    _w, _h = _place_dialog(dlg, hud, 560, 520)
    dlg.minsize(int(_w * 0.78), int(_h * 0.78)); dlg.resizable(True, True)
    # Use scrollable container
    canvas_f = tk.Frame(dlg, bg=_BG); canvas_f.pack(fill='both', expand=True)
    canvas = tk.Canvas(canvas_f, bg=_BG, highlightthickness=0)
    sb = _HudScrollbar(canvas_f, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=sb.set); canvas.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(canvas, bg=_BG)
    _cwin = canvas.create_window((0, 0), window=inner, anchor='nw', width=int(560*hud.zoom_factor))
    def _upd_scroll(): 
        if canvas.winfo_exists():
            h = inner.winfo_reqheight()
            ch = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(h, ch)))
    inner.bind('<Configure>', lambda e: _upd_scroll())
    def _on_wheel(e): canvas.yview_scroll(-1*(e.delta//120), 'units')
    dlg.bind('<MouseWheel>', _on_wheel)

    tk.Frame(inner, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(inner, text=i18n.tr('calendar.setup'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H2, 'bold')).pack(pady=(14, 4))
    tk.Label(inner, text=i18n.tr('calendar.add_files'), bg=_BG, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), wraplength=480, justify='left').pack(anchor='w', padx=24, pady=(0, 12))
    s0 = _load_settings(); sources_var = list(s0.get('calendar_sources', []) if isinstance(s0.get('calendar_sources'), list) else [])
    list_frame = tk.Frame(inner, bg=_PANEL, highlightthickness=1, highlightbackground=_blend(_CYAN, 0.3)); list_frame.pack(fill='both', expand=True, padx=24, pady=(0, 10))
    list_inner = tk.Frame(list_frame, bg=_PANEL); list_inner.pack(fill='both', expand=True, padx=8, pady=8)
    def _refresh_list():
        for w in list_inner.winfo_children(): w.destroy()
        for i, src in enumerate(sources_var):
            ref = src.get('url') or src.get('path') or i18n.tr('calendar.empty')
            row = tk.Frame(list_inner, bg=_PANEL); row.pack(fill='x', pady=2)
            tk.Label(row, text=ref, bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), anchor='w').pack(side='left', fill='x', expand=True, padx=(6, 6))
            ctk.CTkButton(row, text='✕', width=28, height=24, font=(hud._F, JStyle.TEXT_SMALL), fg_color=_blend(_RED, 0.12), hover_color=_blend(_RED, 0.3), text_color=_RED, command=lambda idx=i: (sources_var.pop(idx), _refresh_list())).pack(side='right')
    _refresh_list()
    add_frame = tk.Frame(inner, bg=_BG); add_frame.pack(fill='x', padx=24, pady=(0, 8))
    tk.Label(add_frame, text=i18n.tr('calendar.path_label'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_SMALL, 'bold')).pack(anchor='w', pady=(0, 4))
    entry_row = tk.Frame(add_frame, bg=_BG); entry_row.pack(fill='x')
    add_ent = ctk.CTkEntry(entry_row, height=34, font=(hud._F, JStyle.TEXT_BODY), fg_color=_blend(_CYAN, 0.08), border_color=_blend(_CYAN, 0.35), border_width=1, text_color=_WHITE, placeholder_text=i18n.tr('calendar.placeholder'))
    add_ent.pack(side='left', fill='x', expand=True, padx=(0, 8)); _bind_ctk_entry_clipboard(dlg, add_ent, hud)
    def _add_from_entry():
        val = (add_ent.get() or '').strip()
        if not val: return
        if val.lower().startswith(('http://', 'https://', 'webcal://')): sources_var.append({'url': val})
        else: sources_var.append({'path': val})
        add_ent.delete(0, 'end'); _refresh_list()
    ctk.CTkButton(entry_row, text=i18n.tr('calendar.add'), width=110, height=34, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.35), text_color=_CYAN, command=_add_from_entry).pack(side='left')
    def _confirm():
        s = _load_settings(); s['calendar_sources'] = sources_var; _save_settings(s)
        if on_done: on_done()
        dlg.destroy()
    ctk.CTkButton(inner, text=i18n.tr('buttons.save'), font=(hud._F, JStyle.TEXT_BODY, 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=24, pady=(0, 6))
    ctk.CTkButton(inner, text=i18n.tr('buttons.cancel'), font=(hud._F, JStyle.TEXT_SMALL), height=JStyle.H_TOOL, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=24, pady=(0, 12))

def _ask_mail_setup(parent, hud, on_done):
    dlg = tk.Toplevel(parent); dlg.title(i18n.tr('mail.title')); dlg.configure(bg=_BG)  # type: ignore[call-arg]
    _set_dark_title_bar(dlg)
    dlg.after(100, lambda: _set_dark_title_bar(dlg))
    _apply_window_icon(dlg, hud)
    _w, _h = _place_dialog(dlg, hud, 560, 640)
    dlg.minsize(int(_w * 0.85), int(_h * 0.8)); dlg.resizable(True, True)
    # Use scrollable container
    canvas_f = tk.Frame(dlg, bg=_BG); canvas_f.pack(fill='both', expand=True)
    canvas = tk.Canvas(canvas_f, bg=_BG, highlightthickness=0)
    sb = _HudScrollbar(canvas_f, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=sb.set); canvas.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(canvas, bg=_BG)
    _cwin = canvas.create_window((0, 0), window=inner, anchor='nw', width=int(560*hud.zoom_factor))
    def _upd_scroll(): 
        if canvas.winfo_exists():
            h = inner.winfo_reqheight()
            ch = canvas.winfo_height()
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(h, ch)))
    inner.bind('<Configure>', lambda e: _upd_scroll())
    def _on_wheel(e): canvas.yview_scroll(-1*(e.delta//120), 'units')
    dlg.bind('<MouseWheel>', _on_wheel)

    tk.Frame(inner, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(inner, text=i18n.tr('mail.header'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H2, 'bold')).pack(pady=(14, 4))
    tk.Label(inner, text=i18n.tr('mail.note'), bg=_BG, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), wraplength=480, justify='left').pack(anchor='w', padx=24, pady=(0, 12))
    s0 = _load_settings(); ma0 = s0.get('mail_account') if isinstance(s0.get('mail_account'), dict) else {}
    email_var, pwd_var = tk.StringVar(value=str(ma0.get('email') or '')), tk.StringVar(value=str(ma0.get('password') or ''))
    imap_var, smtp_var = tk.StringVar(value=str(ma0.get('imap_host') or '')), tk.StringVar(value=str(ma0.get('smtp_host') or ''))
    tk.Label(inner, text=i18n.tr('mail.address'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=24)
    ent_email = ctk.CTkEntry(inner, textvariable=email_var, placeholder_text='name@gmail.com', font=(hud._F, JStyle.TEXT_BODY), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=JStyle.H_NORM)
    ent_email.pack(fill='x', padx=24, pady=(5, 12)); _bind_ctk_entry_clipboard(dlg, ent_email, hud)
    tk.Label(inner, text=i18n.tr('mail.pwd'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=24)
    ent_pwd = ctk.CTkEntry(inner, textvariable=pwd_var, placeholder_text=i18n.tr('mail.pwd'), show='*', font=(hud._F, JStyle.TEXT_BODY), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=JStyle.H_NORM)
    ent_pwd.pack(fill='x', padx=24, pady=(5, 12)); _bind_ctk_entry_clipboard(dlg, ent_pwd, hud)
    tk.Label(inner, text=i18n.tr('mail.servers'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=24)
    ent_imap = ctk.CTkEntry(inner, textvariable=imap_var, placeholder_text='IMAP (imap.yandex.ru)', font=(hud._F, JStyle.TEXT_SMALL), fg_color=_PANEL, text_color=_WHITE, border_color=_SEP, border_width=1, corner_radius=2, height=JStyle.H_TOOL)
    ent_imap.pack(fill='x', padx=24, pady=(4, 6)); _bind_ctk_entry_clipboard(dlg, ent_imap, hud)
    ent_smtp = ctk.CTkEntry(inner, textvariable=smtp_var, placeholder_text='SMTP (smtp.yandex.ru)', font=(hud._F, JStyle.TEXT_SMALL), fg_color=_PANEL, text_color=_WHITE, border_color=_SEP, border_width=1, corner_radius=2, height=JStyle.H_TOOL)
    ent_smtp.pack(fill='x', padx=24, pady=(4, 8)); _bind_ctk_entry_clipboard(dlg, ent_smtp, hud)
    def _confirm():
        em, pw, ih, sh = email_var.get().strip(), pwd_var.get().strip(), imap_var.get().strip(), smtp_var.get().strip()
        if not em or '@' not in em: return
        if not pw: return
        try:
            from actions.mail_client import save_mail_account
            save_mail_account(em, pw, ih, sh, 993, 587); on_done(); dlg.destroy()
        except Exception: pass
    ctk.CTkButton(inner, text=i18n.tr('buttons.save'), font=(hud._F, JStyle.TEXT_BODY, 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=24, pady=(10, 6))
    ctk.CTkButton(inner, text=i18n.tr('buttons.cancel'), font=(hud._F, JStyle.TEXT_SMALL), height=JStyle.H_TOOL, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=24, pady=(0, 12))

def _open_commands_help(parent, hud, meta: dict) -> None:
    dlg = getattr(hud, '_ext_cmd_win', None)
    if dlg and dlg.winfo_exists():
        dlg.deiconify(); dlg.lift(); dlg.focus_force()
        for w in dlg.winfo_children(): w.destroy()
    else:
        dlg = tk.Toplevel(parent); hud._ext_cmd_win = dlg
        dlg.configure(bg=_BG)  # type: ignore[call-arg]
        _set_dark_title_bar(dlg)
        dlg.after(100, lambda: _set_dark_title_bar(dlg))
        _apply_window_icon(dlg, hud)
        dlg.title(f"{i18n.tr('extensions.commands_list')}: {meta.get('name', '').upper()}")
        _place_dialog(dlg, hud, 720, 600, grab=False)
        dlg.resizable(True, True)

    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()

    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')

    canvas_f = tk.Frame(dlg, bg=_BG); canvas_f.pack(fill='both', expand=True)
    canvas2 = tk.Canvas(canvas_f, bg=_BG, highlightthickness=0); 
    sb2 = _HudScrollbar(canvas_f, canvas2, color=_CYAN)
    canvas2.configure(yscrollcommand=sb2.set); canvas2.pack(side='left', fill='both', expand=True)
    
    # Absolute fill: Window width is 720, so 720 it is.
    inner2 = tk.Frame(canvas2, bg=_BG); _cwin2 = canvas2.create_window((0, 0), window=inner2, anchor='nw', width=int(720*hud.zoom_factor))
    def _upd_scroll2(): 
        if canvas2.winfo_exists():
            h = inner2.winfo_reqheight()
            ch = canvas2.winfo_height()
            canvas2.configure(scrollregion=(0, 0, canvas2.winfo_width(), max(h, ch)))
            
    def _on_resize_cmd(e):
        if not dlg.winfo_exists(): return
        if e.widget != dlg: return
        if canvas2.winfo_exists():
            canvas2.itemconfig(_cwin2, width=e.width - 12)
            _upd_scroll2()
            
    dlg.bind('<Configure>', _on_resize_cmd, add='+')
    inner2.bind('<Configure>', lambda e: _upd_scroll2())
    
    def _on_wheel2(e):
        if canvas2.winfo_exists(): canvas2.yview_scroll(-1 * (e.delta // 120), 'units')
    def _bind_wheel2(w):
        w.bind('<MouseWheel>', _on_wheel2)
        for child in w.winfo_children(): _bind_wheel2(child)

    for item in meta.get('commands', []):
        row_outer = tk.Frame(inner2, bg=_BG)
        row_outer.pack(fill='x', padx=(12, 12), pady=(0, 2))
        
        accent = tk.Frame(row_outer, bg=_CYAN, width=3)
        accent.pack(side='left', fill='y')
        
        # Consistent row background
        row_bg = _BG
        hover_bg = _blend(_CYAN, 0.1) if _theme == 'light' else "#1a222d"
        
        row = tk.Frame(row_outer, bg=row_bg)
        row.pack(side='left', fill='both', expand=True)
        
        def _on_ent_r(e, r=row, h=hover_bg):
            r.configure(bg=h)  # type: ignore[call-arg]
            for c in r.winfo_children(): c.configure(bg=h)  # type: ignore[call-arg]
        def _on_lev_r(e, r=row, n=row_bg):
            r.configure(bg=n)  # type: ignore[call-arg]
            for c in r.winfo_children(): c.configure(bg=n)  # type: ignore[call-arg]
        row.bind('<Enter>', _on_ent_r); row.bind('<Leave>', _on_lev_r)

        tk.Label(row, text=f"«{item.get('say', '')}»", bg=row_bg, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(side='left', padx=18, pady=10)
        tk.Label(row, text=item.get('do', ''), bg=row_bg, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL)).pack(side='right', padx=24, pady=10)

    _bind_wheel2(dlg)
    dlg.after(200, _upd_scroll2)

ext_mgr = ExtensionManager()


def _ask_ets2_ai_setup(parent, hud, on_done=None) -> None:
    """Ask about AI after ETS2 install — adapts to whether key is already configured."""
    try:
        from features.ets2.llm import has_api_key
        key_ok = has_api_key()
    except Exception:
        return

    is_uk = (i18n.get_language() == 'uk')

    dlg = tk.Toplevel(parent)
    dlg.title("JARVIS AI — ETS2")
    dlg.configure(bg=_BG)
    _set_dark_title_bar(dlg)
    dlg.after(100, lambda: _set_dark_title_bar(dlg))
    _apply_window_icon(dlg, hud)
    _place_dialog(dlg, hud, 520, 310)
    dlg.resizable(False, False)

    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(
        dlg, text="◉  JARVIS AI  —  ETS2",
        bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H2, 'bold'),
    ).pack(pady=(18, 4))
    tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(0, 12))

    if key_ok:
        # Key is already configured — ask if they want AI for ETS2
        if is_uk:
            desc = (
                "AI-ключ вже налаштований.\n\n"
                "Увімкнути розумні брифінги та звіти для ETS2?\n"
                "Джарвіс генеруватиме унікальний коментар\n"
                "до кожного рейсу та доставки."
            )
            btn_yes, btn_no = "Увімкнути", "Ні, стандартні фрази"
        else:
            desc = (
                "AI-ключ уже настроен.\n\n"
                "Включить умные брифинги и отчёты для ETS2?\n"
                "Джарвис будет генерировать уникальный комментарий\n"
                "к каждому рейсу и доставке."
            )
            btn_yes, btn_no = "Включить", "Нет, стандартные фразы"

        def _enable():
            s = _load_settings(); s['ets2_llm_enabled'] = True; _save_settings(s)
            dlg.destroy()
            if on_done: on_done()

        def _disable():
            s = _load_settings(); s['ets2_llm_enabled'] = False; _save_settings(s)
            dlg.destroy()
            if on_done: on_done()

        tk.Label(dlg, text=desc, bg=_BG, fg=_TEXT,
                 font=(hud._F, JStyle.TEXT_SMALL), justify='left').pack(anchor='w', padx=28)
        btn_frame = tk.Frame(dlg, bg=_BG)
        btn_frame.pack(fill='x', padx=28, pady=(18, 10))
        ctk.CTkButton(
            btn_frame, text=btn_yes, font=(hud._F, JStyle.TEXT_BODY, 'bold'),
            height=36, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7),
            text_color=_BG, corner_radius=2, command=_enable,
        ).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ctk.CTkButton(
            btn_frame, text=btn_no, font=(hud._F, JStyle.TEXT_SMALL),
            height=36, fg_color=_PANEL, hover_color=_BRD_I,
            text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2,
            command=_disable,
        ).pack(side='left', fill='x', expand=True)
    else:
        # No key — offer to go to settings
        if is_uk:
            desc = (
                "Підключіть AI-модель — і Джарвіс даватиме\n"
                "розумні брифінги перед кожним рейсом і розгорнуті\n"
                "звіти після доставки замість стандартних фраз.\n\n"
                "Ключ додається один раз у налаштуваннях."
            )
            btn_setup, btn_skip = "Налаштувати AI", "Пропустити"
        else:
            desc = (
                "Подключите AI-модель — и Джарвис будет давать\n"
                "умные брифинги перед каждым рейсом и развёрнутые\n"
                "отчёты после доставки вместо стандартных фраз.\n\n"
                "Ключ добавляется один раз в настройках."
            )
            btn_setup, btn_skip = "Настроить AI", "Пропустить"

        def _open_ai_settings():
            dlg.destroy()
            try:
                from ui.dialogs.settings_dlg import open_settings
                open_settings(hud, tab='modules')
            except Exception:
                pass

        tk.Label(dlg, text=desc, bg=_BG, fg=_TEXT,
                 font=(hud._F, JStyle.TEXT_SMALL), justify='left').pack(anchor='w', padx=28)
        btn_frame = tk.Frame(dlg, bg=_BG)
        btn_frame.pack(fill='x', padx=28, pady=(18, 10))
        ctk.CTkButton(
            btn_frame, text=btn_setup, font=(hud._F, JStyle.TEXT_BODY, 'bold'),
            height=36, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7),
            text_color=_BG, corner_radius=2, command=_open_ai_settings,
        ).pack(side='left', fill='x', expand=True, padx=(0, 6))
        ctk.CTkButton(
            btn_frame, text=btn_skip, font=(hud._F, JStyle.TEXT_SMALL),
            height=36, fg_color=_PANEL, hover_color=_BRD_I,
            text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2,
            command=dlg.destroy,
        ).pack(side='left', fill='x', expand=True)

    tk.Frame(dlg, bg=_GREEN, height=2).pack(fill='x', side='bottom')

