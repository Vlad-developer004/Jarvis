from __future__ import annotations
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon
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
    
    # 1. Load all profiles
    for p in profiles_dir.glob('*.json'):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            game_name = d.get('game', p.stem)
            profiles_data[game_name] = d
            profile_files[game_name] = p
        except Exception:
            pass
            
    if not profiles_data:
        import tkinter.messagebox as mb
        mb.showinfo('Нет профилей', 'Профили управления не найдены в папке data/game_profiles.')
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
    win.title('Редактор макросов и клавиш')
    try:
        if hasattr(hud, '_ico_path'): win.iconbitmap(hud._ico_path)
    except: pass
    win.configure(bg=_BG)
    win.resizable(False, True)
    
    _W, _H = 780, 750
    gw, gh = int(_W * hud.zoom_factor), int(_H * hud.zoom_factor)
    win.geometry(f'{gw}x{gh}')
    
    # --- HEADER ---
    tk.Frame(win, bg=_CYAN, height=3).pack(fill='x')
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', pady=(14, 10))
    tk.Label(hdr, text='⌬', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(20))).pack(side='left', padx=(20, 8))
    title_col = tk.Frame(hdr, bg=_BG)
    title_col.pack(side='left')
    tk.Label(title_col, text='МАКРОСЫ И ГОРЯЧИЕ КЛАВИШИ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(15), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(title_col, text='Глобальная настройка всех игровых профилей', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9)), anchor='w').pack(anchor='w')

    # --- TABS (Scrollable if many) ---
    tab_container = tk.Frame(win, bg=_BG)
    tab_container.pack(fill='x', padx=16, pady=(0, 5))
    
    tab_canvas = tk.Canvas(tab_container, bg=_BG, height=hud._px(40), highlightthickness=0)
    tab_canvas.pack(side='left', fill='x', expand=True)
    
    tab_inner = tk.Frame(tab_canvas, bg=_BG)
    tab_canvas.create_window((0, 0), window=tab_inner, anchor='nw')
    
    tab_buttons: dict[str, ctk.CTkButton] = {}
    
    # --- COLUMN HEADERS ---
    cols_h = tk.Frame(win, bg=_BG)
    cols_h.pack(fill='x', padx=18, pady=(10, 0))
    tk.Label(cols_h, text='КОМАНДА / МАКРОС', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(side='left', padx=(5, 0))
    tk.Label(cols_h, text='ИНСТРУМЕНТЫ', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(side='right', padx=(0, 15))
    tk.Label(cols_h, text='КЛАВИША', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(side='right', padx=(0, 100))
    
    # --- MAIN CONTENT AREA ---
    scroll_area = tk.Frame(win, bg=_BG)
    scroll_area.pack(fill='both', expand=True, pady=(5, 0))
    canvas = tk.Canvas(scroll_area, bg=_BG, highlightthickness=0)
    _vsb = _HudScrollbar(scroll_area, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=_vsb.set)
    canvas.pack(side='left', fill='both', expand=True, padx=(16, 0))
    inner = tk.Frame(canvas, bg=_BG)
    canvas_window = canvas.create_window((0, 0), window=inner, anchor='nw')

    def _on_resize(e):
        canvas.itemconfig(canvas_window, width=e.width)
        canvas.configure(scrollregion=canvas.bbox('all'))
    canvas.bind('<Configure>', _on_resize)
    
    def _on_mousewheel(e):
        if canvas.winfo_exists() and _vsb.winfo_ismapped():
            canvas.yview_scroll(-1 * (e.delta // 120), 'units')
    win.bind('<MouseWheel>', _on_mousewheel)

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
                btn.configure(text=disp, fg_color=_blend(_CYAN, 0.1) if v else _BG, text_color=_CYAN if v else '#555566', border_color=_blend(_CYAN, 0.4) if v else _BRD)
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
        btn.configure(text='Нажмите...', fg_color=_blend(_AMBER, 0.15), text_color=_AMBER, border_color=_blend(_AMBER, 0.5))
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
        d.title("Новая команда")
        d.geometry("460x440")
        d.resizable(False, False)
        
        _apply_window_icon(d, hud)
        
        _set_dark_title_bar(d)
        d.configure(fg_color=_BG)
        d.transient(win)
        d.grab_set()
        
        is_ets = 'truck' in game_name.lower() or 'ets' in game_name.lower()
        ph_name = "Подготовь тягач..." if is_ets else "Revelio..."
        ph_vars = "заведи, включи свет, поехали..." if is_ets else "ревелио, покажи скрытое..."

        hdr_f = tk.Frame(d, bg=_BG)
        hdr_f.pack(fill='x', pady=(25, 10))
        tk.Label(hdr_f, text="СОЗДАНИЕ МАКРОСА", bg=_BG, fg=_GREEN, font=(hud._F, hud._fs(14), 'bold')).pack(side='left', padx=35)
        
        tk.Label(d, text="НАЗВАНИЕ КОМАНДЫ", bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(9), 'bold')).pack(anchor='w', padx=45, pady=(15, 0))
        name_e = ctk.CTkEntry(d, placeholder_text=ph_name, width=370, height=40, corner_radius=10, border_width=1, border_color=_BRD_I, font=(hud._F, hud._fs(11)))
        name_e.pack(pady=(5, 10))
        
        tk.Label(d, text="ГОЛОСОВЫЕ ВАРИАНТЫ", bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9), 'bold')).pack(anchor='w', padx=45)
        vars_e = ctk.CTkEntry(d, placeholder_text=ph_vars, width=370, height=40, corner_radius=10, border_width=1, border_color=_BRD_I, font=(hud._F, hud._fs(11)))
        vars_e.pack(pady=(5, 10))

        tk.Label(d, text="ПЕРВОЕ ДЕЙСТВИЕ (Опционально)", bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(9), 'bold')).pack(anchor='w', padx=45)
        first_cmd_cb = ctk.CTkComboBox(d, values=['—'] + _BIND_LIST, width=370, height=40, corner_radius=10, border_width=1, border_color=_BRD_I, 
                                      dropdown_font=(hud._F, hud._fs(9)), dropdown_fg_color=_PANEL)
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

        ctk.CTkButton(d, text="СОЗДАТЬ И ПЕРЕЙТИ К РЕДАКТИРОВАНИЮ", command=_done, 
                      fg_color=_GREEN, text_color=_BG, font=(hud._F, hud._fs(11), 'bold'), 
                      height=52, corner_radius=12).pack(pady=10, padx=45, fill='x')

    def _open_sequence_editor(game_name: str, entry: dict):
        if not entry: return
        d = ctk.CTkToplevel(win)
        d.title(f"Макрос: {entry.get('name')}")
        d.geometry("560x680")
        d.resizable(False, False)

        _apply_window_icon(d, hud)

        _set_dark_title_bar(d)
        d.configure(fg_color=_BG)
        d.transient(win)
        d.grab_set()
        
        def _delete_macro():
            import tkinter.messagebox as mb
            if mb.askyesno("Удаление", f"Вы уверены, что хотите полностью удалить макрос '{entry.get('name')}'?"):
                data = profiles_data[game_name]
                if 'spells' in data:
                    data['spells'] = [s for s in data['spells'] if s.get('name') != entry.get('name')]
                    _save_changes(game_name)
                d.destroy()
                _load_game_tab(game_name)
        
        hdr_f = tk.Frame(d, bg=_BG)
        hdr_f.pack(fill='x', pady=(25, 10))
        
        # 1. Delete Button FIRST (to reserve space)
        ctk.CTkButton(hdr_f, text="УДАЛИТЬ МАКРОС", width=140, height=36, fg_color="transparent", 
                     text_color=_RED, hover_color=_blend(_RED, 0.1), font=(hud._F, hud._fs(10), 'bold'),
                     border_width=1, border_color=_blend(_RED, 0.3),
                     command=_delete_macro).pack(side='right', padx=35)
        
        # 2. Title (fill remaining space with dynamic font sizing)
        title_text = entry.get('name', 'МАКРОС').upper()
        fs = 15
        if len(title_text) > 28: fs = 13
        if len(title_text) > 36: fs = 11
        if len(title_text) > 48: title_text = title_text[:45] + "..."
        
        tk.Label(hdr_f, text=title_text, bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(fs), 'bold')).pack(side='left', anchor='w', padx=35)
        
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
        
        seq = entry.get('sequence', [])
        if not seq and entry.get('key'):
            seq = [{"key": entry['key']}]
        elif not seq and entry.get('binding'):
            seq = [{"binding": entry['binding']}]
            
        step_widgets = []

        def _render():
            for w in scroll.winfo_children(): w.destroy()
            step_widgets.clear()
            
            # --- SPECIAL TELEMETRY ACTION (if exists) ---
            t_action = entry.get('telemetry_action')
            if t_action:
                has_seq = len(seq) > 0
                t_card = tk.Frame(scroll, bg=_PANEL, highlightthickness=0)
                t_card.pack(fill='x', pady=(0, 10), padx=(0, 10))
                tk.Frame(t_card, bg=_AMBER if not has_seq else _blend(_AMBER, 0.4), width=5).pack(side='left', fill='y')
                t_cont = tk.Frame(t_card, bg=_PANEL)
                t_cont.pack(side='left', fill='both', expand=True, padx=12, pady=6 if has_seq else 12)
                
                type_lbl = "СИСТЕМНЫЙ ТРИГГЕР API" if has_seq else "ЗАПРОС ДАННЫХ ТЕЛЕМЕТРИИ"
                tk.Label(t_cont, text=type_lbl, bg=_PANEL, fg=_AMBER, font=(hud._F, hud._fs(7), 'bold')).pack(anchor='w')
                tk.Label(t_cont, text=_TELEMETRY_RU.get(t_action, t_action), bg=_PANEL, fg=_WHITE, font=(hud._F, hud._fs(9), 'bold')).pack(anchor='w', pady=(1, 0))
                
                if not has_seq:
                    tk.Label(t_cont, text="Это действие получает данные напрямую из игры.", bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8))).pack(anchor='w', pady=(2, 0))
                else:
                    tk.Label(t_cont, text="Это действие дополняет макрос командами движка.", bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8))).pack(anchor='w', pady=(1, 0))

            for i, step in enumerate(seq):
                card = tk.Frame(scroll, bg=_PANEL, highlightthickness=0)
                card.pack(fill='x', pady=4, padx=(0, 10))
                
                # State toggle
                var = tk.BooleanVar(value=not step.get('_disabled', False))
                cb = ctk.CTkCheckBox(card, text="", variable=var, width=28, height=28, corner_radius=6, 
                                   fg_color=_GREEN, border_color=_blend(_CYAN, 0.4), hover_color=_blend(_GREEN, 0.4),
                                   border_width=2, command=_render_after_delay)
                cb.pack(side='left', padx=(12, 5))
                
                # Visual Indicator
                color = _AMBER if 'wait' in step else (_CYAN if 'key' in step else _MAG)
                tk.Frame(card, bg=color, width=4).pack(side='left', fill='y', padx=(5, 12), pady=8)
                
                icon = "🕒" if 'wait' in step else ("⌨" if 'key' in step else "⌬")
                tk.Label(card, text=icon, bg=_PANEL, fg=color, font=(hud._F, hud._fs(16))).pack(side='left', padx=5)
                
                content = tk.Frame(card, bg=_PANEL)
                content.pack(side='left', fill='both', expand=True, pady=10)
                
                if 'wait' in step:
                    tk.Label(content, text="ПАУЗА (секунды)", bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='w')
                    val_e = ctk.CTkEntry(content, width=85, height=32, border_width=1, corner_radius=8, font=(hud._F, hud._fs(11)))
                    val_e.insert(0, str(step['wait']))
                    val_e.pack(side='left', pady=(3, 0))
                    step_widgets.append(('wait', var, val_e, None))
                else:
                    is_bind = 'binding' in step
                    lbl = "СИСТЕМНАЯ КОМАНДА" if is_bind else "НАЖАТИЕ КЛАВИШИ"
                    tk.Label(content, text=lbl, bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8), 'bold')).pack(anchor='w')
                    
                    if is_bind:
                        raw_b = step.get('binding', '')
                        ru_b = _RU_LABELS.get(raw_b, raw_b)
                        val_e = ctk.CTkComboBox(content, values=_BIND_LIST, width=220, height=32, corner_radius=8, border_width=1,
                                               dropdown_font=(hud._F, hud._fs(9)), dropdown_fg_color=_PANEL, dropdown_hover_color=_blend(_MAG, 0.2))
                        val_e.set(ru_b)
                        val_e.pack(side='left', pady=(3, 0))
                    else:
                        val_e = ctk.CTkEntry(content, width=110, height=32, border_width=1, corner_radius=8, font=(hud._F, hud._fs(11)))
                        val_e.insert(0, step.get('key', ''))
                        val_e.pack(side='left', pady=(3, 0))
                    
                    hld_e = None
                    if 'hold' in step or not is_bind:
                        tk.Label(content, text="УДЕРЖАНИЕ:", bg=_PANEL, fg=_DIM, font=(hud._F, hud._fs(8))).pack(side='left', padx=(12, 0), pady=(5, 0))
                        hld_e = ctk.CTkEntry(content, width=65, height=32, border_width=1, corner_radius=8, font=(hud._F, hud._fs(11)))
                        hld_e.insert(0, str(step.get('hold', 0.1)))
                        hld_e.pack(side='left', padx=5, pady=(3, 0))
                    step_widgets.append(('bind' if is_bind else 'key', var, val_e, hld_e))
                
                # Delete Step
                ctk.CTkButton(card, text="×", width=32, height=32, fg_color="transparent", text_color=_RED, 
                             hover_color=_blend(_RED, 0.15), font=(hud._F, hud._fs(16)),
                             command=lambda idx=i: _del(idx)).pack(side='right', padx=12)
            
            d.after(100, lambda: s_canvas.configure(scrollregion=s_canvas.bbox('all')))

        def _render_after_delay():
            d.after(10, lambda: None)

        def _del(idx):
            seq.pop(idx)
            _render()

        def _save():
            new_seq = []
            for i, (stype, var, val_e, hld_e) in enumerate(step_widgets):
                s = {}
                active = var.get()
                val = val_e.get()
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
            if 'key' in entry: entry.pop('key')
            if 'binding' in entry: entry.pop('binding')
            _save_changes(game_name)
            d.destroy()
            _load_game_tab(game_name)

        _render()
        
        # Bottom controls
        bottom_f = tk.Frame(d, bg=_BG)
        bottom_f.pack(fill='x', side='bottom', pady=(10, 30), padx=25)
        
        add_bar = tk.Frame(bottom_f, bg=_BG)
        add_bar.pack(anchor='center', pady=(0, 20))
        
        ctk.CTkButton(add_bar, text="+ ДОБАВИТЬ КОМАНДУ", width=145, height=40, font=(hud._F, hud._fs(9), 'bold'), 
                      fg_color=_blend(_MAG, 0.1), hover_color=_blend(_MAG, 0.2),
                      text_color=_MAG, border_width=1, border_color=_blend(_MAG, 0.3),
                      command=lambda: (seq.append({"binding": "engine"}), _render())).pack(side='left', padx=8)

        ctk.CTkButton(add_bar, text="+ ДОБАВИТЬ КЛАВИШУ", width=145, height=40, font=(hud._F, hud._fs(9), 'bold'), 
                      fg_color=_blend(_CYAN, 0.1), hover_color=_blend(_CYAN, 0.2),
                      text_color=_CYAN, border_width=1, border_color=_blend(_CYAN, 0.3),
                      command=lambda: (seq.append({"key": "..."}), _render())).pack(side='left', padx=15)
        
        ctk.CTkButton(add_bar, text="+ ДОБАВИТЬ ПАУЗУ", width=160, height=42, font=(hud._F, hud._fs(10), 'bold'), 
                      fg_color=_blend(_AMBER, 0.1), hover_color=_blend(_AMBER, 0.2),
                      text_color=_AMBER, border_width=1, border_color=_blend(_AMBER, 0.3),
                      command=lambda: (seq.append({"wait": 0.5}), _render())).pack(side='left', padx=15)
        
        ctk.CTkButton(bottom_f, text="СОХРАНИТЬ ИЗМЕНЕНИЯ МАКРОСА", fg_color=_CYAN, text_color=_BG, 
                      font=(hud._F, hud._fs(12), 'bold'), height=52, corner_radius=12,
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

    def _load_game_tab(game_name: str):
        nonlocal current_game
        current_game = game_name
        for g, b in tab_buttons.items():
            b.configure(fg_color=_CYAN if g == game_name else _BG, text_color=_BG if g == game_name else _CYAN)
        
        # Clear inner
        for w in inner.winfo_children(): w.destroy()
        current_vars.clear()
        key_buttons.clear()
        
        data = profiles_data[game_name]
        is_hogwarts = 'hogwarts' in game_name.lower()
        
        # --- HOGWARTS PATTERN GRID ---
        if is_hogwarts:
            tk.Label(inner, text='⧉ ПАТТЕРНЫ ЗАКЛИНАНИЙ (F1-F4)', bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(10), 'bold'), anchor='w').pack(fill='x', padx=16, pady=(10, 5))
            grid_f = tk.Frame(inner, bg=_BG)
            grid_f.pack(fill='x', padx=6, pady=(0, 15))
            
            spells = data.get('spells', [])
            all_spell_names = ['—'] + [s['name'] for s in spells if s.get('name') and not s.get('mouse')]
            
            _F_COLORS = [_CYAN, _MAG, _GREEN, _AMBER]
            
            for i, set_num in enumerate([1, 2, 3, 4]):
                row = tk.Frame(grid_f, bg=_PANEL if i % 2 == 0 else _BG)
                row.pack(fill='x', pady=0)
                color = _F_COLORS[i]
                tk.Frame(row, bg=color, width=4).pack(side='left', fill='y')
                tk.Label(row, text=f'F{set_num}', bg=row.cget('bg'), fg=color, font=(hud._F, hud._fs(12), 'bold'), width=4).pack(side='left', padx=5)
                
                for slot_num in [1, 2, 3, 4]:
                    # Find spell in this slot
                    current_spell_name = '—'
                    for s in spells:
                        if s.get('set') == set_num and s.get('key') == str(slot_num):
                            current_spell_name = s.get('name', '—')
                            break
                    
                    cb_f = tk.Frame(row, bg=row.cget('bg'))
                    cb_f.pack(side='left', expand=True, fill='x', padx=2, pady=4)
                    
                    filled = current_spell_name != '—'
                    cb = ctk.CTkComboBox(cb_f, values=all_spell_names, state='readonly', 
                                         fg_color=_BG if not filled else _blend(color, 0.08), 
                                         button_color=_BRD if not filled else _blend(color, 0.3),
                                         border_color=_BRD_I if not filled else _blend(color, 0.5),
                                         text_color=_DIM if not filled else color,
                                         font=(hud._F, hud._fs(9)), height=32,
                                         command=lambda v, sn=set_num, sl=slot_num: _on_spell_grid_change(game_name, sn, sl, v))
                    cb.set(current_spell_name)
                    cb.pack(fill='x')

            tk.Frame(inner, bg=_BRD, height=1).pack(fill='x', padx=20, pady=10)
            tk.Label(inner, text='◈ ОБЩИЕ КОМАНДЫ И МАКРОСЫ', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(10), 'bold'), anchor='w').pack(fill='x', padx=16, pady=(0, 5))

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
            
            # Show if it has any functional trigger (key, keys, sequence, telemetry, or binding)
            if (spell.get('key') or spell.get('keys') or spell.get('sequence') or spell.get('telemetry_action') or spell.get('binding')) and not spell.get('mouse'):
                s_id = f"spell_{spell.get('name')}"
                
                # Resolve key display: prefer explicit key, then keys, then binding resolved to key, then fallback to 'MACRO'
                if spell.get('key'):
                    key_disp = spell.get('key')
                elif spell.get('keys'):
                    key_disp = ','.join(spell.get('keys'))
                elif spell.get('binding'):
                    # Resolve technical binding name to the actual key assigned in this profile
                    key_disp = data.get('bindings', {}).get(spell.get('binding'), 'MACRO')
                else:
                    key_disp = 'MACRO'
                    
                items_to_show.append((s_id, spell.get('name'), key_disp, False, spell))

        for i, (bid, label_text, key_val, is_bind, entry) in enumerate(items_to_show):
            # 1. Filter out Pure Telemetry
            is_pure_telemetry = entry and entry.get('telemetry_action') and not entry.get('sequence') and not entry.get('key') and not entry.get('keys')
            if is_pure_telemetry: continue

            # 2. Add pady=6, increase row height to 48
            row_bg = _PANEL if i % 2 == 0 else _BG
            row = tk.Frame(inner, bg=row_bg, height=48)
            row.pack(fill='x', padx=10, pady=6)
            row.pack_propagate(False)
            
            icon_f = tk.Frame(row, bg=row_bg, width=36)
            icon_f.pack(side='left', padx=(12, 0))
            
            # Type-based Iconography (User requested all stars)
            icon_text, icon_color = '⌬', _CYAN
                
            tk.Label(icon_f, text=icon_text, bg=row_bg, fg=icon_color, font=(hud._F, hud._fs(12))).place(relx=0.5, rely=0.5, anchor='center')
            
            # Label
            lbl_text = label_text.upper() if is_bind else label_text
            tk.Label(row, text=lbl_text, bg=row_bg, fg=_TEXT if (key_val and key_val != 'MACRO') else _DIM, 
                     font=(hud._F, hud._fs(12)), anchor='w').pack(side='left', fill='x', expand=True, padx=(10, 4), pady=8)
            
            ctrl_f = tk.Frame(row, bg=row_bg, width=220, height=48)
            ctrl_f.pack(side='right', padx=(0, 12))
            ctrl_f.pack_propagate(False) 
            
            # Type-based Badge
            known_long_keys = {'space', 'enter', 'shift', 'ctrl', 'alt', 'backspace', 'delete', 'escape', 'tab', 'pageup', 'pagedown', 'home', 'end', 'insert', 'printscreen', 'pause', 'capslock', 'numlock', 'scrolllock'}
            
            if isinstance(key_val, str) and key_val != '—' and key_val != 'MACRO' and key_val != 'ИНФО':
                low_val = key_val.lower()
                if len(key_val) <= 4 or low_val in known_long_keys or low_val.startswith('f') or low_val.startswith('numpad'):
                    disp = key_val.upper()
                    current_vars[bid] = key_val
                else:
                    disp = 'MACRO'
                    current_vars[bid] = 'MACRO'
            elif is_pure_telemetry:
                disp = 'ИНФО'
                current_vars[bid] = 'ИНФО'
            else:
                disp = 'MACRO'
                current_vars[bid] = 'MACRO'
            
            # Key button (Grid 0)
            btn = ctk.CTkButton(ctrl_f, text=disp, 
                                fg_color=_BG if key_val else 'transparent', 
                                hover_color=_blend(_CYAN, 0.15),
                                text_color=_CYAN if key_val else _DIM, 
                                border_color=_blend(_CYAN, 0.3) if key_val else _BRD_I, 
                                border_width=1, corner_radius=8, 
                                font=(hud._F, hud._fs(10), 'bold'), 
                                height=30, width=80)
            key_buttons[bid] = btn
            btn.configure(command=lambda b=bid: _start_listen(b, game_name))
            btn.grid(row=0, column=0, padx=5, pady=4)
            
            def _test_cmd(e=entry, gn=game_name, b=bid, kv=key_val):
                try:
                    from actions.game_input import execute_by_name
                    name_to_run = e.get('name') if e else label_text
                    execute_by_name(name_to_run)
                except: pass

            # Test button (Grid 1)
            test_btn = ctk.CTkButton(ctrl_f, text='▶', 
                                   fg_color='transparent', hover_color=_blend(_GREEN, 0.15), 
                                   text_color=_blend(_CYAN, 0.6) if key_val or (entry and entry.get('sequence')) else _DIM, 
                                   width=30, height=30, corner_radius=15,
                                   font=(hud._F, hud._fs(12)),
                                   command=_test_cmd)
            test_btn.grid(row=0, column=1, padx=2)
            if not (key_val or (entry and entry.get('sequence'))): test_btn.configure(state='disabled')

            # Edit button (Grid 2) - now for ALL items
            edit_btn = ctk.CTkButton(ctrl_f, text='⚙', 
                                   fg_color='transparent', hover_color=_blend(_AMBER, 0.2), 
                                   text_color=_blend(_AMBER, 0.7), 
                                   width=30, height=30, corner_radius=15,
                                   font=(hud._F, hud._fs(14)),
                                   command=lambda e=entry, gn=game_name: _open_sequence_editor(gn, e if e else {'name': label_text, 'binding': bid}))
            edit_btn.grid(row=0, column=2, padx=2)

            def _clear(b=bid, gn=game_name):
                _stop_listen()
                current_vars[b] = ''
                key_buttons[b].configure(text='—', fg_color='transparent', text_color=_DIM, border_color=_BRD_I)
                _save_changes(gn)

            # Delete button (Grid 3)
            del_btn = ctk.CTkButton(ctrl_f, text='×', 
                                   fg_color='transparent', hover_color=_blend(_RED, 0.2), 
                                   text_color=_blend(_RED, 0.7) if key_val else _DIM, 
                                   width=30, height=30, corner_radius=15,
                                   font=(hud._F, hud._fs(16)),
                                   command=lambda b=bid: _clear(b))
            del_btn.grid(row=0, column=3, padx=5)
            if not key_val: del_btn.configure(state='disabled')
        
        # --- ADD CUSTOM COMMAND BUTTON ---
        add_f = tk.Frame(inner, bg=_BG)
        add_f.pack(fill='x', padx=8, pady=(15, 25))
        ctk.CTkButton(add_f, text='+ ДОБАВИТЬ МАКРОС / КОМАНДУ', 
                      font=(hud._F, hud._fs(10), 'bold'),
                      fg_color=_blend(_GREEN, 0.1), hover_color=_blend(_GREEN, 0.2),
                      text_color=_GREEN, border_color=_blend(_GREEN, 0.4), border_width=1,
                      height=38, corner_radius=10,
                      command=lambda: _add_custom_macro(game_name)).pack(fill='x', padx=60)

        canvas.yview_moveto(0)
        win.after(100, lambda: canvas.configure(scrollregion=canvas.bbox('all')))

    # Build tab buttons
    for gname in sorted_games:
        btn = ctk.CTkButton(tab_inner, text=gname.upper(), font=(hud._F, hud._fs(10), 'bold'), height=32, corner_radius=6, border_width=1, border_color=_CYAN, command=lambda g=gname: _load_game_tab(g))
        btn.pack(side='left', padx=4)
        tab_buttons[gname] = btn
    
    # Update tab scroll region
    tab_inner.update_idletasks()
    tab_canvas.configure(scrollregion=tab_canvas.bbox('all'))
    
    # Load initial tab
    _load_game_tab(current_game)
    
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='bottom')

    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x', side='bottom')
def open_spell_editor(hud, reopen: bool = False) -> None:
    if reopen and hud._spell_win and hud._spell_win.winfo_exists():
        hud._spell_win.destroy()
    import sys, json
    from pathlib import Path
    _main = sys.modules.get('__main__')
    profile_display = getattr(_main, '_game_profile', '') if _main else ''
    if not profile_display or 'hogwarts' not in profile_display.lower():
        import tkinter.messagebox as mb
        mb.showinfo('Профиль не выбран', 'Редактор паттернов предназначен для Hogwarts Legacy.\nАктивируй игровой режим с профилем Hogwarts Legacy.')
        return
    profiles_dir = Path('data') / 'game_profiles'
    profile_file = None
    for p in profiles_dir.glob('*.json'):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            if d.get('game', p.stem) == profile_display:
                profile_file = p
                break
        except Exception:
            pass
    if not profile_file:
        import tkinter.messagebox as mb
        mb.showinfo('Нет профиля', 'Файл профиля Hogwarts Legacy не найден.')
        return
    data = json.loads(profile_file.read_text(encoding='utf-8'))
    spells: list = data.get('spells')
    if not spells:
        import tkinter.messagebox as mb
        mb.showinfo('Нет паттернов', 'Этот профиль не содержит паттернов голосовых команд.')
        return
    assign: dict[int, dict[int, str]] = {1: {}, 2: {}, 3: {}, 4: {}}
    for s in spells:
        sn = s.get('set')
        sk = s.get('key')
        if sn in (1, 2, 3, 4) and sk in ('1', '2', '3', '4'):
            assign[sn][int(sk)] = s.get('name', '')
    _slottable = [s for s in spells if s.get('name') and (not s.get('mouse')) and (not s.get('key') or s.get('key') in ('1', '2', '3', '4'))]
    all_names = ['—'] + [s['name'] for s in _slottable]
    win = tk.Toplevel(hud.root)
    hud._spell_win = win
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    win.title(f'Редактор паттернов — {profile_display}')
    try:
        if hasattr(hud, '_ico_path'):
            win.iconbitmap(hud._ico_path)
    except Exception:
        pass
    win.configure(bg=_BG)
    win.resizable(False, False)
    win.update_idletasks()
    _W, _H = 740, 420
    gw, gh = int(_W * hud.zoom_factor), int(_H * hud.zoom_factor)
    _sx = (win.winfo_screenwidth() - gw) // 2
    _sy = (win.winfo_screenheight() - gh) // 2
    win.geometry(f'{gw}x{gh}+{_sx}+{_sy}')
    win.lift()
    win.focus_force()
    _F_COLORS = ['#00eaff', '#cc44ff', '#44ff88', '#ffaa00']
    _SLOT_NUMS = ['Р', '②', '③', '④']
    slot_cbs: dict[tuple[int, int], 'ctk.CTkComboBox'] = {}
    def _autosave():
        profile_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    def _on_select(set_num: int, slot_num: int, chosen: str):
        old = assign[set_num].get(slot_num)
        if old and old != chosen:
            for s in spells:
                if s.get('name') == old:
                    s.pop('set', None)
                    s.pop('key', None)
        if chosen != '—':
            for s in spells:
                if s.get('name') == chosen:
                    prev_sn = s.get('set')
                    prev_sk = s.get('key')
                    if prev_sn in (1, 2, 3, 4) and prev_sk in ('1', '2', '3', '4'):
                        prev_slot = int(prev_sk)
                        if (prev_sn, prev_slot) != (set_num, slot_num):
                            assign[prev_sn].pop(prev_slot, None)
                            other = slot_cbs.get((prev_sn, prev_slot))
                            if other:
                                other.set('—')
                    s['set'] = set_num
                    s['key'] = str(slot_num)
                    assign[set_num][slot_num] = chosen
        else:
            assign[set_num].pop(slot_num, None)
        _autosave()
    tk.Frame(win, bg=_AMBER, height=3).pack(fill='x')
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', pady=(14, 0))
    tk.Label(hdr, text='✦', bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(18))).pack(side='left', padx=(20, 6))
    tk.Label(hdr, text='РЕДАКТОР ПАТТЕРНОВ', bg=_BG, fg=_AMBER, font=(hud._F, hud._fs(15), 'bold')).pack(side='left')
    tk.Label(hdr, text=profile_display, bg=_BG, fg=_DIM, font=(hud._F, hud._fs(10))).pack(side='right', padx=20)
    col_hdr = tk.Frame(win, bg=_BG)
    col_hdr.pack(fill='x', padx=20, pady=(10, 2))
    tk.Frame(col_hdr, bg=_BG, width=70).pack(side='left')
    for idx in range(4):
        cell = tk.Frame(col_hdr, bg=_BG)
        cell.pack(side='left', expand=True, fill='x')
        tk.Label(cell, text=f'Слот  {_SLOT_NUMS[idx]}', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9)), anchor='center').pack(fill='x')
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=20, pady=(0, 6))
    cards_area = tk.Frame(win, bg=_BG)
    cards_area.pack(fill='both', expand=True, padx=16, pady=(0, 12))
    for i, set_num in enumerate([1, 2, 3, 4]):
        color = _F_COLORS[i]
        card = tk.Frame(cards_area, bg=_PANEL, highlightthickness=0)
        card.pack(fill='x', pady=4)
        tk.Frame(card, bg=color, width=4).pack(side='left', fill='y')
        badge = tk.Frame(card, bg=_PANEL, width=hud._px(68))
        badge.pack(side='left', fill='y')
        badge.pack_propagate(False)
        tk.Label(badge, text=f'F{set_num}', bg=_PANEL, fg=color, font=(hud._F, hud._fs(16), 'bold'), anchor='center').place(relx=0.5, rely=0.5, anchor='center')
        tk.Frame(card, bg=_BRD, width=1).pack(side='left', fill='y', pady=6)
        slots_row = tk.Frame(card, bg=_PANEL)
        slots_row.pack(side='left', fill='both', expand=True, padx=(8, 10), pady=8)
        for j, slot_num in enumerate([1, 2, 3, 4]):
            val = assign[set_num].get(slot_num, '—')
            filled = val != '—'
            cb = ctk.CTkComboBox(slots_row, values=all_names, state='readonly', fg_color=_blend(color, 0.07) if filled else _BG, button_color=_blend(color, 0.35) if filled else _BRD, button_hover_color=_blend(color, 0.55), border_color=_blend(color, 0.5) if filled else _BRD, border_width=1, corner_radius=6, text_color=color if filled else '#555566', dropdown_fg_color=_PANEL, dropdown_text_color=_TEXT, dropdown_hover_color=_BRD_I, font=(hud._F, hud._fs(11)), height=36, command=lambda v, sn=set_num, sl=slot_num: _on_select(sn, sl, v))
            cb.set(val)
            cb.pack(side='left', fill='x', expand=True, padx=(0, 6) if j < 3 else 0)
            slot_cbs[set_num, slot_num] = cb
    tk.Frame(win, bg=_AMBER, height=2).pack(fill='x', side='bottom')
