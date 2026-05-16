from __future__ import annotations
from ui.hud_style import JStyle
from core import i18n
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
from .hud_utils import _load_hud_settings, _save_hud_settings, _set_dark_title_bar, _blend
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
    # Используем window.show_main_win для корректного восстановления всех окон
    _hud._hud_queue.put(lambda: window.show_main_win(_hud))
    # Принудительно разворачиваем на весь экран
    _hud._hud_queue.put(lambda: _hud.root.state('zoomed'))
class JarvisHUD:
    def __init__(self) -> None:
        self._settings = _load_hud_settings()
        if 'zoom_factor' not in self._settings:
            self.zoom_factor = self._auto_detect_zoom()
        else:
            self.zoom_factor = float(self._settings.get('zoom_factor', 1.0))
        if self.zoom_factor <= 0.0: self.zoom_factor = 1.0
        self._font_scale_left: float = 1.0
        self._font_scale_right: float = 1.0
        JStyle.apply_zoom(self.zoom_factor)
        _c._SCROLLBAR_WIDTH = int(self._settings.get('scrollbar_width', 10))

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
        self._monitoring_enabled: bool = self._settings.get('monitoring_enabled', True)
        
        # --- Separate Widths ---
        self._panel_w_left = self._calc_panel_w('left')
        self._panel_w_right = self._calc_panel_w('right')
        
        # 🔥 ФИКС: Рассчитываем масштаб шрифтов сразу при старте
        self._font_scale_left = self._get_font_scale('left')
        self._font_scale_right = self._get_font_scale('right')
        
        self._last_weather_data = None
        self._tick = 0
        self._resize_timer: Optional[str] = None
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
        self._cx, self._cy = 0, 0
        import collections
        self._perf_history = {k: collections.deque(maxlen=180) for k in [
            'cpu', 'ram', 'dsk_util', 'dsk_read', 'dsk_write',
            'net_up', 'net_dn', 'gpu_util', 'gpu_mem', 'gpu_temp', 'cpu_temp', 'latency'
        ]}
        import tkinter.font as _tkfont
        _avail = set(_tkfont.families())
        self._F = next((f for f in ('JetBrains Mono', 'Share Tech Mono', 'Fira Code', 'Cascadia Code', 'Consolas') if f in _avail), 'Courier New')
        tk.Frame(self.root, bg=_CYAN, height=2).pack(fill='x', side='top')
        tk.Frame(self.root, bg=_c._MAG, height=2).pack(fill='x', side='bottom')
        layout.build_header(self)
        body = tk.Frame(self.root, bg=_BG)
        body.pack(fill='both', expand=True)
        
        # Left Sidebar Container
        self._left_outer = tk.Frame(body, bg=_BG)
        self._left_outer.pack(side='left', fill='y')
        self._left = layout.glass_panel(self, self._left_outer, 'left', self._panel_w_left)
        
        # Resize Handle (Left)
        self._left_sep = tk.Frame(self._left_outer, bg=_BRD, width=4, cursor='size_we')
        self._left_sep.pack(side='left', fill='y')
        
        # Right Sidebar Container
        self._right_outer = tk.Frame(body, bg=_BG)
        self._right_outer.pack(side='right', fill='y')
        self._right = layout.glass_panel(self, self._right_outer, 'right', self._panel_w_right)
        
        # Resize Handle (Right)
        self._right_sep = tk.Frame(self._right_outer, bg=_BRD, width=4, cursor='size_we')
        self._right_sep.pack(side='right', fill='y')

        # --- Resize Bindings ---
        def _start_drag(e, side):
            cur_w = self._panel_w_left if side == 'left' else self._panel_w_right
            self._drag_data = {'side': side, 'x': e.x_root, 'w': cur_w}
            
        def _on_drag(e):
            if not hasattr(self, '_drag_data'): return
            side = self._drag_data['side']
            dx = e.x_root - self._drag_data['x']
            if side == 'right': dx = -dx
            
            new_w = self._drag_data['w'] + dx
            sw = self.root.winfo_screenwidth()
            
            # Constraints: 18% - 38% of screen
            limit_min = int(sw * 0.18)
            limit_max = int(sw * 0.38)
            new_w = max(limit_min, min(new_w, limit_max))
            
            if side == 'left':
                if new_w != self._panel_w_left:
                    self._panel_w_left = new_w
                    self._settings['sidebar_width_left'] = new_w
                    self._left.outer.configure(width=new_w)
            else:
                if new_w != self._panel_w_right:
                    self._panel_w_right = new_w
                    self._settings['sidebar_width_right'] = new_w
                    self._right.outer.configure(width=new_w)
        
        def _stop_drag(e):
            if hasattr(self, '_drag_data'):
                delattr(self, '_drag_data')
                _save_hud_settings(self._settings)
                self._apply_zoom_rebuild()

        self._left_sep.bind('<Button-1>', lambda e: _start_drag(e, 'left'))
        self._left_sep.bind('<B1-Motion>', _on_drag)
        self._left_sep.bind('<ButtonRelease-1>', _stop_drag)
        
        self._right_sep.bind('<Button-1>', lambda e: _start_drag(e, 'right'))
        self._right_sep.bind('<B1-Motion>', _on_drag)
        self._right_sep.bind('<ButtonRelease-1>', _stop_drag)
        
        # Center Area
        self._mid = tk.Frame(body, bg=_BG)
        self._mid.pack(side='left', fill='both', expand=True)

        # Sidebar Toggle Buttons (Managed in layout to avoid overlap)
        _btn_style = dict(
            fg_color='transparent', 
            text_color=_CYAN, 
            hover_color=_blend(_CYAN, 0.2),
            border_color=_CYAN, 
            border_width=1, 
            corner_radius=4, 
            width=30, 
            height=JStyle.H_TOOL, 
            font=(self._F, 12, 'bold')
        )
        self._left_toggle = ctk.CTkButton(self.root, text='«', command=self._toggle_left, **_btn_style)
        self._right_toggle = ctk.CTkButton(self.root, text='»', command=self._toggle_right, **_btn_style)
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

        i18n.register_refresh(self._refresh_ui_text)

        self.root.bind_all('<MouseWheel>', self._route_wheel)
        self.root.bind_all('<Control-equal>', lambda e: self._zoom_step(+0.1))
        self.root.bind_all('<Control-plus>', lambda e: self._zoom_step(+0.1))
        self.root.bind_all('<Control-minus>', lambda e: self._zoom_step(-0.1))
        self.root.bind_all('<Control-0>', lambda e: self._zoom_reset())

    def _auto_detect_zoom(self) -> float:
        try:
            import ctypes
            # Get physical screen width directly from Windows API
            sw = ctypes.windll.user32.GetSystemMetrics(0)
            if sw >= 3800: return 2.0   # 4K
            if sw >= 2500: return 1.5   # 2K / QHD
            if sw >= 1900: return 1.2   # Full HD (slight boost)
            if sw >= 1600: return 1.1
            return 1.0
        except Exception:
            return 1.0
    def _get_dpi_scale(self) -> float:
        # Framework handles DPI natively.
        return 1.0
    def _px(self, n: int) -> int:
        # We scale for internal canvases. CTK widgets will use logical pixels.
        return int(n * self.zoom_factor)
    def _fs(self, n: int, side: str = 'left') -> int:
        # For tk.Label/tk.Canvas: negative = pixel size. 
        scale = self._font_scale_left if side == 'left' else self._font_scale_right
        return -max(6, int(n * 1.33 * self.zoom_factor * scale))

    def _fsc(self, n: int, side: str = 'left') -> int:
        # For CTK widgets (CTkButton, CTkEntry, CTkLabel etc.) — positive point size.
        return max(8, n)

    def _get_font_scale(self, side: str) -> float:
        w = self._panel_w_left if side == 'left' else self._panel_w_right
        # Начинаем уменьшать шрифт раньше (с 320px) и позволяем сжимать сильнее (до 0.5)
        base_w = self._px(320)
        if w < base_w: return max(0.5, w / base_w)
        return 1.0

    def _calc_panel_w(self, side: str, force_auto: bool = False) -> int:
        sw = self.root.winfo_screenwidth()
        limit_min = int(sw * 0.18)
        limit_max = int(sw * 0.38)
        
        # 1. Try side-specific setting (unless forcing auto)
        if not force_auto:
            setting_key = f'sidebar_width_{side}'
            if setting_key in self._settings:
                val = int(self._settings[setting_key])
                return max(limit_min, min(val, limit_max))
                
            # 2. Try legacy raw setting
            if 'sidebar_width_raw' in self._settings:
                val = int(self._settings['sidebar_width_raw'])
                return max(limit_min, min(val, limit_max))
            
        # 3. Auto-calculation (The "Old Way")
        import tkinter.font as _tf
        try:
            # Measure with base size 11 and current zoom
            _test_fs = int(11 * self.zoom_factor)
            _f_test = _tf.Font(family=self._F, size=_test_fs, weight='bold')
            _hdr_texts = [
                'КОМАНДЫ И УПРАВЛЕНИЕ', 'СИСТЕМНЫЕ ПРОФИЛИ',
                'АНАЛИТИКА ДАННЫХ',     'СЕТЕВАЯ СТАТИСТИКА',
                '✧ МИКРОФОН / ЧУВСТВИТЕЛЬНОСТЬ'
            ]
            _max_text_w = max(_f_test.measure(t) for t in _hdr_texts)
            _content_w = _max_text_w + self._px(64) # text + icon + margins
        except Exception:
            _content_w = self._px(300)

        # Max % of screen for sidebars
        _max_pct = 0.36
        if sw >= 1920: _max_pct = 0.32
        if sw >= 2560: _max_pct = 0.24
        if sw >= 3840: _max_pct = 0.18
        
        _limit_w = int(sw * _max_pct)
        _min_w   = self._px(230)
        
        if _content_w > _limit_w:
            _w = _limit_w
        else:
            _w = max(_min_w, _content_w)
            
        return max(limit_min, min(_w, limit_max))
    def _poll_hud_queue(self):
        try:
            while not self._hud_queue.empty():
                callback = self._hud_queue.get_nowait()
                if callable(callback):
                    try:
                        callback()
                    except Exception:
                        import traceback
                        traceback.print_exc()
        except Exception:
            pass
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
        # 🚀 ДЕБАУНСИНГ: Не перерисовываем радар при каждом пикселе движения
        if self._resize_timer:
            self.root.after_cancel(self._resize_timer)
        
        # Ждем 150мс после последнего изменения размера, прежде чем пересчитывать центр
        self._resize_timer = self.root.after(150, lambda: self._on_resize_actual(evt))

    def _on_resize_actual(self, evt: tk.Event) -> None:
        if not hasattr(self, '_canvas') or not self._canvas.winfo_exists():
            return
        # Обновляем координаты центра
        cw, ch = self._canvas.winfo_width(), self._canvas.winfo_height()
        if cw // 2 != self._cx or ch // 2 != self._cy:
            self._cx, self._cy = cw // 2, ch // 2
            renderer.draw_static(self)
            renderer.init_anim_objects(self)
        self._resize_timer = None
    def _toggle_monitoring(self) -> None:
        self._monitoring_enabled = not self._monitoring_enabled
        self._settings['monitoring_enabled'] = self._monitoring_enabled
        _save_hud_settings(self._settings)

    def _zoom_step(self, delta: float) -> None:
        self.zoom_factor = round(max(0.6, min(2.5, self.zoom_factor + delta)), 1)
        self._settings['zoom_factor'] = self.zoom_factor
        _save_hud_settings(self._settings)
        self._apply_zoom_rebuild(force_auto=True)
    def _zoom_reset(self) -> None:
        self.zoom_factor = 1.0
        self._settings['zoom_factor'] = self.zoom_factor
        _save_hud_settings(self._settings)
        self._apply_zoom_rebuild(force_auto=True)
    def _apply_zoom_rebuild(self, force_auto: bool = False) -> None:
        JStyle.apply_zoom(self.zoom_factor)
        ctk.set_widget_scaling(self.zoom_factor)
        ctk.set_window_scaling(self.zoom_factor)
        self.root.update_idletasks()
        
        # Calculate individual widths and font scales
        self._panel_w_left = self._calc_panel_w('left', force_auto=force_auto)
        self._panel_w_right = self._calc_panel_w('right', force_auto=force_auto)
        self._font_scale_left = self._get_font_scale('left')
        self._font_scale_right = self._get_font_scale('right')
        
        # Save auto-calculated widths ONLY if we forced auto (on zoom change)
        if force_auto:
            self._settings['sidebar_width_left'] = self._panel_w_left
            self._settings['sidebar_width_right'] = self._panel_w_right
            _save_hud_settings(self._settings)
        
        # Ensure bottom bar order is preserved during zoom
        try:
            self._left_toggle.pack_forget()
            self._right_toggle.pack_forget()
            self._bot_canvas.pack_forget()
            self._left_toggle.pack(in_=self._bot_strip, side='left', padx=(10, 5))
            self._right_toggle.pack(in_=self._bot_strip, side='right', padx=(5, 10))
            self._bot_canvas.pack(in_=self._bot_strip, side='left', fill='both', expand=True)
        except: pass

        if hasattr(self._left, 'outer'): self._left.outer.configure(width=self._panel_w_left)
        if hasattr(self._right, 'outer'): self._right.outer.configure(width=self._panel_w_right)
        try:
            self._left_toggle.configure(font=(self._F, JStyle.TEXT_BODY, 'bold'), height=JStyle.H_TOOL)
            self._right_toggle.configure(font=(self._F, JStyle.TEXT_BODY, 'bold'), height=JStyle.H_TOOL)
            self._bot_strip.configure(height=JStyle.H_LARGE)
        except Exception:
            pass
        
        self.root.update()
        layout.rebuild_left(self)
        layout.rebuild_right(self)
        layout.update_header_fonts(self)
        
        # 🔥 ИСПРАВЛЕНИЕ: Принудительный пересчет центральной графики
        # Имитируем событие Configure для центрального холста
        _w = self._canvas.winfo_width()
        _h = self._canvas.winfo_height()
        if _w > 1 and _h > 1:
            self._cx, self._cy = _w // 2, _h // 2
        
        # Полностью перерисовываем статику и анимацию центра
        renderer.draw_static(self)
        renderer.init_anim_objects(self)
        
        renderer.draw_bot_strip(self)
        renderer.draw_top_strip(self)
        
        # FORCED SCROLL REFRESH after UI stabilizes
        def _force_scroll():
            try:
                self.root.update_idletasks()
                if hasattr(self, '_left_scroll') and self._left_scroll.winfo_exists():
                    self._left_scroll.event_generate('<Configure>')
                if hasattr(self, '_right_scroll') and self._right_scroll.winfo_exists():
                    self._right_scroll.event_generate('<Configure>')
            except: pass
        self.root.after(350, _force_scroll)
        
        # REFRESH ALL ACTIVE SUB-WINDOWS (Dialogs)
        for reopen_fn in list(self._sub_wins.values()):
            try: 
                # Use reopen=True logic where supported to prevent stacking
                reopen_fn() 
            except: pass

    def _toggle_left(self):
        if self._left_outer.winfo_ismapped():
            self._left_outer.pack_forget()
            self._left_toggle.configure(text='»')
        else:
            self._left_outer.pack(side='left', fill='y', before=self._mid)
            self._left_toggle.configure(text='«')
            
    def _toggle_right(self):
        if self._right_outer.winfo_ismapped():
            self._right_outer.pack_forget()
            self._right_toggle.configure(text='«')
        else:
            # Re-pack to ensure it's on the right of center
            self._right_outer.pack(side='right', fill='y', after=self._mid)
            self._right_toggle.configure(text='»')
        renderer.draw_top_strip(self)
        renderer.draw_bot_strip(self)
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
    def _refresh_ui_text(self):
        try:
            self.root.title(f'J.A.R.V.I.S. — HUD v1.5')
            monitoring.clock_tick(self)
        except Exception:
            pass
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
