from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json
import os
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import (
    _BG, _PANEL, _BRD, _BRD_I,
    _CYAN, _MAG, _GREEN, _AMBER, _RED,
    _TEXT, _DIM, _WHITE,
)
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon

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
    _apply_window_icon(win, hud)
    win.after(160, lambda: _set_dark_title_bar(win))
    
    win.title(i18n.tr('welcome.win_title'))
    win.configure(fg_color=_BG)  # type: ignore[call-arg]
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
        zf = hud.zoom_factor if hud else 1.0
        sw = int(win.winfo_screenwidth() / zf)
        sh = int(win.winfo_screenheight() / zf)
        W = min(1040, sw - 60)
        H = min(700, sh - 100)
        x = (sw - W) // 2
        y = max(0, (sh - H) // 2 - 30)
        win.geometry(f'{W}x{H}+{x}+{y}')
    win.after(50, _center_win)
    # Initial rough size
    win.geometry(f'1040x700')

    F = getattr(hud, '_F', 'Consolas')
    zoom = getattr(hud, 'zoom_factor', 1.0)

    def _sf(n: int) -> int:
        return max(6, int(n * zoom))

    def _px(n: int) -> int:
        return int(n * zoom)

    # Top accent line
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='top')

    # --- Header ---
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', padx=_px(36), pady=(_px(14), _px(8)))
    
    logo_f = tk.Frame(hdr, bg=_BG)
    logo_f.pack(side='left', padx=(0, _px(16)))
    tk.Label(logo_f, text='⌬', bg=_BG, fg=_CYAN, font=(F, _sf(44))).pack()

    title_col = tk.Frame(hdr, bg=_BG)
    title_col.pack(side='left', fill='y')
    tk.Label(title_col, text='J.A.R.V.I.S.', bg=_BG, fg=_CYAN,
             font=(F, _sf(32), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(title_col, text='Just A Rather Very Intelligent System',
             bg=_BG, fg=_DIM, font=(F, _sf(10), 'italic'), anchor='w').pack(anchor='w', pady=(_px(2), 0))
    tk.Label(title_col,
             text=i18n.tr('welcome.subtitle'),
             bg=_BG, fg=_TEXT, font=(F, _sf(12)), anchor='w').pack(anchor='w', pady=(_px(6), 0))

    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.08),
                     highlightbackground=_blend(_CYAN, 0.3), highlightthickness=1)
    badge.pack(side='right', anchor='n', padx=(0, _px(4)), pady=_px(4))
    tk.Label(badge, text=' v 1.5—HUD ', bg=_blend(_CYAN, 0.08), fg=_CYAN,
             font=(F, _sf(9), 'bold')).pack(padx=_px(10), pady=_px(6))

    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=_px(20))

    # --- Scrollable Area ---
    scroll_frame = ctk.CTkScrollableFrame(win, fg_color=_BG, scrollbar_fg_color=_BG,
                                          scrollbar_button_color=_BRD_I,
                                          scrollbar_button_hover_color=_CYAN,
                                          corner_radius=0)
    scroll_frame.pack(fill='both', expand=True, padx=_px(16), pady=(_px(2), _px(4)))

    # Center wrapper
    center_wrap = tk.Frame(scroll_frame, bg=_BG)
    center_wrap.pack(fill='both', expand=True)

    # --- Address selection (first-run only) ---
    _addr_section = tk.Frame(scroll_frame, bg=_BG)
    _addr_section.pack(fill='x', padx=_px(24), pady=(_px(10), _px(4)))

    is_uk_lang = (i18n.get_language() == 'uk')
    _addr_title = 'ХТО ВИ?' if is_uk_lang else 'КТО ВЫ?'
    _addr_subtitle = (
        'Оберіть звернення — Джарвіс буде звертатися до вас відповідно'
        if is_uk_lang else
        'Выберите обращение — Джарвис будет обращаться к вам соответственно'
    )

    tk.Label(_addr_section, text=_addr_title, bg=_BG, fg=_CYAN,
             font=(F, _sf(13), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(_addr_section, text=_addr_subtitle, bg=_BG, fg=_DIM,
             font=(F, _sf(10)), anchor='w').pack(anchor='w', pady=(_px(3), _px(10)))

    _addr_row = tk.Frame(_addr_section, bg=_BG)
    _addr_row.pack(fill='x')

    import json as _json
    from config_pack.config import get_settings_path as _get_sp

    def _load_addr_settings() -> dict:
        try:
            with open(_get_sp(), 'r', encoding='utf-8') as _f:
                return _json.load(_f)
        except Exception:
            return {}

    def _save_addr_field(key: str, val) -> None:
        try:
            _d = _load_addr_settings()
            _d[key] = val
            p = _get_sp()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as _f:
                _json.dump(_d, _f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    _cur_mode = _load_addr_settings().get('address_mode', 'male')
    _addr_mode_var = tk.StringVar(value=_cur_mode)

    def _on_addr_mode(*_):
        _save_addr_field('address_mode', _addr_mode_var.get())
        _custom_frame.pack_forget() if _addr_mode_var.get() != 'custom' else _custom_frame.pack(fill='x', pady=(_px(6), 0))

    _btn_cfg = dict(bg=_BG, activebackground=_BG, relief='flat', cursor='hand2', font=(F, _sf(11)))

    for _val, _lbl_ru, _lbl_uk, _col in [
        ('male',   '♂  Сэр',   '♂  Сер',  _CYAN),
        ('female', '♀  Леди',  '♀  Пані', _MAG),
        ('custom', '✏  Своё',  '✏  Своє', _AMBER),
    ]:
        _lbl_text = _lbl_uk if is_uk_lang else _lbl_ru
        _btn_frame = tk.Frame(_addr_row, bg=_BG, highlightbackground=_blend(_col, 0.4),
                              highlightthickness=1)
        _btn_frame.pack(side='left', padx=(_px(0), _px(10)), pady=_px(2))

        _rb = ctk.CTkRadioButton(
            _btn_frame, text=_lbl_text,
            variable=_addr_mode_var, value=_val,
            font=(F, _sf(11) + 6), fg_color=_col, hover_color=_blend(_col, 0.7),
            command=_on_addr_mode,
        )
        _rb.pack(padx=_px(12), pady=_px(8))

    _custom_frame = tk.Frame(_addr_section, bg=_BG)
    _cur_custom = _load_addr_settings().get('custom_address', '')
    _custom_var = tk.StringVar(value=_cur_custom)

    _custom_hint = 'Введіть своє звернення:' if is_uk_lang else 'Введите своё обращение:'
    tk.Label(_custom_frame, text=_custom_hint, bg=_BG, fg=_DIM,
             font=(F, _sf(10))).pack(anchor='w')
    _custom_entry = tk.Entry(
        _custom_frame, textvariable=_custom_var, width=22,
        bg=_PANEL, fg=_WHITE, insertbackground=_CYAN,
        relief='flat', highlightthickness=1, highlightbackground=_BRD_I,
        highlightcolor=_CYAN, font=(F, _sf(11))
    )
    _custom_entry.pack(anchor='w', pady=(_px(4), 0), ipady=_px(5))

    def _on_custom_change(*_):
        _save_addr_field('custom_address', _custom_var.get())

    _custom_var.trace_add('write', _on_custom_change)

    if _cur_mode == 'custom':
        _custom_frame.pack(fill='x', pady=(_px(6), 0))

    tk.Frame(_addr_section, bg=_BRD, height=1).pack(fill='x', pady=(_px(14), _px(4)))

    # Simplified, shorter card texts for first-time users
    is_uk = (i18n.get_language() == 'uk')
    if is_uk:
        CARDS = [
            (_CYAN,  '🗣  ВІДПОВІДІ НА ІМ\'Я (WAKE WORD)',
             'Скажіть «Джарвіс» — система вас почує і лишиться активною деякий час без повтору імені (за замовчуванням 30 секунд, час можна змінити в Налаштуваннях → Голос). Там само можна вибрати: або він відповідає «Так, сер» тільки 1 раз при пробудженні (не спамить на ім\'я), або завжди відповідає на ім\'я.'),
            (_GREEN, '🧹  ПРИБИРАННЯ ТА СИСТЕМА',
             'Скажіть «Джарвіс, приберися» — він очистить кеш браузерів, тимчасові файли та пам\'ять. Також можна голосом вимикати ПК, керувати Bluetooth та Wi-Fi.'),
            (_MAG,   '🌐  ІНТЕРНЕТ ТА МЕДІА',
             '«Відкрий ютуб», «Відкрий нову вкладку» або «Зроби голосніше». Джарвіс сам знайде все в інтернеті та допоможе керувати переглядом без мишки.'),
            (_AMBER, '🎮  ІГРОВИЙ РЕЖИМ (ETS2)',
             'Граєте за кермом? Скажіть «Статус вантажівки» або «Круїз-контроль на 90», і Джарвіс миттєво виконає дії в грі, не відволікаючи від дороги.'),
            (_CYAN,  '📝  ГОЛОСОВЕ ВВЕДЕННЯ',
             'Поставте курсор у чат або документ і увімкніть режим диктовки. Джарвіс буде друкувати все, що ви говорите, сам розставляючи розділові знаки.'),
            (_GREEN, '⏰  РОЗУМНИЙ ПОМІЧНИК',
             '«Нагадай вимкнути духовку через 20 хвилин» або «Вимкни комп\'ютер через годину». Джарвіс все запам\'ятає і вчасно виведе повідомлення на екран.'),
            (_MAG,   '⚙️  ДЕ ШУКАТИ НАЛАШТУВАННЯ?',
             'Натисніть на кнопку з шестірнею внизу або скажіть «Відкрий налаштування». Там можна відкалібрувати мікрофон, якщо Джарвіс вас погано чує.'),
            (_AMBER, '🔒  НАВІЩО ЦЕ ПОТРІБНО?',
             'Щоб керувати ПК з вільними руками! При цьому Джарвіс працює локально (без інтернету), тому ваші розмови в повній безпеці.'),
            (_MAG,   '◈  БАЗА КОМАНД',
             'Команд дуже багато, і всі не запам\'ятати — скажіть «покажи всі команди» (або «база команд») будь-якої миті, і Джарвіс відкриє повний список із прикладами фраз і поясненнями.'),
            (_CYAN,  '🗣  КІЛЬКА СПОСОБІВ СКАЗАТИ ОДНЕ Й ТЕ САМЕ',
             'Не потрібно запам\'ятовувати точне формулювання — більшість команд розуміються кількома варіантами («пауза» = «зупини» = «стоп»). У базі команд для кожної дії показано одразу декілька прикладів.'),
            (_GREEN, '❓  ЯКЩО ДЖАРВІС НЕ ЗРОЗУМІВ',
             'Якщо фраза не розпізналась, Джарвіс скаже про це вголос («не розчув, повторіть») замість того, щоб мовчати — так завжди зрозуміло, почув він вас чи ні.'),
            (_AMBER, '🚀  КАРТИНКА ДНЯ ВІД NASA',
             'Скажіть «покажи картинку дня від наса» — Джарвіс завантажить астрономічне фото чи відео дня NASA з описом і покаже прямо у своєму вікні, без браузера.'),
            (_MAG,   '🎬  ВИБІР З КІЛЬКОХ ВІДЕО',
             'Кажете «увімкни пісню X» — якщо на YouTube знайшлося кілька схожих відео (кліп, live, кавер), Джарвіс покаже картки з прев\'ю і запропонує обрати: кліком або голосом («друге»).'),
        ]
    else:
        CARDS = [
            (_CYAN,  '🗣  ОТВЕТЫ НА ИМЯ (WAKE WORD)',
             'Скажите «Джарвис» — система вас услышит и останется активной некоторое время без повтора имени (по умолчанию 30 секунд, время настраивается в Настройках → Голос). Там же можно выбрать: либо он отвечает «Да, сэр» только 1 раз при пробуждении (не спамит на имя), либо всегда отвечает на имя.'),
            (_GREEN, '🧹  УБОРКА И СИСТЕМА',
             'Скажите «Джарвис, приберись» — он очистит кэш браузеров, временные файлы и память. Также можно голосом выключать ПК, управлять Bluetooth и Wi-Fi.'),
            (_MAG,   '🌐  ИНТЕРНЕТ И МЕДИА',
             '«Открой ютуб», «Открой новую вкладку» или «Сделай погромче». Джарвис сам найдёт всё в интернете и поможет управлять просмотром без мышки.'),
            (_AMBER, '🎮  ИГРОВОЙ РЕЖИМ (ETS2)',
             'Играете за рулём? Скажите «Статус грузовика» или «Круиз-контроль на 90», и Джарвис мгновенно выполнит действия в игре, не отвлекая от дороги.'),
            (_CYAN,  '📝  ГОЛОСОВАЯ ДИКТОВКА',
             'Поставьте курсор в чат или документ и включите режим диктовки. Джарвис будет печатать всё, что вы говорите, сам расставляя знаки препинания.'),
            (_GREEN, '⏰  УМНЫЙ ПОМОЩНИК',
             '«Напомни выключить духовку через 20 минут» или «Выключи компьютер через час». Джарвис всё запомнит и вовремя выведет сообщение на экран.'),
            (_MAG,   '⚙️  ГДЕ ИСКАТЬ НАСТРОЙКИ?',
             'Нажмите на кнопку с шестеренкой внизу или скажите «Открой настройки». Там можно откалибровать микрофон, если Джарвис вас плохо слышит.'),
            (_AMBER, '🔒  ЗАЧЕМ ЭТО НУЖНО?',
             'Чтобы управлять ПК со свободными руками! При этом Джарвис работает локально (без интернета), поэтому ваши разговоры в полной безопасности.'),
            (_MAG,   '◈  БАЗА КОМАНД',
             'Команд очень много, и все не запомнить — скажите «покажи все команды» (или «база команд») в любой момент, и Джарвис откроет полный список с примерами фраз и описанием.'),
            (_CYAN,  '🗣  НЕСКОЛЬКО СПОСОБОВ СКАЗАТЬ ОДНО И ТО ЖЕ',
             'Не нужно запоминать точную формулировку — большинство команд понимаются несколькими вариантами («пауза» = «останови» = «стоп»). В базе команд для каждого действия сразу показано несколько примеров.'),
            (_GREEN, '❓  ЕСЛИ ДЖАРВИС НЕ ПОНЯЛ',
             'Если фраза не распозналась, Джарвис скажет об этом вслух («не расслышал, повторите») вместо того, чтобы молчать — так всегда понятно, услышал он вас или нет.'),
            (_AMBER, '🚀  КАРТИНКА ДНЯ ОТ NASA',
             'Скажите «покажи картинку дня от наса» — Джарвис скачает астрономическое фото или видео дня NASA с описанием и покажет прямо в своём окне, без браузера.'),
            (_MAG,   '🎬  ВЫБОР ИЗ НЕСКОЛЬКИХ ВИДЕО',
             'Говорите «включи песню X» — если в YouTube нашлось несколько похожих видео (клип, live, кавер), Джарвис покажет карточки с превью и предложит выбрать: кликом или голосом («второе»).'),
        ]

    grid = tk.Frame(center_wrap, bg=_BG)
    grid.pack(fill='both', expand=True, padx=_px(8), pady=_px(6))
    grid.columnconfigure(0, weight=1)
    grid.columnconfigure(1, weight=1)

    label_widgets: list[tk.Label] = []

    for idx, (accent, title, body_text) in enumerate(CARDS):
        r, c = divmod(idx, 2)
        card = tk.Frame(grid, bg=_BG, highlightbackground=_blend(accent, 0.35), highlightthickness=1)
        card.grid(row=r, column=c, padx=_px(8), pady=_px(8), sticky='nsew')
        inner_card = tk.Frame(card, bg=_blend(accent, 0.04))
        inner_card.pack(fill='both', expand=True, padx=1, pady=1)

        tk.Label(inner_card, text=title, bg=_blend(accent, 0.04), fg=accent,
                 font=(F, _sf(12), 'bold'), anchor='w',
                 justify='left').pack(fill='x', padx=_px(14), pady=(_px(14), _px(6)))
        tk.Frame(inner_card, bg=_blend(accent, 0.18), height=1).pack(fill='x', padx=_px(14), pady=(0, _px(8)))
        lbl = tk.Label(inner_card, text=body_text, bg=_blend(accent, 0.04), fg=_TEXT,
                       font=(F, _sf(11)), anchor='nw',
                       justify='left', wraplength=_px(360))
        lbl.pack(fill='both', expand=True, padx=_px(14), pady=(0, _px(16)))
        label_widgets.append(lbl)

    def _on_grid_resize(e=None):
        try:
            w = center_wrap.winfo_width()
            if w > 100:
                col_w = max(100, w // 2 - _px(60))
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
    
    def _open_settings():
        try:
            from ui.dialogs.settings_dlg import open_settings
            open_settings(hud)
        except Exception:
            pass

    def _open_deck():
        try:
            hud._open_deck()
        except Exception:
            pass

    # Pack the buttons (side='right') before the footer label so they always
    # get their required space; the label is packed last with fill='x' and
    # wraplength so it shrinks/wraps into whatever room is left instead of
    # pushing the buttons past the window edge on narrow/zoomed layouts.
    # CTK widgets automatically scale by zoom_factor, so pass base logical pixels
    ctk.CTkButton(bot, text=i18n.tr('welcome.settings_btn'), command=_open_settings,
                  height=JStyle.H_LARGE, font=(F, 12),
                  fg_color='transparent', hover_color=_blend(_DIM, 0.1),
                  text_color=_DIM, border_color=_blend(_DIM, 0.3),
                  border_width=2, corner_radius=JStyle.RAD_PANEL).pack(side='right', padx=(_px(4), _px(14)), pady=_px(10))

    ctk.CTkButton(bot, text=i18n.tr('welcome.deck_btn'), command=_open_deck,
                  height=JStyle.H_LARGE, font=(F, 12),
                  fg_color='transparent', hover_color=_blend(_MAG, 0.1),
                  text_color=_MAG, border_color=_blend(_MAG, 0.3),
                  border_width=2, corner_radius=JStyle.RAD_PANEL).pack(side='right', padx=(_px(4), _px(4)), pady=_px(10))

    ctk.CTkButton(bot, text=i18n.tr('dialog.continue'), command=win.destroy,
                  height=JStyle.H_LARGE, font=(F, 13, 'bold'),
                  fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.28),
                  text_color=_CYAN, border_color=_blend(_CYAN, 0.65),
                  border_width=2, corner_radius=JStyle.RAD_PANEL).pack(side='right', padx=(_px(14), _px(4)), pady=_px(10))

    footer_lbl = tk.Label(bot, text=i18n.tr('welcome.footer_text'),
                           bg=_PANEL, fg=_DIM, font=(F, _sf(10)), anchor='w', justify='left')
    footer_lbl.pack(side='left', fill='x', expand=True, padx=_px(20), pady=_px(14))

    def _on_footer_resize(e=None):
        try:
            w = bot.winfo_width()
            if w > 100:
                footer_lbl.configure(wraplength=max(100, w - _px(420)))
        except Exception:
            pass

    bot.bind('<Configure>', lambda e: _on_footer_resize())
    win.after(200, _on_footer_resize)

    win.grab_set()
    win.focus_set()

