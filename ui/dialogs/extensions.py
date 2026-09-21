from __future__ import annotations
from core import i18n
from ui.hud_style import JStyle
import json, os, threading, time
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM, _GRID, _DYN, _STA, _RU_MON, _RU_DAYS
from ..hud_state import HudState, STATE, set_mode
from ..hud_utils import _blend, _bar_color, _set_dark_title_bar, _apply_window_icon, _center_window, _place_dialog
from ..hud_widgets import _HudScrollbar
from core.extensions import ExtensionManager
from .extensions_common import _load_settings, _save_settings, _save_env_key, _set_feature_module_flag, _load_game_commands
from .extensions_setup import _ask_chat_id, _ask_calendar_setup, _ask_mail_setup, _open_commands_help, _ask_ets2_ai_setup

def open_extensions(hud, reopen: bool = False) -> None:
    if not reopen and hasattr(hud, '_ext_win') and hud._ext_win and hud._ext_win.winfo_exists():
        hud._ext_win.lift()
        return
    if reopen and hasattr(hud, '_ext_win') and hud._ext_win and hud._ext_win.winfo_exists():
        hud._ext_win.destroy()
    win = tk.Toplevel(hud.root)
    hud._ext_win = win
    win.title(i18n.tr('extensions.win_title'))
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    hud._track_subwin('extensions', win, lambda: open_extensions(hud, reopen=True))

    ext_mgr = ExtensionManager()

    ext_mgr.reload()


    win.iconbitmap(hud._ico_path) if hasattr(hud, '_ico_path') else None
    win.configure(bg=_BG); win.after(150, lambda: _set_dark_title_bar(win))  # type: ignore[call-arg]
    _sw_scr = win.winfo_screenwidth()
    _sh_scr = win.winfo_screenheight()
    win.maxsize(_sw_scr, _sh_scr)
    
    _W = int(min(1100 * hud.zoom_factor, _sw_scr * 0.9))
    _H = int(min(800 * hud.zoom_factor, _sh_scr * 0.9))
    win.geometry(f"{_W}x{_H}")
    win.resizable(True, True)
    win.minsize(hud._px(820), hud._px(680))
    
    def _recenter():
        win.update_idletasks()
        rw, rh = win.winfo_width(), win.winfo_height()
        _center_window(win, rw, rh)
    win._recenter = _recenter
    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')
    header_area = tk.Frame(win, bg=_BG)
    header_area.pack(fill='x', padx=24, pady=(16, 0))
    title_f = tk.Frame(header_area, bg=_BG)
    title_f.pack(side='top', fill='x', anchor='w')
    tk.Label(title_f, text=i18n.tr('extensions.title'), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_H1, 'bold')).pack(anchor='w')
    tk.Label(title_f, text=i18n.tr('extensions.subtitle'), bg=_BG, fg=_DIM, font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(anchor='w')
    
    search_entry = ctk.CTkEntry(
        header_area,
        placeholder_text=i18n.tr('extensions.search_placeholder'),
        height=34,
        font=("Consolas", 12),
        fg_color=_PANEL, 
        border_color=_blend(_CYAN, 0.3),
        text_color=_TEXT,
        placeholder_text_color=_DIM,
        corner_radius=JStyle.RAD_PANEL,
        border_width=1
    )
    search_entry.pack(side='top', fill='x', pady=(16, 8))
    
    def _on_search_change(e):
        _refresh_cards(search_entry.get())
    search_entry.bind('<KeyRelease>', _on_search_change)

    tk.Frame(win, bg=_SEP, height=1).pack(fill='x', padx=24, pady=(16, 8))
    canvas = tk.Canvas(win, bg=_BG, highlightthickness=0)
    for i in range(0, 800, 40):
        canvas.create_line(i, 0, i, 1000, fill=_blend(_BG, 1.1), width=1)
        canvas.create_line(0, i, 800, i, fill=_blend(_BG, 1.1), width=1)
    sb = _HudScrollbar(win, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side='left', fill='both', expand=True, padx=24, pady=(0, 20))
    inner = tk.Frame(canvas, bg=_BG)
    _cwin = canvas.create_window((0, 0), window=inner, anchor='nw')
    def _update_scroll(*_):
        try:
            if canvas.winfo_exists():
                canvas.configure(scrollregion=canvas.bbox('all'))
        except (tk.TclError, AttributeError):
            pass
    _desc_labels = []
    _header_mode = None # 'small' or 'large'
    def _on_resize(e):
        try:
            if not win.winfo_exists(): return
            if e.widget != win: return
            
            # Update canvas item width
            if canvas.winfo_exists():
                canvas.itemconfig(_cwin, width=max(10, e.width - 48))
            
            # Update wraplength for description labels
            new_wrap = int(e.width - 120) 
            for lbl in _desc_labels:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=max(200, new_wrap))
            _update_scroll()
        except (tk.TclError, AttributeError, ValueError):
            pass
    
    win.bind('<Configure>', _on_resize)
    inner.bind('<Configure>', _update_scroll)
    def _on_wheel(e):
        try:
            if canvas.winfo_exists():
                canvas.yview_scroll(-1 * (e.delta // 120), 'units')
        except Exception: pass
    def _bind_wheel(w):
        w.bind('<MouseWheel>', _on_wheel)
        for child in w.winfo_children():
            _bind_wheel(child)
    win.bind('<MouseWheel>', _on_wheel)
    canvas.bind('<MouseWheel>', _on_wheel)
    def _refresh_cards(query=None):
        def _do_ref():
            try:
                if not win.winfo_exists(): return
                for w in inner.winfo_children():
                    w.destroy()
                _build_cards(query if query != 'ПОИСК МОДУЛЯ...' else None)
                _bind_wheel(inner)
                win.after(10, _update_scroll)
                hud._rebuild_left()
            except (tk.TclError, AttributeError):
                pass
        win.after(1, _do_ref)
    def _build_cards(query=None):
        all_exts = ext_mgr.list_all()
        categories: dict[str, list[dict]] = {}
        for e_item in all_exts:
            if query and query.lower() not in e_item.get('name', '').lower():
                continue
            cat = e_item.get('category', 'Прочее')
            categories.setdefault(cat, []).append(e_item)
        for cat_name, items in categories.items():
            cat_f = tk.Frame(inner, bg=_BG)
            cat_f.pack(fill='x', pady=(22, 12))
            tk.Label(cat_f, text=cat_name.upper(), bg=_BG, fg=_CYAN, font=(hud._F, JStyle.TEXT_SMALL, 'bold')).pack(side='left', padx=(4, 10))
            tk.Frame(cat_f, bg=_SEP, height=1).pack(side='left', fill='x', expand=True, pady=4)
            for e_item in items:
                _make_card(e_item['id'], e_item)
    def _make_card(eid: str, meta: dict):
        installed = ext_mgr.is_installed(eid)
        bundled = ext_mgr.is_bundled(eid)
        brd_col_idle = _blend(_CYAN, 0.15) if not installed else _blend(_CYAN, 0.4)
        brd_col_active = _CYAN
        card = ctk.CTkFrame(inner, fg_color=_PANEL, border_color=brd_col_idle, border_width=1, corner_radius=JStyle.RAD_PANEL)
        card.pack(fill='x', pady=10, padx=10)
        
        strip_f = tk.Frame(card, bg=_BG, width=4)
        strip_f.pack(side='left', fill='y')
        tk.Frame(strip_f, bg=_CYAN if installed else _SEP).pack(fill='both', expand=True)
        
        body = tk.Frame(card, bg=_PANEL)
        body.pack(side='left', fill='both', expand=True, padx=16, pady=16)
        head = tk.Frame(body, bg=_PANEL)
        head.pack(fill='x')
        
        title_l = tk.Label(head, text=f'★  {meta["name"]}', bg=_PANEL, fg=_CYAN if installed else _TEXT, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='w')
        title_l.pack(side='left')
        
        if installed:
            badge_text, badge_col = (i18n.tr('extensions.installed'), _CYAN)
        elif bundled:
            badge_text, badge_col = (i18n.tr('extensions.ready'), _AMBER)
        else:
            badge_text, badge_col = (i18n.tr('extensions.cloud'), _DIM)
        badge_l = tk.Label(head, text=badge_text, bg=_PANEL, fg=badge_col, font=(hud._F, JStyle.TEXT_TINY, 'bold'))
        badge_l.pack(side='right')

        desc_l = tk.Label(body, text=meta.get('description', ''), bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL), anchor='w', wraplength=int(480*hud.zoom_factor), justify='left')
        desc_l.pack(fill='x', pady=(4, 10))
        _desc_labels.append(desc_l)

        actions_outer = tk.Frame(body, bg=_PANEL)
        actions_outer.pack(fill="x", pady=(8, 0))
        
        inner_row = tk.Frame(actions_outer, bg=_PANEL)
        inner_row.pack(side="right")

        hover_bg = _blend(_CYAN, 0.05)
        def _on_enter(e, c=card, bd=body, h=head, t=title_l, bl=badge_l, d=desc_l, ao=actions_outer, ir=inner_row):
            c.configure(border_color=brd_col_active, fg_color=hover_bg)  # type: ignore[call-arg]
            for w in [bd, h, t, bl, d, ao, ir]: w.configure(bg=hover_bg)  # type: ignore[call-arg]
            if not installed: bl.configure(fg=_CYAN)
        def _on_leave(e, c=card, bd=body, h=head, t=title_l, bl=badge_l, d=desc_l, ao=actions_outer, ir=inner_row):
            c.configure(border_color=brd_col_idle, fg_color=_PANEL)  # type: ignore[call-arg]
            for w in [bd, h, t, bl, d, ao, ir]: w.configure(bg=_PANEL)  # type: ignore[call-arg]
            if not installed: bl.configure(fg=badge_col)
        
        for w in [card, body, head, title_l, badge_l, desc_l, actions_outer, inner_row]:
            w.bind('<Enter>', _on_enter, add='+')
            w.bind('<Leave>', _on_leave, add='+')

        has_catalog_cmds = bool(meta.get("commands"))
        is_game = meta.get("type") == "game_profile"
        
        if has_catalog_cmds or is_game:
            def _show_cmds(m=meta):
                if is_game and not m.get("commands"):
                    m["commands"] = _load_game_commands(m.get("file", ""))
                _open_commands_help(win, hud, m)
            # Единая ширина для всех кнопок для симметрии
            btn_w = 160
            ctk.CTkButton(
                inner_row, text=i18n.tr('extensions.commands'), width=btn_w, font=("Consolas", 12, "bold"), height=JStyle.H_LARGE,
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.2), text_color=_CYAN,
                border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_show_cmds,
            ).pack(side="left", padx=5)

        if installed:
            def _do_uninstall(e=eid):
                ext_mgr.uninstall(e); _refresh_cards()

            ctk.CTkButton(
                inner_row, text=i18n.tr('extensions.uninstall'), width=160, font=("Consolas", 12, 'bold'), height=JStyle.H_LARGE,
                fg_color=_PANEL, hover_color=_blend(_RED, 0.2), text_color=_RED,
                border_color=_blend(_RED, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_do_uninstall
            ).pack(side="left", padx=5)
            
            if eid == 'feature_calendar_ics':
                def _reconfig_cal(): _ask_calendar_setup(win, hud, _refresh_cards)
                ctk.CTkButton(inner_row, text=i18n.tr('extensions.settings'), width=160, font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE, fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_reconfig_cal).pack(side="left", padx=8)
            elif eid == 'feature_mail_client':
                def _reconfig_mail(): _ask_mail_setup(win, hud, _refresh_cards)
                ctk.CTkButton(inner_row, text=i18n.tr('extensions.settings'), width=160, font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE, fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN, border_color=_blend(_CYAN, 0.3), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_reconfig_mail).pack(side="left", padx=8)
            elif eid == 'game_planetbase':
                try:
                    from features.planetbase.installer import find_planetbase_path
                    pb_path = find_planetbase_path()
                    managed = pb_path / "Planetbase_Data" / "Managed" if pb_path else None
                    mod_ok = managed is not None and (managed / "Assembly-CSharp.bak").exists() and (managed / "PlanetbaseTelemetry.dll").exists()
                except Exception:
                    mod_ok = False

                is_uk = (i18n.get_language() == 'uk')
                if mod_ok:
                    m_text = "✓ МОД: АКТИВНИЙ" if is_uk else "✓ МОД: АКТИВЕН"
                    m_col  = _CYAN
                else:
                    m_text = "⬇ МОД: ПОТРІБЕН" if is_uk else "⬇ МОД: ТРЕБУЕТСЯ"
                    m_col  = _AMBER

                def _do_pb_mod_install():
                    import threading as _th
                    def _run():
                        try:
                            from features.planetbase.installer import ensure_installed
                            ensure_installed()
                        except Exception:
                            pass
                        try: win.after(0, _refresh_cards)
                        except Exception: pass
                    _th.Thread(target=_run, daemon=True).start()

                ctk.CTkButton(
                    inner_row, text=m_text,
                    width=160, font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE,
                    fg_color=_PANEL, hover_color=_blend(m_col, 0.2), text_color=m_col,
                    border_color=_blend(m_col, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL,
                    command=_do_pb_mod_install
                ).pack(side="left", padx=5)

            elif eid == 'game_ets2':
                try:
                    from actions.ets2_telemetry_installer import is_telemetry_installed
                    tele_ok = is_telemetry_installed()
                except Exception: tele_ok = False
                
                # Explicit status for Telemetry Plugin (DLL/Library)
                is_uk = (i18n.get_language() == 'uk')
                if is_uk:
                    t_text = "✓ DLL: АКТИВНА" if tele_ok else "⬇ DLL: ПОТРІБНА"
                else:
                    t_text = "✓ DLL: АКТИВНА" if tele_ok else "⬇ DLL: ТРЕБУЕТСЯ"
                t_col = _CYAN if tele_ok else _AMBER
                
                def _do_dll_install():
                    try:
                        from actions.ets2_telemetry_installer import run_installer
                        run_installer(tk_root=win, on_done=lambda r: _refresh_cards())
                    except Exception: pass

                ctk.CTkButton(
                    inner_row, text=t_text,
                    width=160, font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE,
                    fg_color=_PANEL, hover_color=_blend(t_col, 0.2), text_color=t_col,
                    border_color=_blend(t_col, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL,
                    command=_do_dll_install
                ).pack(side="left", padx=5)

                try:
                    from features.ets2.llm import has_api_key as _ets2_has_key
                    if _ets2_has_key():
                        _s_ai = _load_settings()
                        _ai_on = _s_ai.get('ets2_llm_enabled', True)
                        _ai_text = ("◉ AI: УВМ" if _ai_on else "◎ AI: ВИМК") if is_uk else ("◉ AI: ВКЛ" if _ai_on else "◎ AI: ВЫКЛ")
                        _ai_col = _CYAN if _ai_on else _DIM
                        def _toggle_ets2_ai():
                            _s = _load_settings()
                            _s['ets2_llm_enabled'] = not _s.get('ets2_llm_enabled', True)
                            _save_settings(_s)
                            _refresh_cards()
                        ctk.CTkButton(
                            inner_row, text=_ai_text, width=130,
                            font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE,
                            fg_color=_PANEL, hover_color=_blend(_ai_col, 0.2), text_color=_ai_col,
                            border_color=_blend(_ai_col, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL,
                            command=_toggle_ets2_ai,
                        ).pack(side="left", padx=5)
                except Exception:
                    pass
        elif bundled:
            def _do_install(e=eid, m=meta):
                if m.get('requires_chat_id'):
                    if os.environ.get('TELEGRAM_CHAT_ID'):
                        ext_mgr.install(e); _refresh_cards()
                    else:
                        _ask_chat_id(win, hud, lambda cid: (_save_env_key('TELEGRAM_CHAT_ID', cid), ext_mgr.install(e), _refresh_cards()))
                elif e == 'feature_mail_client':
                    s_m = _load_settings(); ma_m = s_m.get('mail_account')
                    if isinstance(ma_m, dict) and str(ma_m.get('email', '')).strip():
                        ext_mgr.install(e); _set_feature_module_flag('inbox_digest', True); _refresh_cards()
                    else: _ask_mail_setup(win, hud, lambda: (ext_mgr.install(e), _set_feature_module_flag('inbox_digest', True), _refresh_cards()))
                elif e == 'game_planetbase':
                    ext_mgr.install(e); _refresh_cards()
                    def _run_pb_installer():
                        import threading as _th
                        def _t():
                            try:
                                from features.planetbase.installer import ensure_installed
                                ensure_installed()
                            except Exception: pass
                            try: win.after(0, _refresh_cards)
                            except Exception: pass
                        _th.Thread(target=_t, daemon=True).start()
                    win.after(300, _run_pb_installer)
                elif e == 'game_ets2':
                    ext_mgr.install(e); _refresh_cards()
                    def _run_dll():
                        try:
                            from actions.ets2_telemetry_installer import run_installer
                            run_installer(tk_root=win)
                        except Exception: pass
                    win.after(200, _run_dll)
                    win.after(1400, lambda: _ask_ets2_ai_setup(win, hud, on_done=_refresh_cards))
                elif e == 'feature_calendar_ics':
                    ext_mgr.install(e); _set_feature_module_flag('calendar_ics', True)
                    if len(_load_settings().get('calendar_sources', [])) > 0: _refresh_cards()
                    else: _ask_calendar_setup(win, hud, _refresh_cards)
                else:
                    ext_mgr.install(e); _refresh_cards()
            ctk.CTkButton(
                inner_row, text=i18n.tr('extensions.install'), width=160, font=("Consolas", 12, 'bold'), height=JStyle.H_LARGE,
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.2), text_color=_CYAN,
                border_color=_blend(_CYAN, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_do_install
            ).pack(side="left", padx=5)
        else:
            def _do_download(e=eid, m=meta):
                def _thread():
                    import urllib.request, zipfile, io; from pathlib import Path
                    try:
                        with urllib.request.urlopen(m.get('download_url')) as resp: data = resp.read()
                        if m.get('download_url').endswith('.zip'):
                            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                                dest = (Path('data') / 'game_profiles').resolve(); dest.mkdir(parents=True, exist_ok=True)
                                for mem in zf.infolist():
                                    if mem.filename.endswith('.json'): zf.extract(mem, dest)
                        m['bundled'] = True; ext_mgr.install(e); 
                        def _done():
                            if win.winfo_exists(): _refresh_cards()
                        win.after(0, _done)
                    except Exception: pass
                threading.Thread(target=_thread, daemon=True).start()
            ctk.CTkButton(
                inner_row, text=i18n.tr('extensions.sync'), width=160, font=("Consolas", 11, 'bold'), height=JStyle.H_LARGE,
                fg_color=_PANEL, hover_color=_blend(_CYAN, 0.15), text_color=_CYAN,
                border_color=_blend(_CYAN, 0.4), border_width=2, corner_radius=JStyle.RAD_PANEL, command=_do_download
            ).pack(side='left', padx=5)
    _build_cards()
    _bind_wheel(inner)
    _recenter()
    win.after(20, _update_scroll)
    tk.Frame(win, bg=_GREEN, height=2).pack(fill='x', side='bottom')
