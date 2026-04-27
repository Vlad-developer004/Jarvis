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
    
    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    ctk.set_appearance_mode("Light" if _theme == "light" else "Dark")
    
    from ui.hud_utils import _center_window, _apply_window_icon, _set_dark_title_bar, _make_resizable
    
    # Resolve scaling factor
    px = lambda v: v
    if master and hasattr(master, '_px'): px = master._px
    elif master and hasattr(master, 'master') and hasattr(master.master, '_px'): px = master.master._px

    _ACCENT = _CYAN
    root = tk.Toplevel(master) if master else tk.Tk()
    
    # Size and Centering
    W, H = px(900), px(500)
    root.withdraw()
    _center_window(root, W, H)
    _make_resizable(root)
    
    root.configure(bg=_BG)
    _set_dark_title_bar(root)
    root.after(150, lambda: _set_dark_title_bar(root))
    _apply_window_icon(root, master)

    root.title('НАПОМИНАНИЕ — J.A.R.V.I.S.')

    inner = tk.Frame(root, bg=_BG, bd=0)
    inner.pack(fill="both", expand=True)

    # Title Bar (Design element only now)
    title_bar = tk.Frame(inner, bg=_PANEL, height=px(50))
    title_bar.pack(fill="x")

    def _close():
        root.destroy()

    # THE FAMOUS ACCENT LINE
    tk.Frame(inner, bg=_ACCENT, height=2).pack(fill='x')

    lbl_bell = tk.Label(title_bar, text="⬡", font=("Consolas", px(18)), fg=_ACCENT, bg=_PANEL)
    lbl_bell.pack(side="left", padx=(px(20), px(10)))
    tk.Label(title_bar, text="НАПОМИНАНИЕ", font=("Consolas", px(12), "bold"), fg=_TEXT, bg=_PANEL).pack(side="left")

    content = tk.Frame(root, bg=_BG)
    content.pack(fill="both", expand=True, padx=px(40), pady=(px(40), 0))

    tk.Label(content, text="Голосом: «закрой» / «ок»", font=("Segoe UI", px(12)), fg=_DIM, bg=_BG, anchor="w").pack(fill="x", pady=(0, px(20)))
    
    display = message if len(message) > 72 else message.upper()
    lbl_msg = tk.Label(content, text=display, font=("Consolas", px(32), "bold"), fg=_AMBER, bg=_BG, wraplength=W - px(100), justify="center")
    lbl_msg.pack(expand=True, fill="both", pady=px(10))

    lbl_sub = tk.Label(content, text="J.A.R.V.I.S. — REMINDER SUBSYSTEM", font=("Consolas", px(10)), fg=_blend(_DIM, 0.7), bg=_BG)
    lbl_sub.pack(pady=(0, px(20)))
    
    # Button Row
    btn_wrap = tk.Frame(inner, bg=_BG)
    btn_wrap.pack(fill="x", pady=(0, px(40)))
    btn_inner = tk.Frame(btn_wrap, bg=_BG)
    btn_inner.pack(anchor="center")

    btn = ctk.CTkButton(
        btn_inner, text="ЗАКРЫТЬ  ✕", width=px(240), height=px(54), 
        fg_color="transparent", border_color=_DIM, border_width=2, text_color=_DIM,
        hover_color=_blend(_WHITE, 0.1), font=("Consolas", px(16), "bold"), corner_radius=6, command=_close
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
        color = _CYAN if _pulse_state[0] else _blend(_CYAN, 0.4)
        if title_bar.winfo_exists(): title_bar.configure(bg=color)
        lbl_bell.configure(fg=color)
        _pulse_state[0] = not _pulse_state[0]
        root.after(600, _pulse)

    _pulse()
    root.after(30000, _close)

    root.deiconify()
    root.lift()
    root.focus_force()
    if master is None:
        root.mainloop()
