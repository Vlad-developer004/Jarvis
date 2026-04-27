from ui.hud_style import JStyle
import os, sys, threading, time, subprocess
import tkinter as tk
import customtkinter as ctk
from .base import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _card, _hint, _blend, _std_action_btn, _hero_btn, _add_context_menu, _slider, _label_row, _HUDDropdown

def build_modules_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
    
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
            rb = ctk.CTkRadioButton(row, text='', variable=_feature_profile_var, value=val, fg_color=_GREEN, radiobutton_width=20, radiobutton_height=20, command=_apply_feature_profile, width=0)
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
            'qa': {'title': 'ИИ / QA', 'icon': '◉', 'what': 'Сложные вопросы через LLM.', 'weight': 3},
            'games': {'title': 'Игровой модуль', 'icon': '✦', 'what': 'Игровой режим и профили.', 'weight': 4},
            'cinema': {'title': 'Кино модуль', 'icon': '▶', 'what': 'Медиа-автоматизация.', 'weight': 1},
            'system_monitoring': {'title': 'Системный мониторинг', 'icon': '▦', 'what': 'Метрики в HUD.', 'weight': 3},
            'battery_monitor': {'title': 'Монитор батареи', 'icon': '▣', 'what': 'Отслеживание питания.', 'weight': 1},
            'lag_hunter': {'title': 'Lag Hunter', 'icon': '⟳', 'what': 'Анализ задержек.', 'weight': 2},
            'morning_briefing': {'title': 'Утренний брифинг', 'icon': '☀', 'what': 'Сводка при старте.', 'weight': 1},
            'updater': {'title': 'Автообновления', 'icon': '⬡', 'what': 'Автоматический апдейтер.', 'weight': 1},
            'network_profiles': {'title': 'Сеть: профили', 'icon': '◎', 'what': 'Профили и VPN.', 'weight': 1},
            'system_health': {'title': 'Система: диски', 'icon': '▤', 'what': 'Отчет по дискам.', 'weight': 1},
            'calendar_ics': {'title': 'Календарь ICS', 'icon': '🗓', 'what': 'События календаря.', 'weight': 1},
            'inbox_digest': {'title': 'Почта', 'icon': '✉', 'what': 'Проверка почты.', 'weight': 1},
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
            row.pack(fill='x', pady=2)
            body = tk.Frame(row, bg=_PANEL)
            body.pack(fill='x', padx=10, pady=6)
            
            var = tk.BooleanVar(value=_effective_module_value(module_key))
            _module_switch_vars[module_key] = var
            
            ctk.CTkSwitch(
                body, text='', variable=var, 
                fg_color=_BRD_I, progress_color=_GREEN, button_color=_WHITE, 
                command=lambda k=module_key, v=var: _on_module_toggle(k, v), 
                switch_width=44, switch_height=20, width=0
            ).pack(side='left', padx=(0, 12))
            
            ic_f_size = 14 if module_key == 'calendar_ics' else 18
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
            'base': 'LIGHT: Устанавливает только основное ядро системы. Минимальный размер.',
            'full': 'FULL: Включает всё необходимое для игр, ИИ-поиска и медиа.',
            'vision': 'VISION: Библиотеки (OpenCV) для анализа игрового изображения.',
            'webqa': 'WEB/QA: Интеллектуальный веб-пакет для парсинга и взаимодействия с LLM.'
        }

        _dep_info_frame = tk.Frame(c_modules, bg=_blend(_CYAN, 0.04), highlightbackground=_blend(_CYAN, 0.1), highlightthickness=1)
        _dep_info_frame.pack(fill='x', pady=(10, 5), padx=2)
        _dep_header = tk.Frame(_dep_info_frame, bg=_blend(_CYAN, 0.04))
        _dep_header.pack(fill='x', padx=12, pady=(8, 4))
        
        tk.Label(_dep_header, text='СТАТУС:', bg=_blend(_CYAN, 0.04), fg=_CYAN, font=(hud._F, _sf(8), 'bold')).pack(side='left')
        _dep_current_val_lbl = tk.Label(_dep_header, text='LIGHT', bg=_blend(_CYAN, 0.04), fg=_WHITE, font=(hud._F, _sf(11), 'bold'))
        _dep_current_val_lbl.pack(side='left', padx=8)
        
        _dep_sync_indicator = tk.Label(_dep_header, text='● СИНХРОНИЗИРОВАНО', bg=_blend(_CYAN, 0.04), fg=_GREEN, font=(hud._F, _sf(8), 'bold'))
        _dep_sync_indicator.pack(side='left', padx=12)

        def _on_dep_change():
            target_id = _dep_var.get()
            title = 'LIGHT'
            for v, t, s in _dep_profiles:
                if v == target_id: title = t; break
            _dep_current_val_lbl.configure(text=title)
            _dep_desc_lbl.configure(text=_dep_desc_map.get(target_id, ''))
        
        _dep_desc_lbl = tk.Label(c_modules, text=_dep_desc_map['base'], bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w')
        _dep_desc_lbl.pack(fill='x', pady=(4, 0))

        def _upd_dep_wrap(e, l=_dep_desc_lbl):
            new_wl = max(hud._px(100), e.width - hud._px(20))
            l.configure(wraplength=new_wl)
        c_modules.bind('<Configure>', _upd_dep_wrap, add='+')
        
        _dep_status_lbl = tk.Label(_dep_info_frame, text='Все зависимости установлены.', bg=_blend(_CYAN, 0.04), fg=_DIM, font=(hud._F, _sf(9)), anchor='w')
        _dep_status_lbl.pack(fill='x', padx=12, pady=(0, 10))
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
            _dep_install_running['busy'] = True
            _dep_sync_indicator.configure(text='● ОБНОВЛЕНИЕ...', fg=_AMBER)
            _dep_status_lbl.configure(text=f'Выполняется синхронизация ({reason})...', fg=_CYAN)
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
                                _dep_sync_indicator.configure(text='● СИНХРОНИЗИРОВАНО' if rc==0 else '● ОШИБКА', fg=_GREEN if rc==0 else _RED)
                                _dep_status_lbl.configure(text='Готово. Все компоненты актуальны.' if rc==0 else 'Ошибка при установке.', fg=_GREEN if rc==0 else _RED)
                        except: pass
                    try: win.after(0, _safe_upd)
                    except: pass
            threading.Thread(target=_worker, daemon=True).start()

        def _schedule_auto_dep_sync(r):
            try:
                if _dep_install_running['after_id']: win.after_cancel(_dep_install_running['after_id'])
                _dep_install_running['after_id'] = win.after(1000, lambda: _start_dep_sync(_current_dep_target(), r))
            except: pass
        _on_dep_change()

        # --- 2. БРИФИНГ ---
        c_brief = _card(inner, '☀', 'БРИФИНГ И «ЧТО СЕГОДНЯ»', _CYAN, hud)
        br = _settings.get('briefing', {})
        _brief_vars = {}
        def _save_briefing():
            d = _settings.get('briefing', {}); d.update({k: bool(v.get()) for k, v in _brief_vars.items()}); _settings['briefing'] = d; _save_hud_settings(_settings)

        br_meta = [('include_greeting', 'Приветствие'), ('include_time', 'Время'), ('include_weather', 'Погода'), ('include_battery', 'Батарея'), ('include_system_load', 'Нагрузка'), ('include_calendar', 'Календарь'), ('include_mail_unread', 'Почта')]
        for k, text in br_meta:
            row = tk.Frame(c_brief, bg=_PANEL)
            row.pack(fill='x', pady=3, padx=10)
            v = tk.BooleanVar(value=br.get(k, True)); _brief_vars[k] = v
            ctk.CTkSwitch(
                row, text='', variable=v, 
                fg_color=_BRD_I, progress_color=_CYAN, button_color=_WHITE, 
                command=_save_briefing, switch_width=44, switch_height=20, width=0
            ).pack(side='left', padx=(0, 10))
            tk.Label(row, text=text, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11)), anchor='w').pack(side='left')

        # --- 3. ИНТЕЛЛЕКТ (LLM) — ПРЕМИУМ ДАШБОРД ---
        c_ai = _card(inner, '◉', 'ИНТЕЛЛЕКТ (LLM)', _CYAN, hud)
        ai_container = tk.Frame(c_ai, bg=_PANEL)
        ai_container.pack(fill='x', padx=15, pady=(5, 10))
        
        _prov_meta = {
            'groq': {
                'name': 'Groq', 'icon': '⚡', 'url': 'https://console.groq.com/keys', 'key': 'GROQ_API_KEY',
                'models': {
                    'llama-3.3-70b-versatile': {'ctx': '128k', 'rpm': 30, 'rpd': 1000, 'alias': 'Универсальный эталон'},
                    'deepseek-r1-distill-llama-70b': {'ctx': '128k', 'rpm': 30, 'rpd': 1000, 'alias': 'Рассуждение (R1-Distill)'},
                    'llama-3.1-8b-instant': {'ctx': '128k', 'rpm': 30, 'rpd': 14400, 'alias': 'Молниеносный чат'},
                    'mixtral-8x7b-32768': {'ctx': '32k', 'rpm': 30, 'rpd': 14400, 'alias': 'Стабильный и быстрый'}
                }
            },
            'gemini': {
                'name': 'Gemini', 'icon': '♊', 'url': 'https://aistudio.google.com/app/apikey', 'key': 'GOOGLE_API_KEY',
                'models': {
                    'gemini-2.0-flash-exp': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Новое поколение (Flash)'},
                    'gemini-2.0-flash-thinking-exp': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Глубокое рассуждение'},
                    'gemini-1.5-pro-002': {'ctx': '2M', 'rpm': 2, 'rpd': 50, 'alias': 'Архивная память (Pro)'},
                    'gemini-1.5-flash-002': {'ctx': '1M', 'rpm': 15, 'rpd': 1500, 'alias': 'Скоростная работа'}
                }
            },
            'anthropic': {
                'name': 'Claude', 'icon': '⦿', 'url': 'https://console.anthropic.com/', 'key': 'ANTHROPIC_API_KEY',
                'models': {
                    'claude-3-5-sonnet-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Лучший для текста и кода'},
                    'claude-3-5-haiku-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Быстрый и точный'},
                    'claude-3-opus-latest': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Философский интеллект'}
                }
            },
            'deepseek': {
                'name': 'DeepSeek', 'icon': '◎', 'url': 'https://platform.deepseek.com/', 'key': 'DEEPSEEK_API_KEY',
                'models': {
                    'deepseek-chat': {'ctx': '128k', 'rpm': 60, 'rpd': 10000, 'alias': 'Мощный V3 (Универсал)'},
                    'deepseek-reasoner': {'ctx': '128k', 'rpm': 60, 'rpd': 10000, 'alias': 'Рассуждение на уровне o1'}
                }
            },
            'openai': {
                'name': 'OpenAI', 'icon': '⚛', 'url': 'https://platform.openai.com/', 'key': 'OPENAI_API_KEY',
                'models': {
                    'gpt-4o': {'ctx': '128k', 'rpm': 10, 'rpd': 500, 'alias': 'Профессиональный стандарт'},
                    'gpt-4o-mini': {'ctx': '128k', 'rpm': 10, 'rpd': 500, 'alias': 'Легкий и быстрый 4o'},
                    'o1-preview': {'ctx': '128k', 'rpm': 10, 'rpd': 100, 'alias': 'Космический разум (o1)'}
                }
            },
            'openrouter': {
                'name': 'OpenRouter', 'icon': '🚀', 'url': 'https://openrouter.ai/keys', 'key': 'OPENROUTER_API_KEY',
                'models': {
                    'deepseek/deepseek-chat': {'ctx': '128k', 'rpm': 10, 'rpd': 500, 'alias': 'DeepSeek V3 (Экономичный)'},
                    'anthropic/claude-3.5-sonnet': {'ctx': '200k', 'rpm': 5, 'rpd': 100, 'alias': 'Claude 3.5 Sonnet'},
                    'openai/o3-mini': {'ctx': '128k', 'rpm': 10, 'rpd': 100, 'alias': 'OpenAI o3-mini (Рассуждение)'}
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

        # --- 1. АДАПТИВНАЯ СЕТКА ПРОВАЙДЕРОВ (КРУПНЫЕ ПЛАТФОРМЫ) ---
        tk.Label(ai_container, text='ВЫБОР ПЛАТФОРМЫ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x')
        _prov_list_outer = tk.Frame(ai_container, bg=_PANEL)
        _prov_list_outer.pack(fill='x', pady=(4, 10))
        _btn_refs = {}

        def _on_ai_upd(*_):
            p = _ai_prov_var.get(); _settings['ai_provider'] = p; m_list = list(_prov_meta[p]['models'].keys())
            if _ai_model_var.get() not in m_list: _ai_model_var.set(m_list[0])
            _ai_model_menu.configure(values=m_list); m = _ai_model_var.get(); _settings['ai_model'] = m; stats = _prov_meta[p]['models'][m]
            
            _stat_ctx.set(stats['ctx'])
            _stat_rpm.set(f"{stats['rpm']}/мин")
            _stat_rpd.set(f"{stats['rpd']} зап/день")
            _stat_alias.set(f"➜ {stats['alias']}")
            
            _ai_ent.delete(0, 'end'); _ai_ent.insert(0, _rd_key(p)); _save_hud_settings(_settings)
            
            from ui.hud_themes import get_current_theme_name
            _theme = get_current_theme_name()
            for k, b in _btn_refs.items():
                is_p = (k == p)
                unsel_alpha = 0.08 if _theme == 'light' else 0.05
                sel_alpha   = 0.30 if _theme == 'light' else 0.22
                try:
                    b.configure(
                        fg_color=_blend(_CYAN, sel_alpha) if is_p else _blend(_CYAN, unsel_alpha),
                        border_color=_CYAN if is_p else _blend(_CYAN, 0.18),
                        border_width=2 if is_p else 1,
                        text_color=_WHITE if is_p else _TEXT
                    )
                except: pass

        _p_ids = list(_prov_meta.keys())
        _last_grid_w = [0]

        # Умная динамическая сетка платформ
        def _rebuild_prov_grid(e=None):
            try:
                curr_w = ai_container.winfo_width()
                if curr_w < 50: return 
                if abs(curr_w - _last_grid_w[0]) < 5: return 
                _last_grid_w[0] = curr_w

                for child in _prov_list_outer.winfo_children(): child.destroy()
                _btn_refs.clear()

                from ui.hud_themes import get_current_theme_name
                _theme = get_current_theme_name()
                unsel_alpha = 0.08 if _theme == 'light' else 0.05
                sel_alpha   = 0.30 if _theme == 'light' else 0.22

                PAD = 4 # Вернули чуть больше отступа для читаемости
                btn_min_w = hud._px(120) 
                safe_w = curr_w - hud._px(20)
                
                cols = max(1, int(safe_w // (btn_min_w + PAD * 2)))
                cols = min(3, cols, len(_p_ids)) # Ограничили до 3 в ряд для стабильности
                rows = [_p_ids[i:i + cols] for i in range(0, len(_p_ids), cols)]

                # Сетка на Grid для идеально равных колонок
                for i in range(cols): _prov_list_outer.columnconfigure(i, weight=1)

                for i, p_id in enumerate(_p_ids):
                    r, c = divmod(i, cols)
                    info = _prov_meta[p_id]
                    is_p = (p_id == _ai_prov_var.get())
                    
                    b = ctk.CTkButton(
                        _prov_list_outer,
                        text=f"{info['icon']}  {info['name']}",
                        command=lambda pid=p_id: (_ai_prov_var.set(pid), _on_ai_upd()),
                        font=(hud._F, _sf(7), 'bold'),
                        height=hud._px(30),
                        width=0, # Grid с weight=1 сам определит ширину
                        corner_radius=6,
                        border_width=1,
                        anchor='center',
                        fg_color=_blend(_CYAN, sel_alpha) if is_p else _blend(_CYAN, unsel_alpha),
                        border_color=_CYAN if is_p else _blend(_CYAN, 0.12),
                        hover_color=_blend(_CYAN, 0.18),
                        text_color=_WHITE if is_p else _TEXT,
                    )
                    b.grid(row=r, column=c, sticky='ew', padx=PAD, pady=2)
                    _btn_refs[p_id] = b
            except Exception: pass

        ai_container.bind('<Configure>', _rebuild_prov_grid)

        # --- 2. СТАТИСТИКА (ШИРОКИЕ И КРУПНЫЕ КАРТОЧКИ) ---
        tk.Label(ai_container, text='ХАРАКТЕРИСТИКИ МОДЕЛИ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x', pady=(5,0))
        alias_lbl = tk.Label(ai_container, textvariable=_stat_alias, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(12), 'bold'), anchor='center')
        alias_lbl.pack(fill='x', pady=(2, 10))

        stats_f = tk.Frame(ai_container, bg=_PANEL)
        stats_f.pack(fill='x', pady=(0, 10))
        
        _stat_cells_frame = tk.Frame(stats_f, bg=_PANEL)
        _stat_cells_frame.pack(fill='x')

        def _rebuild_stats_grid(e=None):
            try:
                curr_w = ai_container.winfo_width()
                if curr_w < 50: return
                for child in _stat_cells_frame.winfo_children(): child.destroy()
                
                # Адаптивность: 3 в ряд если широко, иначе 2+1 или 1+1+1
                cell_min_w = hud._px(140)
                cols = max(1, int(curr_w // (cell_min_w + 10)))
                cols = min(3, cols)
                
                items = [('ПАМЯТЬ', _stat_ctx), ('ТЕМП', _stat_rpm), ('ЛИМИТ', _stat_rpd)]
                _stat_icons = {'ПАМЯТЬ': '📚', 'ТЕМП': '🏃', 'ЛИМИТ': '📅'}
                
                for i, (l, v) in enumerate(items):
                    r, c = divmod(i, cols)
                    cell = ctk.CTkFrame(_stat_cells_frame, fg_color=_blend(_CYAN, 0.04), border_color=_blend(_CYAN, 0.1), border_width=1, corner_radius=6)
                    cell.grid(row=r, column=c, sticky='ew', padx=3, pady=2)
                    _stat_cells_frame.columnconfigure(c, weight=1)
                    
                    ctk.CTkLabel(cell, text=l, text_color=_CYAN, font=(hud._F, _sf(2), 'bold'), bg_color='transparent').pack(pady=(2, 0), padx=8)
                    val_f = tk.Frame(cell, bg=_blend(_CYAN, 0.04))
                    val_f.pack(pady=(0, 2), padx=8) 
                    ctk.CTkLabel(val_f, text=_stat_icons[l], text_color=_CYAN, font=(hud._F, _sf(5)), bg_color='transparent').pack(side='left', padx=(0, 4))
                    ctk.CTkLabel(val_f, textvariable=v, text_color=_WHITE, font=(hud._F, _sf(4), 'bold'), bg_color='transparent').pack(side='left')
            except: pass

        ai_container.bind('<Configure>', lambda e: (_rebuild_prov_grid(e), _rebuild_stats_grid(e)), add='+')

        # --- 3. КАТАЛОГ И КЛЮЧИ ---
        tk.Label(ai_container, text='КАТАЛОГ МОДЕЛЕЙ', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x', pady=(5, 0))
        _ai_model_menu = _HUDDropdown(hud, ai_container, list(_prov_meta[_ai_prov_var.get()]['models'].keys()), _ai_model_var, command=_on_ai_upd, accent=_CYAN)
        _ai_model_menu.frame.pack(fill='x', pady=(4, 12))

        _ai_ent = ctk.CTkEntry(ai_container, placeholder_text='Вставьте ваш ключ API здесь...', font=(hud._F, 11), show='•', height=32, fg_color=_BG, border_color=_blend(_CYAN, 0.3), corner_radius=8)
        _ai_ent.pack(fill='x', pady=(0, 10)) # УМЕНЬШЕНО: Компактное поле ввода
        _add_context_menu(win, _ai_ent, hud, _sf)

        # --- 4. МЕЛКИЕ КНОПКИ ДЕЙСТВИЙ ВНИЗУ ---
        btn_g = tk.Frame(ai_container, bg=_PANEL)
        btn_g.pack(fill='x')
        for i in range(3): btn_g.columnconfigure(i, weight=1)
        
        def _mini_btn(parent, text, col, cmd, c):
            ctk.CTkButton(
                parent, text=text, command=cmd, height=35, font=(hud._F, 12, 'bold'), # УМЕНЬШЕНО: Высота 30, шрифт 10
                fg_color=_blend(col, 0.08), hover_color=_blend(col, 0.18), text_color=col,
                border_color=_blend(col, 0.3), border_width=1, corner_radius=6
            ).grid(row=0, column=c, sticky='ew', padx=4)

        _mini_btn(btn_g, '🌐 САЙТ', _CYAN, lambda: subprocess.Popen(['cmd', '/c', 'start', _prov_meta[_ai_prov_var.get()]['url']]), 0)
        _mini_btn(btn_g, '📋 ВСТАВИТЬ', _CYAN, lambda: (_ai_ent.delete(0, 'end'), _ai_ent.insert(0, win.clipboard_get().strip())), 1)
        
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
            
        _mini_btn(btn_g, '💾 СОХРАНИТЬ', _GREEN, _save_key, 2)

        _on_ai_upd(); _refresh_load_summary()

    except Exception as e:
        import traceback; traceback.print_exc()
        tk.Label(inner, text=f"ERROR: {e}", bg=_BG, fg=_RED).pack()