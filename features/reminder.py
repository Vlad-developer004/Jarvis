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
    if hud is not None and hasattr(hud, '_hud_queue'):
        try:
            # Use the HUD's safe queue to run UI tasks in the main UI thread
            hud._hud_queue.put(lambda: _show_reminder_window(message, hud.root))
        except Exception:
            pass
    elif hud is not None:
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
    import customtkinter as ctk
    from ui.hud_constants import _AMBER, _BG, _CYAN, _DIM, _PANEL, _TEXT, _WHITE, _RED
    from ui.hud_utils import _blend
    
    _ACCENT = _CYAN
    root = tk.Toplevel(master) if master else tk.Tk()
    root.withdraw()
    W, H = 640, 360
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = (sw - W) // 2
    y = (sh - H) // 2
    root.title("REMINDER — J.A.R.V.I.S.")
    root.geometry(f"{W}x{H}+{x}+{y}")
    root.configure(bg=_BG)
    root.resizable(False, False)
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.0)

    outer = tk.Frame(root, bg=_ACCENT, bd=0)
    outer.place(x=0, y=0, width=W, height=H)
    inner = tk.Frame(outer, bg=_BG, bd=0)
    inner.place(x=1, y=1, width=W - 2, height=H - 2)

    # Title Bar
    title_bar = tk.Frame(inner, bg=_PANEL, height=44)
    title_bar.pack(fill="x")
    hdr = tk.Frame(inner, bg=_blend(_ACCENT, 0.4), height=2)
    hdr.pack(fill="x")

    def _close():
        _fade_out(root)

    btn_close = tk.Label(title_bar, text="✕", font=("Consolas", 14), fg=_DIM, bg=_PANEL, cursor="hand2")
    btn_close.pack(side="right", padx=16)
    btn_close.bind("<Button-1>", lambda e: _close())
    btn_close.bind("<Enter>", lambda e: btn_close.configure(fg=_RED))
    btn_close.bind("<Leave>", lambda e: btn_close.configure(fg=_DIM))

    lbl_bell = tk.Label(title_bar, text="⬡", font=("Consolas", 16), fg=_ACCENT, bg=_PANEL)
    lbl_bell.pack(side="left", padx=(18, 10))
    tk.Label(title_bar, text="НАПОМИНАНИЕ", font=("Consolas", 11, "bold"), fg=_TEXT, bg=_PANEL).pack(side="left")

    content = tk.Frame(inner, bg=_BG)
    content.pack(fill="both", expand=True, padx=36, pady=(32, 0))

    tk.Label(content, text="Голосом: «закрой» / «ок»", font=("Segoe UI", 11), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, 20))
    
    display = message if len(message) > 72 else message.upper()
    lbl_msg = tk.Label(content, text=display, font=("Consolas", 20, "bold"), fg=_AMBER, bg=_BG, wraplength=W - 72, justify="center")
    lbl_msg.pack(expand=True, fill="both", pady=10)

    lbl_sub = tk.Label(content, text="J.A.R.V.I.S. — REMINDER SUBSYSTEM", font=("Consolas", 9), fg=_blend(_DIM, 0.7), bg=_BG)
    lbl_sub.pack(pady=(0, 20))
    
    # Button Row
    btn_wrap = tk.Frame(inner, bg=_BG)
    btn_wrap.pack(fill="x", pady=(0, 32))
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor="center")

    btn = ctk.CTkButton(
        btn_inner, text="ЗАКРЫТЬ  ✕", width=200, height=48, 
        fg_color="transparent", border_color=_DIM, border_width=2, text_color=_DIM,
        hover_color=_blend(_WHITE, 0.1), font=("Consolas", 14, "bold"), corner_radius=6, command=_close
    )
    btn.pack()

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

    _pulse_state = [True]
    def _pulse():
        if not root.winfo_exists():
            return
        color = _CYAN if _pulse_state[0] else "#006666"
        hdr.configure(bg=color)
        lbl_bell.configure(fg=color)
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
            root.after(25000, _close)

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
