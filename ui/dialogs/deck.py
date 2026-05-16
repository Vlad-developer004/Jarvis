from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from typing import Optional
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _make_resizable
from ..hud_widgets import _HudScrollbar
from ..hud_commands import _COMMANDS
from core.extensions import ExtensionManager

def open_deck(hud, reopen: bool = False) -> None:
    if not reopen and hud._deck_win and hud._deck_win.winfo_exists():
        hud._deck_win.lift()
        return
    if reopen and hud._deck_win and hud._deck_win.winfo_exists():
        hud._deck_win.destroy()
        
    win = tk.Toplevel(hud.root)
    hud._deck_win = win
    hud._track_subwin('deck', win, lambda: open_deck(hud, reopen=True))
    
    win.configure(bg=_BG)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)

    _W = int(min(1100 * hud.zoom_factor, win.winfo_screenwidth() * 0.95))
    _H = int(min(win.winfo_screenheight() - 80, win.winfo_screenheight() * 0.90))
    _center_window(win, _W, _H)
    
    # Минимальный размер для корректного отображения плиток
    win.minsize(hud._px(500), hud._px(400))
    
    win.resizable(True, True)

    def _close():
        hud._deck_win = None
        win.destroy()

    inner_root = tk.Frame(win, bg=_BG, bd=0)
    inner_root.pack(fill="both", expand=True)

    # THE FAMOUS AMBER LINE
    tk.Frame(inner_root, bg=_AMBER, height=2).pack(fill='x')

    header = tk.Frame(inner_root, bg=_PANEL, height=hud._px(50))
    header.pack(fill="x")
    
    tk.Label(header, text=i18n.tr('dialogs.deck.title'), font=(hud._F, JStyle.TEXT_BODY, "bold"),
             fg=_AMBER, bg=_PANEL).pack(side="left", padx=20)
             
    win.lift()
    win.focus_force()

    # Redefine win for legacy code compatibility inside this function
    win_for_content = inner_root
    
    _f11 = JStyle.TEXT_BODY
    _f12 = JStyle.TEXT_H2
    _f9 = JStyle.TEXT_BODY
    _f10 = JStyle.TEXT_BODY
    _f13 = JStyle.TEXT_H2
    _f14 = JStyle.TEXT_H2
    _f16 = hud._fs(19)

    tk.Label(win_for_content, text=i18n.tr('dialogs.deck.subtitle'), bg=_BG, fg=_TEXT, font=(hud._F, _f11)).pack(pady=(hud._px(10), 0))
    tk.Frame(win_for_content, bg=_SEP, height=hud._px(1)).pack(fill='x', padx=hud._px(20), pady=(hud._px(10), hud._px(6)))
    
    search_f = tk.Frame(win_for_content, bg=_BG)
    search_f.pack(fill='x', padx=hud._px(20), pady=(0, hud._px(8)))
    search_entry = ctk.CTkEntry(
        search_f,
        placeholder_text=i18n.tr('dialogs.deck.search_placeholder'),
        font=(hud._F, JStyle.TEXT_BODY),
        fg_color=_PANEL,
        text_color=_CYAN,
        placeholder_text_color=_blend(_CYAN, 0.4),
        border_color=_blend(_CYAN, 0.3),
        border_width=1,
        corner_radius=JStyle.RAD_PANEL,
        height=JStyle.H_NORM + 4
    )
    search_entry.pack(side='left', fill='x', expand=True)
    
    # --- Sorting Controls ---
    sort_f = tk.Frame(search_f, bg=_BG)
    sort_f.pack(side='right', padx=(10, 0))
    
    _sort_mode = tk.StringVar(value='cat') # 'cat', 'ru', 'en'
    
    def _cycle_sort():
        modes = ['cat', 'ru', 'en']
        cur = _sort_mode.get()
        idx = (modes.index(cur) + 1) % len(modes)
        new_mode = modes[idx]
        _sort_mode.set(new_mode)
        
        lbls = {'cat': i18n.tr('dialogs.deck.sort_by_category'), 'ru': i18n.tr('dialogs.deck.sort_a_z'), 'en': i18n.tr('dialogs.deck.sort_a_z_id')}
        sort_btn.configure(text=lbls[new_mode])
        _build_cards(search_entry.get())

    sort_btn = ctk.CTkButton(
        sort_f,
        text=i18n.tr('dialogs.deck.sort_by_category'),
        command=_cycle_sort,
        width=hud._px(160),
        height=JStyle.H_NORM + 4,
        font=(hud._F, hud._fs(8), 'bold'),
        fg_color=_blend(_AMBER, 0.1),
        hover_color=_blend(_AMBER, 0.2),
        text_color=_TEXT,
        border_color=_blend(_AMBER, 0.3),
        border_width=1,
        corner_radius=JStyle.RAD_PANEL
    )
    sort_btn.pack()

    search_entry.bind('<KeyRelease>', lambda e: _build_cards(search_entry.get()))
    
    tk.Frame(win_for_content, bg=_SEP, height=hud._px(1)).pack(fill='x', padx=hud._px(20), pady=(0, hud._px(4)))
    
    scroll_outer = tk.Frame(win_for_content, bg=_BG)
    scroll_outer.pack(fill='both', expand=True, padx=hud._px(10), pady=hud._px(4))
    
    canvas = tk.Canvas(scroll_outer, bg=_BG, highlightthickness=0, yscrollincrement=1)
    canvas.pack(side='left', fill='both', expand=True)
    _sb = _HudScrollbar(scroll_outer, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=_sb.set)
    
    def _on_wheel(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(int(-e.delta / 4), 'units')
            
    inner = tk.Frame(canvas, bg=_BG)
    _inner_id = canvas.create_window(0, 0, anchor='nw', window=inner)
    
    def _update_scroll(*_):
        canvas.configure(scrollregion=(0, 0, inner.winfo_reqwidth(), inner.winfo_reqheight()))
        
    def _on_canvas_resize(e):
        if not canvas.winfo_exists(): return
        canvas.itemconfigure(_inner_id, width=e.width)
        _update_scroll()
        new_cols = _cols_for_width(e.width)
        if new_cols != _last_cols[0]:
            if _resize_after[0]:
                win.after_cancel(_resize_after[0])
            _resize_after[0] = win.after(100, lambda: _build_cards(search_entry.get()))

    inner.bind('<Configure>', _update_scroll)
    canvas.bind('<Configure>', _on_canvas_resize)
    win.bind('<MouseWheel>', _on_wheel)

    _ext_d = ExtensionManager()
    
    # --- Dynamic Command Loading from core.nlp.commands ---
    from core.nlp.commands import COMMAND_PATTERNS, CANON_SIMPLE
    
    # Pre-defined metadata for commands
    CMD_META = {
        'wake': ('Активация', 'Пробуждение ассистента из спящего режима для приема команд.', 'джарвис'),
        'media_pause': ('Медиа: Пауза', 'Мгновенная остановка видео, музыки или движения курсора мыши.', 'пауза'),
        'media_play_youtube': ('YouTube: Продолжить', 'Возобновление воспроизведения в активной вкладке YouTube.', 'продолжай в ютубе'),
        'media_pause_youtube': ('YouTube: Пауза', 'Остановка воспроизведения видео в браузере на YouTube.', 'пауза в ютубе'),
        'media_play_browser': ('Браузер: Плей', 'Возобновление воспроизведения в любом активном браузере.', 'продолжить в браузере'),
        'media_pause_browser': ('Браузер: Пауза', 'Остановка воспроизведения медиа-контента в браузере.', 'пауза в браузере'),
        'yt_full': ('YouTube: Полный экран', 'Переключение плеера YouTube в полноэкранный режим (клавиша F).', 'полный экран'),
        'max_win': ('Окно: Развернуть', 'Развертывание текущего активного окна на весь экран (Win+Up).', 'на весь экран'),
        'yt_fwd': ('YouTube: Вперед', 'Перемотка видео на 5-10 секунд вперед в активной вкладке.', 'вперед'),
        'yt_bwd': ('YouTube: Назад', 'Перемотка видео на 5-10 секунд назад в активной вкладке.', 'назад'),
        'context_close': ('Закрыть/Отмена', 'Закрытие текущей вкладки браузера (Ctrl+W) или отмена диалога.', 'закрой'),
        'yt_next': ('YouTube: Следующее', 'Переход к следующему видео в плейлисте или рекомендациях.', 'следующее видео'),
        'yt_prev': ('YouTube: Предыдущее', 'Возврат к предыдущему просмотренному видео.', 'предыдущее видео'),
        'vol_up': ('Громкость: Выше', 'Увеличение общей системной громкости на 4% за одну команду.', 'громче'),
        'vol_down': ('Громкость: Ниже', 'Снижение общей системной громкости на 4% за одну команду.', 'тише'),
        'screenshot': ('Скриншот', 'Захват всего экрана и сохранение в папку Изображения/Jarvis.', 'скриншот'),
        'mouse_right': ('Мышь: Вправо', 'Начало непрерывного движения курсора вправо до команды «стоп».', 'правее'),
        'mouse_left': ('Мышь: Влево', 'Начало непрерывного движения курсора влево до команды «стоп».', 'левее'),
        'mouse_up': ('Мышь: Вверх', 'Начало непрерывного движения курсора вверх до команды «стоп».', 'выше'),
        'mouse_down': ('Мышь: Вниз', 'Начало непрерывного движения курсора вниз до команды «стоп».', 'ниже'),
        'mouse_faster': ('Мышь: Быстрее', 'Увеличение скорости текущего движения курсора в 1.5 раза.', 'быстрее'),
        'mouse_slower': ('Мышь: Медленнее', 'Снижение скорости текущего движения курсора для точности.', 'медленнее'),
        'mouse_click': ('Мышь: Клик', 'Эмуляция нажатия левой кнопки мыши в текущей позиции.', 'клик'),
        'mouse_dblclick': ('Мышь: Двойной клик', 'Быстрое двойное нажатие левой кнопки мыши.', 'двойной клик'),
        'mouse_stop': ('Мышь: Стоп', 'Мгновенная остановка любого движения курсора мыши.', 'стоп'),
        'praise': ('Похвала', 'Ответная реакция ассистента на благодарность пользователя.', 'молодец'),
        'restart': ('Перезагрузка ПК', 'Полная перезагрузка операционной системы Windows.', 'перезагрузка'),
        'clip_copy': ('Буфер: Копировать', 'Копирование выделенного объекта (эмуляция Ctrl+C).', 'скопируй'),
        'clip_paste': ('Буфер: Вставить', 'Вставка содержимого из буфера обмена (эмуляция Ctrl+V).', 'вставь'),
        'clip_cut': ('Буфер: Вырезать', 'Вырезание выделенного объекта (эмуляция Ctrl+X).', 'вырежи'),
        'undo': ('Отменить', 'Отмена последнего действия в приложении (эмуляция Ctrl+Z).', 'отмени'),
        'redo': ('Повторить', 'Повтор ранее отмененного действия (эмуляция Ctrl+Y).', 'повтори действие'),
        'select_all': ('Выделить всё', 'Выделение всего текста или файлов в окне (Ctrl+A).', 'выдели всё'),
        'clip_history': ('История буфера', 'Вызов системного окна истории буфера обмена Windows.', 'буфер обмена'),
        'clip_paste_last': ('Вставить последнее', 'Вставка самого последнего скопированного элемента.', 'вставь последний элемент'),
        'clip_paste_prev': ('Вставить старое', 'Вставка предпоследнего элемента из истории буфера.', 'вставь предпоследний элемент'),
        'dictation_on': ('Диктовка', 'Режим ввода текста голосом в любое текстовое поле.', 'диктовка'),
        'empty_trash': ('Очистить корзину', 'Полное удаление всех файлов из системной корзины Windows.', 'очисти корзину'),
        'create_folder': ('Создать папку', 'Создание новой папки в активном окне проводника.', 'создай папку'),
        'create_word_doc': ('Создать документ', 'Создание и открытие нового файла Word или Excel.', 'создай документ'),
        'delete_folder': ('Удалить папку', 'Удаление текущей открытой папки в корзину.', 'удали папку'),
        'note_save': ('Заметка', 'Быстрое сохранение продиктованного текста в файл заметок.', 'запиши'),
        'cancel_reminder': ('Отмена таймера', 'Остановка активного напоминания или таймера.', 'отмени напоминание'),
        'ocr_screen': ('Распознать экран', 'Сканирование экрана и извлечение текста в буфер обмена.', 'прочитай экран'),
        'ocr_last': ('Текст со скрина', 'Извлечение текста из самого последнего сделанного скриншота.', 'текст со скриншота'),
        'explorer_goto': ('Проводник: Папка', 'Быстрый переход в папки (Загрузки, Видео, Документы и др.).', 'открой загрузки'),
        'recent_doc': ('Последний Word', 'Поиск и открытие последнего измененного файла .docx.', 'открой последний документ'),
        'recent_sheet': ('Последний Excel', 'Поиск и открытие последнего измененного файла .xlsx.', 'открой последнюю таблицу'),
        'recent_pres': ('Последний PPT', 'Поиск и открытие последней презентации .pptx.', 'открой последнюю презентацию'),
        'recent_any': ('Последний файл', 'Открытие любого самого последнего измененного файла.', 'открой последний файл'),
        'open_last_video': ('Последнее видео', 'Поиск последнего записанного видео (напр. в OBS или Camera).', 'открой последнее видео'),
        'yt_last_watched': ('История YouTube', 'Открытие страницы истории просмотров в браузере.', 'открой историю ютуба'),
        'open_task_manager': ('Диспетчер задач', 'Запуск системного монитора процессов (Ctrl+Shift+Esc).', 'диспетчер задач'),
        'open_obs': ('Запустить OBS', 'Запуск и инициализация программы записи экрана OBS Studio.', 'открой обс'),
        'find_doc': ('Найти документ', 'Глобальный поиск документа по фрагменту названия.', 'найди документ'),
        'find_file': ('Найти файл', 'Глобальный поиск любого файла в системе.', 'найди файл'),
        'show_hud': ('Показать HUD', 'Развертывание основного интерфейса J.A.R.V.I.S.', 'покажи интерфейс'),
        'show_help': ('Справка', 'Вызов этого окна базы знаний и команд.', 'помощь'),
        'min_all': ('Свернуть всё', 'Свертывание всех окон для доступа к рабочему столу (Win+D).', 'сверни все окна'),
        'delete_file': ('Удалить файл', 'Перемещение выбранного файла в корзину.', 'удали файл'),
        'restart_jarvis': ('Рестарт Jarvis', 'Перезагрузка программного ядра ассистента.', 'перезапусти джарвиса'),
        'game_mode_on': ('Игровой режим', 'Оптимизация системы для игр и включение игровых макросов.', 'игровой режим'),
        'game_mode_off': ('Выход из игры', 'Возврат системы в обычный режим работы.', 'выйди из игры'),
        'guard_on': ('Охрана: ВКЛ', 'Активация режима слежения через веб-камеру.', 'режим охраны'),
        'guard_off': ('Охрана: ВЫКЛ', 'Деактивация режима слежения и уведомлений.', 'вольно'),
        'time_now': ('Время', 'Голосовое оповещение о текущем системном времени.', 'время'),
        'system_status': ('Статус ресурсов', 'Голосовой отчет о нагрузке на CPU, GPU и ОЗУ.', 'статус системы'),
        'audio_switch': ('Переключить звук', 'Смена устройства вывода (Колонки <-> Наушники).', 'звук на наушники'),
        'economy_on': ('Экономия энергии', 'Включение схемы электропитания с низким потреблением.', 'включи режим экономии'),
        'economy_off': ('Макс. мощь', 'Включение высокопроизводительной схемы электропитания.', 'отключи режим экономии'),
        'system_cleanup': ('Очистка диска', 'Удаление временных файлов и кэша приложений.', 'сделай уборку'),
        'internet_speed': ('Тест интернета', 'Запуск проверки скорости соединения и пинга.', 'скрость интернета'),
        'brightness_down': ('Яркость: Ниже', 'Снижение уровня подсветки монитора на 20%.', 'убавь яркость'),
        'brightness_set': ('Яркость: Уровень', 'Установка точного значения яркости в процентах.', 'яркость на [число]'),
        'listen_off': ('Спящий режим', 'Ассистент перестает слушать команды до фразы активации.', 'не слушай меня'),
        'listen_on': ('Пробуждение', 'Принудительный выход из режима ожидания.', 'слушай меня'),
        'how_are_you': ('Диалог', 'Простая беседа с ассистентом о его состоянии.', 'как дела'),
        'download_video': ('Скачать ролик', 'Загрузка текущего видео из браузера на жесткий диск.', 'скачай это видео'),
        'save_video': ('Запомнить ссылку', 'Сохранение ссылки на текущее видео во внутреннюю базу.', 'сохрани это видео'),
        'open_saved': ('Открыть закладку', 'Открытие видео из базы. Можно указать номер: «открой второе сохраненное видео».', 'открой сохраненное видео'),
        'open_youtube': ('YouTube', 'Запуск YouTube в браузере по умолчанию.', 'открой ютуб'),
        'min_win': ('Скрыть HUD', 'Свертывание интерфейса Jarvis в трей/фон.', 'скрой худ'),
        'open_settings': ('Настройки', 'Вход в панель конфигурации внешнего вида и системы.', 'открой настройки'),
        'open_keybinds': ('Макросы/Клавиши', 'Редактор голосовых макросов для приложений.', 'открой макросы'),
        'open_extensions': ('Магазин модулей', 'Управление дополнительными навыками и профилями.', 'открой расширения'),
        'open_perf': ('Мониторинг', 'Открытие детального окна графиков нагрузки ПК.', 'мониторинг ресурсов'),
        'shutdown': ('Выключить компьютер', 'Безопасное завершение работы ПК (команда shutdown /s /t 0).', 'выключи компьютер'),
        'shutdown_timer': ('Таймер выключения', 'Запланированное выключение через N минут (shutdown /s /t ...).', 'выключи компьютер через [время]'),
        'wifi_toggle': ('Wi-Fi', 'Программное включение или отключение Wi-Fi адаптера.', 'выключи вай фай'),
        'bluetooth_toggle': ('Bluetooth', 'Управление состоянием Bluetooth-модуля.', 'включи блютуз'),
        'vol_mute': ('Отключить звук', 'Мгновенное выключение звука (Mute) на всех устройствах.', 'выключи звук'),
        'vol_set': ('Громкость: Уровень', 'Установка громкости на точное значение (0-100%).', 'громкость на [число]'),
        'explorer_go_up': ('Папка: Назад', 'Переход в родительскую директорию в проводнике.', 'выйди из папки'),
        'paste_file': ('Вставить файл', 'Вставка последнего скачанного файла в текущую папку.', 'вставь файл'),
        'close_win': ('Закрыть программу', 'Принудительное закрытие активного приложения (Alt+F4).', 'закрой окно'),
        'win_snap_left': ('Окно: Влево', 'Расположение окна на левой половине экрана.', 'окно влево'),
        'win_snap_right': ('Окно: Вправо', 'Расположение окна на правой половине экрана.', 'окно вправо'),
        'weather': ('Погода', 'Запрос актуального прогноза погоды для вашего региона.', 'какая погода'),
        'reminder': ('Напоминание', 'Установка голосового напоминания через заданный интервал.', 'напомни через [время]'),
        'google_search': ('Поиск Google', 'Открытие браузера с результатами поиска по вашему запросу.', 'найди в гугле [запрос]'),
        'git_commit': ('Git: Коммит', 'Автоматический git add, git commit и git push для проекта.', 'сделай коммит'),
        'system_specs': ('Железо / Характеристики', 'Детальный отчет об установленных компонентах ПК.', 'характеристики компьютера'),
        'open_photoshop': ('Запустить Photoshop', 'Запуск Adobe Photoshop через системный ярлык.', 'открой фотошоп'),
        'open_vscode': ('Запустить VS Code', 'Открытие редактора кода Visual Studio Code.', 'открой vscode'),
        'open_browser': ('Запустить Браузер', 'Открытие веб-браузера по умолчанию.', 'открой браузер'),
        'open_discord': ('Запустить Discord', 'Запуск приложения Discord.', 'открой дискорд'),
        'open_telegram': ('Запустить Telegram', 'Запуск мессенджера Telegram.', 'открой телеграм'),
        'open_steam': ('Запустить Steam', 'Запуск игрового клиента Steam.', 'открой стим')
    }
    
    CAT_MAP = {
        'ОСНОВНЫЕ (СИСТЕМА)': ['session', 'system', 'shutdown', 'cancel_timer', 'economy', 'time_now', 'keyboard_', 'show_help', 'restart', 'guard', 'listen', 'wake', 'how_are_you', 'praise', 'open_settings', 'open_keybinds', 'open_extensions', 'open_perf'],
        'ЮТЮБ И МЕДИА': ['yt_', 'video', 'cinema', 'clipchamp', 'media', 'open_youtube', 'download_video', 'save_video', 'open_saved', 'open_last_video'],
        'ЗВУК И ЭКРАН': ['vol_', 'app_vol', 'audio_switch', 'brightness', 'screenshot', 'start_video', 'move_monitor'],
        'ПРИЛОЖЕНИЯ И ОКНА': ['app_', 'win_', 'min_', 'max_', 'close_', 'browser_tab', 'open_task_manager', 'open_obs', 'terminal', 'google_', 'git_', 'clip_', 'undo', 'redo', 'select_all', 'press_enter', 'change_layout', 'context_close'],
        'ФАЙЛЫ И ДОКУМЕНТЫ': ['folder', 'doc', 'sheet', 'pres', 'any', 'paste_file', 'create_', 'delete_', 'explorer_', 'find_', 'recent_', 'empty_trash'],
        'ИГРЫ И АВТОМАТИЗАЦИЯ': ['game_mode', 'mouse_', 'dictation_', 'note_save', 'cancel_reminder', 'reminder', 'ocr_', 'weather'],
        'ИНТЕРФЕЙС HUD': ['show_hud', 'min_win']
    }

    _commands: dict[str, list[tuple[str, str, str, str]]] = {} # pid, name, phrase, desc
    
    def _add_cmd(pid: str, name: str, phrase: str, desc: str):
        target_cat = 'РАЗНОЕ'
        for cat_name, prefixes in CAT_MAP.items():
            if any(pid.startswith(p) for p in prefixes):
                target_cat = cat_name
                break
        if target_cat not in _commands: _commands[target_cat] = []
        _commands[target_cat].append((pid, name, phrase, desc))

    # Reverse CANON_SIMPLE to pick shortest activation phrase
    canon_rev = {}
    for phrase, cid in CANON_SIMPLE.items():
        if cid not in canon_rev:
            canon_rev[cid] = []
        canon_rev[cid].append(phrase)

    seen_ids = set()
    # 1. Process COMMAND_PATTERNS
    for pat in COMMAND_PATTERNS:
        pid = pat['id']
        seen_ids.add(pid)
        name = CMD_META.get(pid, (pid.replace('_', ' ').title(), '', ''))[0]
        desc = CMD_META.get(pid, ('', pat.get('description', 'Голосовая команда'), ''))[1]
        phrase_from_meta = CMD_META.get(pid, ('', '', ''))[2]
        phrase_str = phrase_from_meta if phrase_from_meta else pat['patterns'][0].replace('{N}', '[число]')
        phrase = f"«{phrase_str}»"
        _add_cmd(pid, name, phrase, desc)

    # 2. Process CANON_SIMPLE
    for cid in canon_rev:
        if cid in seen_ids or cid == 'system_insult': continue
        if cid in CMD_META:
            name, desc, phrase_str = CMD_META[cid]
        else:
            name = cid.replace('_', ' ').title()
            desc = 'Голосовая команда'
            phrase_str = sorted(canon_rev[cid], key=len)[0]
        phrase = f"«{phrase_str}»"
        _add_cmd(cid, name, phrase, desc)

    _all_items: list[tuple[str, str, str, str, str]] = [] # cat, pid, name, phrase, desc
    for cat, items in _commands.items():
        for pid, name, phrase, desc in items:
            _all_items.append((cat, pid, name, phrase, desc))

    def _cols_for_width(w: int) -> int:
        if w >= int(1150 * hud.zoom_factor): return 3
        if w >= int(750 * hud.zoom_factor): return 2
        return 1

    def _make_card(parent, name: str, phrase: str, desc: str, cat: str = '', wrap_w: int = 300) -> tk.Frame:
        card = tk.Frame(parent, bg=_PANEL, highlightbackground=_BRD, highlightthickness=1)
        card.grid_columnconfigure(0, weight=1)
        tk.Label(card, text=name, bg=_PANEL, fg=_WHITE, font=(hud._F, _f13, 'bold'), anchor='w', wraplength=wrap_w, justify='left').grid(row=0, column=0, sticky='ew', padx=hud._px(15), pady=(hud._px(12), hud._px(4)))
        tk.Label(card, text=phrase, bg=_PANEL, fg=_CYAN, font=(hud._F, _f12, 'bold'), anchor='w', wraplength=wrap_w, justify='left').grid(row=1, column=0, sticky='ew', padx=hud._px(15))
        _desc_text = f'{desc}  ·  {cat}' if cat else desc
        tk.Label(card, text=_desc_text, bg=_PANEL, fg=_TEXT, font=(hud._F, _f10), anchor='w', wraplength=wrap_w, justify='left').grid(row=2, column=0, sticky='ew', padx=hud._px(15), pady=(hud._px(4), hud._px(12)))
        return card

    _last_cols = [0]
    _resize_after = [None]

    def _build_cards(query: str = '') -> None:
        if not inner.winfo_exists(): return
        for w in inner.winfo_children():
            w.destroy()
        canvas.yview_moveto(0)
        q = query.strip().lower()
        cols = _cols_for_width(canvas.winfo_width() or _W)
        _last_cols[0] = cols

        def _grid_section(items_with_cat) -> None:
            col_idx = 0
            cur_row_f: Optional[tk.Frame] = None
            cw = canvas.winfo_width() or _W
            card_wrap = (cw // cols) - hud._px(60)
            for name, phrase, desc, cat in items_with_cat:
                if col_idx == 0:
                    cur_row_f = tk.Frame(inner, bg=_BG)
                    cur_row_f.pack(fill='x', pady=hud._px(4))
                    for ci in range(cols):
                        cur_row_f.grid_columnconfigure(ci, weight=1)
                card = _make_card(cur_row_f, name, phrase, desc, cat, wrap_w=card_wrap)
                card.grid(row=0, column=col_idx, sticky='nsew', padx=hud._px(5))
                col_idx = (col_idx + 1) % cols

        if q:
            matched = [(cat, name, phrase, desc) for cat, pid, name, phrase, desc in _all_items if q in name.lower() or q in phrase.lower() or q in desc.lower() or q in pid.lower()]
            if not matched:
                tk.Label(inner, text='КОМАНДЫ НЕ НАЙДЕНЫ', bg=_BG, fg=_RED, font=(hud._F, _f12, 'bold')).pack(pady=hud._px(50))
            else:
                _grid_section(matched)
        else:
            mode = _sort_mode.get()
            if mode == 'cat':
                for cat, items in _commands.items():
                    tk.Label(inner, text=cat, bg=_BG, fg=_MAG, font=(hud._F, _f11, 'bold'), anchor='w').pack(fill='x', padx=hud._px(10), pady=(hud._px(24), hud._px(8)))
                    tk.Frame(inner, bg=_MAG, height=hud._px(1)).pack(fill='x', padx=hud._px(10), pady=(0, hud._px(12)))
                    _grid_section([(cat, name, phrase, desc) for pid, name, phrase, desc in items])
            elif mode == 'ru':
                # Sort all by Russian name
                sorted_items = sorted(_all_items, key=lambda x: x[2])
                _grid_section([(cat, name, phrase, desc) for cat, pid, name, phrase, desc in sorted_items])
            elif mode == 'en':
                # Sort all by English ID
                sorted_items = sorted(_all_items, key=lambda x: x[1])
                _grid_section([(cat, name, phrase, desc) for cat, pid, name, phrase, desc in sorted_items])

    _build_cards()
    # Поиск теперь привязан через KeyRelease в начале
    tk.Frame(win, bg=_CYAN, height=hud._px(2)).pack(fill='x', side='bottom')
