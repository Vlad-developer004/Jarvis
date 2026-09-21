"""Key-macro binding editor dialog. Split out of the old editors.py
purely for file size; no behavior change.
"""
from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _make_resizable
from ..hud_widgets import _HudScrollbar
def open_keybind_editor(hud, reopen: bool = False) -> None:
    if not reopen and hud._keybind_win and hud._keybind_win.winfo_exists():
        hud._keybind_win.lift()
        return
    if reopen and hud._keybind_win and hud._keybind_win.winfo_exists():
        hud._keybind_win.destroy()

    import sys, json, os
    from pathlib import Path
    
    profiles_dir = Path('data') / 'game_profiles'
    profiles_data: dict[str, dict] = {}
    profile_files: dict[str, Path] = {}
    
    is_uk = (i18n.get_language() == 'uk')
    
    # 1. Load all profiles
    for p in profiles_dir.glob('*.json'):
        stem = p.stem
        if is_uk and not stem.endswith('_uk'):
            continue
        if not is_uk and stem.endswith('_uk'):
            continue
            
        try:
            d = json.loads(p.read_text(encoding='utf-8-sig'))
            game_name = d.get('game', p.stem)
            if game_name.endswith('_uk'):
                game_name = game_name[:-3]
            profiles_data[game_name] = d
            profile_files[game_name] = p
        except Exception:
            pass
            
    if not profiles_data:
        import tkinter.messagebox as mb
        mb.showinfo(i18n.tr('editor.no_profiles'), i18n.tr('editor.profiles_not_found'))
        return

    # Sort profiles: ETS2 first, then alphabetical
    sorted_games = sorted(profiles_data.keys(), key=lambda x: (0 if 'euro truck' in x.lower() or 'ets' in x.lower() else 1, x))
    
    # Identify active profile
    _main = sys.modules.get('__main__')
    active_profile_name = getattr(_main, '_game_profile', '') if _main else ''
    current_game = next((g for g in sorted_games if g == active_profile_name), sorted_games[0])

    _KEYSYM_MAP = {
        'Return': 'enter', 'space': 'space', 'BackSpace': 'backspace', 'Delete': 'delete', 'Escape': 'escape', 'Tab': 'tab',
        'Shift_L': 'shift', 'Shift_R': 'shift', 'Control_L': 'ctrl', 'Control_R': 'ctrl', 'Alt_L': 'alt', 'Alt_R': 'alt',
        'Up': 'up', 'Down': 'down', 'Left': 'left', 'Right': 'right', 'Prior': 'pageup', 'Next': 'pagedown', 'Home': 'home', 'End': 'end', 'Insert': 'insert',
        'KP_Add': 'add', 'KP_Subtract': 'subtract', 'KP_Divide': 'divide', 'KP_Multiply': 'multiply', 'KP_Enter': 'numpadenter',
        'KP_0': 'numpad0', 'KP_1': 'numpad1', 'KP_2': 'numpad2', 'KP_3': 'numpad3', 'KP_4': 'numpad4', 'KP_5': 'numpad5', 'KP_6': 'numpad6', 'KP_7': 'numpad7', 'KP_8': 'numpad8', 'KP_9': 'numpad9',
        'KP_Decimal': 'decimal', 'bracketleft': '[', 'bracketright': ']', 'semicolon': ';', 'apostrophe': "'", 'grave': '`', 'minus': '-', 'equal': '=', 'backslash': '\\', 'comma': ',', 'period': '.', 'slash': '/',
        'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4', 'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8', 'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12',
        'Print': 'printscreen', 'Pause': 'pause', 'Caps_Lock': 'capslock', 'Num_Lock': 'numlock', 'Scroll_Lock': 'scrolllock'
    }
    
    _CYR_MAP = {
        'Cyrillic_a': 'f', 'Cyrillic_be': 'comma', 'Cyrillic_ve': 'd', 'Cyrillic_ge': 'u', 'Cyrillic_de': 'l', 'Cyrillic_ie': 't', 'Cyrillic_io': '`', 'Cyrillic_zhe': 'semicolon', 'Cyrillic_ze': 'p', 'Cyrillic_i': 'b', 'Cyrillic_shorti': 'q', 'Cyrillic_ka': 'r', 'Cyrillic_el': 'k', 'Cyrillic_em': 'v', 'Cyrillic_en': 'y', 'Cyrillic_o': 'j', 'Cyrillic_pe': 'g', 'Cyrillic_er': 'h', 'Cyrillic_es': 'c', 'Cyrillic_te': 'n', 'Cyrillic_u': 'e', 'Cyrillic_ef': 'a', 'Cyrillic_ha': '[', 'Cyrillic_tse': 'w', 'Cyrillic_che': 'x', 'Cyrillic_sha': 'i', 'Cyrillic_shcha': 'o', 'Cyrillic_hardsign': ']', 'Cyrillic_yeru': 's', 'Cyrillic_softsign': 'm', 'Cyrillic_e': "'", 'Cyrillic_yu': 'period', 'Cyrillic_ya': 'z'
    }
    
    _RU_LABELS = {
        'engine': 'Двигатель', 'handbrake': 'Стояночный тормоз', 'cruise': 'Круиз-контроль', 
        'cruise_up': 'Круиз: Больше', 'cruise_down': 'Круиз: Меньше',
        'differential': 'Дифференциал', 'axle_lift': 'Подъём оси', 'trailer': 'Прицеп', 
        'lights_main': 'Фары ближний', 'lights_high': 'Фары дальний', 'strobe': 'Проблесковые огни', 
        'turn_left': 'Поворотник левый', 'turn_right': 'Поворотник правый', 'hazard': 'Аварийка', 
        'horn': 'Клаксон', 'air_horn': 'Пневмосигнал', 'wipers': 'Дворники', 'info': 'Инфо', 
        'navigator': 'Навигатор', 'action': 'Действие', 'gear_up': 'Повышенная передача', 
        'gear_down': 'Пониженная передача', 'refuel': 'Заправка'
    }
    _TELEMETRY_RU = {
        'cruise_set': 'Установка скорости круиза (через API)',
        'cruise_adjust': 'Подстройка скорости круиза (через API)',
        'cruise_limit': 'Круиз по ограничению (через API)',
        'auto_cruise_on': 'Активация адаптивного круиза (AI)',
        'auto_cruise_off': 'Деактивация адаптивного круиза (AI)',
        'go_to_sleep': 'Симуляция сна (через API)',
        'close_game': 'Экстренный выход из игры',
        'gear_set': 'Установка передачи (через API)'
    }
    _UK_LABELS = {
        'engine': 'Двигун', 'handbrake': 'Стоянкове гальмо', 'cruise': 'Круїз-контроль', 
        'cruise_up': 'Круїз: Більше', 'cruise_down': 'Круїз: Менше',
        'differential': 'Диференціал', 'axle_lift': 'Підйом осі', 'trailer': 'Причіп', 
        'lights_main': 'Фари ближнє', 'lights_high': 'Фари дальнє', 'strobe': 'Проблискові вогні', 
        'turn_left': 'Поворотник лівий', 'turn_right': 'Поворотник правий', 'hazard': 'Аварійка', 
        'horn': 'Клаксон', 'air_horn': 'Пневмосигнал', 'wipers': 'Двірники', 'info': 'Інфо', 
        'navigator': 'Навігатор', 'action': 'Дія', 'gear_up': 'Підвищена передача', 
        'gear_down': 'Понижена передача', 'refuel': 'Заправка'
    }
    _TELEMETRY_UK = {
        'cruise_set': 'Встановлення швидкості круїзу (через API)',
        'cruise_adjust': 'Підлаштування швидкості круїзу (через API)',
        'cruise_limit': 'Круїз за обмеженням (через API)',
        'auto_cruise_on': 'Активація адаптивного круїзу (AI)',
        'auto_cruise_off': 'Деактивація адаптивного круизу (AI)',
        'go_to_sleep': 'Симуляція сну (через API)',
        'close_game': 'Екстрений вихід з гри',
        'gear_set': 'Встановлення передачі (через API)'
    }
    
    lang = i18n.get_language()
    _RU_LABELS = _UK_LABELS if lang == 'uk' else _RU_LABELS
    _TELEMETRY_RU = _TELEMETRY_UK if lang == 'uk' else _TELEMETRY_RU
    _RU_TO_BIND = {v: k for k, v in _RU_LABELS.items()}
    _BIND_LIST = sorted(_RU_LABELS.values())

    def _norm_key(sym: str) -> str:
        if sym in _KEYSYM_MAP: return _KEYSYM_MAP[sym]
        if sym in _CYR_MAP: return _CYR_MAP[sym]
        # Handle cases like Cyrillic_A (uppercase)
        if sym.startswith('Cyrillic_'):
            low_sym = 'Cyrillic_' + sym[9:].lower()
            if low_sym in _CYR_MAP: return _CYR_MAP[low_sym]
        return sym.lower()

    win = tk.Toplevel(hud.root)
    hud._keybind_win = win
    _set_dark_title_bar(win)
    win.after(50, lambda: _set_dark_title_bar(win))
    win.title(i18n.tr('editor.title'))
    try:
        if hasattr(hud, '_ico_path'): win.iconbitmap(hud._ico_path)
    except: pass
    win.configure(bg=_BG)  # type: ignore[call-arg]
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)

    _W = 780
    _H = 500
    _center_window(win, hud._px(_W), hud._px(_H))
    
    win.resizable(True, True)
    win.minsize(hud._px(600), hud._px(450))

    def _close():
        hud._keybind_win = None
        win.destroy()

    # THE FAMOUS CYAN LINE
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')

    # --- HEADER ---
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x')

    # Header Content (Icon + Title + Subtitle)
    content_hdr = tk.Frame(hdr, bg=_BG)
    content_hdr.pack(side='left', fill='x', expand=True, padx=(20, 10), pady=15)

    i_lbl = tk.Label(content_hdr, text='★', bg=_BG, fg=_CYAN, font=("Segoe UI Symbol", JStyle.TEXT_H1))
    i_lbl.pack(side='left', padx=(0, 15))
    
    txt_f = tk.Frame(content_hdr, bg=_BG)
    txt_f.pack(side='left', fill='x')

    t_lbl = tk.Label(txt_f, text=i18n.tr('editor.header'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H1, 'bold'), anchor='w')
    t_lbl.pack(anchor='w')
    
    s_lbl = tk.Label(txt_f, text=i18n.tr('editor.subtitle'), bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_BODY), anchor='w')
    s_lbl.pack(anchor='w')

    # --- TABS (Scrollable if many) ---
    tab_container = tk.Frame(win, bg=_BG)
    tab_container.pack(fill='x', padx=0, pady=(0, 0))
    
    # Bottom border for tabs area
    tk.Frame(win, bg=_blend(_CYAN, 0.15), height=1).pack(fill='x')
    
    tab_inner = tk.Frame(tab_container, bg=_BG)
    tab_inner.pack(fill='x', padx=0)
    
    tab_buttons: dict[str, tuple[ctk.CTkButton, tk.Frame]] = {}
    tab_frames: dict[str, tk.Frame] = {}  # Cache for fast switching
    
    # --- MAIN CONTENT AREA ---
    scroll_area = tk.Frame(win, bg=_BG)
    scroll_area.pack(fill='both', expand=True)
    
    # --- GRID CONTAINER (to avoid mixing pack/grid in scroll_area) ---
    grid_container = tk.Frame(scroll_area, bg=_BG)
    grid_container.pack(fill='both', expand=True, padx=hud._px(8))
    grid_container.columnconfigure(0, weight=1)
    grid_container.rowconfigure(2, weight=1)

# === MODERN SEARCH BAR ===
    search_wrap = tk.Frame(scroll_area, bg=_BG)
    search_wrap.pack(fill='x', padx=hud._px(20), pady=(hud._px(12), hud._px(8)))
    
    search_pill = ctk.CTkEntry(
        search_wrap,
        placeholder_text=i18n.tr('editor.search'), 
        placeholder_text_color=_blend(_CYAN, 0.7),
        fg_color=_PANEL,
        text_color=_CYAN,
        border_color=_blend(_CYAN, 0.35),
        border_width=1,
        corner_radius=JStyle.RAD_PANEL,
        font=(hud._F, JStyle.TEXT_BODY),
        height=JStyle.H_NORM,
    )
    search_pill.pack(fill='x')

# === COLUMN HEADERS — FULL GRID LAYOUT ===
    cols_h = tk.Frame(grid_container, bg=_BG)
    cols_h.grid(row=0, column=0, sticky='ew', pady=(hud._px(4), 0))
    
    # Упрощенная разметка: Иконка (50), Название (остальное), Контролы (300)
    cols_h.grid_columnconfigure(0, minsize=hud._px(50), weight=0)
    cols_h.grid_columnconfigure(1, weight=1)
    cols_h.grid_columnconfigure(2, minsize=hud._px(300), weight=0)
    
    tk.Label(cols_h, text='★', bg=_BG, fg=_BG, font=(hud._F, JStyle.TEXT_H1)).grid(row=0, column=0)
    ctk.CTkLabel(cols_h, text='КОМАНДА', text_color=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='w').grid(row=0, column=1, sticky='w', padx=(hud._px(10), hud._px(10)))
    
    # Контейнер для заголовков управления (Клавиша + Инструменты)
    ctrl_h = tk.Frame(cols_h, bg=_BG)
    ctrl_h.grid(row=0, column=2, sticky='nsew')
    ctrl_h.columnconfigure(0, weight=1)
    ctrl_h.columnconfigure(1, weight=1)
    
    ctk.CTkLabel(ctrl_h, text='КЛАВИША', text_color=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='center').grid(row=0, column=0, sticky='ew')
    ctk.CTkLabel(ctrl_h, text='ИНСТРУМЕНТЫ', text_color=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='center').grid(row=0, column=1, sticky='ew')

    tk.Frame(grid_container, bg=_CYAN, height=2).grid(row=1, column=0, sticky='ew')
    
    canvas = tk.Canvas(grid_container, bg=_BG, highlightthickness=0, borderwidth=0)
    _vsb = _HudScrollbar(grid_container, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=_vsb.set)
    canvas.grid(row=2, column=0, sticky='nsew')
    inner = tk.Frame(canvas, bg=_BG)
    canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')

    def _on_resize(e):
        # Синхронизация ширины: список должен быть равен шапке
        w = e.width
        if w > 10:
            canvas.itemconfig(canvas_window, width=w)
        
    def _update_scroll(e=None):
        # Update scroll region when content changes
        canvas.configure(scrollregion=canvas.bbox('all'))
        
    canvas.bind('<Configure>', _on_resize)
    inner.bind('<Configure>', _update_scroll)
    
    def _on_mousewheel(e):
        if canvas.winfo_exists() and _vsb.winfo_ismapped():
            canvas.yview_scroll(-1 * (e.delta // 120), 'units')
    win.bind('<MouseWheel>', _on_mousewheel)
    
    _search_debounce_id = [None]
    
    def _refresh_current_game():
        """Force-rebuild the current tab (used by search). Debounced."""
        if hasattr(win, '_current_game_name') and win._current_game_name:
            gname = win._current_game_name
            if gname in tab_frames:
                tab_frames[gname].destroy()
                del tab_frames[gname]
            _load_game_tab(gname)
    
    def _on_search_change(e=None):
        """Debounced: rebuild 300ms after last change."""
        if _search_debounce_id[0]:
            win.after_cancel(_search_debounce_id[0])
        _search_debounce_id[0] = win.after(300, _refresh_current_game)
    
    search_pill.bind('<KeyRelease>', _on_search_change)

    _listening: list[str | None] = [None]
    current_vars: dict[str, str] = {}
    key_buttons: dict[str, ctk.CTkButton] = {}

    def _stop_listen():
        bid = _listening[0]
        if bid:
            btn = key_buttons.get(bid)
            if btn:
                v = current_vars.get(bid, '')
                disp = v.upper() if v and len(v) <= 3 else v or '—'
                btn.configure(text=disp, fg_color=_blend(_CYAN, 0.1) if v else _BG, text_color=_CYAN if v else '#555566', border_color=_blend(_CYAN, 0.4) if v else _BRD)  # type: ignore[call-arg]
        _listening[0] = None
        win.unbind('<Key>')

    def _on_key(event, bid: str, game_name: str):
        key = _norm_key(event.keysym)
        if not key or key == '??': return
        current_vars[bid] = key
        _stop_listen()
        _save_changes(game_name)

    def _start_listen(bid: str, game_name: str):
        _stop_listen()
        _listening[0] = bid
        btn = key_buttons[bid]
        btn.configure(text=i18n.tr('editor.press'), fg_color=_blend(_AMBER, 0.15), text_color=_AMBER, border_color=_blend(_AMBER, 0.5))  # type: ignore[call-arg]
        win.bind('<Key>', lambda e: _on_key(e, bid, game_name))

    def _on_spell_grid_change(game_name: str, set_num: int, slot_num: int, chosen_name: str):
        data = profiles_data[game_name]
        spells = data.get('spells', [])
        for s in spells:
            if s.get('set') == set_num and s.get('key') == str(slot_num):
                s.pop('set', None)
                s.pop('key', None)
        if chosen_name != '—':
            for s in spells:
                if s.get('name') == chosen_name:
                    s['set'] = set_num
                    s['key'] = str(slot_num)
                    break
        _save_changes(game_name)
        _load_game_tab(game_name)

    def _add_custom_macro(game_name: str):
        d = ctk.CTkToplevel(win)
        d.title(i18n.tr("editor.new_command"))
        d.geometry("460x440")
        d.resizable(False, False)
        
        _apply_window_icon(d, hud)
        
        _set_dark_title_bar(d)
        d.configure(fg_color=_BG)  # type: ignore[call-arg]
        d.transient(win)
        
        is_ets = 'truck' in game_name.lower() or 'ets' in game_name.lower()
        ph_name = i18n.tr("ui.подготовь_тягач") if is_ets else "Revelio..."
        ph_vars = i18n.tr("ui.заведи_включи_свет_поехал") if is_ets else i18n.tr("ui.ревелио_покажи_скрытое")

        hdr_f = tk.Frame(d, bg=_BG)
        hdr_f.pack(fill='x', pady=(hud._px(25), hud._px(10)))
        tk.Label(hdr_f, text=i18n.tr("editor.create_macro"), bg=_BG, fg=_GREEN, font=(hud._F, JStyle.TEXT_H2, 'bold')).pack(side='left', padx=hud._px(35))
        
        tk.Label(d, text=i18n.tr("editor.command_name"), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=45, pady=(15, 0))
        name_e = ctk.CTkEntry(d, placeholder_text=ph_name, width=370, height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL, border_width=1, border_color=_BRD_I, font=(hud._F, JStyle.TEXT_BODY))
        name_e.pack(pady=(5, 10))
        
        tk.Label(d, text=i18n.tr("editor.voice_variants"), bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=45)
        vars_e = ctk.CTkEntry(d, placeholder_text=ph_vars, width=370, height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL, border_width=1, border_color=_BRD_I, font=(hud._F, JStyle.TEXT_BODY))
        vars_e.pack(pady=(5, 10))

        tk.Label(d, text=i18n.tr("editor.first_action"), bg=_BG, fg=_AMBER, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(anchor='w', padx=45)
        first_cmd_cb = ctk.CTkComboBox(d, values=['—'] + _BIND_LIST, width=370, height=JStyle.H_NORM, corner_radius=JStyle.RAD_PANEL, border_width=1, border_color=_BRD_I, 
                                      dropdown_font=(hud._F, JStyle.TEXT_BODY), dropdown_fg_color=_PANEL)
        first_cmd_cb.set('—')
        first_cmd_cb.pack(pady=(5, 25))
        
        def _done():
            nm = name_e.get().strip()
            vr = [v.strip().lower() for v in vars_e.get().split(',') if v.strip()]
            first_ru = first_cmd_cb.get()
            
            if not nm: return
            if not vr: vr = [nm.lower()]
            
            initial_seq = []
            if first_ru != '—':
                initial_seq.append({"binding": _RU_TO_BIND.get(first_ru, first_ru)})
            else:
                initial_seq.append({"wait": 0.5})

            data = profiles_data[game_name]
            if 'spells' not in data: data['spells'] = []
            data['spells'].append({"name": nm, "variants": vr, "sequence": initial_seq})
            _save_changes(game_name)
            d.destroy()
            _load_game_tab(game_name)

        ctk.CTkButton(d, text=i18n.tr("editor.create_and_edit"), command=_done, 
                      fg_color=_GREEN, text_color=_BG, font=(hud._F, JStyle.TEXT_BODY, 'bold'), 
                      height=JStyle.H_HUGE, corner_radius=JStyle.RAD_PANEL).pack(pady=10, padx=45, fill='x')

    def _open_sequence_editor(game_name: str, entry: dict):
        if not entry: return
        d = ctk.CTkToplevel(win)
        d.title(f"{i18n.tr('editor.command')}: {entry.get('name')}")
        d.geometry("640x540")
        d.minsize(400, 300)

        _apply_window_icon(d, hud)

        _set_dark_title_bar(d)
        d.after(200, lambda: _set_dark_title_bar(d))
        d.configure(fg_color=_BG)  # type: ignore[call-arg]
        d.transient(win)
        d.lift()
        d.focus_force()
        d.attributes('-topmost', True)
        d.after(300, lambda: d.attributes('-topmost', False))
        
        def _delete_macro():
            conf = ctk.CTkToplevel(d)
            conf.title(i18n.tr("editor.delete_macro"))
            conf.geometry("400x240")
            conf.resizable(False, False)
            _apply_window_icon(conf, hud)
            _set_dark_title_bar(conf)
            conf.configure(fg_color=_BG)  # type: ignore[call-arg]
            conf.transient(d); conf.grab_set()
            
            tk.Label(conf, text=i18n.tr("editor.confirm"), bg=_BG, fg=_RED, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(pady=(25, 10))
            tk.Label(conf, text=i18n.tr("editor.delete_confirm").format(entry.get('name')), 
                      bg=_BG, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), justify='center').pack(pady=10)
            
            btn_f = tk.Frame(conf, bg=_BG)
            btn_f.pack(fill='x', side='bottom', pady=25, padx=30)
            
            def _real_del():
                data = profiles_data[game_name]
                if 'spells' in data:
                    data['spells'] = [s for s in data['spells'] if s.get('name') != entry.get('name')]
                    _save_changes(game_name)
                conf.destroy(); d.destroy()
                _load_game_tab(game_name)
            
            ctk.CTkButton(btn_f, text=i18n.tr('buttons.delete'), fg_color=_RED, hover_color=_blend(_RED, 0.7), 
                          text_color=_WHITE, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), height=JStyle.H_NORM, width=150,
                          command=_real_del).pack(side='left', expand=True, padx=5)
            ctk.CTkButton(btn_f, text=i18n.tr('buttons.cancel'), fg_color=_PANEL, hover_color=_BRD_I,
                          text_color=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), height=JStyle.H_NORM, width=150,
                          command=conf.destroy).pack(side='right', expand=True, padx=5)
        
        hdr_f = tk.Frame(d, bg=_BG)
        hdr_f.pack(fill='x', pady=(25, 10))
        
        # 1. Delete Button FIRST (to reserve space)
        ctk.CTkButton(hdr_f, text=i18n.tr("editor.delete_macro"), width=140, height=JStyle.H_NORM, fg_color="transparent", 
                     text_color=_RED, hover_color=_blend(_RED, 0.1), font=(hud._F, JStyle.TEXT_BODY, 'bold'),
                     border_width=1, border_color=_blend(_RED, 0.3),
                     command=_delete_macro).pack(side='right', padx=35)
        
        # 2. Title (fill remaining space with dynamic font sizing and wrapping)
        title_text = entry.get('name', 'МАКРОС').upper()
        fs = 14
        if len(title_text) > 30: fs = 12
        if len(title_text) > 40: fs = 10
        
        tk.Label(hdr_f, text=title_text, bg=_BG, fg=_AMBER, 
                 font=(hud._F, hud._fs(fs), 'bold'), 
                 wraplength=350, justify='left', anchor='w').pack(side='left', padx=(20, 10), fill='x', expand=True)
        
        # --- CUSTOM SCROLLABLE AREA ---
        scroll_f = tk.Frame(d, bg=_BG)
        scroll_f.pack(fill='both', expand=True, padx=25, pady=5)
        
        s_canvas = tk.Canvas(scroll_f, bg=_BG, highlightthickness=0)
        s_vsb = _HudScrollbar(scroll_f, s_canvas, color=_AMBER)
        s_canvas.configure(yscrollcommand=s_vsb.set)
        s_canvas.pack(side='left', fill='both', expand=True)
        
        scroll = tk.Frame(s_canvas, bg=_BG)
        s_window = s_canvas.create_window((0, 0), window=scroll, anchor='nw')
        
        def _on_s_resize(e):
            s_canvas.itemconfig(s_window, width=e.width)
            s_canvas.configure(scrollregion=s_canvas.bbox('all'))
        s_canvas.bind('<Configure>', _on_s_resize)

        def _on_s_mousewheel(e):
            try:
                if s_canvas.winfo_exists():
                    s_canvas.yview_scroll(-1 * (e.delta // 120), 'units')
            except: pass
        s_canvas.bind_all('<MouseWheel>', _on_s_mousewheel)
        
        seq = list(entry.get('sequence', []))  # mutable copy

        # Resolve "MACRO" placeholder steps to real bindings or keys
        _resolved_seq = []
        for step in seq:
            if step.get('key') == 'MACRO':
                # Try to resolve from entry's binding or from profiles_data
                if entry.get('binding'):
                    _resolved_seq.append({'binding': entry['binding'], 'hold': step.get('hold', 0.1)})
                elif entry.get('key') and entry['key'] != 'MACRO':
                    _resolved_seq.append({'key': entry['key'], 'hold': step.get('hold', 0.1)})
                else:
                    # Try to look up via profiles_data bindings
                    _bid = entry.get('binding', '')
                    _pdata = profiles_data.get(game_name, {})
                    _real_key = _pdata.get('bindings', {}).get(_bid, '')
                    if _real_key and _real_key != 'MACRO':
                        _resolved_seq.append({'key': _real_key, 'hold': step.get('hold', 0.1)})
                    else:
                        _resolved_seq.append(step)
            else:
                _resolved_seq.append(step)
        seq = _resolved_seq

        # Bootstrap: if seq still empty, create from entry data
        if not seq and entry.get('key') and entry['key'] != 'MACRO':
            seq = [{'key': entry['key'], 'hold': 0.1}]
        elif not seq and entry.get('binding'):
            seq = [{'binding': entry['binding']}]
            
        step_widgets = []

        def _render():
            for w in scroll.winfo_children(): w.destroy()
            step_widgets.clear()
            
            # --- SPECIAL TELEMETRY ACTION (if exists) ---
            t_action = entry.get('telemetry_action')
            if t_action:
                has_seq = len(seq) > 0
                t_card = ctk.CTkFrame(scroll, fg_color=_PANEL, corner_radius=JStyle.RAD_PANEL, border_width=1, border_color=_blend(_AMBER if not has_seq else _blend(_AMBER, 0.4), 0.4))
                t_card.pack(fill='x', pady=(0, 10), padx=(0, 10))
                ctk.CTkFrame(t_card, fg_color=_AMBER if not has_seq else _blend(_AMBER, 0.4), width=5, corner_radius=2.5).pack(side='left', fill='y', padx=(6, 0), pady=10)
                t_cont = tk.Frame(t_card, bg=_PANEL)
                t_cont.pack(side='left', fill='both', expand=True, padx=12, pady=6 if has_seq else 12)
                
                type_lbl = i18n.tr("editor.system_trigger") if has_seq else i18n.tr("editor.telemetry_request")
                tk.Label(t_cont, text=type_lbl, bg=_PANEL, fg=_AMBER, font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(anchor='w')
                tk.Label(t_cont, text=_TELEMETRY_RU.get(t_action, t_action), bg=_PANEL, fg=_WHITE, font=(hud._F, JStyle.TEXT_SMALL, 'bold')).pack(anchor='w', pady=(1, 0))
                
                if not has_seq:
                    tk.Label(t_cont, text=i18n.tr("editor.telemetry_desc"), bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_TINY)).pack(anchor='w', pady=(2, 0))
                else:
                    tk.Label(t_cont, text=i18n.tr("editor.engine_desc"), bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_TINY)).pack(anchor='w', pady=(1, 0))

            for i, step in enumerate(seq):
                color = _AMBER if 'wait' in step else (_CYAN if 'key' in step else _MAG)
                icon  = "\u23f1" if 'wait' in step else ("\u2328" if 'key' in step else "\u2605")

                # Outer border frame (simulates rounded look without CTkFrame padding)
                outer = tk.Frame(scroll, bg=_blend(color, 0.25), padx=1, pady=1)
                outer.pack(fill='x', pady=2, padx=(0, 10))
                card = tk.Frame(outer, bg=_PANEL)
                card.pack(fill='x')

                # Left accent stripe
                tk.Frame(card, bg=color, width=4).pack(side='left', fill='y', padx=(4, 0))

                # Checkbox container
                left_icons = tk.Frame(card, bg=_PANEL)
                left_icons.pack(side='left', fill='y', padx=(8, 0))

                # Checkbox
                var = tk.BooleanVar(value=not step.get('_disabled', False))
                cb = ctk.CTkCheckBox(left_icons, text="", variable=var, width=28, height=JStyle.H_TOOL,
                                     corner_radius=JStyle.RAD_BTN, fg_color=_GREEN, checkmark_color=_BG,
                                     border_color=_blend(_GREEN, 0.5), hover_color=_blend(_GREEN, 0.25),
                                     border_width=2, command=_render)
                cb.pack(expand=True)

                # Icon — separate fixed-width frame so center of icon = center of card
                icon_f = tk.Frame(card, bg=_PANEL, width=hud._px(30))
                icon_f.pack(side='left', fill='y', padx=(4, 4))
                icon_f.pack_propagate(False)
                tk.Label(icon_f, text=icon, bg=_PANEL, fg=color,
                         font=(hud._F, JStyle.TEXT_H2)).place(relx=0.5, rely=0.5, anchor='center')

                # Content — controls the actual height of the card
                content = tk.Frame(card, bg=_PANEL)
                content.pack(side='left', fill='both', expand=True, pady=6)

                if 'wait' in step:
                    tk.Label(content, text=i18n.tr("editor.pause"), bg=_PANEL, fg=_DIM,
                             font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(anchor='w')
                    val_e = ctk.CTkEntry(content, width=85, height=JStyle.H_TOOL, border_width=1,
                                         corner_radius=JStyle.RAD_BTN, font=(hud._F, JStyle.TEXT_SMALL))
                    val_e.insert(0, str(step['wait']))
                    val_e.pack(side='left', pady=(2, 0))
                    step_widgets.append(('wait', var, val_e, None))
                else:
                    is_bind = 'binding' in step
                    tk.Label(content,
                             text=i18n.tr("editor.game_action") if is_bind else i18n.tr("editor.press_key_step"),
                             bg=_PANEL, fg=_DIM,
                             font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(anchor='w')

                    if is_bind:
                        raw_b = step.get('binding', '')
                        ru_b  = _RU_LABELS.get(raw_b, raw_b)

                        def _pick_cb(chosen, s_idx=i):
                            seq[s_idx]['binding'] = _RU_TO_BIND.get(chosen, chosen)
                            _render()

                        from ui.hud_widgets import _HUDSearchableDropdown
                        v_var = tk.StringVar(value=ru_b)
                        val_e = _HUDSearchableDropdown(hud, content, _BIND_LIST, v_var,
                                                       command=_pick_cb, accent=_MAG)
                        val_e.frame.pack(side='left', pady=(2, 0), fill='x', expand=True, padx=(0, 8))
                    else:
                        val_e = ctk.CTkEntry(content, width=110, height=JStyle.H_TOOL, border_width=1,
                                              corner_radius=JStyle.RAD_BTN, font=(hud._F, JStyle.TEXT_SMALL))
                        
                        raw_k = step.get('key', '')
                        # Resolve "MACRO" placeholder to actual key for display
                        if raw_k == 'MACRO' and entry and entry.get('key'):
                            disp_k = entry.get('key', '').upper()
                        else:
                            disp_k = raw_k.upper()
                            
                        val_e.insert(0, disp_k)
                        val_e.pack(side='left', pady=(2, 0))

                    hld_e = None
                    if 'hold' in step or not is_bind:
                        tk.Label(content, text="УДЕРЖ:", bg=_PANEL, fg=_DIM,
                                 font=(hud._F, JStyle.TEXT_TINY)).pack(side='left', padx=(10, 0), pady=(4, 0))
                        hld_e = ctk.CTkEntry(content, width=60, height=JStyle.H_TOOL, border_width=1,
                                              corner_radius=JStyle.RAD_BTN, font=(hud._F, JStyle.TEXT_SMALL))
                        hld_e.insert(0, str(step.get('hold', 0.1)))
                        hld_e.pack(side='left', padx=4, pady=(2, 0))
                    step_widgets.append(('bind' if is_bind else 'key', var, val_e, hld_e))

                # Delete button
                ctk.CTkButton(card, text="×", width=30, height=JStyle.H_TOOL, fg_color="transparent",
                              text_color=_RED, hover_color=_blend(_RED, 0.15),
                              font=(hud._F, JStyle.TEXT_H2),
                              command=lambda idx=i: _del(idx)).pack(side='right', padx=8)
            
            d.after(100, lambda: s_canvas.configure(scrollregion=s_canvas.bbox('all')))

        def _del(idx):
            seq.pop(idx)
            _render()

        def _save():
            new_seq = []
            for i, (stype, var, val_e, hld_e) in enumerate(step_widgets):
                s = {}
                active = var.get()
                
                # If it's a dropdown, it might be a _HUDSearchableDropdown (not a ctk.Entry)
                # But it has a 'variable' attribute or we can use get() if it's a widget
                if hasattr(val_e, 'variable'):
                    val = val_e.variable.get()
                elif hasattr(val_e, 'get'):
                    val = val_e.get()
                else:
                    val = ''

                if stype == 'wait':
                    try: s['wait'] = float(val)
                    except: s['wait'] = 0.5
                elif stype == 'bind':
                    s['binding'] = _RU_TO_BIND.get(val, val)
                else:
                    s['key'] = val
                    if hld_e:
                        try: s['hold'] = float(hld_e.get())
                        except: s['hold'] = 0.1
                if not active: s['_disabled'] = True
                new_seq.append(s)
            
            entry['sequence'] = new_seq
            # Do NOT pop 'key' or 'binding' - we want to keep them for primary display and reference
            _save_changes(game_name)
            d.destroy()
            _load_game_tab(game_name)

        _render()
        
        # Bottom controls
        bottom_f = tk.Frame(d, bg=_BG)
        bottom_f.pack(fill='x', side='bottom', pady=(10, 30), padx=25)
        
        add_bar = tk.Frame(bottom_f, bg=_BG)
        add_bar.pack(anchor='center', pady=(0, 20))
        
        ctk.CTkButton(add_bar, text=i18n.tr("editor.add_command"), width=145, height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), 
                      fg_color=_blend(_MAG, 0.1), hover_color=_blend(_MAG, 0.2),
                      text_color=_MAG, border_width=1, border_color=_blend(_MAG, 0.3),
                      command=lambda: (seq.append({"binding": "engine"}), _render())).pack(side='left', padx=8)


        ctk.CTkButton(add_bar, text=i18n.tr("editor.add_key"), width=145, height=JStyle.H_NORM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), 
                      fg_color=_blend(_CYAN, 0.1), hover_color=_blend(_CYAN, 0.2),
                      text_color=_CYAN, border_width=1, border_color=_blend(_CYAN, 0.3),
                      command=lambda: (seq.append({"key": "..."}), _render())).pack(side='left', padx=15)
        
        ctk.CTkButton(add_bar, text=i18n.tr("editor.add_pause"), width=160, height=JStyle.H_LARGE, font=(hud._F, JStyle.TEXT_BODY, 'bold'), 
                      fg_color=_blend(_AMBER, 0.1), hover_color=_blend(_AMBER, 0.2),
                      text_color=_AMBER, border_width=1, border_color=_blend(_AMBER, 0.3),
                      command=lambda: (seq.append({"wait": 0.5}), _render())).pack(side='left', padx=15)
        
        ctk.CTkButton(bottom_f, text=i18n.tr("editor.save_changes"), fg_color=_CYAN, text_color=_BG, 
                      font=(hud._F, JStyle.TEXT_BODY, 'bold'), height=JStyle.H_HUGE, corner_radius=JStyle.RAD_PANEL,
                      command=_save).pack(fill='x')


    def _save_changes(game_name: str):
        data = profiles_data[game_name]
        # Check if it was a binding or a spell key
        if 'bindings' in data and any(bid in data['bindings'] for bid in current_vars):
            for bid, val in current_vars.items():
                if bid in data['bindings']:
                    data['bindings'][bid] = val
        
        # Check spells
        for spell in data.get('spells', []):
            s_id = f"spell_{spell.get('name')}"
            if s_id in current_vars:
                val = current_vars[s_id]
                spell['key'] = val
                # If user manually set a real key, we should usually remove the macro sequence
                # to prevent conflicts and ensure the new key is what actually works.
                if val and val != 'MACRO' and 'sequence' in spell:
                    # Keep only if it's a "dummy" sequence (wait only) or telemetry
                    if not spell.get('telemetry_action'):
                        spell.pop('sequence', None)
        
        profile_files[game_name].write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # If active, reload
        _m = sys.modules.get('__main__')
        if _m and getattr(_m, '_game_profile', '') == game_name and getattr(_m, '_game_mode', False):
            try:
                from actions.game_input import load_profile
                load_profile(profile_files[game_name].stem)
            except: pass


    def _load_game_tab(game_name: str):
        nonlocal current_game
        current_game = game_name
        win._current_game_name = game_name  # track for search
        
        # UI Tab Indicators
        for g, b_tuple in tab_buttons.items():
            btn, ind = b_tuple
            if g == game_name:
                btn.configure(text_color=_CYAN, fg_color=_blend(_CYAN, 0.05))  # type: ignore[call-arg]
                ind.configure(bg=_CYAN)  # type: ignore[call-arg]
            else:
                btn.configure(text_color=_DIM, fg_color='transparent')  # type: ignore[call-arg]
                ind.configure(bg=_BG)  # type: ignore[call-arg]
        
        # Hide all cached frames
        for f in tab_frames.values():
            f.pack_forget()
            
        # If already built, just show it
        if game_name in tab_frames:
            tab_frames[game_name].pack(fill='both', expand=True)
            # Re-sync variables for this game
            _sync_vars_from_cache(game_name)
            
            # Reset scroll for cached tab
            win.update_idletasks()
            canvas.yview_moveto(0)
            _update_scroll()
            return

        # Build new frame for this game
        game_f = tk.Frame(inner, bg=_BG)
        game_f.pack(fill='both', expand=True)
        tab_frames[game_name] = game_f
        
        data = profiles_data[game_name]
        is_hogwarts = 'hogwarts' in game_name.lower()
        

        # --- STANDARD MACRO LIST ---
        items_to_show = [] # (id, label, current_val, is_binding, original_entry)
        
        if 'bindings' in data:
            for bid, val in data['bindings'].items():
                items_to_show.append((bid, _RU_LABELS.get(bid, bid.replace('_', ' ').title()), val, True, None))
        
        # Add spells that are NOT in the grid or are general actions
        for spell in data.get('spells', []):
            s_set = spell.get('set')
            s_key = str(spell.get('key', ''))
            # Skip if it's part of the grid (sets 1-4, keys 1-4)
            if is_hogwarts and s_set in (1, 2, 3, 4) and s_key in ('1', '2', '3', '4'):
                continue
            
            # Show ONLY entries with a direct key assignment (not macro-only)
            # Macros (sequence-only) are edited via the ▶ button, not here
            has_direct_key = spell.get('key') or spell.get('keys')
            if has_direct_key and not spell.get('mouse'):
                s_id = f"spell_{spell.get('name')}"
                if spell.get('keys'):
                    key_disp = ','.join(spell.get('keys'))
                else:
                    key_disp = spell.get('key')
                items_to_show.append((s_id, spell.get('name'), key_disp, False, spell))

        # --- SEARCH FILTER ---
        _q = search_pill.get().strip().lower()
        _is_placeholder = False
        def _clean_label(t: str) -> str:
            import re
            t = re.sub(r'\s*\([^)]*\)', '', t)
            t = t.split(' / ')[0]
            overrides = {
                'Запуск двигателя': 'Двигатель',
                'Запуск / Остановка Двигателя': 'Двигатель',
                'Газ / Ускорение': 'Газ',
                'Тормоз / Остановка': 'Тормоз',
                'Покинуть / Сесть в технику': 'Техника',
                'Следующая машина в списке': 'След. техника',
                'Предыдущая машина в списке': 'Пред. техника',
                'Передача: Выше': 'Передача+',
                'Передача: Ниже': 'Передача-',
                'Запуск двигуна': 'Двигун',
                'Запуск / Зупинка Двигуна': 'Двигун',
                'Газ / Прискорення': 'Газ',
                'Гальмо / Зупинка': 'Гальмо',
                'Покинути / Сісти в техніку': 'Техніка',
                'Наступна машина в списку': 'Наст. техніка',
                'Попередня машина в списку': 'Попер. техніка',
                'Передача: Вище': 'Передача+',
                'Передача: Нижче': 'Передача-'
            }
            res = overrides.get(t, t).strip()
            return res.upper()

        # Build list of items to show (cleaned and filtered)
        visible_items = []
        for (bid, label_text, key_val, is_bind, entry) in items_to_show:
            # Filter pure telemetry
            if entry and entry.get('telemetry_action') and not entry.get('sequence') \
               and not entry.get('key') and not entry.get('keys'):
                continue
            
            clean_name = _clean_label(label_text)
            
            # Apply Search Filter
            if _q and not _is_placeholder:
                if not (_q in clean_name.lower() or _q in str(key_val).lower()):
                    continue
                    
            visible_items.append((bid, clean_name, key_val, is_bind, entry))

        if not visible_items and _q and not _is_placeholder:
            tk.Label(game_f, text=i18n.tr("editor.nothing_found").format(_q),
                     bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_BODY), anchor='center'
                     ).pack(expand=True, fill='both', pady=60)
            return

        for i, (bid, label_text, key_val, is_bind, entry) in enumerate(visible_items):

            row_bg = _PANEL if i % 2 == 0 else _BG
            row = tk.Frame(game_f, bg=row_bg, height=hud._px(64))
            row.pack(fill='x', pady=hud._px(2)) # padx убран, он теперь на grid_container
            # --- 3-КОЛОНОЧНАЯ РАЗМЕТКА (ИДЕНТИЧНО ШАПКЕ) ---
            row.grid_columnconfigure(0, minsize=hud._px(50), weight=0)
            row.grid_columnconfigure(1, weight=1)
            row.grid_columnconfigure(2, minsize=hud._px(300), weight=0)
            row.grid_rowconfigure(0, weight=1)
            row.grid_rowconfigure(0, weight=1)

            # 1. Иконка
            tk.Label(row, text='★', bg=row_bg, fg=_blend(_CYAN, 0.7), font=(hud._F, JStyle.TEXT_H1)).grid(row=0, column=0, sticky='nsew', padx=0)
            
            # 2. Название Макроса
            lbl_text = label_text.upper() if is_bind else label_text
            l_lbl = ctk.CTkLabel(row, text=lbl_text, fg_color='transparent',
                                 text_color=_TEXT if (key_val and key_val != 'MACRO') else _DIM, 
                                 font=(hud._F, JStyle.TEXT_BODY), anchor='w')
            l_lbl.grid(row=0, column=1, sticky='ew', padx=(hud._px(10), hud._px(10)))
            
            # 3. Блок управления (Клавиша + Инструменты)
            ctrl_f = tk.Frame(row, bg=row_bg)
            ctrl_f.grid(row=0, column=2, sticky='nsew')
            ctrl_f.columnconfigure(0, weight=1)
            ctrl_f.columnconfigure(1, weight=1)
            ctrl_f.rowconfigure(0, weight=1)

            if key_val and key_val not in ('—', 'MACRO', 'ИНФО'):
                disp = str(key_val).upper()
                current_vars[bid] = key_val
            else:
                disp = '—'
                current_vars[bid] = ''
            
            btn = ctk.CTkButton(ctrl_f, text=disp, 
                                fg_color=_blend(_CYAN, 0.1) if key_val else 'transparent', 
                                hover_color=_blend(_CYAN, 0.2),
                                text_color=_CYAN if key_val else _DIM, 
                                border_color=_blend(_CYAN, 0.4) if key_val else _BRD_I, 
                                border_width=1, corner_radius=JStyle.RAD_BTN, 
                                font=(hud._F, JStyle.TEXT_BODY, 'bold'), 
                                height=JStyle.H_TOOL, width=110)
            key_buttons[bid] = btn
            btn.configure(command=lambda b=bid: _start_listen(b, game_name))
            btn.grid(row=0, column=0) # Центровка в левой половине блока управления

            tools_f = tk.Frame(ctrl_f, bg=row_bg)
            tools_f.grid(row=0, column=1) # Центровка в правой половине блока управления
            
            def _test_cmd(e=entry, gn=game_name, b=bid, kv=key_val):
                try:
                    from actions.game_input import execute_by_name
                    name_to_run = e.get('name') if e else label_text
                    execute_by_name(name_to_run)
                except: pass

            test_btn = ctk.CTkButton(tools_f, text='▶', 
                                   fg_color='transparent', hover_color=_blend(_GREEN, 0.12), 
                                   text_color=_GREEN if key_val or (entry and entry.get('sequence')) else _DIM, 
                                   width=36, height=JStyle.H_NORM, corner_radius=18,
                                   font=(hud._F, JStyle.TEXT_H2),
                                   command=_test_cmd)
            test_btn.pack(side='left', padx=2)
            if not (key_val or (entry and entry.get('sequence'))): test_btn.configure(state='disabled')

            edit_btn = ctk.CTkButton(tools_f, text='⚙', 
                                   fg_color='transparent', hover_color=_blend(_AMBER, 0.15), 
                                   text_color=_AMBER, 
                                   width=36, height=JStyle.H_NORM, corner_radius=18,
                                   font=(hud._F, JStyle.TEXT_H2),
                                   command=lambda e=entry, gn=game_name: _open_sequence_editor(gn, e if e else {'name': label_text, 'binding': bid}))
            edit_btn.pack(side='left', padx=2)

            def _clear(b=bid, gn=game_name):
                _stop_listen()
                current_vars[b] = ''
                key_buttons[b].configure(text='—', fg_color='transparent', text_color=_DIM, border_color=_BRD_I)  # type: ignore[call-arg]
                _save_changes(gn)

            del_btn = ctk.CTkButton(tools_f, text='✕', 
                                   fg_color='transparent', hover_color=_blend(_RED, 0.12), 
                                   text_color=_RED, 
                                   width=36, height=JStyle.H_NORM, corner_radius=18,
                                   font=(hud._F, JStyle.TEXT_H2, 'bold'),
                                   command=lambda b=bid: _clear(b))
            del_btn.pack(side='left', padx=2)
            if not key_val: del_btn.configure(state='disabled')
        
        # --- ADD CUSTOM COMMAND BUTTON (At the end of the list) ---
        add_f = tk.Frame(game_f, bg=_BG)
        add_f.pack(fill='x', padx=8, pady=(15, 25))
        ctk.CTkButton(add_f, text='+ ДОБАВИТЬ МАКРОС / КОМАНДУ', 
                      font=(hud._F, JStyle.TEXT_BODY, 'bold'),
                      fg_color=_blend(_GREEN, 0.1), hover_color=_blend(_GREEN, 0.2),
                      text_color=_GREEN, border_color=_blend(_GREEN, 0.4), border_width=1,
                      height=JStyle.H_LARGE, corner_radius=JStyle.RAD_PANEL,
                      command=lambda: _add_custom_macro(game_name)).pack(fill='x', padx=60)
        
        # Non-blocking layout update — schedule scroll recalc after rendering
        canvas.yview_moveto(0)
        win.after(10, _update_scroll)
        
        # --- DYNAMIC ADAPTIVE HEIGHT ---
        def _adapt_height():
            win.update_idletasks()
            # Calculate content height from game_f (scroll area contents)
            content_h = game_f.winfo_reqheight() + 180 # Room for header/search
            screen_h = win.winfo_screenheight()
            
            # Clamp height between 400 and 80% of screen
            new_h = int(max(400, min(content_h, screen_h * 0.80)))
            curr_w = win.winfo_width()
            if curr_w < 100: curr_w = 880
            
            win.geometry(f"{curr_w}x{new_h}")
            
        win.after(150, _adapt_height)

    def _sync_vars_from_cache(game_name: str):
        # Implementation to update key_buttons and current_vars 
        # based on what's visible in the cached frame
        pass # Will refine if needed, but the labels are already built

    # --- Determine which games to show tabs for ---
    # Filter by installed game extensions in Extension Manager
    _m = sys.modules.get('__main__')
    _active_profile = getattr(_m, '_game_profile', '') if _m else ''
    
    # Map game extension IDs to keyword matches against profile names
    _EXT_GAME_MAP = {
        'game_ets2':     ('euro truck', 'ets2', 'ets'),
        'game_fs22':     ('farming simulator', 'fs22', 'farming'),
        'game_hogwarts': ('hogwarts', 'harry potter'),
    }
    
    import threading
    _installed_ids: set = set()

    def _fetch_extensions():
        try:
            from core.extensions import ExtensionManager
            ids = {e['id'] for e in ExtensionManager().list_installed()}
            _installed_ids.update(ids)
        except Exception:
            pass

    _ext_thread = threading.Thread(target=_fetch_extensions, daemon=True)
    _ext_thread.start()
    _ext_thread.join(timeout=1.5)  # Increased timeout for reliability
    
    def _is_game_installed(gname: str) -> bool:
        low = gname.lower()
        for ext_id, keywords in _EXT_GAME_MAP.items():
            if ext_id in _installed_ids:
                if any(kw in low for kw in keywords):
                    return True
        return False
    
    # Build tabs_to_show: only installed game profiles
    # Fallback to all if none match (e.g. first run / no extensions data)
    tabs_to_show = [g for g in sorted_games if _is_game_installed(g)]
    # Safe fallback: only show profiles whose extension is actually installed
    # If the extension manager failed completely (empty set), show nothing extra
    if not tabs_to_show and not _installed_ids:
        tabs_to_show = sorted_games  # extension manager unavailable, show all
    
    _GAME_ICONS = {
        'euro truck': '🚛', 'ets': '🚛', 'ets2': '🚛',
        'farming': '🚜', 'fs22': '🚜', 'farming simulator': '🚜',
        'hogwarts': '⚡', 'harry potter': '⚡',
    }
    
    def _get_game_icon(gname: str) -> str:
        low = gname.lower()
        for kw, ico in _GAME_ICONS.items():
            if kw in low: return ico
        return '🎮'

    # Build tab buttons with modern style
    for gname in tabs_to_show:
        is_active_game = (gname == _active_profile)
        ico = _get_game_icon(gname)
        
        # Shorten name: "Euro Truck Simulator 2" → "ETS 2", etc.
        short = gname.upper()
        if 'EURO TRUCK SIMULATOR' in short: short = 'ETS 2'
        elif 'FARMING SIMULATOR' in short: short = 'FS 22'
        elif 'HOGWARTS LEGACY' in short: short = 'HOGWARTS'
        
        t_f = tk.Frame(tab_inner, bg=_BG)
        t_f.pack(side='left')
        
        tab_color = _CYAN if is_active_game else _DIM
        btn_bg = _blend(_CYAN, 0.08) if is_active_game else 'transparent'
        
        btn = ctk.CTkButton(t_f,
                            text=f'{ico}  {short}',
                            font=(hud._F, JStyle.TEXT_BODY, 'bold' if is_active_game else 'normal'),
                            height=JStyle.H_LARGE, corner_radius=0,
                            fg_color=btn_bg,
                            text_color=tab_color,
                            hover_color=_blend(_CYAN, 0.12),
                            command=lambda g=gname: _load_game_tab(g))
        btn.pack(fill='x', padx=(0, 1))
        
        ind = tk.Frame(t_f, bg=_CYAN if is_active_game else _BG, height=3)
        ind.pack(fill='x')
        
        tab_buttons[gname] = (btn, ind)
    
    # Show window skeleton immediately, load content deferred
    _loading_lbl = tk.Label(inner, text='\u23f3  Загрузка...', bg=_BG, fg=_DIM,
                            font=(hud._F, JStyle.TEXT_BODY))
    _loading_lbl.pack(expand=True)

    def _deferred_load():
        _loading_lbl.destroy()
        _load_game_tab(current_game)

    win.after(40, _deferred_load)
    
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='bottom')

