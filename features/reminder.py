from __future__ import annotations
import re
import threading
import time
from core.nlp.commands import normalize_numbers

_TIME_PATTERNS = [
    r'\d+\s*час(?:а|ов)?',
    r'\d+\s*минут(?:у|ы|е)?',
    r'\d+\s*секунд(?:у|ы|е)?',
]


def extract_reminder_text(raw: str) -> str:
    text = normalize_numbers(raw.lower()).strip()
    for prefix in ('напомни мне', 'напомни', 'поставь напоминание', 'напоминание'):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    text = re.sub(r'через\s+(?:\d+\s*)?(?:час(?:а|ов)?|минут(?:у|ы|е)?|секунд(?:у|ы|е)?)', '', text)
    for word in ('что', 'о том что', 'про то что'):
        if text.startswith(word):
            text = text[len(word):].strip()
            break
    return text.strip(' ,.') or 'Напоминание'


def schedule_reminder(seconds: int, message: str, speak_fn, hud=None) -> None:
    if hud is not None:
        try:
            from ui.hud_timer_widget import show_reminder_widget
            hud._hud_queue.put(lambda: show_reminder_widget(hud, seconds, message))
        except Exception:
            pass

    def _run():
        time.sleep(seconds)
        _fire_reminder(message, speak_fn, hud)

    threading.Thread(target=_run, daemon=True, name='reminder').start()


def _fire_reminder(message: str, speak_fn, hud=None):
    # Hide HUD widget
    if hud is not None:
        try:
            from ui.hud_timer_widget import hide_reminder_widget
            hud._hud_queue.put(lambda: hide_reminder_widget(hud))
        except Exception:
            pass

    _play_alert_sound()

    if hud is not None and hasattr(hud, '_hud_queue'):
        try:
            hud._hud_queue.put(lambda: _show_reminder_window(message, speak_fn, hud, hud.root))
        except Exception:
            pass
    elif hud is not None:
        try:
            hud.root.after(0, lambda: _show_reminder_window(message, speak_fn, hud, hud.root))
        except Exception:
            pass
    else:
        try:
            threading.Thread(
                target=lambda: _show_reminder_window(message, speak_fn, None, None),
                daemon=True
            ).start()
        except Exception:
            pass

    try:
        speak_fn(f'Сэр, напоминаю: {message}')
    except Exception:
        pass


def _play_alert_sound():
    try:
        from core.speech import play_alert_sound
        play_alert_sound('reminder')
    except Exception:
        pass


def _show_reminder_window(message: str, speak_fn, hud=None, master=None):
    import tkinter as tk
    import customtkinter as ctk
    from ui.hud_constants import _AMBER, _BG, _CYAN, _DIM, _PANEL, _TEXT, _WHITE, _RED
    from ui.hud_utils import _blend
    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    ctk.set_appearance_mode('Light' if _theme == 'light' else 'Dark')

    from ui.hud_utils import _center_window, _apply_window_icon, _set_dark_title_bar, _make_resizable

    px = lambda v: v
    if master and hasattr(master, '_px'):
        px = master._px
    elif master and hasattr(master, 'master') and hasattr(master.master, '_px'):
        px = master.master._px

    _ACCENT = _CYAN
    root = tk.Toplevel(master) if master else tk.Tk()

    W, H = px(900), px(520)
    root.withdraw()
    _center_window(root, W, H)
    _make_resizable(root)
    root.configure(bg=_BG)
    _set_dark_title_bar(root)
    root.after(150, lambda: _set_dark_title_bar(root))
    _apply_window_icon(root, master)
    root.title('НАПОМИНАНИЕ — J.A.R.V.I.S.')

    inner = tk.Frame(root, bg=_BG, bd=0)
    inner.pack(fill='both', expand=True)

    title_bar = tk.Frame(inner, bg=_PANEL, height=px(50))
    title_bar.pack(fill='x')

    def _close():
        try:
            from ui.voice_prompt_bridge import unregister_voice_prompt
            unregister_voice_prompt(root)
        except Exception:
            pass
        root.destroy()

    def _snooze(snooze_sec: int):
        _close()
        schedule_reminder(snooze_sec, message, speak_fn, hud)

    tk.Frame(inner, bg=_ACCENT, height=2).pack(fill='x')

    lbl_bell = tk.Label(title_bar, text='⬡', font=('Consolas', px(18)), fg=_ACCENT, bg=_PANEL)
    lbl_bell.pack(side='left', padx=(px(20), px(10)))
    tk.Label(title_bar, text='НАПОМИНАНИЕ', font=('Consolas', px(12), 'bold'),
             fg=_TEXT, bg=_PANEL).pack(side='left')

    content = tk.Frame(root, bg=_BG)
    content.pack(fill='both', expand=True, padx=px(40), pady=(px(30), 0))

    tk.Label(content, text='Голосом: «закрой» / «ок»',
             font=('Segoe UI', px(12)), fg=_DIM, bg=_BG, anchor='w').pack(fill='x', pady=(0, px(16)))

    display = message if len(message) > 72 else message.upper()
    tk.Label(content, text=display, font=('Consolas', px(32), 'bold'),
             fg=_AMBER, bg=_BG, wraplength=W - px(100), justify='center').pack(expand=True, fill='both', pady=px(10))

    tk.Label(content, text='J.A.R.V.I.S. — REMINDER SUBSYSTEM',
             font=('Consolas', px(10)), fg=_blend(_DIM, 0.7), bg=_BG).pack(pady=(0, px(12)))

    # Button row: Snooze 5m | Snooze 10m | Close
    btn_wrap = tk.Frame(inner, bg=_BG)
    btn_wrap.pack(fill='x', pady=(0, px(36)))
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor='center')

    _snooze_color = _blend(_CYAN, 0.5)
    ctk.CTkButton(
        btn_inner, text='ОТЛОЖИТЬ  5 МИН', width=px(200), height=px(50),
        fg_color='transparent', border_color=_CYAN, border_width=2,
        text_color=_CYAN, hover_color=_blend(_CYAN, 0.12),
        font=('Consolas', px(13), 'bold'), corner_radius=6,
        command=lambda: _snooze(300)
    ).pack(side='left', padx=(0, px(10)))

    ctk.CTkButton(
        btn_inner, text='ОТЛОЖИТЬ  10 МИН', width=px(210), height=px(50),
        fg_color='transparent', border_color=_CYAN, border_width=2,
        text_color=_CYAN, hover_color=_blend(_CYAN, 0.12),
        font=('Consolas', px(13), 'bold'), corner_radius=6,
        command=lambda: _snooze(600)
    ).pack(side='left', padx=(0, px(10)))

    ctk.CTkButton(
        btn_inner, text='ЗАКРЫТЬ  ✕', width=px(180), height=px(50),
        fg_color='transparent', border_color=_DIM, border_width=2,
        text_color=_DIM, hover_color=_blend(_WHITE, 0.1),
        font=('Consolas', px(14), 'bold'), corner_radius=6,
        command=_close
    ).pack(side='left')

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
        register_voice_prompt(
            root,
            on_confirm=_close,
            on_cancel=_close,
            confirm_phrases=('закрой', 'закрыть', 'ок', 'окей', 'okay', 'понял', 'ясно', 'хорошо', 'да'),
            cancel_phrases=('закрой', 'закрыть', 'стоп'),
        )
    except Exception:
        pass

    _pulse_state = [True]
    def _pulse():
        if not root.winfo_exists():
            return
        color = _CYAN if _pulse_state[0] else _blend(_CYAN, 0.4)
        if title_bar.winfo_exists():
            title_bar.configure(bg=color)
        lbl_bell.configure(fg=color)
        _pulse_state[0] = not _pulse_state[0]
        root.after(600, _pulse)
    _pulse()

    root.after(60000, _close)
    root.deiconify()
    root.lift()
    root.focus_force()
    if master is None:
        root.mainloop()
