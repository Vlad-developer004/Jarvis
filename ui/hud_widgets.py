from __future__ import annotations
import tkinter as tk
from .hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _WHITE, _TEXT, _DIM
from .hud_utils import _blend
class _HudScrollbar:
    W = 6
    def __init__(self, parent, canvas: tk.Canvas, color=None):
        self._canvas = canvas
        self._color = color or _CYAN
        self._needed = False
        self._lo = 0.0
        self._hi = 1.0
        self._drag_y = None
        self._bar = tk.Canvas(parent, width=self.W, bg=_BG, highlightthickness=0, cursor='arrow')
        self._bar.place(relx=1.0, x=-self.W, rely=0, relheight=1.0)
        self._bar.bind('<ButtonPress-1>', self._on_press)
        self._bar.bind('<B1-Motion>', self._on_drag)
        self._bar.bind('<ButtonRelease-1>', self._on_release)
        self._bar.place_forget()
    def winfo_ismapped(self):
        return self._needed
    def set(self, lo: str, hi: str):
        try:
            lo, hi = float(lo), float(hi)
            self._lo, self._hi = lo, hi
            needed = (hi - lo < 0.99)
            if needed != self._needed:
                self._needed = needed
                if not self._needed:
                    self._bar.place_forget()
                else:
                    self._bar.place(relx=1.0, x=-self.W, rely=0, relheight=1.0)
            self._bar.delete('all')
            if not self._needed: return
            h = self._bar.winfo_height() or 100
            y0 = int(lo * h)
            y1 = max(y0 + 16, int(hi * h))
            self._bar.create_rectangle(0, 0, self.W, h, fill=_blend(self._color, 0.05), outline='')
            self._bar.create_rectangle(1, y0, self.W - 1, y1, fill=self._color, outline='')
        except: pass
    def _on_press(self, e):
        self._drag_y = e.y
    def _on_drag(self, e):
        if self._drag_y is None:
            return
        h = self._bar.winfo_height() or 1
        dy = (e.y - self._drag_y) / h
        self._drag_y = e.y
        self._canvas.yview_moveto(max(0.0, self._lo + dy))
    def _on_release(self, e):
        self._drag_y = None
def make_hud_btn(hud, parent, text: str, icon: str, color: str, command, **kwargs) -> tk.Canvas:
    _h = hud._px(48)
    _br = max(12, hud._px(14))
    _s = {'text': text, 'icon': icon, 'color': color, 'hover': False, 'icon_fs': kwargs.get('icon_fs', 18)}
    c = tk.Canvas(parent, height=_h, bg=_BG, highlightthickness=0, cursor='hand2')
    c.pack(fill='x', padx=12, pady=(0, 16))
    def _draw() -> None:
        c.delete('all')
        hover = _s['hover']
        col = _s['color']
        bg = _blend(col, 0.14) if hover else _blend(col, 0.06)
        w = c.winfo_width() or hud._panel_w - 16
        c.configure(bg=bg)
        c.create_line(0, 0, w, 0, fill=_blend(col, 0.3), width=1)
        c.create_line(0, _h - 1, w, _h - 1, fill=_blend(col, 0.3), width=1)
        lw = 3 if hover else 2
        for bx, by, sx, sy in ((1, 1, 1, 1), (w - 1, 1, -1, 1), (1, _h - 1, 1, -1), (w - 1, _h - 1, -1, -1)):
            c.create_line(bx, by, bx + sx * _br, by, fill=col, width=lw)
            c.create_line(bx, by, bx, by + sy * _br, fill=col, width=lw)
        ix = hud._px(14)
        icon_fs = _s.get('icon_fs', 18)
        icon_id = c.create_text(ix, _h // 2, text=_s['icon'], fill=col, font=(hud._F, hud._fs(icon_fs), 'bold'), anchor='w')
        bbox = c.bbox(icon_id)
        icon_right = bbox[2] if bbox else ix + hud._px(18)
        tx = icon_right + hud._px(8)
        t_col = _WHITE if hover else _TEXT
        c.create_text(tx, _h // 2, text=_s['text'], fill=t_col, font=(hud._F, hud._fs(10), 'bold'), anchor='w')
    def _update(new_text: str, new_icon: str, new_color: str, **new_kwargs) -> None:
        _s['text'] = new_text
        _s['icon'] = new_icon
        _s['color'] = new_color
        if 'icon_fs' in new_kwargs: _s['icon_fs'] = new_kwargs['icon_fs']
        _s['hover'] = False
        _draw()
    c.bind('<Configure>', lambda _e: _draw())
    c.bind('<Enter>', lambda _e: [_s.update({'hover': True}), _draw()])
    c.bind('<Leave>', lambda _e: [_s.update({'hover': False}), _draw()])
    c.bind('<Button-1>', lambda _e: command())
    c.hud_update = _update
    return c
def make_dlg_btn(hud, parent, text: str, icon: str, color: str, command,
                 height: int = 42, width: int = 132) -> tk.Widget:
    import customtkinter as ctk
    btn = ctk.CTkButton(parent, text=f'{icon}  {text}', command=command,
                        height=hud._px(height), width=hud._px(width),
                        font=(hud._F, hud._fs(12), 'bold'),
                        fg_color=_blend(color, 0.08),
                        hover_color=_blend(color, 0.22),
                        text_color=color,
                        border_color=color,
                        border_width=1,
                        corner_radius=6)
    return btn
def glass_panel(hud, parent: tk.Frame, side: str, w: int) -> tk.Frame:
    outer = tk.Frame(parent, bg=_BRD, width=w)
    outer.pack(side=side, fill='y', anchor='n')
    outer.pack_propagate(False)
    accent_col = _CYAN if side == 'left' else _MAG
    tk.Frame(outer, bg=accent_col, height=2).pack(fill='x', side='top')
    inner = tk.Frame(outer, bg=_PANEL)
    inner.pack(fill='both', expand=True, padx=1, pady=(0, 1), anchor='n')
    return inner
def section_hdr(hud, parent, text: str, color: str=_CYAN, pady: tuple=(12, 8)) -> None:
    bar = tk.Frame(parent, bg=_SEP)
    bar.pack(fill='x', pady=pady)
    row = tk.Frame(bar, bg=_SEP)
    row.pack(anchor='w', padx=10, pady=6)
    tk.Label(row, text='◈', bg=_SEP, fg=color, font=(hud._F, hud._fs(18), 'bold')).pack(side='left', padx=(0, 10))
    tk.Label(row, text=text, bg=_SEP, fg=color, font=(hud._F, hud._fs(14), 'bold')).pack(side='left')
def bar_row(hud, parent, label: str, color: str):
    import customtkinter as ctk
    wrap = tk.Frame(parent, bg=_PANEL)
    wrap.pack(fill='x', padx=20, pady=(4, 6))
    top = tk.Frame(wrap, bg=_PANEL)
    top.pack(fill='x')
    tk.Label(top, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(10), 'bold'), anchor='w').pack(side='left', fill='x', expand=True)
    val = tk.Label(top, text='—', bg=_PANEL, fg=color, font=(hud._F, hud._fs(11), 'bold'), anchor='e')
    val.pack(side='right', padx=(hud._px(6), 0))
    bar = ctk.CTkProgressBar(wrap, height=11, progress_color=color, fg_color=_BRD_I, corner_radius=4)
    bar.set(0)
    bar.pack(fill='x', pady=(4, 0))
    return (bar, val)
def kv_row(hud, parent, key: str, vcol: str=_CYAN) -> tk.Label:
    row = tk.Frame(parent, bg=_PANEL)
    row.pack(fill='x', padx=20, pady=3)
    tk.Label(row, text=key, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(10), 'bold'), anchor='w').pack(side='left')
    v = tk.Label(row, text='—', bg=_PANEL, fg=vcol, font=(hud._F, hud._fs(11), 'bold'), anchor='w')
    v.pack(side='left', padx=(hud._px(12), 0), fill='x', expand=True)
    return v
