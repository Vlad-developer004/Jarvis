"""
Live countdown widgets for the HUD right panel (timer + reminder).
Colors are always sourced from hud_constants so they follow the active theme.
"""
from __future__ import annotations
import tkinter as tk
import time


def _fmt_hms(sec: int) -> str:
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f'{h:02d}:{m:02d}:{s:02d}'
    return f'{m:02d}:{s:02d}'


# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────

def build_alert_section(hud, parent) -> None:
    """
    Insert an always-present (but initially empty) container at the top of
    the right-panel scrollable frame.  Timer and reminder cards live inside.
    """
    from .hud_constants import _PANEL, _BRD, _AMBER, _CYAN, _TEXT, _DIM, _BG
    from ui.hud_style import JStyle

    F = hud._F

    hud._alerts_container = tk.Frame(parent, bg=_PANEL)
    hud._alerts_container.pack(fill='x')

    # ── Timer card ────────────────────────────────────────────────────────
    hud._timer_card = tk.Frame(hud._alerts_container, bg=_PANEL)

    tk.Frame(hud._timer_card, bg=_AMBER, height=2).pack(fill='x')
    _ti = tk.Frame(hud._timer_card, bg=_PANEL)
    _ti.pack(fill='x', padx=14, pady=(8, 10))

    _th = tk.Frame(_ti, bg=_PANEL)
    _th.pack(fill='x')
    tk.Label(_th, text='⏱', font=(F, JStyle.TEXT_SMALL), bg=_PANEL, fg=_AMBER).pack(side='left')
    hud._timer_card_name = tk.Label(_th, text='ТАЙМЕР', font=(F, JStyle.TEXT_SMALL, 'bold'), bg=_PANEL, fg=_TEXT)
    hud._timer_card_name.pack(side='left', padx=(6, 0))

    hud._timer_card_time = tk.Label(_ti, text='00:00', font=(F, hud._fs(26), 'bold'), bg=_PANEL, fg=_AMBER)
    hud._timer_card_time.pack(fill='x', pady=(4, 2))

    _bar_bg = tk.Frame(_ti, bg=_BRD, height=3)
    _bar_bg.pack(fill='x', pady=(0, 6))
    _bar_bg.pack_propagate(False)
    hud._timer_card_bar = tk.Frame(_bar_bg, bg=_AMBER, height=3)
    hud._timer_card_bar.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

    _cxl = tk.Label(_ti, text='[ ОТМЕНА ]', font=(F, JStyle.TEXT_TINY, 'bold'),
                    bg=_PANEL, fg=_DIM, cursor='hand2')
    _cxl.pack(anchor='e')
    _cxl.bind('<Button-1>', lambda e: _cancel_timer_from_hud(hud))

    tk.Frame(hud._alerts_container, bg=_BRD, height=1).pack(fill='x', padx=14)

    hud._timer_card.pack_forget()
    hud._timer_total_sec = 1

    # ── Reminder card ─────────────────────────────────────────────────────
    hud._reminder_card = tk.Frame(hud._alerts_container, bg=_PANEL)

    tk.Frame(hud._reminder_card, bg=_CYAN, height=2).pack(fill='x')
    _ri = tk.Frame(hud._reminder_card, bg=_PANEL)
    _ri.pack(fill='x', padx=14, pady=(8, 10))

    _rh = tk.Frame(_ri, bg=_PANEL)
    _rh.pack(fill='x')
    tk.Label(_rh, text='◎', font=(F, JStyle.TEXT_SMALL), bg=_PANEL, fg=_CYAN).pack(side='left')
    tk.Label(_rh, text='НАПОМИНАНИЕ', font=(F, JStyle.TEXT_SMALL, 'bold'),
             bg=_PANEL, fg=_TEXT).pack(side='left', padx=(6, 0))

    hud._reminder_card_msg = tk.Label(_ri, text='', font=(F, JStyle.TEXT_TINY, 'bold'),
                                       bg=_PANEL, fg=_CYAN, anchor='w', wraplength=180, justify='left')
    hud._reminder_card_msg.pack(fill='x', pady=(4, 2))

    hud._reminder_card_time = tk.Label(_ri, text='', font=(F, JStyle.TEXT_BODY, 'bold'),
                                        bg=_PANEL, fg=_TEXT)
    hud._reminder_card_time.pack(fill='x')

    tk.Frame(hud._alerts_container, bg=_BRD, height=1).pack(fill='x', padx=14)

    hud._reminder_card.pack_forget()
    hud._reminder_total_sec = 1
    hud._reminder_start_mono = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Timer widget public API
# ─────────────────────────────────────────────────────────────────────────────

def show_timer_widget(hud, total_sec: int, label: str) -> None:
    if not hasattr(hud, '_timer_card') or not hud._timer_card.winfo_exists():
        return
    hud._timer_total_sec = max(1, total_sec)
    name = f'ТАЙМЕР  —  {label.upper()}' if label else 'ТАЙМЕР'
    hud._timer_card_name.configure(text=name)
    hud._timer_card_time.configure(text=_fmt_hms(total_sec))
    hud._timer_card_bar.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
    hud._timer_card.pack(fill='x')
    # Delay first tick so pack() has time to map the widget
    hud.root.after(300, lambda: _timer_tick(hud))


def hide_timer_widget(hud) -> None:
    if not hasattr(hud, '_timer_card'):
        return
    try:
        hud._timer_card.pack_forget()
    except Exception:
        pass
    try:
        if hasattr(hud, '_bot_timer_lbl') and hud._bot_timer_lbl.winfo_exists():
            hud._bot_timer_lbl.configure(text='')
    except Exception:
        pass


def update_timer_total(hud, new_total_sec: int) -> None:
    """Called when add_time() extends the timer."""
    if hasattr(hud, '_timer_total_sec'):
        hud._timer_total_sec = max(1, new_total_sec)


# ─────────────────────────────────────────────────────────────────────────────
# Reminder widget public API
# ─────────────────────────────────────────────────────────────────────────────

def show_reminder_widget(hud, total_sec: int, message: str) -> None:
    if not hasattr(hud, '_reminder_card') or not hud._reminder_card.winfo_exists():
        return
    hud._reminder_total_sec = max(1, total_sec)
    hud._reminder_start_mono = time.monotonic()
    short = message if len(message) <= 38 else message[:35] + '...'
    hud._reminder_card_msg.configure(text=short.upper())
    hud._reminder_card_time.configure(text=_fmt_hms(total_sec))
    hud._reminder_card.pack(fill='x')
    hud.root.after(300, lambda: _reminder_tick(hud))


def hide_reminder_widget(hud) -> None:
    if not hasattr(hud, '_reminder_card'):
        return
    try:
        hud._reminder_card.pack_forget()
    except Exception:
        pass
    try:
        if hasattr(hud, '_bot_timer_lbl') and hud._bot_timer_lbl.winfo_exists():
            hud._bot_timer_lbl.configure(text='')
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Tick loops (run in UI thread via root.after)
# ─────────────────────────────────────────────────────────────────────────────

def _timer_tick(hud) -> None:
    try:
        if not hud._timer_card.winfo_exists() or not hud._timer_card.winfo_ismapped():
            return
    except Exception:
        return

    from actions.game_timer import get_status
    remaining = get_status()
    if remaining is None:
        hide_timer_widget(hud)
        return

    frac = remaining / hud._timer_total_sec
    time_str = _fmt_hms(remaining)
    hud._timer_card_time.configure(text=time_str)
    hud._timer_card_bar.place(relx=0, rely=0, relwidth=max(0.0, min(1.0, frac)), relheight=1.0)

    # Bottom bar compact display
    try:
        if hasattr(hud, '_bot_timer_lbl') and hud._bot_timer_lbl.winfo_exists():
            hud._bot_timer_lbl.configure(text=f'⏱  {time_str}')
    except Exception:
        pass

    hud.root.after(1000, lambda: _timer_tick(hud))


def _reminder_tick(hud) -> None:
    try:
        if not hud._reminder_card.winfo_exists() or not hud._reminder_card.winfo_ismapped():
            # Card hidden (cancelled) — clear bot label and stop
            try:
                if hasattr(hud, '_bot_timer_lbl') and hud._bot_timer_lbl.winfo_exists():
                    hud._bot_timer_lbl.configure(text='')
            except Exception:
                pass
            return
    except Exception:
        return

    elapsed = time.monotonic() - hud._reminder_start_mono
    remaining = max(0, hud._reminder_total_sec - int(elapsed))
    time_str = _fmt_hms(remaining)
    hud._reminder_card_time.configure(text=time_str)

    # Bottom bar compact display
    try:
        if hasattr(hud, '_bot_timer_lbl') and hud._bot_timer_lbl.winfo_exists():
            hud._bot_timer_lbl.configure(text=f'◎  {time_str}')
    except Exception:
        pass

    if remaining > 0:
        hud.root.after(1000, lambda: _reminder_tick(hud))
    else:
        hide_reminder_widget(hud)


# ─────────────────────────────────────────────────────────────────────────────
# Timer completion popup
# ─────────────────────────────────────────────────────────────────────────────

def show_timer_done_popup(label: str, master=None) -> None:
    """Called from game_timer thread via hud_queue when countdown hits zero."""
    import math
    import tkinter as tk
    import customtkinter as ctk
    from ui.hud_constants import _BG, _PANEL, _AMBER, _TEXT, _DIM, _WHITE, _BRD, _GRID
    from ui.hud_utils import _center_window, _apply_window_icon, _set_dark_title_bar, _blend
    from ui.hud_themes import get_current_theme_name
    ctk.set_appearance_mode('Light' if get_current_theme_name() == 'light' else 'Dark')

    px = (lambda v: v) if not (master and hasattr(master, '_px')) else master._px
    F = 'Consolas'

    root = tk.Toplevel(master) if master else tk.Tk()
    W, H = px(720), px(380)
    root.withdraw()
    _center_window(root, W, H)
    root.resizable(False, False)
    root.configure(bg=_BG)
    _set_dark_title_bar(root)
    root.after(150, lambda: _set_dark_title_bar(root))
    _apply_window_icon(root, master)
    root.title('ТАЙМЕР — J.A.R.V.I.S.')

    def _close():
        try:
            from ui.voice_prompt_bridge import unregister_voice_prompt
            unregister_voice_prompt(root)
        except Exception:
            pass
        root.destroy()

    # ── Single canvas covers entire window ───────────────────────────────
    c = tk.Canvas(root, bg=_BG, highlightthickness=0)
    c.pack(fill='both', expand=True)

    # Button embedded in canvas via create_window — no layering artifacts
    btn_frame = tk.Frame(c, bg=_BRD)
    btn_inner = tk.Frame(btn_frame, bg=_BG, padx=px(18), pady=px(7))
    btn_inner.pack(padx=1, pady=1)
    from core.responses import spk
    from core.i18n import get_language as _lang
    _L = _lang()
    btn_lbl = tk.Label(btn_inner, text=spk('timer.btn_close'), bg=_BG, fg=_DIM,
                       font=(F, px(12), 'bold'), cursor='hand2')
    btn_lbl.pack()
    for w in (btn_frame, btn_inner, btn_lbl):
        w.bind('<Button-1>', lambda e: _close())
        w.bind('<Enter>', lambda e: btn_lbl.configure(fg=_TEXT))
        w.bind('<Leave>', lambda e: btn_lbl.configure(fg=_DIM))
    _btn_win = c.create_window(W // 2, H - px(30), window=btn_frame, anchor='center')

    def _draw(evt=None):
        cw, ch = c.winfo_width() or W, c.winfo_height() or H
        c.delete('bg')

        # Move button window to correct position on resize
        c.coords(_btn_win, cw // 2, ch - px(30))

        # Grid
        step = px(44)
        for gx in range(0, cw, step):
            c.create_line(gx, 0, gx, ch, fill=_GRID, width=1, tags='bg')
        for gy in range(0, ch, step):
            c.create_line(0, gy, cw, gy, fill=_GRID, width=1, tags='bg')

        # Corner brackets (amber, 4 corners)
        cs, mg = px(22), px(16)
        for bx, by, fx, fy in ((mg, mg, 1, 1), (cw-mg, mg, -1, 1),
                                (mg, ch-mg, 1, -1), (cw-mg, ch-mg, -1, -1)):
            c.create_line(bx, by, bx+cs*fx, by, fill=_AMBER, width=2, tags='bg')
            c.create_line(bx, by, bx, by+cs*fy, fill=_AMBER, width=2, tags='bg')

        # Header background
        c.create_rectangle(0, 0, cw, px(44), fill=_PANEL, outline='', tags='bg')

        # Header text
        c.create_text(px(16), px(22), text='⏱', anchor='w',
                      fill=_AMBER, font=(F, px(13)), tags='bg')
        hdr = f'ТАЙМЕР  ·  {label.upper()}' if label else 'ТАЙМЕР'
        c.create_text(px(40), px(22), text=hdr, anchor='w',
                      fill=_TEXT, font=(F, px(11), 'bold'), tags='bg')
        c.create_text(cw - px(14), px(22), text='[ TIMER ]', anchor='e',
                      fill=_blend(_AMBER, 0.38), font=(F, px(11)), tags='bg')

        # Accent line
        c.create_rectangle(0, px(44), cw, px(46), fill=_AMBER, outline='', tags='pulse_bar')

        # Main text — центр окна
        main_text = spk('timer.done_title') if not label else spk('timer.done_ready')
        c.create_text(cw // 2, ch // 2 - px(20), text=main_text, anchor='center',
                      fill=_AMBER, font=(F, px(52), 'bold'), tags='bg')

        # Sub text — время завершения
        import time as _t
        ts = _t.strftime('%H:%M:%S')
        c.create_text(cw // 2, ch // 2 + px(22), text=f'[ {ts} ]',
                      anchor='center', fill=_blend(_AMBER, 0.42), font=(F, px(13)), tags='bg')

        # Voice hint — между контентом и кнопкой
        c.create_text(cw // 2, ch - px(62), text=spk('timer.hint_close'), anchor='center',
                      fill=_DIM, font=(F, px(12)), tags='bg')

        # Raise button window above grid lines
        c.tag_raise(_btn_win)

    c.bind('<Configure>', _draw)
    root.after(50, _draw)

    # Voice close
    def _on_destroy(event):
        if event.widget is root:
            try:
                from ui.voice_prompt_bridge import unregister_voice_prompt
                unregister_voice_prompt(root)
            except Exception:
                pass
    root.bind('<Destroy>', _on_destroy)
    try:
        from ui.voice_prompt_bridge import register_voice_prompt
        register_voice_prompt(root, on_confirm=_close, on_cancel=_close,
                              confirm_phrases=('закрой','закрыть','ок','окей','okay','понял','хорошо','да'),
                              cancel_phrases=('закрой','закрыть','стоп'))
    except Exception:
        pass

    # Pulse: just recolor the existing pulse_bar items
    _ps = [True]
    def _pulse():
        if not root.winfo_exists(): return
        color = _AMBER if _ps[0] else _blend(_AMBER, 0.25)
        try:
            c.itemconfigure('pulse_bar', fill=color)
        except Exception:
            pass
        _ps[0] = not _ps[0]
        root.after(550, _pulse)
    root.after(400, _pulse)

    root.after(60000, _close)
    root.deiconify()
    root.lift()
    root.focus_force()
    if master is None:
        root.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cancel_timer_from_hud(hud) -> None:
    from actions.game_timer import cancel_timer
    cancel_timer()
    hide_timer_widget(hud)
