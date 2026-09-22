"""Mail client (inbox viewer) dialog. Split out of the old mail_dlg.py
purely for file size; no behavior change. See mail_compose_dlg.py for the
compose window this opens when the user hits "new message".
"""
from __future__ import annotations
import re
from core import i18n
from ui.hud_style import JStyle
import threading
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _SEP, _CYAN, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _get_work_area
from .mail_shared import _sf, _show_confirm_hud
from .mail_compose_dlg import open_compose_dialog
from .mail_reply_panel import build_reply_panel

def _clean_email_body(raw_body: str) -> str:
    """Clean up and format raw email body, shortening massive tracking URLs."""
    if not raw_body:
        return ''
    def _url_repl(match):
        url = match.group(0)
        if len(url) > 75:
            from urllib.parse import urlparse
            try:
                parsed = urlparse(url)
                netloc = parsed.netloc or 'link'
                return f'{url[:55]}… [{netloc}]'
            except Exception:
                return f'{url[:65]}…'
        return url
    cleaned = re.sub(r'https?://[^\s<">]+', _url_repl, raw_body)
    return cleaned.strip()

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
    win.configure(bg=_BG)  # type: ignore[call-arg]
    win.overrideredirect(True)
    _apply_window_icon(win, hud)
    l, t, r, b = _get_work_area(hud)
    sw, sh = r - l, b - t
    win.geometry(f'{sw}x{sh}+{l}+{t}')
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
    status_bg = tk.Frame(top, bg=_blend(_CYAN, 0.08), highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
    status_bg.pack(side='right', padx=(20, 10))
    status = tk.Label(
        status_bg,
        text='',
        bg=_blend(_CYAN, 0.08),
        fg=_DIM,
        font=(hud._F, _sf(9, hud.zoom_factor), 'bold'),
        padx=10,
        pady=4,
        anchor='e'
    )
    status.pack(fill='both', expand=True)
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
    # Logical width of the sidebar
    left = tk.Frame(pan, bg=_BG, width=hud._px(340))
    left.pack_propagate(False)
    right = tk.Frame(pan, bg=_BG)
    pan.add(left, width=hud._px(340), minsize=int(280 * hud.zoom_factor))
    pan.add(right, minsize=int(400 * hud.zoom_factor))
    _CARD_IDLE = _blend(_CYAN, 0.05)
    _CARD_HOVER = _blend(_CYAN, 0.14)
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
        card.configure(bg=bg_c, highlightbackground=brd_c)  # type: ignore[call-arg]
        for ch in card.winfo_children():
            if isinstance(ch, tk.Frame) and ch.cget('width') == 4:
                ch.configure(bg=strip_c)  # type: ignore[call-arg]
            elif isinstance(ch, tk.Frame):
                ch.configure(bg=bg_c)  # type: ignore[call-arg]
                for sub in ch.winfo_children():
                    if isinstance(sub, tk.Label) or isinstance(sub, tk.Frame):
                        sub.configure(bg=bg_c)  # type: ignore[call-arg]
                        if isinstance(sub, tk.Frame):
                            for ssub in sub.winfo_children():
                                if isinstance(ssub, tk.Label):
                                    ssub.configure(bg=bg_c)  # type: ignore[call-arg]
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
        reply_panel.clear()
        current_mail[0] = None
        def work():
            ok, payload = fetch_message_body(uid or '')
            win.after(0, lambda: _apply_body(ok, payload))
        threading.Thread(target=work, daemon=True).start()
    def _build_card(idx: int, row: dict):
        subj = row.get('subject') or '(без темы)'
        sender_raw = row.get('from') or ''
        date_s = row.get('date') or ''
        date_short = date_s[:16] if len(date_s) > 16 else date_s

        # Clean up sender display name & extract avatar initial
        clean_sender = sender_raw.split('<')[0].strip(' "\'') or sender_raw
        if len(clean_sender) > 36:
            clean_sender = clean_sender[:34] + '…'
        initial = (clean_sender[0].upper() if clean_sender and clean_sender[0].isalnum() else '✉')

        card = tk.Frame(
            list_inner, bg=_CARD_IDLE,
            highlightthickness=1, highlightbackground=_blend(_CYAN, 0.12),
            cursor='hand2',
        )
        card.pack(fill='x', padx=(8, hud._px(10)), pady=(0, 6))

        # Avatar initial badge (centered using place anchor)
        av_fr = tk.Frame(card, bg=_blend(_CYAN, 0.15), width=hud._px(30), height=hud._px(30))
        av_fr.pack(side='left', padx=(8, 4), pady=8)
        av_fr.pack_propagate(False)
        av_lbl = tk.Label(
            av_fr, text=initial, bg=_blend(_CYAN, 0.15), fg=_CYAN,
            font=(hud._F, _sf(11, hud.zoom_factor), 'bold')
        )
        av_lbl.place(relx=0.5, rely=0.5, anchor='center')

        body = tk.Frame(card, bg=_CARD_IDLE)
        body.pack(side='left', fill='both', expand=True, padx=(6, 6), pady=6)
        subj_l = tk.Label(
            body, text=subj, bg=_CARD_IDLE, fg=_WHITE,
            font=(hud._F, _sf(10, hud.zoom_factor), 'bold'), anchor='w', justify='left',
            wraplength=hud._px(240)
        )
        subj_l.pack(fill='x', pady=(0, 2))
        sender_l = tk.Label(
            body, text=clean_sender, bg=_CARD_IDLE, fg=_DIM,
            font=(hud._F, _sf(9, hud.zoom_factor)), anchor='w', justify='left',
            wraplength=hud._px(240)
        )
        sender_l.pack(fill='x')
        if date_short:
            date_l = tk.Label(
                body, text=date_short, bg=_CARD_IDLE, fg=_blend(_CYAN, 0.4),
                font=(hud._F, _sf(8, hud.zoom_factor)), anchor='w',
            )
            date_l.pack(fill='x')
            date_l.bind('<Button-1>', lambda e, i=idx: _select_card(i))
            date_l.bind('<MouseWheel>', _on_mousewheel)
        def _enter(e, c=card, i=idx):
            if selected_idx[0] != i:
                c.configure(bg=_CARD_HOVER, highlightbackground=_blend(_CYAN, 0.35))  # type: ignore[call-arg]
                for w in c.winfo_children():
                    if isinstance(w, tk.Frame) and w != av_fr:
                        w.configure(bg=_CARD_HOVER)  # type: ignore[call-arg]
                        for ch in w.winfo_children():
                            if isinstance(ch, tk.Label):
                                ch.configure(bg=_CARD_HOVER)  # type: ignore[call-arg]
        def _leave(e, c=card, i=idx):
            if selected_idx[0] != i:
                c.configure(bg=_CARD_IDLE, highlightbackground=_blend(_CYAN, 0.12))  # type: ignore[call-arg]
                for w in c.winfo_children():
                    if isinstance(w, tk.Frame) and w != av_fr:
                        w.configure(bg=_CARD_IDLE)  # type: ignore[call-arg]
                        for ch in w.winfo_children():
                            if isinstance(ch, tk.Label):
                                ch.configure(bg=_CARD_IDLE)  # type: ignore[call-arg]
        for widget in (card, body, subj_l, sender_l, av_fr, av_lbl):
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
    right_inner.grid_rowconfigure(0, weight=0)  # Header card
    right_inner.grid_rowconfigure(1, weight=2, minsize=hud._px(160))  # Body text
    right_inner.grid_rowconfigure(2, weight=3, minsize=hud._px(220))  # Reply card
    right_inner.grid_rowconfigure(3, weight=0)  # Bottom button row

    # --- Structured Header Card for Selected Message ---
    hdr_card = tk.Frame(right_inner, bg=_PANEL, highlightbackground=_blend(_CYAN, 0.22), highlightthickness=1)
    hdr_card.grid(row=0, column=0, sticky='ew', pady=(0, 8))
    
    hdr_top = tk.Frame(hdr_card, bg=_PANEL)
    hdr_top.pack(fill='x', padx=14, pady=(10, 4))
    hdr_subj_lbl = tk.Label(
        hdr_top, text='◈  Выберите письмо из списка слева', bg=_PANEL, fg=_CYAN,
        font=(hud._F, _sf(11, hud.zoom_factor), 'bold'), anchor='w', justify='left',
        wraplength=hud._px(550)
    )
    hdr_subj_lbl.pack(side='left', fill='x', expand=True)

    hdr_meta_fr = tk.Frame(hdr_card, bg=_PANEL)
    hdr_meta_fr.pack(fill='x', padx=14, pady=(0, 8))
    hdr_from_lbl = tk.Label(
        hdr_meta_fr, text='', bg=_PANEL, fg=_CYAN,
        font=(hud._F, _sf(9, hud.zoom_factor), 'bold'), anchor='w'
    )
    hdr_from_lbl.pack(side='left')
    hdr_date_lbl = tk.Label(
        hdr_meta_fr, text='', bg=_PANEL, fg=_DIM,
        font=(hud._F, _sf(8, hud.zoom_factor)), anchor='e'
    )
    hdr_date_lbl.pack(side='right')

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
    body_card.grid(row=1, column=0, sticky='nsew', pady=(0, 8))
    tk.Label(body_card, text='Текст письма', bg=_BG, fg=_CYAN, font=(hud._F, _sf(10, hud.zoom_factor), 'bold')).pack(anchor='w', pady=(0, 4))
    body_wrap = tk.Frame(body_card, bg=_card_bg, highlightbackground=_blend(_CYAN, 0.3), highlightthickness=1)
    body_wrap.pack(fill='both', expand=True)
    body_txt = tk.Text(body_wrap, height=14, **_txt_common)
    body_txt.pack(fill='both', expand=True)

    reply_card = tk.Frame(right_inner, bg=_BG)
    reply_card.grid(row=2, column=0, sticky='nsew', pady=(0, 8))
    btn_row = tk.Frame(right_inner, bg=_BG)
    btn_row.grid(row=3, column=0, sticky='ew', pady=(8, 12))
    _btn_reply_center = tk.Frame(btn_row, bg=_BG)
    _btn_reply_center.pack(anchor='center')
    reply_panel = build_reply_panel(
        hud, win, reply_card, _btn_reply_center,
        send_reply=send_reply, current_mail=current_mail, set_status=lambda t, c=_DIM: set_status(t, c), W=W,
    )
    reply_txt = reply_panel.reply_txt
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

        # Update dedicated Header Card
        subj = payload.get("subject") or '(без темы)'
        sender = payload.get("from") or ''
        date_s = payload.get("date") or ''

        hdr_subj_lbl.configure(text=subj, fg=_WHITE)
        hdr_from_lbl.configure(text=f'От: {sender}')
        hdr_date_lbl.configure(text=date_s[:24] if date_s else '')

        # Clean body text (shorten long tracking URLs)
        clean_text = _clean_email_body(payload.get('body') or '')
        body_txt.delete('1.0', 'end')
        body_txt.insert('1.0', clean_text)

        reply_panel.set_quote(payload)
        set_status('Письмо загружено', _GREEN)
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
                        hdr_subj_lbl.configure(text='◈  Выберите письмо из списка слева', fg=_CYAN)
                        hdr_from_lbl.configure(text='')
                        hdr_date_lbl.configure(text='')
                        body_txt.delete('1.0', 'end')
                        reply_panel.clear()
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
    ctk.CTkButton(
        _btn_reply_center,
        text='🗑  УДАЛИТЬ ПИСЬМО',
        width=190,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        fg_color=_blend(_RED, 0.15),
        hover_color=_blend(_RED, 0.3),
        text_color=_RED,
        command=do_delete,
    ).pack(side='left', padx=6)
    ctk.CTkButton(
        _btn_reply_center,
        text='🔄  ОБНОВИТЬ СПИСОК',
        width=190,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
        fg_color=_blend(_CYAN, 0.12),
        hover_color=_blend(_CYAN, 0.22),
        text_color=_CYAN,
        command=load_list,
    ).pack(side='left', padx=6)
    body_txt.insert('1.0', 'Выберите письмо в списке слева — текст отобразится здесь.')
    body_txt.tag_add('hint', '1.0', 'end')
    body_txt.tag_configure('hint', foreground=_DIM)
    win.after(80, lambda: reply_txt.focus_set())
    load_list()

