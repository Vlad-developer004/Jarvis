from __future__ import annotations
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar
from ..hud_widgets import _HudScrollbar
from core.extensions import ExtensionManager
def _bind_ctk_entry_clipboard(parent: tk.Toplevel, entry: ctk.CTkEntry, hud) -> None:
    def _inner():
        return getattr(entry, '_entry', None)
    def _clipboard_text() -> str:
        try:
            import pyperclip
            t = pyperclip.paste()
            if t:
                return str(t)
        except Exception:
            pass
        try:
            return str(parent.clipboard_get())
        except Exception:
            return ''
    def _first_line(s: str) -> str:
        return s.replace('\r\n', '\n').split('\n')[0].strip('\r\n')
    def _paste(_e=None):
        t = _first_line(_clipboard_text())
        if not t:
            return 'break'
        w = _inner()
        if w is not None:
            try:
                if w.selection_present():
                    w.delete('sel.first', 'sel.last')
                w.insert('insert', t)
            except Exception:
                pass
            return 'break'
        try:
            if hasattr(entry, 'selection_present') and entry.selection_present():
                entry.delete('sel.first', 'sel.last')
            entry.insert(tk.INSERT, t)
        except Exception:
            try:
                cur = entry.get()
                entry.delete(0, 'end')
                entry.insert(0, cur + t)
            except Exception:
                pass
        return 'break'
    def _copy(_e=None):
        w = _inner()
        try:
            if w is not None and w.selection_present():
                parent.clipboard_clear()
                parent.clipboard_append(w.selection_get())
            elif hasattr(entry, 'selection_present') and entry.selection_present():
                parent.clipboard_clear()
                parent.clipboard_append(entry.selection_get())
        except Exception:
            pass
        return 'break'
    def _select_all(_e=None):
        w = _inner()
        if w is not None:
            try:
                w.select_range(0, 'end')
                w.icursor('end')
            except Exception:
                pass
            return 'break'
        try:
            entry.select_range(0, 'end')
        except Exception:
            pass
        return 'break'
    menu = tk.Menu(
        parent,
        tearoff=0,
        bg=_PANEL,
        fg=_WHITE,
        activebackground=_CYAN,
        activeforeground=_BG,
        font=(hud._F, hud._fs(11)),
    )
    menu.add_command(label='Вставить (Ctrl+V)', command=lambda: _paste())
    menu.add_command(label='Копировать (Ctrl+C)', command=lambda: _copy())
    menu.add_separator()
    menu.add_command(label='Выделить всё (Ctrl+A)', command=lambda: _select_all())
    entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    entry.bind('<Control-v>', _paste)
    entry.bind('<Control-V>', _paste)
    entry.bind('<Shift-Insert>', _paste)
    entry.bind('<Control-c>', _copy)
    entry.bind('<Control-C>', _copy)
    entry.bind('<Control-a>', _select_all)
    entry.bind('<Control-A>', _select_all)
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
    def _secrets_env_path() -> str:
        appdata = os.environ.get('APPDATA', '') or os.environ.get('LOCALAPPDATA', '')
        if appdata:
            p = os.path.join(appdata, 'Jarvis', 'secrets.env')
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
            except Exception:
                pass
            return p
        return os.path.abspath('.env')
    _ENV_PATH = _secrets_env_path()
    def _save_env_key(key: str, value: str) -> None:
        lines = []
        if os.path.exists(_ENV_PATH):
            with open(_ENV_PATH, encoding='utf-8') as f:
                lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith(key + '='):
                lines[i] = f'{key}="{value}"\n'
                found = True
                break
        if not found:
            lines.append(f'{key}="{value}"\n')
        with open(_ENV_PATH, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    def _ask_chat_id(parent, on_confirm):
        dlg = tk.Toplevel(parent)
        dlg.title('Настройка JARVIS')
        dlg.configure(bg=_BG)
        _W = hud._px(500)
        _H = hud._px(380)
        dlg.geometry(f'{_W}x{_H}+150+110')
        dlg.grab_set()
        dlg.resizable(False, False)
        tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
        tk.Label(dlg, text='⦿  ОХРАННАЯ КАМЕРА', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(16, 4))
        tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(0, 10))
        lines = ['Для получения фото на телефон при обнаружении движения', 'введите ваш личный Telegram Chat ID.', '', 'Как узнать Chat ID:', '1. Найти @userinfobot в Telegram', '2. Нажать /start — бот пришлет ID']
        for line in lines:
            col = _CYAN if 'Как' in line else _TEXT if line else _BG
            tk.Label(dlg, text=line, bg=_BG, fg=col, font=(hud._F, hud._fs(10), 'bold' if 'Как' in line else '')).pack(anchor='w', padx=28)
        tk.Frame(dlg, bg=_SEP, height=1).pack(fill='x', padx=20, pady=(12, 10))
        entry_var = tk.StringVar()
        entry = ctk.CTkEntry(dlg, textvariable=entry_var, placeholder_text='Chat ID (например: 123456789)', font=(hud._F, hud._fs(11)), fg_color=_PANEL, text_color=_WHITE, border_color=_CYAN, border_width=1, corner_radius=2, height=hud._px(36))
        entry.pack(fill='x', padx=28, pady=(0, 15))
        _bind_ctk_entry_clipboard(dlg, entry, hud)
        entry.focus_set()
        def _confirm():
            cid = entry_var.get().strip()
            if not cid.lstrip('-').isdigit():
                entry.configure(border_color=_RED)
                return
            on_confirm(cid)
            dlg.destroy()
        ctk.CTkButton(dlg, text='СОХРАНИТЬ', font=(hud._F, hud._fs(11), 'bold'), height=hud._px(34), fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2, command=_confirm).pack(fill='x', padx=28, pady=(0, 6))
        ctk.CTkButton(dlg, text='ОТМЕНА', font=(hud._F, hud._fs(10)), height=hud._px(30), fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2, command=dlg.destroy).pack(fill='x', padx=28)
        dlg.bind('<Return>', lambda _: _confirm())
    def _ask_calendar_setup(parent, on_done=None):
        dlg = tk.Toplevel(parent)
        dlg.title('Настройка календаря')
        dlg.configure(bg=_BG)
        _W = hud._px(560)
        _H = hud._px(520)
        dlg.geometry(f'{_W}x{_H}+150+90')
        dlg.grab_set()
        dlg.minsize(hud._px(440), hud._px(400))
        dlg.resizable(True, True)
        tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
        _wrap = hud._px(500)
        tk.Label(dlg, text='📅  НАСТРОЙКА КАЛЕНДАРЯ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(14, 4))
        tk.Label(
            dlg,
            text='Добавьте файлы (.ics) или ссылки на ваш календарь. Можно добавить несколько источников.',
            bg=_BG, fg=_TEXT, font=(hud._F, hud._fs(10)), wraplength=_wrap, justify='left',
        ).pack(anchor='w', padx=24, pady=(0, 12))
        s0 = _load_settings()
        sources_list = s0.get('calendar_sources', [])
        if not isinstance(sources_list, list):
            sources_list = []
        sources_var: list[dict] = list(sources_list)
        list_frame = tk.Frame(dlg, bg=_PANEL, highlightthickness=1, highlightbackground=_blend(_CYAN, 0.3))
        list_frame.pack(fill='both', expand=True, padx=24, pady=(0, 10))
        list_inner = tk.Frame(list_frame, bg=_PANEL)
        list_inner.pack(fill='both', expand=True, padx=8, pady=8)
        def _refresh_list():
            for w in list_inner.winfo_children():
                w.destroy()
            if not sources_var:
                tk.Label(list_inner, text='Нет источников. Добавьте файл или ссылку ниже.', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(10))).pack(anchor='w', pady=6)
                return
            for i, src in enumerate(sources_var):
                ref = src.get('url') or src.get('path') or '(пусто)'
                kind = 'URL' if src.get('url') else 'Файл'
                row = tk.Frame(list_inner, bg=_PANEL)
                row.pack(fill='x', pady=2)
                tk.Label(row, text=f'{kind}:', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(9)), width=5, anchor='e').pack(side='left')
                tk.Label(row, text=ref, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(9)), anchor='w').pack(side='left', fill='x', expand=True, padx=(6, 6))
                ctk.CTkButton(
                    row, text='✕', width=hud._px(28), height=hud._px(24),
                    font=(hud._F, hud._fs(10)),
                    fg_color=_blend(_RED, 0.12), hover_color=_blend(_RED, 0.3), text_color=_RED,
                    command=lambda idx=i: _remove_source(idx),
                ).pack(side='right')
        def _remove_source(idx):
            if 0 <= idx < len(sources_var):
                sources_var.pop(idx)
                _refresh_list()
        _refresh_list()
        add_frame = tk.Frame(dlg, bg=_BG)
        add_frame.pack(fill='x', padx=24, pady=(0, 8))
        tk.Label(add_frame, text='Ссылка или путь к .ics файлу:', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(10), 'bold')).pack(anchor='w', pady=(0, 4))
        entry_row = tk.Frame(add_frame, bg=_BG)
        entry_row.pack(fill='x')
        add_ent = ctk.CTkEntry(
            entry_row, height=hud._px(34), font=(hud._F, hud._fs(11)),
            fg_color=_blend(_CYAN, 0.08), border_color=_blend(_CYAN, 0.35), border_width=1, text_color=_WHITE,
            placeholder_text='https://.../.ics  или  C:\\путь\\calendar.ics',
        )
        add_ent.pack(side='left', fill='x', expand=True, padx=(0, 8))
        _bind_ctk_entry_clipboard(dlg, add_ent, hud)
        def _add_from_entry():
            val = (add_ent.get() or '').strip()
            if not val:
                return
            low = val.lower()
            if low.startswith(('http://', 'https://', 'webcal://')):
                sources_var.append({'url': val})
            else:
                sources_var.append({'path': val})
            add_ent.delete(0, 'end')
            _refresh_list()
        def _browse_file():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                parent=dlg, title='Выберите файл календаря',
                filetypes=[('Календарь ICS', '*.ics'), ('Все файлы', '*.*')],
            )
            if path:
                sources_var.append({'path': path})
                _refresh_list()
        ctk.CTkButton(
            entry_row, text='ДОБАВИТЬ', width=hud._px(110), height=hud._px(34),
            font=(hud._F, hud._fs(10), 'bold'),
            fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.35), text_color=_CYAN,
            command=_add_from_entry,
        ).pack(side='left')
        add_ent.bind('<Return>', lambda _: _add_from_entry())
        ctk.CTkButton(
            add_frame, text='📂  ВЫБРАТЬ ФАЙЛ…', width=hud._px(200), height=hud._px(32),
            font=(hud._F, hud._fs(10)),
            fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.22), text_color=_CYAN,
            command=_browse_file,
        ).pack(anchor='w', pady=(8, 0))
        err_lbl = tk.Label(dlg, text='', bg=_BG, fg=_RED, font=(hud._F, hud._fs(9)), wraplength=_wrap, justify='left')
        err_lbl.pack(anchor='w', padx=24, pady=(0, 6))
        def _confirm():
            s = _load_settings()
            s['calendar_sources'] = sources_var
            _save_settings(s)
            if on_done:
                on_done()
            dlg.destroy()
        ctk.CTkButton(
            dlg, text='СОХРАНИТЬ', font=(hud._F, hud._fs(11), 'bold'), height=hud._px(34),
            fg_color=_CYAN, hover_color=_blend(_CYAN, 0.7), text_color=_BG, corner_radius=2,
            command=_confirm,
        ).pack(fill='x', padx=24, pady=(0, 6))
        ctk.CTkButton(
            dlg, text='ОТМЕНА', font=(hud._F, hud._fs(10)), height=hud._px(30),
            fg_color=_PANEL, hover_color=_BRD_I, text_color=_DIM, border_color=_SEP, border_width=1, corner_radius=2,
            command=dlg.destroy,
        ).pack(fill='x', padx=24, pady=(0, 12))
    def _looks_gmail_addr(em: str) -> bool:
        e = em.lower().strip()
        return e.endswith('@gmail.com') or e.endswith('@googlemail.com')
    def _ask_mail_setup(parent, on_done):
        dlg = tk.Toplevel(parent)
        dlg.title('Подключение почты к JARVIS')
        dlg.configure(bg=_BG)
        _W = hud._px(560)
        _H = hud._px(640)
        dlg.geometry(f'{_W}x{_H}+150+70')
        dlg.grab_set()
        dlg.minsize(hud._px(480), hud._px(520))
        dlg.resizable(True, True)
        tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
        _wrap = hud._px(500)
        tk.Label(dlg, text='✉  ПОДКЛЮЧЕНИЕ ПОЧТЫ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(pady=(14, 4))
        tk.Label(
            dlg,
            text='JARVIS сможет читать входящие письма и отправлять ответы. Данные хранятся только на вашем компьютере.',
            bg=_BG,
            fg=_TEXT,
            font=(hud._F, hud._fs(10)),
            wraplength=_wrap,
            justify='left',
        ).pack(anchor='w', padx=24, pady=(0, 12))
        s0 = _load_settings()
        ma0 = s0.get('mail_account') if isinstance(s0.get('mail_account'), dict) else {}
        email_var = tk.StringVar(value=str(ma0.get('email') or ''))
        pwd_var = tk.StringVar(value=str(ma0.get('password') or ''))
        imap_var = tk.StringVar(value=str(ma0.get('imap_host') or ''))
        smtp_var = tk.StringVar(value=str(ma0.get('smtp_host') or ''))
        tk.Label(dlg, text='1. Адрес почты', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
        tk.Label(
            dlg,
            text='Ваш полный e-mail, например: имя@gmail.com',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, hud._fs(9)),
            wraplength=_wrap,
            justify='left',
        ).pack(anchor='w', padx=24, pady=(0, 4))
        ent_email = ctk.CTkEntry(
            dlg,
            textvariable=email_var,
            placeholder_text='name@gmail.com',
            font=(hud._F, hud._fs(11)),
            fg_color=_PANEL,
            text_color=_WHITE,
            border_color=_CYAN,
            border_width=1,
            corner_radius=2,
            height=hud._px(36),
        )
        ent_email.pack(fill='x', padx=24, pady=(0, 12))
        _bind_ctk_entry_clipboard(dlg, ent_email, hud)
        tk.Label(dlg, text='2. Пароль приложения', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
        tk.Label(
            dlg,
            text='Не обычный пароль! Gmail: Google → Безопасность → Пароли приложений (16 символов). Яндекс/Mail.ru — пароль приложения в настройках почты.',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, hud._fs(9)),
            wraplength=_wrap,
            justify='left',
        ).pack(anchor='w', padx=24, pady=(0, 4))
        ent_pwd = ctk.CTkEntry(
            dlg,
            textvariable=pwd_var,
            placeholder_text='Пароль приложения (не пароль от аккаунта в браузере)',
            show='*',
            font=(hud._F, hud._fs(11)),
            fg_color=_PANEL,
            text_color=_WHITE,
            border_color=_CYAN,
            border_width=1,
            corner_radius=2,
            height=hud._px(36),
        )
        ent_pwd.pack(fill='x', padx=24, pady=(0, 12))
        _bind_ctk_entry_clipboard(dlg, ent_pwd, hud)
        tk.Label(dlg, text='3. Серверы (только если НЕ Gmail)', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold')).pack(anchor='w', padx=24)
        tk.Label(
            dlg,
            text='Для Gmail оставьте пустыми. Для Яндекс, Mail.ru и др. — впишите серверы из справки вашей почты.',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, hud._fs(9)),
            wraplength=_wrap,
            justify='left',
        ).pack(anchor='w', padx=24, pady=(0, 4))
        tk.Label(dlg, text='IMAP (входящие)', bg=_BG, fg=_TEXT, font=(hud._F, hud._fs(9))).pack(anchor='w', padx=24)
        ent_imap = ctk.CTkEntry(
            dlg,
            textvariable=imap_var,
            placeholder_text='Пусто для Gmail; иначе imap.yandex.ru',
            font=(hud._F, hud._fs(10)),
            fg_color=_PANEL,
            text_color=_WHITE,
            border_color=_SEP,
            border_width=1,
            corner_radius=2,
            height=hud._px(32),
        )
        ent_imap.pack(fill='x', padx=24, pady=(4, 6))
        _bind_ctk_entry_clipboard(dlg, ent_imap, hud)
        tk.Label(dlg, text='SMTP (исходящие)', bg=_BG, fg=_TEXT, font=(hud._F, hud._fs(9))).pack(anchor='w', padx=24)
        ent_smtp = ctk.CTkEntry(
            dlg,
            textvariable=smtp_var,
            placeholder_text='Пусто для Gmail; иначе smtp.yandex.ru',
            font=(hud._F, hud._fs(10)),
            fg_color=_PANEL,
            text_color=_WHITE,
            border_color=_SEP,
            border_width=1,
            corner_radius=2,
            height=hud._px(32),
        )
        ent_smtp.pack(fill='x', padx=24, pady=(4, 8))
        _bind_ctk_entry_clipboard(dlg, ent_smtp, hud)
        err_lbl = tk.Label(dlg, text='', bg=_BG, fg=_RED, font=(hud._F, hud._fs(9)), wraplength=_wrap, justify='left')
        err_lbl.pack(anchor='w', padx=24, pady=(0, 6))
        def _confirm():
            em = email_var.get().strip()
            pw = pwd_var.get().strip()
            ih = imap_var.get().strip()
            sh = smtp_var.get().strip()
            err_lbl.config(text='')
            if not em or '@' not in em:
                err_lbl.config(text='Введите корректный адрес электронной почты.')
                return
            if not pw:
                err_lbl.config(text='Введите пароль приложения.')
                return
            if not _looks_gmail_addr(em) and (not ih or not sh):
                err_lbl.config(text='Для почты не Gmail укажите IMAP и SMTP хосты.')
                return
            try:
                from actions.mail_client import save_mail_account
                save_mail_account(em, pw, ih, sh, 993, 587)
            except Exception as ex:
                err_lbl.config(text=f'Ошибка сохранения: {ex}')
                return
            on_done()
            dlg.destroy()
        ctk.CTkButton(
            dlg,
            text='СОХРАНИТЬ И ПРОДОЛЖИТЬ',
            font=(hud._F, hud._fs(11), 'bold'),
            height=hud._px(34),
            fg_color=_CYAN,
            hover_color=_blend(_CYAN, 0.7),
            text_color=_BG,
            corner_radius=2,
            command=_confirm,
        ).pack(fill='x', padx=24, pady=(0, 6))
        ctk.CTkButton(
            dlg,
            text='ОТМЕНА',
            font=(hud._F, hud._fs(10)),
            height=hud._px(30),
            fg_color=_PANEL,
            hover_color=_BRD_I,
            text_color=_DIM,
            border_color=_SEP,
            border_width=1,
            corner_radius=2,
            command=dlg.destroy,
        ).pack(fill='x', padx=24, pady=(0, 12))
        dlg.bind('<Return>', lambda _: _confirm())
    ext_mgr = ExtensionManager()
    try:
        ext_mgr.reload()
    except Exception:
        pass
    _SETTINGS_PATH = os.path.join('data', 'jarvis_settings.json')
    def _load_settings():
        try:
            if os.path.exists(_SETTINGS_PATH):
                with open(_SETTINGS_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    def _save_settings(s):
        try:
            os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
            with open(_SETTINGS_PATH, 'w', encoding='utf-8') as f:
                json.dump(s, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    def _set_feature_module_flag(module_key: str, enabled: bool) -> None:
        s = _load_settings()
        mods = s.get('feature_modules', {})
        if not isinstance(mods, dict):
            mods = {}
        mods[module_key] = bool(enabled)
        s['feature_modules'] = mods
        _save_settings(s)
        try:
            from core.system import refresh_module_flags
            refresh_module_flags()
        except Exception:
            pass
    GAME_CMD_L10N = {
        "Engine": "Двигатель (Вкл/Выкл)",
        "StartEngine": "Запуск двигателя",
        "StopEngine": "Заглушить двигатель",
        "Handbrake": "Ручной тормоз",
        "HandbrakeOn": "Затянуть ручник",
        "HandbrakeOff": "Снять с ручника",
        "CruiseControl": "Круиз-контроль",
        "CruiseSet": "Установить лимит круиза",
        "CruiseAdjust": "Настройка скорости круиза",
        "CruiseLimit": "Круиз по ограничению",
        "AutoCruiseOn": "Адаптивный круиз (Вкл)",
        "AutoCruiseOff": "Адаптивный круиз (Выкл)",
        "Differential": "Блокировка дифференциала",
        "AxleLift": "Подъём/Опускание оси",
        "Trailer": "Сцепка / Отцепка прицепа",
        "GearUp": "Повысить передачу",
        "GearDown": "Понизить передачу",
        "GearSet": "Поставить передачу (по номеру)",
        "GearReverse": "Задний ход / Реверс",
        "GearNeutral": "Нейтраль",
        "LightsMainOn": "Ближний свет (Вкл)",
        "LightsMainOff": "Ближний свет (Выкл)",
        "LightsHighOn": "Дальний свет (Вкл)",
        "LightsHighOff": "Дальний свет (Выкл)",
        "StrobeLights": "Проблесковые маячки",
        "Beacon": "Маячок / Мигалка",
        "TurnLeft": "Левый поворотник",
        "TurnRight": "Правый поворотник",
        "Hazard": "Аварийная сигнализация",
        "Horn": "Звуковой сигнал",
        "AirHorn": "Пневматический сигнал",
        "WipersOn": "Стеклоочистители (Вкл)",
        "WipersOff": "Стеклоочистители (Выкл)",
        "WipersMedium": "Стеклоочистители (Средне)",
        "WipersFast": "Стеклоочистители (Быстро)",
        "InfoScreen": "Инфо-экран / Бортовой ПК",
        "Navigator": "Карта / Навигатор",
        "Action": "Действие / Взаимодействие",
        "GoToSleep": "Лечь спать",
        "WakeUp": "Проснуться / Поехали",
        "CloseGame": "Выход из игры",
        "PrepareForTrip": "Подготовка к рейсу",
        "Shutdown": "Конец рейса / Глушим всё",
        "BreakTime": "Остановка на отдых",
        "ResumeFromBreak": "Продолжить после отдыха",
        "BadWeather": "Режим плохой погоды",
        "ClearWeather": "Режим ясной погоды",
        "EmergencyStop": "Экстренная остановка",
        "NightDriveMode": "Ночной режим освещения",
        "MorningMode": "Утренний режим (Свет выкл)",
        "CityDriveMode": "Городской режим",
        "HighwayMode": "Трассовый режим",
        "LoadingDock": "Режим погрузки/разгрузки",
        "FogMode": "Режим тумана",
        "Overtake": "Манёвр обгона",
        "ThankYou": "Благодарность (Аварийка)",
        "Basic Cast": "Основная атака",
        "Protego": "Протего (Щит)",
        "Revelio": "Ревелио (Подсветка)",
        "Heal": "Зелье лечения",
        "Ancient Magic": "Древняя магия",
        "Ancient Magic Throw": "Бросок магии",
        "Lumos": "Люмос (Свет)",
        "Interact": "Взаимодействие",
        "Lower Tool": "Опустить оборудование",
        "Lower All Tools": "Опустить всё",
        "Tool Function 1": "Функция 1 (Запуск)",
        "All Tools Toggle": "Запуск всего оборудования",
        "Fold All Tools": "Сложить оборудование",
        "Attach Tool": "Прицепить",
        "Detach Tool": "Отцепить",
        "Dump": "Выгрузка",
        "Enable Dumper": "Включить разгрузку",
        "Pipe": "Труба / Шнек",
        "Lid": "Крышка / Люк",
        "Worker": "Нанять рабочего",
        "HarvestMode": "Цикл уборки урожая",
        "UnloadMode": "Подготовка к разгрузке",
        "TransportMode": "Транспортный режим",
        "refuel": "Заправка (удерживать)",
        "handbrake": "Ручной тормоз (клавиша)",
        "engine": "Двигатель (клавиша)",
        "cruise": "Круиз-контроль (клавиша)",
        "trailer": "Сцепка (клавиша)",
        "horn": "Сигнал (клавиша)",
        "UnloadCargo": "Конец рейса / Разгрузка (умный сценарий)",
    }
    def _load_game_commands(filename: str) -> list[dict]:
        path = os.path.join("data", "game_profiles", filename)
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            spells = data.get("spells", [])
            cmds = []
            seen_actions = set()
            for s in spells:
                name = s.get("name", "")
                variants = s.get("variants", [])
                resp = s.get("response", "")
                if not variants:
                    continue
                main_desc = GAME_CMD_L10N.get(name, name)
                if resp and len(resp) < 100:
                    do_text = resp
                else:
                    do_text = main_desc
                say_text = variants[0]
                other_vars = variants[1:]
                if other_vars:
                    extra_info = ", ".join(other_vars[:5])
                    if len(other_vars) > 5:
                        extra_info += "..."
                    do_text += f"\n(Варианты: {extra_info})"
                cmds.append({
                    "say": say_text,
                    "do": do_text,
                    "search": " ".join(variants).lower() + " " + main_desc.lower() + " " + (resp.lower() if resp else "")
                })
                seen_actions.add(name)
            bindings = data.get("bindings", {})
            for b_key in bindings:
                if b_key not in seen_actions and b_key in GAME_CMD_L10N:
                    pass
            return cmds
        except Exception:
            return []
    def _open_commands_help(meta: dict) -> None:
        cmds = meta.get('commands', [])
        if not isinstance(cmds, list) or not cmds:
            return
        dlg = getattr(hud, '_ext_cmd_win', None)
        if dlg is not None and getattr(dlg, 'winfo_exists', lambda: False)():
            try:
                dlg.deiconify()
                dlg.lift()
                dlg.focus_force()
            except Exception:
                pass
            try:
                for wdg in dlg.winfo_children():
                    wdg.destroy()
            except Exception:
                pass
        else:
            dlg = tk.Toplevel(win)
            hud._ext_cmd_win = dlg
            dlg.configure(bg=_BG)
            _set_dark_title_bar(dlg)
            dlg.after(100, lambda: _set_dark_title_bar(dlg))
            dlg.geometry(f'{hud._px(760)}x{hud._px(640)}+160+110')
            dlg.minsize(520, 420)
            try:
                dlg.transient(win)
            except Exception:
                pass
            dlg.bind('<Destroy>', lambda e: setattr(hud, '_ext_cmd_win', None) if str(e.widget) == str(dlg) else None)
        dlg.title(f'JARVIS — Команды: {meta.get("name", "")}')
        tk.Frame(dlg, bg=_CYAN, height=2).pack(fill='x')
        hdr = tk.Frame(dlg, bg=_BG)
        hdr.pack(fill='x', padx=18, pady=(14, 10))
        tk.Label(hdr, text=f'{meta.get("icon", "◇")}  {meta.get("name", "")}', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(16), 'bold')).pack(anchor='w')
        tk.Label(
            hdr,
            text='Слева — пример фразы для голоса. Справа — что сделает ассистент. Часть модулей доступна ещё из кнопок в HUD.',
            bg=_BG,
            fg=_DIM,
            font=(hud._F, hud._fs(9)),
            wraplength=hud._px(680),
            justify='left',
        ).pack(anchor='w')
        search_f = tk.Frame(dlg, bg=_PANEL, highlightthickness=1, highlightbackground=_SEP)
        search_f.pack(fill='x', padx=18, pady=(0, 10))
        tk.Label(search_f, text='⌕', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(12))).pack(side='left', padx=(10, 4))
        q_var = tk.StringVar()
        ent = tk.Entry(search_f, textvariable=q_var, bg=_PANEL, fg=_WHITE, font=(hud._F, hud._fs(10)), insertbackground=_CYAN, borderwidth=0)
        ent.pack(side='left', fill='x', expand=True, padx=(0, 10), pady=6)
        ent.insert(0, 'ПОИСК КОМАНДЫ...')
        canvas2 = tk.Canvas(dlg, bg=_BG, highlightthickness=0)
        sb2 = _HudScrollbar(dlg, canvas2, color=_CYAN)
        canvas2.configure(yscrollcommand=sb2.set)
        canvas2.pack(side='left', fill='both', expand=True, padx=(18, 0), pady=(0, 18))
        inner2 = tk.Frame(canvas2, bg=_BG)
        _cwin2 = canvas2.create_window((0, 0), window=inner2, anchor='nw')
        def _upd_scroll2(*_):
            try:
                dlg.update_idletasks()
            except Exception:
                pass
            bb = canvas2.bbox('all')
            if bb:
                canvas2.configure(scrollregion=bb)
        def _on_resize2(e):
            canvas2.itemconfig(_cwin2, width=e.width)
            _upd_scroll2()
        def _on_wheel2(e):
            if canvas2.winfo_exists():
                canvas2.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        def _bind_wheel2(w):
            w.bind('<MouseWheel>', _on_wheel2)
            try:
                w.bind('<Button-4>', lambda _e: canvas2.yview_scroll(-1, 'units'))
                w.bind('<Button-5>', lambda _e: canvas2.yview_scroll(1, 'units'))
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_wheel2(ch)
        canvas2.bind('<Configure>', _on_resize2)
        inner2.bind('<Configure>', _upd_scroll2)
        dlg.bind('<MouseWheel>', _on_wheel2)
        canvas2.bind('<MouseWheel>', _on_wheel2)
        def _bind_wheel_chain(w):
            w.bind('<MouseWheel>', _on_wheel2)
            try:
                w.bind('<Button-4>', lambda _e: canvas2.yview_scroll(-1, 'units'))
                w.bind('<Button-5>', lambda _e: canvas2.yview_scroll(1, 'units'))
            except Exception:
                pass
            for ch in w.winfo_children():
                _bind_wheel_chain(ch)
        _bind_wheel_chain(hdr)
        _bind_wheel_chain(search_f)
        def _render_list(query: str | None):
            for w in inner2.winfo_children():
                w.destroy()
            qq = (query or '').strip().lower()
            shown = 0
            for item in cmds:
                say = str(item.get('say', '')).strip()
                do = str(item.get('do', '')).strip()
                if not say or not do:
                    continue
                if qq and (qq not in say.lower()) and (qq not in do.lower()) and (qq not in str(item.get('search', '')).lower()):
                    continue
                shown += 1
                row = tk.Frame(inner2, bg=_PANEL, highlightthickness=1, highlightbackground=_blend(_CYAN, 0.12))
                row.pack(fill='x', padx=(0, 18), pady=(0, 8))
                b = tk.Frame(row, bg=_PANEL)
                b.pack(fill='x', padx=12, pady=10)
                left = tk.Frame(b, bg=_PANEL)
                left.pack(side='left', fill='x', expand=True)
                tk.Label(left, text='Скажи:', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='w')
                tk.Label(left, text=f'«{say}»', bg=_PANEL, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold'), anchor='w').pack(anchor='w')
                right = tk.Frame(b, bg=_PANEL)
                right.pack(side='right', padx=(12, 0))
                tk.Label(right, text='Действие:', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='e')
                tk.Label(
                    right,
                    text=do,
                    bg=_PANEL,
                    fg=_WHITE,
                    font=(hud._F, hud._fs(10)),
                    anchor='e',
                    justify='right',
                    wraplength=hud._px(340),
                ).pack(anchor='e')
            if shown == 0:
                tk.Label(inner2, text='Ничего не найдено.', bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(10), 'bold')).pack(anchor='w', padx=6, pady=6)
            _bind_wheel2(inner2)
            def _after_render():
                _upd_scroll2()
                _bind_wheel2(inner2)
            dlg.after(10, _after_render)
        def _on_focus(_e):
            if ent.get() == 'ПОИСК КОМАНДЫ...':
                ent.delete(0, 'end')
        def _on_change(_e=None):
            val = q_var.get()
            if val == 'ПОИСК КОМАНДЫ...':
                val = ''
            _render_list(val)
        ent.bind('<FocusIn>', _on_focus)
        ent.bind('<KeyRelease>', _on_change)
        dlg.after(0, lambda: canvas2.itemconfig(_cwin2, width=max(200, canvas2.winfo_width())))
        dlg.after(10, lambda: _render_list(''))
    win.iconbitmap(hud._ico_path) if hasattr(hud, '_ico_path') else None
    win.configure(bg=_BG)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _W = int(min(hud._px(740), win.winfo_screenwidth() * 0.95))
    _H = int(min(hud._px(680), win.winfo_screenheight() * 0.92))
    win.geometry(f'{_W}x{_H}+110+70')
    win.resizable(False, True)
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')
    header_area = tk.Frame(win, bg=_BG)
    header_area.pack(fill='x', padx=24, pady=(16, 0))
    title_f = tk.Frame(header_area, bg=_BG)
    title_f.pack(side='left')
    tk.Label(title_f, text='⬡  ЦЕНТР РАСШИРЕНИЙ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(20), 'bold')).pack(anchor='w')
    tk.Label(title_f, text='СИСТЕМНАЯ ДИАГНОСТИКА И КОНФИГУРАЦИЯ МОДУЛЕЙ', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='w')
    search_f = tk.Frame(header_area, bg=_PANEL, highlightthickness=1, highlightbackground=_SEP)
    search_f.pack(side='right', pady=5)
    tk.Label(search_f, text='⌕', bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(12))).pack(side='left', padx=(8, 4))
    search_entry = tk.Entry(search_f, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(10)), insertbackground=_CYAN, borderwidth=0, width=22)
    search_entry.pack(side='left', padx=(0, 8), pady=4)
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
        for w in inner.winfo_children():
            w.destroy()
        _build_cards(query if query != 'ПОИСК МОДУЛЯ...' else None)
        _bind_wheel(inner)
        win.after(10, _update_scroll)
        hud._rebuild_left()
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
        tk.Label(body, text=meta.get('description', ''), bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(11)), anchor='w', wraplength=hud._px(480), justify='left').pack(fill='x', pady=(4, 10))
        actions_outer = tk.Frame(body, bg=_PANEL)
        actions_outer.pack(fill="x")
        has_catalog_cmds = bool(meta.get("commands"))
        is_game = meta.get("type") == "game_profile"
        if has_catalog_cmds or is_game:
            def _show_cmds(m=meta):
                if is_game and not m.get("commands"):
                    m["commands"] = _load_game_commands(m.get("file", ""))
                _open_commands_help(m)
            ctk.CTkButton(
                actions_outer,
                text="◈  СПИСОК ГОЛОСОВЫХ КОМАНД",
                width=hud._px(280),
                font=(hud._F, hud._fs(10), "bold"),
                height=hud._px(36),
                fg_color=_blend(_CYAN, 0.10),
                hover_color=_blend(_CYAN, 0.25),
                text_color=_CYAN,
                border_color=_blend(_CYAN, 0.5),
                border_width=1,
                corner_radius=4,
                command=_show_cmds,
            ).pack(anchor="center", pady=(0, 10))
            tk.Frame(actions_outer, bg=_SEP, height=1).pack(fill="x", pady=(0, 12))
        btn_row = tk.Frame(actions_outer, bg=_PANEL)
        btn_row.pack(fill='x')
        if installed:
            def _do_uninstall(e=eid):
                ext_mgr.uninstall(e)
                if e == 'feature_photoshop_voice':
                    _set_feature_module_flag('photoshop_voice', False)
                if e == 'feature_figma_voice':
                    _set_feature_module_flag('figma_voice', False)
                if e == 'feature_network_profiles':
                    _set_feature_module_flag('network_profiles', False)
                if e == 'feature_system_health':
                    _set_feature_module_flag('system_health', False)
                if e == 'feature_calendar_ics':
                    _set_feature_module_flag('calendar_ics', False)
                if e == 'feature_mail_client':
                    _set_feature_module_flag('inbox_digest', False)
                _refresh_cards()
            ctk.CTkButton(btn_row, text='🗑  ОТКЛЮЧИТЬ МОДУЛЬ', width=hud._px(280), font=(hud._F, hud._fs(11), 'bold'), height=hud._px(40), fg_color=_blend(_RED, 0.15), hover_color=_blend(_RED, 0.35), text_color=_RED, border_color=_RED, border_width=2, corner_radius=4, command=_do_uninstall).pack(anchor='center', pady=(0, 5))
            if eid == 'feature_calendar_ics':
                def _reconfig_cal():
                    _ask_calendar_setup(win, _refresh_cards)
                ctk.CTkButton(
                    btn_row,
                    text='⚙  НАСТРОЙКИ КАЛЕНДАРЯ',
                    width=hud._px(280),
                    font=(hud._F, hud._fs(10), 'bold'),
                    height=hud._px(34),
                    fg_color=_blend(_CYAN, 0.08),
                    hover_color=_blend(_CYAN, 0.22),
                    text_color=_CYAN,
                    border_color=_CYAN,
                    border_width=1,
                    corner_radius=4,
                    command=_reconfig_cal,
                ).pack(anchor='center', pady=(0, 5))
            if eid == 'feature_mail_client':
                def _reconfig_mail():
                    _ask_mail_setup(win, _refresh_cards)
                ctk.CTkButton(
                    btn_row,
                    text='⚙  НАСТРОЙКИ ПОЧТЫ',
                    width=hud._px(280),
                    font=(hud._F, hud._fs(10), 'bold'),
                    height=hud._px(34),
                    fg_color=_blend(_CYAN, 0.08),
                    hover_color=_blend(_CYAN, 0.22),
                    text_color=_CYAN,
                    border_color=_CYAN,
                    border_width=1,
                    corner_radius=4,
                    command=_reconfig_mail,
                ).pack(anchor='center', pady=(0, 5))
            if eid == 'game_ets2':
                try:
                    from actions.ets2_telemetry_installer import is_telemetry_installed
                    tele_ok = is_telemetry_installed()
                except Exception:
                    tele_ok = False
                dll_status_lbl = tk.Label(btn_row, text='ТЕЛЕМЕТРИЯ УСТАНОВЛЕНА' if tele_ok else '', bg=_PANEL, fg=_GREEN if tele_ok else _AMBER, font=(hud._F, hud._fs(9)))
                def _do_dll_install(lbl=dll_status_lbl):
                    lbl.config(text='Поиск ETS2...', fg=_AMBER)
                    try:
                        from actions.ets2_telemetry_installer import run_installer
                        def _on_done(result):
                            if result and result.ok:
                                msg = 'Плагин установлен' if result.message == 'installed' else 'Плагин уже установлен'
                                win.after(0, lambda: lbl.config(text=msg, fg=_GREEN))
                            else:
                                win.after(0, lambda: lbl.config(text='Ошибка установки', fg=_RED))
                        run_installer(tk_root=win, on_done=_on_done)
                    except Exception as ex:
                        lbl.config(text=f'Ошибка: {ex}', fg=_RED)
                btn_text = '❖  ОБНОВИТЬ ТЕЛЕМЕТРИЮ' if tele_ok else '⬇  УСТАНОВИТЬ ПЛАГИН ТЕЛЕМЕТРИИ'
                ctk.CTkButton(btn_row, text=btn_text, width=hud._px(280), font=(hud._F, hud._fs(10), 'bold'), height=hud._px(36), fg_color=_blend(_AMBER, 0.12), hover_color=_blend(_AMBER, 0.3), text_color=_AMBER, border_color=_AMBER, border_width=1, corner_radius=4, command=_do_dll_install).pack(anchor='center', pady=(6, 0))
                dll_status_lbl.pack(anchor='center', pady=(3, 0))
        elif bundled:
            def _do_install(e=eid, m=meta):
                if m.get('requires_chat_id'):
                    _ask_chat_id(win, lambda cid: (_save_env_key('TELEGRAM_CHAT_ID', cid), ext_mgr.install(e), _refresh_cards()))
                elif e == 'feature_mail_client':
                    s_m = _load_settings()
                    ma_m = s_m.get('mail_account')
                    has_creds = isinstance(ma_m, dict) and str(ma_m.get('email', '')).strip() and str(ma_m.get('password', '')).strip()
                    if has_creds:
                        ext_mgr.install(e)
                        _set_feature_module_flag('inbox_digest', True)
                        _refresh_cards()
                    else:
                        def _after_mail():
                            ext_mgr.install(e)
                            _set_feature_module_flag('inbox_digest', True)
                            _refresh_cards()
                        _ask_mail_setup(win, _after_mail)
                elif e == 'game_ets2':
                    ext_mgr.install(e)
                    _refresh_cards()
                    def _run_dll_install():
                        try:
                            from actions.ets2_telemetry_installer import run_installer
                            run_installer(tk_root=win)
                        except Exception:
                            pass
                    win.after(200, _run_dll_install)
                elif e == 'feature_calendar_ics':
                    ext_mgr.install(e)
                    _set_feature_module_flag('calendar_ics', True)
                    s_c = _load_settings()
                    cs = s_c.get('calendar_sources')
                    has_sources = isinstance(cs, list) and len(cs) > 0
                    if has_sources:
                        _refresh_cards()
                    else:
                        _ask_calendar_setup(win, _refresh_cards)
                else:
                    ext_mgr.install(e)
                    if e == 'feature_photoshop_voice':
                        _set_feature_module_flag('photoshop_voice', True)
                    if e == 'feature_figma_voice':
                        _set_feature_module_flag('figma_voice', True)
                    if e == 'feature_network_profiles':
                        _set_feature_module_flag('network_profiles', True)
                    if e == 'feature_system_health':
                        _set_feature_module_flag('system_health', True)
                    _refresh_cards()
            ctk.CTkButton(btn_row, text='↓  УСТАНОВИТЬ МОДУЛЬ', width=hud._px(280), font=(hud._F, hud._fs(11), 'bold'), height=hud._px(40), fg_color=_blend(_CYAN, 0.18), hover_color=_blend(_CYAN, 0.5), text_color=_CYAN, border_color=_CYAN, border_width=2, corner_radius=4, command=_do_install).pack(anchor='center', pady=(0, 5))
        else:
            progress_lbl = tk.Label(btn_row, text='', bg=_PANEL, fg=_AMBER, font=(hud._F, hud._fs(9)))
            progress_lbl.pack(side='left', padx=(8, 0))
            def _do_download(e=eid, m=meta, lbl=progress_lbl):
                download_url = m.get('download_url', '')
                if not download_url:
                    win.after(0, lambda: lbl.config(text='Ссылка не найдена'))
                    return
                try:
                    from urllib.parse import urlparse
                    import ipaddress
                    import socket
                    parsed = urlparse(download_url)
                    if parsed.scheme.lower() != 'https':
                        win.after(0, lambda: lbl.config(text='Разрешены только HTTPS ссылки'))
                        return
                    host = (parsed.hostname or '').strip().lower()
                    if not host or host in {'localhost', '127.0.0.1', '::1'}:
                        win.after(0, lambda: lbl.config(text='Небезопасный адрес'))
                        return
                    try:
                        ip = ipaddress.ip_address(socket.gethostbyname(host))
                        if ip.is_private or ip.is_loopback or ip.is_link_local:
                            win.after(0, lambda: lbl.config(text='Небезопасный адрес'))
                            return
                    except Exception:
                        pass
                except Exception:
                    win.after(0, lambda: lbl.config(text='Некорректная ссылка'))
                    return
                def _download_thread():
                    import urllib.request, zipfile, io
                    from pathlib import Path
                    try:
                        win.after(0, lambda: lbl.config(text='Загрузка...'))
                        with urllib.request.urlopen(download_url) as resp:
                            data = resp.read()
                        if download_url.endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                                dest = Path('data') / 'game_profiles'
                                dest.mkdir(parents=True, exist_ok=True)
                                dest_root = dest.resolve()
                                for member in zf.infolist():
                                    if not member.filename.endswith('.json'):
                                        continue
                                    target = (dest_root / member.filename).resolve()
                                    try:
                                        target.relative_to(dest_root)
                                    except ValueError:
                                        continue
                                    zf.extract(member, dest_root)
                        m['bundled'] = True
                        ext_mgr.install(e)
                        win.after(0, _refresh_cards)
                    except Exception as err:
                        win.after(0, lambda: lbl.config(text=f'Ошибка: {err}'))
                threading.Thread(target=_download_thread, daemon=True).start()
            ctk.CTkButton(btn_row, text='↑  СИНХРОНИЗАЦИЯ С ОБЛАКОМ', width=hud._px(260), font=(hud._F, hud._fs(10), 'bold'), height=hud._px(36), fg_color=_blend(_CYAN, 0.03), hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, border_color=_blend(_CYAN, 0.4), border_width=1, corner_radius=2, command=_do_download).pack(side='left')
    _build_cards()
    _bind_wheel(inner)
    win.after(20, _update_scroll)
    tk.Frame(win, bg=_GREEN, height=2).pack(fill='x', side='bottom')
