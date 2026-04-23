from __future__ import annotations
import tkinter as tk
from .hud_constants import _BG, _PANEL, _BRD, _BRD_I, _SEP, _CYAN, _MAG, _WHITE, _TEXT, _DIM
from .hud_utils import _blend
class _HudScrollbar:
    def __init__(self, parent, canvas: tk.Canvas, color=None, orient='vertical'):
        self._canvas = canvas
        self._color = color or _CYAN
        self._orient = orient
        self._needed = False
        self._lo = 0.0
        self._hi = 1.0
        self._drag_start = None
        self.W = 6
        self._bar = tk.Canvas(parent, bg=_BG, highlightthickness=0, cursor='arrow')
        if self._orient == 'vertical':
            self._bar.place(relx=1.0, x=-self.W, rely=0, relheight=1.0, width=self.W)
        else:
            self._bar.place(relx=0, rely=1.0, y=-self.W, relwidth=1.0, height=self.W)
            
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
                    if self._orient == 'vertical':
                        self._bar.place(relx=1.0, x=-self.W, rely=0, relheight=1.0, width=self.W)
                    else:
                        self._bar.place(relx=0, rely=1.0, y=-self.W, relwidth=1.0, height=self.W)
            
            self._bar.delete('all')
            if not self._needed: return
            
            bw = self._bar.winfo_width()
            bh = self._bar.winfo_height()
            
            if self._orient == 'vertical':
                y0 = int(lo * bh)
                y1 = max(y0 + 16, int(hi * bh))
                self._bar.create_rectangle(0, 0, self.W, bh, fill=_blend(self._color, 0.05), outline='')
                self._bar.create_rectangle(1, y0, self.W - 1, y1, fill=self._color, outline='')
            else:
                x0 = int(lo * bw)
                x1 = max(x0 + 16, int(hi * bw))
                self._bar.create_rectangle(0, 0, bw, self.W, fill=_blend(self._color, 0.05), outline='')
                self._bar.create_rectangle(x0, 1, x1, self.W - 1, fill=self._color, outline='')
        except: pass

    def _on_press(self, e):
        self._drag_start = e.y if self._orient == 'vertical' else e.x

    def _on_drag(self, e):
        if self._drag_start is None: return
        if self._orient == 'vertical':
            size = self._bar.winfo_height() or 1
            curr = e.y
        else:
            size = self._bar.winfo_width() or 1
            curr = e.x
            
        ds = (curr - self._drag_start) / size
        self._drag_start = curr
        self._canvas.xview_scroll(int(ds*10), 'units') if self._orient == 'horizontal' else self._canvas.yview_scroll(int(ds*10), 'units')
        # Actually xview_scroll usage is different than moveto. Let's use moveto.
        self._canvas.xview_moveto(max(0.0, self._lo + ds)) if self._orient == 'horizontal' else self._canvas.yview_moveto(max(0.0, self._lo + ds))

    def _on_release(self, e):
        self._drag_start = None
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
    inner.outer = outer # Store reference for live resizing
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
    val = tk.Label(top, text='...', bg=_PANEL, fg=color, font=(hud._F, hud._fs(11), 'bold'), anchor='e')
    val.pack(side='right', padx=(hud._px(6), 0))
    bar = ctk.CTkProgressBar(wrap, height=11, progress_color=color, fg_color=_BRD_I, corner_radius=4)
    bar.set(0)
    bar.pack(fill='x', pady=(4, 0))
    return (bar, val)
def kv_row(hud, parent, key: str, vcol: str=_CYAN) -> tk.Label:
    row = tk.Frame(parent, bg=_PANEL)
    row.pack(fill='x', padx=20, pady=3)
    tk.Label(row, text=key, bg=_PANEL, fg=_TEXT, font=(hud._F, hud._fs(10), 'bold'), anchor='w').pack(side='left')
    v = tk.Label(row, text='...', bg=_PANEL, fg=vcol, font=(hud._F, hud._fs(11), 'bold'), anchor='w')
    v.pack(side='left', padx=(hud._px(12), 0), fill='x', expand=True)
    return v
class _HUDDropdown:
    def __init__(self, hud, master, values, variable, command=None, accent=_CYAN):
        self.hud = hud
        self.master = master
        self.values = values
        self.variable = variable
        self.command = command
        self.accent = accent
        self.is_open = False
        self.menu = None
        
        self._sf = lambda n: hud._fs(n + 6)
        
        self.frame = tk.Frame(master, bg=_BG, highlightbackground=_blend(self.accent, 0.4), highlightthickness=1)
        
        # Reduced pady from 10 to 6 for a sleeker field
        self.lbl = tk.Label(self.frame, textvariable=self.variable, bg=_BG, fg=_TEXT, font=(hud._F, self._sf(9), 'bold'), anchor='w', padx=12)
        self.lbl.pack(side='left', fill='x', expand=True, pady=6)
        
        self.arr = tk.Label(self.frame, text='▼', bg=_BG, fg=self.accent, font=(hud._F, self._sf(8)), padx=12)
        self.arr.pack(side='right')
        
        for w in (self.frame, self.lbl, self.arr):
            w.bind('<Button-1>', lambda e: self.toggle())
            w.bind('<Enter>', lambda e: self.frame.configure(highlightbackground=self.accent))
            w.bind('<Leave>', lambda e: self.frame.configure(highlightbackground=_blend(self.accent, 0.4)))
        
        self._bind_scroll_close()

    def _bind_scroll_close(self):
        root = self.frame.winfo_toplevel()
        root.bind('<MouseWheel>', lambda e: self.close(), add='+')
        root.bind('<Button-4>', lambda e: self.close(), add='+')
        root.bind('<Button-5>', lambda e: self.close(), add='+')
        self.master.bind('<Configure>', lambda e: self.close(), add='+')

    def toggle(self):
        if self.is_open: self.close()
        else: self.open()

    def open(self):
        self.close()
        self.is_open = True
        self.menu = tk.Toplevel(self.master)
        self.menu.overrideredirect(True)
        self.menu.attributes('-topmost', True)
        self.menu.attributes('-alpha', 0.96)
        self.menu.configure(bg=_BG, highlightbackground=self.accent, highlightthickness=1)
        
        # Use a canvas for scrolling support
        self.container = tk.Frame(self.menu, bg=_BG)
        self.container.pack(fill='both', expand=True)
        
        self.canvas = tk.Canvas(self.container, bg=_BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        
        # Use our existing HUD-styled scrollbar
        self.scroll = _HudScrollbar(self.container, self.canvas, color=self.accent)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        
        self.list_frame = tk.Frame(self.canvas, bg=_BG)
        self.canvas.create_window((0, 0), window=self.list_frame, anchor='nw', tags='frame')
        
        def _on_resize_canvas(e):
            self.canvas.itemconfig('frame', width=e.width)
        self.canvas.bind('<Configure>', _on_resize_canvas)

        for val in self.values:
            f = tk.Frame(self.list_frame, bg=_BG)
            f.pack(fill='x')
            is_sel = val == self.variable.get()
            
            ind = tk.Label(f, text='✦' if is_sel else '', bg=_BG, fg=self.accent, font=(self.hud._F, self._sf(10)), width=3)
            ind.pack(side='left', padx=(5, 0))
            
            l = tk.Label(f, text=val, bg=_BG, fg=self.accent if is_sel else _TEXT, font=(self.hud._F, self._sf(9)), anchor='w', pady=4)
            l.pack(side='left', fill='x', expand=True, padx=(5, 10))
            
            def _sel(v=val):
                self.variable.set(v)
                self.close()
                if self.command: self.command(v)
            
            def _hvr(e, fw=f, lw=l, iw=ind, s=is_sel):
                if fw.winfo_exists(): fw.configure(bg=_blend(self.accent, 0.2))
                if lw.winfo_exists(): lw.configure(bg=_blend(self.accent, 0.2), fg=self.accent)
                if iw.winfo_exists(): iw.configure(bg=_blend(self.accent, 0.2))
            def _lve(e, fw=f, lw=l, iw=ind, s=is_sel):
                if fw.winfo_exists(): fw.configure(bg=_BG)
                if lw.winfo_exists(): lw.configure(bg=_BG, fg=self.accent if s else _TEXT)
                if iw.winfo_exists(): iw.configure(bg=_BG)
                
            for bw in (l, ind, f):
                bw.bind('<Button-1>', lambda e, v=val: _sel(v))
                bw.bind('<Enter>', _hvr)
                bw.bind('<Leave>', _lve)
            
            # Allow mouse wheel to work anywhere in the menu
            f.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
            l.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
            ind.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        
        # Update scrolling region
        self.list_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        
        # Determine total items height
        item_h = self.list_frame.winfo_reqheight()
        h = min(400, item_h) # Max 400px height
        
        x = self.frame.winfo_rootx()
        y = self.frame.winfo_rooty() + self.frame.winfo_height()
        w = self.frame.winfo_width()

        # --- Screen boundary detection & Auto-flip ---
        screen_h = self.master.winfo_screenheight()
        if y + h > screen_h - 40: # Allow 40px for taskbar
            new_y = self.frame.winfo_rooty() - h
            if new_y > 0: y = new_y
            else:
                h = screen_h - y - 40
                if h < 100: h = 300 
        
        self.menu.geometry(f'{w}x{h}+{x}+{y}')
        
        def _on_focus_out(e):
            if self.menu and self.menu.winfo_exists():
                active = self.menu.focus_displayof()
                if not active or str(active).startswith(str(self.menu)):
                    return
                self.close()

        self.menu.bind('<FocusOut>', _on_focus_out)
        self.menu.bind('<Unmap>', lambda e: self.close())
        self.menu.focus_set()
        
        # Also bind wheel to the menu background itself
        self.menu.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        
        self._start_y = self.frame.winfo_rooty()
        self._check_anchoring()

    def _check_anchoring(self):
        if not self.is_open or not self.menu: return
        try:
            curr_y = self.frame.winfo_rooty()
            if abs(curr_y - self._start_y) > 5:
                self.close()
                return
            self.master.after(100, self._check_anchoring)
        except: pass

    def close(self):
        if self.menu: 
            try: self.menu.destroy()
            except: pass
        self.menu = None
        self.is_open = False

    def configure(self, values=None):
        if values is not None: self.values = values
