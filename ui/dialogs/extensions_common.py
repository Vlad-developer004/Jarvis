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
from ..hud_constants import _PANEL, _WHITE, _CYAN, _BG, _DIM
from ..hud_utils import _blend
from config_pack.config import get_settings_path
# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\jarvis_settings.json)
# — this used to be a project-relative 'data/jarvis_settings.json' instead, a
# different file that other settings readers never saw and that a rebuild/
# reinstall silently wipes (the bundled data/ folder gets overwritten).
_SETTINGS_PATH = get_settings_path()


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

def _hud_popup_menu(parent, x: int, y: int, hud, items: list) -> None:
    """A small themed right-click popup (dark panel, cyan border/hover),
    used in place of tk.Menu — which renders with plain OS chrome on Windows
    (small system font, no theming, default separators) and looked out of
    place against the rest of the HUD's styled widgets.

    `items` is a list of (label, command) tuples, or None for a separator.
    """
    top = tk.Toplevel(parent)
    top.overrideredirect(True)
    try:
        top.attributes('-topmost', True)
    except Exception:
        pass
    top.configure(bg=_blend(_CYAN, 0.5))
    inner = tk.Frame(top, bg=_PANEL)
    inner.pack(padx=1, pady=1)

    def _dismiss(_e=None):
        try:
            top.destroy()
        except Exception:
            pass

    rows: list[tk.Widget] = []
    for item in items:
        if item is None:
            tk.Frame(inner, bg=_blend(_CYAN, 0.15), height=1).pack(fill='x', padx=8, pady=3)
            continue
        label, cmd = item
        row = tk.Label(inner, text=label, bg=_PANEL, fg=_WHITE,
                        font=(hud._F, JStyle.TEXT_SMALL), anchor='w',
                        padx=16, pady=7, cursor='hand2')
        row.pack(fill='x')
        rows.append(row)
        def _enter(_e, w=row): w.configure(bg=_blend(_CYAN, 0.22), fg=_CYAN)
        def _leave(_e, w=row): w.configure(bg=_PANEL, fg=_WHITE)
        def _click(_e, c=cmd): (_dismiss(), c())
        row.bind('<Enter>', _enter)
        row.bind('<Leave>', _leave)
        row.bind('<ButtonRelease-1>', _click)

    top.update_idletasks()
    sw, sh = top.winfo_screenwidth(), top.winfo_screenheight()
    w, h = top.winfo_reqwidth(), top.winfo_reqheight()
    x = min(x, sw - w - 4)
    y = min(y, sh - h - 4)
    top.geometry(f'+{max(0, x)}+{max(0, y)}')
    top.bind('<FocusOut>', _dismiss)
    top.bind('<Escape>', _dismiss)
    top.focus_force()

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
    # Every handler below returns 'break' ONLY on actual success. Tk's native
    # Entry class binding already implements Ctrl+V/Ctrl+A/Ctrl+C correctly
    # via the <<Paste>>/<<SelectAll>>/<<Copy>> virtual events — if our own
    # clipboard read (pyperclip / Tk clipboard_get, either of which can fail
    # silently, e.g. no clipboard owner) or selection call fails, returning
    # 'break' anyway would swallow the key event and block that native
    # fallback from ever running, turning "our extra code didn't help" into
    # "Ctrl+V/Ctrl+A do nothing at all" — which is exactly what happened.
    def _paste(_e=None):
        t = _first_line(_clipboard_text())
        if not t: return None
        w = _inner()
        if w is not None:
            try:
                if w.selection_present(): w.delete('sel.first', 'sel.last')
                w.insert('insert', t)
                return 'break'
            except Exception:
                return None
        try:
            if hasattr(entry, 'selection_present') and entry.selection_present():
                entry.delete('sel.first', 'sel.last')
            entry.insert(tk.INSERT, t)
            return 'break'
        except Exception:
            try:
                cur = entry.get()
                entry.delete(0, 'end'); entry.insert(0, cur + t)
                return 'break'
            except Exception:
                return None
    def _copy(_e=None):
        w = _inner()
        try:
            if w is not None and w.selection_present():
                parent.clipboard_clear(); parent.clipboard_append(w.selection_get())
                return 'break'
            elif hasattr(entry, 'selection_present') and entry.selection_present():
                parent.clipboard_clear(); parent.clipboard_append(entry.selection_get())
                return 'break'
        except Exception:
            pass
        return None
    def _select_all(_e=None):
        w = _inner()
        if w is not None:
            try:
                w.select_range(0, 'end'); w.icursor('end')
                return 'break'
            except Exception:
                return None
        try:
            entry.select_range(0, 'end')
            return 'break'
        except Exception:
            return None
    def _show_menu(e):
        _hud_popup_menu(parent, e.x_root, e.y_root, hud, [
            (i18n.tr('context_menu.paste'), _paste),
            (i18n.tr('context_menu.copy'), _copy),
            None,
            (i18n.tr('context_menu.select_all'), _select_all),
        ])
    # Bind on both the outer CTkEntry frame AND its real inner tk.Entry —
    # mouse/keyboard events land on whichever one is actually under the
    # cursor/has focus (normally the inner widget, since it fills almost the
    # whole visible area), so binding the outer frame alone silently never
    # fires and right-click paste appears completely broken.
    targets = [entry]
    inner_w = _inner()
    if inner_w is not None and inner_w is not entry:
        targets.append(inner_w)
    for t in targets:
        t.bind('<Button-3>', _show_menu)
        t.bind('<Control-v>', _paste); t.bind('<Control-V>', _paste); t.bind('<Shift-Insert>', _paste)
        t.bind('<Control-c>', _copy); t.bind('<Control-C>', _copy)
        t.bind('<Control-a>', _select_all); t.bind('<Control-A>', _select_all)
