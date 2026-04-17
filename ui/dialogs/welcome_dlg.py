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
    win = tk.Toplevel(hud.root)
    hud._welcome_win = win
    _set_dark_title_bar(win)
    win.after(160, lambda: _set_dark_title_bar(win))
    win.title('J.A.R.V.I.S. — Добро пожаловать')
    win.configure(bg=_BG)
    win.resizable(True, True)
    win.minsize(880, 580)
    W, H = 980, 710
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f'{W}x{H}+{max(0,(sw-W)//2)}+{max(0,(sh-H)//2)}')
    try:
        if hasattr(hud, '_ico_path'):
            win.iconbitmap(hud._ico_path)
    except Exception:
        pass
    F = getattr(hud, '_F', 'Consolas')
    zoom = getattr(hud, '_zoom', 1.0)
    def _sf(n: int) -> int:
        return max(6, int(n * zoom))
    def _px(n: int) -> int:
        return hud._px(n) if hasattr(hud, '_px') else max(4, int(n * zoom))
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='top')
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', padx=36, pady=(22, 0))
    title_col = tk.Frame(hdr, bg=_BG)
    title_col.pack(side='left', fill='y')
    tk.Label(title_col, text='J.A.R.V.I.S.', bg=_BG, fg=_CYAN,
             font=(F, _sf(30), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(title_col, text='Just A Rather Very Intelligent System',
             bg=_BG, fg=_DIM, font=(F, _sf(9)), anchor='w').pack(anchor='w', pady=(2, 0))
    tk.Label(title_col,
             text='Ваш персональный голосовой ИИ-ассистент. Добро пожаловать, сэр.',
             bg=_BG, fg=_TEXT, font=(F, _sf(11)), anchor='w').pack(anchor='w', pady=(8, 0))
    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.08),
                     highlightbackground=_blend(_CYAN, 0.3), highlightthickness=1)
    badge.pack(side='right', anchor='n', padx=(0, 4), pady=4)
    tk.Label(badge, text=' v 1.4 ', bg=_blend(_CYAN, 0.08), fg=_CYAN,
             font=(F, _sf(9), 'bold')).pack(padx=10, pady=6)
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=36, pady=(18, 0))
    body_frame = tk.Frame(win, bg=_BG)
    body_frame.pack(fill='both', expand=True)
    canvas = tk.Canvas(body_frame, bg=_BG, bd=0, highlightthickness=0)
    vsb = tk.Scrollbar(body_frame, orient='vertical', command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    vsb.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(canvas, bg=_BG)
    inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')
    def _on_cfg(e=None):
        canvas.configure(scrollregion=canvas.bbox('all'))
        canvas.itemconfig(inner_id, width=canvas.winfo_width())
    inner.bind('<Configure>', _on_cfg)
    canvas.bind('<Configure>', _on_cfg)
    def _wheel(e):
        canvas.yview_scroll(-1 * (e.delta // 120), 'units')
    canvas.bind('<Enter>', lambda e: win.bind('<MouseWheel>', _wheel))
    canvas.bind('<Leave>', lambda e: win.unbind('<MouseWheel>'))
    CARDS = [
        (_CYAN, '◎  КАК АКТИВИРОВАТЬ',
         'Скажите  «Джарвис»  — ассистент слушает и ждёт команду.\n'
         'Через 30 секунд тишины он уходит в режим ожидания.\n'
         '«Не слушай меня» / «Режим тишины» — замолчать.\n'
         '«Слушай меня» — вернуть прослушивание.'),
        (_GREEN, '🖥  СИСТЕМА И ПРИЛОЖЕНИЯ',
         '«Открой браузер» / «Открой Discord» / «Запусти Steam»\n'
         '«Закрой окно» / «Сверни все окна» / «На весь экран»\n'
         '«Сделай скриншот» / «Громче» / «Тише» / «Отключи звук»\n'
         '«Скопируй» / «Вставь» / «Отмени» / «Найди файл»'),
        (_MAG, '📝  ДИКТОВКА',
         'Скажите «Режим диктовки» — всё что вы говорите\n'
         'будет напечатано в активном текстовом поле.\n'
         'Работает в браузере, мессенджерах, документах.\n'
         '«Стоп» или «Хватит» — выход из диктовки.'),
        (_AMBER, '🎮  ИГРОВОЙ РЕЖИМ',
         '«Игровой режим» — активирует профиль текущей игры.\n'
         'Euro Truck Simulator 2: круиз-контроль, поворотники,\n'
         'свет, дворники, авто-круиз по ограничению скорости.\n'
         '«Закрой игру» — закрывает ETS2 и выходит из режима.'),
        (_CYAN, '⏰  НАПОМИНАНИЯ',
         '«Напомни через 20 минут» / «Напомни через час»\n'
         '«Напомни через полчаса выключить плиту»\n'
         '«Выключи компьютер через 2 часа»\n'
         '«Отмени выключение» / «Отмени напоминание»'),
        (_GREEN, '🔍  ПОИСК И ПЕРЕВОДЫ',
         '«Найди в гугле [запрос]» — открывает браузер\n'
         '«Переведи [текст]» / «Переведи на английский»\n'
         '«Скажи мне [вопрос]» — ИИ-поиск\n'
         '«Курс доллара» / «Мой IP» / «Скорость интернета»'),
        (_MAG, '🎵  МЕДИА И YOUTUBE',
         '«Включи следующий трек» / «Пауза» / «Стоп»\n'
         '«Включи песню [название]» — поиск на YouTube\n'
         '«Полный экран» / «Вперёд на 10» / «Назад на 30»\n'
         '«Скачай» — загрузить текущее видео'),
        (_TEXT, '⚙️  НАСТРОЙКИ',
         'Нажмите кнопку ⚙ в правом верхнем углу HUD:\n'
         '• Чувствительность и усиление микрофона\n'
         '• Выбор STT-модели (GigaAM / Vosk)\n'
         '• Управление модулями и расширениями\n'
         '• Ссылки на встречи (Zoom, Teams, Meet)'),
    ]
    grid = tk.Frame(inner, bg=_BG)
    grid.pack(fill='both', padx=26, pady=(14, 4))
    grid.columnconfigure(0, weight=1, uniform='c')
    grid.columnconfigure(1, weight=1, uniform='c')
    for idx, (accent, title, body_text) in enumerate(CARDS):
        r, c = divmod(idx, 2)
        card = tk.Frame(grid,
                        bg=_blend(accent, 0.055),
                        highlightbackground=_blend(accent, 0.28),
                        highlightthickness=1)
        card.grid(row=r, column=c, padx=6, pady=5, sticky='nsew')
        tk.Label(card, text=title, bg=_blend(accent, 0.055), fg=accent,
                 font=(F, _sf(9), 'bold'), anchor='w',
                 justify='left').pack(fill='x', padx=13, pady=(11, 4))
        tk.Frame(card, bg=_blend(accent, 0.22), height=1).pack(fill='x', padx=13, pady=(0, 5))
        tk.Label(card, text=body_text, bg=_blend(accent, 0.055), fg=_TEXT,
                 font=(F, _sf(9)), anchor='w',
                 justify='left').pack(fill='x', padx=13, pady=(0, 13))
    try:
        from core.mic_calibration import is_calibrated as _ic
        if not _ic():
            cal = tk.Frame(inner,
                           bg=_blend(_AMBER, 0.08),
                           highlightbackground=_blend(_AMBER, 0.45),
                           highlightthickness=1)
            cal.pack(fill='x', padx=32, pady=(4, 2))
            tk.Label(cal,
                     text='⚠  Микрофон ещё не откалиброван.  '
                          'Откройте Настройки → МИКРОФОН / ЧУВСТВИТЕЛЬНОСТЬ для точной настройки.',
                     bg=_blend(_AMBER, 0.08), fg=_AMBER,
                     font=(F, _sf(9))).pack(padx=16, pady=9, anchor='w')
    except Exception:
        pass
    tip = tk.Frame(inner, bg=_blend(_CYAN, 0.04),
                   highlightbackground=_blend(_CYAN, 0.15), highlightthickness=1)
    tip.pack(fill='x', padx=32, pady=(6, 4))
    tk.Label(tip,
             text='💡  Скажите «Покажи хад» чтобы вернуть этот экран в любой момент.',
             bg=_blend(_CYAN, 0.04), fg=_DIM, font=(F, _sf(8))).pack(
             padx=14, pady=8, anchor='w')
    tk.Frame(inner, bg=_BG, height=10).pack()
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x')
    bot = tk.Frame(win, bg=_PANEL)
    bot.pack(fill='x', side='bottom')
    tk.Label(bot,
             text='Скажите «Джарвис, помощь» — чтобы снова открыть это руководство.',
             bg=_PANEL, fg=_DIM, font=(F, _sf(8))).pack(side='left', padx=18, pady=12)
    def _open_settings():
        try:
            from ui.dialogs.settings_dlg import open_settings
            open_settings(hud)
        except Exception:
            pass
    ctk.CTkButton(bot, text='⚙  Настройки', command=_open_settings,
                  height=_px(38), font=(F, _sf(10)),
                  fg_color='transparent', hover_color=_blend(_DIM, 0.1),
                  text_color=_DIM, border_color=_blend(_DIM, 0.3),
                  border_width=2, corner_radius=8).pack(side='right', padx=(4, 12), pady=9)
    def _start():
        win.destroy()
    ctk.CTkButton(bot, text='  Начать работу  ▶', command=_start,
                  height=_px(38), font=(F, _sf(11), 'bold'),
                  fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.28),
                  text_color=_CYAN, border_color=_blend(_CYAN, 0.65),
                  border_width=2, corner_radius=8).pack(side='right', padx=(12, 4), pady=9)
    tk.Frame(win, bg=_MAG, height=2).pack(fill='x', side='bottom')
    win.grab_set()
    win.focus_set()
