import os, sys, threading, time, subprocess
import tkinter as tk
import customtkinter as ctk
from .base import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _card, _hint, _blend, _std_action_btn, _hero_btn, _add_context_menu, _slider, _label_row, _HUDDropdown

def build_modules_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
    
    # Safe settings access
    _settings = getattr(hud, '_settings', {})
    if not isinstance(_settings, dict): _settings = {}

    try:
        # --- 1. МОДУЛИ И ПРОФИЛИ ---
        c_modules = _card(inner, '🧩', 'МОДУЛИ И ПРОФИЛИ', _GREEN, hud)
        _hint(c_modules, 'Выберите, какие функции и зависимости нужны: это снижает нагрузку и размер установки.', hud)
        
        _feature_profile_var = tk.StringVar(value=str(_settings.get('feature_profile', 'minimal')))
        _feature_status_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)))
        _feature_desc_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), justify='left', anchor='w')
        _feature_desc_lbl.pack(fill='x', pady=(4, 0))
        
        _feature_presets = {
            'full': {'games': True, 'qa': True, 'cinema': True, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': True, 'morning_briefing': True, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False},
            'assistant': {'games': False, 'qa': False, 'cinema': False, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': False, 'morning_briefing': False, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False},
            'minimal': {'games': False, 'qa': False, 'cinema': False, 'system_monitoring': False, 'battery_monitor': False, 'lag_hunter': False, 'morning_briefing': False, 'updater': False, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False}
        }
        _feature_desc_map = {
            'full': 'FULL: Максимальный потенциал Jarvis OS. Активирует все доступные технологии: продвинутый ИИ-поиск, игровой движок (ETS2 / FS / Hogwarts), умную медиа-автоматизацию и глубокий мониторинг ресурсов системы.',
            'assistant': 'ASSISTANT: Сбалансированная конфигурация для повседневных задач. Оптимизирует нагрузку, отключая тяжелые игровые и медиа-модули, сохраняя при этом все функции умного ассистента.',
            'minimal': 'MINIMAL: Ультра-легкая редакция. JARVIS сводится к базовому ядру распознавания речи и управлению окнами. Обладает самой высокой скоростью отклика и минимальным потреблением памяти.'
        }
        _feature_modules_overrides = _settings.get('feature_modules', {})
        if not isinstance(_feature_modules_overrides, dict): _feature_modules_overrides = {}
        
        _module_switch_vars: dict[str, tk.BooleanVar] = {}
        def _effective_module_value(module_key: str) -> bool:
            profile = _feature_profile_var.get(); base = _feature_presets.get(profile, _feature_presets['minimal']).get(module_key, False)
            override = _feature_modules_overrides.get(module_key); return override if isinstance(override, bool) else base

        def _refresh_module_switches_from_profile():
            for module_key, var in _module_switch_vars.items(): var.set(_effective_module_value(module_key))

        def _apply_feature_profile():
            profile = _feature_profile_var.get(); _settings['feature_profile'] = profile; _save_hud_settings(_settings)
            _feature_desc_lbl.configure(text=_feature_desc_map.get(profile, _feature_desc_map['minimal']))
            _feature_status_lbl.configure(text='Профиль сохранен. Перезапуск JARVIS обязателен.', fg=_AMBER)
            _refresh_module_switches_from_profile(); _refresh_load_summary(); _schedule_auto_dep_sync('profile-change')
            try: from core.system import refresh_module_flags; refresh_module_flags()
            except Exception: pass

        _feature_options = [('full', 'FULL', 'Все функции'), ('assistant', 'ASSISTANT', 'Без ИИ/игр/кино'), ('minimal', 'MINIMAL', 'Максимально легкий')]
        for val, title, sub in _feature_options:
            row = tk.Frame(c_modules, bg=_PANEL); row.pack(fill='x', pady=(4, 0), padx=(8, 0))
            rb = ctk.CTkRadioButton(row, text='', variable=_feature_profile_var, value=val, fg_color=_GREEN, radiobutton_width=hud._px(18), radiobutton_height=hud._px(18), command=_apply_feature_profile, width=0)
            rb.pack(side='left', padx=(0, 6))
            lbl = tk.Label(row, text=f'{title} — {sub}', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w'); lbl.pack(side='left', fill='x', expand=True); lbl.bind('<Button-1>', lambda e, v=val: (_feature_profile_var.set(v), _apply_feature_profile()))
        _feature_desc_lbl.configure(text=_feature_desc_map.get(_feature_profile_var.get(), _feature_desc_map['minimal']))
        _feature_status_lbl.pack(fill='x', pady=(6, 0))

        def _upd_desc_wrap(e, l=_feature_desc_lbl):
            new_wl = max(hud._px(100), e.width - hud._px(20))
            l.configure(wraplength=new_wl)
        c_modules.bind('<Configure>', _upd_desc_wrap, add='+')

        tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(12, 0))
        tk.Label(c_modules, text='Детальная настройка модулей', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(10, 0))
        
        _module_meta = {
            'qa': {'title': 'ИИ / QA', 'icon': '◉', 'what': 'Сложные вопросы через LLM.', 'weight': 3, 'impact': 'CPU: средний'},
            'games': {'title': 'Игровой модуль', 'icon': '✦', 'what': 'Игровой режим и профили.', 'weight': 4, 'impact': 'CPU: высокий'},
            'cinema': {'title': 'Кино модуль', 'icon': '▶', 'what': 'Медиа-автоматизация.', 'weight': 1, 'impact': 'CPU: низкий'},
            'system_monitoring': {'title': 'Системный мониторинг', 'icon': '▦', 'what': 'Метрики в HUD.', 'weight': 3, 'impact': 'CPU: средний'},
            'battery_monitor': {'title': 'Монитор батареи', 'icon': '▣', 'what': 'Отслеживание питания.', 'weight': 1, 'impact': 'CPU: низкий'},
            'lag_hunter': {'title': 'Lag Hunter', 'icon': '⟳', 'what': 'Анализ задержек.', 'weight': 2, 'impact': 'CPU: средний'},
            'morning_briefing': {'title': 'Утренний брифинг', 'icon': '☀', 'what': 'Сводка при старте.', 'weight': 1, 'impact': 'CPU: низкий'},
            'updater': {'title': 'Автообновления', 'icon': '⬡', 'what': 'Автоматический апдейтер.', 'weight': 1, 'impact': 'CPU: низкий'},
            'network_profiles': {'title': 'Сеть: профили', 'icon': '◎', 'what': 'Профили и VPN.', 'weight': 1, 'impact': 'CPU: низкий'},
            'system_health': {'title': 'Система: диски', 'icon': '▤', 'what': 'Отчет по дискам.', 'weight': 1, 'impact': 'CPU: низкий'},
            'calendar_ics': {'title': 'Календарь ICS', 'icon': '🗓', 'what': 'События календаря.', 'weight': 1, 'impact': 'CPU: низкий'},
            'inbox_digest': {'title': 'Почта', 'icon': '✉', 'what': 'Проверка почты.', 'weight': 1, 'impact': 'CPU: низкий'},
        }
        _module_order = list(_module_meta.keys())
        _module_load_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(9), 'bold'), anchor='w'); _module_load_lbl.pack(fill='x', pady=(4, 2))
        
        def _refresh_load_summary():
            score = sum(int(_module_meta.get(k,{}).get('weight',1)) for k in _module_order if _module_switch_vars.get(k) and _module_switch_vars[k].get())
            level, col = ('НИЗКАЯ', _GREEN) if score <= 4 else ('СРЕДНЯЯ', _AMBER) if score <= 9 else ('ВЫСОКАЯ', _RED)
            _module_load_lbl.configure(text=f'JARVIS LOAD PROFILE: {level} (Score: {score})', fg=col)

        def _on_module_toggle(k, var):
            _feature_modules_overrides[k] = bool(var.get())
            _settings['feature_modules'] = _feature_modules_overrides
            _save_hud_settings(_settings)
            _refresh_load_summary()
            
            # --- Adaptive Dependency Logic ---
            qa_on = _module_switch_vars.get('qa') and _module_switch_vars['qa'].get()
            gm_on = _module_switch_vars.get('games') and _module_switch_vars['games'].get()
            
            if qa_on and gm_on: _dep_var.set('full')
            elif qa_on: _dep_var.set('webqa')
            elif gm_on: _dep_var.set('vision')
            else: _dep_var.set('base')
            
            _on_dep_change()
            _schedule_auto_dep_sync('module-toggle')
            
            try: from core.system import refresh_module_flags; refresh_module_flags()
            except Exception: pass

        for module_key in _module_order:
            row = tk.Frame(c_modules, bg=_PANEL, highlightbackground=_blend(_GREEN, 0.2), highlightthickness=1)
            row.pack(fill='x', pady=2) # Increased pady
            body = tk.Frame(row, bg=_PANEL)
            body.pack(fill='x', padx=10, pady=6) # Increased padding
            
            var = tk.BooleanVar(value=_effective_module_value(module_key))
            _module_switch_vars[module_key] = var
            
            ctk.CTkSwitch(
                body, text='', variable=var, 
                fg_color=_BRD_I, progress_color=_GREEN, button_color=_WHITE, 
                command=lambda k=module_key, v=var: _on_module_toggle(k, v), 
                switch_width=hud._px(44), # Larger switch
                switch_height=hud._px(20), 
                width=0
            ).pack(side='left', padx=(0, 12))
            
            ic_f_size = 14 if module_key == 'calendar_ics' else 18 # Larger icons
            tk.Label(body, text=_module_meta[module_key]['icon'], bg=_PANEL, fg=_GREEN, font=(hud._F, _sf(ic_f_size))).pack(side='left', padx=(0, 12))
            tk.Label(body, text=f"{_module_meta[module_key]['title']} — {_module_meta[module_key]['what']}", bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(side='left')

        # --- DEPENDENCY SECTION ---
        tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
        tk.Label(c_modules, text='Синхронизация зависимостей', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(8, 0))
        _dep_var = tk.StringVar(value='base')
        _dep_profiles = [
            ('base', 'LIGHT', 'Базовое ядро'),
            ('full', 'FULL', 'Полный пакет (ИИ + Игры)'),
            ('vision', 'VISION', 'Компьютерное зрение'),
            ('webqa', 'WEB/QA', 'Продвинутый ИИ-поиск')
        ]
        _dep_desc_map = {
            'base': 'LIGHT: Базовая синхронизация. Устанавливает только основное ядро системы, библиотеки распознавания речи и управления Windows. Минимально возможный размер установки.',
            'full': 'FULL: Полная синхронизация пакетов. Включает всё необходимое для игр (ETS2 / FS / Hogwarts), сложного ИИ-поиска и мультимедийных расширений. Рекомендуется для большинства пользователей.',
            'vision': 'VISION: Набор компьютерного зрения. Фокусируется на библиотеках для анализа игрового изображения (OpenCV), необходимых для авто-круиза и автоматизации в FS22/FS25.',
            'webqa': 'WEB/QA: Интеллектуальный веб-пакет. Устанавливает библиотеки для продвинутого поиска в интернете, парсинга данных и глубокого взаимодействия с LLM моделями.'
        }

        def _on_dep_change():
            _dep_desc_lbl.configure(text=_dep_desc_map.get(_dep_var.get(), ''))

        for val, title, sub in _dep_profiles:
            row = tk.Frame(c_modules, bg=_PANEL)
            row.pack(fill='x', pady=3, padx=(8, 0)) # Increased pady
            rb = ctk.CTkRadioButton(
                row, text='', variable=_dep_var, value=val, command=_on_dep_change, 
                fg_color=_CYAN, 
                radiobutton_width=hud._px(22), # Larger radio
                radiobutton_height=hud._px(22), 
                width=0
            )
            rb.pack(side='left', padx=(0, 8))
            lbl = tk.Label(row, text=f'{title} — {sub}', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w')
            lbl.pack(side='left', fill='x', expand=True)
            lbl.bind('<Button-1>', lambda e, v=val: (_dep_var.set(v), _on_dep_change()))
        
        _dep_desc_lbl = tk.Label(c_modules, text=_dep_desc_map['base'], bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w')
        _dep_desc_lbl.pack(fill='x', pady=(4, 0))

        def _upd_dep_wrap(e, l=_dep_desc_lbl):
            new_wl = max(hud._px(100), e.width - hud._px(20))
            l.configure(wraplength=new_wl)
        c_modules.bind('<Configure>', _upd_dep_wrap, add='+')
        
        _dep_status_lbl = tk.Label(c_modules, text='Готов к синхронизации.', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)), anchor='w')
        _dep_status_lbl.pack(fill='x', pady=(6,0))
        _dep_log_path = os.path.join('logs', 'dependency_install.log')
        _dep_install_running = {'busy': False, 'after_id': None}

        def _current_dep_target():
            inc = ['requirements-base.txt']; tid = _dep_var.get()
            if tid == 'full': inc.extend(['requirements-vision-game.txt', 'requirements-web-qa.txt'])
            elif tid == 'vision': inc.append('requirements-vision-game.txt')
            elif tid == 'webqa': inc.append('requirements-web-qa.txt')
            return {'id': tid, 'include_files': inc, 'remove_files': [f for f in ['requirements-vision-game.txt', 'requirements-web-qa.txt'] if f not in inc]}

        def _start_dep_sync(target, reason):
            if _dep_install_running['busy']: return
            _dep_install_running['busy'] = True; _dep_status_lbl.configure(text=f'Синхронизация ({reason})...', fg=_CYAN)
            def _worker():
                rc = 0
                try:
                    os.makedirs('logs', exist_ok=True)
                    with open(_dep_log_path, 'w', encoding='utf-8') as logf:
                        if target['remove_files']:
                            subprocess.Popen([sys.executable, '-m', 'pip', 'uninstall', '-y', '-r', target['remove_files'][0]], stdout=logf, stderr=subprocess.STDOUT).wait()
                        cmd = [sys.executable, '-m', 'pip', 'install']; [cmd.extend(['-r', f]) for f in target['include_files']]
                        rc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT).wait()
                except: rc = 1
                finally: 
                    _dep_install_running['busy'] = False
                    def _safe_upd():
                        try:
                            if _dep_status_lbl.winfo_exists():
                                _dep_status_lbl.configure(text='Готово.' if rc==0 else 'Ошибка.', fg=_GREEN if rc==0 else _RED)
                        except: pass
                    try: win.after(0, _safe_upd)
                    except: pass
            threading.Thread(target=_worker, daemon=True).start()

        def _schedule_auto_dep_sync(r):
            try:
                if _dep_install_running['after_id']: win.after_cancel(_dep_install_running['after_id'])
                _dep_install_running['after_id'] = win.after(1000, lambda: _start_dep_sync(_current_dep_target(), r))
            except: pass

        _dep_btn_row = tk.Frame(c_modules, bg=_PANEL); _dep_btn_row.pack(fill='x', pady=12)
        _hero_btn(_dep_btn_row, text='⚙ СИНХРОНИЗИРОВАТЬ', command=lambda: _start_dep_sync(_current_dep_target(), 'manual'), accent=_CYAN, hud=hud).pack(anchor='center', expand=True)

        # --- 2. БРИФИНГ ---
        c_brief = _card(inner, '☀', 'БРИФИНГ И «ЧТО СЕГОДНЯ»', _CYAN, hud)
        br = _settings.get('briefing', {})
        _brief_vars = {}
        def _save_briefing():
            d = _settings.get('briefing', {}); d.update({k: bool(v.get()) for k, v in _brief_vars.items()}); _settings['briefing'] = d; _save_hud_settings(_settings)

        br_meta = [('include_greeting', 'Приветствие'), ('include_time', 'Время'), ('include_weather', 'Погода'), ('include_battery', 'Батарея'), ('include_system_load', 'Нагрузка'), ('include_calendar', 'Календарь'), ('include_mail_unread', 'Почта')]
        for k, text in br_meta:
            row = tk.Frame(c_brief, bg=_PANEL)
            row.pack(fill='x', pady=3, padx=10) # Increased pady/padx
            v = tk.BooleanVar(value=br.get(k, True)); _brief_vars[k] = v
            ctk.CTkSwitch(
                row, text='', variable=v, 
                fg_color=_BRD_I, progress_color=_CYAN, button_color=_WHITE, 
                command=_save_briefing, 
                switch_width=hud._px(44), # Larger switch
                switch_height=hud._px(20), 
                width=0
            ).pack(side='left', padx=(0, 10))
            tk.Label(row, text=text, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11)), anchor='w').pack(side='left')

        # --- 3. ИНТЕЛЛЕКТ (LLM) — ПРЕМИУМ ДАШБОРД ---
        c_ai = _card(inner, '◉', 'ИНТЕЛЛЕКТ (LLM)', _CYAN, hud)
        
        _prov_meta = {
            'groq': {
                'name': 'Groq', 'icon': '⚡', 'url': 'https://console.groq.com/keys', 'key': 'GROQ_API_KEY',
                'models': {
                    'llama-3.3-70b-versatile': {'ctx': '128k', 'rpm': 30, 'rpd': 1000, 'alias': 'Универсальный эталон', 'power': '⚡⚡⚡⚡ 🧠🧠🧠'},
                    'llama-3.1-405b-reasoning': {'ctx': '128k', 'rpm': 30, 'rpd': 1000, 'alias': 'Масштабный разум (SOTA)', 'power': '⚡ 🧠🧠🧠🧠'},
                    'llama-3.1-8b-instant': {'ctx': '128k', 'rpm': 30, 'rpd': 14400, 'alias': 'Молниеносный чат', 'power': '⚡⚡⚡⚡⚡ 🧠'},
                    'mixtral-8x7b-32768': {'ctx': '32k', 'rpm': 30, 'rpd': 14400, 'alias': 'Стабильный и быстрый', 'power': '⚡⚡⚡ 🧠🧠'}
                }
            },
            'gemini': {
                'name': 'Gemini', 'icon': '♊', 'url': 'https://aistudio.google.com/app/apikey', 'key': 'GOOGLE_API_KEY',
                'models': {
                    'gemini-2.0-flash-exp': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Новое поколение (Ultra-Flash)', 'power': '⚡⚡⚡⚡⚡ 🧠🧠'},
                    'gemini-2.0-flash-thinking-exp': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Глубокое рассуждение', 'power': '⚡⚡ 🧠🧠🧠🧠'},
                    'gemini-1.5-pro-002': {'ctx': '2M', 'rpm': 2, 'rpd': 50, 'alias': 'Архивная память (Pro)', 'power': '⚡ 🧠🧠🧠🧠'},
                    'gemini-1.5-flash-002': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Скоростная работа', 'power': '⚡⚡⚡⚡ 🧠'}
                }
            },
            'anthropic': {
                'name': 'Claude', 'icon': '⦿', 'url': 'https://console.anthropic.com/', 'key': 'ANTHROPIC_API_KEY',
                'models': {
                    'claude-3-5-sonnet-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Лучший для текста и кода', 'power': '⚡⚡⚡ 🧠🧠🧠🧠'},
                    'claude-3-5-haiku-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Быстрый и точный', 'power': '⚡⚡⚡⚡ 🧠🧠'},
                    'claude-3-opus-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Философский интеллект', 'power': '⚡ 🧠🧠🧠🧠'}
                }
            },
            'deepseek': {
                'name': 'DeepSeek', 'icon': '◎', 'url': 'https://platform.deepseek.com/', 'key': 'DEEPSEEK_API_KEY',
                'models': {
                    'deepseek-chat': {'ctx': '128k', 'rpm': 60, 'rpd': 10000, 'alias': 'Мощный V3 (Универсал)', 'power': '⚡⚡⚡ 🧠🧠🧠'},
                    'deepseek-reasoner': {'ctx': '128k', 'rpm': 60, 'rpd': 10000, 'alias': 'Рассуждение на уровне o1', 'power': '⚡ 🧠🧠🧠🧠'}
                }
            },
            'openai': {
                'name': 'OpenAI', 'icon': '⚛', 'url': 'https://platform.openai.com/', 'key': 'OPENAI_API_KEY',
                'models': {
                    'gpt-4o': {'ctx': '128k', 'rpm': 10, 'rpd': 500, 'alias': 'Профессиональный стандарт', 'power': '⚡⚡⚡ 🧠🧠🧠🧠'},
                    'gpt-4o-mini': {'ctx': '128k', 'rpm': 10, 'rpd': 500, 'alias': 'Легкий и быстрый 4o', 'power': '⚡⚡⚡⚡ 🧠🧠'},
                    'o1-preview': {'ctx': '128k', 'rpm': 10, 'rpd': 100, 'alias': 'Космический разум (o1)', 'power': '⚡ 🧠🧠🧠🧠🧠'}
                }
            }
        }

        def _sec_path(): appdata = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA'); p = os.path.join(appdata, 'Jarvis', 'secrets.env') if appdata else '.env'; os.makedirs(os.path.dirname(p), exist_ok=True); return p
        def _rd_key(prov): 
            try:
                p, k = _sec_path(), _prov_meta[prov]['key']
                if os.path.exists(p):
                    for l in open(p,'r',encoding='utf-8'): 
                        if l.strip().startswith(f'{k}='): return l.split('=', 1)[1].strip().strip('"').strip("'")
            except: pass
            return ''

        _ai_prov_var = tk.StringVar(value=_settings.get('ai_provider', 'groq'))
        _ai_model_var = tk.StringVar(value=_settings.get('ai_model', 'llama-3.3-70b-versatile'))
        _stat_ctx = tk.StringVar(value='-'); _stat_rpm = tk.StringVar(value='-'); _stat_rpd = tk.StringVar(value='-')
        _stat_alias = tk.StringVar(value='-')

        # --- PROVIDER SELECT (CENTERED GRID) ---
        tk.Label(c_ai, text='ВЫБОР ПЛАТФОРМЫ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold')).pack(fill='x', anchor='w')
        _prov_list_outer = tk.Frame(c_ai, bg=_PANEL); _prov_list_outer.pack(fill='x', pady=(6, 12))
        _btn_refs = {}

        def _on_ai_upd(*_):
            p = _ai_prov_var.get(); _settings['ai_provider'] = p; m_list = list(_prov_meta[p]['models'].keys())
            if _ai_model_var.get() not in m_list: _ai_model_var.set(m_list[0])
            _ai_model_menu.configure(values=m_list); m = _ai_model_var.get(); _settings['ai_model'] = m; stats = _prov_meta[p]['models'][m]
            _stat_ctx.set(f"📚 {stats['ctx']}"); _stat_rpm.set(f"🏃 {stats['rpm']}/мин"); _stat_rpd.set(f"📅 {stats['rpd']} зап/день")
            _stat_alias.set(f"➜ {stats['alias']}")
            _ai_ent.delete(0, 'end'); _ai_ent.insert(0, _rd_key(p)); _save_hud_settings(_settings)
            for k, b in _btn_refs.items(): b.configure(fg_color=_blend(_CYAN, 0.22) if k == p else _blend(_CYAN, 0.04), border_color=_CYAN if k == p else _blend(_CYAN, 0.2))

        # Centered Rows Logic
        _p_ids = list(_prov_meta.keys())
        for i in range(0, len(_p_ids), 3):
            _row_f = tk.Frame(_prov_list_outer, bg=_PANEL)
            _row_f.pack(anchor='center', pady=2)
            for p_id in _p_ids[i:i+3]:
                info = _prov_meta[p_id]
                b = ctk.CTkButton(
                    _row_f, text=f"{info['icon']}  {info['name']}", 
                    command=lambda i=p_id: (_ai_prov_var.set(i), _on_ai_upd()), 
                    font=(hud._F, _sf(10), 'bold'), height=hud._px(42), 
                    width=hud._px(160), # Fixed width for consistent centering
                    corner_radius=10, border_width=1
                )
                b.pack(side='left', padx=4, pady=2)
                _btn_refs[p_id] = b

        # --- MODEL SELECT & INFO ---
        tk.Label(c_ai, text='ХАРАКТЕРИСТИКИ МОДЕЛИ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold')).pack(fill='x', anchor='w', pady=(5,0))
        alias_lbl = tk.Label(c_ai, textvariable=_stat_alias, bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(11), 'bold'), anchor='w')
        alias_lbl.pack(fill='x', pady=(2, 8))

        stats_f = tk.Frame(c_ai, bg=_PANEL); stats_f.pack(fill='x', pady=(0, 10))
        for i, (l, v) in enumerate([('ПАМЯТЬ', _stat_ctx), ('ТЕМП', _stat_rpm), ('ЛИМИТ', _stat_rpd)]):
            cell = tk.Frame(stats_f, bg=_blend(_CYAN, 0.05), highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1); cell.pack(side='left', expand=True, fill='both', padx=3)
            tk.Label(cell, text=l, bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(7), 'bold')).pack(pady=(5,0))
            tk.Label(cell, textvariable=v, bg=_PANEL, fg=_WHITE, font=(hud._F, _sf(10), 'bold')).pack(pady=(0,5))

        # --- CUSTOM MODEL LIST ---
        tk.Label(c_ai, text='КАТАЛОГ МОДЕЛЕЙ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold')).pack(fill='x', anchor='w')
        _ai_model_menu = _HUDDropdown(hud, c_ai, list(_prov_meta[_ai_prov_var.get()]['models'].keys()), _ai_model_var, command=_on_ai_upd, accent=_CYAN)
        _ai_model_menu.frame.pack(fill='x', pady=(4, 12))

        # --- KEY & ACTIONS ---
        _ai_ent = ctk.CTkEntry(c_ai, placeholder_text='Вставьте ваш ключ API здесь...', font=(hud._F, _sf(11)), show='•', height=hud._px(48), fg_color='#0b0e14', border_color=_blend(_CYAN, 0.3), corner_radius=10); _ai_ent.pack(fill='x', pady=(0,10))
        _add_context_menu(win, _ai_ent, hud, _sf)

        btn_g = tk.Frame(c_ai, bg=_PANEL); btn_g.pack(fill='x')
        for i in range(3): btn_g.columnconfigure(i, weight=1)
        _std_action_btn(btn_g, text='🌐 САЙТ', command=lambda: subprocess.Popen(['cmd', '/c', 'start', _prov_meta[_ai_prov_var.get()]['url']]), accent=_CYAN, hud=hud, row=0, column=0, sticky='ew', padx=(0,3))
        _std_action_btn(btn_g, text='📋 ВСТАВИТЬ', command=lambda: (_ai_ent.delete(0, 'end'), _ai_ent.insert(0, win.clipboard_get().strip())), accent=_CYAN, hud=hud, row=0, column=1, sticky='ew', padx=(3,3))
        def _save_key():
            try:
                p, k, v = _sec_path(), _prov_meta[_ai_prov_var.get()]['key'], _ai_ent.get().strip()
                lines = open(p,'r',encoding='utf-8').read().splitlines() if os.path.exists(p) else []
                with open(p,'w',encoding='utf-8') as f:
                    wrote = False
                    for l in lines:
                        if l.strip().startswith(f'{k}='): f.write(f'{k}="{v}"\n'); wrote = True
                        else: f.write(f'{l}\n')
                    if not wrote: f.write(f'{k}="{v}"\n')
                hud.show_msg('Ключ сохранен', _GREEN)
            except: hud.show_msg('Ошибка доступа', _RED)
        _std_action_btn(btn_g, text='💾 СОХРАНИТЬ', command=_save_key, accent=_CYAN, hud=hud, row=0, column=2, sticky='ew', padx=(3,0))

        _on_ai_upd(); _refresh_load_summary()

    except Exception as e:
        import traceback; traceback.print_exc()
        tk.Label(inner, text=f"ERROR: {e}", bg=_BG, fg=_RED).pack()
