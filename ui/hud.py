from __future__ import annotations
import os
import queue as _q_mod
import threading
import psutil
import time
from typing import Optional
import customtkinter as ctk
import tkinter as tk
from core.system import module_enabled
from . import hud_constants as _c
from .hud_constants import _BG, _CYAN, _PANEL, _BRD, _STA
from .hud_state import STATE, HudState
from .hud_utils import _load_hud_settings, _save_hud_settings, _set_dark_title_bar
from . import hud_layout as layout
from . import hud_renderer as renderer
from . import hud_monitoring as monitoring
from . import hud_camera as camera
from . import hud_weather as weather
from . import hud_window as window
_UPDATE_ASR_CALLBACK: callable | None = None
_hud: Optional[JarvisHUD] = None
def show_hud() -> None:
    if _hud is None:
        return
    _hud._hud_queue.put(_hud.root.deiconify)
    _hud._hud_queue.put(_hud.root.lift)
    _hud._hud_queue.put(_hud.root.focus_force)
class JarvisHUD:
    def __init__(self) -> None:
        self._settings = _load_hud_settings()
        self.zoom_factor: float = float(self._settings.get('zoom_factor', 1.0))
        if self.zoom_factor <= 0.0: self.zoom_factor = 1.0

        # Framework scaling MUST be set before or during root creation
        from .hud_themes import get_current_theme_name
        _theme = get_current_theme_name()
        ctk.set_appearance_mode('light' if _theme == 'light' else 'dark')
        ctk.set_default_color_theme('dark-blue')
        ctk.set_widget_scaling(self.zoom_factor)
        ctk.set_window_scaling(self.zoom_factor)
        
        self.root = ctk.CTk()
        from core.system import app_state
        app_state.hud = self
        
        # 1. Hide immediately to prepare geometry
        self.root.withdraw()
        self.root.title('J.A.R.V.I.S. — HUD v1.5')
        self.root.configure(fg_color=_BG)
        _set_dark_title_bar(self.root)
        self.root.minsize(1100, 620)
        
        # 2. Set base geometry THEN request maximization
        self.root.geometry('1280x720')
        if self._settings.get('start_maximized', True):
            try: self.root.state('zoomed')
            except: pass

        # --- Original Initialization Block (Stable) ---
        import sys
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._ico_path = os.path.join(base_path, 'assets', 'icon.ico')
        try:
            if os.path.exists(self._ico_path):
                self.root.iconbitmap(self._ico_path)
        except Exception:
            pass
            
        self.root.protocol('WM_DELETE_WINDOW', self._hide_to_tray)
        self._tray_icon = None
        self._hud_queue: _q_mod.Queue = _q_mod.Queue()
        self._sub_wins: dict[str, callable] = {}
        self._perf_win = None
        self._deck_win = None
        self._settings_win = None
        self._ext_win = None
        self._spell_win = None
        self._keybind_win = None
        self._ui_scale = self._get_dpi_scale()
        self._widget_vis: dict = {**_c._DEFAULT_VIS, **self._settings.get('widget_vis', {})}
        self._panel_w = self._calc_panel_w()
        self._last_weather_data = None
        self._cx = self._cy = 300
        self._tick = 0
        self._cam_run = False
        _cpu_phys = psutil.cpu_count(logical=False) or 2
        _low_perf = _cpu_phys <= 2
        self._PARTICLE_COUNT = 2 if _low_perf else 8
        self._FPS_IDLE = 20 if _low_perf else 30
        self._FPS_ACTIVE = 25 if _low_perf else 40
        _c._LOW_PERF_MODE = _low_perf
        self._sys_lock = threading.Lock()
        self._sys_data: dict = {}
        self._perf_meta: dict = {}
        self._net_t = time.time()
        self._net_prev = psutil.net_io_counters()
        self._top_rise = '—:—'
        self._top_set = '—:—'
        self._top_pct = 0.0
        self._top_week = 'ОЖИДАНИЕ ДАННЫХ'
        self._top_day = '...'
        self._top_pct_str = '0%'
        self._weather_city = '...'
        import collections
        self._perf_history = {k: collections.deque(maxlen=180) for k in [
            'cpu', 'ram', 'dsk_util', 'dsk_read', 'dsk_write',
            'net_up', 'net_dn', 'gpu_util', 'gpu_mem', 'gpu_temp', 'cpu_temp'
        ]}
        import tkinter.font as _tkfont
        _avail = set(_tkfont.families())
        self._F = next((f for f in ('JetBrains Mono', 'Share Tech Mono', 'Fira Code', 'Cascadia Code', 'Consolas') if f in _avail), 'Courier New')
        tk.Frame(self.root, bg=_CYAN, height=2).pack(fill='x', side='top')
        tk.Frame(self.root, bg=_c._MAG, height=2).pack(fill='x', side='bottom')
        layout.build_header(self)
        body = tk.Frame(self.root, bg=_BG)
        body.pack(fill='both', expand=True)
        self._left = layout.glass_panel(self, body, 'left', self._panel_w)
        tk.Frame(body, bg=_BRD, width=1).pack(side='left', fill='y')
        self._right = layout.glass_panel(self, body, 'right', self._panel_w)
        tk.Frame(body, bg=_BRD, width=1).pack(side='right', fill='y')
        self._mid = tk.Frame(body, bg=_BG)
        self._mid.pack(side='left', fill='both', expand=True)
        layout.build_left(self)
        layout.build_center(self)
        layout.build_right(self)
        renderer.draw_static(self)
        renderer.init_anim_objects(self)
        renderer.animate(self)
        if module_enabled('system_monitoring'):
            monitoring.start_perf_collector(self)
            monitoring.start_sys_thread(self)
        monitoring.clock_tick(self)
        monitoring.net_tick(self)
        monitoring.refresh_ip(self)
        monitoring.state_tick(self)
        weather.weather_tick(self)
        self.root.after(50, self._poll_hud_queue)
        self.root.after(200, self._start_tray)
        self.root.after(250, self.root.deiconify)
        self.root.bind_all('<MouseWheel>', self._route_wheel)
        self.root.bind_all('<Control-equal>', lambda e: self._zoom_step(+0.1))
        self.root.bind_all('<Control-plus>', lambda e: self._zoom_step(+0.1))
        self.root.bind_all('<Control-minus>', lambda e: self._zoom_step(-0.1))
        self.root.bind_all('<Control-0>', lambda e: self._zoom_reset())

    def _px(self, n: int) -> int:
        # We scale for internal canvases. CTK widgets will use logical pixels.
        return int(n * self.zoom_factor)
    def _fs(self, n: int) -> int:
        # Standard tk.Labels need font scaling as CTK doesn't auto-scale them.
        return max(6, int(n * self.zoom_factor))
    def _auto_detect_zoom(self) -> float:
        try:
            sw = self.root.winfo_screenwidth()
            # On 4K, sw is usually 3840 (if DPI is 1.0) or logical (~1920 with 2x DPI)
            # Since CTK handles DPI, winfo_screenwidth() returns logical pixels.
            if sw >= 3000: return 2.0
            if sw >= 2000: return 1.5
            if sw >= 1600: return 1.25
            return 1.0
        except Exception:
            return 1.0
    def _get_dpi_scale(self) -> float:
        # Framework handles DPI natively.
        return 1.0
    def _calc_panel_w(self) -> int:
        import tkinter.font as _tf
        try:
            _f10  = _tf.Font(family=self._F, size=self._fs(10), weight='bold')
            _f11  = _tf.Font(family=self._F, size=self._fs(11), weight='bold')
            _f_ico = _tf.Font(family=self._F, size=self._fs(22), weight='bold')
            _btn_texts = [
                'АВТОЗАПУСК СИСТЕМЫ', 'ЦЕНТР РАСШИРЕНИЙ',
                'НАСТРОЙКИ СИСТЕМЫ',  'МОНИТОР СИСТЕМЫ',
            ]
            _ico_w   = _f_ico.measure('▦')
            _btn_w   = max(_f10.measure(t) for t in _btn_texts)
            _btn_total = 8*2 + self._px(14) + _ico_w + self._px(8) + _btn_w + self._px(8)
            _hdr_texts = [
                'КОМАНДЫ И УПРАВЛЕНИЕ', 'СИСТЕМНЫЕ ПРОФИЛИ',
                'АНАЛИТИКА ДАННЫХ',     'СЕТЕВАЯ СТАТИСТИКА',
            ]
            _hdr_total = 8*2 + max(_f11.measure('  ◈ ' + t) for t in _hdr_texts)
            _bar_lbls = ['УРОВЕНЬ ЗАРЯДА БАТАРЕИ', 'ПАМЯТЬ (RAM)', 'ТЕМПЕРАТУРА ВИДЕОКАРТЫ']
            _bar_total = 16*2 + max(_f10.measure(t) for t in _bar_lbls) + self._px(44)
            _key_w = _f10.measure('ЛОКАЛЬНЫЙ IP ')
            _val_w = _f11.measure('000.000.000.000')
            _kv_total = 16*2 + _key_w + _val_w + self._px(8)
            _mic_total = (self._px(14)*2 + 4 + self._px(12)*2 +
                          _f10.measure('✧ МИКРОФОН / ЧУВСТВИТЕЛЬНОСТЬ') + self._px(10))
            _content_w = max(_btn_total, _hdr_total, _kv_total, _mic_total, _bar_total)
        except Exception:
            _content_w = self._px(280)
        sw = self.root.winfo_screenwidth()
        _max_pct = 0.38
        if sw >= 1920: _max_pct = 0.32
        if sw >= 2560: _max_pct = 0.26
        if sw >= 3840: _max_pct = 0.20
        if self.zoom_factor >= 1.8: _max_pct += 0.05
        
        _w = max(self._px(230), min(_content_w + 30, int(sw * _max_pct)))
        # Hard cap for 4K to prevent half-screen buttons
        return min(_w, self._px(550))
    def _poll_hud_queue(self):
        try:
            while not self._hud_queue.empty():
                callback = self._hud_queue.get_nowait()
                if callable(callback):
                    callback()
        except: pass
        _poll_ms = 100 if _c._LOW_PERF_MODE else 50
        self.root.after(_poll_ms, self._poll_hud_queue)
    def _route_wheel(self, e):
        wx, wy = (e.x_root, e.y_root)
        for canvas, panel in ((getattr(self, '_left_scroll', None), self._left), (getattr(self, '_right_scroll', None), self._right)):
            if not canvas: continue
            try:
                px, py = panel.winfo_rootx(), panel.winfo_rooty()
                if px <= wx <= px + panel.winfo_width() and py <= wy <= py + panel.winfo_height():
                    canvas.yview_scroll(-1 * (e.delta // 120), 'units')
                    return
            except: pass
    def _on_resize(self, evt: tk.Event) -> None:
        if evt.width // 2 != self._cx or evt.height // 2 != self._cy:
            self._cx, self._cy = evt.width // 2, evt.height // 2
            renderer.draw_static(self)
            renderer.init_anim_objects(self)
    def _zoom_step(self, delta: float) -> None:
        self.zoom_factor = round(max(0.6, min(2.5, self.zoom_factor + delta)), 1)
        self._settings['zoom_factor'] = self.zoom_factor
        _save_hud_settings(self._settings)
        self._apply_zoom_rebuild()
    def _zoom_reset(self) -> None:
        self.zoom_factor = 1.0
        self._settings['zoom_factor'] = self.zoom_factor
        _save_hud_settings(self._settings)
        self._apply_zoom_rebuild()
    def _apply_zoom_rebuild(self) -> None:
        self.root.update_idletasks()
        self._panel_w = self._calc_panel_w()
        if hasattr(self._left, 'outer'): self._left.outer.configure(width=self._panel_w)
        if hasattr(self._right, 'outer'): self._right.outer.configure(width=self._panel_w)
        self.root.update()
        layout.rebuild_left(self)
        layout.rebuild_right(self)
        layout.update_header_fonts(self)
        renderer.draw_top_strip(self)
        renderer.draw_bot_strip(self)
        for reopen_fn in list(self._sub_wins.values()):
            try: reopen_fn()
            except: pass
    def _apply_widget_visibility(self) -> None:
        layout.apply_widget_visibility(self)
    def show_msg(self, text: str, color: str = _c._CYAN, duration: int = 3000):
        if not hasattr(self, '_hdr_title_lbl') or not self._hdr_title_lbl.winfo_exists():
            return
        orig_text = 'J.A.R.V.I.S.'
        orig_color = _c._CYAN
        self._hdr_title_lbl.configure(text=text.upper(), fg=color)
        def _restore():
            if self._hdr_title_lbl.winfo_exists():
                self._hdr_title_lbl.configure(text=orig_text, fg=orig_color)
        self.root.after(duration, _restore)

    def show_msg_stream(self, text: str, color: str = _c._CYAN):
        """Update header without duration/restore for streaming."""
        if not hasattr(self, '_hdr_title_lbl') or not self._hdr_title_lbl.winfo_exists():
            return
        self._hdr_title_lbl.configure(text=text.upper(), fg=color)

    def hide_msg_stream(self):
        """Manually restore header after stream is finished."""
        if not hasattr(self, '_hdr_title_lbl') or not self._hdr_title_lbl.winfo_exists():
            return
        self._hdr_title_lbl.configure(text='J.A.R.V.I.S.', fg=_c._CYAN)
    def update_jarvis_params(self, threshold: int, gain: float, volume: float):
        if _UPDATE_ASR_CALLBACK:
            _UPDATE_ASR_CALLBACK(threshold, gain, volume)
    def _track_subwin(self, name: str, win: tk.Toplevel, reopen_fn: callable) -> None:
        self._sub_wins[name] = reopen_fn
        win.bind('<Destroy>', lambda e: self._sub_wins.pop(name, None) if str(e.widget) == str(win) else None)
    def _close_other_subwins(self, keep: str | None = None) -> None:
        mapping = {
            'settings': '_settings_win',
            'extensions': '_ext_win',
            'deck': '_deck_win',
            'perf_monitor': '_perf_win',
            'spell_editor': '_spell_win',
            'keybind_editor': '_keybind_win',
            'mail': '_mail_win',
        }
        for key, attr in mapping.items():
            if keep and key == keep:
                continue
            win = getattr(self, attr, None)
            if win is not None and getattr(win, 'winfo_exists', lambda: False)():
                try:
                    win.destroy()
                except Exception:
                    pass
    def _start_tray(self): window.start_tray(self)
    def _hide_to_tray(self, evt=None): window.hide_to_tray(self)
    def _show_main_win(self): window.show_main_win(self)
    def _exit_app(self): window.exit_app(self)
    def _toggle_cam(self): camera.toggle_cam(self)
    def _draw_cam_standby(self): camera.draw_cam_standby(self)
    def _toggle_autostart(self):
        from core.system import autostart_enabled, autostart_set
        on = not autostart_enabled()
        autostart_set(on)
        try: self._autostart_btn.hud_update('АВТОЗАПУСК СИСТЕМЫ', '◉' if on else '○', _c._GREEN if on else _c._DIM)
        except: pass
    def _open_settings(self, reopen=False):
        from .dialogs.settings_dlg import open_settings
        if not reopen:
            self._close_other_subwins(keep='settings')
        open_settings(self, reopen=reopen)
    def _open_perf_monitor(self, reopen=False):
        from .dialogs.perf_monitor import open_perf_monitor
        if not reopen:
            self._close_other_subwins(keep='perf_monitor')
        open_perf_monitor(self, reopen=reopen)
    def _open_deck(self, reopen=False):
        from .dialogs.deck import open_deck
        if not reopen:
            self._close_other_subwins(keep='deck')
        open_deck(self, reopen=reopen)
    def _open_extensions(self, reopen=False):
        from .dialogs.extensions import open_extensions
        if not reopen:
            self._close_other_subwins(keep='extensions')
        open_extensions(self, reopen=reopen)
    def _open_mail(self, reopen=False):
        from .dialogs.mail_dlg import open_mail_client
        if not reopen:
            self._close_other_subwins(keep='mail')
        open_mail_client(self, reopen=reopen)
    def _open_spell_editor(self, reopen=False):
        from .dialogs.editors import open_spell_editor
        if not reopen:
            self._close_other_subwins(keep='spell_editor')
        open_spell_editor(self, reopen=reopen)
    def _open_keybind_editor(self, reopen=False):
        from .dialogs.editors import open_keybind_editor
        if not reopen:
            self._close_other_subwins(keep='keybind_editor')
        open_keybind_editor(self, reopen=reopen)
    def _update_sys_widgets(self): monitoring.update_sys_widgets(self)
    def _draw_top_strip(self, e=None): renderer.draw_top_strip(self)
    def _draw_bot_strip(self, e=None): renderer.draw_bot_strip(self)
    def _rebuild_left(self): layout.rebuild_left(self)
    def _rebuild_right(self): layout.rebuild_right(self)
def _try_show_welcome(hud: 'JarvisHUD') -> None:
    try:
        from ui.dialogs.welcome_dlg import open_welcome
        open_welcome(hud)
    except Exception:
        pass
def start():
    global _hud
    hud = JarvisHUD()
    _hud = hud
    hud.root.after(900, lambda: _try_show_welcome(hud))
    hud.root.mainloop()
