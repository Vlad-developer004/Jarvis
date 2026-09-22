"""Review dialog for deep-cleanup orphan candidates: checkbox list, nothing
is pre-selected — the user picks what to delete, deletion happens only on
confirm."""
from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from core import i18n
from ui.hud_style import JStyle
from ui.hud_constants import _BG, _PANEL, _CYAN, _AMBER, _RED, _WHITE, _DIM
from ui.hud_utils import _blend
from ui.dialogs.manage_dlg import _base_win, _scrollable
from ui.hud_widgets import make_dlg_btn
from ui.dialogs.git_stage_dlg import _Checkbox


def _fmt_size(size_bytes: int) -> str:
    mb = size_bytes / (1024 * 1024)
    if mb >= 1024:
        return f'{mb / 1024:.2f} GB'
    return f'{mb:.1f} MB'


def open_cleanup_review(hud, candidates: list[dict], on_confirm) -> None:
    """candidates: list of {'path','name','size_bytes','age_days'}.
    on_confirm(paths: list[str]) is called with the paths the user left checked."""
    win = _base_win(hud, i18n.tr('cleanup.review.win_title'), w=hud._px(1040), h=hud._px(800))
    inner = _scrollable(win, hud, _AMBER)

    hdr = tk.Frame(inner, bg=_BG)
    hdr.pack(fill='x', padx=hud._px(24), pady=(hud._px(20), hud._px(6)))
    tk.Label(hdr, text='⚠', bg=_BG, fg=_AMBER,
             font=(hud._F, hud._fs(24))).pack(side='left', padx=(0, hud._px(14)))
    tk.Label(hdr, text=i18n.tr('cleanup.review.title'), bg=_BG, fg=_AMBER,
             font=(hud._F, hud._fs(17), 'bold')).pack(side='left')

    total_size = sum(c['size_bytes'] for c in candidates)
    sub_text = i18n.tr('cleanup.review.subtitle').format(count=len(candidates), size=_fmt_size(total_size))
    sub = tk.Label(inner, text=sub_text,
                    bg=_BG, fg=_DIM, font=(hud._F, hud._fs(11)), justify='left', anchor='w')
    sub.pack(fill='x', padx=hud._px(24), pady=(0, hud._px(10)))

    checks: dict[str, tk.BooleanVar] = {}
    selected_lbl = tk.Label(inner, text='', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(12), 'bold'))

    def _refresh_selected():
        n = sum(1 for v in checks.values() if v.get())
        size = sum(c['size_bytes'] for c in candidates if checks[c['path']].get())
        selected_lbl.configure(text=i18n.tr('cleanup.review.selected').format(count=n, size=_fmt_size(size)))

    bulk_row = tk.Frame(inner, bg=_BG)
    if candidates:
        bulk_row.pack(fill='x', padx=hud._px(24), pady=(0, hud._px(10)))

    def _set_all(value: bool):
        for v in checks.values():
            v.set(value)
        _refresh_selected()

    make_dlg_btn(hud, bulk_row, i18n.tr('cleanup.review.select_all'), '☑', _CYAN,
                 lambda: _set_all(True), height=hud._px(36), width=hud._px(170)).pack(side='left', padx=(0, hud._px(10)))
    make_dlg_btn(hud, bulk_row, i18n.tr('cleanup.review.select_none'), '☐', _DIM,
                 lambda: _set_all(False), height=hud._px(36), width=hud._px(170)).pack(side='left')

    cards_frame = tk.Frame(inner, bg=_BG)
    cards_frame.pack(fill='x', padx=hud._px(24), pady=(0, hud._px(16)))

    if not candidates:
        tk.Label(cards_frame, text=i18n.tr('cleanup.review.none_found'), bg=_BG, fg=_DIM,
                 font=(hud._F, hud._fs(12))).pack(pady=hud._px(20))
    else:
        for c in candidates:
            var = tk.BooleanVar(value=False)
            checks[c['path']] = var

            card = ctk.CTkFrame(cards_frame, fg_color=_PANEL, border_color=_blend(_AMBER, 0.25),
                                 border_width=1, corner_radius=JStyle.RAD_PANEL)
            card.pack(fill='x', pady=hud._px(5))

            cb = _Checkbox(card, var, _PANEL, on_toggle=_refresh_selected,
                            size=hud._px(24), accent=_AMBER)
            cb.pack(side='left', padx=(hud._px(16), hud._px(12)), pady=hud._px(16))

            body = tk.Frame(card, bg=_PANEL)
            body.pack(side='left', fill='both', expand=True, pady=hud._px(12))
            tk.Label(body, text=c['name'], bg=_PANEL, fg=_WHITE,
                     font=(hud._F, hud._fs(12), 'bold'), anchor='w').pack(fill='x')
            tk.Label(body, text=c['path'], bg=_PANEL, fg=_DIM,
                     font=(hud._F, hud._fs(9)), anchor='w').pack(fill='x')
            meta_text = i18n.tr('cleanup.review.item_meta').format(size=_fmt_size(c['size_bytes']), age=c['age_days'])
            tk.Label(body, text=meta_text,
                     bg=_PANEL, fg=_blend(_AMBER, 0.65), font=(hud._F, hud._fs(9), 'bold'), anchor='w').pack(fill='x', pady=(hud._px(3), 0))

    selected_lbl.pack(fill='x', padx=hud._px(24), pady=(0, hud._px(12)))
    _refresh_selected()

    btn_row = tk.Frame(inner, bg=_BG)
    btn_row.pack(fill='x', padx=hud._px(24), pady=(0, hud._px(22)))

    def _confirm():
        paths = [p for p, v in checks.items() if v.get()]
        win.destroy()
        if paths:
            on_confirm(paths)

    make_dlg_btn(hud, btn_row, i18n.tr('buttons.cancel'), '✕', _DIM, win.destroy,
                 height=hud._px(52), width=hud._px(160)).pack(side='left')
    make_dlg_btn(hud, btn_row, i18n.tr('cleanup.review.delete_btn'), '🗑', _RED, _confirm,
                 height=hud._px(52), width=hud._px(260)).pack(side='right')

    win.lift()
    win.focus_force()
    if hasattr(win, '_recenter'):
        win._recenter()
