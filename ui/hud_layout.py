from __future__ import annotations
from ui.hud_style import JStyle
import tkinter as tk
import tkinter.font as _tkfont
from .hud_constants import _BG, _PANEL, _BRD, _CYAN, _MAG, _TEXT, _DIM, _SEP, _AMBER, _GREEN, _RED, _BRD_I, _WHITE
from .hud_widgets import _HudScrollbar, section_hdr, bar_row, kv_row, glass_panel, make_hud_btn
from .hud_utils import _make_sun_icon
from core.extensions import ExtensionManager
from core.system import app_state, autostart_enabled, module_enabled
from core import i18n

def tr(key: str, default: str = None) -> str:
    """Локализация текстов HUD"""
    return i18n.tr(f'hud.{key}', default if default is not None else key)

def build_header(hud) -> None:
    _hdr_sm = max(9, min(JStyle.TEXT_SMALL, 12))
    _hdr_lg = max(10, min(JStyle.TEXT_BODY, 16))
    hdr = tk.Frame(hud.root, bg=_BG, height=hud._px(40))
    hdr.pack(fill='x')
    hdr.pack_propagate(False)
    hud._hdr_os_lbl = tk.Label(hdr, text='  JARVIS OS  v1.5', bg=_BG, fg=_TEXT, font=(hud._F, _hdr_sm, 'bold'))
    hud._hdr_os_lbl.pack(side='left', padx=8)
    hud._hdr_time = tk.Label(hdr, text='', bg=_BG, fg=_TEXT, font=(hud._F, _hdr_sm, 'bold'))
    hud._hdr_time.pack(side='right', padx=12)
    hud._hdr_title_lbl = tk.Label(hdr, text='J.A.R.V.I.S.', bg=_BG, fg=_CYAN, font=(hud._F, _hdr_lg, 'bold'))
    hud._hdr_title_lbl.pack(fill='both', expand=True)

def update_header_fonts(hud) -> None:
    _hdr_sm = max(9, min(JStyle.TEXT_SMALL, 12))
    _hdr_lg = max(10, min(JStyle.TEXT_BODY, 16))
    if hasattr(hud, '_hdr_os_lbl') and hud._hdr_os_lbl.winfo_exists():
        hud._hdr_os_lbl.configure(font=(hud._F, _hdr_sm, 'bold'))
    if hasattr(hud, '_hdr_time') and hud._hdr_time.winfo_exists():
        hud._hdr_time.configure(font=(hud._F, _hdr_sm, 'bold'))
    if hasattr(hud, '_hdr_title_lbl') and hud._hdr_title_lbl.winfo_exists():
        hud._hdr_title_lbl.configure(font=(hud._F, _hdr_lg, 'bold'))

def build_left(hud) -> None:
    _scroll_canvas = tk.Canvas(hud._left, bg=_PANEL, highlightthickness=0, bd=0)
    hud._left_scroll = _scroll_canvas
    _vsb = _HudScrollbar(hud._left, _scroll_canvas, color=_CYAN)
    _scroll_canvas.configure(yscrollcommand=_vsb.set)
    _scroll_canvas.pack(side='left', fill='both', expand=True)
    p = tk.Frame(_scroll_canvas, bg=_PANEL)
    _win_id = _scroll_canvas.create_window((0, 0), window=p, anchor='nw')
    
    def _update_scroll(*_):
        hud.root.after(50, _do_update)
        
    def _do_update():
        if not p.winfo_exists(): return
        p.update_idletasks()
        h = p.winfo_reqheight()
        cw = _scroll_canvas.winfo_width()
        ch = _scroll_canvas.winfo_height()
        # Зона прокрутки строго по ширине канваса (запрет горизонтального скролла)
        _scroll_canvas.configure(scrollregion=(0, 0, cw, max(h, ch)))
        
    def _on_canvas_cfg(e):
        # 🔥 ФИКС ШИРИНЫ: Берём реальную физическую ширину холста, 
        # игнорируя параметр e.width, который может быть равен 0 при "холостых" событиях
        cw = _scroll_canvas.winfo_width()
        if cw > 10:
            _scroll_canvas.itemconfig(_win_id, width=cw)
        _update_scroll()
        
    p.bind('<Configure>', _update_scroll)
    _scroll_canvas.bind('<Configure>', _on_canvas_cfg)
    _scroll_canvas.yview_moveto(0)
    
    if hud._widget_vis.get('sysinfo', True):
        section_hdr(hud, p, tr('system_profiles'), _CYAN, pady=(2, 6))
        _dummy_cpu = tk.Label(p, text='', bg=_PANEL)
        hud._cpu_bar = _dummy_cpu
        hud._cpu_val = _dummy_cpu
        hud._gpu_container = tk.Frame(p, bg=_PANEL)
        hud._gpu_container.pack(fill='x')
        hud._gpu_bar, hud._gpu_val, hud._gpu_bar_frame = bar_row(hud, hud._gpu_container, 'ТЕМПЕРАТУРА ВИДЕОКАРТЫ', _AMBER)
        for child in hud._gpu_container.winfo_children():
            child.pack_forget()
        hud._gpu_bar_visible = False
        
        hud._bat_section = tk.Frame(p, bg=_PANEL)
        hud._bat_section.pack(fill='x')
        
        sub_p = tk.Frame(hud._bat_section, bg=_PANEL)
        sub_p.pack(fill='x', padx=14, pady=(2, 0))
        tk.Label(sub_p, text='◈ ДОСТУП К ПИТАНИЮ', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w').pack(fill='x', pady=(2, 0))
        tk.Frame(sub_p, bg=_GREEN, height=1).pack(fill='x', pady=(0, 6))
        
        _bat_txt = 'ЗАРЯД БАТАРЕИ' if hud.zoom_factor > 1.8 else 'УРОВЕНЬ ЗАРЯДА БАТАРЕИ'
        hud._bat_bar, hud._bat_val, hud._bat_bar_frame = bar_row(hud, hud._bat_section, _bat_txt, _GREEN)
        hud._bat_lbl = tk.Label(hud._bat_section, text='', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'))
        hud._bat_lbl.pack(anchor='e', padx=18, pady=(2, 6))
        hud._bat_visible = True
        
        try:
            from core.mic_calibration import load_profile as _lmp
            _mp0 = _lmp()
            _thresh_display = str(_mp0.get('threshold', '—'))
            _gain_display = f'×{float(_mp0.get("gain", 2.5)):.1f}'
        except Exception:
            _thresh_display, _gain_display = ('—', '—')
            
        if hud._widget_vis.get('sysinfo_mic', True):
            _mic_card = tk.Frame(p, bg=_PANEL, highlightbackground=_SEP, highlightthickness=1)
            _mic_card.pack(fill='x', padx=14, pady=(6, 12))
            tk.Frame(_mic_card, bg=_CYAN, width=4).pack(side='left', fill='y')
            _mic_inner = tk.Frame(_mic_card, bg=_PANEL)
            _mic_inner.pack(side='left', fill='x', expand=True, padx=6, pady=10)
            
            # Постоянно короткий заголовок для надежности
            tk.Label(_mic_inner, text=tr('microphone_short'), bg=_PANEL, fg=_CYAN, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w').pack(fill='x', pady=(0, 4))
            
            _mic_vals = tk.Frame(_mic_inner, bg=_PANEL)
            _mic_vals.pack(fill='x')
            tk.Label(_mic_vals, text=tr('gain'), bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(side='left')
            hud._mic_gain_lbl = tk.Label(_mic_vals, text=_gain_display, bg=_PANEL, fg=_WHITE, font=(hud._F, JStyle.TEXT_BODY, 'bold'))
            hud._mic_gain_lbl.pack(side='left', padx=(4, 8))
            tk.Label(_mic_vals, text=tr('threshold'), bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_TINY, 'bold')).pack(side='left')
            hud._mic_thresh_lbl = tk.Label(_mic_vals, text=_thresh_display, bg=_PANEL, fg=_AMBER, font=(hud._F, JStyle.TEXT_BODY, 'bold'))
            hud._mic_thresh_lbl.pack(side='left', padx=(4, 0))
        else:
            hud._mic_thresh_lbl = tk.Label(p)
            hud._mic_gain_lbl = tk.Label(p)
    else:
        _dummy = tk.Label(p, text='', bg=_PANEL)
        hud._cpu_bar = _dummy
        hud._cpu_val = _dummy
        hud._gpu_container = tk.Frame(p, bg=_PANEL)
        hud._gpu_bar = _dummy
        hud._gpu_val = _dummy
        hud._gpu_bar_visible = False
        hud._bat_section = tk.Frame(p, bg=_PANEL)
        hud._bat_bar = _dummy
        hud._bat_val = _dummy
        hud._bat_lbl = _dummy
        hud._bat_visible = False
        hud._mic_thresh_lbl = _dummy
        hud._mic_gain_lbl = _dummy
        
    _ext = ExtensionManager()
    if hud._widget_vis.get('camera', True):
        section_hdr(hud, p, 'ВИДЕОСЕНСОР ', _CYAN, pady=(12, 4))
        cam_outer = tk.Frame(p, bg=_BRD_I, highlightthickness=0)
        cam_outer.pack(fill='x', padx=14, pady=(2, 6))
        _cam_w = hud._panel_w_left - 28
        _cam_h = min(hud._px(220), int(_cam_w * 3 / 4))
        cam_inner = tk.Frame(cam_outer, bg=_BG, width=_cam_w, height=_cam_h, highlightthickness=0)
        cam_inner.pack()
        cam_inner.pack_propagate(False)
        hud._cam_placeholder = tk.Canvas(cam_inner, bg=_BG, highlightthickness=0)
        hud._cam_placeholder.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        hud._vis_box = hud._cam_placeholder
        hud._draw_cam_standby()
        tk.Frame(p, bg=_PANEL, height=4).pack()
        hud._cam_btn = make_hud_btn(hud, p, 'АКТИВИРОВАТЬ ВИДЕОСЕНСОР ', '⦿', _CYAN, hud._toggle_cam, icon_fs=22)
    else:
        hud._cam_placeholder = None
        hud._cam_btn = None
        
    section_hdr(hud, p, tr('commands'), _MAG, pady=(14, 10))
    make_hud_btn(hud, p, tr('system_monitor'), '▦', _GREEN, hud._open_perf_monitor, icon_fs=24)
    make_hud_btn(hud, p, 'БАЗА КОМАНД', '◈', _MAG, hud._open_deck, icon_fs=24)
    make_hud_btn(hud, p, 'НАСТРОЙКИ СИСТЕМЫ', '⚙', _CYAN, hud._open_settings, icon_fs=16)
    make_hud_btn(hud, p, 'ЦЕНТР РАСШИРЕНИЙ', '⬡', _RED, hud._open_extensions, icon_fs=24)
    if module_enabled('inbox_digest') and _ext.is_installed('feature_mail_client'):
        make_hud_btn(hud, p, 'ПОЧТА', '✉', _CYAN, hud._open_mail, icon_fs=22)
    if hud._widget_vis.get('meetings_btn', True):
        from actions.meetings import get_meetings as _get_meetings
        if _get_meetings():
            def _open_meetings(h=hud):
                from .dialogs.manage_dlg import open_meetings_manager
                open_meetings_manager(h)
            hud._meetings_btn_frame = make_hud_btn(hud, p, 'БЫСТРЫЕ ССЫЛКИ', '🔗', _GREEN, _open_meetings, icon_fs=18)
    if hud._widget_vis.get('videos_btn', True):
        import os as _os
        _vp = _os.path.join(_os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')
        if _os.path.exists(_vp) and _os.path.getsize(_vp) > 0:
            def _open_videos(h=hud):
                from .dialogs.manage_dlg import open_videos_manager
                open_videos_manager(h)
            hud._videos_btn_frame = make_hud_btn(hud, p, 'СОХРАНЁННЫЕ ВИДЕО', '▶', _CYAN, _open_videos, icon_fs=20)
            
    _as_on = autostart_enabled()
    hud._autostart_btn = make_hud_btn(hud, p, 'АВТОЗАПУСК СИСТЕМЫ', '◉' if _as_on else '○', _GREEN if _as_on else _DIM, hud._toggle_autostart, icon_fs=24)
    _has_spells = _ext.has_feature('spells')
    _has_bindings = _ext.has_feature('bindings')
    if (_has_spells or _has_bindings) and hud._widget_vis.get('gamemode', True):
        section_hdr(hud, p, 'ИГРОВОЙ РЕЖИМ', _AMBER, pady=(14, 10))
        if _has_spells:
            make_hud_btn(hud, p, 'РЕДАКТОР ПАТТЕРНОВ', '✦', _AMBER, hud._open_spell_editor, icon_fs=20)
        if _has_bindings:
            hud._keybind_btn_frame = make_hud_btn(hud, p, 'МАКРОСЫ КЛАВИШ', '⌨', _AMBER, hud._open_keybind_editor, icon_fs=20)
    tk.Frame(p, bg=_PANEL, height=10).pack()

def build_center(hud) -> None:
    hud._top_rise = '—:—'
    hud._top_set = '—:—'
    hud._top_pct = 0.0
    hud._top_week = '—'
    hud._top_day = '—/—'
    hud._top_pct_str = '0%'
    _ico_sz = max(32, int(42 * hud._ui_scale))
    hud._rise_icon_img = _make_sun_icon(_ico_sz, rising=True)
    hud._set_icon_img = _make_sun_icon(_ico_sz, rising=False)
    _ch = hud._px(120)
    hud._top_canvas = tk.Canvas(hud._mid, bg=_BG, highlightthickness=0, height=_ch)
    hud._top_canvas.pack(fill='x')
    hud._top_canvas.bind('<Configure>', hud._draw_top_strip)
    hud._top_sep = tk.Frame(hud._mid, bg=_BRD, height=1)
    hud._top_sep.pack(fill='x')
    hud._canvas = tk.Canvas(hud._mid, bg=_BG, highlightthickness=0)
    hud._canvas.pack(fill='both', expand=True)
    hud._canvas.bind('<Configure>', hud._on_resize)
    hud._bot_strip = tk.Frame(hud._mid, bg=_BG, height=hud._px(48))
    hud._bot_strip.pack(fill='x', side='bottom')
    hud._bot_strip.pack_propagate(False)
    tk.Frame(hud._bot_strip, bg=_BRD_I, height=1).pack(fill='x', side='top')
    hud._left_toggle.pack(in_=hud._bot_strip, side='left', padx=(10, 5))
    hud._right_toggle.pack(in_=hud._bot_strip, side='right', padx=(5, 10))
    
    hud._bot_canvas = tk.Canvas(hud._bot_strip, bg=_BG, highlightthickness=0)
    hud._bot_canvas.pack(side='left', fill='both', expand=True)
    hud._bot_canvas.bind('<Configure>', hud._draw_bot_strip)
    
    hud._bot_items = []

def build_right(hud) -> None:
    _scroll_canvas = tk.Canvas(hud._right, bg=_PANEL, highlightthickness=0, bd=0)
    hud._right_scroll = _scroll_canvas
    _vsb = _HudScrollbar(hud._right, _scroll_canvas, color=_MAG)
    _scroll_canvas.configure(yscrollcommand=_vsb.set)
    _scroll_canvas.pack(side='left', fill='both', expand=True)
    p = tk.Frame(_scroll_canvas, bg=_PANEL)
    _win_id = _scroll_canvas.create_window((0, 0), window=p, anchor='nw')
    
    def _update_scroll(*_):
        hud.root.after(50, _do_update)
        
    def _do_update():
        if not p.winfo_exists(): return
        p.update_idletasks()
        h = p.winfo_reqheight()
        cw = _scroll_canvas.winfo_width()
        ch = _scroll_canvas.winfo_height()
        _scroll_canvas.configure(scrollregion=(0, 0, cw, max(h, ch)))
        
    def _on_canvas_cfg(e):
        # 🔥 ТОТ ЖЕ ФИКС ДЛЯ ПРАВОЙ ПАНЕЛИ
        cw = _scroll_canvas.winfo_width()
        if cw > 10:
            _scroll_canvas.itemconfig(_win_id, width=cw)
        _update_scroll()
        
    p.bind('<Configure>', _update_scroll)
    _scroll_canvas.bind('<Configure>', _on_canvas_cfg)
    _scroll_canvas.yview_moveto(0)
    
    if hud._widget_vis.get('storage', True):
        section_hdr(hud, p, tr('storage_analytics'), _MAG, pady=(0, 4))
        tk.Label(p, text=tr('storage_analytics'), bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w').pack(fill='x', padx=14, pady=(6, 2))
        hud._ram_bar, hud._ram_val, hud._ram_bar_frame = bar_row(hud, p, tr('memory_ram'), _MAG)
        hud._ram_det = tk.Label(p, text='', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'))
        hud._ram_det.pack(anchor='e', padx=18)
        hud._dsk_bar, hud._dsk_val, hud._dsk_bar_frame = bar_row(hud, p, tr('disk_storage'), _GREEN)
        hud._dsk_det = tk.Label(p, text='', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'))
        hud._dsk_det.pack(anchor='e', padx=18)
    else:
        _dummy = tk.Label(p, text='', bg=_PANEL)
        hud._ram_bar = _dummy
        hud._ram_val = _dummy
        hud._dsk_bar = _dummy
        hud._dsk_val = _dummy
        hud._ram_det = _dummy
        hud._dsk_det = _dummy
        
    if hud._widget_vis.get('network', True):
        _mic_txt = tr('network_stats') if hud.zoom_factor <= 1.8 else tr('network_stats_short')
        section_hdr(hud, p, _mic_txt, _CYAN)
        
        if hud._widget_vis.get('network_ip', True):
            hud._ip_v = kv_row(hud, p, tr('local_ip'), _CYAN)
        else:
            hud._ip_v = tk.Label(p)

        if hud._widget_vis.get('network_ssid', True):
            hud._ssid_v = kv_row(hud, p, tr('wifi_network'), _AMBER)
        else:
            hud._ssid_v = tk.Label(p)

        if hud._widget_vis.get('network_ls', True):
            hud._ls_v = kv_row(hud, p, tr('link_speed'), _GREEN)
        else:
            hud._ls_v = tk.Label(p)

        if hud._widget_vis.get('network_traffic', True):
            hud._up_v = kv_row(hud, p, tr('upload'), _GREEN)
            hud._dn_v = kv_row(hud, p, tr('download'), _MAG)
        else:
            hud._up_v = tk.Label(p)
            hud._dn_v = tk.Label(p)
    else:
        _dummy = tk.Label(p)
        hud._ip_v = _dummy
        hud._ssid_v = _dummy
        hud._ls_v = _dummy
        hud._up_v = _dummy
        hud._dn_v = _dummy
        
    if hud._widget_vis.get('weather', True):
        section_hdr(hud, p, tr('weather'), _AMBER)
        _wx_outer = tk.Frame(p, bg=_PANEL)
        _wx_outer.pack(fill='x', padx=14, pady=(0, 8))
        _wx_top = tk.Frame(_wx_outer, bg=_PANEL)
        _wx_top.pack(pady=(6, 0))
        hud._wx_icon_lbl = tk.Label(_wx_top, text='?', bg=_PANEL, fg=_AMBER, font=(hud._F, hud._fs(32), 'bold'))
        hud._wx_icon_lbl.pack(side='left', padx=(0, 10))
        _wx_temp_col = tk.Frame(_wx_top, bg=_PANEL)
        _wx_temp_col.pack(side='left')
        hud._wx_temp_lbl = tk.Label(_wx_temp_col, text='—°', bg=_PANEL, fg=_WHITE, font=(hud._F, hud._fs(30), 'bold'), anchor='w')
        hud._wx_temp_lbl.pack(anchor='w')
        hud._wx_feels_lbl = tk.Label(_wx_temp_col, text=tr('feels_like') + ' —°', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='w')
        hud._wx_feels_lbl.pack(anchor='w')
        hud._wx_desc_lbl = tk.Label(_wx_outer, text='—', bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='center', justify='center')
        hud._wx_desc_lbl.pack(fill='x', pady=(4, 0))
        hud._wx_city_lbl = tk.Label(_wx_outer, text='', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_BODY), anchor='center', justify='center')
        hud._wx_city_lbl.pack(fill='x')
        tk.Frame(_wx_outer, bg=_BRD, height=1).pack(fill='x', pady=(8, 6))
        _wx_grid = tk.Frame(_wx_outer, bg=_PANEL)
        _wx_grid.pack(fill='x')
        _wx_grid.columnconfigure(0, weight=1)
        _wx_grid.columnconfigure(1, weight=1)
        _wx_grid.columnconfigure(2, weight=1)
        
        def _wx_cell(parent, row, col, label, color):
            f = tk.Frame(parent, bg=_PANEL)
            f.grid(row=row, column=col, sticky='nsew', padx=2, pady=4)
            lbl = tk.Label(f, text='—', bg=_PANEL, fg=color, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='center', justify='center')
            lbl.pack(fill='x')
            tk.Label(f, text=label, bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_TINY), anchor='center', justify='center').pack(fill='x')
            return lbl
            
        hud._wx_wind_lbl = _wx_cell(_wx_grid, 0, 0, tr('wind'), _CYAN)
        hud._wx_hum_lbl = _wx_cell(_wx_grid, 0, 1, tr('humidity'), _MAG)
        hud._wx_pres_lbl = _wx_cell(_wx_grid, 0, 2, tr('pressure'), _AMBER)
        
    if hud._widget_vis.get('clock', True):
        tk.Frame(p, bg=_SEP, height=1).pack(fill='x', padx=16, pady=8)
        _clk_fs = max(16, min(hud._fs(32), int((hud._panel_w_right - 32) / 5.2)))
        hud._clock_lbl = tk.Label(p, text='00:00:00', bg=_PANEL, fg=_WHITE, font=(hud._F, _clk_fs, 'bold'))
        hud._clock_lbl.pack(fill='x')
        hud._date_lbl = tk.Label(p, text='01 ЯНВАРЯ', bg=_PANEL, fg=_CYAN, font=(hud._F, JStyle.TEXT_BODY, 'bold'))
        hud._date_lbl.pack(fill='x', pady=(0, 4))
        hud._uptime_lbl = tk.Label(p, text='ВРЕМЯ РАБОТЫ: 0ч 00м', bg=_PANEL, fg=_DIM, font=(hud._F, JStyle.TEXT_SMALL, 'bold'))
        hud._uptime_lbl.pack(fill='x', pady=(0, 8))

def apply_widget_visibility(hud) -> None:
    show_sunrise = hud._widget_vis.get('sunrise', True)
    if show_sunrise:
        if not hud._top_canvas.winfo_ismapped():
            hud._top_canvas.pack(fill='x', before=hud._canvas)
        if not hud._top_sep.winfo_ismapped():
            hud._top_sep.pack(fill='x', before=hud._canvas)
    else:
        hud._top_canvas.pack_forget()
        hud._top_sep.pack_forget()

def rebuild_left(hud) -> None:
    if hasattr(hud, '_cam_run') and hud._cam_run:
        hud._cam_run = False
    for w in hud._left.winfo_children():
        w.destroy()
    hud._cam_placeholder = None
    hud._vis_box = None
    hud._cam_btn = None
    build_left(hud)
    
    hud.root.update_idletasks()
    if hasattr(hud, '_left_scroll'):
        hud._left_scroll.yview_moveto(0)

def rebuild_right(hud) -> None:
    for w in hud._right.winfo_children():
        w.destroy()
    build_right(hud)
    
    hud.root.update_idletasks()
    if hasattr(hud, '_right_scroll'):
        hud._right_scroll.yview_moveto(0)
        
    if hasattr(hud, '_last_weather_data') and hud._last_weather_data:
        from . import hud_weather
        hud.root.after(50, lambda: hud_weather.apply_weather(hud, hud._last_weather_data))