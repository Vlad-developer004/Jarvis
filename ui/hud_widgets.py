from __future__ import annotations
from ui.hud_style import JStyle
import tkinter as tk
import time
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

    def winfo_ismapped(self): return self._needed

    def set(self, lo: str, hi: str):
        try:
            lo, hi = max(0.0, min(1.0, float(lo))), max(0.0, min(1.0, float(hi)))
            self._lo, self._hi = lo, hi
            needed = (hi - lo < 0.99)
            if needed != self._needed:
                self._needed = needed
                if not self._needed: self._bar.place_forget()
                else:
                    if self._orient == 'vertical': self._bar.place(relx=1.0, x=-self.W, rely=0, relheight=1.0, width=self.W)
                    else: self._bar.place(relx=0, rely=1.0, y=-self.W, relwidth=1.0, height=self.W)
            
            self._bar.delete('all')
            if not self._needed: return
            
            bw, bh = self._bar.winfo_width(), self._bar.winfo_height()
            if self._orient == 'vertical':
                y0, y1 = int(lo * bh), max(int(lo * bh) + 16, int(hi * bh))
                self._bar.create_rectangle(0, 0, self.W, bh, fill=_blend(self._color, 0.05), outline='')
                self._bar.create_rectangle(1, y0, self.W - 1, y1, fill=self._color, outline='')
            else:
                x0, x1 = int(lo * bw), max(int(lo * bw) + 16, int(hi * bw))
                self._bar.create_rectangle(0, 0, bw, self.W, fill=_blend(self._color, 0.05), outline='')
                self._bar.create_rectangle(x0, 1, x1, self.W - 1, fill=self._color, outline='')
        except: pass

    def _on_press(self, e): self._drag_start = e.y if self._orient == 'vertical' else e.x
    def _on_drag(self, e):
        if self._drag_start is None: return
        size = self._bar.winfo_height() if self._orient == 'vertical' else self._bar.winfo_width()
        if size == 0: size = 1
        curr = e.y if self._orient == 'vertical' else e.x
        ds = (curr - self._drag_start) / size
        self._drag_start = curr
        if self._orient == 'horizontal':
            self._canvas.xview_scroll(int(ds*10), 'units')
            self._canvas.xview_moveto(max(0.0, self._lo + ds))
        else:
            self._canvas.yview_scroll(int(ds*10), 'units')
            self._canvas.yview_moveto(max(0.0, self._lo + ds))
    def _on_release(self, e): self._drag_start = None

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
        c.create_text(tx, _h // 2, text=_s['text'], fill=t_col, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w')
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
                        height=height, width=width,
                        font=(hud._F, JStyle.TEXT_BODY, 'bold'),
                        fg_color=_blend(color, 0.08),
                        hover_color=_blend(color, 0.22),
                        text_color=color,
                        border_color=color,
                        border_width=1,
                        corner_radius=JStyle.RAD_BTN)
    return btn

def glass_panel(hud, parent: tk.Frame, side: str, w: int) -> tk.Frame:
    outer = tk.Frame(parent, bg=_BRD, width=w)
    outer.pack(side=side, fill='y', anchor='n')
    outer.pack_propagate(False)
    accent_col = _CYAN if side == 'left' else _MAG
    tk.Frame(outer, bg=accent_col, height=2).pack(fill='x', side='top')
    inner = tk.Frame(outer, bg=_PANEL)
    inner.pack(fill='both', expand=True, padx=1, pady=(0, 1), anchor='n')
    inner.outer = outer 
    return inner

def section_hdr(hud, parent, text: str, color: str=_CYAN, pady: tuple=(12, 8)) -> None:
    bar = tk.Frame(parent, bg=_SEP)
    bar.pack(fill='x', pady=pady)
    row = tk.Frame(bar, bg=_SEP)
    row.pack(anchor='w', padx=10, pady=6)
    tk.Label(row, text='◈', bg=_SEP, fg=color, font=(hud._F, JStyle.TEXT_H1, 'bold')).pack(side='left', padx=(0, 10))
    tk.Label(row, text=text, bg=_SEP, fg=color, font=(hud._F, JStyle.TEXT_H2, 'bold')).pack(side='left')

def bar_row(hud, parent, label: str, color: str):
    import customtkinter as ctk
    wrap = tk.Frame(parent, bg=_PANEL)
    wrap.pack(fill='x', padx=20, pady=(4, 6))
    top = tk.Frame(wrap, bg=_PANEL)
    top.pack(fill='x')
    tk.Label(top, text=label, bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w').pack(side='left', fill='x', expand=True)
    val = tk.Label(top, text='...', bg=_PANEL, fg=color, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='e')
    val.pack(side='right', padx=(hud._px(6), 0))
    bar = ctk.CTkProgressBar(wrap, height=11, progress_color=color, fg_color=_BRD_I, corner_radius=4)
    bar.set(0)
    bar.pack(fill='x', pady=(4, 0))
    return (bar, val, wrap)

def kv_row(hud, parent, key: str, vcol: str=_CYAN) -> tk.Label:
    row = tk.Frame(parent, bg=_PANEL)
    row.pack(fill='x', padx=20, pady=3)
    tk.Label(row, text=key, bg=_PANEL, fg=_TEXT, font=(hud._F, JStyle.TEXT_SMALL, 'bold'), anchor='w').pack(side='left')
    v = tk.Label(row, text='...', bg=_PANEL, fg=vcol, font=(hud._F, JStyle.TEXT_BODY, 'bold'), anchor='w')
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
        self._click_id = None
        
        # Применяем масштабирование к шрифтам
        _sf_tk = lambda n: self.hud._fs(n + 14)
        _sf_ctk = lambda n: n + 14

        import customtkinter as ctk
        self.frame = ctk.CTkFrame(master, fg_color=_PANEL, border_color=_blend(self.accent, 0.4), border_width=1, corner_radius=JStyle.RAD_PANEL)
        
        self.arr = ctk.CTkLabel(self.frame, text='▼', fg_color='transparent', text_color=self.accent, font=(hud._F, _sf_ctk(0)), width=28)
        self.arr.pack(side='right', padx=4)
        
        def _get_clean_val(*a):
            v = self.variable.get()
            if v.startswith('spell_'): v = v.replace('spell_', '', 1)
            return v
            
        self.lbl = ctk.CTkLabel(self.frame, text=_get_clean_val(), fg_color='transparent', text_color=_TEXT, font=(hud._F, _sf_ctk(0), 'bold'), anchor='w')
        self.lbl.pack(side='left', fill='x', expand=True, padx=12, pady=6)
        
        self.variable.trace_add('write', lambda *a: self.lbl.configure(text=_get_clean_val()))
        
        for w in (self.frame, self.lbl, self.arr):
            w.bind('<Button-1>', self.toggle)
            w.bind('<Enter>', lambda e: self.frame.configure(border_color=self.accent))
            w.bind('<Leave>', lambda e: self.frame.configure(border_color=_blend(self.accent, 0.4)))
        
        self.frame.bind('<Destroy>', lambda e: self.close())

    def toggle(self, e=None):
        now = time.time()
        if hasattr(self, '_last_toggle') and now - self._last_toggle < 0.2: return 'break'
        self._last_toggle = now
        
        if self.is_open: self.close()
        else: self.open()
        return 'break'

    def _check_click(self, e):
        # ИДЕАЛЬНАЯ ПРОВЕРКА КЛИКОВ (По иерархии виджетов, без координат и математики)
        if not self.is_open or not self.menu or not self.menu.winfo_exists(): return
        
        w = e.widget
        try:
            # Поднимаемся по дереву виджетов от места клика вверх
            while w:
                if w == self.menu or w == self.frame:
                    return # Клик был внутри списка или по кнопке открытия - игнорируем
                w = w.master
        except AttributeError:
            pass # Если попался системный элемент без master
            
        # Если цикл дошел до конца и не нашел наше меню - значит клик был где-то снаружи
        self.close()

    def open(self):
        self.close()
        self.is_open = True
        self.menu = tk.Toplevel(self.master)
        self.menu.overrideredirect(True)
        self.menu.attributes('-topmost', True)
        self.menu.attributes('-alpha', 0.98)
        self.menu.configure(bg=_BG, highlightbackground=self.accent, highlightthickness=1)
        
        # Привязываем слушатель кликов на главное окно с задержкой (защита от пробития первого клика)
        self.master.after(50, lambda: setattr(self, '_click_id', self.master.winfo_toplevel().bind('<Button-1>', self._check_click, add='+')))
        
        self.container = tk.Frame(self.menu, bg=_BG)
        self.container.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(self.container, bg=_BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        
        self.scroll = _HudScrollbar(self.container, self.canvas, color=self.accent)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        
        self.list_frame = tk.Frame(self.canvas, bg=_BG)
        self.canvas.create_window((0, 0), window=self.list_frame, anchor='nw', tags='frame')
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig('frame', width=e.width) or (self.canvas.configure(scrollregion=self.canvas.bbox('all')) if self.canvas.bbox('all') else None))

        # Применяем масштабирование к элементам списка
        _sf_tk = lambda n: self.hud._fs(n + 14)

        for val in self.values:
            f = tk.Frame(self.list_frame, bg=_BG)
            f.pack(fill='x')
            is_sel = val == self.variable.get()
            
            ind = tk.Label(f, text='✦' if is_sel else '', bg=_BG, fg=self.accent, font=(self.hud._F, _sf_tk(0)), width=3)
            ind.pack(side='left', padx=(5, 0))
            
            l = tk.Label(f, text=val, bg=_BG, fg=self.accent if is_sel else _TEXT, font=(self.hud._F, _sf_tk(-1)), anchor='w', pady=4)
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
            
            f.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
            l.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
            ind.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        
        self.list_frame.update_idletasks()
        self.frame.update_idletasks()
        
        if self.canvas.bbox('all'): self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        
        # Позиционирование с учетом масштаба
        w_req = self.list_frame.winfo_reqwidth() + self.hud._px(30)
        w = int(max(self.frame.winfo_width(), w_req, self.hud._px(280)))
        h = int(min(self.hud._px(400), self.list_frame.winfo_reqheight()))
        
        x = int(self.frame.winfo_rootx())
        y = int(self.frame.winfo_rooty() + self.frame.winfo_height())
        
        zoom = getattr(self.hud, 'zoom_factor', 1.0)
        screen_w = int(self.master.winfo_screenwidth() * zoom)
        screen_h = int(self.master.winfo_screenheight() * zoom)

        if x + w > screen_w - 10: x = max(0, screen_w - w - 10)
        if y + h > screen_h - 40: 
            new_y = int(self.frame.winfo_rooty()) - h
            if new_y > 0: y = new_y
            else: y, h = 40, screen_h - 80
                
        self.menu.geometry(f'{max(100, w)}x{max(100, h)}+{x}+{y}')
        
        self.menu.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

    def close(self):
        if self.menu: 
            try: self.menu.destroy()
            except: pass
        self.menu = None
        self.is_open = False
        if self._click_id:
            try: self.master.winfo_toplevel().unbind('<Button-1>', self._click_id)
            except: pass
            self._click_id = None

    def configure(self, values=None, width=None, height=40):
        if values is not None: self.values = values
        if width is not None:
            self.frame.configure(width=width, height=height)
            self.frame.pack_propagate(False)
        else:
            self.frame.configure(height=height)
            self.frame.pack_propagate(True)


class _HUDSearchableDropdown(_HUDDropdown):
    def open(self):
        self.close()
        self.is_open = True
        self.menu = tk.Toplevel(self.master)
        self.menu.overrideredirect(True)
        self.menu.attributes('-topmost', True)
        self.menu.attributes('-alpha', 0.98)
        self.menu.configure(bg=_BG, highlightbackground=self.accent, highlightthickness=1)
        
        self.master.after(50, lambda: setattr(self, '_click_id', self.master.winfo_toplevel().bind('<Button-1>', self._check_click, add='+')))
        
        search_f = tk.Frame(self.menu, bg=_PANEL)
        search_f.pack(fill='x')
        
        import customtkinter as ctk
        sv = tk.StringVar()
        ent = ctk.CTkEntry(search_f, textvariable=sv, placeholder_text="Поиск...", 
                          height=36, font=(self.hud._F, 12),
                          fg_color=_BG, border_color=_blend(self.accent, 0.4),
                          text_color=_WHITE, placeholder_text_color=_DIM)
        ent.pack(fill='x', padx=8, pady=8)
        
        self.container = tk.Frame(self.menu, bg=_BG)
        self.container.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(self.container, bg=_BG, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.scroll = _HudScrollbar(self.container, self.canvas, color=self.accent)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        
        self.list_frame = tk.Frame(self.canvas, bg=_BG)
        self.canvas.create_window((0, 0), window=self.list_frame, anchor='nw', tags='frame')
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig('frame', width=e.width) or (self.canvas.configure(scrollregion=self.canvas.bbox('all')) if self.canvas.bbox('all') else None))

        def _rebuild(q=""):
            for w in self.list_frame.winfo_children(): w.destroy()
            filtered = [v for v in self.values if not q or q.lower() in v.lower()]
            
            for val in filtered:
                f = tk.Frame(self.list_frame, bg=_BG)
                f.pack(fill='x')
                is_sel = val == self.variable.get()
                
                ind = tk.Label(f, text='✦' if is_sel else '', bg=_BG, fg=self.accent, font=(self.hud._F, 12), width=3)
                ind.pack(side='left', padx=(5, 0))
                l = tk.Label(f, text=val, bg=_BG, fg=self.accent if is_sel else _TEXT, font=(self.hud._F, 11), anchor='w', pady=4)
                l.pack(side='left', fill='x', expand=True, padx=(5, 10))
                
                def _sel(v=val):
                    self.variable.set(v)
                    self.close()
                    if self.command: self.command(v)
                
                def _hvr(e, fw=f, lw=l, iw=ind, s=is_sel):
                    if fw.winfo_exists(): fw.configure(bg=_blend(self.accent, 0.15))
                    if lw.winfo_exists(): lw.configure(bg=_blend(self.accent, 0.15), fg=self.accent)
                    if iw.winfo_exists(): iw.configure(bg=_blend(self.accent, 0.15))
                def _lve(e, fw=f, lw=l, iw=ind, s=is_sel):
                    if fw.winfo_exists(): fw.configure(bg=_BG)
                    if lw.winfo_exists(): lw.configure(bg=_BG, fg=self.accent if s else _TEXT)
                    if iw.winfo_exists(): iw.configure(bg=_BG)
                    
                for bw in (l, ind, f):
                    bw.bind('<Button-1>', lambda e, v=val: _sel(v))
                    bw.bind('<Enter>', _hvr)
                    bw.bind('<Leave>', _lve)
                    bw.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), 'units'))

            self.list_frame.update_idletasks()
            if self.canvas.bbox('all'): self.canvas.configure(scrollregion=self.canvas.bbox('all'))

        sv.trace_add("write", lambda *a: _rebuild(sv.get()))
        _rebuild()

        self.list_frame.update_idletasks()
        self.frame.update_idletasks()
        
        h = int(min(460, self.list_frame.winfo_reqheight() + 60))
        w_req = self.list_frame.winfo_reqwidth() + 40
        w = int(max(280, self.frame.winfo_width(), w_req))
        
        x = int(self.frame.winfo_rootx())
        y = int(self.frame.winfo_rooty() + self.frame.winfo_height())
        screen_w, screen_h = int(self.master.winfo_screenwidth()), int(self.master.winfo_screenheight())
        
        if x + w > screen_w: x = max(0, screen_w - w - 10)
        if y + h > screen_h - 40:
            new_y = int(self.frame.winfo_rooty()) - h
            if new_y > 0: y = new_y
            else: y, h = 40, screen_h - 80
                
        self.menu.geometry(f'{max(100, w)}x{max(100, h)}+{x}+{y}')
        
        ent.focus_set()
        
        def _on_enter(e):
            kids = self.list_frame.winfo_children()
            if kids:
                for k in kids[0].winfo_children():
                    if isinstance(k, tk.Label) and k.cget('anchor') == 'w':
                        val = k.cget('text')
                        self.variable.set(val)
                        if self.command: self.command(val)
                        self.close()
                        break
                        
        ent.bind('<Return>', _on_enter)
        ent.bind('<Escape>', lambda e: self.close())