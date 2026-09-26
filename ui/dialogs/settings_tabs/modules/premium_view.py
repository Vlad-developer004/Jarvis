from ui.hud_style import JStyle
from core import i18n
import os, sys, threading, time, subprocess
import tkinter as tk
import customtkinter as ctk
from .base import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _card, _hint, _blend, _std_action_btn, _hero_btn, _add_context_menu, _slider, _label_row, _HUDDropdown
from .constants import _AI_CONFIG

def _build_prov_meta():
    from features.qa import model_fetcher
    out = {}
    for pname, pdata in _AI_CONFIG.items():
        pid = pdata['id']
        out[pid] = {
            'name':   pname,
            'icon':   pdata['icon'],
            'url':    pdata['site'],
            'key':    pdata['env'],
            'models': model_fetcher.get_models_for_ui(pid),
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
        # Restart notice frame (hidden until a profile change actually needs
        # one) — same pack-on-demand pattern as the theme-change notice in
        # settings_tabs/appearance.py, reused here since a feature-profile
        # switch equally requires a restart to take effect.
        _profile_restart_f = tk.Frame(c_modules, bg=_blend(_AMBER, 0.08),
                                       highlightbackground=_blend(_AMBER, 0.3), highlightthickness=1)
        _feature_desc_lbl = tk.Label(c_modules, text='', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(10)), justify='left', anchor='w')
        _feature_desc_lbl.pack(fill='x', pady=(4, 0))

        def _show_profile_restart_notice():
            for w in _profile_restart_f.winfo_children(): w.destroy()
            lbl = tk.Label(
                _profile_restart_f, text=i18n.tr('premium.profile_saved_msg'),
                bg=_blend(_AMBER, 0.08), fg=_AMBER,
                font=(hud._F, _sf(9), 'bold'), anchor='w', justify='left'
            )
            lbl.pack(side='left', fill='x', expand=True, padx=12, pady=8)
            def _upd_wrap(e, l=lbl):
                l.configure(wraplength=max(100, e.width - hud._px(190)))
            _profile_restart_f.bind('<Configure>', _upd_wrap, add='+')
            def _restart():
                import subprocess, sys, os as _os
                subprocess.Popen([sys.executable] + sys.argv)
                win.after(200, lambda: _os._exit(0))
            ctk.CTkButton(
                _profile_restart_f, text=i18n.tr('theme.restart_btn'), command=_restart,
                height=34, font=(hud._F, _sf(9), 'bold'),
                fg_color=_blend(_AMBER, 0.15), hover_color=_blend(_AMBER, 0.25),
                text_color=_AMBER, border_color=_blend(_AMBER, 0.5),
                border_width=1, corner_radius=6, width=160
            ).pack(side='right', padx=8, pady=6)
            _profile_restart_f.pack(fill='x', pady=(6, 0))
        
        _feature_presets = {
            'full': {'games': True, 'qa': True, 'llm_chat_fallback': True, 'cinema': True, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': True, 'morning_briefing': True, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False, 'git_integration': True, 'translator': True, 'song_id': True},
            'assistant': {'games': False, 'qa': False, 'llm_chat_fallback': True, 'cinema': False, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': False, 'morning_briefing': False, 'updater': True, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False, 'git_integration': True, 'translator': True, 'song_id': False},
            'minimal': {'games': False, 'qa': False, 'llm_chat_fallback': True, 'cinema': False, 'system_monitoring': True, 'battery_monitor': True, 'lag_hunter': False, 'morning_briefing': False, 'updater': False, 'network_profiles': False, 'system_health': False, 'calendar_ics': False, 'inbox_digest': False, 'git_integration': True, 'translator': True, 'song_id': False}
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
            _show_profile_restart_notice()
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

        def _upd_desc_wrap(e, l=_feature_desc_lbl): l.configure(wraplength=max(hud._px(100), e.width - hud._px(20)))
        c_modules.bind('<Configure>', _upd_desc_wrap, add='+')

        tk.Frame(c_modules, bg=_BRD, height=1).pack(fill='x', pady=(10, 0))
        tk.Label(c_modules, text=i18n.tr('premium.modules_detailed_title'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(fill='x', pady=(8, 0))
        
        _module_meta = {
            'qa': {'title': i18n.tr('premium.module_qa_title'), 'icon': '◉', 'what': i18n.tr('premium.module_qa_desc'), 'weight': 3},
            'llm_chat_fallback': {'title': i18n.tr('premium.module_llm_chat_title'), 'icon': '◈', 'what': i18n.tr('premium.module_llm_chat_desc'), 'weight': 2},
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
            'git_integration': {'title': i18n.tr('premium.module_git_title'), 'icon': '⎇', 'what': i18n.tr('premium.module_git_desc'), 'weight': 1},
            'translator': {'title': i18n.tr('premium.module_translator_title'), 'icon': '⇄', 'what': i18n.tr('premium.module_translator_desc'), 'weight': 1},
            'song_id': {'title': i18n.tr('premium.module_song_title'), 'icon': '♪', 'what': i18n.tr('premium.module_song_desc'), 'weight': 1},
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
            try:
                from core.nlp.semantic import _INTENT_MODULE_MAP, rebuild_cache
                if k in _INTENT_MODULE_MAP.values():
                    import threading
                    threading.Thread(target=rebuild_cache, daemon=True).start()
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
        _saved_prov = _settings.get('ai_provider', 'groq')
        if _saved_prov not in _prov_meta:
            _saved_prov = list(_prov_meta.keys())[0] if _prov_meta else 'groq'
        _ai_prov_var = tk.StringVar(value=_saved_prov)

        _saved_model = _settings.get('ai_model', '')
        _m_list_init = list(_prov_meta[_saved_prov]['models'].keys()) if _saved_prov in _prov_meta else []
        if not _saved_model or _saved_model not in _m_list_init:
            _saved_model = _m_list_init[0] if _m_list_init else ''
        _ai_model_var = tk.StringVar(value=_saved_model)

        _stat_ctx = tk.StringVar(value='-'); _stat_rpm = tk.StringVar(value='-')
        _stat_rpd = tk.StringVar(value='-'); _stat_alias = tk.StringVar(value='-')
        _refresh_status_var = tk.StringVar(value='')

        tk.Label(ai_container, text=i18n.tr('premium.ai_platform_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x')
        _prov_list_outer = tk.Frame(ai_container, bg=_PANEL); _prov_list_outer.pack(fill='x', pady=(4, 8)); _btn_refs = {}
        _model_menu_ref = [None]

        def _update_stats(p, m):
            stats = _prov_meta[p]['models'].get(m, {})
            _stat_ctx.set(stats.get('ctx', '?'))
            _stat_rpm.set(f"{stats.get('rpm', '?')}/m")
            _stat_rpd.set(f"{stats.get('rpd', '?')} req/d")
            _stat_alias.set(f"➜ {stats.get('alias', '')}" if stats.get('alias') else '—')

        def _on_ai_upd(*_):
            p = _ai_prov_var.get()
            if p not in _prov_meta:
                p = list(_prov_meta.keys())[0] if _prov_meta else 'groq'
                _ai_prov_var.set(p)
            _settings['ai_provider'] = p
            m_list = list(_prov_meta[p]['models'].keys())
            if not m_list:
                _ai_model_var.set('')
                _settings['ai_model'] = ''
                if _model_menu_ref[0]: _model_menu_ref[0].configure(values=[i18n.tr('premium.ai_no_models')])
                _stat_ctx.set('?'); _stat_rpm.set('?'); _stat_rpd.set('?')
                _stat_alias.set(i18n.tr('premium.ai_no_models'))
                _save_hud_settings(_settings)
                for k, b in _btn_refs.items(): b.configure(border_width=2 if k==p else 1, border_color=_CYAN if k==p else _blend(_CYAN, 0.12))
                _fill_key_entry(p); return
            m = _ai_model_var.get() if _ai_model_var.get() in m_list else m_list[0]
            _ai_model_var.set(m)
            _settings['ai_model'] = m
            if _model_menu_ref[0]: _model_menu_ref[0].configure(values=m_list)
            _update_stats(p, m)
            _save_hud_settings(_settings)
            for k, b in _btn_refs.items(): b.configure(border_width=2 if k==p else 1, border_color=_CYAN if k==p else _blend(_CYAN, 0.12))
            _fill_key_entry(p)

        def _on_model_upd(*_):
            p = _ai_prov_var.get(); m = _ai_model_var.get()
            _settings['ai_model'] = m
            _update_stats(p, m)
            _save_hud_settings(_settings)

        def _load_current_api_key(provider: str) -> str:
            try:
                from features.qa.llm_processor import _load_api_key
                return _load_api_key(provider)
            except Exception:
                return ''

        _refreshing: set = set()

        def _auto_refresh(provider: str):
            if provider in _refreshing:
                return
            from features.qa import model_fetcher
            api_key = _load_current_api_key(provider)
            # 'local' needs no key at all (Ollama/llama.cpp/TabbyAPI don't
            # check it by default) — same free pass 'openrouter' already gets.
            if not api_key and provider not in ('openrouter', 'local'):
                _refresh_status_var.set(i18n.tr('premium.ai_no_key'))
                return
            base_url = _local_url_ent.get().strip() if provider == 'local' else ''
            _refreshing.add(provider)
            _refresh_status_var.set(i18n.tr('premium.ai_refreshing'))
            def _on_done(prov, models):
                _refreshing.discard(prov)
                if models:
                    _prov_meta[prov]['models'] = models
                def _ui():
                    if models:
                        n = len(_prov_meta[prov]['models'])
                        _refresh_status_var.set(f'{n} {i18n.tr("premium.ai_models_count")}')
                        if _ai_prov_var.get() == prov:
                            _on_ai_upd()
                    else:
                        _refresh_status_var.set(i18n.tr('premium.ai_no_key') if provider != 'local' else i18n.tr('premium.ai_local_unreachable'))
                win.after(0, _ui)
            model_fetcher.refresh_async(provider, api_key, _on_done, base_url=base_url)

        _p_ids = list(_prov_meta.keys())

        def _fit_prov_font_size(text: str, avail_px: int, base_n: int, min_n: int = 5) -> int:
            """Shrink the button font just enough for `text` to fit avail_px,
            measured with the real resolved font metrics — keeps provider
            names (Anthropic/OpenRouter/...) from clipping ("Anthro") on
            narrower windows or lower-DPI monitors, without a fixed guess
            that only happens to work at one window size."""
            import tkinter.font as tkfont
            n = base_n
            while n > min_n:
                if tkfont.Font(family=hud._F, size=_sf(n), weight='bold').measure(text) <= avail_px:
                    break
                n -= 1
            return n

        def _rebuild_prov_grid(e=None):
            [w.destroy() for w in _prov_list_outer.winfo_children()]; _btn_refs.clear()
            _cols = 2 if len(_p_ids) <= 4 else 3
            container_w = (e.width if e is not None and e.width > 1 else _prov_list_outer.winfo_width()) or 400
            col_w = max(60, container_w // _cols - hud._px(16))
            for i, p_id in enumerate(_p_ids):
                row_i, col_i = divmod(i, _cols); info = _prov_meta[p_id]; is_p = (p_id == _ai_prov_var.get())
                label = f"{info['icon']}  {info['name']}"
                font_n = _fit_prov_font_size(label, col_w, 8)
                def _pick_provider(pid=p_id):
                    _ai_prov_var.set(pid); _on_ai_upd()
                    # Re-sync the model catalog for whichever provider was
                    # just selected — Groq/OpenAI/etc. included, not just
                    # Local — instead of showing whatever was cached from
                    # the last manual ⟳ click (or nothing, if never
                    # refreshed). _auto_refresh() already no-ops quietly if
                    # there's no key configured for that provider yet.
                    _auto_refresh(pid)
                b = ctk.CTkButton(_prov_list_outer, text=label, command=_pick_provider, font=(hud._F, _sf(font_n), 'bold'), height=30, corner_radius=6, border_width=2 if is_p else 1, fg_color=_blend(_CYAN, 0.22 if is_p else 0.05), border_color=_CYAN if is_p else _blend(_CYAN, 0.12)); b.grid(row=row_i, column=col_i, sticky='ew', padx=3, pady=2); _prov_list_outer.columnconfigure(col_i, weight=1); _btn_refs[p_id] = b
        tk.Label(ai_container, text=i18n.tr('premium.ai_model_specs_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='center').pack(fill='x', pady=(4, 0))
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

        _models_hdr = tk.Frame(ai_container, bg=_PANEL); _models_hdr.pack(fill='x', pady=(4, 0))
        tk.Label(_models_hdr, text=i18n.tr('premium.ai_models_label'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), anchor='w').pack(side='left')
        ctk.CTkButton(_models_hdr, text='⟳', command=lambda: _auto_refresh(_ai_prov_var.get()), width=26, height=20, font=(hud._F, _sf(9), 'bold'), fg_color=_blend(_CYAN, 0.08), hover_color=_blend(_CYAN, 0.2), text_color=_CYAN, corner_radius=4).pack(side='right')

        _init_models = list(_prov_meta[_ai_prov_var.get()]['models'].keys()) or [i18n.tr('premium.ai_no_models')]
        _ai_model_menu = _HUDDropdown(hud, ai_container, _init_models, _ai_model_var, command=_on_model_upd, accent=_CYAN); _model_menu_ref[0] = _ai_model_menu; _ai_model_menu.frame.pack(fill='x', pady=(4, 2), padx=2)
        tk.Label(ai_container, textvariable=_refresh_status_var, bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='center').pack(fill='x', pady=(0, 6))

        # Manual model override — the catalog above is now kept in sync
        # automatically, but a model your account has access to can lag
        # behind the public catalog (early access, a private fine-tune, a
        # model your key can use that the listing endpoint doesn't surface),
        # so a way to just type the exact id and use it directly is still
        # worth having alongside the sync.
        _custom_model_row = tk.Frame(ai_container, bg=_PANEL); _custom_model_row.pack(fill='x', pady=(0, 6), padx=2)
        _custom_model_ent = ctk.CTkEntry(_custom_model_row, placeholder_text=i18n.tr('premium.ai_custom_model_placeholder'), font=(hud._F, 11), height=32, fg_color=_BG, border_color=_blend(_CYAN, 0.25), corner_radius=8)
        _custom_model_ent.pack(side='left', fill='x', expand=True, padx=(0, 6))

        def _apply_custom_model():
            mid = _custom_model_ent.get().strip()
            if not mid:
                return
            p = _ai_prov_var.get()
            _ai_model_var.set(mid)
            _settings['ai_model'] = mid
            _save_hud_settings(_settings)
            _update_stats(p, mid)
            _custom_model_ent.delete(0, 'end')
        ctk.CTkButton(_custom_model_row, text='✓', command=_apply_custom_model, width=32, height=32, font=(hud._F, hud._fsc(10), 'bold'), fg_color=_blend(_CYAN, 0.1), hover_color=_blend(_CYAN, 0.22), text_color=_CYAN, corner_radius=8).pack(side='right')
        _custom_model_ent.bind('<Return>', lambda e: _apply_custom_model())

        # Local-server address — only shown for provider == 'local', since
        # it's the one provider without a fixed base_url (see
        # llm_processor._OPENAI_COMPAT['local']). Created hidden; _on_ai_upd
        # packs/unpacks it as the selected provider changes.
        _local_hint_lbl = tk.Label(ai_container, text=i18n.tr('premium.ai_local_hint'), bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), justify='left', anchor='w', wraplength=1)
        _local_url_ent = ctk.CTkEntry(ai_container, placeholder_text=i18n.tr('premium.ai_local_url_placeholder'), font=(hud._F, 11), height=40, fg_color=_BG, border_color=_blend(_CYAN, 0.3), corner_radius=10)
        ai_container.bind('<Configure>', lambda e: _local_hint_lbl.configure(wraplength=max(hud._px(100), e.width - hud._px(8))), add='+')

        _last_synced_local_url = ['']
        def _save_local_url(*_):
            url = _local_url_ent.get().strip()
            _settings['ai_local_base_url'] = url
            _save_hud_settings(_settings)
            try:
                from features.qa.llm_processor import invalidate_clients
                invalidate_clients('local')
            except Exception:
                pass
            # Re-sync the model catalog against the (possibly new) address —
            # editing the URL is exactly when the old cached model list is
            # most likely wrong.
            if url != _last_synced_local_url[0]:
                _last_synced_local_url[0] = url
                _auto_refresh('local')
        _local_url_ent.bind('<FocusOut>', _save_local_url)
        _local_url_ent.bind('<Return>', _save_local_url)

        _ai_ent = ctk.CTkEntry(ai_container, placeholder_text=i18n.tr('premium.ai_api_key_placeholder'), font=(hud._F, 11), show='•', height=40, fg_color=_BG, border_color=_blend(_CYAN, 0.3), corner_radius=10); _ai_ent.pack(fill='x', pady=(0, 8), padx=2)
        try:
            from ui.dialogs.extensions_common import _bind_ctk_entry_clipboard
            _bind_ctk_entry_clipboard(win, _ai_ent, hud)
            _bind_ctk_entry_clipboard(win, _local_url_ent, hud)
        except Exception:
            pass

        def _fill_key_entry(provider):
            try:
                k = _load_current_api_key(provider)
                _ai_ent.delete(0, 'end')
                if k:
                    _ai_ent.insert(0, k)
            except Exception:
                pass
            if provider == 'local':
                _local_hint_lbl.pack(fill='x', pady=(0, 4), padx=2, before=_ai_ent)
                _local_url_ent.pack(fill='x', pady=(0, 8), padx=2, before=_ai_ent)
                _local_url_ent.delete(0, 'end')
                _local_url_ent.insert(0, _settings.get('ai_local_base_url', '') or 'http://localhost:11434/v1')
                # wraplength starts at a throwaway value (see creation above)
                # and is normally corrected by the ai_container <Configure>
                # handler — but that only fires on an actual resize, so if
                # the container is already at its final size when this tab
                # is built, the label was staying wrapped at ~1px forever
                # (every character on its own line). Set it here too, from
                # whatever width is already known.
                ai_container.update_idletasks()
                w = ai_container.winfo_width()
                _local_hint_lbl.configure(wraplength=max(hud._px(100), (w - hud._px(8)) if w > 1 else hud._px(400)))
            else:
                _local_hint_lbl.pack_forget()
                _local_url_ent.pack_forget()
            if provider == 'local':
                _topk_frame.pack(fill='x')
            else:
                _topk_frame.pack_forget()

        btn_g = tk.Frame(ai_container, bg=_PANEL); btn_g.pack(fill='x')
        def _mini_btn(parent, text, col, cmd, c): ctk.CTkButton(parent, text=text, command=cmd, height=32, font=(hud._F, 11, 'bold'), fg_color=_blend(col, 0.08), hover_color=_blend(col, 0.18), text_color=col, border_color=_blend(col, 0.3), border_width=1, corner_radius=6).grid(row=0, column=c, sticky='ew', padx=3); parent.columnconfigure(c, weight=1)
        def _do_paste():
            text = ''
            try:
                import pyperclip
                text = (pyperclip.paste() or '').strip()
            except Exception:
                pass
            if not text:
                try:
                    text = win.clipboard_get().strip()
                except Exception:
                    text = ''
            if not text:
                _refresh_status_var.set(i18n.tr('premium.ai_clipboard_empty'))
                return
            _ai_ent.delete(0, 'end')
            _ai_ent.insert(0, text)

        def _do_save():
            key = _ai_ent.get().strip()
            p = _ai_prov_var.get()
            if p == 'local':
                # No API key required for a local server — just persist the
                # address (and the key too, if the user's TabbyAPI setup
                # actually wants one) and refresh the model list.
                _save_local_url()
                if key:
                    os.environ[_prov_meta.get(p, {}).get('key', '') or 'LOCAL_LLM_API_KEY'] = key
                _refresh_status_var.set(i18n.tr('premium.ai_key_saved'))
                _auto_refresh(p)
                return
            env_name = _prov_meta.get(p, {}).get('key', '')
            if not key or not env_name:
                return
            # Single source of truth — same path the startup loader and
            # llm_processor._load_api_key() read from. See config_pack.config.get_secrets_path().
            from config_pack.config import get_secrets_path
            env_path = get_secrets_path()
            try:
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, encoding='utf-8-sig') as f:
                        lines = f.readlines()
                new_lines, found = [], False
                for line in lines:
                    if line.strip().startswith(f'{env_name}='):
                        new_lines.append(f'{env_name}={key}\n'); found = True
                    else:
                        new_lines.append(line)
                if not found:
                    new_lines.append(f'{env_name}={key}\n')
                parent_dir = os.path.dirname(env_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                with open(env_path, 'w', encoding='utf-8') as f:
                    f.writelines(new_lines)
                os.environ[env_name] = key
                try:
                    from features.qa.llm_processor import invalidate_clients
                    invalidate_clients(p)
                except Exception:
                    pass
                _refresh_status_var.set(i18n.tr('premium.ai_key_saved'))
                _auto_refresh(p)
            except Exception as e:
                _refresh_status_var.set(f'✗ {e}')

        import webbrowser
        def _open_prov_site():
            url = _prov_meta.get(_ai_prov_var.get(), {}).get('url', '')
            if url:
                webbrowser.open(url)
        _mini_btn(btn_g, f'🌐 {i18n.tr("premium.ai_btn_website")}', _CYAN, _open_prov_site, 0)
        _mini_btn(btn_g, f'📋 {i18n.tr("premium.ai_btn_paste")}', _CYAN, _do_paste, 1)
        _mini_btn(btn_g, f'💾 {i18n.tr("premium.ai_btn_save")}', _GREEN, _do_save, 2)

        # --- Advanced generation params ---
        tk.Frame(ai_container, bg=_BRD, height=1).pack(fill='x', pady=(10, 4))
        tk.Label(ai_container, text=i18n.tr('premium.ai_advanced_title'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(9), 'bold'), anchor='w').pack(fill='x')

        def _debounced_setting_save(after_ref, key, value):
            if after_ref[0]:
                win.after_cancel(after_ref[0])
            def _save():
                _settings[key] = value
                _save_hud_settings(_settings)
            after_ref[0] = win.after(400, _save)

        _temp_lbl = _label_row(ai_container, i18n.tr('premium.ai_temperature'), _CYAN, hud)
        _cur_temp = float(_settings.get('ai_temperature') or 0.3)
        _temp_lbl.configure(text=f'{_cur_temp:.2f}')
        _temp_save_after = [None]
        def _on_temp(v):
            val = round(float(v), 2)
            _temp_lbl.configure(text=f'{val:.2f}')
            _debounced_setting_save(_temp_save_after, 'ai_temperature', val)
        _slider(ai_container, 0.0, 1.0, 20, _CYAN, _cur_temp, _on_temp, hud)
        _hint(ai_container, i18n.tr('premium.ai_temperature_hint'), hud)

        _maxtok_lbl = _label_row(ai_container, i18n.tr('premium.ai_max_tokens'), _CYAN, hud)
        _cur_maxtok = int(_settings.get('ai_max_tokens') or 250)
        _maxtok_lbl.configure(text=str(_cur_maxtok))
        _maxtok_save_after = [None]
        def _on_maxtok(v):
            val = int(round(float(v) / 10) * 10)
            _maxtok_lbl.configure(text=str(val))
            _debounced_setting_save(_maxtok_save_after, 'ai_max_tokens', val)
        _slider(ai_container, 50, 2000, 39, _CYAN, _cur_maxtok, _on_maxtok, hud)

        # top_k — only shown for 'local': not part of the OpenAI chat
        # completions schema, so Groq/OpenAI/etc. would just ignore it
        # (or reject it) — only local inference servers (llama.cpp/
        # Ollama/TabbyAPI) actually honor it (see llm_processor._ask_openai_compat).
        _topk_frame = tk.Frame(ai_container, bg=_PANEL)
        _topk_lbl = _label_row(_topk_frame, i18n.tr('premium.ai_top_k'), _MAG, hud)
        _cur_topk = int(_settings.get('ai_top_k') or 40)
        _topk_lbl.configure(text=str(_cur_topk))
        _topk_save_after = [None]
        def _on_topk(v):
            val = int(round(float(v)))
            _topk_lbl.configure(text=str(val))
            _debounced_setting_save(_topk_save_after, 'ai_top_k', val)
        _slider(_topk_frame, 1, 100, 99, _MAG, _cur_topk, _on_topk, hud)
        _hint(_topk_frame, i18n.tr('premium.ai_top_k_hint'), hud)

        _on_ai_upd(); _refresh_load_summary()
        if _ai_prov_var.get() == 'local':
            _last_synced_local_url[0] = _local_url_ent.get().strip()
        # Sync the catalog for whichever provider was active when the
        # dialog was last closed, same as picking it fresh from the grid.
        _auto_refresh(_ai_prov_var.get())

        row_mini = tk.Frame(c_ai, bg=_PANEL)
        row_mini.pack(fill='x', pady=(6, 8), padx=12)
        _ai_mini_window_var = tk.BooleanVar(value=bool(_settings.get('ai_mini_window', True)))
        def _save_ai_mini_window():
            _settings['ai_mini_window'] = bool(_ai_mini_window_var.get())
            _save_hud_settings(_settings)
        ctk.CTkSwitch(row_mini, text='', variable=_ai_mini_window_var, fg_color=_BRD_I, progress_color=_CYAN, button_color=_WHITE, command=_save_ai_mini_window, switch_width=40, switch_height=18, width=0).pack(side='left', padx=(0, 10))
        tk.Label(row_mini, text=i18n.tr('premium.ai_mini_window'), bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10)), anchor='w').pack(side='left')

    except Exception as e:
        import traceback; traceback.print_exc(); tk.Label(inner, text=f"ERROR: {e}", bg=_BG, fg=_RED).pack()