"""Mail compose dialog. Split out of the old mail_dlg.py purely for file
size; no behavior change. See mail_client_dlg.py for the inbox viewer.
"""
from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from ..hud_constants import _BG, _CYAN, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _place_dialog
from .extensions_common import _bind_ctk_entry_clipboard
from .mail_shared import _sf, _bind_text_clipboard

def open_compose_dialog(hud, parent_win, set_status=None) -> None:
    from actions.mail_client import get_resolved_mail_config, send_message
    cfg = get_resolved_mail_config()
    if not cfg:
        if set_status:
            set_status('Почта не настроена', _RED)
        return
    dlg = tk.Toplevel(parent_win)
    dlg.title('JARVIS — Новое письмо')
    _set_dark_title_bar(dlg)
    dlg.after(100, lambda: _set_dark_title_bar(dlg))
    dlg.configure(bg=_BG)  # type: ignore[call-arg]
    _apply_window_icon(dlg, hud)
    _w, _h = _place_dialog(dlg, hud, 720, 620, grab=False)
    dlg.minsize(int(_w * 0.72), int(_h * 0.71))
    _card_bg = _BG
    _field_border = _blend(_CYAN, 0.35)
    top = tk.Frame(dlg, bg=_BG)
    top.pack(fill='x', padx=20, pady=(16, 12))
    tk.Label(top, text='НОВОЕ ПИСЬМО', bg=_BG, fg=_CYAN, font=(hud._F, _sf(14, hud.zoom_factor), 'bold')).pack(side='left')
    dlg_status = tk.Label(
        top, text=f'От: {cfg["email"]}', bg=_BG, fg=_DIM,
        font=(hud._F, _sf(9, hud.zoom_factor)), anchor='e',
    )
    dlg_status.pack(side='right')
    def _set_dlg_status(t, color=_DIM):
        dlg_status.config(text=t, fg=color)
    fields_fr = tk.Frame(dlg, bg=_BG)
    fields_fr.pack(fill='x', padx=14, pady=(4, 0))
    def _make_field(parent, label_text, row):
        tk.Label(
            parent, text=label_text, bg=_BG, fg=_DIM,
            font=(hud._F, _sf(10, hud.zoom_factor), 'bold'), width=10, anchor='e',
        ).grid(row=row, column=0, sticky='e', padx=(0, 8), pady=4)
        ent = ctk.CTkEntry(
            parent,
            height=JStyle.H_LARGE,
            font=(hud._F, _sf(11), 'bold'),
            fg_color=_blend(_CYAN, 0.08),
            border_color=_field_border,
            border_width=1,
            text_color=_WHITE,
        )
        ent.grid(row=row, column=1, sticky='ew', pady=4)
        _bind_ctk_entry_clipboard(dlg, ent, hud)
        return ent
    fields_fr.grid_columnconfigure(1, weight=1)
    to_ent = _make_field(fields_fr, 'Кому:', 0)
    cc_ent = _make_field(fields_fr, 'Копия:', 1)
    subj_ent = _make_field(fields_fr, 'Тема:', 2)
    body_fr = tk.Frame(dlg, bg=_BG)
    body_fr.pack(fill='both', expand=True, padx=14, pady=(8, 4))
    tk.Label(body_fr, text='Текст письма', bg=_BG, fg=_CYAN,
             font=(hud._F, _sf(10, hud.zoom_factor), 'bold')).pack(anchor='w', pady=(0, 6))
    compose_txt = ctk.CTkTextbox(
        body_fr,
        font=(hud._F, _sf(11)),
        fg_color=_card_bg,
        text_color=_TEXT,
        border_color=_blend(_GREEN, 0.5),
        border_width=1,
        corner_radius=JStyle.RAD_BTN,
        scrollbar_button_color=_blend(_CYAN, 0.25),
        scrollbar_button_hover_color=_blend(_CYAN, 0.42),
    )
    compose_txt.pack(fill='both', expand=True)
    try:
        compose_txt._textbox.configure(
            insertbackground=_CYAN,
            selectbackground=_blend(_CYAN, 0.35),
            selectforeground=_WHITE,
        )
    except Exception:
        pass
    _bind_text_clipboard(dlg, compose_txt)
    comp_attach: list[Path] = []
    attach_wrap = tk.Frame(dlg, bg=_card_bg, highlightbackground=_blend(_GREEN, 0.22), highlightthickness=1)
    attach_wrap.pack(fill='x', padx=14, pady=(4, 0))
    attach_inner = tk.Frame(attach_wrap, bg=_card_bg)
    tk.Label(attach_wrap, text='Вложения', bg=_card_bg, fg=_DIM,
             font=(hud._F, _sf(9, hud.zoom_factor), 'bold')).pack(anchor='w', padx=8, pady=(6, 2))
    attach_inner.pack(fill='both', padx=8, pady=(0, 8))
    def _refresh_comp_attach():
        for w in attach_inner.winfo_children():
            w.destroy()
        if not comp_attach:
            tk.Label(attach_inner, text='Нет вложений', bg=_card_bg, fg=_DIM,
                     font=(hud._F, _sf(9, hud.zoom_factor))).pack(anchor='w')
            return
        for p in comp_attach:
            row = tk.Frame(attach_inner, bg=_card_bg)
            row.pack(fill='x', pady=2)
            tk.Label(row, text=p.name, bg=_card_bg, fg=_TEXT,
                     font=(hud._F, _sf(9, hud.zoom_factor)), anchor='w').pack(side='left', fill='x', expand=True)
            ctk.CTkButton(
                row, text='✕', width=36, height=JStyle.H_TOOL,
                font=(hud._F, _sf(10), 'bold'),
                fg_color=_blend(_RED, 0.12), hover_color=_blend(_RED, 0.3), text_color=_RED,
                command=lambda path=p: _rm_comp_attach(path),
            ).pack(side='right')
    def _rm_comp_attach(p):
        try:
            comp_attach.remove(p)
        except ValueError:
            pass
        _refresh_comp_attach()
    def _add_comp_paths(paths):
        for s in paths:
            if not s:
                continue
            p = Path(s)
            if p.is_file() and p not in comp_attach:
                comp_attach.append(p)
        _refresh_comp_attach()
    def _comp_pick_files():
        paths = filedialog.askopenfilenames(parent=dlg, title='Файлы для вложения',
                                            filetypes=[('Все файлы', '*.*')])
        _add_comp_paths(paths)
    def _comp_pick_images():
        paths = filedialog.askopenfilenames(parent=dlg, title='Фото',
                                            filetypes=[('Изображения', '*.png *.jpg *.jpeg *.gif *.webp *.bmp'),
                                                       ('Все файлы', '*.*')])
        _add_comp_paths(paths)
    def _comp_pick_videos():
        paths = filedialog.askopenfilenames(parent=dlg, title='Видео',
                                            filetypes=[('Видео', '*.mp4 *.mov *.avi *.mkv *.webm *.m4v'),
                                                       ('Все файлы', '*.*')])
        _add_comp_paths(paths)
    _refresh_comp_attach()
    tool = tk.Frame(dlg, bg=_BG)
    tool.pack(fill='x', padx=14, pady=(8, 4))
    bt_kw = {
        'font': (hud._F, _sf(10), 'bold'),
        'height': 44,
        'fg_color': _blend(_CYAN, 0.12),
        'hover_color': _blend(_CYAN, 0.24),
    }
    ctk.CTkButton(tool, text='Файл…', width=88, command=_comp_pick_files, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='Фото…', width=88, command=_comp_pick_images, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='Видео…', width=88, command=_comp_pick_videos, **bt_kw).pack(side='left', padx=(0, 6))
    btn_row = tk.Frame(dlg, bg=_BG)
    btn_row.pack(fill='x', padx=14, pady=(12, 20))
    _btn_center = tk.Frame(btn_row, bg=_BG)
    _btn_center.pack(anchor='center')
    def _do_compose_send():
        to_val = (to_ent.get() or '').strip()
        cc_val = (cc_ent.get() or '').strip()
        subj_val = (subj_ent.get() or '').strip()
        body_val = compose_txt.get('1.0', 'end-1c').strip()
        if not to_val:
            _set_dlg_status('Укажите адрес получателя', _AMBER)
            return
        if not body_val and not comp_attach:
            _set_dlg_status('Введите текст письма или добавьте вложения', _AMBER)
            return
        total_b = sum(p.stat().st_size for p in comp_attach if p.is_file())
        if total_b > 26 * 1024 * 1024:
            _set_dlg_status('Вложения > 25 МБ — уменьшите размер', _RED)
            return
        _set_dlg_status('Отправка…', _AMBER)
        paths_copy = [Path(x) for x in comp_attach]
        def work():
            ok, msg = send_message(
                to_addr=to_val,
                subject=subj_val,
                body=body_val,
                cc=cc_val,
                attachments=paths_copy,
            )
            def _done():
                _set_dlg_status(msg, _GREEN if ok else _RED)
                if ok:
                    if set_status:
                        set_status(f'Письмо отправлено → {to_val}', _GREEN)
                    dlg.after(1200, dlg.destroy)
            dlg.after(0, _done)
        threading.Thread(target=work, daemon=True).start()
    ctk.CTkButton(
        _btn_center, text='ОТПРАВИТЬ', width=220, height=JStyle.H_HUGE,
        font=(hud._F, _sf(12), 'bold'),
        fg_color=_blend(_GREEN, 0.25), hover_color=_blend(_GREEN, 0.45), text_color=_GREEN,
        command=_do_compose_send,
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _btn_center, text=i18n.tr('buttons.cancel'), width=160, height=JStyle.H_HUGE,
        font=(hud._F, _sf(11), 'bold'),
        fg_color=_blend(_CYAN, 0.12), hover_color=_blend(_CYAN, 0.22),
        command=dlg.destroy,
    ).pack(side='left')
    to_ent.focus_set()
