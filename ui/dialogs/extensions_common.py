"""Shared helpers for the extensions dialog and its setup wizards:
settings.json read/write, secrets.env key storage, feature-module flags,
game-command loading, and a generic Ctk entry clipboard binder (also used
by the mail dialogs). Split out of the old extensions.py purely for file
size; no behavior change.
"""
from __future__ import annotations
import json, os
import tkinter as tk
from core import i18n
from ..hud_style import JStyle
from ..hud_constants import _PANEL, _WHITE, _CYAN, _BG
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
    # Single source of truth — see config_pack.config.get_secrets_path().
    try:
        from config_pack.config import get_secrets_path
        p = get_secrets_path()
        try: os.makedirs(os.path.dirname(p), exist_ok=True)
        except Exception: pass
        return p
    except Exception:
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
    # Try to load Ukrainian version if language is set to Ukrainian
    lang = i18n.get_language()
    if lang == 'uk':
        uk_filename = filename.replace('.json', '_uk.json')
        uk_path = os.path.join("data", "game_profiles", uk_filename)
        if os.path.exists(uk_path):
            path = uk_path
        else:
            path = os.path.join("data", "game_profiles", filename)
    else:
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
    menu = tk.Menu(parent, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, JStyle.TEXT_BODY))
    menu.add_command(label=i18n.tr('context_menu.paste'), command=lambda: _paste())
    menu.add_command(label=i18n.tr('context_menu.copy'), command=lambda: _copy())
    menu.add_separator()
    menu.add_command(label=i18n.tr('context_menu.select_all'), command=lambda: _select_all())
    entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    entry.bind('<Control-v>', _paste); entry.bind('<Control-V>', _paste); entry.bind('<Shift-Insert>', _paste)
    entry.bind('<Control-c>', _copy); entry.bind('<Control-C>', _copy)
    entry.bind('<Control-a>', _select_all); entry.bind('<Control-A>', _select_all)
