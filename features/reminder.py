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
    def _run():
        time.sleep(seconds)
        _fire_reminder(message, speak_fn, hud)
    threading.Thread(target=_run, daemon=True, name='reminder').start()
def _fire_reminder(message: str, speak_fn, hud=None):
    _play_alert_sound()
    if hud is not None:
        try:
            hud.root.after(0, lambda: _show_reminder_window(message, hud.root))
        except Exception:
            pass
    else:
        try:
            import threading as _t
            _t.Thread(target=lambda: _show_reminder_window(message, None), daemon=True).start()
        except Exception:
            pass
    try:
        speak_fn(f'Сэр, напоминаю: {message}')
    except Exception:
        pass
def _play_alert_sound():
    try:
        import pygame
        if not pygame.mixer.get_init():
            return
        try:
            import numpy as np
            sample_rate = 44100
            duration = 0.35
            freq = 880
            t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
            wave = (np.sin(2 * np.pi * freq * t) * 0.6).astype(np.float32)
            fade_len = int(len(wave) * 0.2)
            wave[-fade_len:] *= np.linspace(1, 0, fade_len)
            sound = pygame.sndarray.make_sound((wave * 32767).astype(np.int16).reshape(-1, 1).repeat(2, axis=1))
            sound.play()
        except Exception:
            import winsound
            winsound.Beep(880, 350)
    except Exception:
        try:
            import winsound
            winsound.Beep(880, 350)
        except Exception:
            pass
def _show_reminder_window(message: str, master=None):
    import tkinter as tk
    from ui.hud_constants import _AMBER, _BG, _BRD, _CYAN, _DIM, _PANEL, _SEP
    _BTN_BG = "#0d1a2e"
    _HDR_LINE = 3
    root = tk.Toplevel(master) if master else tk.Tk()
    root.withdraw()
    W, H = 520, 260
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    root.title("REMINDER — J.A.R.V.I.S.")
    root.geometry(f"{W}x{H}+{x}+{y}")
    root.configure(bg=_BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)
    try:
        from ui.hud_utils import _set_dark_title_bar
        _set_dark_title_bar(root)
    except Exception:
        pass
    outer = tk.Frame(root, bg=_BRD, bd=0)
    outer.place(x=0, y=0, width=W, height=H)
    inner = tk.Frame(outer, bg=_PANEL, bd=0)
    inner.place(x=1, y=1, width=W - 2, height=H - 2)
    hdr = tk.Frame(inner, bg=_CYAN, height=_HDR_LINE)
    hdr.pack(fill="x", side="top")
    lbl_title = tk.Label(
        inner,
        text="⏰  НАПОМИНАНИЕ",
        font=("Consolas", 11, "bold"),
        fg=_CYAN,
        bg=_PANEL,
        anchor="w",
        padx=18,
    )
    lbl_title.pack(fill="x", pady=(12, 0))
    tk.Label(
        inner,
        text="Голосом: «закрой» / «ок»",
        font=("Consolas", 8),
        fg=_DIM,
        bg=_PANEL,
        anchor="w",
        padx=18,
    ).pack(fill="x", pady=(2, 0))
    tk.Frame(inner, bg=_SEP, height=1).pack(fill="x", padx=18, pady=(8, 10))
    display = message if len(message) > 72 else message.upper()
    lbl_msg = tk.Label(
        inner,
        text=display,
        font=("Consolas", 13, "bold"),
        fg=_AMBER,
        bg=_PANEL,
        wraplength=W - 44,
        justify="center",
    )
    lbl_msg.pack(expand=True, fill="both", padx=18, pady=(4, 6))
    lbl_sub = tk.Label(
        inner,
        text="J.A.R.V.I.S. — REMINDER SUBSYSTEM",
        font=("Consolas", 7),
        fg=_DIM,
        bg=_PANEL,
    )
    lbl_sub.pack(pady=(0, 4))
    tk.Frame(inner, bg=_SEP, height=1).pack(fill="x", padx=18, pady=(0, 10))
    def _close():
        _fade_out(root)
    def _destroy_voice(event):
        if event.widget is root:
            try:
                from ui.voice_prompt_bridge import unregister_voice_prompt
                unregister_voice_prompt(root)
            except Exception:
                pass
    root.bind("<Destroy>", _destroy_voice)
    try:
        from ui.voice_prompt_bridge import register_voice_prompt
        register_voice_prompt(
            root,
            on_confirm=_close,
            on_cancel=_close,
            confirm_phrases=(
                "закрой",
                "закрыть",
                "ок",
                "окей",
                "okay",
                "понял",
                "ясно",
                "хорошо",
                "да",
            ),
            cancel_phrases=("закрой", "закрыть", "стоп"),
        )
    except Exception:
        pass
    btn_frame = tk.Frame(inner, bg=_PANEL)
    btn_frame.pack(pady=(0, 16))
    btn = tk.Button(
        btn_frame,
        text="  ЗАКРЫТЬ  ",
        font=("Consolas", 9, "bold"),
        fg=_CYAN,
        bg=_BTN_BG,
        activeforeground=_AMBER,
        activebackground=_BTN_BG,
        relief="flat",
        bd=0,
        cursor="hand2",
        command=_close,
    )
    btn.pack()
    _pulse_state = [True]
    def _pulse():
        if not root.winfo_exists():
            return
        color = _CYAN if _pulse_state[0] else "#006666"
        hdr.configure(bg=color)
        lbl_title.configure(fg=color)
        _pulse_state[0] = not _pulse_state[0]
        root.after(600, _pulse)
    def _fade_in(alpha=0.0):
        if not root.winfo_exists():
            return
        alpha = min(alpha + 0.07, 0.97)
        root.attributes("-alpha", alpha)
        if alpha < 0.97:
            root.after(20, lambda: _fade_in(alpha))
        else:
            _pulse()
            root.after(15000, _close)
    def _fade_out(win, alpha=0.97):
        if not win.winfo_exists():
            return
        alpha = max(alpha - 0.08, 0.0)
        win.attributes("-alpha", alpha)
        if alpha > 0:
            win.after(20, lambda: _fade_out(win, alpha))
        else:
            win.destroy()
    root.deiconify()
    root.lift()
    root.focus_force()
    _fade_in()
    if master is None:
        root.mainloop()
