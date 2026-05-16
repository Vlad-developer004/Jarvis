from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _SEP, _CYAN, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon
from .extensions import _bind_ctk_entry_clipboard
def _show_confirm_hud(hud, parent, title, text, ok_cb, danger=True):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.configure(bg=_BG)
    dlg.transient(parent)
    dlg.grab_set()
    _set_dark_title_bar(dlg)
    _apply_window_icon(dlg, hud)
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    W, H = 540, 180
    dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+{(sw - int(W*hud.zoom_factor)) // 2}+{(sh - int(H*hud.zoom_factor)) // 2}')
    dlg.resizable(False, False)
    tk.Frame(dlg, bg=_RED if danger else _CYAN, height=2).pack(fill='x', side='top')
    body = tk.Frame(dlg, bg=_BG)
    body.pack(fill='both', expand=True, padx=24, pady=20)
    tk.Label(
        body, text=text, bg=_BG, fg=_WHITE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        wraplength=W - 50, justify='center'
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
    dlg.configure(bg=_BG)
    _apply_window_icon(dlg, hud)
    sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
    W = int(min(720, sw * 0.85 / hud.zoom_factor))
    H = int(min(620, sh * 0.85 / hud.zoom_factor))
    dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+{(sw - int(W*hud.zoom_factor)) // 2}+{(sh - int(H*hud.zoom_factor)) // 2}')
    dlg.minsize(520, 440)
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
def open_mail_client(hud, reopen: bool = False) -> None:
    if not reopen and hasattr(hud, '_mail_win') and hud._mail_win and hud._mail_win.winfo_exists():
        hud._mail_win.lift()
        return
    if reopen and hasattr(hud, '_mail_win') and hud._mail_win and hud._mail_win.winfo_exists():
        hud._mail_win.destroy()
    win = tk.Toplevel(hud.root)
    hud._mail_win = win
    win.title('JARVIS — Почта')
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    hud._track_subwin('mail', win, lambda: open_mail_client(hud, reopen=True))
    win.configure(bg=_BG)
    win.overrideredirect(True)
    _apply_window_icon(win, hud)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f'{sw}x{sh}+0+0')
    W = int(sw / hud.zoom_factor)
    from actions.mail_client import (
        delete_message_by_uid,
        fetch_message_body,
        get_resolved_mail_config,
        list_recent_messages,
        send_message,
        send_reply,
    )
    cfg = get_resolved_mail_config()
    top = tk.Frame(win, bg=_BG)
    top.pack(fill='x', padx=20, pady=(16, 12))
    tk.Label(top, text='ПОЧТА', bg=_BG, fg=_CYAN, font=(hud._F, _sf(16, hud.zoom_factor), 'bold')).pack(side='left')
    def _open_compose():
        open_compose_dialog(hud, win, set_status=lambda t, c=_DIM: status.config(text=t, fg=c))
    ctk.CTkButton(
        top, text='✉  НАПИСАТЬ', width=180, height=JStyle.H_LARGE,
        font=(hud._F, _sf(11), 'bold'),
        fg_color=_blend(_GREEN, 0.22), hover_color=_blend(_GREEN, 0.4), text_color=_GREEN,
        command=_open_compose,
    ).pack(side='left', padx=(24, 0))
    
    # Close button for full-screen mode
    ctk.CTkButton(
        top, text='✕', width=48, height=JStyle.H_LARGE,
        font=(hud._F, _sf(14), 'bold'),
        fg_color="transparent", hover_color=_blend(_RED, 0.2), text_color=_RED,
        command=win.destroy,
    ).pack(side='right', padx=(10, 0))
    status = tk.Label(
        top,
        text='',
        bg=_BG,
        fg=_DIM,
        font=(hud._F, _sf(9, hud.zoom_factor), 'bold'),
        wraplength=int(max(400, sw/hud.zoom_factor - 550) * hud.zoom_factor),
        justify='right', # Change to right to keep it away from buttons
        anchor='e'
    )
    status.pack(side='right', fill='x', expand=True, padx=(20, 10))
    if not cfg:
        tk.Label(
            win,
            text='Учётная запись не заполнена. Откройте «Центр расширений», отключите и снова включите модуль «Почта» — '
            'или добавьте раздел mail_account в data/jarvis_settings.json (email, password, imap/smtp).',
            bg=_BG,
            fg=_AMBER,
            font=(hud._F, _sf(11, hud.zoom_factor)),
            wraplength=W - 40,
            justify='left',
        ).pack(padx=20, pady=40)
        ctk.CTkButton(
            win,
            text=i18n.tr('buttons.close'),
            width=160,
            font=(hud._F, _sf(11), 'bold'),
            fg_color=_blend(_CYAN, 0.2),
            command=win.destroy,
        ).pack(pady=20)
        return
    pan = tk.PanedWindow(win, bg=_BG, sashwidth=5, sashrelief='flat', sashpad=2)
    pan.pack(fill='both', expand=True, padx=20, pady=(0, 20))
    # Logical width of the sidebar, PanedWindow scales the frame but width=360 is starting point
    left = tk.Frame(pan, bg=_BG, width=320)
    right = tk.Frame(pan, bg=_BG)
    pan.add(left, minsize=int(260 * hud.zoom_factor))
    pan.add(right, minsize=int(400 * hud.zoom_factor))
    _LB = _BG
    _CARD_IDLE = _blend(_CYAN, 0.08)
    _CARD_HOVER = _blend(_CYAN, 0.16)
    _CARD_SEL = _blend(_CYAN, 0.22)
    _BR = hud._px(14)
    left_outer = tk.Frame(left, bg=_BRD)
    left_outer.pack(fill='both', expand=True, padx=4, pady=4)
    accent_bar = tk.Frame(left_outer, bg=_CYAN, height=2)
    accent_bar.pack(fill='x', side='top')
    left_inner = tk.Frame(left_outer, bg=_PANEL)
    left_inner.pack(fill='both', expand=True, padx=1, pady=(0, 1))
    corner_cv = tk.Canvas(left_inner, bg=_PANEL, highlightthickness=0, height=hud._px(10))
    corner_cv.pack(fill='x')
    def _draw_top_corners(_e=None):
        corner_cv.delete('all')
        w_c = corner_cv.winfo_width() or 300
        h_c = corner_cv.winfo_height() or 10
        for bx, by, sx, sy in ((2, 2, 1, 1), (w_c - 2, 2, -1, 1)):
            corner_cv.create_line(bx, by, bx + sx * _BR, by, fill=_CYAN, width=2)
            corner_cv.create_line(bx, by, bx, by + sy * _BR, fill=_CYAN, width=2)
    corner_cv.bind('<Configure>', _draw_top_corners)
    hdr_fr = tk.Frame(left_inner, bg=_PANEL)
    hdr_fr.pack(fill='x', padx=14, pady=(2, 0))
    tk.Label(hdr_fr, text='◈  ВХОДЯЩИЕ', bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(12, hud.zoom_factor), 'bold')).pack(anchor='w')
    tk.Frame(left_inner, bg=_blend(_CYAN, 0.18), height=1).pack(fill='x', padx=14, pady=(6, 0))
    count_lbl = tk.Label(
        left_inner, text='', bg=_PANEL, fg=_DIM,
        font=(hud._F, _sf(8, hud.zoom_factor)),
        wraplength=hud._px(320), justify='left', anchor='w'
    )
    count_lbl.pack(fill='x', padx=16, pady=(4, 2))
    list_canvas = tk.Canvas(left_inner, bg=_PANEL, highlightthickness=0)
    list_canvas.pack(fill='both', expand=True, padx=(6, 0), pady=(2, 6))
    sb_cv = tk.Canvas(list_canvas, width=hud._px(6), bg=_PANEL, highlightthickness=0)
    sb_cv.place(relx=1.0, x=-hud._px(6), rely=0, relheight=1.0)
    _sb_needed = [False]
    _sb_lo = [0.0]
    _sb_hi = [1.0]
    def _sb_set(lo, hi):
        lo, hi = float(lo), float(hi)
        _sb_lo[0], _sb_hi[0] = lo, hi
        needed = (hi - lo) < 0.99
        if needed != _sb_needed[0]:
            _sb_needed[0] = needed
            if not needed:
                sb_cv.place_forget()
            else:
                sb_cv.place(relx=1.0, x=-hud._px(6), rely=0, relheight=1.0)
        sb_cv.delete('all')
        if not needed:
            return
        h = sb_cv.winfo_height() or 100
        y0 = int(lo * h)
        y1 = max(y0 + 16, int(hi * h))
        sb_cv.create_rectangle(0, 0, hud._px(6), h, fill=_blend(_CYAN, 0.04), outline='')
        sb_cv.create_rectangle(1, y0, hud._px(6) - 1, y1, fill=_CYAN, outline='')
    list_inner = tk.Frame(list_canvas, bg=_PANEL)
    list_canvas.create_window((0, 0), window=list_inner, anchor='nw', tags='inner')
    def _on_list_configure(_e=None):
        list_canvas.configure(scrollregion=list_canvas.bbox('all'))
        w = list_canvas.winfo_width()
        if w > 1:
            list_canvas.itemconfigure('inner', width=w - hud._px(8))
    list_inner.bind('<Configure>', _on_list_configure)
    list_canvas.bind('<Configure>', lambda e: list_canvas.after_idle(_on_list_configure))
    list_canvas.configure(yscrollcommand=_sb_set)
    def _on_mousewheel(e):
        list_canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
    list_canvas.bind('<MouseWheel>', _on_mousewheel)
    list_inner.bind('<MouseWheel>', _on_mousewheel)
    selected_idx = [None]
    card_widgets: list[tk.Frame] = []
    def _set_card_colors(card, bg_c, strip_c, brd_c):
        card.configure(bg=bg_c, highlightbackground=brd_c)
        for ch in card.winfo_children():
            if isinstance(ch, tk.Frame) and ch.cget('width') == 4:
                ch.configure(bg=strip_c)
            elif isinstance(ch, tk.Frame):
                ch.configure(bg=bg_c)
                for sub in ch.winfo_children():
                    if isinstance(sub, tk.Label):
                        sub.configure(bg=bg_c)
    def _select_card(idx):
        prev = selected_idx[0]
        selected_idx[0] = idx
        if prev is not None and prev < len(card_widgets):
            _set_card_colors(card_widgets[prev], _CARD_IDLE, _SEP, _blend(_CYAN, 0.12))
        if idx is not None and idx < len(card_widgets):
            _set_card_colors(card_widgets[idx], _CARD_SEL, _CYAN, _CYAN)
            _trigger_select(idx)
    def _trigger_select(idx):
        if idx < 0 or idx >= len(meta_by_index):
            return
        uid = meta_by_index[idx].get('uid')
        current_uid[0] = uid
        set_status('Загрузка письма…', _AMBER)
        body_txt.delete('1.0', 'end')
        reply_txt.delete('1.0', 'end')
        attach_paths.clear()
        _refresh_attach_ui()
        current_mail[0] = None
        def work():
            ok, payload = fetch_message_body(uid or '')
            win.after(0, lambda: _apply_body(ok, payload))
        threading.Thread(target=work, daemon=True).start()
    def _build_card(idx: int, row: dict):
        subj = row.get('subject') or '(без темы)'
        sender = row.get('from') or ''
        date_s = row.get('date') or ''
        date_short = date_s[:16] if len(date_s) > 16 else date_s
        card = tk.Frame(
            list_inner, bg=_CARD_IDLE,
            highlightthickness=1, highlightbackground=_blend(_CYAN, 0.12),
            cursor='hand2',
        )
        card.pack(fill='x', padx=(8, hud._px(10)), pady=(0, 6))
        strip = tk.Frame(card, bg=_SEP, width=hud._px(6))
        strip.pack(side='left', fill='y')
        strip.pack_propagate(False)
        body = tk.Frame(card, bg=_CARD_IDLE)
        body.pack(side='left', fill='both', expand=True, padx=(8, 6), pady=6)
        subj_l = tk.Label(
            body, text=subj, bg=_CARD_IDLE, fg=_WHITE,
            font=(hud._F, _sf(10, hud.zoom_factor), 'bold'), anchor='w', justify='left',
            wraplength=hud._px(280)
        )
        subj_l.pack(fill='x', pady=(0, 2))
        sender_l = tk.Label(
            body, text=sender, bg=_CARD_IDLE, fg=_DIM,
            font=(hud._F, _sf(9, hud.zoom_factor)), anchor='w', justify='left',
            wraplength=hud._px(280)
        )
        sender_l.pack(fill='x')
        if date_short:
            date_l = tk.Label(
                body, text=date_short, bg=_CARD_IDLE, fg=_blend(_CYAN, 0.35),
                font=(hud._F, _sf(8, hud.zoom_factor)), anchor='w',
            )
            date_l.pack(fill='x')
            date_l.bind('<Button-1>', lambda e, i=idx: _select_card(i))
            date_l.bind('<MouseWheel>', _on_mousewheel)
        def _enter(e, c=card, s=strip, i=idx):
            if selected_idx[0] != i:
                c.configure(bg=_CARD_HOVER, highlightbackground=_blend(_CYAN, 0.4))
                s.configure(bg=_blend(_CYAN, 0.5))
                for w in c.winfo_children():
                    if isinstance(w, tk.Frame) and w != s:
                        w.configure(bg=_CARD_HOVER)
                        for ch in w.winfo_children():
                            if isinstance(ch, tk.Label):
                                ch.configure(bg=_CARD_HOVER)
        def _leave(e, c=card, s=strip, i=idx):
            if selected_idx[0] != i:
                c.configure(bg=_CARD_IDLE, highlightbackground=_blend(_CYAN, 0.12))
                s.configure(bg=_SEP)
                for w in c.winfo_children():
                    if isinstance(w, tk.Frame) and w != s:
                        w.configure(bg=_CARD_IDLE)
                        for ch in w.winfo_children():
                            if isinstance(ch, tk.Label):
                                ch.configure(bg=_CARD_IDLE)
        for widget in (card, body, subj_l, sender_l, strip):
            widget.bind('<Button-1>', lambda e, i=idx: _select_card(i))
            widget.bind('<Enter>', _enter)
            widget.bind('<Leave>', _leave)
            widget.bind('<MouseWheel>', _on_mousewheel)
        return card
    corner_bot_cv = tk.Canvas(left_inner, bg=_PANEL, highlightthickness=0, height=hud._px(10))
    corner_bot_cv.pack(fill='x', side='bottom')
    def _draw_bot_corners(_e=None):
        corner_bot_cv.delete('all')
        w_c = corner_bot_cv.winfo_width() or 300
        h_c = corner_bot_cv.winfo_height() or 10
        for bx, by, sx, sy in ((2, h_c - 2, 1, -1), (w_c - 2, h_c - 2, -1, -1)):
            corner_bot_cv.create_line(bx, by, bx + sx * _BR, by, fill=_CYAN, width=2)
            corner_bot_cv.create_line(bx, by, bx, by + sy * _BR, fill=_CYAN, width=2)
    corner_bot_cv.bind('<Configure>', _draw_bot_corners)
    meta_by_index: list[dict] = []
    current_uid: list[str | None] = [None]
    current_mail: list[dict | None] = [None]
    right_inner = tk.Frame(right, bg=_BG)
    right_inner.pack(fill='both', expand=True, padx=4, pady=(0, 4))
    right_inner.grid_columnconfigure(0, weight=1)
    right_inner.grid_rowconfigure(0, weight=4, minsize=hud._px(260))
    right_inner.grid_rowconfigure(1, weight=1, minsize=hud._px(140))
    right_inner.grid_rowconfigure(2, weight=0)
    _card_bg = _BG
    _txt_common = {
        'bg': _card_bg,
        'fg': _TEXT,
        'insertbackground': _CYAN,
        'selectbackground': _blend(_CYAN, 0.35),
        'selectforeground': _WHITE,
        'highlightthickness': 1,
        'highlightbackground': _blend(_CYAN, 0.28),
        'highlightcolor': _CYAN,
        'borderwidth': 0,
        'relief': 'flat',
        'font': (hud._F, _sf(11, hud.zoom_factor)),
        'wrap': 'word',
        'padx': 12,
        'pady': 12,
    }
    body_card = tk.Frame(right_inner, bg=_BG)
    body_card.grid(row=0, column=0, sticky='nsew', pady=(0, 8))
    tk.Label(body_card, text='Текст письма', bg=_BG, fg=_CYAN, font=(hud._F, _sf(11, hud.zoom_factor), 'bold')).pack(anchor='w', pady=(0, 6))
    body_wrap = tk.Frame(body_card, bg=_card_bg, highlightbackground=_blend(_CYAN, 0.3), highlightthickness=1)
    body_wrap.pack(fill='both', expand=True)
    body_txt = tk.Text(body_wrap, height=18, **_txt_common)
    body_txt.pack(fill='both', expand=True)
    reply_card = tk.Frame(right_inner, bg=_BG)
    reply_card.grid(row=1, column=0, sticky='nsew', pady=(0, 8))
    attach_paths: list[Path] = []
    attach_wrap = tk.Frame(reply_card, bg=_card_bg, highlightbackground=_blend(_GREEN, 0.22), highlightthickness=1)
    attach_inner = tk.Frame(attach_wrap, bg=_card_bg)
    def _refresh_attach_ui():
        for w in attach_inner.winfo_children():
            w.destroy()
        if not attach_paths:
            tk.Label(
                attach_inner,
                text='Нет вложений — кнопки «Файл», «Фото», «Видео»',
                bg=_card_bg,
                fg=_DIM,
                font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
            ).pack(anchor='w')
            return
        for p in attach_paths:
            row = tk.Frame(attach_inner, bg=_card_bg)
            row.pack(fill='x', pady=2)
            tk.Label(
                row,
                text=p.name,
                bg=_card_bg,
                fg=_TEXT,
                font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
                anchor='w',
            ).pack(side='left', fill='x', expand=True)
            ctk.CTkButton(
                row,
                text='✕',
                width=28,
                height=24,
                font=(hud._F, _sf(11), 'bold'),
                fg_color=_blend(_RED, 0.12),
                hover_color=_blend(_RED, 0.3),
                text_color=_RED,
                command=lambda path=p: _remove_attachment(path),
            ).pack(side='right')
    def _remove_attachment(p: Path):
        try:
            attach_paths.remove(p)
        except ValueError:
            pass
        _refresh_attach_ui()
    def _add_paths(paths: tuple[str, ...]):
        for s in paths:
            if not s:
                continue
            p = Path(s)
            if p.is_file() and p not in attach_paths:
                attach_paths.append(p)
        _refresh_attach_ui()
    def _pick_files():
        paths = filedialog.askopenfilenames(
            parent=win,
            title='Файлы для вложения',
            filetypes=[('Все файлы', '*.*')],
        )
        _add_paths(paths)
    def _pick_images():
        paths = filedialog.askopenfilenames(
            parent=win,
            title='Фото',
            filetypes=[
                ('Изображения', '*.png *.jpg *.jpeg *.gif *.webp *.bmp'),
                ('Все файлы', '*.*'),
            ],
        )
        _add_paths(paths)
    def _pick_videos():
        paths = filedialog.askopenfilenames(
            parent=win,
            title='Видео',
            filetypes=[
                ('Видео', '*.mp4 *.mov *.avi *.mkv *.webm *.m4v'),
                ('Все файлы', '*.*'),
            ],
        )
        _add_paths(paths)
    hdr = tk.Frame(reply_card, bg=_BG)
    hdr.pack(fill='x', pady=(0, 6))
    tk.Label(hdr, text='Ваш ответ', bg=_BG, fg=_CYAN, font=(hud._F, _sf(11, hud.zoom_factor), 'bold')).pack(side='left')
    tk.Label(
        hdr,
        text='Текст, вложения и ссылки',
        bg=_BG,
        fg=_DIM,
        font=(hud._F, _sf(8, hud.zoom_factor)),
    ).pack(side='left', padx=(10, 0))
    tool = tk.Frame(reply_card, bg=_BG)
    tool.pack(fill='x', pady=(0, 6))
    bt_kw = {
        'font': (hud._F, _sf(10), 'bold'),
        'height': 44,
        'fg_color': _blend(_CYAN, 0.12),
        'hover_color': _blend(_CYAN, 0.24),
        'text_color': _TEXT,
    }
    ctk.CTkButton(tool, text='Файл…', width=92, command=_pick_files, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='Фото…', width=92, command=_pick_images, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='Видео…', width=92, command=_pick_videos, **bt_kw).pack(side='left', padx=(0, 6))
    attach_wrap.pack(fill='x', pady=(0, 8))
    tk.Label(attach_wrap, text='Вложения', bg=_card_bg, fg=_DIM, font=(hud._F, _sf(10, hud.zoom_factor), 'bold')).pack(anchor='w', padx=8, pady=(6, 2))
    attach_inner.pack(fill='both', padx=8, pady=(0, 8))
    reply_wrap = tk.Frame(reply_card, bg=_BG)
    reply_wrap.pack(fill='both', expand=True)
    reply_txt = ctk.CTkTextbox(
        reply_wrap,
        width=max(400, W - 340),
        height=160,
        font=(hud._F, _sf(11)),
        fg_color=_card_bg,
        text_color=_TEXT,
        border_color=_blend(_GREEN, 0.5),
        border_width=1,
        corner_radius=JStyle.RAD_BTN,
        scrollbar_button_color=_blend(_CYAN, 0.25),
        scrollbar_button_hover_color=_blend(_CYAN, 0.42),
    )
    reply_txt.pack(fill='both', expand=True)
    try:
        reply_txt._textbox.configure(
            insertbackground=_CYAN,
            selectbackground=_blend(_CYAN, 0.35),
            selectforeground=_WHITE,
        )
    except Exception:
        pass
    def _add_link_dialog():
        dlg = tk.Toplevel(win)
        dlg.title('Ссылка в ответ')
        dlg.configure(bg=_BG)
        dlg.transient(win)
        dlg.grab_set()
        _set_dark_title_bar(dlg)
        _apply_window_icon(dlg, hud)
        dw = 460
        dlg.geometry(f'{int(dw*hud.zoom_factor)}x{int(132*hud.zoom_factor)}')
        dlg.minsize(380, 110)
        tk.Label(
            dlg,
            text='Вставьте URL — он будет добавлен в текст ответа (как в обычном письме).',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
            wraplength=dw - 24,
            justify='left',
        ).pack(anchor='w', padx=12, pady=(12, 6))
        ent = ctk.CTkEntry(
            dlg,
            width=dw - 24,
            height=34,
            font=(hud._F, _sf(11), 'bold'),
            fg_color=_blend(_CYAN, 0.08),
            border_color=_blend(_CYAN, 0.35),
        )
        ent.pack(padx=12, pady=(0, 10))
        _bind_ctk_entry_clipboard(dlg, ent, hud)
        def _ok():
            u = (ent.get() or '').strip()
            dlg.destroy()
            if u:
                reply_txt.focus_set()
                reply_txt.insert('insert', f'\n{u}\n')
        def _cancel():
            dlg.destroy()
        row = tk.Frame(dlg, bg=_BG)
        row.pack(fill='x', padx=12, pady=(0, 12))
        ctk.CTkButton(
            row,
            text='ВСТАВИТЬ',
            width=160,
            height=JStyle.H_LARGE,
            font=(hud._F, _sf(11), 'bold'),
            fg_color=_blend(_GREEN, 0.25),
            command=_ok,
        ).pack(side='left', padx=(0, 8))
        ctk.CTkButton(row, text=i18n.tr('buttons.cancel'), width=hud._px(120), height=hud._px(44), font=(hud._F, _sf(10, hud.zoom_factor)), fg_color=_blend(_CYAN, 0.1), command=_cancel).pack(side='left')
        ent.bind('<Return>', lambda e: _ok())
        ent.focus_set()
    ctk.CTkButton(tool, text='Ссылка…', width=92, command=_add_link_dialog, **bt_kw).pack(side='left', padx=(0, 6))
    _refresh_attach_ui()
    _bind_text_clipboard(win, reply_txt)
    def _body_readonly_key(e):
        if e.state & 0x4 and e.keysym.lower() in ('c', 'a', 'insert'):
            return
        if e.keysym in ('Left', 'Right', 'Up', 'Down', 'Home', 'End', 'Next', 'Prior'):
            return
        if e.keysym == 'Tab':
            reply_txt.focus_set()
            return 'break'
        return 'break'
    body_txt.bind('<Key>', _body_readonly_key)
    btn_row = tk.Frame(right_inner, bg=_BG)
    btn_row.grid(row=2, column=0, sticky='ew', pady=(4, 0))
    def set_status(t: str, color=_DIM):
        status.config(text=t, fg=color)
    def load_list():
        set_status('Загрузка списка…', _AMBER)
        def work():
            ok, data = list_recent_messages(50)
            win.after(0, lambda: _apply_list(ok, data))
        threading.Thread(target=work, daemon=True).start()
    def _apply_list(ok, data):
        for w in list_inner.winfo_children():
            w.destroy()
        card_widgets.clear()
        meta_by_index.clear()
        selected_idx[0] = None
        if not ok:
            set_status(str(data), _RED)
            return
        rows = data if isinstance(data, list) else []
        for i, row in enumerate(rows):
            meta_by_index.append(row)
            c = _build_card(i, row)
            card_widgets.append(c)
        count_lbl.configure(text=f'{len(rows)} писем  •  {cfg["email"]}')
        set_status(f'Аккаунт: {cfg["email"]}  •  {len(rows)} писем', _GREEN)
    def _apply_body(ok, payload):
        if not ok:
            set_status(str(payload), _RED)
            return
        if not isinstance(payload, dict):
            set_status('Пусто', _RED)
            return
        current_mail[0] = payload
        hdr = f'От: {payload.get("from", "")}\nТема: {payload.get("subject", "")}\n\n'
        body_txt.insert('1.0', hdr + (payload.get('body') or ''))
        subj = payload.get('subject') or ''
        if not subj.lower().startswith('re:'):
            subj = f'Re: {subj}'
        reply_txt.insert('1.0', '')
        set_status('Письмо загружено', _GREEN)
    def do_send():
        m = current_mail[0]
        if not m:
            set_status('Выберите письмо', _AMBER)
            return
        text = reply_txt.get('1.0', 'end-1c').strip()
        if not text and not attach_paths:
            set_status('Введите текст ответа или добавьте вложения', _AMBER)
            return
        total_b = sum(p.stat().st_size for p in attach_paths if p.is_file())
        if total_b > 26 * 1024 * 1024:
            set_status('Вложения слишком большие (> ~25 МБ). Уменьшите размер или вставьте ссылку в текст.', _RED)
            return
        subj = m.get('subject') or ''
        if not subj.lower().startswith('re:'):
            subj = f'Re: {subj}'
        to_addr = m.get('reply_to') or ''
        if not to_addr:
            set_status('Некому отвечать', _RED)
            return
        set_status('Отправка…', _AMBER)
        paths_copy = [Path(x) for x in attach_paths]
        def work():
            ok, msg = send_reply(
                to_addr,
                subj,
                text,
                in_reply_to=m.get('message_id') or '',
                references=m.get('references') or '',
                attachments=paths_copy,
            )
            def _done():
                set_status(msg, _GREEN if ok else _RED)
                if ok:
                    attach_paths.clear()
                    _refresh_attach_ui()
                    reply_txt.delete('1.0', 'end')
            win.after(0, _done)
        threading.Thread(target=work, daemon=True).start()
    def do_delete():
        uid = (current_uid[0] or '').strip()
        if not uid:
            set_status('Сначала выберите письмо в списке слева', _AMBER)
            return
        def _confirmed():
            set_status('Удаление…', _AMBER)
            def work():
                ok, msg = delete_message_by_uid(uid)
                def _done():
                    set_status(msg, _GREEN if ok else _RED)
                    if ok:
                        body_txt.delete('1.0', 'end')
                        reply_txt.delete('1.0', 'end')
                        attach_paths.clear()
                        _refresh_attach_ui()
                        current_mail[0] = None
                        current_uid[0] = None
                        load_list()
                win.after(0, _done)
            threading.Thread(target=work, daemon=True).start()
        _show_confirm_hud(
            hud, win, 'Удалить письмо?',
            'Письмо будет удалено с сервера (IMAP) безвозвратно. Продолжить?',
            _confirmed, danger=True
        )
    btn_row = tk.Frame(right_inner, bg=_BG)
    btn_row.grid(row=2, column=0, sticky='ew', pady=(12, 16))
    _btn_reply_center = tk.Frame(btn_row, bg=_BG)
    _btn_reply_center.pack(anchor='center')
    ctk.CTkButton(
        _btn_reply_center,
        text='ОТПРАВИТЬ ОТВЕТ',
        width=220,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(11, hud.zoom_factor), 'bold'),
        fg_color=_blend(_GREEN, 0.25),
        hover_color=_blend(_GREEN, 0.45),
        text_color=_GREEN,
        command=do_send,
    ).pack(side='left', padx=8)
    ctk.CTkButton(
        _btn_reply_center,
        text='УДАЛИТЬ ПИСЬМО',
        width=200,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        fg_color=_blend(_RED, 0.15),
        hover_color=_blend(_RED, 0.3),
        text_color=_RED,
        command=do_delete,
    ).pack(side='left', padx=8)
    ctk.CTkButton(
        _btn_reply_center,
        text='ОБНОВИТЬ СПИСОК',
        width=200,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        fg_color=_blend(_CYAN, 0.12),
        hover_color=_blend(_CYAN, 0.22),
        text_color=_CYAN,
        command=load_list,
    ).pack(side='left', padx=8)
    body_txt.insert('1.0', 'Выберите письмо в списке слева — текст отобразится здесь.')
    body_txt.tag_add('hint', '1.0', 'end')
    body_txt.tag_configure('hint', foreground=_DIM)
    win.after(80, lambda: reply_txt.focus_set())
    load_list()
