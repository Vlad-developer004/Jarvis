from __future__ import annotations
import json, os, threading, time, sys, subprocess
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar
from ..hud_widgets import _HudScrollbar
def open_settings(hud, reopen: bool = False) -> None:
    from pathlib import Path
    import importlib
    _hud_mod = importlib.import_module('ui.hud')
    _save_hud_settings = _hud_mod._save_hud_settings
    if not reopen and hasattr(hud, '_settings_win') and hud._settings_win and hud._settings_win.winfo_exists():
        hud._settings_win.lift()
        return
    if reopen and hasattr(hud, '_settings_win') and hud._settings_win and hud._settings_win.winfo_exists():
        hud._settings_win.destroy()
    win = tk.Toplevel(hud.root)
    hud._settings_win = win
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    hud._track_subwin('settings', win, lambda: open_settings(hud, reopen=True))
    win.title('НАСТРОЙКИ — J.A.R.V.I.S.')
    try:
        if hasattr(hud, '_ico_path'):
            win.iconbitmap(hud._ico_path)
    except Exception:
        pass
    win.configure(bg=_BG)
    win.update_idletasks()
    _sw_scr = win.winfo_screenwidth()
    _sh_scr = win.winfo_screenheight()
    _W = int(min(hud._px(700), _sw_scr * 0.92))
    _H = int(min(hud._px(860), _sh_scr * 0.92))
    _sx = max(0, (_sw_scr - _W) // 2)
    _sy = max(0, (_sh_scr - _H) // 2)
    win.geometry(f'{_W}x{_H}+{_sx}+{_sy}')
    win.minsize(hud._px(520), hud._px(400))
    win.resizable(True, True)
    win.lift()
    win.focus_force()
    _sf = lambda n: hud._fs(n + 6)
    _accent = tk.Frame(win, bg=_CYAN, height=4)
    _accent.pack(fill='x')
    _hdr_bg = '#060810'
    hdr_outer = tk.Frame(win, bg=_hdr_bg)
    hdr_outer.pack(fill='x')
    hdr = tk.Frame(hdr_outer, bg=_hdr_bg)
    hdr.pack(fill='x', padx=28, pady=(18, 14))
    badge = tk.Frame(hdr, bg=_blend(_CYAN, 0.12), highlightbackground=_blend(_CYAN, 0.35), highlightthickness=1)
    badge.pack(side='left', padx=(0, 14))
    tk.Label(badge, text='⚙', bg=_blend(_CYAN, 0.12), fg=_CYAN, font=(hud._F, _sf(22))).pack(padx=10, pady=6)
    hdr_text = tk.Frame(hdr, bg=_hdr_bg)
    hdr_text.pack(side='left', fill='x', expand=True)
    tk.Label(hdr_text, text='НАСТРОЙКИ СИСТЕМЫ', bg=_hdr_bg, fg=_CYAN, font=(hud._F, _sf(16), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(hdr_text, text='Конфигурация интерфейса, голоса и микрофона', bg=_hdr_bg, fg=_DIM, font=(hud._F, _sf(10)), anchor='w').pack(anchor='w')
    tk.Frame(hdr, bg=_hdr_bg).pack(side='right', padx=10)
    tk.Frame(win, bg=_BRD_I, height=1).pack(fill='x')
    scroll_canvas = tk.Canvas(win, bg=_BG, highlightthickness=0)
    _vsb = _HudScrollbar(win, scroll_canvas, color=_CYAN)
    scroll_canvas.configure(yscrollcommand=_vsb.set)
    scroll_canvas.pack(side='left', fill='both', expand=True, pady=(0, 0))
    inner = tk.Frame(scroll_canvas, bg=_BG)
    _cw = scroll_canvas.create_window((0, 0), window=inner, anchor='nw')
    def _upd_scroll(*_):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox('all'))
    def _on_cfg(e):
        scroll_canvas.itemconfig(_cw, width=e.width)
        _upd_scroll()
    inner.bind('<Configure>', _upd_scroll)
    scroll_canvas.bind('<Configure>', _on_cfg)
    win.bind('<MouseWheel>', lambda e: scroll_canvas.yview_scroll(-1 * (e.delta // 120), 'units'))
    def _bind_mousewheel(w):
        try:
            cl = w.winfo_class()
            if cl in ('Listbox', 'Text'):
                return
        except Exception:
            pass
        w.bind('<MouseWheel>', lambda e: scroll_canvas.yview_scroll(-1 * (e.delta // 120), 'units'), add='+')
        for child in w.winfo_children():
            _bind_mousewheel(child)
    win.after(600, lambda: _bind_mousewheel(inner))
    def _add_context_menu(entry):
        menu = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=_CYAN, activeforeground=_BG, font=(hud._F, _sf(9)))
        def _paste():
            try:
                import pyperclip
                txt = pyperclip.paste()
                if txt:
                    if entry.selection_present():
                        entry.delete('sel.first', 'sel.last')
                    entry.insert(tk.INSERT, txt)
            except Exception: pass
        def _copy():
            try:
                if entry.selection_present():
                    win.clipboard_clear()
                    win.clipboard_append(entry.selection_get())
            except Exception: pass
        def _select_all():
            entry.select_range(0, 'end')
            entry.icursor('end')
        menu.add_command(label='Вставить (Ctrl+V)', command=_paste)
        menu.add_command(label='Копировать (Ctrl+C)', command=_copy)
        menu.add_separator()
        menu.add_command(label='Выделить всё (Ctrl+A)', command=_select_all)
        def _show_menu(e):
            menu.tk_popup(e.x_root, e.y_root)
        entry.bind('<Button-3>', _show_menu)
        entry.bind('<Control-v>', lambda e: (_paste(), 'break'))
        entry.bind('<Control-V>', lambda e: (_paste(), 'break'))
        entry.bind('<Control-a>', lambda e: (_select_all(), 'break'))
        entry.bind('<Control-A>', lambda e: (_select_all(), 'break'))
    def _card(icon: str, title: str, accent: str):
        outer = tk.Frame(inner, bg=_PANEL, highlightbackground=_blend(accent, 0.2), highlightthickness=1)
        outer.pack(fill='x', padx=20, pady=(14, 0))
        tk.Frame(outer, bg=accent, width=3).pack(side='left', fill='y')
        body = tk.Frame(outer, bg=_PANEL)
        body.pack(side='left', fill='both', expand=True, padx=(16, 18), pady=(14, 14))
        head = tk.Frame(body, bg=_PANEL)
        head.pack(fill='x', pady=(0, 6))
        tk.Label(head, text=icon, bg=_PANEL, fg=accent, font=(hud._F, _sf(16))).pack(side='left', padx=(0, 10))
        tk.Label(head, text=title, bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='w').pack(side='left')
        return body
    def _hint(parent, text: str):
        lbl = tk.Label(
            parent,
            text=text,
            bg=_PANEL,
            fg=_blend(_TEXT, 0.72),
            font=(hud._F, _sf(10)),
            anchor='w',
            justify='left',
        )
        lbl.pack(fill='x', pady=(0, 8))
        def _upd_hint(e, l=lbl):
            new_wl = max(hud._px(100), e.width - hud._px(8))
            l.configure(wraplength=new_wl)
        parent.bind('<Configure>', _upd_hint, add='+')
        def _try_init_wrap(tries_left: int = 10):
            try:
                w = int(parent.winfo_width() or 0)
            except Exception:
                w = 0
            if w > 1:
                _upd_hint(type('E', (), {'width': w})())
                return
            if tries_left > 0:
                parent.after(30, lambda: _try_init_wrap(tries_left - 1))
        parent.after(10, _try_init_wrap)
    def _label_row(parent, label: str, accent: str):
        row = tk.Frame(parent, bg=_PANEL)
        row.pack(fill='x', pady=(6, 0))
        tk.Label(row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11), 'bold'), anchor='w').pack(side='left')
        val_lbl = tk.Label(row, text='', bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'))
        val_lbl.pack(side='right')
        return val_lbl
    def _slider(parent, from_, to, steps, accent, init_val, callback):
        s = ctk.CTkSlider(parent, from_=from_, to=to, number_of_steps=steps, progress_color=accent, button_color=accent, button_hover_color=_blend(accent, 0.7), fg_color=_BRD_I, height=hud._px(16))
        s.set(init_val)
        s.pack(fill='x', pady=(10, 4))
        s.configure(command=callback)
        return s
    def _std_action_btn(parent, *, text: str, command, accent: str, **grid_kw):
        b = ctk.CTkButton(
            parent,
            text=text,
            command=command,
            height=hud._px(44),
            font=(hud._F, _sf(10), 'bold'),
            fg_color=_blend(accent, 0.08),
            hover_color=_blend(accent, 0.18),
            text_color=accent,
            border_color=_blend(accent, 0.32),
            border_width=1,
            corner_radius=10,
        )
        b.grid(**grid_kw)
        return b
    c1 = _card('◈', 'ОТОБРАЖЕНИЕ', _CYAN)
    _zoom_val_lbl = _label_row(c1, 'Масштаб интерфейса', _CYAN)
    _zoom_val_lbl.configure(text=f'{hud.zoom_factor:.1f}×')
    _hint(c1, 'Ctrl + +/−  быстро  •  Ctrl+0 сброс  •  ✦ Авто определит масштаб по экрану')
    _max_var = tk.BooleanVar(value=hud._settings.get('start_maximized', True))
    def _on_max():
        hud._settings['start_maximized'] = _max_var.get()
        _save_hud_settings(hud._settings)
    _max_row = tk.Frame(
        c1,
        bg=_blend(_CYAN, 0.05),
        highlightbackground=_blend(_CYAN, 0.2),
        highlightthickness=1,
    )
    _max_row.pack(fill='x', pady=(6, 10))
    ctk.CTkSwitch(
        _max_row,
        text='Запуск во весь экран  ·  окно HUD на весь монитор',
        variable=_max_var,
        command=_on_max,
        font=(hud._F, _sf(11), 'bold'),
        progress_color=_CYAN,
        fg_color=_BRD_I,
        button_color=_WHITE,
        switch_width=hud._px(46),
        switch_height=hud._px(24),
    ).pack(side='left', padx=(12, 12), pady=(12, 12))
    def _apply_zoom(z: float) -> None:
        hud.zoom_factor = z
        hud._settings['zoom_factor'] = z
        _save_hud_settings(hud._settings)
        _zoom_val_lbl.configure(text=f'{z:.1f}×')
        zoom_slider.set(z)
        hud._apply_zoom_rebuild()
    def _on_zoom_slide(v):
        z = round(float(v), 1)
        _zoom_val_lbl.configure(text=f'{z:.1f}×')
        if abs(z - hud.zoom_factor) >= 0.09:
            _apply_zoom(z)
    zoom_slider = _slider(c1, 0.6, 2.5, 19, _CYAN, hud.zoom_factor, _on_zoom_slide)
    btns_row = tk.Frame(c1, bg=_PANEL)
    btns_row.pack(fill='x', pady=(8, 8))
    z_btns = tk.Frame(btns_row, bg=_PANEL)
    z_btns.pack(anchor='center', fill='x', padx=0)
    for zi in range(4):
        z_btns.columnconfigure(zi, weight=1, uniform='zoom_btns')
    for col, (lbl, delta) in enumerate((('−', -0.1), ('+', +0.1), ('↺ Сброс', 1.0), ('✦ Авто', 0.0))):
        def _cb(d=delta):
            if d == 0.0:
                z = hud._auto_detect_zoom()
                hud._settings['zoom_factor'] = 0.0
                _save_hud_settings(hud._settings)
            else:
                z = round(hud.zoom_factor + d, 1) if d != 1.0 else 1.0
                z = max(0.6, min(2.5, z))
            _apply_zoom(z)
        padx_z = ((0, 4), (4, 4), (4, 4), (4, 0))[col]
        _std_action_btn(
            z_btns,
            text=lbl,
            command=_cb,
            accent=_CYAN,
            row=0,
            column=col,
            sticky='ew',
            padx=padx_z,
        )
    c2 = _card('◉', 'МОДУЛИ ИНТЕРФЕЙСА', _MAG)
    _hint(c2, 'Скрытые модули убираются из панели автоматически.')
    _vis_icons = {'sunrise': '☀', 'sysinfo': '◈', 'storage': '📊', 'network': '⟳', 'weather': '≋', 'clock': '🕐', 'camera': '📷', 'gamemode': '✦', 'meetings_btn': '🔗', 'videos_btn': '▶'}
    _vis_map = {'sunrise': 'Восход / Закат  (верхняя полоса)', 'sysinfo': 'Системные профили (Батарея / Мик)', 'storage': 'Аналитика хранилища (RAM / Диск)', 'network': 'Сетевая статистика', 'weather': 'Погода — Атмосфера', 'clock': 'Часы, дата и аптайм', 'camera': 'Видеосенсор (камера)', 'gamemode': 'Игровой режим', 'meetings_btn': 'Быстрые ссылки (кнопка в HUD)', 'videos_btn': 'Сохранённые видео (кнопка в HUD)'}
    _vis_vars: dict[str, tk.BooleanVar] = {}
    for key, label in _vis_map.items():
        var = tk.BooleanVar(value=hud._widget_vis.get(key, True))
        _vis_vars[key] = var
        sw_row = tk.Frame(c2, bg=_PANEL)
        sw_row.pack(fill='x', pady=4)
        icon_f = tk.Frame(sw_row, bg=_PANEL, width=hud._px(36), height=hud._px(36))
        icon_f.pack_propagate(False)
        icon_f.pack(side='left')
        tk.Label(icon_f, text=_vis_icons[key], bg=_PANEL, fg=_MAG, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
        sw = ctk.CTkSwitch(sw_row, text='', variable=var, onvalue=True, offvalue=False, fg_color=_BRD_I, progress_color=_MAG, button_color=_WHITE, switch_width=hud._px(36), switch_height=hud._px(18), width=0)
        sw.pack(side='left', padx=(4, 5))
        lbl = tk.Label(sw_row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(12), 'bold'), anchor='w', justify='left')
        lbl.pack(side='left', fill='x', expand=True, padx=(2, 0))
        def _upd_sw_wrap(e, l=lbl):
            avail = e.width - hud._px(80)
            l.configure(wraplength=max(60, avail))
        sw_row.bind('<Configure>', _upd_sw_wrap, add='+')
        def _on_vis_change(k=key, v=var):
            hud._widget_vis[k] = v.get()
            hud._settings['widget_vis'] = hud._widget_vis
            _save_hud_settings(hud._settings)
            if k in ('camera', 'sysinfo', 'gamemode', 'meetings_btn', 'videos_btn'):
                hud._rebuild_left()
            else:
                hud._rebuild_right()
            if k == 'sunrise':
                hud._apply_widget_visibility()
            if k == 'weather' and v.get():
                hud._weather_tick()
        sw.configure(command=lambda k=key, v=var: _on_vis_change(k, v))
        lbl.bind('<Button-1>', lambda e, k=key, v=var: (v.set(not v.get()), _on_vis_change(k, v)))
    c_modules = _card('🧩', 'МОДУЛИ И ПРОФИЛИ', _GREEN)
    _hint(c_modules, 'Выберите, какие функции и зависимости нужны: это снижает нагрузку и размер установки.')
    _feature_profile_var = tk.StringVar(value=str(hud._settings.get('feature_profile', 'minimal')))
    _feature_status_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)))
    _feature_desc_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), justify='left', anchor='w')
    _feature_desc_lbl.pack(fill='x', pady=(4, 0))
    _feature_presets = {
        'full': {
            'games': True, 'qa': True, 'cinema': True, 'system_monitoring': True,
            'battery_monitor': True, 'lag_hunter': True, 'morning_briefing': True, 'updater': True,
            'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False,
        },
        'assistant': {
            'games': False, 'qa': False, 'cinema': False, 'system_monitoring': True,
            'battery_monitor': True, 'lag_hunter': False, 'morning_briefing': False, 'updater': True,
            'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False,
        },
        'minimal': {
            'games': False, 'qa': False, 'cinema': False, 'system_monitoring': False,
            'battery_monitor': False, 'lag_hunter': False, 'morning_briefing': False, 'updater': False,
            'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False,
        },
    }
    _feature_desc_map = {
        'full': 'FULL: все модули активны (ИИ, игры, мониторинг, обновления).',
        'assistant': 'ASSISTANT: базовый ассистент, без игровых/кино/ИИ модулей.',
        'minimal': 'MINIMAL: минимальная нагрузка при запуске (режим по умолчанию).',
    }
    _feature_modules_overrides = hud._settings.get('feature_modules', {})
    if not isinstance(_feature_modules_overrides, dict):
        _feature_modules_overrides = {}
    hud._settings['feature_modules'] = _feature_modules_overrides
    _module_switch_vars: dict[str, tk.BooleanVar] = {}
    def _effective_module_value(module_key: str) -> bool:
        profile = _feature_profile_var.get()
        base = _feature_presets.get(profile, _feature_presets['minimal']).get(module_key, False)
        override = _feature_modules_overrides.get(module_key)
        if isinstance(override, bool):
            return override
        return base
    def _sync_dep_profile_to_feature_profile() -> None:
        fp = _feature_profile_var.get()
        _dep_var.set('full' if fp == 'full' else 'base')
        _dep_selected()
    def _refresh_module_switches_from_profile():
        for module_key, var in _module_switch_vars.items():
            var.set(_effective_module_value(module_key))
    def _apply_feature_profile():
        profile = _feature_profile_var.get()
        hud._settings['feature_profile'] = profile
        _save_hud_settings(hud._settings)
        _feature_desc_lbl.configure(text=_feature_desc_map.get(profile, _feature_desc_map['minimal']))
        _feature_status_lbl.configure(text='Профиль сохранен. Для фоновых служб нужен перезапуск JARVIS.', fg=_AMBER)
        _refresh_module_switches_from_profile()
        _refresh_load_summary()
        _sync_dep_profile_to_feature_profile()
        _schedule_auto_dep_sync('profile-change')
        try:
            from core.system import refresh_module_flags
            refresh_module_flags()
        except Exception:
            pass
    _feature_options = [
        ('full', 'FULL', 'Все функции'),
        ('assistant', 'ASSISTANT', 'Без ИИ/игр/кино'),
        ('minimal', 'MINIMAL', 'Максимально легкий'),
    ]
    for val, title, sub in _feature_options:
        row = tk.Frame(c_modules, bg=_PANEL)
        row.pack(fill='x', pady=(4, 0), padx=(8, 0))
        rb = ctk.CTkRadioButton(
            row,
            text='',
            variable=_feature_profile_var,
            value=val,
            fg_color=_GREEN,
            radiobutton_width=hud._px(18),
            radiobutton_height=hud._px(18),
            command=_apply_feature_profile,
            width=0,
        )
        rb.pack(side='left', padx=(0, 6))
        lbl = tk.Label(row, text=f'{title} — {sub}', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w')
        lbl.pack(side='left', fill='x', expand=True)
        lbl.bind('<Button-1>', lambda e, v=val: (_feature_profile_var.set(v), _apply_feature_profile()))
    _feature_desc_lbl.configure(text=_feature_desc_map.get(_feature_profile_var.get(), _feature_desc_map['minimal']))
    _feature_status_lbl.pack(fill='x', pady=(6, 0))
    tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
    tk.Label(c_modules, text='Тонкая настройка модулей (поверх профиля)', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(8, 0))
    _hint(c_modules, 'Каждый модуль описан: что делает, как часто работает и как влияет на ресурсы.')
    _module_meta = {
        'qa': {
            'title': 'ИИ / QA',
            'icon': '◉',
            'what': 'Обрабатывает сложные вопросы через LLM и уточнения.',
            'freq': 'По запросу пользователя.',
            'impact': 'CPU: средний  •  RAM: средний',
            'weight': 3,
        },
        'games': {
            'title': 'Игровой модуль',
            'icon': '✦',
            'what': 'Игровой режим, профили игр, обработка игровых команд.',
            'freq': 'Фоново + активно в режиме игры.',
            'impact': 'CPU: средний/высокий  •  RAM: средний',
            'weight': 4,
        },
        'cinema': {
            'title': 'Кино модуль',
            'icon': '▶',
            'what': 'Сценарии фильмов/сериалов и медиа-автоматизация.',
            'freq': 'По команде, без постоянного фонового цикла.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'system_monitoring': {
            'title': 'Системный мониторинг',
            'icon': '▦',
            'what': 'Сбор и обновление системных метрик в HUD.',
            'freq': 'Периодически (каждые 2-12 секунд).',
            'impact': 'CPU: средний  •  RAM: низкий',
            'weight': 3,
        },
        'battery_monitor': {
            'title': 'Монитор батареи',
            'icon': '▣',
            'what': 'Отслеживает питание и состояние аккумулятора.',
            'freq': 'Редкий фоновый опрос.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'lag_hunter': {
            'title': 'Lag Hunter',
            'icon': '⟳',
            'what': 'Анализирует лаги и пиковые задержки системы.',
            'freq': 'Фоново, периодические проверки.',
            'impact': 'CPU: средний  •  RAM: низкий/средний',
            'weight': 2,
        },
        'morning_briefing': {
            'title': 'Утренний брифинг',
            'icon': '☀',
            'what': 'Утренний сценарий сводки после старта.',
            'freq': 'Единоразово при старте по условиям.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'updater': {
            'title': 'Автообновления',
            'icon': '⬡',
            'what': 'Проверяет доступность обновлений и применяет их.',
            'freq': 'Фоново, редкие проверки.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'network_profiles': {
            'title': 'Сеть: профили и подсказки',
            'icon': '◎',
            'what': 'Профили «дом / офис / публичная сеть», подсказки по VPN (без автоматического netsh).',
            'freq': 'По голосовой команде.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'system_health': {
            'title': 'Система: диски',
            'icon': '▤',
            'what': 'Краткий отчёт по свободному месту на дисках (psutil).',
            'freq': 'По команде.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'calendar_ics': {
            'title': 'Календарь ICS',
            'icon': '📅',
            'what': 'Озвучивает ближайшие события из вашего календаря.',
            'freq': 'По команде; при чтении URL — сетевой запрос.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
        'inbox_digest': {
            'title': 'Почта',
            'icon': '✉',
            'what': 'Проверка непрочитанных писем голосом, просмотр и отправка через окно «Почта».',
            'freq': 'По команде и при открытии окна почты.',
            'impact': 'CPU: низкий  •  RAM: низкий',
            'weight': 1,
        },
    }
    _module_order = [
        'qa', 'games', 'cinema', 'system_monitoring', 'battery_monitor', 'lag_hunter',
        'morning_briefing', 'updater', 'network_profiles', 'system_health', 'calendar_ics', 'inbox_digest',
    ]
    _module_load_lbl = tk.Label(
        c_modules,
        text='',
        bg=_PANEL,
        fg=_CYAN,
        font=(hud._F, _sf(9), 'bold'),
        anchor='w',
        justify='left',
    )
    _module_load_lbl.pack(fill='x', pady=(4, 2))
    def _wrap_module_load(e=None):
        try:
            w = c_modules.winfo_width()
            if w and w > 1:
                _module_load_lbl.configure(wraplength=max(hud._px(120), w - hud._px(16)))
        except Exception:
            pass
    c_modules.bind('<Configure>', lambda e: _wrap_module_load(e), add='+')
    c_modules.after(30, _wrap_module_load)
    def _on_module_toggle(module_key: str, module_var: tk.BooleanVar):
        _feature_modules_overrides[module_key] = bool(module_var.get())
        hud._settings['feature_modules'] = _feature_modules_overrides
        _save_hud_settings(hud._settings)
        _feature_status_lbl.configure(text='Индивидуальный модуль сохранен. Для фоновых служб нужен перезапуск JARVIS.', fg=_AMBER)
        _refresh_load_summary()
        _schedule_auto_dep_sync('module-toggle')
        try:
            from core.system import refresh_module_flags
            refresh_module_flags()
        except Exception:
            pass
    def _refresh_load_summary():
        score = 0
        enabled_count = 0
        for key in _module_order:
            if _module_switch_vars.get(key) and _module_switch_vars[key].get():
                enabled_count += 1
                score += int(_module_meta.get(key, {}).get('weight', 1))
        if score <= 4:
            level, col = ('НИЗКАЯ', _GREEN)
        elif score <= 9:
            level, col = ('СРЕДНЯЯ', _AMBER)
        else:
            level, col = ('ВЫСОКАЯ', _RED)
        _module_load_lbl.configure(
            text=f'JARVIS LOAD PROFILE: {level}  •  Активно модулей: {enabled_count}/{len(_module_order)}  •  Балл: {score}',
            fg=col,
        )
    for module_key in _module_order:
        sw_row = tk.Frame(c_modules, bg=_PANEL, highlightbackground=_blend(_GREEN, 0.2), highlightthickness=1)
        sw_row.pack(fill='x', pady=(4, 0))
        body = tk.Frame(sw_row, bg=_PANEL)
        body.pack(fill='x', padx=8, pady=6)
        var = tk.BooleanVar(value=_effective_module_value(module_key))
        _module_switch_vars[module_key] = var
        sw = ctk.CTkSwitch(
            body,
            text='',
            variable=var,
            onvalue=True,
            offvalue=False,
            fg_color=_BRD_I,
            progress_color=_GREEN,
            button_color=_WHITE,
            switch_width=hud._px(36),
            switch_height=hud._px(18),
            width=0,
            command=lambda k=module_key, v=var: _on_module_toggle(k, v),
        )
        sw.pack(side='left', padx=(0, 8), anchor='n')
        icon_cell = tk.Frame(body, bg=_PANEL, width=hud._px(36), height=hud._px(36))
        icon_cell.pack(side='left', padx=(0, 10), anchor='n')
        icon_cell.pack_propagate(False)
        tk.Label(
            icon_cell,
            text=_module_meta[module_key]['icon'],
            bg=_PANEL,
            fg=_GREEN,
            font=(hud._F, _sf(15)),
        ).place(relx=0.5, rely=0.5, anchor='center')
        txt_col = tk.Frame(body, bg=_PANEL)
        txt_col.pack(side='left', fill='both', expand=True)
        head = tk.Label(
            txt_col,
            text=_module_meta[module_key]['title'],
            bg=_PANEL,
            fg=_TEXT,
            font=(hud._F, _sf(12), 'bold'),
            anchor='w',
        )
        head.pack(fill='x')
        what_lbl = tk.Label(txt_col, text=f"Что делает: {_module_meta[module_key]['what']}", bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w', justify='left')
        what_lbl.pack(fill='x')
        freq_lbl = tk.Label(txt_col, text=f"Частота: {_module_meta[module_key]['freq']}", bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w', justify='left')
        freq_lbl.pack(fill='x')
        impact_lbl = tk.Label(txt_col, text=f"Ресурсы: {_module_meta[module_key]['impact']}", bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(8), 'bold'), anchor='w', justify='left')
        impact_lbl.pack(fill='x', pady=(0, 1))
        def _wrap_labels(e, labels=(what_lbl, freq_lbl, impact_lbl)):
            for lbl_wrap in labels:
                lbl_wrap.configure(wraplength=max(120, e.width - hud._px(20)))
        txt_col.bind('<Configure>', _wrap_labels, add='+')
        for clickable in (icon_cell, head, what_lbl, freq_lbl, impact_lbl):
            clickable.bind('<Button-1>', lambda e, k=module_key, v=var: (v.set(not v.get()), _on_module_toggle(k, v)))
    try:
        from actions.briefing_config import merge_default_briefing_into_settings
        merge_default_briefing_into_settings(hud._settings)
        _save_hud_settings(hud._settings)
    except Exception:
        pass
    c_brief = _card('☀', 'БРИФИНГ И «ЧТО СЕГОДНЯ»', _CYAN)
    _hint(c_brief, 'Что озвучивает утренний брифинг и команда «что сегодня» (если модули календаря/почты выключены — блоки пропускаются).')
    br = hud._settings.get('briefing', {})
    if not isinstance(br, dict):
        br = {}
    _reminder_minute_presets = (5, 10, 15, 20, 30, 45, 60, 90, 120)
    def _snap_reminder_minute(raw: int) -> int:
        raw = max(1, min(120, int(raw or 15)))
        if raw in _reminder_minute_presets:
            return raw
        return min(_reminder_minute_presets, key=lambda x: abs(x - raw))
    _raw_rem = int(br.get('calendar_reminder_minutes', 15) or 15)
    _snapped_rem = _snap_reminder_minute(_raw_rem)
    if _snapped_rem != _raw_rem and isinstance(hud._settings.get('briefing'), dict):
        hud._settings['briefing']['calendar_reminder_minutes'] = _snapped_rem
        _save_hud_settings(hud._settings)
        br = hud._settings['briefing']
    def _brief_key(k: str, default: bool = True) -> bool:
        v = br.get(k, default)
        return bool(v) if isinstance(v, bool) else default
    _brief_vars: dict[str, tk.BooleanVar] = {}
    def _reminder_minute_label(m: int) -> str:
        return f'{m} мин'
    _rem_menu_var = tk.StringVar(value=_reminder_minute_label(_snapped_rem))
    def _save_briefing():
        d = hud._settings.get('briefing')
        if not isinstance(d, dict):
            d = {}
        for k, var in _brief_vars.items():
            d[k] = bool(var.get())
        try:
            label = str(_rem_menu_var.get()).strip()
            m = int(label.split()[0])
            d['calendar_reminder_minutes'] = max(1, min(120, m))
        except (ValueError, tk.TclError, IndexError):
            d['calendar_reminder_minutes'] = 15
        hud._settings['briefing'] = d
        _save_hud_settings(hud._settings)
    def _brief_row(parent, label: str, key: str, default: bool = True):
        row = tk.Frame(parent, bg=_PANEL)
        row.pack(fill='x', pady=2, padx=(8, 0))
        var = tk.BooleanVar(value=_brief_key(key, default))
        _brief_vars[key] = var
        sw_b = ctk.CTkSwitch(
            row,
            text='',
            variable=var,
            onvalue=True,
            offvalue=False,
            fg_color=_BRD_I,
            progress_color=_GREEN,
            button_color=_WHITE,
            switch_width=hud._px(36),
            switch_height=hud._px(18),
            width=0,
            command=_save_briefing,
        )
        sw_b.pack(side='left', padx=(0, 8))
        tk.Label(row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10)), anchor='w').pack(side='left', fill='x', expand=True)
    _brief_row(c_brief, 'Приветствие и тон сводки', 'include_greeting', True)
    _brief_row(c_brief, 'Время', 'include_time', True)
    _brief_row(c_brief, 'Погода', 'include_weather', True)
    _brief_row(c_brief, 'Батарея ноутбука', 'include_battery', True)
    _brief_row(c_brief, 'Предупреждение о нагрузке CPU/RAM', 'include_system_load', True)
    _brief_row(c_brief, 'Календарь (если модуль включён)', 'include_calendar', True)
    _brief_row(c_brief, 'Непрочитанная почта (если модуль включён)', 'include_mail_unread', True)
    _brief_row(c_brief, 'Напоминания до встреч из календаря', 'calendar_reminders_enabled', True)
    rem_row = tk.Frame(c_brief, bg=_PANEL)
    rem_row.pack(fill='x', pady=(6, 2), padx=(8, 0))
    tk.Label(rem_row, text='За сколько минут до события:', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), anchor='w').pack(side='left')
    rem_wrap = tk.Frame(rem_row, bg=_PANEL)
    rem_wrap.pack(side='left', padx=(hud._px(8), 0))
    rem_menu = ctk.CTkOptionMenu(
        rem_wrap,
        values=[_reminder_minute_label(m) for m in _reminder_minute_presets],
        variable=_rem_menu_var,
        command=lambda _v: _save_briefing(),
        width=hud._px(130),
        height=hud._px(42),
        font=(hud._F, _sf(10), 'bold'),
        fg_color=_blend(_CYAN, 0.08),
        button_color=_blend(_CYAN, 0.22),
        button_hover_color=_blend(_CYAN, 0.36),
        dropdown_fg_color=_PANEL,
        dropdown_font=(hud._F, _sf(10), 'bold'),
        dropdown_hover_color=_blend(_CYAN, 0.12),
        dropdown_text_color=_TEXT,
        text_color=_TEXT,
        corner_radius=hud._px(8),
    )
    rem_menu.pack(side='left')
    _feature_mod_btn_row = tk.Frame(c_modules, bg=_PANEL)
    _feature_mod_btn_row.pack(fill='x', pady=(10, 0))
    _mod_preset_grid = tk.Frame(_feature_mod_btn_row, bg=_PANEL)
    _mod_preset_grid.pack(anchor='center', fill='x')
    for _mpi in range(4):
        _mod_preset_grid.columnconfigure(_mpi, weight=1, uniform='modpreset')
    def _reset_module_overrides():
        _feature_modules_overrides.clear()
        hud._settings['feature_modules'] = _feature_modules_overrides
        _save_hud_settings(hud._settings)
        _refresh_module_switches_from_profile()
        _refresh_load_summary()
        _feature_status_lbl.configure(text='Индивидуальные модификации сброшены к профилю.', fg=_GREEN)
        _schedule_auto_dep_sync('reset-overrides')
        try:
            from core.system import refresh_module_flags
            refresh_module_flags()
        except Exception:
            pass
    def _apply_auto_scenario(name: str):
        _feature_modules_overrides.clear()
        if name == 'eco':
            _feature_profile_var.set('minimal')
        elif name == 'balanced':
            _feature_profile_var.set('assistant')
        else:
            _feature_profile_var.set('full')
        _apply_feature_profile()
        _refresh_load_summary()
        _feature_status_lbl.configure(text=f'Автосценарий JARVIS: {name.upper()} применен.', fg=_GREEN)
    _std_action_btn(
        _mod_preset_grid,
        text='⚡ ЭКО',
        command=lambda: _apply_auto_scenario('eco'),
        accent=_CYAN,
        row=0,
        column=0,
        sticky='ew',
        padx=(0, 4),
    )
    _std_action_btn(
        _mod_preset_grid,
        text='◈ БАЛАНС',
        command=lambda: _apply_auto_scenario('balanced'),
        accent=_AMBER,
        row=0,
        column=1,
        sticky='ew',
        padx=(4, 4),
    )
    _std_action_btn(
        _mod_preset_grid,
        text='⬡ MAX',
        command=lambda: _apply_auto_scenario('max'),
        accent=_GREEN,
        row=0,
        column=2,
        sticky='ew',
        padx=(4, 4),
    )
    _std_action_btn(
        _mod_preset_grid,
        text='↺ Сброс',
        command=_reset_module_overrides,
        accent=_CYAN,
        row=0,
        column=3,
        sticky='ew',
        padx=(4, 0),
    )
    _refresh_load_summary()
    tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
    tk.Label(c_modules, text='Профиль установки зависимостей', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(8, 0))
    _dep_var = tk.StringVar(value='base')
    _dep_status_lbl = tk.Label(c_modules, text='Авто-синхронизация зависимостей включена.', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), anchor='w')
    _dep_profiles = [
        ('base', 'LIGHT', ['-r', 'requirements.txt']),
        ('full', 'FULL', ['-r', 'requirements-full.txt']),
        ('vision', 'GAME/VISION', ['-r', 'requirements-base.txt', '-r', 'requirements-vision-game.txt']),
        ('webqa', 'WEB/QA', ['-r', 'requirements-base.txt', '-r', 'requirements-web-qa.txt']),
    ]
    _dep_desc = {
        'base': 'Легкий профиль: базовые зависимости.',
        'full': 'Полный профиль: все возможности.',
        'vision': 'Игры/камера: база + game/vision зависимости.',
        'webqa': 'Веб/ИИ: база + web/qa зависимости.',
    }
    _dep_desc_lbl = tk.Label(c_modules, text=_dep_desc.get(_dep_var.get(), _dep_desc['base']), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), anchor='w', justify='left')
    def _dep_selected():
        _dep_desc_lbl.configure(text=_dep_desc.get(_dep_var.get(), _dep_desc['base']))
    for val, title, _args in _dep_profiles:
        row = tk.Frame(c_modules, bg=_PANEL)
        row.pack(fill='x', pady=(4, 0), padx=(8, 0))
        rb = ctk.CTkRadioButton(
            row,
            text='',
            variable=_dep_var,
            value=val,
            fg_color=_CYAN,
            radiobutton_width=hud._px(18),
            radiobutton_height=hud._px(18),
            command=_dep_selected,
            width=0,
        )
        rb.pack(side='left', padx=(0, 6))
        lbl = tk.Label(row, text=title, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w')
        lbl.pack(side='left', fill='x', expand=True)
        lbl.bind('<Button-1>', lambda e, v=val: (_dep_var.set(v), _dep_selected()))
    _dep_selected()
    _dep_desc_lbl.pack(fill='x', pady=(4, 0))
    _dep_status_lbl.pack(fill='x', pady=(6, 0))
    _dep_install_running = {'busy': False, 'pending_target': None, 'after_id': None}
    _dep_log_path = os.path.join('logs', 'dependency_install.log')
    def _set_dep_status(text: str, color: str = _DIM):
        if _dep_status_lbl.winfo_exists():
            _dep_status_lbl.configure(text=text, fg=color)
    def _current_dep_target() -> dict:
        games_on = _effective_module_value('games')
        qa_on = _effective_module_value('qa')
        include_files = ['requirements-base.txt']
        target_id = 'base'
        if games_on:
            include_files.append('requirements-vision-game.txt')
            target_id = 'vision'
        if qa_on:
            include_files.append('requirements-web-qa.txt')
            target_id = 'webqa' if target_id == 'base' else 'full'
        remove_optional_files = ['requirements-vision-game.txt', 'requirements-web-qa.txt', 'requirements-system-optional.txt']
        remove_files = [f for f in remove_optional_files if f not in include_files]
        return {
            'id': target_id,
            'include_files': include_files,
            'remove_files': remove_files,
            'remove_packages': ['fuzzywuzzy'],
        }
    def _run_cmd(logf, cmd: list[str]) -> int:
        logf.write('$ ' + ' '.join(cmd) + '\n')
        logf.flush()
        proc = subprocess.Popen(
            cmd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            cwd=os.getcwd(),
        )
        rc = proc.wait()
        logf.write(f'-> exit_code={rc}\n\n')
        logf.flush()
        return rc
    def _start_dep_sync(target: dict, reason: str):
        if _dep_install_running['busy']:
            _dep_install_running['pending_target'] = (target, reason)
            _set_dep_status('Синхронизация в очереди...', _AMBER)
            return
        missing_target_files = [p for p in (target['include_files'] + target['remove_files']) if not os.path.exists(p)]
        if missing_target_files:
            _set_dep_status(f'Не найдены файлы зависимостей: {", ".join(missing_target_files)}', _RED)
            return
        _dep_install_running['busy'] = True
        _dep_var.set(target['id'])
        _dep_selected()
        _set_dep_status(f'Авто-синхронизация зависимостей ({reason})...', _CYAN)
        def _worker():
            os.makedirs('logs', exist_ok=True)
            rc = 0
            try:
                with open(_dep_log_path, 'w', encoding='utf-8') as logf:
                    logf.write(f'AUTO SYNC REASON: {reason}\n')
                    logf.write(f'TARGET: {target["id"]}\n')
                    logf.write(f'INCLUDE FILES: {", ".join(target["include_files"])}\n')
                    logf.write(f'REMOVE FILES: {", ".join(target["remove_files"])}\n\n')
                    uninstall_cmd = [sys.executable, '-m', 'pip', 'uninstall', '-y']
                    for rf in target['remove_files']:
                        uninstall_cmd.extend(['-r', rf])
                    uninstall_cmd.extend(target.get('remove_packages', []))
                    if len(uninstall_cmd) > 5:
                        _run_cmd(logf, uninstall_cmd)
                    install_cmd = [sys.executable, '-m', 'pip', 'install']
                    for inc in target['include_files']:
                        install_cmd.extend(['-r', inc])
                    rc = _run_cmd(logf, install_cmd)
                    _run_cmd(logf, [sys.executable, '-m', 'pip', 'check'])
            except Exception as e:
                rc = 1
                with open(_dep_log_path, 'a', encoding='utf-8') as logf:
                    logf.write(f'\nERROR: {e}\n')
            finally:
                _dep_install_running['busy'] = False
                pending = _dep_install_running.get('pending_target')
                _dep_install_running['pending_target'] = None
                if rc == 0:
                    hud._settings['dep_sync_target'] = target['id']
                    _save_hud_settings(hud._settings)
                    win.after(0, lambda: _set_dep_status('Зависимости синхронизированы автоматически.', _GREEN))
                else:
                    win.after(0, lambda: _set_dep_status('Ошибка авто-синхронизации. Откройте лог.', _RED))
                if pending:
                    p_target, p_reason = pending
                    win.after(300, lambda t=p_target, r=p_reason: _start_dep_sync(t, r))
        threading.Thread(target=_worker, daemon=True).start()
    def _schedule_auto_dep_sync(reason: str):
        target = _current_dep_target()
        _dep_var.set(target['id'])
        _dep_selected()
        last_synced = str(hud._settings.get('dep_sync_target', '')).strip().lower()
        if reason != 'manual-sync' and last_synced == target['id'] and not _dep_install_running['busy']:
            _set_dep_status('Зависимости уже соответствуют активному режиму.', _GREEN)
            return
        if _dep_install_running['after_id']:
            try:
                win.after_cancel(_dep_install_running['after_id'])
            except Exception:
                pass
        _dep_install_running['after_id'] = win.after(
            900,
            lambda t=target, r=reason: _start_dep_sync(t, r)
        )
    _dep_btn_row = tk.Frame(c_modules, bg=_PANEL)
    _dep_btn_row.pack(fill='x', pady=(12, 0))
    _dep_btn_grid = tk.Frame(_dep_btn_row, bg=_PANEL)
    _dep_btn_grid.pack(fill='x', anchor='center')
    _dep_btn_grid.columnconfigure(0, weight=1, uniform='depbtn')
    _dep_btn_grid.columnconfigure(1, weight=1, uniform='depbtn')
    def _open_dep_log():
        if not os.path.exists(_dep_log_path):
            _set_dep_status('Лог установки пока отсутствует.', _AMBER)
            return
        try:
            subprocess.Popen(['notepad.exe', _dep_log_path])
        except Exception:
            _set_dep_status('Не удалось открыть лог.', _RED)
    _std_action_btn(
        _dep_btn_grid,
        text='⚙ Синхронизировать сейчас',
        command=lambda: _start_dep_sync(_current_dep_target(), 'manual-sync'),
        accent=_CYAN,
        row=0,
        column=0,
        sticky='ew',
        padx=(0, 5),
    )
    _std_action_btn(
        _dep_btn_grid,
        text='📄 Открыть лог',
        command=_open_dep_log,
        accent=_CYAN,
        row=0,
        column=1,
        sticky='ew',
        padx=(5, 0),
    )
    _schedule_auto_dep_sync('initial-open')
    c_ai = _card('◉', 'ИИ / QA — API КЛЮЧ', _CYAN)
    _hint(
        c_ai,
        'Чтобы ИИ работал, каждому пользователю нужен СВОЙ ключ. '
        'Откройте сайт, создайте ключ (есть бесплатный план), и вставьте его сюда. '
    )
    def _secrets_env_path() -> str:
        try:
            import os as _os
            appdata = _os.environ.get('APPDATA', '') or _os.environ.get('LOCALAPPDATA', '')
            if appdata:
                p = os.path.join(appdata, 'Jarvis', 'secrets.env')
                try:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                except Exception:
                    pass
                return p
        except Exception:
            pass
        return os.path.abspath('.env')
    def _read_env_value(key: str) -> str:
        try:
            import os as _os
            v = (_os.environ.get(key) or '').strip()
            if v:
                return v
        except Exception:
            pass
        try:
            from pathlib import Path
            p = Path(_secrets_env_path())
            if not p.exists():
                return ''
            for line in p.read_text(encoding='utf-8').splitlines():
                s = line.strip()
                if not s or s.startswith('#'):
                    continue
                if s.startswith(key + '='):
                    return s.split('=', 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
        return ''
    def _write_env_value(key: str, value: str) -> bool:
        try:
            from pathlib import Path
            p = Path(_secrets_env_path())
            lines: list[str] = []
            if p.exists():
                lines = p.read_text(encoding='utf-8').splitlines()
            out: list[str] = []
            wrote = False
            for line in lines:
                if line.strip().startswith(key + '='):
                    out.append(f'{key}="{value}"')
                    wrote = True
                else:
                    out.append(line)
            if not wrote:
                if out and out[-1].strip():
                    out.append('')
                out.append(f'{key}="{value}"')
            p.write_text('\n'.join(out) + '\n', encoding='utf-8')
            return True
        except Exception:
            return False
    _ai_status = tk.Label(c_ai, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)))
    _ai_status.pack(fill='x', pady=(2, 6))
    def _upd_ai_wrap(e, l=_ai_status):
        l.configure(wraplength=max(100, e.width - 20))
    c_ai.bind('<Configure>', _upd_ai_wrap, add='+')
    def _ai_set_status(t: str, col: str = _DIM):
        try:
            _ai_status.configure(text=t, fg=col)
        except Exception:
            pass
    tk.Label(c_ai, text='GROQ_API_KEY', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w').pack(fill='x', pady=(6, 0))
    _ai_key_entry = ctk.CTkEntry(
        c_ai,
        placeholder_text='gsk_...',
        font=(hud._F, _sf(11), 'bold'),
        fg_color='#0b0e14',
        text_color=_WHITE,
        border_color=_blend(_CYAN, 0.25),
        border_width=2,
        corner_radius=8,
        height=hud._px(48),
        placeholder_text_color=_blend(_WHITE, 0.3),
        show='•',
    )
    _ai_key_entry.pack(fill='x', pady=(2, 8))
    _add_context_menu(_ai_key_entry)
    try:
        _v0 = _read_env_value('GROQ_API_KEY')
        if _v0:
            _ai_key_entry.insert(0, _v0)
    except Exception:
        pass
    def _ai_open_site():
        try:
            import webbrowser
            webbrowser.open('https://console.groq.com/keys')
            _ai_set_status('Открыл сайт Groq. Создайте ключ и вернитесь сюда.', _CYAN)
        except Exception:
            _ai_set_status('Не удалось открыть браузер. Откройте вручную: console.groq.com/keys', _AMBER)
    def _ai_paste_clipboard():
        try:
            val = str(win.clipboard_get()).strip()
            if not val:
                _ai_set_status('Буфер обмена пуст.', _AMBER)
                return
            _ai_key_entry.delete(0, 'end')
            _ai_key_entry.insert(0, val)
            _ai_set_status('Вставлено из буфера. Нажмите «Сохранить ключ».', _GREEN)
        except Exception:
            _ai_set_status('Не удалось прочитать буфер обмена.', _RED)
    def _ai_save_key():
        val = (_ai_key_entry.get() or '').strip().strip('"').strip("'")
        if not val:
            _ai_set_status('Введите ключ.', _AMBER)
            return
        if not val.lower().startswith('gsk_'):
            _ai_set_status('Похоже, это не Groq ключ (обычно начинается с gsk_). Всё равно сохраню.', _AMBER)
        ok = _write_env_value('GROQ_API_KEY', val)
        if ok:
            _ai_set_status('Сохранено в secrets.env (профиль пользователя). Перезапуск не обязателен, но желателен.', _GREEN)
        else:
            _ai_set_status('Не удалось записать secrets.env (проверьте права/папку).', _RED)
    btn_row_ai = tk.Frame(c_ai, bg=_PANEL)
    btn_row_ai.pack(fill='x', pady=(14, 0))
    ai_btn_grid = tk.Frame(btn_row_ai, bg=_PANEL)
    ai_btn_grid.pack(fill='x', anchor='center')
    for _ai_i in range(3):
        ai_btn_grid.columnconfigure(_ai_i, weight=1, uniform='ai_btn')
    _std_action_btn(
        ai_btn_grid,
        text='🌐 Открыть сайт',
        command=_ai_open_site,
        accent=_CYAN,
        row=0,
        column=0,
        sticky='ew',
        padx=(0, 4),
    )
    _std_action_btn(
        ai_btn_grid,
        text='📋 Вставить',
        command=_ai_paste_clipboard,
        accent=_CYAN,
        row=0,
        column=1,
        sticky='ew',
        padx=(4, 4),
    )
    _std_action_btn(
        ai_btn_grid,
        text='💾 Сохранить ключ',
        command=_ai_save_key,
        accent=_CYAN,
        row=0,
        column=2,
        sticky='ew',
        padx=(4, 0),
    )
    c3 = _card('◎', 'РАСПОЗНАВАНИЕ РЕЧИ (STT)', _GREEN)
    _cur_stt = hud._settings.get('stt_engine', 'gigaam')
    _stt_var = tk.StringVar(value=_cur_stt)
    _vosk_warn_frame = tk.Frame(c3, bg=_blend(_AMBER, 0.08), highlightbackground=_blend(_AMBER, 0.3), highlightthickness=1)
    _vosk_warn_inner = tk.Frame(_vosk_warn_frame, bg=_blend(_AMBER, 0.08))
    _vosk_warn_inner.pack(fill='x', padx=8, pady=6)
    tk.Label(_vosk_warn_inner, text='Р', bg=_blend(_AMBER, 0.08), fg=_AMBER, font=(hud._F, _sf(14))).pack(side='left', padx=(0, 8))
    tk.Label(_vosk_warn_inner, text='Внимание: Vosk лёгкая модель.\nТочность распознавания снижена, но нагрузка на систему минимальна.', bg=_blend(_AMBER, 0.08), fg=_AMBER, font=(hud._F, _sf(9)), justify='left', anchor='w').pack(side='left')
    _active_stt_cards = []
    def _on_stt_change():
        engine = _stt_var.get()
        if engine == 'vosk':
            _vosk_warn_frame.pack(fill='x', pady=(6, 0))
        else:
            _vosk_warn_frame.pack_forget()
        hud._settings['stt_engine'] = engine
        _save_hud_settings(hud._settings)
        for val, card, col in _active_stt_cards:
            card.configure(highlightbackground=_blend(col, 0.35) if engine == val else _BRD)
    _stt_restart_warn = tk.Frame(c3, bg=_blend(_RED, 0.08), highlightbackground=_blend(_RED, 0.3), highlightthickness=1)
    tk.Label(_stt_restart_warn, text='⟳ Изменение движка STT требует перезапуска Джарвиса.', bg=_blend(_RED, 0.08), fg=_RED, font=(hud._F, _sf(9)), justify='left').pack(padx=10, pady=6)
    def _on_stt_change_plus():
        _on_stt_change()
        if _stt_var.get() != _cur_stt:
            _stt_restart_warn.pack(fill='x', pady=(6, 0))
        else:
            _stt_restart_warn.pack_forget()
    _stt_options = [('gigaam', '☁', 'GigaAM', 'Высокая точность', 'Требует GPU / мощный CPU', _GREEN), ('vosk', '📦', 'Vosk', 'Офлайн, лёгкий', 'Минимальная нагрузка на ОЗУ', _AMBER)]
    for val, icon, name, badge_txt, desc, col in _stt_options:
        rb_card = tk.Frame(c3, bg=_BG, highlightbackground=_blend(col, 0.3) if _stt_var.get() == val else _BRD, highlightthickness=1)
        rb_card.pack(fill='x', pady=(4, 0))
        rb_inner = tk.Frame(rb_card, bg=_BG)
        rb_inner.pack(fill='x', padx=10, pady=8)
        rb = ctk.CTkRadioButton(rb_inner, text='', variable=_stt_var, value=val, fg_color=col, command=None, radiobutton_width=hud._px(18), radiobutton_height=hud._px(18), width=0)
        rb.pack(side='left', padx=(0, 4))
        icon_lbl = tk.Label(rb_inner, text=icon, bg=_BG, fg=col, font=(hud._F, _sf(14)))
        icon_lbl.pack(side='left', padx=(0, 5))
        badge_f = tk.Frame(rb_inner, bg=_blend(col, 0.1), highlightbackground=_blend(col, 0.35), highlightthickness=1)
        badge_f.pack(side='right')
        tk.Label(badge_f, text=badge_txt, bg=_blend(col, 0.1), fg=col, font=(hud._F, _sf(10), 'bold')).pack(padx=10, pady=6)
        info = tk.Frame(rb_inner, bg=_BG)
        info.pack(side='left', fill='both', expand=True)
        tk.Label(info, text=name, bg=_BG, fg=col, font=(hud._F, _sf(13), 'bold'), anchor='w').pack(anchor='w')
        desc_lbl = tk.Label(info, text=desc, bg=_BG, fg=_DIM, font=(hud._F, _sf(10)), anchor='w', justify='left')
        desc_lbl.pack(anchor='w')
        def _upd_desc(e, l=desc_lbl):
            l.configure(wraplength=max(100, e.width - 10))
        info.bind('<Configure>', _upd_desc, add='+')
        _active_stt_cards.append((val, rb_card, col))
        def _bind_safe(w, v=val):
            try:
                w.bind('<Button-1>', lambda e, val=v: (_stt_var.set(val), _on_stt_change_plus()))
                for child in w.winfo_children():
                    child.bind('<Button-1>', lambda e, val=v: (_stt_var.set(val), _on_stt_change_plus()))
                    for sub in child.winfo_children():
                        sub.bind('<Button-1>', lambda e, val=v: (_stt_var.set(val), _on_stt_change_plus()))
            except: pass
        _bind_safe(rb_card)
        rb.configure(command=_on_stt_change_plus)
    if _cur_stt == 'vosk':
        _vosk_warn_frame.pack(fill='x', pady=(6, 0))
    c4 = _card('◈', 'МИКРОФОН / ЧУВСТВИТЕЛЬНОСТЬ', _AMBER)
    try:
        from core.mic_calibration import load_profile as _load_mp
        _mp = _load_mp()
        _cur_thresh = int(_mp.get('threshold', 200))
        _cur_gain = float(_mp.get('gain', 2.5))
    except Exception:
        _cur_thresh, _cur_gain = (200, 2.5)
    _thresh_lbl = _label_row(c4, 'Порог срабатывания (Threshold)', _AMBER)
    _thresh_lbl.configure(text=str(_cur_thresh))
    _hint(c4, 'Ниже = чувствительнее к тихому голосу  •  Выше = только громкий голос')
    tk.Label(c4, text='✓  Применяется сразу, без перезапуска',
             bg=_PANEL, fg=_GREEN, font=(hud._F, _sf(8))).pack(anchor='w', padx=4, pady=(0, 4))
    _cur_vol = float(hud._settings.get('volume', 1.0))
    _live_params = {'t': _cur_thresh, 'g': _cur_gain, 'v': _cur_vol}
    _thresh_save_after = [None]
    def _on_thresh(v):
        t = int(float(v))
        _live_params['t'] = t
        _thresh_lbl.configure(text=str(t))
        if _thresh_save_after[0]:
            win.after_cancel(_thresh_save_after[0])
        hud.update_jarvis_params(_live_params['t'], _live_params['g'], _live_params['v'])
        def _save():
            try:
                from core.mic_calibration import load_profile as _lp, save_profile as _sp
                mp = _lp()
                _sp(t, float(mp.get('gain', _cur_gain)), float(mp.get('noise_floor', 0)))
                if hasattr(hud, '_mic_thresh_lbl') and hud._mic_thresh_lbl.winfo_exists():
                    hud._mic_thresh_lbl.configure(text=str(t))
            except Exception:
                pass
        _thresh_save_after[0] = win.after(600, _save)
    _slider(c4, 30, 1200, 117, _AMBER, _cur_thresh, _on_thresh)
    tk.Frame(c4, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
    _gain_lbl = _label_row(c4, 'Усиление микрофона (Gain)', _AMBER)
    _gain_lbl.configure(text=f'{_cur_gain:.1f}×')
    _hint(c4, '1.0× = без усиления  •  6.0× = максимальное усиление (для слабого микрофона)')
    _gain_save_after = [None]
    def _on_gain(v):
        g = round(float(v), 1)
        _live_params['g'] = g
        _gain_lbl.configure(text=f'{g:.1f}×')
        if _gain_save_after[0]:
            win.after_cancel(_gain_save_after[0])
        hud.update_jarvis_params(_live_params['t'], _live_params['g'], _live_params['v'])
        def _save():
            try:
                from core.mic_calibration import load_profile as _lp, save_profile as _sp
                mp = _lp()
                _sp(int(mp.get('threshold', _cur_thresh)), g, float(mp.get('noise_floor', 0)))
                if hasattr(hud, '_mic_gain_lbl') and hud._mic_gain_lbl.winfo_exists():
                    hud._mic_gain_lbl.configure(text=f'×{g:.1f}')
            except Exception:
                pass
        _gain_save_after[0] = win.after(600, _save)
    _slider(c4, 1.0, 6.0, 50, _AMBER, _cur_gain, _on_gain)
    tk.Frame(c4, bg=_BRD, height=1).pack(fill='x', pady=(6, 0))
    tk.Label(
        c4,
        text='Устройства ввода / вывода',
        bg=_PANEL,
        fg=_AMBER,
        font=(hud._F, _sf(10), 'bold'),
        anchor='w',
    ).pack(fill='x', pady=(4, 0))
    _hint(c4, 'Выберите микрофон и устройство для голоса JARVIS. '
              'Микрофон применяется сразу. Вывод (TTS) может потребовать перезапуск.')
    def _load_settings_json() -> dict:
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'jarvis_settings.json'
            if p.exists():
                d = json.loads(p.read_text(encoding='utf-8'))
                return d if isinstance(d, dict) else {}
        except Exception:
            pass
        return {}
    def _save_settings_json(d: dict) -> None:
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'jarvis_settings.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
    _aud_status = tk.Label(
        c4,
        text='',
        bg=_PANEL,
        fg=_DIM,
        font=(hud._F, _sf(10)),
        anchor='w',
        justify='left',
    )
    _aud_status.pack(fill='x', pady=(0, 4))
    def _set_aud_status(t: str, col: str = _DIM):
        try:
            _aud_status.configure(text=t, fg=col)
        except Exception:
            pass
    def _list_devices():
        _SKIP_IN  = {'Microsoft Sound Mapper - Input',  'Primary Sound Capture Driver'}
        _SKIP_OUT = {'Microsoft Sound Mapper - Output', 'Primary Sound Driver'}
        try:
            import pyaudio
            pa = pyaudio.PyAudio()
            mme_devs:   list[dict] = []
            wasapi_devs: list[dict] = []
            for i in range(pa.get_device_count()):
                try:
                    d = pa.get_device_info_by_index(i)
                    rec = dict(d)
                    rec['_idx'] = i
                    api = int(d.get('hostApi', -1))
                    if api == 0:
                        mme_devs.append(rec)
                    elif api == 2:
                        wasapi_devs.append(rec)
                except Exception:
                    pass
            def _prefix(name: str) -> str:
                return name[:12].lower()
            wasapi_in_full:  dict[str, str] = {}
            wasapi_out_full: dict[str, str] = {}
            for d in wasapi_devs:
                n = str(d.get('name', '')).strip()
                if not n:
                    continue
                if int(d.get('maxInputChannels',  0)) > 0:
                    wasapi_in_full.setdefault(_prefix(n), n)
                if int(d.get('maxOutputChannels', 0)) > 0:
                    wasapi_out_full.setdefault(_prefix(n), n)
            ins:  list[tuple[int, str]] = []
            outs: list[tuple[int, str]] = []
            for d in mme_devs:
                name    = str(d.get('name', '')).strip()
                idx     = int(d['_idx'])
                n_in    = int(d.get('maxInputChannels',  0))
                n_out   = int(d.get('maxOutputChannels', 0))
                if n_in > 0 and name not in _SKIP_IN:
                    full = wasapi_in_full.get(_prefix(name), name)
                    ins.append((idx, full))
                if n_out > 0 and name not in _SKIP_OUT:
                    full = wasapi_out_full.get(_prefix(name), name)
                    outs.append((idx, full))
            try:
                pa.terminate()
            except Exception:
                pass
            return ins, outs
        except Exception:
            return [], []
    _in_list, _out_list = _list_devices()
    _s0 = _load_settings_json()
    _in_idx0  = _s0.get('audio_input_device_index')
    _out_name0 = _s0.get('audio_output_device_name')
    if not isinstance(_in_idx0, int):
        _in_idx0 = _in_list[0][0] if _in_list else None
    if not isinstance(_out_name0, str):
        _out_name0 = ''
    def _fmt_dev(i: int, name: str) -> str:
        safe = name.replace('\n', ' ').replace('\r', '').strip()
        return safe
    _in_default_label = '⬥ Системный микрофон (по умолчанию)'
    _out_default_label = '⬥ Системный вывод (по умолчанию)'
    _in_map  = {_in_default_label: None}
    _in_map.update({_fmt_dev(i, n): i for (i, n) in _in_list})
    _out_map = {_out_default_label: ''}
    _out_map.update({n: n for (_i, n) in _out_list})
    _in_init  = next((k for k, v in _in_map.items()  if v == _in_idx0),  _in_default_label)
    _out_init = next((k for k, v in _out_map.items() if v == _out_name0), _out_default_label)
    _in_var  = tk.StringVar(value=_in_init)
    _out_var = tk.StringVar(value=_out_init)
    def _dev_count_label(n: int) -> str:
        if n == 0:
            return 'Устройства не обнаружены'
        if n % 10 == 1 and n % 100 != 11:
            return f'{n} устройство найдено'
        if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
            return f'{n} устройства найдено'
        return f'{n} устройств найдено'
    _AUD_ICO = hud._px(40)
    _mic_block = tk.Frame(c4, bg=_PANEL)
    _mic_block.pack(fill='x', pady=(2, 0))
    _mic_top = tk.Frame(_mic_block, bg=_PANEL)
    _mic_top.pack(fill='x', pady=(0, 6))
    _in_icon = tk.Frame(
        _mic_top,
        bg=_blend(_AMBER, 0.10),
        highlightbackground=_blend(_AMBER, 0.28),
        highlightthickness=1,
        width=_AUD_ICO,
        height=_AUD_ICO,
    )
    _in_icon.pack(side='left', padx=(0, 10))
    _in_icon.pack_propagate(False)
    tk.Label(_in_icon, text='🎙', bg=_blend(_AMBER, 0.10), fg=_AMBER, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
    _in_col = tk.Frame(_mic_top, bg=_PANEL)
    _in_col.pack(side='left', fill='x', expand=True)
    tk.Label(_in_col, text='Микрофон (ввод)', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(_in_col, text=_dev_count_label(len(_in_list)), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9))).pack(anchor='w')
    tk.Label(
        _mic_block,
        text='Выбор устройства',
        bg=_PANEL,
        fg=_blend(_TEXT, 0.55),
        font=(hud._F, _sf(8)),
        anchor='w',
    ).pack(fill='x', pady=(0, 4))
    _in_menu_shell = tk.Frame(
        _mic_block,
        bg='#070a10',
        highlightbackground=_blend(_AMBER, 0.22),
        highlightthickness=1,
    )
    _in_menu_shell.pack(fill='x', pady=(0, 10))
    _in_menu = ctk.CTkOptionMenu(
        _in_menu_shell,
        values=list(_in_map.keys()),
        variable=_in_var,
        command=lambda _v: None,
        width=hud._px(560),
        height=hud._px(40),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='#0c121c',
        button_color=_blend(_AMBER, 0.22),
        button_hover_color=_blend(_AMBER, 0.36),
        dropdown_fg_color='#0d1117',
        dropdown_font=(hud._F, _sf(10), 'bold'),
        dropdown_hover_color=_blend(_AMBER, 0.14),
        dropdown_text_color=_TEXT,
        text_color=_TEXT,
        corner_radius=10,
    )
    _in_menu.pack(fill='x', padx=5, pady=5)
    _out_block = tk.Frame(c4, bg=_PANEL)
    _out_block.pack(fill='x', pady=(10, 0))
    _out_top = tk.Frame(_out_block, bg=_PANEL)
    _out_top.pack(fill='x', pady=(0, 6))
    _out_icon = tk.Frame(
        _out_top,
        bg=_blend(_MAG, 0.10),
        highlightbackground=_blend(_MAG, 0.28),
        highlightthickness=1,
        width=_AUD_ICO,
        height=_AUD_ICO,
    )
    _out_icon.pack(side='left', padx=(0, 10))
    _out_icon.pack_propagate(False)
    tk.Label(_out_icon, text='🔊', bg=_blend(_MAG, 0.10), fg=_MAG, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
    _out_col = tk.Frame(_out_top, bg=_PANEL)
    _out_col.pack(side='left', fill='x', expand=True)
    tk.Label(_out_col, text='Вывод (голос JARVIS)', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(anchor='w')
    tk.Label(_out_col, text=_dev_count_label(len(_out_list)), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9))).pack(anchor='w')
    tk.Label(
        _out_block,
        text='Выбор устройства',
        bg=_PANEL,
        fg=_blend(_TEXT, 0.55),
        font=(hud._F, _sf(8)),
        anchor='w',
    ).pack(fill='x', pady=(0, 4))
    _out_menu_shell = tk.Frame(
        _out_block,
        bg='#070a10',
        highlightbackground=_blend(_MAG, 0.22),
        highlightthickness=1,
    )
    _out_menu_shell.pack(fill='x', pady=(0, 4))
    _out_menu = ctk.CTkOptionMenu(
        _out_menu_shell,
        values=list(_out_map.keys()),
        variable=_out_var,
        command=lambda _v: None,
        width=hud._px(560),
        height=hud._px(40),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='#0c121c',
        button_color=_blend(_MAG, 0.22),
        button_hover_color=_blend(_MAG, 0.36),
        dropdown_fg_color='#0d1117',
        dropdown_font=(hud._F, _sf(10), 'bold'),
        dropdown_hover_color=_blend(_MAG, 0.14),
        dropdown_text_color=_TEXT,
        text_color=_TEXT,
        corner_radius=10,
    )
    _out_menu.pack(fill='x', padx=5, pady=5)
    def _c4_audio_layout(_e=None):
        try:
            w = int(c4.winfo_width() or 0)
            if w > 1:
                _aud_status.configure(wraplength=max(hud._px(100), w - hud._px(24)))
                mw = max(hud._px(260), w - hud._px(56))
                _in_menu.configure(width=mw)
                _out_menu.configure(width=mw)
        except Exception:
            pass
    c4.bind('<Configure>', lambda e: _c4_audio_layout(e), add='+')
    win.after(80, _c4_audio_layout)
    def _apply_audio_settings():
        s = _load_settings_json()
        sel_in = _in_var.get()
        if sel_in in _in_map:
            v = _in_map[sel_in]
            if v is None:
                s.pop('audio_input_device_index', None)
            else:
                s['audio_input_device_index'] = int(v)
        sel_out = _out_var.get()
        if sel_out in _out_map:
            v = _out_map[sel_out]
            if not v:
                s.pop('audio_output_device_name', None)
            else:
                s['audio_output_device_name'] = str(v).strip()
        _save_settings_json(s)
        _set_aud_status('✓ Сохранено. Микрофон применяется сразу; вывод может потребовать перезапуск.', _GREEN)
    def _run_calibration_ui():
        _set_aud_status('🔄  Поиск лучшей частоты…  JARVIS не реагирует на «Джарвис».',
                        _AMBER)
        def _worker():
            ok = False
            msg = 'Готово.'
            t_result: int   = _live_params['t']
            g_result: float = _live_params['g']
            rate_used: int  = 16000
            try:
                from core.engine.jarvis import get_engine
                eng = get_engine()
                if eng:
                    eng._calibrating = True
                try:
                    import pyaudio
                    from config_pack.config import CHUNK_MS
                    from core.audio_utils import open_input_stream
                    from core.mic_calibration import (
                        run_calibration, find_best_rate, load_profile as _lp,
                    )
                    pa = pyaudio.PyAudio()
                    s  = _load_settings_json()
                    di = s.get('audio_input_device_index')
                    di = int(di) if isinstance(di, int) else None
                    best_rate = find_best_rate(pa, CHUNK_MS, di)
                    rate_used = best_rate
                    win.after(
                        0,
                        lambda r=best_rate: _set_aud_status(
                            f'✓ Лучшая частота: {r} Гц — открываю микрофон…', _AMBER),
                    )
                    chunk = max(128, int(best_rate * CHUNK_MS / 1000))
                    stream = open_input_stream(pa, best_rate, chunk, device_index=di)
                    try:
                        t_result, g_result = run_calibration(
                            stream, chunk, best_rate, CHUNK_MS)
                        ok = True
                        s2 = _load_settings_json()
                        s2['best_sample_rate'] = best_rate
                        _save_settings_json(s2)
                        msg = (f'✓ Калибровка завершена — '
                               f'{best_rate} Гц  |  '
                               f'Threshold={t_result}  |  '
                               f'Gain={g_result:.1f}×')
                    finally:
                        try:
                            stream.close()
                        except Exception:
                            pass
                        try:
                            pa.terminate()
                        except Exception:
                            pass
                finally:
                    if eng:
                        eng._calibrating = False
            except Exception as exc:
                msg = f'Ошибка калибровки: {exc}'
                ok  = False
            def _refresh_ui(t=t_result, g=g_result):
                try:
                    _thresh_lbl.configure(text=str(t))
                    _gain_lbl.configure(text=f'{g:.1f}×')
                    _live_params['t'] = t
                    _live_params['g'] = g
                except Exception:
                    pass
                try:
                    hud.update_jarvis_params(
                        int(t), float(g),
                        float(hud._settings.get('volume', 1.0)),
                    )
                except Exception:
                    pass
                try:
                    if hasattr(hud, '_mic_thresh_lbl') and hud._mic_thresh_lbl.winfo_exists():
                        hud._mic_thresh_lbl.configure(text=str(t))
                    if hasattr(hud, '_mic_gain_lbl') and hud._mic_gain_lbl.winfo_exists():
                        hud._mic_gain_lbl.configure(text=f'×{g:.1f}')
                except Exception:
                    pass
                _set_aud_status(msg, _GREEN if ok else _RED)
            win.after(0, _refresh_ui)
        threading.Thread(target=_worker, daemon=True).start()
    _aud_row = tk.Frame(c4, bg=_PANEL)
    _aud_row.pack(fill='x', pady=(10, 0))
    _aud_btn_inner = tk.Frame(_aud_row, bg=_PANEL)
    _aud_btn_inner.pack(anchor='center')
    _btn_w = hud._px(280)
    ctk.CTkButton(
        _aud_btn_inner,
        text='🎙 Тест и калибровка',
        width=_btn_w,
        height=hud._px(48),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_AMBER, 0.18),
        text_color=_AMBER,
        border_color=_blend(_AMBER, 0.4),
        border_width=2,
        command=_run_calibration_ui,
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _aud_btn_inner,
        text='✓ Сохранить устройства',
        width=_btn_w,
        height=hud._px(48),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_GREEN, 0.18),
        text_color=_GREEN,
        border_color=_blend(_GREEN, 0.4),
        border_width=2,
        command=_apply_audio_settings,
    ).pack(side='left', padx=10)
    c_vol = _card('🔊', 'ЗВУК / ГРОМКОСТЬ ДЖАРВИСА', _MAG)
    _vol_lbl = _label_row(c_vol, 'Мастер-громкость', _MAG)
    _vol_lbl.configure(text=f'{int(_cur_vol*100)}%')
    _hint(c_vol, 'Влияет на голос и звуковые уведомления Джарвиса')
    _vol_save_after = [None]
    def _on_vol(v):
        vol = round(float(v), 2)
        _live_params['v'] = vol
        _vol_lbl.configure(text=f'{int(vol*100)}%')
        if _vol_save_after[0]:
            win.after_cancel(_vol_save_after[0])
        hud.update_jarvis_params(_live_params['t'], _live_params['g'], _live_params['v'])
        def _save():
            hud._settings['volume'] = vol
            _save_hud_settings(hud._settings)
        _vol_save_after[0] = win.after(600, _save)
    _slider(c_vol, 0.0, 1.0, 100, _MAG, _cur_vol, _on_vol)
    c_code_ext = _card('📄', 'НОВЫЙ ФАЙЛ — РАСШИРЕНИЯ', _CYAN)
    _hint(
        c_code_ext,
        'Подсказки для списка при создании файла (py, .tsx и т.д.). Пока список пуст — '
        'остаётся только расширение из команды и ручной ввод в поле.',
    )
    from actions.programming_extensions import (
        SETTINGS_JSON_KEY as _PROG_EXT_KEY,
        get_programming_extensions as _g_prog_ext,
        normalize_extension as _norm_prog_ext,
        set_programming_extensions as _set_prog_ext,
    )
    _ext_well = tk.Frame(
        c_code_ext,
        bg=_blend(_CYAN, 0.05),
        highlightbackground=_blend(_CYAN, 0.22),
        highlightthickness=1,
    )
    _ext_well.pack(fill='both', expand=True, pady=(2, 10))
    tk.Label(
        _ext_well,
        text='Список подсказок',
        bg=_blend(_CYAN, 0.05),
        fg=_blend(_CYAN, 0.9),
        font=(hud._F, _sf(9), 'bold'),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(10, 6))
    _ext_lb_shell = tk.Frame(_ext_well, bg='#070a10', highlightbackground=_blend(_CYAN, 0.15), highlightthickness=1)
    _ext_lb_shell.pack(fill='both', expand=True, padx=12, pady=(0, 10))
    _ext_lb_fr = tk.Frame(_ext_lb_shell, bg='#070a10')
    _ext_lb_fr.pack(fill='both', expand=True, padx=6, pady=6)
    lb_code_ext = tk.Listbox(
        _ext_lb_fr,
        height=7,
        font=(hud._F, _sf(11)),
        bg='#0c121c',
        fg=_TEXT,
        selectbackground=_blend(_CYAN, 0.38),
        selectforeground=_BG,
        borderwidth=0,
        highlightthickness=0,
        activestyle='none',
        exportselection=False,
    )
    _sb_code_ext = tk.Scrollbar(
        _ext_lb_fr,
        command=lb_code_ext.yview,
        bg='#070a10',
        troughcolor='#070a10',
        activebackground=_blend(_CYAN, 0.45),
        borderwidth=0,
        highlightthickness=0,
        width=hud._px(8),
    )
    lb_code_ext.config(yscrollcommand=_sb_code_ext.set)
    lb_code_ext.pack(side='left', fill='both', expand=True)
    _sb_code_ext.pack(side='right', fill='y', padx=(4, 0))
    def _refresh_prog_ext_lb():
        lb_code_ext.delete(0, tk.END)
        for e in _g_prog_ext():
            lb_code_ext.insert(tk.END, f'  .{e}')
    _refresh_prog_ext_lb()
    tk.Label(
        _ext_well,
        text='Новое расширение',
        bg=_blend(_CYAN, 0.05),
        fg=_blend(_TEXT, 0.65),
        font=(hud._F, _sf(8)),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(0, 4))
    _ext_add_row = tk.Frame(_ext_well, bg=_blend(_CYAN, 0.05))
    _ext_add_row.pack(fill='x', padx=12, pady=(0, 12))
    ent_code_ext = ctk.CTkEntry(
        _ext_add_row,
        placeholder_text='py, tsx, rs или .py  ·  Enter — добавить',
        font=(hud._F, _sf(10)),
        fg_color='#0c121c',
        border_color=_blend(_CYAN, 0.3),
        border_width=1,
        text_color=_WHITE,
        height=hud._px(36),
        corner_radius=10,
    )
    ent_code_ext.pack(fill='x')
    def _sync_prog_ext_to_hud(cur: list[str]):
        if isinstance(hud._settings, dict):
            hud._settings[_PROG_EXT_KEY] = list(cur)
    def _on_add_prog_ext():
        n = _norm_prog_ext(ent_code_ext.get())
        if not n:
            return
        cur = list(_g_prog_ext())
        if n in cur:
            return
        cur.append(n)
        _set_prog_ext(cur)
        _sync_prog_ext_to_hud(cur)
        ent_code_ext.delete(0, tk.END)
        _refresh_prog_ext_lb()
    def _on_del_prog_ext():
        sel = lb_code_ext.curselection()
        if not sel:
            return
        lines = [lb_code_ext.get(i).strip() for i in range(lb_code_ext.size())]
        del lines[sel[0]]
        cur = [_norm_prog_ext(x) for x in lines if _norm_prog_ext(x)]
        _set_prog_ext(cur)
        _sync_prog_ext_to_hud(cur)
        _refresh_prog_ext_lb()
    def _ext_on_return(_e=None):
        _on_add_prog_ext()
        return 'break'
    ent_code_ext.bind('<Return>', _ext_on_return)
    _ext_btn_row = tk.Frame(c_code_ext, bg=_PANEL)
    _ext_btn_row.pack(fill='x', pady=(12, 0))
    _ext_btn_inner = tk.Frame(_ext_btn_row, bg=_PANEL)
    _ext_btn_inner.pack(anchor='center')
    ctk.CTkButton(
        _ext_btn_inner,
        text='➕  Добавить',
        width=hud._px(280),
        height=hud._px(48),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_GREEN, 0.12),
        text_color=_GREEN,
        border_color=_blend(_GREEN, 0.4),
        border_width=2,
        command=_on_add_prog_ext,
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _ext_btn_inner,
        text='🗑  Удалить',
        width=hud._px(280),
        height=hud._px(48),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_RED, 0.14),
        text_color=_RED,
        border_color=_blend(_RED, 0.4),
        border_width=2,
        command=_on_del_prog_ext,
    ).pack(side='left', padx=10)
    c_yt = _card('▶', 'YOUTUBE / СОХРАНЁННЫЕ ВИДЕО', _CYAN)
    _cur_max_saved = int(hud._settings.get('max_saved_videos', 10))
    _max_saved_lbl = _label_row(c_yt, 'Максимум сохранённых видео', _CYAN)
    _max_saved_lbl.configure(text=str(_cur_max_saved))
    _hint(c_yt, 'Старые записи удаляются автоматически при превышении лимита')
    _max_saved_save_after = [None]
    def _on_max_saved(v):
        val = int(float(v))
        _max_saved_lbl.configure(text=str(val))
        if _max_saved_save_after[0]:
            win.after_cancel(_max_saved_save_after[0])
        def _save():
            hud._settings['max_saved_videos'] = val
            _save_hud_settings(hud._settings)
        _max_saved_save_after[0] = win.after(600, _save)
    _slider(c_yt, 1, 50, 49, _CYAN, _cur_max_saved, _on_max_saved)
    _v_row = tk.Frame(c_yt, bg=_PANEL)
    _v_row.pack(fill='x', pady=(14, 0))
    ctk.CTkButton(
        _v_row, text='📋  Просмотр сохранённых видео',
        command=lambda: __import__('ui.dialogs.manage_dlg', fromlist=['open_videos_manager']).open_videos_manager(hud),
        height=hud._px(48), font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent', hover_color=_blend(_CYAN, 0.15),
        text_color=_CYAN, border_color=_blend(_CYAN, 0.4),
        border_width=2, corner_radius=8
    ).pack(anchor='center')
    c_mtg = _card('🔗', 'БЫСТРЫЕ ССЫЛКИ', _GREEN)
    _hint(c_mtg, 'Пары, совещания, конференции — любая ссылка по голосовой фразе.')
    from actions.meetings import get_meetings, save_meetings as _save_meetings
    _meetings_list: list[dict] = list(get_meetings())
    _mtg_count_lbl = tk.Label(c_mtg, text=f'Сохранено: {len(_meetings_list)}', bg=_PANEL, fg=_DIM,
                               font=(hud._F, _sf(9)))
    _mtg_count_lbl.pack(anchor='w', pady=(4, 0))
    _entry_kw = dict(font=(hud._F, _sf(10), 'bold'), fg_color='#0b0e14', text_color=_WHITE,
                     border_color=_blend(_GREEN, 0.25), border_width=2,
                     corner_radius=8, height=hud._px(48),
                     placeholder_text_color=_blend(_WHITE, 0.3))
    _lkw_mtg = dict(bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), anchor='w')
    tk.Label(c_mtg, text='Голосовая фраза', **_lkw_mtg).pack(fill='x', pady=(10, 0))
    _mtg_phrase_entry = ctk.CTkEntry(c_mtg, placeholder_text='например: заходим на пару по математике', **_entry_kw)
    _mtg_phrase_entry.pack(fill='x', pady=(2, 8))
    tk.Label(c_mtg, text='Ссылка', **_lkw_mtg).pack(fill='x')
    _mtg_url_entry = ctk.CTkEntry(c_mtg, placeholder_text='https://zoom.us/j/123...', **_entry_kw)
    _mtg_url_entry.pack(fill='x', pady=(2, 8))
    tk.Label(c_mtg, text='Название (необязательно)', **_lkw_mtg).pack(fill='x')
    _mtg_name_entry = ctk.CTkEntry(c_mtg, placeholder_text='например: Высшая математика', **_entry_kw)
    _mtg_name_entry.pack(fill='x', pady=(2, 12))
    _add_context_menu(_mtg_phrase_entry)
    _add_context_menu(_mtg_url_entry)
    _add_context_menu(_mtg_name_entry)
    _mtg_status = tk.Label(c_mtg, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)))
    _mtg_status.pack(anchor='w', pady=(0, 6))
    def _add_meeting():
        phrase = _mtg_phrase_entry.get().strip().lower()
        url = _mtg_url_entry.get().strip()
        name = _mtg_name_entry.get().strip()
        if not phrase or not url:
            _mtg_status.configure(text='Укажите фразу и ссылку.', fg=_AMBER)
            return
        if not name:
            name = phrase
        _meetings_list.append({'name': name, 'phrase': phrase, 'url': url})
        _save_meetings(_meetings_list)
        _mtg_phrase_entry.delete(0, 'end')
        _mtg_url_entry.delete(0, 'end')
        _mtg_name_entry.delete(0, 'end')
        _mtg_status.configure(text=f'Добавлено: «{phrase}»  ✓', fg=_GREEN)
        _mtg_count_lbl.configure(text=f'Сохранено: {len(_meetings_list)}')
    btn_row_mtg = tk.Frame(c_mtg, bg=_PANEL)
    btn_row_mtg.pack(fill='x', pady=(10, 2))
    _mtg_btn_inner = tk.Frame(btn_row_mtg, bg=_PANEL)
    _mtg_btn_inner.pack(anchor='center')
    _btn_w_mtg = hud._px(280)
    ctk.CTkButton(
        _mtg_btn_inner, text='➕  Добавить ссылку', command=_add_meeting,
        width=_btn_w_mtg,
        height=hud._px(48), font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent', hover_color=_blend(_GREEN, 0.15),
        text_color=_GREEN, border_color=_blend(_GREEN, 0.5),
        border_width=2, corner_radius=8
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _mtg_btn_inner, text='✏  Управление списком',
        command=lambda: __import__('ui.dialogs.manage_dlg', fromlist=['open_meetings_manager']).open_meetings_manager(hud),
        width=_btn_w_mtg,
        height=hud._px(48), font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent', hover_color=_blend(_CYAN, 0.15),
        text_color=_CYAN, border_color=_blend(_CYAN, 0.4),
        border_width=2, corner_radius=8
    ).pack(side='left', padx=10)
    c_gm = _card('✦', 'ИГРОВОЙ РЕЖИМ — ЗАКРЫТИЕ ОКОН', _AMBER)
    _hint(
        c_gm,
        'Что НЕ закрывать при включении игрового режима: '
        'введите фрагмент заголовка (discord, obs) или выберите приложение.'
    )
    def _load_game_mode_prefs_ui() -> dict:
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'game_mode_prefs.json'
            if p.exists():
                d = json.loads(p.read_text(encoding='utf-8'))
                return d if isinstance(d, dict) else {}
        except Exception:
            pass
        return {}
    def _save_game_mode_prefs_ui(d: dict) -> None:
        try:
            import json
            from pathlib import Path
            p = Path('data') / 'game_mode_prefs.json'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception:
            pass
    _gm_status = tk.Label(
        c_gm,
        text='',
        bg=_PANEL,
        fg=_blend(_TEXT, 0.55),
        font=(hud._F, _sf(8)),
        anchor='w',
        justify='left',
    )
    _gm_status.pack(anchor='w', pady=(0, 6))
    _gm_prefs0 = _load_game_mode_prefs_ui()
    _keep0 = _gm_prefs0.get('keep_titles', [])
    if not isinstance(_keep0, list):
        _keep0 = []
    _keep_titles: list[str] = [str(x) for x in _keep0 if isinstance(x, str) and x.strip()]
    def _gm_set_status(t: str, col: str = _DIM):
        try:
            _gm_status.configure(text=t, fg=col)
        except Exception:
            pass
    try:
        from actions.app_launcher import APPS as _APPS
        _app_items = []
        for k, v in (_APPS or {}).items():
            if not isinstance(v, dict):
                continue
            if k in ('explorer',):
                continue
            disp = ''
            if isinstance(v.get('name'), str) and v.get('name'):
                disp = v.get('name')
            elif isinstance(v.get('names'), list) and v.get('names'):
                disp = str(v.get('names')[0])
            else:
                disp = str(k)
            _app_items.append((disp, k))
        _app_items.sort(key=lambda x: x[0].lower())
    except Exception:
        _app_items = []
    _gm_app_map = {'— выбрать —': ''}
    for disp, k in _app_items:
        label = disp
        if label in _gm_app_map:
            label = f'{disp} ({k})'
        _gm_app_map[label] = k
    _gm_well = tk.Frame(
        c_gm,
        bg=_blend(_AMBER, 0.05),
        highlightbackground=_blend(_AMBER, 0.22),
        highlightthickness=1,
    )
    _gm_well.pack(fill='both', expand=True, pady=(2, 10))
    tk.Label(
        _gm_well,
        text='Список исключений',
        bg=_blend(_AMBER, 0.05),
        fg=_blend(_AMBER, 0.92),
        font=(hud._F, _sf(9), 'bold'),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(10, 6))
    _gm_lb_shell = tk.Frame(_gm_well, bg='#070a10', highlightbackground=_blend(_AMBER, 0.18), highlightthickness=1)
    _gm_lb_shell.pack(fill='both', expand=True, padx=12, pady=(0, 10))
    _gm_lb_fr = tk.Frame(_gm_lb_shell, bg='#070a10')
    _gm_lb_fr.pack(fill='both', expand=True, padx=6, pady=6)
    _list_box = tk.Listbox(
        _gm_lb_fr,
        height=6,
        font=(hud._F, _sf(13), 'bold'),
        bg='#0c121c',
        fg=_TEXT,
        selectbackground=_blend(_AMBER, 0.42),
        selectforeground=_BG,
        borderwidth=0,
        highlightthickness=0,
        relief='flat',
        activestyle='none',
        exportselection=False,
    )
    _sb_gm = tk.Scrollbar(
        _gm_lb_fr,
        command=_list_box.yview,
        bg='#070a10',
        troughcolor='#070a10',
        activebackground=_blend(_AMBER, 0.45),
        borderwidth=0,
        highlightthickness=0,
        width=hud._px(8),
    )
    _list_box.config(yscrollcommand=_sb_gm.set)
    _list_box.pack(side='left', fill='both', expand=True)
    _sb_gm.pack(side='right', fill='y', padx=(4, 0))
    tk.Label(
        _gm_well,
        text='Фрагмент заголовка окна',
        bg=_blend(_AMBER, 0.05),
        fg=_blend(_TEXT, 0.65),
        font=(hud._F, _sf(8)),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(0, 4))
    _gm_entry = ctk.CTkEntry(
        _gm_well,
        placeholder_text='например: discord  ·  Enter — добавить',
        font=(hud._F, _sf(10)),
        fg_color='#0c121c',
        text_color=_WHITE,
        border_color=_blend(_AMBER, 0.3),
        border_width=1,
        corner_radius=10,
        height=hud._px(48),
        placeholder_text_color=_blend(_WHITE, 0.3),
    )
    _gm_entry.pack(fill='x', padx=12, pady=(0, 10))
    _add_context_menu(_gm_entry)
    tk.Label(
        _gm_well,
        text='Добавить из приложений',
        bg=_blend(_AMBER, 0.05),
        fg=_blend(_TEXT, 0.65),
        font=(hud._F, _sf(8)),
        anchor='w',
    ).pack(fill='x', padx=12, pady=(0, 4))
    _gm_app_var = tk.StringVar(value='— выбрать —')
    _gm_app_menu = ctk.CTkOptionMenu(
        _gm_well,
        values=list(_gm_app_map.keys()),
        variable=_gm_app_var,
        command=lambda _v: None,
        width=hud._px(300),
        height=hud._px(44),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='#0c121c',
        button_color=_blend(_AMBER, 0.22),
        button_hover_color=_blend(_AMBER, 0.36),
        dropdown_fg_color='#0d1117',
        dropdown_font=(hud._F, _sf(11), 'bold'),
        dropdown_hover_color=_blend(_AMBER, 0.14),
        dropdown_text_color=_TEXT,
        text_color=_TEXT,
        corner_radius=10,
    )
    _gm_app_menu.pack(fill='x', padx=12, pady=(0, 12))
    def _gm_refresh_list():
        try:
            _list_box.delete(0, 'end')
            for s in _keep_titles:
                _list_box.insert('end', f'  {s}')
        except Exception:
            pass
    def _gm_save_now():
        d = _load_game_mode_prefs_ui()
        d['keep_titles'] = list(_keep_titles)
        _save_game_mode_prefs_ui(d)
        _gm_set_status('Сохранено. Изменения применятся при следующем включении игрового режима.', _GREEN)
    def _gm_add():
        s = (_gm_entry.get() or '').strip().lower()
        if not s:
            _gm_set_status('Введите фрагмент заголовка окна.', _AMBER)
            return
        if s in _keep_titles:
            _gm_set_status('Уже в списке.', _DIM)
            return
        _keep_titles.append(s)
        _gm_refresh_list()
        _gm_entry.delete(0, 'end')
        _gm_save_now()
    def _gm_on_entry_return(_e=None):
        _gm_add()
        return 'break'
    _gm_entry.bind('<Return>', _gm_on_entry_return)
    def _gm_add_app_from_menu():
        label = str(_gm_app_var.get() or '').strip()
        app_key = _gm_app_map.get(label, '')
        if not app_key:
            _gm_set_status('Выберите приложение из списка.', _AMBER)
            return
        try:
            from actions.app_launcher import APPS as _APPS2
            app = (_APPS2 or {}).get(app_key) or {}
        except Exception:
            app = {}
        frags: list[str] = []
        for src in (app.get('keywords'), app.get('names')):
            if isinstance(src, list):
                for it in src:
                    if isinstance(it, str) and it.strip():
                        frags.append(it.strip().lower())
            elif isinstance(src, str) and src.strip():
                frags.append(src.strip().lower())
        if not frags:
            frags = [app_key.lower()]
        added = 0
        for f in frags:
            if f and f not in _keep_titles:
                _keep_titles.append(f)
                added += 1
        _gm_refresh_list()
        _gm_save_now()
        _gm_set_status(f'Добавлено: {label} (фрагментов: {added}).', _GREEN)
        _gm_app_var.set('— выбрать —')
    def _gm_remove_selected():
        try:
            sel = list(_list_box.curselection())
        except Exception:
            sel = []
        if not sel:
            _gm_set_status('Выберите элемент в списке.', _AMBER)
            return
        for i in sorted(sel, reverse=True):
            try:
                _keep_titles.pop(i)
            except Exception:
                pass
        _gm_refresh_list()
        _gm_save_now()
    btn_row_gm = tk.Frame(c_gm, bg=_PANEL)
    btn_row_gm.pack(fill='x', pady=(12, 0))
    _gm_btn_inner = tk.Frame(btn_row_gm, bg=_PANEL)
    _gm_btn_inner.pack(anchor='center')
    _gm_btn_kw = {
        'width': hud._px(210),
        'height': hud._px(48),
        'font': (hud._F, _sf(11), 'bold'),
        'fg_color': 'transparent',
        'border_width': 2,
        'corner_radius': 8,
    }
    ctk.CTkButton(
        _gm_btn_inner,
        text='➕  Добавить',
        command=_gm_add,
        hover_color=_blend(_AMBER, 0.18),
        text_color=_AMBER,
        border_color=_blend(_AMBER, 0.55),
        **_gm_btn_kw
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _gm_btn_inner,
        text='🚀  Из приложений',
        command=_gm_add_app_from_menu,
        hover_color=_blend(_AMBER, 0.18),
        text_color=_AMBER,
        border_color=_blend(_AMBER, 0.55),
        **_gm_btn_kw
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _gm_btn_inner,
        text='🗑  Удалить',
        command=_gm_remove_selected,
        hover_color=_blend(_RED, 0.18),
        text_color=_RED,
        border_color=_blend(_RED, 0.55),
        **_gm_btn_kw
    ).pack(side='left', padx=10)
    _gm_refresh_list()
    warn_box = tk.Frame(inner, bg=_blend(_AMBER, 0.1), highlightbackground=_blend(_AMBER, 0.3), highlightthickness=1)
    warn_box.pack(fill='x', pady=(12, 0))
    tk.Label(warn_box, text='⚠  ОБРАТИТЕ ВНИМАНИЕ', bg=_blend(_AMBER, 0.1), fg=_AMBER, font=(hud._F, _sf(10), 'bold')).pack(anchor='w', padx=12, pady=(8, 0))
    _warn_text = tk.Label(
        warn_box,
        text='Настройки микрофона — применяются сразу.  |  STT-модель, модули — нужен перезапуск.',
        bg=_blend(_AMBER, 0.1),
        fg=_AMBER,
        font=(hud._F, _sf(9)),
        justify='left',
        anchor='w',
    )
    _warn_text.pack(anchor='w', padx=12, pady=(2, 6), fill='x')
    try:
        def _wrap_warn(e=None):
            try:
                w = warn_box.winfo_width()
                if w and w > 1:
                    _warn_text.configure(wraplength=max(hud._px(140), w - hud._px(24)))
            except Exception:
                pass
        warn_box.bind('<Configure>', _wrap_warn, add='+')
        warn_box.after(20, _wrap_warn)
    except Exception:
        pass
    def _do_restart():
        import sys, subprocess, os as _os
        exe = sys.executable
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([exe], creationflags=0x00000008)
            else:
                subprocess.Popen([exe] + sys.argv)
        except Exception:
            pass
        finally:
            _os._exit(0)
    import customtkinter as _ctk_r
    _restart_row = tk.Frame(warn_box, bg=_blend(_AMBER, 0.1))
    _restart_row.pack(fill='x', padx=12, pady=(0, 10))
    _restart_inner = tk.Frame(_restart_row, bg=_blend(_AMBER, 0.1))
    _restart_inner.pack(anchor='center')
    _ctk_r.CTkButton(
        _restart_inner,
        text='⟳  Перезапустить JARVIS сейчас',
        command=_do_restart,
        height=hud._px(48),
        font=(hud._F, _sf(11), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_AMBER, 0.22),
        text_color=_AMBER,
        border_color=_blend(_AMBER, 0.6),
        border_width=2,
        corner_radius=10,
    ).pack(padx=20)
    tk.Frame(inner, bg=_BG, height=28).pack()
    tk.Frame(win, bg=_MAG, height=2).pack(fill='x', side='bottom')
