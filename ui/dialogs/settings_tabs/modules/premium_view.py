from ui.hud_style import JStyle
from core import i18n
import os, sys, threading, time, subprocess
import tkinter as tk
import customtkinter as ctk
from .base import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _card, _hint, _blend, _std_action_btn, _hero_btn, _add_context_menu, _slider, _label_row, _HUDDropdown
from .constants import _AI_CONFIG

def _build_prov_meta():
    _icons = {'Groq': '⚡', 'OpenAI': '◆', 'Google': '♊', 'DeepSeek': '◎', 'Anthropic': '✦', 'OpenRouter': '⬡'}
    _id_map = {'Groq': 'groq', 'OpenAI': 'openai', 'Google': 'gemini', 'DeepSeek': 'deepseek', 'Anthropic': 'anthropic', 'OpenRouter': 'openrouter'}
    out = {}
    for pname, pdata in _AI_CONFIG.items():
        pid = _id_map.get(pname, pname.lower())
        out[pid] = {
            'name': pname,
            'icon': _icons.get(pname, '◉'),
            'url': pdata['site'],
            'key': pdata['env'],
            'models': {m: {'ctx': v['ctx'], 'rpm': v['rpm'], 'rpd': v['rpd'], 'alias': v['desc']} for m, v in pdata['models'].items()}
        }
    return out

def build_modules_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)
    
    _settings = getattr(hud, '_settings', {})
    if not isinstance(_settings, dict): _settings = {}

    try:
        c_modules = _card(inner, '🧩', i18n.tr('premium.modules_profiles_title'), _GREEN, hud)
        c_modules.master.pack_forget()
        c_modules.master.pack(fill='x', padx=20, pady=(0, 0))
        _hint(c_modules, i18n.tr('premium.modules_profiles_hint'), hud)
        
        _feature_profile_var = tk.StringVar(value=str(_settings.get('feature_profile', 'minimal')))
        _feature_status_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)))
        _feature_desc_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w')
        _feature_desc_lbl.pack(fill='x', pady=(4, 0))
        
        _feature_presets = {
            'full': {'games': True, 'qa': True, 'cinema': True, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': True, 'morning_briefing': True, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False},
            'assistant': {'games': False, 'qa': False, 'cinema': False, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': False, 'morning_briefing': False, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False},
            'minimal': {'games': False, 'qa': False, 'cinema': False, 'system_monitoring': False, 'battery_monitor': False, 'lag_hunter': False, 'morning_briefing': False, 'updater': False, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False}
        }
        _feature_desc_map = {
            'full': i18n.tr('premium.profile_full_desc'),
            'assistant': i18n.tr('premium.profile_assistant_desc'),
            'minimal': i18n.tr('premium.profile_minimal_desc')
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
            _feature_status_lbl.configure(text=i18n.tr('premium.profile_saved_msg'), fg=_AMBER)
            _refresh_module_switches_from_profile(); _refresh_load_summary(); _schedule_auto_dep_sync('profile-change')
            try: from core.system import refresh_module_flags; refresh_module_flags()
            except Exception: pass

        _feature_options = [
            ('full', 'FULL', i18n.tr('premium.profile_full_short')),
            ('assistant', 'ASSISTANT', i18n.tr('premium.profile_assistant_short')),
            ('minimal', 'MINIMAL', i18n.tr('premium.profile_minimal_short'))
        ]
        for val, title, sub in _feature_options:
            row = tk.Frame(c_modules, bg=_PANEL); row.pack(fill='x', pady=(2, 0), padx=(8, 0))
            rb = ctk.CTkRadioButton(row, text='', variable=_feature_profile_var, value=val, fg_color=_GREEN, radiobutton_width=18, radiobutton_height=18, command=_apply_feature_profile, width=0)
            rb.pack(side='left', padx=(0, 6))
            lbl = tk.Label(row, text=f'{title} — {sub}', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w'); lbl.pack(side='left', fill='x', expand=True); lbl.bind('<Button-1>', lambda e, v=val: (_feature_profile_var.set(v), _apply_feature_profile()))
        _feature_desc_lbl.configure(text=_feature_desc_map.get(_feature_profile_var.get(), _feature_desc_map['minimal']))
        _feature_status_lbl.pack(fill='x', pady=(6, 0))

        def _upd_desc_wrap(e, l=_feature_desc_lbl): l.configure(wraplength=max(hud._px(100), e.width - hud._px(20)))
        c_modules.bind('<Configure>', _upd_desc_wrap, add='+')

        tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
        tk.Label(c_modules, text=i18n.tr('premium.modules_detailed_title'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(8, 0))
        
        _module_meta = {
            'qa': {'title': i18n.tr('premium.module_qa_title'), 'icon': '◉', 'what': i18n.tr('premium.module_qa_desc'), 'weight': 3},
            'games': {'title': i18n.tr('premium.module_games_title'), 'icon': '✦', 'what': i18n.tr('premium.module_games_desc'), 'weight': 4},
            'cinema': {'title': i18n.tr('premium.module_cinema_title'), 'icon': '▶', 'what': i18n.tr('premium.module_cinema_desc'), 'weight': 1},
            'system_monitoring': {'title': i18n.tr('premium.module_monitoring_title'), 'icon': '▦', 'what': i18n.tr('premium.module_monitoring_desc'), 'weight': 3},
            'battery_monitor': {'title': i18n.tr('premium.module_battery_title'), 'icon': '▣', 'what': i18n.tr('premium.module_battery_desc'), 'weight': 1},
            'lag_hunter': {'title': i18n.tr('premium.module_lag_hunter_title'), 'icon': '⟳', 'what': i18n.tr('premium.module_lag_hunter_desc'), 'weight': 2},
            'morning_briefing': {'title': i18n.tr('premium.module_briefing_title'), 'icon': '☀', 'what': i18n.tr('premium.module_briefing_desc'), 'weight': 1},
            'updater': {'title': i18n.tr('premium.module_updater_title'), 'icon': '⬡', 'what': i18n.tr('premium.module_updater_desc'), 'weight': 1},
            'network_profiles': {'title': i18n.tr('premium.module_network_title'), 'icon': '◎', 'what': i18n.tr('premium.module_network_desc'), 'weight': 1},
            'system_health': {'title': i18n.tr('premium.module_health_title'), 'icon': '▤', 'what': i18n.tr('premium.module_health_desc'), 'weight': 1},
            'calendar_ics': {'title': i18n.tr('premium.module_calendar_title'), 'icon': '🗓', 'what': i18n.tr('premium.module_calendar_desc'), 'weight': 1},
            'inbox_digest': {'title': i18n.tr('premium.module_mail_title'), 'icon': '✉', 'what': i18n.tr('premium.module_mail_desc'), 'weight': 1},
        }
        _module_order = list(_module_meta.keys()); _module_switch_vars = {}
        _module_load_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_CYAN, font=(hud._F, _sf(9), 'bold'), anchor='w'); _module_load_lbl.pack(fill='x', pady=(4, 2))
        
        def _refresh_load_summary():
            score = sum(int(_module_meta.get(k,{}).get('weight',1)) for k in _module_order if _module_switch_vars.get(k) and _module_switch_vars[k].get())
            if score <= 4:
                level, col = i18n.tr('premium.load_low'), _GREEN
            elif score <= 9:
                level, col = i18n.tr('premium.load_medium'), _AMBER
            else:
                level, col = i18n.tr('premium.load_high'), _RED
            _module_load_lbl.configure(text=f'JARVIS LOAD PROFILE: {level} (Score: {score})', fg=col)

        def _on_module_toggle(k, var):
            _feature_modules_overrides[k] = bool(var.get()); _settings['feature_modules'] = _feature_modules_overrides; _save_hud_settings(_settings); _refresh_load_summary()
            qa_on = _module_switch_vars.get('qa') and _module_switch_vars['qa'].get(); gm_on = _module_switch_vars.get('games') and _module_switch_vars['games'].get()
            if qa_on and gm_on: _dep_var.set('full')
            elif qa_on: _dep_var.set('webqa')
            elif gm_on: _dep_var.set('vision')
            else: _dep_var.set('base')
            _on_dep_change(); _schedule_auto_dep_sync('module-toggle')
            try: from core.system import refresh_module_flags; refresh_module_flags()
            except: pass

        for module_key in _module_order:
            row = tk.Frame(c_modules, bg=_PANEL, highlightbackground=_blend(_GREEN, 0.15), highlightthickness=1)
            row.pack(fill='x', pady=1)
            body = tk.Frame(row, bg=_PANEL); body.pack(fill='x', padx=8, pady=4)
            var = tk.BooleanVar(value=_effective_module_value(module_key)); _module_switch_vars[module_key] = var
            ctk.CTkSwitch(body, text='', variable=var, fg_color=_BRD_I, progress_color=_GREEN, button_color=_WHITE, command=lambda k=module_key, v=var: _on_module_toggle(k, v), switch_width=40, switch_height=18, width=0).pack(side='left', padx=(0, 10))
            tk.Label(body, text=_module_meta[module_key]['icon'], bg=_PANEL, fg=_GREEN, font=(hud._F, _sf(14))).pack(side='left', padx=(0, 10))
            tk.Label(body, text=f"{_module_meta[module_key]['title']} — {_module_meta[module_key]['what']}", bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(side='left')

        tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(8, 0))
        tk.Label(c_modules, text=i18n.tr('premium.dependencies_title'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(6, 0))
        _dep_var = tk.StringVar(value='base')
        _dep_profiles = [
            ('base', 'LIGHT', i18n.tr('premium.dep_base_desc')),
            ('full', 'FULL', i18n.tr('premium.dep_full_desc')),
            ('vision', 'VISION', i18n.tr('premium.dep_vision_desc')),
            ('webqa', 'WEB/QA', i18n.tr('premium.dep_webqa_desc'))
        ]
        _dep_desc_map = {
            'base': i18n.tr('premium.dep_base_detail'),
            'full': i18n.tr('premium.dep_full_detail'),
            'vision': i18n.tr('premium.dep_vision_detail'),
            'webqa': i18n.tr('premium.dep_webqa_detail')
        }
        _dep_info_frame = tk.Frame(c_modules, bg=_blend(_CYAN, 0.04), highlightbackground=_blend(_CYAN, 0.1), highlightthickness=1); _dep_info_frame.pack(fill='x', pady=(6, 4), padx=2)
        _dep_header = tk.Frame(_dep_info_frame, bg=_blend(_CYAN, 0.04)); _dep_header.pack(fill='x', padx=10, pady=(6, 2))
        tk.Label(_dep_header, text=i18n.tr('premium.dep_status_label'), bg=_blend(_CYAN, 0.04), fg=_CYAN, font=(hud._F, _sf(8), 'bold')).pack(side='left')
        _dep_current_val_lbl = tk.Label(_dep_header, text='LIGHT', bg=_blend(_CYAN, 0.04), fg=_WHITE, font=(hud._F, _sf(11), 'bold')); _dep_current_val_lbl.pack(side='left', padx=6)
        _dep_sync_indicator = tk.Label(_dep_header, text=i18n.tr('premium.dep_synced'), bg=_blend(_CYAN, 0.04), fg=_GREEN, font=(hud._F, _sf(8), 'bold')); _dep_sync_indicator.pack(side='left', padx=10)

        def _on_dep_change():
            target_id = _dep_var.get(); title = 'LIGHT'
            for v, t, s in _dep_profiles:
                if v == target_id: title = t; break
            _dep_current_val_lbl.configure(text=title); _dep_desc_lbl.configure(text=_dep_desc_map.get(target_id, ''))
        _dep_desc_lbl = tk.Label(c_modules, text=_dep_desc_map['base'], bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w'); _dep_desc_lbl.pack(fill='x', pady=(2, 0))
        _dep_status_lbl = tk.Label(_dep_info_frame, text=i18n.tr('premium.dep_uptodate'), bg=_blend(_CYAN, 0.04), fg=_DIM, font=(hud._F, _sf(9)), anchor='w'); _dep_status_lbl.pack(fill='x', padx=10, pady=(0, 6))
        _dep_log_path = os.path.join('logs', 'dependency_install.log'); _dep_install_running = {'busy': False, 'after_id': None}

        def _start_dep_sync(target, reason):
            if _dep_install_running['busy']: return
            _dep_install_running['busy'] = True; _dep_sync_indicator.configure(text=i18n.tr('premium.dep_syncing'), fg=_AMBER); _dep_status_lbl.configure(text=i18n.tr('premium.dep_syncing_msg'), fg=_CYAN)
            def _worker():
                rc = 0
                try:
                    os.makedirs('logs', exist_ok=True)
                    with open(_dep_log_path, 'w', encoding='utf-8') as logf:
                        cmd = [sys.executable, '-m', 'pip', 'install']; [cmd.extend(['-r', f]) for f in target['include_files']]; rc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT).wait()
                except: rc = 1
                finally:
                    _dep_install_running['busy'] = False
                    def _safe():
                        if _dep_status_lbl.winfo_exists():
                            _dep_sync_indicator.configure(
                                text=i18n.tr('premium.dep_done') if rc==0 else i18n.tr('premium.dep_error'),
                                fg=_GREEN if rc==0 else _RED
                            )
                            _dep_status_lbl.configure(
                                text=i18n.tr('premium.dep_uptodate') if rc==0 else i18n.tr('premium.dep_error_msg'),
                                fg=_GREEN if rc==0 else _RED
                            )
                    win.after(0, _safe)
            threading.Thread(target=_worker, daemon=True).start()

        def _schedule_auto_dep_sync(r):
            if _dep_install_running['after_id']: win.after_cancel(_dep_install_running['after_id'])
            _dep_install_running['after_id'] = win.after(1000, lambda: _start_dep_sync({'include_files':['requirements-base.txt']}, r))
        _on_dep_change()

        c_brief = _card(inner, '☀', i18n.tr('premium.briefing_title'), _CYAN, hud)
        br = _settings.get('briefing', {}); _brief_vars = {}
        def _save_briefing(): _settings['briefing'] = {k: bool(v.get()) for k, v in _brief_vars.items()}; _save_hud_settings(_settings)
        for k, text in [
            ('include_greeting', i18n.tr('premium.brief_greeting')),
            ('include_time', i18n.tr('premium.brief_time')),
            ('include_weather', i18n.tr('premium.brief_weather')),
            ('include_battery', i18n.tr('premium.brief_battery')),
            ('include_system_load', i18n.tr('premium.brief_system_load')),
            ('include_calendar', i18n.tr('premium.brief_calendar')),
            ('include_mail_unread', i18n.tr('premium.brief_mail'))
        ]:
            row = tk.Frame(c_brief, bg=_PANEL); row.pack(fill='x', pady=2, padx=8)
            v = tk.BooleanVar(value=br.get(k, True)); _brief_vars[k] = v
            ctk.CTkSwitch(row, text='', variable=v, fg_color=_BRD_I, progress_color=_CYAN, button_color=_WHITE, command=_save_briefing, switch_width=40, switch_height=18, width=0).pack(side='left', padx=(0, 10))
            tk.Label(row, text=text, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10)), anchor='w').pack(side='left')

        c_ai = _card(inner, '◉', i18n.tr('premium.ai_title'), _CYAN, hud)
        ai_container = tk.Frame(c_ai, bg=_PANEL); ai_container.pack(fill='x', padx=12, pady=(4, 8))
        _prov_meta = _build_prov_meta()
        _ai_prov_var = tk.StringVar(value=_settings.get('ai_provider', 'groq')); _ai_model_var = tk.StringVar(value=_settings.get('ai_model', 'llama-3.3-70b-versatile'))
        _stat_ctx = tk.StringVar(value='-'); _stat_rpm = tk.StringVar(value='-'); _stat_rpd = tk.StringVar(value='-'); _stat_alias = tk.StringVar(value='-')

        tk.Label(ai_container, text=i18n.tr('premium.ai_platform_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x')
        _prov_list_outer = tk.Frame(ai_container, bg=_PANEL); _prov_list_outer.pack(fill='x', pady=(4, 8)); _btn_refs = {}
        _model_menu_ref = [None]  # контейнер для обхода ограничения closure
        def _on_ai_upd(*_):
            p = _ai_prov_var.get(); _settings['ai_provider'] = p; m_list = list(_prov_meta[p]['models'].keys()); m = _ai_model_var.get() if _ai_model_var.get() in m_list else m_list[0]
            _ai_model_var.set(m)
            if _model_menu_ref[0]: _model_menu_ref[0].configure(values=m_list)
            stats = _prov_meta[p]['models'][m]; _stat_ctx.set(stats['ctx']); _stat_rpm.set(f"{stats['rpm']}/m"); _stat_rpd.set(f"{stats['rpd']} req/d"); _stat_alias.set(f"➜ {stats['alias']}"); _save_hud_settings(_settings)
            for k, b in _btn_refs.items(): b.configure(border_width=2 if k==p else 1, border_color=_CYAN if k==p else _blend(_CYAN, 0.12))
        _p_ids = list(_prov_meta.keys())
        def _rebuild_prov_grid(e=None):
            [w.destroy() for w in _prov_list_outer.winfo_children()]; _btn_refs.clear()
            _cols = 2 if len(_p_ids) <= 4 else 3
            for i, p_id in enumerate(_p_ids):
                row_i, col_i = divmod(i, _cols); info = _prov_meta[p_id]; is_p = (p_id == _ai_prov_var.get())
                b = ctk.CTkButton(_prov_list_outer, text=f"{info['icon']}  {info['name']}", command=lambda pid=p_id: (_ai_prov_var.set(pid), _on_ai_upd()), font=(hud._F, _sf(8), 'bold'), height=30, corner_radius=6, border_width=2 if is_p else 1, fg_color=_blend(_CYAN, 0.22 if is_p else 0.05), border_color=_CYAN if is_p else _blend(_CYAN, 0.12)); b.grid(row=row_i, column=col_i, sticky='ew', padx=3, pady=2); _prov_list_outer.columnconfigure(col_i, weight=1); _btn_refs[p_id] = b
        tk.Label(ai_container, text=i18n.tr('premium.ai_model_specs_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x', pady=(4,0))
        tk.Label(ai_container, textvariable=_stat_alias, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='center').pack(fill='x', pady=(2, 6))
        stats_f = tk.Frame(ai_container, bg=_PANEL); stats_f.pack(fill='x', pady=(0, 8)); _stat_cells_frame = tk.Frame(stats_f, bg=_PANEL); _stat_cells_frame.pack(fill='x')
        def _rebuild_stats_grid(e=None):
            [w.destroy() for w in _stat_cells_frame.winfo_children()]
            for i, (lbl_t, var) in enumerate([
                (i18n.tr('premium.ai_memory_label'), _stat_ctx),
                (i18n.tr('premium.ai_rpm_label'), _stat_rpm),
                (i18n.tr('premium.ai_limit_label'), _stat_rpd)
            ]):
                row_i, col_i = divmod(i, 3); cell = ctk.CTkFrame(_stat_cells_frame, fg_color=_blend(_CYAN, 0.04), border_color=_blend(_CYAN, 0.1), border_width=1, corner_radius=6); cell.grid(row=row_i, column=col_i, sticky='nsew', padx=2, pady=1); _stat_cells_frame.columnconfigure(col_i, weight=1); _stat_cells_frame.rowconfigure(row_i, uniform='stat_row')
                ctk.CTkLabel(cell, text=lbl_t, text_color=_CYAN, font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(pady=(4, 0)); ctk.CTkLabel(cell, textvariable=var, text_color=_WHITE, font=(hud._F, JStyle.TEXT_BODY, 'bold')).pack(pady=(0, 4))
        ai_container.bind('<Configure>', lambda e: (_rebuild_prov_grid(e), _rebuild_stats_grid(e)), add='+')
        tk.Label(ai_container, text=i18n.tr('premium.ai_models_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x', pady=(4, 0))
        _ai_model_menu = _HUDDropdown(hud, ai_container, list(_prov_meta[_ai_prov_var.get()]['models'].keys()), _ai_model_var, command=_on_ai_upd, accent=_CYAN); _model_menu_ref[0] = _ai_model_menu; _ai_model_menu.frame.pack(fill='x', pady=(4, 8), padx=2)
        _ai_ent = ctk.CTkEntry(ai_container, placeholder_text=i18n.tr('premium.ai_api_key_placeholder'), font=(hud._F, 11), show='•', height=40, fg_color=_BG, border_color=_blend(_CYAN, 0.3), corner_radius=10); _ai_ent.pack(fill='x', pady=(0, 8), padx=2)
        btn_g = tk.Frame(ai_container, bg=_PANEL); btn_g.pack(fill='x')
        def _mini_btn(parent, text, col, cmd, c): ctk.CTkButton(parent, text=text, command=cmd, height=32, font=(hud._F, 11, 'bold'), fg_color=_blend(col, 0.08), hover_color=_blend(col, 0.18), text_color=col, border_color=_blend(col, 0.3), border_width=1, corner_radius=6).grid(row=0, column=c, sticky='ew', padx=3); parent.columnconfigure(c, weight=1)
        _mini_btn(btn_g, f'🌐 {i18n.tr("premium.ai_btn_website")}', _CYAN, lambda: None, 0)
        _mini_btn(btn_g, f'📋 {i18n.tr("premium.ai_btn_paste")}', _CYAN, lambda: None, 1)
        _mini_btn(btn_g, f'💾 {i18n.tr("premium.ai_btn_save")}', _GREEN, lambda: None, 2)
        _on_ai_upd(); _refresh_load_summary()

    except Exception as e:
        import traceback; traceback.print_exc(); tk.Label(inner, text=f"ERROR: {e}", bg=_BG, fg=_RED).pack()