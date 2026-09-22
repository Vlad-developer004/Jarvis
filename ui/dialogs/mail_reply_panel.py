"""Reply panel (attachments + reply textbox + send button) for the mail
client dialog. Split out of mail_client_dlg.py purely for file size —
behavior unchanged except where noted in CLAUDE.md-approved UI fixes:
bigger reply textbox, and quoting the original message on select.
"""
from __future__ import annotations
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from ui.hud_style import JStyle
from ..hud_constants import _BG, _CYAN, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _place_dialog
from .extensions_common import _bind_ctk_entry_clipboard
from .mail_shared import _sf, _bind_text_clipboard

_QUOTE_MAX_LINES = 25
_QUOTE_MAX_CHARS = 1200

def _quote_block(payload: dict) -> str:
    date_s = (payload.get('date') or '').strip()
    frm = (payload.get('from') or '').strip()
    body = (payload.get('body') or '').strip()
    lines = body.splitlines()[:_QUOTE_MAX_LINES]
    quoted = '\n'.join(f'> {ln}' for ln in lines)
    if len(quoted) > _QUOTE_MAX_CHARS:
        quoted = quoted[:_QUOTE_MAX_CHARS].rstrip() + '…'
    elif len(body.splitlines()) > _QUOTE_MAX_LINES:
        quoted += '\n> …'
    header = f'{date_s}, {frm} написал(а):' if (date_s or frm) else 'Исходное письмо:'
    return f'\n\n{header}\n{quoted}\n'

class ReplyPanel:
    def __init__(self, reply_txt: ctk.CTkTextbox, attach_paths: list[Path], refresh_attach_ui):
        self.reply_txt = reply_txt
        self._attach_paths = attach_paths
        self._refresh_attach_ui = refresh_attach_ui

    def clear(self):
        self.reply_txt.delete('1.0', 'end')
        self._attach_paths.clear()
        self._refresh_attach_ui()

    def set_quote(self, payload: dict):
        self.reply_txt.delete('1.0', 'end')
        self.reply_txt.insert('1.0', _quote_block(payload))
        try:
            self.reply_txt._textbox.mark_set('insert', '1.0')
        except Exception:
            pass
        self.reply_txt.focus_set()

def build_reply_panel(hud, win, reply_card: tk.Frame, send_row: tk.Frame, *, send_reply, current_mail: list, set_status, W: int) -> ReplyPanel:
    """Builds attachments + reply textbox inside `reply_card`, and adds the
    send button into `send_row`. `current_mail` is the caller's mutable
    single-element list (current_mail[0] holds the selected message dict)."""
    card_bg = _BG
    attach_paths: list[Path] = []
    attach_wrap = tk.Frame(reply_card, bg=card_bg, highlightbackground=_blend(_GREEN, 0.22), highlightthickness=1)
    attach_inner = tk.Frame(attach_wrap, bg=card_bg)

    def _refresh_attach_ui():
        for w in attach_inner.winfo_children():
            w.destroy()
        if not attach_paths:
            tk.Label(
                attach_inner,
                text='Нет вложений — кнопки «Файл», «Фото», «Видео»',
                bg=card_bg,
                fg=_DIM,
                font=(hud._F, _sf(9, hud.zoom_factor)),
            ).pack(anchor='w')
            return
        for p in attach_paths:
            row = tk.Frame(attach_inner, bg=card_bg)
            row.pack(fill='x', pady=2)
            tk.Label(
                row,
                text=p.name,
                bg=card_bg,
                fg=_TEXT,
                font=(hud._F, _sf(9, hud.zoom_factor), 'bold'),
                anchor='w',
            ).pack(side='left', fill='x', expand=True)
            ctk.CTkButton(
                row,
                text='✕',
                width=28,
                height=24,
                font=(hud._F, _sf(10), 'bold'),
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
        paths = filedialog.askopenfilenames(parent=win, title='Файлы для вложения', filetypes=[('Все файлы', '*.*')])
        _add_paths(paths)

    def _pick_images():
        paths = filedialog.askopenfilenames(
            parent=win, title='Фото',
            filetypes=[('Изображения', '*.png *.jpg *.jpeg *.gif *.webp *.bmp'), ('Все файлы', '*.*')],
        )
        _add_paths(paths)

    def _pick_videos():
        paths = filedialog.askopenfilenames(
            parent=win, title='Видео',
            filetypes=[('Видео', '*.mp4 *.mov *.avi *.mkv *.webm *.m4v'), ('Все файлы', '*.*')],
        )
        _add_paths(paths)

    hdr = tk.Frame(reply_card, bg=_BG)
    hdr.pack(fill='x', pady=(0, 4))
    tk.Label(hdr, text='Ответ', bg=_BG, fg=_CYAN, font=(hud._F, _sf(10, hud.zoom_factor), 'bold')).pack(side='left')
    tool = tk.Frame(reply_card, bg=_BG)
    tool.pack(fill='x', pady=(0, 4))
    bt_kw = {
        'font': (hud._F, _sf(9), 'bold'),
        'height': 36,
        'fg_color': _blend(_CYAN, 0.12),
        'hover_color': _blend(_CYAN, 0.24),
        'text_color': _TEXT,
    }
    ctk.CTkButton(tool, text='📁 Файл…', width=84, command=_pick_files, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='🖼 Фото…', width=84, command=_pick_images, **bt_kw).pack(side='left', padx=(0, 6))
    ctk.CTkButton(tool, text='🎥 Видео…', width=84, command=_pick_videos, **bt_kw).pack(side='left', padx=(0, 6))

    reply_wrap = tk.Frame(reply_card, bg=_BG)
    reply_txt = ctk.CTkTextbox(
        reply_wrap,
        width=max(400, W - 340),
        font=(hud._F, _sf(11)),
        fg_color=card_bg,
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
        dlg.configure(bg=_BG)  # type: ignore[call-arg]
        dlg.transient(win)
        dlg.grab_set()
        _set_dark_title_bar(dlg)
        _apply_window_icon(dlg, hud)
        _place_dialog(dlg, hud, 460, 132, grab=False)
        dlg.minsize(380, 110)
        tk.Label(
            dlg,
            text='Вставьте URL — он будет добавлен в текст ответа.',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, _sf(10, hud.zoom_factor), 'bold'),
            wraplength=460 - 24,
            justify='left',
        ).pack(anchor='w', padx=12, pady=(12, 6))
        ent = ctk.CTkEntry(
            dlg,
            width=460 - 24,
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
            row, text='ВСТАВИТЬ', width=160, height=JStyle.H_LARGE,
            font=(hud._F, _sf(11), 'bold'), fg_color=_blend(_GREEN, 0.25), command=_ok,
        ).pack(side='left', padx=(0, 8))
        ctk.CTkButton(
            row, text='Отмена', width=hud._px(120), height=hud._px(44),
            font=(hud._F, _sf(10, hud.zoom_factor)), fg_color=_blend(_CYAN, 0.1), command=_cancel,
        ).pack(side='left')
        ent.bind('<Return>', lambda e: _ok())
        ent.focus_set()

    ctk.CTkButton(tool, text='🔗 Ссылка…', width=84, command=_add_link_dialog, **bt_kw).pack(side='left', padx=(0, 6))
    attach_wrap.pack(fill='x', pady=(0, 6))
    attach_inner.pack(fill='both', padx=8, pady=(2, 6))
    reply_wrap.pack(fill='both', expand=True)
    _refresh_attach_ui()
    _bind_text_clipboard(win, reply_txt)

    def do_send():
        m = current_mail[0]
        if not m:
            set_status('Выберите письмо в списке слева', _DIM)
            return
        text = reply_txt.get('1.0', 'end-1c').strip()
        if not text and not attach_paths:
            set_status('Введите текст ответа или добавьте вложения', _AMBER)
            return
        total_b = sum(p.stat().st_size for p in attach_paths if p.is_file())
        if total_b > 26 * 1024 * 1024:
            set_status('Вложения слишком большие (> ~25 МБ).', _RED)
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
                to_addr, subj, text,
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

    ctk.CTkButton(
        send_row,
        text='✉  ОТПРАВИТЬ ОТВЕТ',
        width=210,
        height=JStyle.H_LARGE,
        font=(hud._F, _sf(11, hud.zoom_factor), 'bold'),
        fg_color=_blend(_GREEN, 0.25),
        hover_color=_blend(_GREEN, 0.45),
        text_color=_GREEN,
        command=do_send,
    ).pack(side='left', padx=6)

    return ReplyPanel(reply_txt, attach_paths, _refresh_attach_ui)
