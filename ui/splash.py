import tkinter as tk
import math
import time
_BG = '#0a0b10'
_PANEL = '#0d0f1e'
_CYAN = '#00ffff'
_DIM = '#4a4b6a'
_TEXT = '#a0a8c0'
_WHITE = '#ffffff'
_FONT = 'Courier'
_W, _H = (500, 300)
class SplashScreen:
    def __init__(self):
        self._root = tk.Tk()
        r = self._root
        r.overrideredirect(True)
        r.configure(bg=_BG)
        r.attributes('-topmost', True)
        sw = r.winfo_screenwidth()
        sh = r.winfo_screenheight()
        r.geometry(f'{_W}x{_H}+{(sw - _W) // 2}+{(sh - _H) // 2}')
        border = tk.Frame(r, bg=_CYAN, padx=1, pady=1)
        border.pack(fill='both', expand=True)
        inner = tk.Frame(border, bg=_BG)
        inner.pack(fill='both', expand=True, padx=1, pady=1)
        self._arc_canvas = tk.Canvas(inner, bg=_BG, width=80, height=80, highlightthickness=0)
        self._arc_canvas.pack(pady=(20, 0))
        tk.Label(inner, text='J.A.R.V.I.S.', bg=_BG, fg=_CYAN, font=(_FONT, 22, 'bold')).pack(pady=(4, 0))
        tk.Label(inner, text='СИСТЕМА ИНИЦИАЛИЗАЦИИ v1.4', bg=_BG, fg=_DIM, font=(_FONT, 8)).pack()
        tk.Frame(inner, bg=_CYAN, height=1).pack(fill='x', padx=30, pady=8)
        self._msg_var = tk.StringVar(value='Запуск...')
        tk.Label(inner, textvariable=self._msg_var, bg=_BG, fg=_TEXT, font=(_FONT, 9)).pack()
        bar_outer = tk.Frame(inner, bg=_DIM, height=8)
        bar_outer.pack(fill='x', padx=30, pady=(8, 2))
        bar_outer.pack_propagate(False)
        self._bar_inner = tk.Frame(bar_outer, bg=_CYAN, height=8)
        self._bar_inner.place(x=0, y=0, relheight=1.0, relwidth=0.0)
        self._pct_var = tk.StringVar(value='0%')
        tk.Label(inner, textvariable=self._pct_var, bg=_BG, fg=_CYAN, font=(_FONT, 8)).pack()
        self._pct = 0
        self._t0 = time.time()
        r.update()
        self._animate_arc(0)
    def _animate_arc(self, frame: int):
        c = self._arc_canvas
        cx, cy = (40, 40)
        t = time.time()
        c.delete('all')
        c.create_oval(8, 8, 72, 72, outline=_DIM, width=1)
        ang = t * 60 % 360
        c.create_arc(8, 8, 72, 72, start=ang, extent=110, outline=_CYAN, width=2, style='arc')
        c.create_oval(18, 18, 62, 62, outline=_DIM, width=1)
        ang2 = -t * 90 % 360
        c.create_arc(18, 18, 62, 62, start=ang2, extent=60, outline=_CYAN, width=1, style='arc')
        pulse = 6 + math.sin(t * 4) * 2
        c.create_oval(cx - pulse, cy - pulse, cx + pulse, cy + pulse, fill=_WHITE, outline='')
        if not self._closed:
            try:
                self._root.after(50, self._animate_arc, frame + 1)
            except Exception:
                pass
    def update(self, message: str, percent: int):
        self._pct = max(self._pct, min(100, percent))
        self._msg_var.set(message)
        self._pct_var.set(f'{self._pct}%')
        self._bar_inner.place(relwidth=self._pct / 100)
        try:
            self._root.update()
        except Exception:
            pass
    def close(self):
        self._closed = True
        try:
            self._root.destroy()
        except Exception:
            pass
    _closed = False
_splash: 'SplashScreen | None' = None
def show() -> SplashScreen:
    global _splash
    _splash = SplashScreen()
    return _splash
def step(message: str, percent: int):
    if _splash is not None:
        _splash.update(message, percent)
def done():
    if _splash is not None:
        _splash.close()
