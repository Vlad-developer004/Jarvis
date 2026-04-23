import os, json, sys, subprocess, threading, time
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ui.hud_utils import _blend, _bar_color, _set_dark_title_bar
from ui.hud_widgets import _HudScrollbar, _HUDDropdown

def build_voice_tab(inner, win, hud, _save_hud_settings):
    _sf = lambda n: hud._fs(n + 6)

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
        
        lbl = tk.Label(row, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(11), 'bold'), anchor='w', justify='left')
        lbl.pack(side='left', fill='x', expand=True, anchor='nw')
        
        val_lbl = tk.Label(row, text='', bg=_PANEL, fg=accent, font=(hud._F, _sf(12), 'bold'), anchor='e', justify='right')
        val_lbl.pack(side='right', padx=(10, 0), anchor='ne')
        
        _last_row_w = [0]
        def _upd_row(e, l=lbl, v=val_lbl):
            if abs(e.width - _last_row_w[0]) < 10: return
            _last_row_w[0] = e.width
            # Dynamic wrap based on value width
            v_req = v.winfo_reqwidth()
            l.configure(wraplength=max(100, e.width - (v_req + 20)))
            if v_req > e.width * 0.6:
                v.configure(wraplength=int(e.width * 0.4))
            else:
                v.configure(wraplength=0)
                
        row.bind('<Configure>', _upd_row, add='+')
        return val_lbl
    def _slider(parent, from_, to, steps, accent, init_val, callback):
        container = tk.Frame(parent, bg=_PANEL)
        container.pack(fill='x', pady=(10, 4))
        
        # Neural Scale (Ticks) - Defined first to use in callback
        scale_canvas = tk.Canvas(container, height=10, bg=_PANEL, highlightthickness=0)
        scale_canvas.pack(side='bottom', fill='x', pady=(2, 0))

        def _draw_ticks(current_val=None):
            scale_canvas.delete('all')
            w = scale_canvas.winfo_width()
            if w <= 1: return
            
            num_ticks = steps if steps and steps < 30 else 20
            # Normalize current_val to 0-1 range
            progress = (current_val - from_) / (to - from_) if current_val is not None else (init_val - from_) / (to - from_)
            
            for i in range(num_ticks + 1):
                f = i / num_ticks
                x = f * (w - 20) + 10
                
                # Milestone logic
                is_milestone = i in (0, num_ticks // 2, num_ticks)
                h = 6 if is_milestone else 3
                
                # Glow logic: ticks behind the handle are brighter
                is_active = f <= (progress + 0.01)
                color = accent if is_active else _blend(accent, 0.25)
                width = 2 if is_milestone and is_active else 1
                
                scale_canvas.create_line(x, 0, x, h, fill=color, width=width)
        
        def _on_change(v):
            _draw_ticks(float(v))
            callback(v)

        s = ctk.CTkSlider(
            container, from_=from_, to=to, number_of_steps=steps,
            progress_color=accent, 
            button_color=_WHITE, 
            button_hover_color=accent,
            fg_color=_blend(accent, 0.1),
            height=hud._px(12),
            border_width=hud._px(2),
            border_color=_blend(accent, 0.2),
            command=_on_change
        )
        s.set(init_val)
        s.pack(side='top', fill='x')
        
        scale_canvas.bind('<Configure>', lambda e: _draw_ticks(s.get()))
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
    def _pick_app_dialog(on_selected):
        """Reusable premium app picker dialog."""
        from core.system.windows import get_installed_apps
        apps = get_installed_apps()
        pick_win = ctk.CTkToplevel(win)
        pick_win.title("ВЫБОР ПРИЛОЖЕНИЯ")
        pick_win.geometry(f"{hud._px(600)}x{hud._px(700)}")
        pick_win.configure(bg=_BG)
        _set_dark_title_bar(pick_win)
        pick_win.attributes("-topmost", True)
        pick_win.lift()
        top_bar = tk.Frame(pick_win, bg=_BG)
        top_bar.pack(fill='x', padx=20, pady=(20, 10))
        tk.Label(top_bar, text="ВЫБЕРИТЕ ПРИЛОЖЕНИЕ", bg=_BG, fg=_CYAN, font=(hud._F, _sf(14), 'bold')).pack(anchor='w')
        tk.Label(top_bar, text="Выберите программу для добавления в список", bg=_BG, fg=_DIM, font=(hud._F, _sf(10))).pack(anchor='w')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text='Поиск...', font=(hud._F, _sf(11)), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=hud._px(44), corner_radius=10)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        sw_all = ctk.CTkSwitch(ctrl_f, text='Системные', variable=_show_all_var, font=(hud._F, _sf(10), 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=hud._px(36), switch_height=hud._px(18))
        sw_all.pack(side='right')
        lb_frame = tk.Frame(pick_win, bg=_BG, highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
        lb_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
        lb = tk.Listbox(lb_frame, bg=_BG, fg=_TEXT, font=(hud._F, _sf(11)), borderwidth=0, highlightthickness=0, selectbackground=_blend(_CYAN, 0.3), activestyle='none')
        sb = _HudScrollbar(lb_frame, lb, color=_CYAN)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        _f_data = []
        def _refresh(*_):
            lb.delete(0, tk.END)
            search = ent_search.get().lower().strip()
            show_all = _show_all_var.get()
            _f_data.clear()
            ides = [a for a in apps if a.get('is_ide')]
            others = [a for a in apps if not a.get('is_ide')]
            for app in ides + others:
                if app.get('is_noise') and not show_all: continue
                if search and search not in app['name'].lower() and search not in (app.get('exe') or '').lower(): continue
                prefix = "✦ " if app.get('is_ide') else "  "
                exe_part = f" — {app['exe']}" if app.get('exe') else ""
                lb.insert(tk.END, f"{prefix}{app['name']}{exe_part}")
                _f_data.append(app)
        ent_search.bind('<KeyRelease>', _refresh)
        sw_all.configure(command=_refresh)
        _refresh()
        def _on_pick(_e=None):
            sel = lb.curselection()
            if sel:
                app = _f_data[sel[0]]
                on_selected(app.get('exe') or app['name'])
                pick_win.destroy()
        lb.bind('<Double-Button-1>', _on_pick)
        ctk.CTkButton(pick_win, text="ВЫБРАТЬ ПРИЛОЖЕНИЕ", command=_on_pick, height=hud._px(50), font=(hud._F, _sf(12), 'bold'), fg_color=_CYAN, text_color=_BG).pack(fill='x', padx=20, pady=(0, 20))

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
        info.pack(side='left', fill='both', expand=True, padx=(8, 0)) # Added left padding
        tk.Label(info, text=name, bg=_BG, fg=col, font=(hud._F, _sf(13), 'bold'), anchor='w').pack(anchor='w')
        desc_lbl = tk.Label(info, text=desc, bg=_BG, fg=_DIM, font=(hud._F, _sf(10)), anchor='w', justify='left')
        desc_lbl.pack(anchor='w')
        
        _last_stt_w = [0]
        def _upd_desc(e, l=desc_lbl):
            if abs(e.width - _last_stt_w[0]) < 10: return
            _last_stt_w[0] = e.width
            l.configure(wraplength=max(60, e.width - 10))
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
    tk.Label(c4, text='🔄  Применяется сразу, без перезапуска',
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
    thresh_slider = _slider(c4, 30, 1200, 117, _AMBER, _cur_thresh, _on_thresh)
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
    gain_slider = _slider(c4, 1.0, 6.0, 50, _AMBER, _cur_gain, _on_gain)
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
            from config_pack.config import get_settings_path
            p = get_settings_path()
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                return d if isinstance(d, dict) else {}
        except Exception:
            pass
        return {}
    def _save_settings_json(d: dict) -> None:
        try:
            from config_pack.config import get_settings_path
            p = get_settings_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    _status_f = tk.Frame(c4, bg=_PANEL)
    _status_f.pack(fill='x', pady=(0, 6))
    _status_accent = tk.Frame(_status_f, width=3, bg=_PANEL)
    _status_accent.pack(side='left', fill='y')
    _aud_status = tk.Label(
        _status_f,
        text='',
        bg=_PANEL,
        fg=_DIM,
        font=(hud._F, _sf(9), 'bold'),
        anchor='w',
        justify='left',
        padx=10
    )
    _aud_status.pack(side='left', fill='x', expand=True, pady=6)
    def _set_aud_status(t: str, col: str = _DIM):
        try:
            if not t:
                _status_f.configure(bg=_PANEL)
                _status_accent.configure(bg=_PANEL)
                _aud_status.configure(text='', bg=_PANEL, fg=_DIM)
                return
            _is_solid = col in (_GREEN, _AMBER, _CYAN, _RED)
            _bg = _blend(col, 0.08) if _is_solid else _PANEL
            _status_f.configure(bg=_bg)
            _status_accent.configure(bg=col if _is_solid else _PANEL)
            _aud_status.configure(text=t, bg=_bg, fg=col)
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

    _s0 = _load_settings_json()
    _in_idx0  = _s0.get('audio_input_device_index')
    _out_name0 = _s0.get('audio_output_device_name')
    
    _in_default_label = 'Системный микрофон (по умолчанию)'
    _out_default_label = 'Системный вывод (по умолчанию)'
    
    _in_var  = tk.StringVar(value='⌛ Сканирование...')
    _out_var = tk.StringVar(value='⌛ Сканирование...')
    
    # Placeholders for the async scanner
    _in_map = {_in_default_label: None}
    _out_map = {_out_default_label: ''}

    def _fmt_dev(i: int, name: str) -> str:
        return name.replace('\n', ' ').strip()

    def _dev_count_label(n: int) -> str:
        if n == 0: return 'Устройства не обнаружены'
        return f'Найдено устройств: {n}'

    _AUD_ICO = hud._px(40)
    _mic_block = tk.Frame(c4, bg=_PANEL)
    _mic_block.pack(fill='x', pady=(2, 0))
    _mic_top = tk.Frame(_mic_block, bg=_PANEL)
    _mic_top.pack(fill='x', pady=(0, 6))
    _in_icon = tk.Frame(_mic_top, bg=_blend(_AMBER, 0.10), highlightbackground=_blend(_AMBER, 0.28), highlightthickness=1, width=_AUD_ICO, height=_AUD_ICO)
    _in_icon.pack(side='left', padx=(0, 10))
    _in_icon.pack_propagate(False)
    tk.Label(_in_icon, text='🎙', bg=_blend(_AMBER, 0.10), fg=_AMBER, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
    
    _in_col = tk.Frame(_mic_top, bg=_PANEL)
    _in_col.pack(side='left', fill='x', expand=True)
    _in_title_row = tk.Frame(_in_col, bg=_PANEL)
    _in_title_row.pack(anchor='w', fill='x')
    
    _in_title_lbl = tk.Label(_in_title_row, text='Микрофон (ввод)', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w')
    _in_title_lbl.pack(side='left')
    
    _live_badge = tk.Frame(_in_title_row, bg=_PANEL)
    _live_badge.pack(side='left', padx=(10, 0)) # Back to side-layout to save space
    tk.Label(_live_badge, text='[', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9))).pack(side='left')
    tk.Label(_live_badge, text='●', bg=_PANEL, fg=_AMBER, font=(hud._F, _sf(7))).pack(side='left', padx=2)
    _live_txt = tk.Label(_live_badge, text='Обновление в реальном времени ]', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8), 'bold'), justify='left')
    _live_txt.pack(side='left')

    def _upd_badge_wrap(e, l=_live_txt):
        if e.width < hud._px(550): # Higher priority wrapping for single line
            l.configure(text='LIVE ]')
        else:
            l.configure(text='Обновление в реальном времени ]')
    _in_col.bind('<Configure>', _upd_badge_wrap)

    _in_count_lbl = tk.Label(_in_col, text='⌛ Поиск...', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)))
    _in_count_lbl.pack(anchor='w')

    _in_m = _HUDDropdown(hud, _mic_block, ['⌛ Ожидание...'], _in_var, lambda _v: _apply_audio_settings(), accent=_AMBER)
    _in_m.frame.pack(fill='x', pady=(6, 12)) # More padding for clarity

    _out_block = tk.Frame(c4, bg=_PANEL)
    _out_block.pack(fill='x', pady=(10, 0))
    _out_top = tk.Frame(_out_block, bg=_PANEL)
    _out_top.pack(fill='x', pady=(0, 6))
    _out_icon = tk.Frame(_out_top, bg=_blend(_MAG, 0.10), highlightbackground=_blend(_MAG, 0.28), highlightthickness=1, width=_AUD_ICO, height=_AUD_ICO)
    _out_icon.pack(side='left', padx=(0, 10))
    _out_icon.pack_propagate(False)
    tk.Label(_out_icon, text='🔊', bg=_blend(_MAG, 0.10), fg=_MAG, font=(hud._F, _sf(14))).place(relx=0.5, rely=0.5, anchor='center')
    
    _out_col = tk.Frame(_out_top, bg=_PANEL)
    _out_col.pack(side='left', fill='x', expand=True)
    tk.Label(_out_col, text='Вывод (голос JARVIS)', bg=_PANEL, fg=_TEXT, font=(hud._F, _sf(10), 'bold'), anchor='w').pack(anchor='w')
    _out_count_lbl = tk.Label(_out_col, text='⌛ Поиск...', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(9)))
    _out_count_lbl.pack(anchor='w')

    _out_m = _HUDDropdown(hud, _out_block, ['⌛ Ожидание...'], _out_var, lambda _v: _apply_audio_settings(), accent=_MAG)
    _out_m.frame.pack(fill='x', pady=(6, 12))

    def _apply_scan_results(ins, outs):
        nonlocal _in_map, _out_map
        _in_map = {_in_default_label: None}
        _in_map.update({n.replace('\n', ' ').strip(): i for (i, n) in ins})
        _out_map = {_out_default_label: ''}
        _out_map.update({n.replace('\n', ' ').strip(): n for (_i, n) in outs})
        
        in_vals = list(_in_map.keys())
        out_vals = list(_out_map.keys())
        
        _in_m.configure(values=in_vals)
        _out_m.configure(values=out_vals)
        
        in_init = next((k for k, v in _in_map.items() if v == _in_idx0), _in_default_label)
        out_init = next((k for k, v in _out_map.items() if v == _out_name0), _out_default_label)
        
        _in_var.set(in_init)
        _out_var.set(out_init)
        _in_count_lbl.configure(text=_dev_count_label(len(ins)))
        _out_count_lbl.configure(text=_dev_count_label(len(outs)))
        _set_aud_status(f'Найдено устройств: {len(ins)} ввод, {len(outs)} вывод', _CYAN)

    def _async_load():
        try:
            _set_aud_status('Поиск аудио-устройств...', _CYAN)
            ins, outs = _list_devices()
            win.after(0, lambda: _apply_scan_results(ins, outs))
        except Exception as e:
            win.after(0, lambda: _set_aud_status(f'Ошибка сканирования: {e}', _RED))

    threading.Thread(target=_async_load, daemon=True).start()

    def _c4_audio_layout(_e=None):
        try:
            w = int(c4.winfo_width() or 0)
            if w > 1:
                _aud_status.configure(wraplength=max(hud._px(100), w - hud._px(24)))
                mw = max(hud._px(260), w - hud._px(56))
                _in_m.configure(width=mw)
                _out_m.configure(width=mw)
        except Exception:
            pass
    c4.bind('<Configure>', lambda e: _c4_audio_layout(e), add='+')
    win.after(80, _c4_audio_layout)
    def _apply_audio_settings():
        s = _load_settings_json()
        sel_in = _in_var.get()
        in_idx = None
        if sel_in in _in_map:
            v = _in_map[sel_in]
            if v is None:
                s.pop('audio_input_device_index', None)
            else:
                in_idx = int(v)
                s['audio_input_device_index'] = in_idx
        sel_out = _out_var.get()
        out_name = None
        if sel_out in _out_map:
            v = _out_map[sel_out]
            if not v:
                s.pop('audio_output_device_name', None)
            else:
                out_name = str(v).strip()
                s['audio_output_device_name'] = out_name
        _save_settings_json(s)
        # Apply the changes live to the running engine
        def _do_apply():
            try:
                from core.speech.tts import apply_audio_devices
                ok, msg = apply_audio_devices(
                    output_device_name=out_name,
                    input_device_index=in_idx,
                )
                col = _GREEN if ok else _AMBER
                win.after(0, lambda: _set_aud_status(msg, col))
            except Exception as e:
                win.after(0, lambda: _set_aud_status(f'⚠ Ошибка применения: {e}', _RED))
        _set_aud_status('⟳ Применяю настройки...', _AMBER)
        threading.Thread(target=_do_apply, daemon=True).start()
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
                            f'🔄 Лучшая частота: {r} Гц — открываю микрофон…', _AMBER),
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
                        msg = (f'🔄 Калибровка завершена — '
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
                    thresh_slider.set(t)
                    gain_slider.set(g)
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
        text='🎙  ТЕСТ И КАЛИБРОВКА',
        width=_btn_w,
        height=hud._px(50),
        font=(hud._F, _sf(10), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_AMBER, 0.12),
        text_color=_AMBER,
        border_color=_AMBER,
        border_width=2,
        corner_radius=10,
        command=_run_calibration_ui,
    ).pack(side='left', padx=10)
    ctk.CTkButton(
        _aud_btn_inner,
        text='🔄  СИНХРОНИЗИРОВАТЬ',
        width=_btn_w,
        height=hud._px(50),
        font=(hud._F, _sf(10), 'bold'),
        fg_color='transparent',
        hover_color=_blend(_GREEN, 0.12),
        text_color=_GREEN,
        border_color=_GREEN,
        border_width=2,
        corner_radius=10,
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
    _on_vol(hud._settings.get('volume', 1.0))
    _slider(c_vol, 0.0, 1.0, 100, _MAG, _cur_vol, _on_vol)

    c_tts = _card('🧠', 'ОПТИМИЗАЦИЯ ПАМЯТИ (TTS)', _CYAN)
    _tts_lbl = _label_row(c_tts, 'Время удержания в ОЗУ', _CYAN)
    
    def _fmt_tout(v):
        v = int(v)
        if v == 0: return "Бессрочно (рекомендуется)"
        if v < 60: return f"{v} сек."
        if v < 3600: return f"{v//60} мин."
        return f"{v//3600} ч."

    _tout_vals = [60, 180, 300, 600, 900, 1800, 3600, 7200, 18000, 0]
    _s_json = _load_settings_json()
    _cur_tout = float(_s_json.get('tts_unload_timeout', 300.0))
    
    def _fmt_tout(v):
        v = int(v)
        if v == 0: return "Бессрочно (рекомендуется)"
        if v < 60: return f"{v} сек."
        if v < 3600: return f"{v//60} мин."
        return f"{v//3600} ч."

    _tts_lbl.configure(text=_fmt_tout(_cur_tout))
    
    _hint(c_tts, 'Выгрузка модели экономит ~300МБ ОЗУ, но вызывает задержку при первом ответе после долгого молчания.')
    _hint(c_tts, 'ℹ В игровом режиме выгрузка автоматически отключается для мгновенной реакции.')

    _tts_save_after = [None]
    def _on_tts_slider(v):
        idx = int(round(float(v)))
        tout = _tout_vals[idx] if idx < len(_tout_vals) else _tout_vals[-1]
        _tts_lbl.configure(text=_fmt_tout(tout))
        
        if _tts_save_after[0]: 
            win.after_cancel(_tts_save_after[0])
            
        def _save():
            sj = _load_settings_json()
            sj['tts_unload_timeout'] = float(tout)
            _save_settings_json(sj)
            try:
                import config_pack.config as _cfg
                _cfg.TTS_UNLOAD_TIMEOUT = float(tout)
            except Exception: pass

        _tts_save_after[0] = win.after(600, _save)

    # Initial slider pos
    _init_idx = 2 # 5 mins
    try:
        # Match current value to closest index
        target = int(_cur_tout)
        if target in _tout_vals:
            _init_idx = _tout_vals.index(target)
        else:
            # Find closest
            _init_idx = min(range(len(_tout_vals)), key=lambda i: abs(_tout_vals[i] - target) if _tout_vals[i] > 0 else 999999)
    except Exception:
        pass
        
    _slider(c_tts, 0, len(_tout_vals)-1, len(_tout_vals)-1, _CYAN, _init_idx, _on_tts_slider)

    def _pick_app_dialog(on_selected):
        """Reusable premium app picker dialog."""
        from core.system.windows import get_installed_apps
        apps = get_installed_apps()
        pick_win = ctk.CTkToplevel(win)
        pick_win.title("ВЫБОР ПРИЛОЖЕНИЯ")
        pick_win.geometry(f"{hud._px(600)}x{hud._px(700)}")
        pick_win.configure(bg=_BG)
        _set_dark_title_bar(pick_win)
        pick_win.attributes("-topmost", True)
        pick_win.lift()
        top_bar = tk.Frame(pick_win, bg=_BG)
        top_bar.pack(fill='x', padx=20, pady=(20, 10))
        tk.Label(top_bar, text="ВЫБЕРИТЕ ПРИЛОЖЕНИЕ", bg=_BG, fg=_CYAN, font=(hud._F, _sf(14), 'bold')).pack(anchor='w')
        tk.Label(top_bar, text="Выберите программу для добавления в список", bg=_BG, fg=_DIM, font=(hud._F, _sf(10))).pack(anchor='w')
        ctrl_f = tk.Frame(pick_win, bg=_BG)
        ctrl_f.pack(fill='x', padx=20, pady=(15, 10))
        ent_search = ctk.CTkEntry(ctrl_f, placeholder_text='Поиск...', font=(hud._F, _sf(11)), fg_color=_BG, border_color=_blend(_CYAN, 0.3), height=hud._px(44), corner_radius=10)
        ent_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
        _show_all_var = tk.BooleanVar(value=False)
        sw_all = ctk.CTkSwitch(ctrl_f, text='Системные', variable=_show_all_var, font=(hud._F, _sf(10), 'bold'), progress_color=_CYAN, fg_color=_BRD_I, button_color=_WHITE, switch_width=hud._px(36), switch_height=hud._px(18))
        sw_all.pack(side='right')
        lb_frame = tk.Frame(pick_win, bg=_BG, highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
        lb_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))
        lb = tk.Listbox(lb_frame, bg=_BG, fg=_TEXT, font=(hud._F, _sf(11)), borderwidth=0, highlightthickness=0, selectbackground=_blend(_CYAN, 0.3), activestyle='none')
        sb = _HudScrollbar(lb_frame, lb, color=_CYAN)
        lb.config(yscrollcommand=sb.set)
        lb.pack(side='left', fill='both', expand=True, padx=8, pady=8)
        _f_data = []
        def _refresh(*_):
            lb.delete(0, tk.END)
            search = ent_search.get().lower().strip()
            show_all = _show_all_var.get()
            _f_data.clear()
            ides = [a for a in apps if a.get('is_ide')]
            others = [a for a in apps if not a.get('is_ide')]
            for app in ides + others:
                if app.get('is_noise') and not show_all: continue
                if search and search not in app['name'].lower() and search not in (app.get('exe') or '').lower(): continue
                prefix = "✦ " if app.get('is_ide') else "  "
                exe_part = f" — {app['exe']}" if app.get('exe') else ""
                lb.insert(tk.END, f"{prefix}{app['name']}{exe_part}")
                _f_data.append(app)
        ent_search.bind('<KeyRelease>', _refresh)
        sw_all.configure(command=_refresh)
        _refresh()
        def _on_pick(_e=None):
            sel = lb.curselection()
            if sel:
                app = _f_data[sel[0]]
                on_selected(app.get('exe') or app['name'])
                pick_win.destroy()
        lb.bind('<Double-Button-1>', _on_pick)
        ctk.CTkButton(pick_win, text="ВЫБРАТЬ ПРИЛОЖЕНИЕ", command=_on_pick, height=hud._px(50), font=(hud._F, _sf(12), 'bold'), fg_color=_CYAN, text_color=_BG).pack(fill='x', padx=20, pady=(0, 20))

