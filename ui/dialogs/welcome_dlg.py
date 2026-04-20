from __future__ import annotations
import json
import os
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import (
    _BG, _PANEL, _BRD, _BRD_I,
    _CYAN, _MAG, _GREEN, _AMBER, _RED,
    _TEXT, _DIM, _WHITE,
)
from ..hud_utils import _blend, _set_dark_title_bar

_SETTINGS_PATH = os.path.join('data', 'jarvis_settings.json')

def is_first_run() -> bool:
    try:
        with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return not bool(json.load(f).get('first_run_done'))
    except Exception:
        return True

def _mark_done() -> None:
    try:
        data: dict = {}
        if os.path.exists(_SETTINGS_PATH):
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        data['first_run_done'] = True
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def open_welcome(hud, force: bool = False) -> None:
    if not force and not is_first_run():
        return
    if hasattr(hud, '_welcome_win') and hud._welcome_win:
        try:
            if hud._welcome_win.winfo_exists():
                hud._welcome_win.lift()
                hud._welcome_win.focus_set()
                return
        except Exception:
            pass
    _mark_done()
    
    win = ctk.CTkToplevel(hud.root)
    hud._welcome_win = win
    _set_dark_title_bar(win)
    win.after(160, lambda: _set_dark_title_bar(win))
    
    win.title('J.A.R.V.I.S. — Руководство пользователя')
    win.configure(fg_color=_BG)
    win.resizable(True, True)
    win.minsize(820, 520)
    
    # --- Icon: always use hud._ico_path (absolute path, set at startup) ---
    def _set_icon():
        try:
            if hasattr(hud, '_ico_path') and hud._ico_path and os.path.exists(hud._ico_path):
                win.iconbitmap(hud._ico_path)
        except Exception:
            pass
    # Delay needed: CTkToplevel may reset the icon after init
    win.after(100, _set_icon)
    win.after(400, _set_icon)  # Second attempt for reliability

    # --- Centered geometry, respects taskbar ---
    def _center_win():
        win.update_idletasks()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        W = min(1040, sw - 60)
        H = min(700, sh - 100)
        x = (sw - W) // 2
        y = max(0, (sh - H) // 2 - 30)
        win.geometry(f'{W}x{H}+{x}+{y}')
    win.after(50, _center_win)
    # Initial rough size so window doesn't flash huge
    win.geometry(f'1040x700')

    F = getattr(hud, '_F', 'Consolas')
    zoom = getattr(hud, '_zoom', 1.0)

    def _sf(n: int) -> int:
        return max(6, int(n * zoom))

    def _px(n: int) -> int:
        return hud._px(n) if hasattr(hud, '_px') else max(4, int(n * zoom))

    # Top accent line
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='top')

    # --- Header ---
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', padx=36, pady=(14, 8))
    
    logo_f = tk.Frame(hdr, bg=_BG)
    logo_f.pack(side='left', padx=(0, 16))
    tk.Label(logo_f, text='⌬', bg=_BG, fg=_CYAN, font=(F, _sf(44))).pack()

    title_col = tk.Frame(hdr, bg=_BG)
    title_col.pack(side='left', fill='y')
    tk.Label(title_col, text='J.A.R.V.I.S.', bg=_BG, fg=_CYAN,
             font=(F, _sf(32), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(title_col, text='Just A Rather Very Intelligent System',
             bg=_BG, fg=_DIM, font=(F, _sf(10), 'italic'), anchor='w').pack(anchor='w', pady=(2, 0))
    tk.Label(title_col,
             text='Голосовое управление вашей системой. Скажите «Джарвис» — и начните.',
             bg=_BG, fg=_TEXT, font=(F, _sf(12)), anchor='w').pack(anchor='w', pady=(6, 0))

    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.08),
                     highlightbackground=_blend(_CYAN, 0.3), highlightthickness=1)
    badge.pack(side='right', anchor='n', padx=(0, 4), pady=4)
    tk.Label(badge, text=' v 1.5—HUD ', bg=_blend(_CYAN, 0.08), fg=_CYAN,
             font=(F, _sf(9), 'bold')).pack(padx=10, pady=6)

    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=20)

    # --- Scrollable Area ---
    scroll_frame = ctk.CTkScrollableFrame(win, fg_color=_BG, scrollbar_fg_color=_BG,
                                          scrollbar_button_color=_BRD_I,
                                          scrollbar_button_hover_color=_CYAN,
                                          corner_radius=0)
    scroll_frame.pack(fill='both', expand=True, padx=16, pady=(2, 4))

    # Center wrapper
    center_wrap = tk.Frame(scroll_frame, bg=_BG)
    center_wrap.pack(fill='both', expand=True)

    # Simplified, shorter card texts for first-time users
    CARDS = [
        (_CYAN,  '◎  ГОЛОСОВАЯ АКТИВАЦИЯ',
         'Скажите «Джарвис» — система услышит вас мгновенно. Нейросеть фильтрует фоновые звуки, поэтому команды работают даже в шумной обстановке.'),
        (_GREEN, '🖥  КОНТРОЛЬ WINDOWS',
         'Открывайте программы, управляйте окнами, папками и файлами голосом. «Открой браузер», «создай папку на рабочем столе» — всё это без мыши.'),
        (_MAG,   '📝  ДИКТОВКА',
         'Диктуйте текст в любое поле: чаты, документы, редакторы кода. Джарвис расставит пунктуацию и поймёт технические термины.'),
        (_AMBER, '🎮  ИГРОВОЙ РЕЖИМ',
         'ETS2 и FS22: управляйте машиной, грузом и маршрутом голосом. Джарвис следит за телеметрией и помогает в пути, не отвлекая от руля.'),
        (_CYAN,  '⏰  НАПОМИНАНИЯ',
         'Скажите «напомни через час» или «задача на утро» — Джарвис запомнит и оповестит в нужный момент. Ваш голосовой планировщик.'),
        (_GREEN, '🔍  УМНЫЙ ПОИСК',
         'Джарвис ищет, анализирует и озвучивает ответ — погода, курсы валют, любой вопрос. Не нужно открывать браузер и читать страницы.'),
        (_MAG,   '🎵  МЕДИА',
         'Найдите и включите видео на YouTube голосом. Управляйте громкостью и воспроизведением. Скажите «скачай это видео» — сохранит.'),
        (_AMBER, '⚙️  РАСШИРЕНИЯ',
         'В настройках включите нужные модули: Photoshop, почта, календарь, мониторинг. Джарвис подстраивается под вас.'),
    ]

    grid = tk.Frame(center_wrap, bg=_BG)
    grid.pack(fill='both', expand=True, padx=8, pady=6)
    grid.columnconfigure(0, weight=1)
    grid.columnconfigure(1, weight=1)

    label_widgets: list[tk.Label] = []

    for idx, (accent, title, body_text) in enumerate(CARDS):
        r, c = divmod(idx, 2)
        card = tk.Frame(grid, bg=_BG, highlightbackground=_blend(accent, 0.35), highlightthickness=1)
        card.grid(row=r, column=c, padx=8, pady=8, sticky='nsew')
        inner_card = tk.Frame(card, bg=_blend(accent, 0.04))
        inner_card.pack(fill='both', expand=True, padx=1, pady=1)

        tk.Label(inner_card, text=title, bg=_blend(accent, 0.04), fg=accent,
                 font=(F, _sf(12), 'bold'), anchor='w',
                 justify='left').pack(fill='x', padx=14, pady=(14, 6))
        tk.Frame(inner_card, bg=_blend(accent, 0.18), height=1).pack(fill='x', padx=14, pady=(0, 8))
        lbl = tk.Label(inner_card, text=body_text, bg=_blend(accent, 0.04), fg=_TEXT,
                       font=(F, _sf(11)), anchor='nw',
                       justify='left', wraplength=360)
        lbl.pack(fill='both', expand=True, padx=14, pady=(0, 16))
        label_widgets.append(lbl)

    def _on_grid_resize(e=None):
        try:
            w = center_wrap.winfo_width()
            if w > 100:
                col_w = max(100, w // 2 - 60)
                for l in label_widgets:
                    l.configure(wraplength=col_w)
        except Exception:
            pass

    center_wrap.bind('<Configure>', lambda e: _on_grid_resize())
    win.after(200, _on_grid_resize)

    # --- Bottom accent ---
    tk.Frame(win, bg=_MAG, height=2).pack(fill='x', side='bottom')

    # --- Footer ---
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', side='bottom')
    bot = tk.Frame(win, bg=_PANEL)
    bot.pack(fill='x', side='bottom')
    
    tk.Label(bot, text='Настройте Джарвиса под себя, сэр. Мы всегда готовы к работе.',
             bg=_PANEL, fg=_DIM, font=(F, _sf(10))).pack(side='left', padx=20, pady=14)

    def _open_settings():
        try:
            from ui.dialogs.settings_dlg import open_settings
            open_settings(hud)
        except Exception:
            pass

    ctk.CTkButton(bot, text='⚙  Настройки', command=_open_settings,
                  height=_px(42), font=(F, _sf(12)),
                  fg_color='transparent', hover_color=_blend(_DIM, 0.1),
                  text_color=_DIM, border_color=_blend(_DIM, 0.3),
                  border_width=2, corner_radius=10).pack(side='right', padx=(4, 14), pady=10)

    ctk.CTkButton(bot, text='  Продолжить  ▶', command=win.destroy,
                  height=_px(42), font=(F, _sf(13), 'bold'),
                  fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.28),
                  text_color=_CYAN, border_color=_blend(_CYAN, 0.65),
                  border_width=2, corner_radius=10).pack(side='right', padx=(14, 4), pady=10)

    win.grab_set()
    win.focus_set()
