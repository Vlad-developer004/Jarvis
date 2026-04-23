from __future__ import annotations
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar
from ..hud_widgets import _HudScrollbar
from core.extensions import ExtensionManager

_SETTINGS_PATH = os.path.join('data', 'jarvis_settings.json')

def _load_settings():
    try:
        if os.path.exists(_SETTINGS_PATH):
            with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception: pass
    return {}

def _save_settings(s):
    try:
        os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
        with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(s, f, indent=2, ensure_ascii=False)
    except Exception: pass

def _secrets_env_path() -> str:
    try:
        import os as _os
        appdata = _os.environ.get('APPDATA', '') or _os.environ.get('LOCALAPPDATA', '')
        if appdata:
            p = os.path.join(appdata, 'Jarvis', 'secrets.env')
            try: os.makedirs(os.path.dirname(p), exist_ok=True)
            except Exception: pass
            return p
    except Exception: pass
    return os.path.abspath('.env')

_ENV_PATH = _secrets_env_path()

def _save_env_key(key: str, value: str) -> None:
    lines = []
    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, encoding='utf-8') as f: lines = f.readlines()
    found = False
    for i, line in enumerate(lines):
        if line.startswith(key + '='):
            lines[i] = f'{key}="{value}"\n'
            found = True
            break
    if not found: lines.append(f'{key}="{value}"\n')
    with open(_ENV_PATH, 'w', encoding='utf-8') as f: f.writelines(lines)

def _set_feature_module_flag(module_key: str, enabled: bool) -> None:
    s = _load_settings()
    mods = s.get('feature_modules', {})
    if not isinstance(mods, dict): mods = {}
    mods[module_key] = bool(enabled)
    s['feature_modules'] = mods
    _save_settings(s)
    try:
        from core.system import refresh_module_flags
        refresh_module_flags()
    except Exception: pass

GAME_CMD_L10N = {
    "Engine": "Двигатель (Вкл/Выкл)", "StartEngine": "Запуск двигателя", "StopEngine": "Заглушить двигатель",
    "Handbrake": "Ручной тормоз", "HandbrakeOn": "Затянуть ручник", "HandbrakeOff": "Снять с ручника",
    "CruiseControl": "Круиз-контроль", "CruiseSet": "Установить лимит круиза", "CruiseAdjust": "Настройка скорости круиза",
    "CruiseLimit": "Круиз по ограничению", "AutoCruiseOn": "Адаптивный круиз (Вкл)", "AutoCruiseOff": "Адаптивный круиз (Выкл)",
    "Differential": "Блокировка дифференциала", "AxleLift": "Подъём/Опускание оси", "Trailer": "Сцепка / Отцепка прицепа",
    "GearUp": "Повысить передачу", "GearDown": "Понизить передачу", "GearSet": "Поставить передачу (по номеру)",
    "GearReverse": "Задний ход / Реверс", "GearNeutral": "Нейтраль", "LightsMainOn": "Ближний свет (Вкл)",
    "LightsMainOff": "Ближний свет (Выкл)", "LightsHighOn": "Дальний свет (Вкл)", "LightsHighOff": "Дальний свет (Выкл)",
    "StrobeLights": "Проблесковые маячки", "Beacon": "Маячок / Мигалка", "TurnLeft": "Левый поворотник",
    "TurnRight": "Правый поворотник", "Hazard": "Аварийная сигнализация", "Horn": "Звуковой сигнал",
    "AirHorn": "Пневматический сигнал", "WipersOn": "Стеклоочистители (Вкл)", "WipersOff": "Стеклоочистители (Выкл)",
    "WipersMedium": "Стеклоочистители (Средне)", "WipersFast": "Стеклоочистители (Быстро)",
    "InfoScreen": "Инфо-экран / Бортовой ПК", "Navigator": "Карта / Навигатор", "Action": "Действие / Взаимодействие",
    "GoToSleep": "Лечь спать", "WakeUp": "Проснуться / Поехали", "CloseGame": "Выход из игры",
    "PrepareForTrip": "Подготовка к рейсу", "Shutdown": "Конец рейса / Глушим всё", "BreakTime": "Остановка на отдых",
    "ResumeFromBreak": "Продолжить после отдыха", "BadWeather": "Режим плохой погоды", "ClearWeather": "Режим ясной погоды",
    "EmergencyStop": "Экстренная остановка", "NightDriveMode": "Ночной режим освещения", "MorningMode": "Утренний режим (Свет выкл)",
    "CityDriveMode": "Городской режим", "HighwayMode": "Трассовый режим", "LoadingDock": "Режим погрузки/разгрузки",
    "FogMode": "Режим тумана", "Overtake": "Манёвр обгона", "ThankYou": "Благодарность (Аварийка)",
}

def _load_game_commands(filename: str) -> list[dict]:
    path = os.path.join("data", "game_profiles", filename)
    if not os.path.exists(path): return []
    try:
        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
        spells = data.get("spells", [])
        cmds = []
        for s in spells:
            name, variants = s.get("name", ""), s.get("variants", [])
            if not variants: continue
            main_desc = GAME_CMD_L10N.get(name, name)
            cmds.append({"say": variants[0], "do": main_desc, "search": " ".join(variants).lower() + " " + main_desc.lower()})
        return cmds
    except Exception: return []

def _ask_chat_id(parent, hud, on_confirm):
    dlg = tk.Toplevel(parent); dlg.title('Настройка JARVIS'); dlg.configure(bg=_BG)
    W, H = 500, 380
    dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+150+110'); dlg.grab_set(); dlg.resizable(False, False)
    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(dlg, text='⦿  ОХРАННАЯ КАМЕРА', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(16, 4))
    tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(0, 10))
    lines = ['Для получения фото на телефон при обнаружении движения', 'введите ваш личный Telegram Chat ID.', '', 'Как узнать Chat ID:', '1. Найти @userinfobot в Telegram', '2. Нажать /start — бот пришлет ID']
    for line in lines:
        col = _CYAN if 'Как' in line else _TEXT if line else _BG
        tk.Label(dlg, text=line, bg=_BG, fg=col, font=(hud._F, hud._fs(10), 'bold' if 'Как' in line else '')).pack(anchor='w', padx=28)
    tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(12, 10))
    entry_var = tk.StringVar(); entry = ctk.CTkEntry(dlg, textvariable=entry_var, placeholder_text='Chat ID', font=(hud._F, hud._fs(11)), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=36)
    entry.pack(fill='x', padx=28, pady=(0, 15)); _bind_ctk_entry_clipboard(dlg, entry, hud); entry.focus_set()
    def _confirm():
        cid = entry_var.get().strip()
        if not cid.lstrip('-').isdigit(): entry.configure(border_color=_RED); return
        on_confirm(cid); dlg.destroy()
    ctk.CTkButton(dlg, text='СОХРАНИТЬ', font=(hud._F, hud._fs(11), 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=28, pady=(0, 6))
    ctk.CTkButton(dlg, text='ОТМЕНА', font=(hud._F, hud._fs(10)), height=30, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=28)
    dlg.bind('<Return>', lambda _: _confirm())

def _ask_calendar_setup(parent, hud, on_done=None):
    dlg = tk.Toplevel(parent); dlg.title('Настройка календаря'); dlg.configure(bg=_BG)
    W, H = 560, 520
    dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+150+90'); dlg.grab_set(); dlg.minsize(int(440*hud.zoom_factor), int(400*hud.zoom_factor)); dlg.resizable(True, True)
    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(dlg, text='📅  НАСТРОЙКА КАЛЕНДАРЯ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(14, 4))
    tk.Label(dlg, text='Добавьте файлы (.ics) или ссылки.', bg=_BG, fg=_TEXT, font=(hud._F, hud._fs(10)), wraplength=480, justify='left').pack(anchor='w', padx=24, pady=(0, 12))
    s0 = _load_settings(); sources_var = list(s0.get('calendar_sources', []) if isinstance(s0.get('calendar_sources'), list) else [])
    list_frame = tk.Frame(dlg, bg=_PANEL, highlightthickness=1, highlightbackground=_blend(_CYAN, 0.3)); list_frame.pack(fill='both', expand=True, padx=24, pady=(0, 10))
    list_inner = tk.Frame(list_frame, bg=_PANEL); list_inner.pack(fill='both', expand=True, padx=8, pady=8)
    def _refresh_list():
        for w in list_inner.winfo_children(): w.destroy()
        for i, src in enumerate(sources_var):
            ref = src.get('url') or src.get('path') or '(пусто)'
            row = tk.Frame(list_inner, bg=_PANEL); row.pack(fill='x', pady=2)
            tk.Label(row, text=ref, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(9)), anchor='w').pack(side='left', fill='x', expand=True, padx=(6, 6))
            ctk.CTkButton(row, text='✕', width=28, height=24, font=(hud._F, hud._fs(10)), fg_color=_blend(_RED, 0.12), hover_color=_blend(_RED, 0.3), text_color=_RED, command=lambda idx=i: (sources_var.pop(idx), _refresh_list())).pack(side='right')
    _refresh_list()
    add_frame = tk.Frame(dlg, bg=_BG); add_frame.pack(fill='x', padx=24, pady=(0, 8))
    tk.Label(add_frame, text='Ссылка или путь к .ics файлу:', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(10), 'bold')).pack(anchor='w', pady=(0, 4))
    entry_row = tk.Frame(add_frame, bg=_BG); entry_row.pack(fill='x')
    add_ent = ctk.CTkEntry(entry_row, height=34, font=(hud._F, hud._fs(11)), fg_color=_blend(_CYAN, 0.08), border_color=_blend(_CYAN, 0.35), border_width=1, text_color=_WHITE, placeholder_text='https://.../.ics  или  C:\\путь\\...')
    add_ent.pack(side='left', fill='x', expand=True, padx=(0, 8)); _bind_ctk_entry_clipboard(dlg, add_ent, hud)
    def _add_from_entry():
        val = (add_ent.get() or '').strip()
        if not val: return
        if val.lower().startswith(('http://', 'https://', 'webcal://')): sources_var.append({'url': val})
        else: sources_var.append({'path': val})
        add_ent.delete(0, 'end'); _refresh_list()
    ctk.CTkButton(entry_row, text='ДОБАВИТЬ', width=110, height=34, font=(hud._F, hud._fs(10), 'bold'), fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.35), text_color=_CYAN, command=_add_from_entry).pack(side='left')
    def _confirm():
        s = _load_settings(); s['calendar_sources'] = sources_var; _save_settings(s)
        if on_done: on_done()
        dlg.destroy()
    ctk.CTkButton(dlg, text='СОХРАНИТЬ', font=(hud._F, hud._fs(11), 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=24, pady=(0, 6))
    ctk.CTkButton(dlg, text='ОТМЕНА', font=(hud._F, hud._fs(10)), height=30, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=24, pady=(0, 12))

def _ask_mail_setup(parent, hud, on_done):
    dlg = tk.Toplevel(parent); dlg.title('Подключение почты к JARVIS'); dlg.configure(bg=_BG)
    W, H = 560, 640
    dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+150+70'); dlg.grab_set(); dlg.minsize(int(480*hud.zoom_factor), int(520*hud.zoom_factor)); dlg.resizable(True, True)
    tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(dlg, text='✉  ПОДКЛЮЧЕНИЕ ПОЧТЫ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(14, 4))
    tk.Label(dlg, text='Данные хранятся только на вашем компьютере.', bg=_BG, fg=_TEXT, font=(hud._F, hud._fs(10)), wraplength=480, justify='left').pack(anchor='w', padx=24, pady=(0, 12))
    s0 = _load_settings(); ma0 = s0.get('mail_account') if isinstance(s0.get('mail_account'), dict) else {}
    email_var, pwd_var = tk.StringVar(value=str(ma0.get('email') or '')), tk.StringVar(value=str(ma0.get('password') or ''))
    imap_var, smtp_var = tk.StringVar(value=str(ma0.get('imap_host') or '')), tk.StringVar(value=str(ma0.get('smtp_host') or ''))
    tk.Label(dlg, text='1. Адрес почты', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
    ent_email = ctk.CTkEntry(dlg, textvariable=email_var, placeholder_text='name@gmail.com', font=(hud._F, hud._fs(11)), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=36)
    ent_email.pack(fill='x', padx=24, pady=(5, 12)); _bind_ctk_entry_clipboard(dlg, ent_email, hud)
    tk.Label(dlg, text='2. Пароль приложения', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
    ent_pwd = ctk.CTkEntry(dlg, textvariable=pwd_var, placeholder_text='Пароль приложения', show='*', font=(hud._F, hud._fs(11)), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=36)
    ent_pwd.pack(fill='x', padx=24, pady=(5, 12)); _bind_ctk_entry_clipboard(dlg, ent_pwd, hud)
    tk.Label(dlg, text='3. Серверы (если не Gmail)', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
    ent_imap = ctk.CTkEntry(dlg, textvariable=imap_var, placeholder_text='IMAP (imap.yandex.ru)', font=(hud._F, hud._fs(10)), fg_color=_PANEL, text_color=_WHITE, border_color=_SEP, border_width=1, corner_radius=2, height=32)
    ent_imap.pack(fill='x', padx=24, pady=(4, 6)); _bind_ctk_entry_clipboard(dlg, ent_imap, hud)
    ent_smtp = ctk.CTkEntry(dlg, textvariable=smtp_var, placeholder_text='SMTP (smtp.yandex.ru)', font=(hud._F, hud._fs(10)), fg_color=_PANEL, text_color=_WHITE, border_color=_SEP, border_width=1, corner_radius=2, height=32)
    ent_smtp.pack(fill='x', padx=24, pady=(4, 8)); _bind_ctk_entry_clipboard(dlg, ent_smtp, hud)
    def _confirm():
        em, pw, ih, sh = email_var.get().strip(), pwd_var.get().strip(), imap_var.get().strip(), smtp_var.get().strip()
        if not em or '@' not in em: return
        if not pw: return
        try:
            from actions.mail_client import save_mail_account
            save_mail_account(em, pw, ih, sh, 993, 587); on_done(); dlg.destroy()
        except Exception: pass
    ctk.CTkButton(dlg, text='СОХРАНИТЬ', font=(hud._F, hud._fs(11), 'bold'), height=34, fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=24, pady=(10, 6))
    ctk.CTkButton(dlg, text='ОТМЕНА', font=(hud._F, hud._fs(10)), height=30, fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=24, pady=(0, 12))

def _open_commands_help(parent, hud, meta: dict) -> None:
    dlg = getattr(hud, '_ext_cmd_win', None)
    if dlg and dlg.winfo_exists():
        dlg.deiconify(); dlg.lift(); dlg.focus_force()
        for w in dlg.winfo_children(): w.destroy()
    else:
        dlg = tk.Toplevel(parent); hud._ext_cmd_win = dlg
        W, H = 720, 600
        dlg.overrideredirect(True)
        dlg.configure(bg=_BG); 
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        dlg.geometry(f'{int(W*hud.zoom_factor)}x{int(H*hud.zoom_factor)}+{x}+{y}')

    # Draggable logic
    def _start_move(e): dlg._drag_x, dlg._drag_y = e.x, e.y
    def _do_move(e):
        nx = dlg.winfo_x() + (e.x - dlg._drag_x)
        ny = dlg.winfo_y() + (e.y - dlg._drag_y)
        dlg.geometry(f"+{nx}+{ny}")

    from ui.hud_themes import get_current_theme_name
    _theme = get_current_theme_name()
    header = tk.Frame(dlg, bg=_PANEL, height=60); header.pack(fill='x')
    header.bind("<Button-1>", _start_move)
    header.bind("<B1-Motion>", _do_move)
    
    tk.Label(header, text="◈", bg=_PANEL, fg=_CYAN, font=(hud._F, hud._fs(18))).pack(side='left', padx=(20, 8))
    lb_title = tk.Label(header, text=f'СПИСОК КОМАНД: {meta.get("name", "").upper()}', bg=_PANEL, fg=_CYAN, font=(hud._F, hud._fs(13), 'bold'))
    lb_title.pack(side='left')
    lb_title.bind("<Button-1>", _start_move); lb_title.bind("<B1-Motion>", _do_move)
    
    # Larger, more stylish close button
    ctk.CTkButton(header, text='✕', width=54, height=54, fg_color="transparent", hover_color=_blend(_RED, 0.4), text_color=_RED, font=(hud._F, hud._fs(15), 'bold'), command=dlg.destroy).pack(side='right', padx=15)
    tk.Frame(dlg, bg=_CYAN, height=1).pack(fill='x')

    canvas_f = tk.Frame(dlg, bg=_BG); canvas_f.pack(fill='both', expand=True)
    canvas2 = tk.Canvas(canvas_f, bg=_BG, highlightthickness=0); 
    sb2 = _HudScrollbar(canvas_f, canvas2, color=_CYAN)
    canvas2.configure(yscrollcommand=sb2.set); canvas2.pack(side='left', fill='both', expand=True)
    
    # Absolute fill: Window width is 720, so 720 it is.
    inner2 = tk.Frame(canvas2, bg=_BG); canvas2.create_window((0, 0), window=inner2, anchor='nw', width=int(720*hud.zoom_factor))
    def _upd_scroll2(): canvas2.configure(scrollregion=canvas2.bbox('all'))
    inner2.bind('<Configure>', lambda e: _upd_scroll2())
    
    def _on_wheel2(e):
        if canvas2.winfo_exists(): canvas2.yview_scroll(-1 * (e.delta // 120), 'units')
    def _bind_wheel2(w):
        w.bind('<MouseWheel>', _on_wheel2)
        for child in w.winfo_children(): _bind_wheel2(child)

    for item in meta.get('commands', []):
        row_outer = tk.Frame(inner2, bg=_BG)
        row_outer.pack(fill='x', padx=(12, 12), pady=(0, 2))
        
        accent = tk.Frame(row_outer, bg=_CYAN, width=3)
        accent.pack(side='left', fill='y')
        
        # Consistent row background
        row_bg = _BG
        hover_bg = _blend(_CYAN, 0.1) if _theme == 'light' else "#1a222d"
        
        row = tk.Frame(row_outer, bg=row_bg)
        row.pack(side='left', fill='both', expand=True)
        
        def _on_ent_r(e, r=row, h=hover_bg): 
            r.configure(bg=h)
            for c in r.winfo_children(): c.configure(bg=h)
        def _on_lev_r(e, r=row, n=row_bg): 
            r.configure(bg=n)
            for c in r.winfo_children(): c.configure(bg=n)
        row.bind('<Enter>', _on_ent_r); row.bind('<Leave>', _on_lev_r)

        tk.Label(row, text=f"«{item.get('say', '')}»", bg=row_bg, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(side='left', padx=18, pady=10)
        tk.Label(row, text=item.get('do', ''), bg=row_bg, fg=_DIM, font=(hud._F, hud._fs(10))).pack(side='right', padx=24, pady=10)

    _bind_wheel2(dlg)

ext_mgr = ExtensionManager()

def _bind_ctk_entry_clipboard(parent, entry, hud):
    def _inner(): return getattr(entry, '_entry', None)
    def _clipboard_text() -> str:
        try:
            import pyperclip
            t = pyperclip.paste()
            if t: return str(t)
        except Exception: pass
        try: return str(parent.clipboard_get())
        except Exception: return ''
    def _first_line(s: str) -> str: return s.replace('\r\n', '\n').split('\n')[0].strip('\r\n')
    def _paste(_e=None):
        t = _first_line(_clipboard_text())
        if not t: return 'break'
        w = _inner()
        if w is not None:
            try:
                if w.selection_present(): w.delete('sel.first', 'sel.last')
                w.insert('insert', t)
            except Exception: pass
            return 'break'
        try:
            if hasattr(entry, 'selection_present') and entry.selection_present():
                entry.delete('sel.first', 'sel.last')
            entry.insert(tk.INSERT, t)
        except Exception:
            try:
                cur = entry.get()
                entry.delete(0, 'end'); entry.insert(0, cur + t)
            except Exception: pass
        return 'break'
    def _copy(_e=None):
        w = _inner()
        try:
            if w is not None and w.selection_present():
                parent.clipboard_clear(); parent.clipboard_append(w.selection_get())
            elif hasattr(entry, 'selection_present') and entry.selection_present():
                parent.clipboard_clear(); parent.clipboard_append(entry.selection_get())
        except Exception: pass
        return 'break'
    def _select_all(_e=None):
        w = _inner()
        if w is not None:
            try:
                w.select_range(0, 'end'); w.icursor('end')
            except Exception: pass
            return 'break'
        try: entry.select_range(0, 'end')
        except Exception: pass
        return 'break'
    menu = tk.Menu(parent, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, hud._fs(11)))
    menu.add_command(label='Вставить (Ctrl+V)', command=lambda: _paste())
    menu.add_command(label='Копировать (Ctrl+C)', command=lambda: _copy())
    menu.add_separator()
    menu.add_command(label='Выделить всё (Ctrl+A)', command=lambda: _select_all())
    entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    entry.bind('<Control-v>', _paste); entry.bind('<Control-V>', _paste); entry.bind('<Shift-Insert>', _paste)
    entry.bind('<Control-c>', _copy); entry.bind('<Control-C>', _copy)
    entry.bind('<Control-a>', _select_all); entry.bind('<Control-A>', _select_all)
def open_extensions(hud, reopen: bool = False) -> None:
    if not reopen and hasattr(hud, '_ext_win') and hud._ext_win and hud._ext_win.winfo_exists():
        hud._ext_win.lift()
        return
    if reopen and hasattr(hud, '_ext_win') and hud._ext_win and hud._ext_win.winfo_exists():
        hud._ext_win.destroy()
    win = tk.Toplevel(hud.root)
    hud._ext_win = win
    win.title('JARVIS 1.4 — Менеджер расширений')
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    hud._track_subwin('extensions', win, lambda: open_extensions(hud, reopen=True))





    ext_mgr.reload()


    win.iconbitmap(hud._ico_path) if hasattr(hud, '_ico_path') else None
    win.configure(bg=_BG); win.after(150, lambda: _set_dark_title_bar(win))
    _sw_scr = win.winfo_screenwidth()
    _sh_scr = win.winfo_screenheight()
    win.geometry("")
    win.resizable(False, True)
    
    def _recenter():
        win.update_idletasks()
        zf = hud.zoom_factor if hud else 1.0
        rw, rh = int(win.winfo_reqwidth() / zf), int(win.winfo_reqheight() / zf)
        win.geometry(f"{rw}x{rh}+110+70") # Extensions often stick to side
    win._recenter = _recenter
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')
    header_area = tk.Frame(win, bg=_BG)
    header_area.pack(fill='x', padx=24, pady=(16, 0))
    title_f = tk.Frame(header_area, bg=_BG)
    title_f.pack(side='left')
    tk.Label(title_f, text='⬡  ЦЕНТР РАСШИРЕНИЙ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(20), 'bold')).pack(anchor='w')
    tk.Label(title_f, text='СИСТЕМНАЯ ДИАГНОСТИКА И КОНФИГУРАЦИЯ МОДУЛЕЙ', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='w')
    search_f = tk.Frame(header_area, bg="#0d0f1e", highlightthickness=1, highlightbackground=_blend(_CYAN, 0.3))
    search_f.pack(side='right', pady=5)
    tk.Label(search_f, text='⌕', bg="#0d0f1e", fg=_CYAN, font=(hud._F, hud._fs(13))).pack(side='left', padx=(10, 4))
    search_entry = tk.Entry(search_f, bg="#0d0f1e", fg=_DIM, font=(hud._F, hud._fs(11)), insertbackground=_CYAN, borderwidth=0, width=22)
    search_entry.pack(side='left', padx=(0, 12), pady=6)
    search_entry.insert(0, 'ПОИСК МОДУЛЯ...')
    def _on_search_focus(e):
        if search_entry.get() == 'ПОИСК МОДУЛЯ...':
            search_entry.delete(0, 'end')
            search_entry.configure(fg=_WHITE)
    def _on_search_change(e):
        _refresh_cards(search_entry.get())
    search_entry.bind('<FocusIn>', _on_search_focus)
    search_entry.bind('<KeyRelease>', _on_search_change)
    tk.Frame(win, bg=_SEP, height=1).pack(fill='x', padx=24, pady=(16, 8))
    canvas = tk.Canvas(win, bg=_BG, highlightthickness=0)
    for i in range(0, 800, 40):
        canvas.create_line(i, 0, i, 1000, fill=_blend(_BG, 1.1), width=1)
        canvas.create_line(0, i, 800, i, fill=_blend(_BG, 1.1), width=1)
    sb = _HudScrollbar(win, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side='left', fill='both', expand=True, padx=(24, 0), pady=(0, 20))
    inner = tk.Frame(canvas, bg=_BG)
    _cwin = canvas.create_window((0, 0), window=inner, anchor='nw')
    def _update_scroll(*_):
        canvas.configure(scrollregion=canvas.bbox('all'))
    def _on_resize(e):
        canvas.itemconfig(_cwin, width=e.width)
        _update_scroll()
    canvas.bind('<Configure>', _on_resize)
    inner.bind('<Configure>', _update_scroll)
    def _on_wheel(e):
        if canvas.winfo_exists():
            canvas.yview_scroll(-1 * (e.delta // 120), 'units')
    def _bind_wheel(w):
        w.bind('<MouseWheel>', _on_wheel)
        for child in w.winfo_children():
            _bind_wheel(child)
    win.bind('<MouseWheel>', _on_wheel)
    canvas.bind('<MouseWheel>', _on_wheel)
    def _refresh_cards(query=None):
        def _do_ref():
            if not win.winfo_exists(): return
            try:
                for w in inner.winfo_children():
                    w.destroy()
                _build_cards(query if query != 'ПОИСК МОДУЛЯ...' else None)
                _bind_wheel(inner)
                win.after(10, _update_scroll)
                hud._rebuild_left()
            except Exception: pass
        win.after(1, _do_ref) # Safe jump to next event loop iteration
    def _build_cards(query=None):
        all_exts = ext_mgr.list_all()
        categories: dict[str, list[dict]] = {}
        for e_item in all_exts:
            if query and query.lower() not in e_item.get('name', '').lower():
                continue
            cat = e_item.get('category', 'Прочее')
            categories.setdefault(cat, []).append(e_item)
        for cat_name, items in categories.items():
            cat_f = tk.Frame(inner, bg=_BG)
            cat_f.pack(fill='x', pady=(22, 12))
            tk.Label(cat_f, text=cat_name.upper(), bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(9), 'bold')).pack(side='left', padx=(4, 10))
            tk.Frame(cat_f, bg=_SEP, height=1).pack(side='left', fill='x', expand=True, pady=4)
            for e_item in items:
                _make_card(e_item['id'], e_item)
    def _make_card(eid: str, meta: dict):
        installed = ext_mgr.is_installed(eid)
        bundled = ext_mgr.is_bundled(eid)
        brd_col_idle = _blend(_CYAN, 0.15) if not installed else _blend(_CYAN, 0.4)
        brd_col_active = _CYAN
        card = tk.Frame(inner, bg=_PANEL, highlightthickness=1, highlightbackground=brd_col_idle)
        card.pack(fill='x', pady=8, padx=(0, 16))
        strip_f = tk.Frame(card, bg=_BG, width=4)
        strip_f.pack(side='left', fill='y')
        tk.Frame(strip_f, bg=_CYAN if installed else _SEP).pack(fill='both', expand=True)
        body = tk.Frame(card, bg=_PANEL)
        body.pack(side='left', fill='both', expand=True, padx=16, pady=16)
        head = tk.Frame(body, bg=_PANEL)
        head.pack(fill='x')
        tk.Label(head, text=f'{meta.get("icon", "◇")}  {meta["name"]}', bg=_PANEL, fg=_CYAN if installed else _TEXT, font=(hud._F, hud._fs(15), 'bold'), anchor='w').pack(side='left')
        if installed:
            badge_text, badge_col = ('АКТИВНО', _CYAN)
        elif bundled:
            badge_text, badge_col = ('ГОТОВО К УСТАНОВКЕ', _AMBER)
        else:
            badge_text, badge_col = ('ОБЛАЧНЫЙ МОДУЛЬ', _DIM)
        badge_l = tk.Label(head, text=badge_text, bg=_PANEL, fg=badge_col, font=(hud._F, hud._fs(10), 'bold'))
        badge_l.pack(side='right')
        def _on_enter(e, c=card, b=badge_l):
            c.configure(highlightbackground=brd_col_active)
            if not installed:
                b.configure(fg=_CYAN)
        def _on_leave(e, c=card, b=badge_l):
            c.configure(highlightbackground=brd_col_idle)
            if not installed:
                b.configure(fg=badge_col)
        card.bind('<Enter>', _on_enter)
        card.bind('<Leave>', _on_leave)
        tk.Label(body, text=meta.get('description', ''), bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(11)), anchor='w', wraplength=int(480*hud.zoom_factor), justify='left').pack(fill='x', pady=(4, 10))
        actions_outer = tk.Frame(body, bg=_PANEL)
        actions_outer.pack(fill="x", pady=(8, 0))
        
        inner_row = tk.Frame(actions_outer, bg=_PANEL)
        inner_row.pack(anchor="center")

        has_catalog_cmds = bool(meta.get("commands"))
        is_game = meta.get("type") == "game_profile"
        
        if has_catalog_cmds or is_game:
            def _show_cmds(m=meta):
                if is_game and not m.get("commands"):
                    m["commands"] = _load_game_commands(m.get("file", ""))
                _open_commands_help(win, hud, m)
            # Standard width for row symmetry: 220 if pair, 160 if trio
            btn_w = 160 if (installed and eid == 'game_ets2') else 220
            ctk.CTkButton(
                inner_row, text="◈  КОМАНДЫ", width=btn_w, font=(hud._F, hud._fs(10), "bold"), height=48,
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.2), text_color=_CYAN,
                border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=12, command=_show_cmds,
            ).pack(side="left", padx=8)

        if installed:
            def _do_uninstall(e=eid):
                ext_mgr.uninstall(e); _refresh_cards()

            ctk.CTkButton(
                inner_row, text='🗑  УДАЛИТЬ', width=160, font=(hud._F, hud._fs(11), 'bold'), height=48,
                fg_color=_PANEL, hover_color=_blend(_RED, 0.2), text_color=_RED,
                border_color=_blend(_RED, 0.4), border_width=2, corner_radius=12, command=_do_uninstall
            ).pack(side="left", padx=8)
            
            if eid == 'feature_calendar_ics':
                def _reconfig_cal(): _ask_calendar_setup(win, hud, _refresh_cards)
                ctk.CTkButton(inner_row, text='⚙  НАСТРОЙКИ', width=160, font=(hud._F, hud._fs(10), 'bold'), height=48, fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=12, command=_reconfig_cal).pack(side="left", padx=8)
            elif eid == 'feature_mail_client':
                def _reconfig_mail(): _ask_mail_setup(win, hud, _refresh_cards)
                ctk.CTkButton(inner_row, text='⚙  НАСТРОЙКИ', width=160, font=(hud._F, hud._fs(10), 'bold'), height=48, fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=12, command=_reconfig_mail).pack(side="left", padx=8)
            elif eid == 'game_ets2':
                try:
                    from actions.ets2_telemetry_installer import is_telemetry_installed
                    tele_ok = is_telemetry_installed()
                except Exception: tele_ok = False
                
                # Explicit status for Telemetry Plugin (DLL/Library)
                t_text = "✓ DLL: АКТИВНА" if tele_ok else "⬇ DLL: ТРЕБУЕТСЯ"
                t_col = _CYAN if tele_ok else _AMBER
                
                def _do_dll_install():
                    try:
                        from actions.ets2_telemetry_installer import run_installer
                        run_installer(tk_root=win, on_done=lambda r: _refresh_cards())
                    except Exception: pass

                ctk.CTkButton(
                    inner_row, text=t_text, 
                    width=160, font=(hud._F, hud._fs(9), 'bold'), height=48, 
                    fg_color=_PANEL, hover_color=_blend(t_col, 0.2), text_color=t_col,
                    border_color=_blend(t_col, 0.4), border_width=2, corner_radius=12, 
                    command=_do_dll_install
                ).pack(side="left", padx=8)
        elif bundled:
            def _do_install(e=eid, m=meta):
                if m.get('requires_chat_id'):
                    _ask_chat_id(win, hud, lambda cid: (_save_env_key('TELEGRAM_CHAT_ID', cid), ext_mgr.install(e), _refresh_cards()))
                elif e == 'feature_mail_client':
                    s_m = _load_settings(); ma_m = s_m.get('mail_account')
                    if isinstance(ma_m, dict) and str(ma_m.get('email', '')).strip():
                        ext_mgr.install(e); _set_feature_module_flag('inbox_digest', True); _refresh_cards()
                    else: _ask_mail_setup(win, hud, lambda: (ext_mgr.install(e), _set_feature_module_flag('inbox_digest', True), _refresh_cards()))
                elif e == 'game_ets2':
                    ext_mgr.install(e); _refresh_cards()
                    def _run_dll():
                        try:
                            from actions.ets2_telemetry_installer import run_installer
                            run_installer(tk_root=win)
                        except Exception: pass
                    win.after(200, _run_dll)
                elif e == 'feature_calendar_ics':
                    ext_mgr.install(e); _set_feature_module_flag('calendar_ics', True)
                    if len(_load_settings().get('calendar_sources', [])) > 0: _refresh_cards()
                    else: _ask_calendar_setup(win, hud, _refresh_cards)
                else:
                    ext_mgr.install(e); _refresh_cards()
            ctk.CTkButton(
                inner_row, text='⬇  УСТАНОВИТЬ', width=220, font=(hud._F, hud._fs(10), 'bold'), height=48, 
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.2), text_color=_CYAN, 
                border_color=_blend(_CYAN, 0.4), border_width=2, corner_radius=12, command=_do_install
            ).pack(side="left", padx=8)
        else:
            def _do_download(e=eid, m=meta):
                def _thread():
                    import urllib.request, zipfile, io; from pathlib import Path
                    try:
                        with urllib.request.urlopen(m.get('download_url')) as resp: data = resp.read()
                        if m.get('download_url').endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                                dest = (Path('data') / 'game_profiles').resolve(); dest.mkdir(parents=True, exist_ok=True)
                                for mem in zf.infolist():
                                    if mem.filename.endswith('.json'): zf.extract(mem, dest)
                        m['bundled'] = True; ext_mgr.install(e); win.after(0, _refresh_cards)
                    except Exception: pass
                threading.Thread(target=_thread, daemon=True).start()
            ctk.CTkButton(
                inner_row, text='☁  СИНХРОНИЗАЦИЯ', width=160, font=(hud._F, hud._fs(10), 'bold'), height=44, 
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, 
                border_color=_blend(_CYAN, 0.4), border_width=2, corner_radius=10, command=_do_download
            ).pack(side='left', padx=5)
    _build_cards()
    _bind_wheel(inner)
    _recenter()
    win.after(20, _update_scroll)
    tk.Frame(win, bg=_GREEN, height=2).pack(fill='x', side='bottom')
