from __future__ import annotations
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar
from ..hud_widgets import _HudScrollbar
def open_keybind_editor(hud, reopen: bool = False) -> None:
    if not reopen and hud._keybind_win and hud._keybind_win.winfo_exists():
        hud._keybind_win.lift()
        return
    if reopen and hud._keybind_win and hud._keybind_win.winfo_exists():
        hud._keybind_win.destroy()
    import sys, json, os
    from pathlib import Path
    _main = sys.modules.get('__main__')
    profile_display = getattr(_main, '_game_profile', '') if _main else ''
    profiles_dir = Path('data') / 'game_profiles'
    profile_file = None
    if profile_display:
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
        mb.showinfo('Нет профиля', 'Сначала активируй игровой режим с профилем игры.')
        return
    data = json.loads(profile_file.read_text(encoding='utf-8'))
    bindings: dict = data.get('bindings')
    if bindings is None:
        import tkinter.messagebox as mb
        mb.showinfo('Нет биндингов', 'Этот профиль не поддерживает редактор клавиш.')
        return
    _KEYSYM_MAP = {'Return': 'enter', 'space': 'space', 'BackSpace': 'backspace', 'Delete': 'delete', 'Escape': 'escape', 'Tab': 'tab', 'Shift_L': 'shift', 'Shift_R': 'shift', 'Control_L': 'ctrl', 'Control_R': 'ctrl', 'Alt_L': 'alt', 'Alt_R': 'alt', 'Up': 'up', 'Down': 'down', 'Left': 'left', 'Right': 'right', 'Prior': 'pageup', 'Next': 'pagedown', 'Home': 'home', 'End': 'end', 'Insert': 'insert', 'KP_Add': 'add', 'KP_Subtract': 'subtract', 'KP_Divide': 'divide', 'KP_Multiply': 'multiply', 'KP_Enter': 'numpadenter', 'KP_0': 'numpad0', 'KP_1': 'numpad1', 'KP_2': 'numpad2', 'KP_3': 'numpad3', 'KP_4': 'numpad4', 'KP_5': 'numpad5', 'KP_6': 'numpad6', 'KP_7': 'numpad7', 'KP_8': 'numpad8', 'KP_9': 'numpad9', 'KP_Decimal': 'decimal', 'bracketleft': '[', 'bracketright': ']', 'semicolon': ';', 'apostrophe': "'", 'grave': '`', 'minus': '-', 'equal': '=', 'backslash': '\\', 'comma': ',', 'period': '.', 'slash': '/', 'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4', 'F5': 'f5', 'F6': 'f6', 'F7': 'f7', 'F8': 'f8', 'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12', 'Print': 'printscreen', 'Pause': 'pause', 'Caps_Lock': 'capslock', 'Num_Lock': 'numlock', 'Scroll_Lock': 'scrolllock'}
    def _norm_key(sym: str) -> str:
        if sym in _KEYSYM_MAP:
            return _KEYSYM_MAP[sym]
        return sym.lower() if len(sym) == 1 else sym.lower()
    _total = len(bindings)
    _assigned = sum((1 for v in bindings.values() if v))
    win = tk.Toplevel(hud.root)
    hud._keybind_win = win
    _set_dark_title_bar(win)
    win.after(50, lambda: _set_dark_title_bar(win))
    win.title(f'Редактор клавиш — {profile_display}')
    try:
        if hasattr(hud, '_ico_path'):
            win.iconbitmap(hud._ico_path)
    except Exception:
        pass
    win.configure(bg=_BG)
    win.resizable(False, True)
    win.update_idletasks()
    _W, _H = 640, 700
    gw, gh = int(_W * hud.zoom_factor), int(_H * hud.zoom_factor)
    _sx = (win.winfo_screenwidth() - gw) // 2
    _sy = (win.winfo_screenheight() - gh) // 2
    win.geometry(f'{gw}x{gh}+{_sx}+{_sy}')
    win.lift()
    win.focus_force()
    tk.Frame(win, bg=_CYAN, height=3).pack(fill='x')
    hdr = tk.Frame(win, bg=_BG)
    hdr.pack(fill='x', pady=(14, 0))
    tk.Label(hdr, text='⌨', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(20))).pack(side='left', padx=(20, 8))
    title_col = tk.Frame(hdr, bg=_BG)
    title_col.pack(side='left')
    tk.Label(title_col, text='РЕДАКТОР КЛАВИШ', bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(15), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(title_col, text=profile_display, bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9)), anchor='w').pack(anchor='w')
    _count_lbl = tk.Label(hdr, bg=_BG, fg=_CYAN, font=(hud._F, hud._fs(11), 'bold'), text=f'{_assigned} / {_total}')
    _count_lbl.pack(side='right', padx=20)
    tk.Label(hdr, text='назначено', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9))).pack(side='right')
    tk.Frame(win, bg=_BRD, height=1).pack(fill='x', padx=16, pady=(10, 0))
    tk.Label(win, text='  Нажмите кнопку → введите клавишу   /   ✕ — очистить', bg=_BG, fg=_DIM, font=(hud._F, hud._fs(9))).pack(anchor='w', padx=20, pady=(5, 8))
    scroll_area = tk.Frame(win, bg=_BG)
    scroll_area.pack(fill='both', expand=True)
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
    def _update_scroll(*_):
        canvas.configure(scrollregion=canvas.bbox('all'))
    inner.bind('<Configure>', _update_scroll)
    def _on_mousewheel(e):
        if canvas.winfo_exists() and _vsb.winfo_ismapped():
            canvas.yview_scroll(-1 * (e.delta // 120), 'units')
    win.bind('<MouseWheel>', _on_mousewheel)
    current: dict[str, str] = dict(bindings)
    key_buttons: dict[str, tk.Button] = {}
    _listening: list[str | None] = [None]
    def _stop_listen():
        bid = _listening[0]
        if bid:
            btn = key_buttons.get(bid)
            if btn:
                v = current.get(bid, '')
                btn.configure(text=v or '—', fg_color=_blend(_CYAN, 0.1) if v else _PANEL, hover_color=_blend(_CYAN, 0.25) if v else _BRD_I, text_color=_CYAN if v else '#555566', border_color=_blend(_CYAN, 0.4) if v else _BRD)
        _listening[0] = None
        win.unbind('<Key>')
    def _on_key(event, bid: str):
        key = _norm_key(event.keysym)
        if key in ('', '??'):
            return
        for other_bid, other_key in list(current.items()):
            if other_bid != bid and other_key == key:
                current[other_bid] = ''
                btn = key_buttons.get(other_bid)
                if btn:
                    btn.configure(text='—', fg_color=_BG, hover_color=_BRD_I, text_color='#555566', border_color=_BRD)
        current[bid] = key
        _stop_listen()
        _autosave()
    def _start_listen(bid: str):
        _stop_listen()
        _listening[0] = bid
        btn = key_buttons[bid]
        btn.configure(text='Нажмите...', fg_color=_blend(_AMBER, 0.15), hover_color=_blend(_AMBER, 0.3), text_color=_AMBER, border_color=_blend(_AMBER, 0.5))
        win.bind('<Key>', lambda e: _on_key(e, bid))
    _RU_LABELS = {'engine': 'Двигатель', 'handbrake': 'Стояночный тормоз', 'cruise': 'Круиз-контроль', 'differential': 'Дифференциал', 'axle_lift': 'Подъём оси', 'trailer': 'Прицеп', 'lights_main': 'Фары ближний', 'lights_high': 'Фары дальний', 'strobe': 'Проблесковые огни', 'turn_left': 'Поворотник левый', 'turn_right': 'Поворотник правый', 'hazard': 'Аварийка', 'horn': 'Клаксон', 'air_horn': 'Пневмосигнал', 'wipers': 'Дворники', 'info': 'Инфо', 'navigator': 'Навигатор', 'action': 'Действие', 'gear_up': 'Повышенная передача', 'gear_down': 'Пониженная передача'}
    _CAT_ICON = {'engine': '◈', 'handbrake': '◈', 'cruise': '◈', 'differential': '◈', 'axle_lift': '◈', 'trailer': '◈', 'gear_up': '◈', 'gear_down': '◈', 'lights_main': '◉', 'lights_high': '◉', 'strobe': '◉', 'turn_left': '◀', 'turn_right': '▶', 'hazard': '◆', 'horn': '▲', 'air_horn': '▲', 'wipers': '≋', 'navigator': '◎', 'info': '◇', 'action': '▸'}
    for i, (bid, key_val) in enumerate(current.items()):
        row_bg = _PANEL if i % 2 == 0 else _BG
        row = tk.Frame(inner, bg=row_bg)
        row.pack(fill='x', pady=1, padx=6)
        tk.Frame(row, bg=_CYAN if key_val else _BRD, width=4).pack(side='left', fill='y')
        disp = key_val.upper() if key_val and len(key_val) <= 3 else key_val or '—'
        btn = ctk.CTkButton(row, text=disp, fg_color=_blend(_CYAN, 0.1) if key_val else _BG, hover_color=_blend(_CYAN, 0.24) if key_val else _BRD_I, text_color=_CYAN if key_val else '#555566', border_color=_blend(_CYAN, 0.5) if key_val else _BRD, border_width=1, corner_radius=8, font=(hud._F, hud._fs(14), 'bold'), height=42, width=140)
        key_buttons[bid] = btn
        def _clear(b=bid):
            _stop_listen()
            current[b] = ''
            key_buttons[b].configure(text='—', fg_color=_BG, hover_color=_BRD_I, text_color='#555566', border_color=_BRD)
            _autosave()
        ctk.CTkButton(row, text='✕', fg_color=row_bg, hover_color=_blend(_RED, 0.22), text_color=_blend(_RED, 0.55), border_color=row_bg, border_width=0, corner_radius=8, font=(hud._F, hud._fs(12)), width=28, height=34, command=lambda b=bid: _clear(b)).pack(side='right', padx=(0, 10))
        btn.configure(command=lambda b=bid: _start_listen(b))
        btn.pack(side='right', padx=(0, 6))
        icon = _CAT_ICON.get(bid, '·')
        tk.Label(row, text=icon, bg=row_bg, fg=_DIM, font=(hud._F, hud._fs(11)), width=2).pack(side='left', padx=(8, 0), pady=10)
        label = _RU_LABELS.get(bid, bid.replace('_', ' ').title())
        tk.Label(row, text=label, bg=row_bg, fg=_TEXT, font=(hud._F, hud._fs(11)), anchor='w').pack(side='left', fill='x', expand=True, padx=(6, 8), pady=10)
    def _autosave():
        data['bindings'] = current
        profile_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        _count_lbl.configure(text=f'{sum((1 for v in current.values() if v))} / {_total}')
        _m = sys.modules.get('__main__')
        if _m and getattr(_m, '_game_mode', False):
            try:
                from actions.game_input import load_profile
                load_profile(profile_file.stem)
            except Exception:
                pass
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
