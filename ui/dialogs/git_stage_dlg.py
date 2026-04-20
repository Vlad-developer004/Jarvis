import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _DIM, _TEXT, _CYAN, _MAG, _WHITE, _PANEL, _BRD, _AMBER
from ui.hud_utils import _blend
from ui.hud_widgets import _HudScrollbar

class GitStageDialog(ctk.CTkToplevel):
    def __init__(self, master, repo_path, files):
        super().__init__(master)
        import ui.hud as hud_mod
        from ui.hud_constants import _BG, _DIM, _TEXT, _CYAN, _MAG, _WHITE, _PANEL, _BRD, _AMBER, _SEP
        hud = hud_mod._hud
        self._hu = hud
        
        self.repo_path = repo_path
        self.files = files
        self.result = None
        
        self.title("GIT CONTROL — J.A.R.V.I.S.")
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.0)
        self.configure(bg=_BG)
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Compact geometry: 620x580, aligned to top
        w, h = 620, 580
        gw, gh = int(w * hud.zoom_factor), int(h * hud.zoom_factor)
        self.geometry(f"{gw}x{gh}+{(sw-gw)//2}+{hud._px(60)}")
        
        self.drag_data = {"x": 0, "y": 0}
        def start_move(e): self.drag_data["x"], self.drag_data["y"] = e.x, e.y
        def on_move(e):
            x, y = self.winfo_x() + (e.x - self.drag_data["x"]), self.winfo_y() + (e.y - self.drag_data["y"])
            self.geometry(f"+{x}+{y}")

        self.main_frame = tk.Frame(self, bg=_BG, highlightbackground=_CYAN, highlightthickness=1)
        self.main_frame.pack(fill="both", expand=True)
        
        # Header
        hdr = tk.Frame(self.main_frame, bg=_PANEL, height=52)
        hdr.pack(fill="x")
        hdr.bind("<Button-1>", start_move); hdr.bind("<B1-Motion>", on_move)
        tk.Label(hdr, text="⬡  GIT CONTROL SYSTEM", font=("Consolas", 15, "bold"), fg=_CYAN, bg=_PANEL).pack(side="left", padx=20)
        close_btn = tk.Label(hdr, text="✕", font=("Consolas", hud._fs(12)), fg=_DIM, bg=_PANEL, cursor="hand2")
        close_btn.pack(side="right", padx=16)
        close_btn.bind("<Button-1>", lambda e: self._cancel())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#ff4444"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=_DIM))

        c_wrap = tk.Frame(self.main_frame, bg=_BG)
        c_wrap.pack(fill="both", expand=True, padx=30, pady=(40, 20))
        
        # SEARCH BAR
        self.search_entry = ctk.CTkEntry(
            c_wrap, placeholder_text="Поиск файлов...",
            height=48, # Slightly taller for better touch/visibility
            fg_color="#0d0f1e", border_color=_blend(_CYAN, 0.3),
            text_color=_WHITE, font=("Consolas", self._hu._fs(12)),
            placeholder_text_color=_blend(_WHITE, 0.3),
            border_width=2, corner_radius=12
        )
        self.search_entry.pack(fill="x", pady=(0, 20))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_items())

        # LIST HEADER
        list_hdr = tk.Frame(c_wrap, bg=_BG)
        list_hdr.pack(fill="x", pady=(0, 5))
        
        tk.Label(list_hdr, text="ИЗМЕНЕНИЯ", font=("Consolas", hud._fs(11), "bold"), fg=_DIM, bg=_BG).pack(side="left")
        
        self.all_var = tk.BooleanVar(value=True)
        self.all_cb = ctk.CTkCheckBox(
            list_hdr, text="ВЫБРАТЬ ВСЕ", variable=self.all_var,
            font=("Consolas", hud._fs(10), "bold"), text_color=_CYAN,
            fg_color=_CYAN, hover_color=_CYAN, border_color=_CYAN,
            checkmark_color=_BG, width=22, height=22, corner_radius=6,
            command=self._toggle_all
        )
        self.all_cb.pack(side="right")

        # SCROLL AREA
        scroll_container = tk.Frame(c_wrap, bg="#05070a", highlightbackground=_blend(_CYAN, 0.1), highlightthickness=1)
        scroll_container.pack(fill="both", expand=True)
        
        self.canvas = tk.Canvas(scroll_container, bg="#05070a", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll = _HudScrollbar(scroll_container, self.canvas, color=_CYAN)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        
        self.list_inner = tk.Frame(self.canvas, bg="#05070a")
        self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw", tags="frame")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig("frame", width=e.width))
        self.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.item_rows = []
        self._load_batch(0, 40)

        # MESSAGE SECTION
        tk.Frame(c_wrap, bg=_blend(_CYAN, 0.15), height=1).pack(fill="x", pady=18)
        tk.Label(c_wrap, text="✧ СООБЩЕНИЕ КОММИТА", font=("Consolas", self._hu._fs(10), "bold"), fg=_CYAN, bg=_BG).pack(fill="x", anchor="w", pady=(0, 10))
        
        self.msg_entry = ctk.CTkEntry(
            c_wrap, height=52, font=("Consolas", self._hu._fs(14)),
            fg_color="#0d0f1e", border_color=_blend(_CYAN, 0.25),
            text_color=_WHITE, placeholder_text="Опишите изменения...",
            placeholder_text_color=_blend(_WHITE, 0.2),
            border_width=2, corner_radius=12
        )
        self.msg_entry.pack(fill="x")
        self.msg_entry.focus_set()

        # FOOTER
        footer = tk.Frame(self.main_frame, bg=_BG)
        footer.pack(fill="x", side="bottom", pady=20)
        tk.Label(footer, text="Голосом: «коммит» / «отмена»  ·  Esc / Enter", font=("Segoe UI", 10), fg=_DIM, bg=_BG).pack(pady=(0, 15))
        
        btn_inner = tk.Frame(footer, bg=_BG)
        btn_inner.pack()
        self.btn_ok = ctk.CTkButton(
            btn_inner, text="ОТПРАВИТЬ  ✦", width=220, height=48,
            fg_color=_blend(_CYAN, 0.12), border_color=_CYAN, border_width=2,
            text_color=_CYAN, font=("Consolas", self._hu._fs(12), "bold"), corner_radius=12,
            command=self._confirm
        )
        self.btn_ok.pack(side="left", padx=12)
        ctk.CTkButton(
            btn_inner, text="ОТМЕНА  ✕", width=220, height=48,
            fg_color="transparent", border_color=_DIM, border_width=2,
            text_color=_DIM, font=("Consolas", self._hu._fs(12), "bold"), corner_radius=12,
            command=self._cancel
        ).pack(side="left", padx=12)

        from ui.voice_prompt_bridge import register_voice_prompt
        from ui.dialogs.commit_dlg import _VOICE_COMMIT_CONFIRM
        from ui.dialogs.name_dlg import _VOICE_DOC_CANCEL
        register_voice_prompt(self, on_confirm=self._confirm, on_cancel=self._cancel,
                               confirm_phrases=_VOICE_COMMIT_CONFIRM, cancel_phrases=_VOICE_DOC_CANCEL)
        
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._confirm())
        self._fade()

    def _load_batch(self, start, size):
        end = min(start + size, len(self.files))
        from ui.hud_constants import _BG, _DIM, _TEXT, _CYAN, _MAG, _WHITE, _PANEL, _BRD, _AMBER
        for i in range(start, end):
            item = self.files[i]
            f = tk.Frame(self.list_inner, bg="#05070a")
            f.pack(fill="x", pady=1)
            var = tk.BooleanVar(value=True)
            st = item['status']
            st_text = "U" if st == "??" else st
            st_color = _CYAN if st in ('A', '??') else (_AMBER if 'M' in st else "#ff4444")
            
            cb = ctk.CTkCheckBox(f, text=item['file'], variable=var,
                                 font=("Consolas", self._hu._fs(10)), text_color=_TEXT,
                                 fg_color=_CYAN, hover_color=_CYAN, border_color=_blend(_CYAN, 0.25),
                                 checkmark_color=_BG, width=20, height=20, corner_radius=6)
            cb.pack(side="left", padx=15, pady=4, fill="x", expand=True)
            
            # Status Badge (Bigger Chip)
            badge_f = tk.Frame(f, bg=_blend(st_color, 0.15), padx=6, pady=2)
            badge_f.pack(side="right", padx=15)
            
            tk.Label(badge_f, text=st_text, font=("Consolas", self._hu._fs(9), "bold"), 
                     fg=st_color, bg=_blend(st_color, 0.15), width=2).pack()
            
            self.item_rows.append({'frame': f, 'file': item['file'], 'var': var})
        
        self.list_inner.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if end < len(self.files): self.after(40, lambda: self._load_batch(end, 50))

    def _fade(self, alpha=0.0):
        if not self.winfo_exists(): return
        alpha = min(alpha + 0.1, 0.98); self.attributes("-alpha", alpha)
        if alpha < 0.98: self.after(10, lambda: self._fade(alpha))

    def _filter_items(self):
        query = self.search_entry.get().lower()
        for row in self.item_rows:
            if query in row['file'].lower(): row['frame'].pack(fill="x", pady=1)
            else: row['frame'].pack_forget()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _toggle_all(self):
        v = self.all_var.get()
        for r in self.item_rows: r['var'].set(v)

    def _confirm(self):
        sel = [r['file'] for r in self.item_rows if r['var'].get()]
        self.result = (sel, self.msg_entry.get().strip()); self._cleanup()

    def _cancel(self): self.result = None; self._cleanup()

    def _cleanup(self):
        try: self.unbind_all("<MouseWheel>")
        except: pass
        try:
            from ui.voice_prompt_bridge import unregister_voice_prompt
            unregister_voice_prompt(self)
        except: pass
        self.destroy()

def ask_git_stage(repo_path, files):
    import ui.hud as hud
    m = hud._hud.root if hud._hud else None
    win = GitStageDialog(m, repo_path, files); win.wait_window(); return win.result
