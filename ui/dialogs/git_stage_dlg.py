from ui.hud_style import JStyle
import tkinter as tk
import customtkinter as ctk
from ui.hud_constants import _BG, _DIM, _TEXT, _CYAN, _MAG, _WHITE, _PANEL, _BRD, _AMBER, _GREEN, _SEP
from ui.hud_utils import _blend
from ui.hud_widgets import _HudScrollbar
from core import i18n

_NEW_BRANCH_SENTINEL = '＋  новая ветка'
_ROW_H = 36   # fixed virtual row height in pixels


class _Checkbox(tk.Canvas):
    """Lightweight custom checkbox drawn via canvas."""
    _SZ = 17

    def __init__(self, parent, variable: tk.BooleanVar, bg: str,
                 on_toggle=None, size: int = None, accent: str = None, **kw):
        sz = size or self._SZ
        self._sz = sz
        self._accent = accent or _CYAN
        super().__init__(parent, width=sz, height=sz,
                         bg=bg, highlightthickness=0, bd=0,
                         cursor="hand2", **kw)
        self._var = variable
        self._bg  = bg
        self._cb  = on_toggle
        variable.trace_add('write', lambda *_: self._draw())
        self.bind('<Button-1>', self._toggle)
        self._draw()

    def _toggle(self, _=None):
        self._var.set(not self._var.get())
        if self._cb: self._cb()

    def _draw(self):
        self.delete('all')
        s, p, col = self._sz, 2, self._accent
        if self._var.get():
            # filled accent box
            self.create_rectangle(p, p, s - p, s - p,
                                  fill=col, outline=col, width=0)
            # checkmark  ✓
            cx, cy = s // 2, s // 2
            self.create_line(p + 3, cy,
                             cx - 1, s - p - 3,
                             width=2, fill=_BG, capstyle='round', joinstyle='round')
            self.create_line(cx - 1, s - p - 3,
                             s - p - 2, p + 2,
                             width=2, fill=_BG, capstyle='round', joinstyle='round')
        else:
            # dark box with accent border
            self.create_rectangle(p, p, s - p, s - p,
                                  fill=_blend(col, 0.07),
                                  outline=_blend(col, 0.38), width=1)

_STATUS_LABELS = {
    'A':  ('ADD', _GREEN),
    '??': ('NEW', _GREEN),
    'M':  ('MOD', _AMBER),
    'MM': ('MOD', _AMBER),
    'AM': ('MOD', _AMBER),
    'D':  ('DEL', '#ff4444'),
    'AD': ('DEL', '#ff4444'),
}

def _status_display(st: str) -> tuple[str, str]:
    for key, val in _STATUS_LABELS.items():
        if key in st:
            return val
    return (st[:3].upper(), _DIM)


class _ToggleButton(tk.Frame):
    def __init__(self, parent, text: str, color: str, bg: str,
                 variable: tk.BooleanVar, fs: int = 11, command=None, **kw):
        super().__init__(parent, bg=bg, **kw)
        self._var = variable
        self._color = color
        self._bg = bg
        self._cmd = command
        self._disabled = False

        self._btn = tk.Label(self, text=text, font=("Consolas", fs, "bold"),
                              padx=14, pady=7, cursor="hand2")
        self._btn.pack()
        self._btn.bind("<Button-1>", self._toggle)
        self._refresh()

    def _toggle(self, _=None):
        if self._disabled: return
        self._var.set(not self._var.get())
        self._refresh()
        if self._cmd: self._cmd()

    def _refresh(self):
        on = self._var.get()
        if on:
            self._btn.configure(fg=self._bg, bg=self._color, relief="flat")
            self.configure(highlightbackground=self._color, highlightthickness=1)
        else:
            self._btn.configure(fg=_blend(self._color, 0.6),
                                 bg=_blend(self._color, 0.07), relief="flat")
            self.configure(highlightbackground=_blend(self._color, 0.28), highlightthickness=1)

    def configure_state(self, enabled: bool):
        self._disabled = not enabled
        if enabled:
            self._btn.configure(cursor="hand2"); self._refresh()
        else:
            self._btn.configure(fg=_blend(_DIM, 0.35), bg=_blend(_DIM, 0.05), cursor="")
            self.configure(highlightbackground=_blend(_DIM, 0.12), highlightthickness=1)


class GitStageDialog(ctk.CTkToplevel):
    def __init__(self, master, repo_path, files):
        super().__init__(master)
        import ui.hud as hud_mod
        hud = hud_mod._hud
        self._hu = hud

        from ui.hud_themes import get_current_theme_name
        ctk.set_appearance_mode("Light" if get_current_theme_name() == "light" else "Dark")

        self.repo_path = repo_path
        self.files = files
        self._filtered: list[int] = list(range(len(files)))  # indices into self.files
        self.result = None

        # All BooleanVars created upfront — cheap, no widgets
        self._vars: list[tk.BooleanVar] = [tk.BooleanVar(value=True) for _ in files]

        # Virtual list state
        self._virt_items: dict[int, tuple[int, tk.Frame]] = {}  # filt_idx -> (win_id, frame)
        self._canvas_w = 1

        from actions.git_commit import get_branches, get_current_branch
        self._all_branches = get_branches(repo_path)
        self._current_branch = get_current_branch(repo_path)

        self.title(i18n.tr("git.title"))
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.0)
        self.configure(fg_color=_BG)  # type: ignore[call-arg]
        tk.Toplevel.geometry(self, "")

        def _recenter():
            from ui.hud_utils import _get_work_area
            self.update_idletasks()
            rw, rh = self.winfo_reqwidth(), self.winfo_reqheight()
            l, t, r, b = _get_work_area()
            sw = min(rw, r - l - 20)
            sh = min(rh, int((b - t) * 0.94))
            x = l + (r - l) // 2 - sw // 2
            tk.Toplevel.geometry(self, f"{sw}x{sh}+{x}+{t + 30}")

        self.drag_data = {"x": 0, "y": 0}
        def _start(e): self.drag_data["x"], self.drag_data["y"] = e.x, e.y
        def _move(e):
            tk.Toplevel.geometry(self,
                f"+{self.winfo_x()+(e.x-self.drag_data['x'])}+{self.winfo_y()+(e.y-self.drag_data['y'])}")

        # ── outer glow border ────────────────────────────────────────────────
        outer = tk.Frame(self, bg=_blend(_CYAN, 0.3), padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        self.main_frame = tk.Frame(outer, bg=_BG)
        self.main_frame.pack(fill="both", expand=True)

        # ── header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self.main_frame, bg=_PANEL, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        hdr.bind("<Button-1>", _start); hdr.bind("<B1-Motion>", _move)

        tk.Frame(hdr, bg=_CYAN, width=3).pack(side="left", fill="y")
        tk.Label(hdr, text="⬡", font=("Consolas", 15), fg=_CYAN, bg=_PANEL).pack(side="left", padx=(14, 7))
        tk.Label(hdr, text=i18n.tr("git.header").replace("⬡  ", ""),
                 font=("Consolas", 13, "bold"), fg=_WHITE, bg=_PANEL).pack(side="left")

        self._hdr_branch = tk.Label(hdr, text=f"  {self._current_branch}  ",
                                     font=("Consolas", 10, "bold"), fg=_BG, bg=_CYAN, padx=2, pady=4)
        self._hdr_branch.pack(side="left", padx=16)

        close_btn = tk.Label(hdr, text="✕", font=("Consolas", 12),
                              fg=_DIM, bg=_PANEL, cursor="hand2", padx=18)
        close_btn.pack(side="right")
        close_btn.bind("<Button-1>", lambda e: self._cancel())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#ff4444"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=_DIM))

        # ── footer ───────────────────────────────────────────────────────────
        footer = tk.Frame(self.main_frame, bg=_BG)
        footer.pack(fill="x", side="bottom", padx=26, pady=(0, 20))

        tk.Label(footer, text=i18n.tr("git.voice_hint"),
                 font=("Segoe UI", 11), fg=_blend(_DIM, 0.6), bg=_BG).pack(pady=(0, 12))

        btn_row = tk.Frame(footer, bg=_BG)
        btn_row.pack()
        _fs = self._hu._fs(12)

        self.btn_ok = ctk.CTkButton(btn_row, text=f"✦  {i18n.tr('git.submit')}",
                                     width=210, height=44,
                                     fg_color=_blend(_CYAN, 0.15), hover_color=_blend(_CYAN, 0.28),
                                     border_color=_CYAN, border_width=2,
                                     text_color=_CYAN, font=("Consolas", _fs, "bold"),
                                     corner_radius=10, command=self._confirm)
        self.btn_ok.pack(side="left", padx=7)

        ctk.CTkButton(btn_row, text=f"✕  {i18n.tr('git.cancel')}",
                       width=210, height=44,
                       fg_color="transparent", hover_color=_blend(_DIM, 0.08),
                       border_color=_blend(_DIM, 0.4), border_width=2,
                       text_color=_blend(_DIM, 0.7), font=("Consolas", _fs, "bold"),
                       corner_radius=10, command=self._cancel).pack(side="left", padx=7)

        # ── options panel ────────────────────────────────────────────────────
        _opts_bg = _blend(_PANEL, 0.65)
        opts_panel = tk.Frame(self.main_frame, bg=_opts_bg,
                               highlightbackground=_blend(_CYAN, 0.12), highlightthickness=1)
        opts_panel.pack(fill="x", side="bottom", padx=26, pady=(0, 10))

        inner_opts = tk.Frame(opts_panel, bg=_opts_bg)
        inner_opts.pack(fill="x", padx=18, pady=14)

        _lbl_font = ("Consolas", 11, "bold")
        _lbl_w    = 12

        # branch row
        branch_row = tk.Frame(inner_opts, bg=_opts_bg)
        branch_row.pack(fill="x", pady=(0, 12))

        tk.Label(branch_row, text=i18n.tr("git.branch_label"), font=_lbl_font,
                 fg=_blend(_CYAN, 0.75), bg=_opts_bg, width=_lbl_w, anchor="w").pack(side="left")

        self._branch_var = tk.StringVar(value=self._current_branch)
        self._branch_menu = ctk.CTkOptionMenu(
            branch_row, variable=self._branch_var,
            values=self._all_branches + [_NEW_BRANCH_SENTINEL],
            width=210, height=34,
            fg_color=_blend(_CYAN, 0.09), button_color=_blend(_CYAN, 0.2),
            button_hover_color=_blend(_CYAN, 0.34), text_color=_TEXT,
            font=("Consolas", self._hu._fs(11)),
            dropdown_fg_color=_PANEL, dropdown_text_color=_TEXT,
            dropdown_hover_color=_blend(_CYAN, 0.16),
            command=self._on_branch_select,
        )
        self._branch_menu.pack(side="left", padx=(0, 10))

        self._new_branch_entry = ctk.CTkEntry(
            branch_row, height=34, width=180,
            font=("Consolas", self._hu._fs(11)), fg_color=_opts_bg,
            border_color=_blend(_GREEN, 0.4), text_color=_TEXT,
            placeholder_text=i18n.tr("git.new_branch_ph"),
            placeholder_text_color=_blend(_TEXT, 0.25),
            border_width=2, corner_radius=JStyle.RAD_PANEL,
        )

        # toggle row
        toggle_row = tk.Frame(inner_opts, bg=_opts_bg)
        toggle_row.pack(fill="x")

        tk.Label(toggle_row, text="OPTIONS", font=_lbl_font,
                 fg=_blend(_DIM, 0.5), bg=_opts_bg, width=_lbl_w, anchor="w").pack(side="left")

        tgl_grp = tk.Frame(toggle_row, bg=_opts_bg)
        tgl_grp.pack(side="left")

        self._push_var     = tk.BooleanVar(value=True)
        self._force_var    = tk.BooleanVar(value=False)
        self._upstream_var = tk.BooleanVar(value=False)
        _tfs = self._hu._fs(11)

        self._tgl_push = _ToggleButton(tgl_grp, f" ↑  {i18n.tr('git.push_label')} ",
                                        _CYAN, _opts_bg, self._push_var, fs=_tfs,
                                        command=self._on_push_toggle)
        self._tgl_push.pack(side="left", padx=(0, 7))

        self._tgl_force = _ToggleButton(tgl_grp, f" ⚠  {i18n.tr('git.force_label')} ",
                                         _AMBER, _opts_bg, self._force_var, fs=_tfs)
        self._tgl_force.pack(side="left", padx=(0, 7))

        self._tgl_upstream = _ToggleButton(tgl_grp, f" ⇡  {i18n.tr('git.upstream_label')} ",
                                            _GREEN, _opts_bg, self._upstream_var, fs=_tfs)
        self._tgl_upstream.pack(side="left")

        # PR title row
        self._pr_row = tk.Frame(inner_opts, bg=_opts_bg)
        self._pr_row.pack(fill="x", pady=(12, 0))

        tk.Label(self._pr_row, text=i18n.tr("git.pr_title_label"), font=_lbl_font,
                 fg=_blend(_MAG, 0.75), bg=_opts_bg, width=_lbl_w, anchor="w").pack(side="left")

        self._pr_entry = ctk.CTkEntry(
            self._pr_row, height=34, font=("Consolas", self._hu._fs(11)),
            fg_color=_opts_bg, border_color=_blend(_MAG, 0.3), text_color=_TEXT,
            placeholder_text=i18n.tr("git.pr_title_ph"),
            placeholder_text_color=_blend(_TEXT, 0.22),
            border_width=2, corner_radius=JStyle.RAD_PANEL,
        )
        self._pr_entry.pack(side="left", fill="x", expand=True)

        # ── commit message ────────────────────────────────────────────────────
        msg_wrap = tk.Frame(self.main_frame, bg=_BG)
        msg_wrap.pack(fill="x", side="bottom", padx=26, pady=(0, 8))

        msg_hdr = tk.Frame(msg_wrap, bg=_BG)
        msg_hdr.pack(fill="x", pady=(0, 7))
        tk.Frame(msg_hdr, bg=_CYAN, width=3, height=18).pack(side="left")
        tk.Label(msg_hdr, text=f"  {i18n.tr('git.commit_msg')}",
                 font=("Consolas", 11, "bold"), fg=_blend(_CYAN, 0.8), bg=_BG).pack(side="left")

        self.msg_entry = ctk.CTkEntry(
            msg_wrap, height=46, font=("Consolas", self._hu._fs(14)),
            fg_color=_blend(_PANEL, 0.7), border_color=_blend(_CYAN, 0.22),
            text_color=_TEXT, placeholder_text=i18n.tr("git.commit_ph"),
            placeholder_text_color=_blend(_TEXT, 0.22),
            border_width=2, corner_radius=JStyle.RAD_PANEL,
        )
        self.msg_entry.pack(fill="x")
        self.msg_entry.focus_set()

        # ── file list (virtual) ───────────────────────────────────────────────
        c_wrap = tk.Frame(self.main_frame, bg=_BG)
        c_wrap.pack(fill="both", expand=True, padx=26, pady=(16, 8))

        self.search_entry = ctk.CTkEntry(
            c_wrap, placeholder_text=i18n.tr("git.search"), height=38,
            fg_color=_blend(_PANEL, 0.7), border_color=_blend(_CYAN, 0.22),
            text_color=_TEXT, font=("Consolas", self._hu._fs(12)),
            placeholder_text_color=_blend(_TEXT, 0.28),
            border_width=2, corner_radius=JStyle.RAD_PANEL,
        )
        self.search_entry.pack(fill="x", pady=(0, 10))
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_items())

        list_hdr = tk.Frame(c_wrap, bg=_BG)
        list_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(list_hdr, text=i18n.tr("git.changes"),
                 font=("Consolas", 11, "bold"), fg=_blend(_DIM, 0.7), bg=_BG).pack(side="left")

        self.all_var = tk.BooleanVar(value=True)
        self.all_cb = ctk.CTkCheckBox(
            list_hdr, text=i18n.tr("git.select_all"), variable=self.all_var,
            font=("Consolas", 11, "bold"), text_color=_CYAN,
            fg_color=_CYAN, hover_color=_CYAN, border_color=_blend(_CYAN, 0.35),
            checkmark_color=_BG, width=22, height=22, corner_radius=JStyle.RAD_BTN,
            command=self._toggle_all,
        )
        self.all_cb.pack(side="right")

        from ui.hud_utils import _get_work_area
        _wl, _wt, _wr, _wb = _get_work_area()
        _max_canvas_h = int((_wb - _wt) * 0.33)

        scroll_container = tk.Frame(c_wrap, bg=_blend(_PANEL, 0.45),
                                     highlightbackground=_blend(_CYAN, 0.12), highlightthickness=1)
        scroll_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(scroll_container, bg=_blend(_PANEL, 0.45),
                                 highlightthickness=0, height=_max_canvas_h)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll = _HudScrollbar(scroll_container, self.canvas, color=_CYAN)
        self.canvas.configure(yscrollcommand=self.scroll.set)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        self._update_scrollregion()

        from ui.voice_prompt_bridge import register_voice_prompt
        from ui.dialogs.commit_dlg import _VOICE_COMMIT_CONFIRM
        from ui.dialogs.name_dlg import _VOICE_DOC_CANCEL
        register_voice_prompt(self, on_confirm=self._confirm, on_cancel=self._cancel,
                               confirm_phrases=_VOICE_COMMIT_CONFIRM, cancel_phrases=_VOICE_DOC_CANCEL)

        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._confirm())
        _recenter()
        self._fade()

    # ── virtual list ─────────────────────────────────────────────────────────

    _LIST_BG = None
    _ROW_ALT = None
    _FS_FILE = None

    def _row_colors(self):
        if self._LIST_BG is None:
            GitStageDialog._LIST_BG = _blend(_PANEL, 0.45)
            GitStageDialog._ROW_ALT = _blend(_PANEL, 0.65)
            GitStageDialog._FS_FILE = self._hu._fs(11)
        return self._LIST_BG, self._ROW_ALT, self._FS_FILE

    def _update_scrollregion(self):
        total_h = max(len(self._filtered) * _ROW_H, 1)
        self.canvas.configure(scrollregion=(0, 0, 1, total_h))

    def _visible_range(self) -> tuple[int, int]:
        top = self.canvas.canvasy(0)
        h   = self.canvas.winfo_height() or 1
        first = max(0, int(top / _ROW_H) - 1)
        last  = min(len(self._filtered), int((top + h) / _ROW_H) + 2)
        return first, last

    def _render_visible(self):
        if not self.winfo_exists(): return
        first, last = self._visible_range()
        w = self._canvas_w or self.canvas.winfo_width() or 600

        # destroy rows outside visible range
        for fi in list(self._virt_items):
            if fi < first or fi >= last:
                win_id, frame = self._virt_items.pop(fi)
                self.canvas.delete(win_id)
                frame.destroy()

        list_bg, row_alt, fs = self._row_colors()

        # create missing visible rows
        for fi in range(first, last):
            if fi in self._virt_items: continue
            real_i = self._filtered[fi]
            item = self.files[real_i]
            row_bg = list_bg if fi % 2 == 0 else row_alt

            f = tk.Frame(self.canvas, bg=row_bg, height=_ROW_H)
            f.pack_propagate(False)

            lbl_text, lbl_color = _status_display(item['status'])
            tk.Label(f, text=f" {lbl_text} ", font=("Consolas", 9, "bold"),
                     fg=lbl_color, bg=_blend(lbl_color, 0.10), padx=4).pack(
                side="right", padx=(6, 14), pady=0)

            var = self._vars[real_i]

            # custom canvas checkbox
            chk = _Checkbox(f, var, row_bg, on_toggle=self._sync_select_all)
            chk.pack(side="left", padx=(16, 8))

            # filename label — clicking it also toggles the checkbox
            lbl = tk.Label(f, text=item['file'], font=("Consolas", fs),
                           fg=_blend(_TEXT, 0.9), bg=row_bg,
                           anchor="w", cursor="hand2")
            lbl.pack(side="left", fill="x", expand=True)
            lbl.bind("<Button-1>", lambda e, v=var: (v.set(not v.get()),
                                                      self._sync_select_all()))

            win_id = self.canvas.create_window(0, fi * _ROW_H, window=f,
                                                anchor="nw", width=w)
            self._virt_items[fi] = (win_id, f)

    def _on_canvas_configure(self, e):
        self._canvas_w = e.width
        # update width of all existing windows
        for win_id, _ in self._virt_items.values():
            self.canvas.itemconfig(win_id, width=e.width)
        self._render_visible()

    def _on_mousewheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        self._render_visible()

    def _sync_select_all(self):
        checked = sum(1 for v in self._vars if v.get())
        self.all_var.set(checked == len(self._vars))

    # ── branch handling ───────────────────────────────────────────────────────

    def _on_branch_select(self, value: str):
        if value == _NEW_BRANCH_SENTINEL:
            self._new_branch_entry.pack(side="left", padx=(0, 4))
            self._new_branch_entry.focus_set()
            self._hdr_branch.configure(text="  новая ветка  ", bg=_GREEN, fg=_BG)
        else:
            self._new_branch_entry.pack_forget()
            self._hdr_branch.configure(text=f"  {value}  ", bg=_CYAN, fg=_BG)

    def _on_push_toggle(self):
        enabled = self._push_var.get()
        self._tgl_force.configure_state(enabled)
        self._tgl_upstream.configure_state(enabled)
        if enabled: self._pr_row.pack(fill="x", pady=(12, 0))
        else:        self._pr_row.pack_forget()

    def _resolve_branch(self) -> str:
        if self._branch_var.get() == _NEW_BRANCH_SENTINEL:
            return self._new_branch_entry.get().strip()
        return self._branch_var.get()

    # ── search / select all ───────────────────────────────────────────────────

    def _filter_items(self):
        q = self.search_entry.get().lower()
        self._filtered = [i for i, f in enumerate(self.files)
                          if q in f['file'].lower()]
        # destroy all rendered rows — positions change
        for win_id, frame in self._virt_items.values():
            self.canvas.delete(win_id)
            frame.destroy()
        self._virt_items.clear()
        self._update_scrollregion()
        self.canvas.yview_moveto(0)
        self._render_visible()

    def _toggle_all(self):
        v = self.all_var.get()
        for var in self._vars: var.set(v)
        # refresh visible checkbutton appearance (tk vars update automatically,
        # but visible rows may need a redraw nudge)
        self.canvas.update_idletasks()

    # ── fade ──────────────────────────────────────────────────────────────────

    def _fade(self, step: int = 0):
        if not self.winfo_exists(): return
        _steps = (0.35, 0.75, 0.98)
        self.attributes("-alpha", _steps[step])
        if step < len(_steps) - 1:
            self.after(35, lambda: self._fade(step + 1))

    # ── confirm / cancel ──────────────────────────────────────────────────────

    def _confirm(self):
        sel = [self.files[i]['file'] for i, v in enumerate(self._vars) if v.get()]
        branch   = self._resolve_branch()
        pr_title = self._pr_entry.get().strip() if self._push_var.get() else ''
        self.result = {
            'files':    sel,
            'message':  self.msg_entry.get().strip(),
            'branch':   branch,
            'push':     self._push_var.get(),
            'force':    self._force_var.get(),
            'upstream': self._upstream_var.get(),
            'open_pr':  bool(pr_title),
            'pr_title': pr_title,
        }
        self._cleanup()

    def _cancel(self):
        self.result = None
        self._cleanup()

    def _cleanup(self):
        try: self.unbind_all("<MouseWheel>")
        except: pass
        try:
            from ui.voice_prompt_bridge import unregister_voice_prompt
            unregister_voice_prompt(self)
        except: pass
        self.destroy()


def ask_git_stage(repo_path, files) -> dict | None:
    import ui.hud as hud
    m = hud._hud.root if hud._hud else None
    win = GitStageDialog(m, repo_path, files)
    win.wait_window()
    return win.result
