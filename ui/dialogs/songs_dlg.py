"""'Recognized songs' HUD panel — browses actions/song_cache.py's history
log (title/artist/links/cover/when) built up by actions/song_id.py. Read-only
display + a way to clear the log; the actual recognition always goes to
Shazam/AudD live (see song_id.py's module docstring for why the local
history no longer doubles as a match cache).
"""
from __future__ import annotations
import time
import webbrowser
import tkinter as tk
import customtkinter as ctk
from ui.hud_style import JStyle
from core import i18n
from ui.hud_widgets import _HudScrollbar
from ui.hud_constants import _BG, _PANEL, _BRD, _CYAN, _MAG, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ui.hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _center_window


def _sf(hud, n: int) -> int:
    return int(n * hud.zoom_factor)


def _relative_time(ts: float) -> str:
    if not ts:
        return ''
    secs = max(0, time.time() - ts)
    if secs < 60:
        return i18n.tr('songs.just_now')
    if secs < 3600:
        return i18n.tr('songs.minutes_ago').format(n=int(secs // 60))
    if secs < 86400:
        return i18n.tr('songs.hours_ago').format(n=int(secs // 3600))
    return i18n.tr('songs.days_ago').format(n=int(secs // 86400))


def open_songs_dialog(hud, reopen: bool = False) -> None:
    if not reopen and getattr(hud, '_songs_win', None) and hud._songs_win.winfo_exists():
        hud._songs_win.lift()
        return
    if reopen and getattr(hud, '_songs_win', None) and hud._songs_win.winfo_exists():
        hud._songs_win.destroy()

    win = tk.Toplevel(hud.root)
    hud._songs_win = win
    win.title(i18n.tr('songs.window_title'))
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    hud._track_subwin('songs', win, lambda: open_songs_dialog(hud, reopen=True))
    win.configure(bg=_BG)
    _center_window(win, 720, 780, hud.zoom_factor)
    _apply_window_icon(win, hud)
    win.attributes('-topmost', True)
    win.lift()

    top = tk.Frame(win, bg=_BG)
    top.pack(fill='x', padx=20, pady=(18, 8))
    tk.Label(top, text='♪ ' + i18n.tr('songs.window_title'), bg=_BG, fg=_CYAN,
              font=(hud._F, _sf(hud, 16), 'bold')).pack(side='left')
    ctk.CTkButton(top, text='✕', command=win.destroy, width=36, height=32,
                  fg_color='transparent', hover_color=_blend(_RED, 0.2), text_color=_RED,
                  font=(hud._F, hud._fsc(12), 'bold')).pack(side='right')

    body = tk.Frame(win, bg=_BG, highlightbackground=_blend(_CYAN, 0.2), highlightthickness=1)
    body.pack(fill='both', expand=True, padx=20, pady=(0, 12))
    canvas = tk.Canvas(body, bg=_BG, highlightthickness=0, borderwidth=0)
    canvas.pack(side='left', fill='both', expand=True, padx=8, pady=8)
    scroll = _HudScrollbar(body, canvas, color=_CYAN)
    canvas.configure(yscrollcommand=scroll.set)
    list_frame = tk.Frame(canvas, bg=_BG)
    canvas.create_window((0, 0), window=list_frame, anchor='nw', tags='frame')
    canvas.bind('<Configure>', lambda e: (canvas.itemconfig('frame', width=e.width),
                                           canvas.configure(scrollregion=canvas.bbox('all')) if canvas.bbox('all') else None))
    canvas.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, 'units'))

    _images: list = []  # keep PhotoImage refs alive — tk drops them otherwise

    def _link_btn(parent, text: str, url: str, col: str) -> None:
        ctk.CTkButton(parent, text=text, command=lambda u=url: webbrowser.open(u),
                      height=26, font=(hud._F, hud._fsc(9), 'bold'),
                      fg_color=_blend(col, 0.1), hover_color=_blend(col, 0.22), text_color=col,
                      border_color=_blend(col, 0.35), border_width=1, corner_radius=6).pack(side='left', padx=(0, 6))

    def _build_row(entry: dict) -> None:
        row = tk.Frame(list_frame, bg=_PANEL, highlightbackground=_blend(_CYAN, 0.12), highlightthickness=1)
        row.pack(fill='x', pady=4, padx=2)
        inner = tk.Frame(row, bg=_PANEL)
        inner.pack(fill='x', padx=10, pady=8)

        cover_path = entry.get('cover_path')
        if cover_path:
            try:
                from PIL import Image, ImageTk
                img = Image.open(cover_path)
                img.thumbnail((64, 64), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _images.append(photo)
                tk.Label(inner, image=photo, bg=_PANEL).pack(side='left', padx=(0, 10))
            except Exception:
                tk.Label(inner, text='♪', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(hud, 20))).pack(side='left', padx=(0, 10))
        else:
            tk.Label(inner, text='♪', bg=_PANEL, fg=_DIM, font=(hud._F, _sf(hud, 20))).pack(side='left', padx=(0, 10))

        text_col = tk.Frame(inner, bg=_PANEL)
        text_col.pack(side='left', fill='x', expand=True)
        title = entry.get('title') or i18n.tr('songs.unknown_title')
        artist = entry.get('artist') or ''
        head = f'{title} — {artist}' if artist else title
        tk.Label(text_col, text=head, bg=_PANEL, fg=_WHITE, font=(hud._F, hud._fsc(11), 'bold'), anchor='w', justify='left').pack(fill='x')
        meta_bits = [_relative_time(entry.get('recognized_at', 0))]
        src = entry.get('source')
        if src:
            meta_bits.append(src)
        tk.Label(text_col, text='  •  '.join(b for b in meta_bits if b), bg=_PANEL, fg=_DIM, font=(hud._F, hud._fsc(9)), anchor='w').pack(fill='x', pady=(2, 6))

        links = tk.Frame(text_col, bg=_PANEL)
        links.pack(fill='x')
        if entry.get('spotify_url'):
            _link_btn(links, 'Spotify', entry['spotify_url'], _GREEN)
        if entry.get('apple_music_url'):
            _link_btn(links, 'Apple Music', entry['apple_music_url'], _WHITE)
        if entry.get('youtube_url'):
            _link_btn(links, 'YouTube', entry['youtube_url'], _RED)

    from actions import song_cache
    songs = song_cache.list_recent()

    if not songs:
        tk.Label(list_frame, text=i18n.tr('songs.empty'), bg=_BG, fg=_DIM,
                  font=(hud._F, hud._fsc(11)), wraplength=600, justify='center').pack(pady=40)
    else:
        for entry in songs:
            _build_row(entry)

    bottom = tk.Frame(win, bg=_BG)
    bottom.pack(fill='x', padx=20, pady=(0, 16))
    count_lbl = tk.Label(bottom, text=i18n.tr('songs.count').format(n=len(songs)), bg=_BG, fg=_DIM, font=(hud._F, hud._fsc(9)))
    count_lbl.pack(side='left')

    def _do_clear():
        song_cache.clear()
        open_songs_dialog(hud, reopen=True)

    if songs:
        ctk.CTkButton(bottom, text=i18n.tr('songs.clear_btn'), command=_do_clear,
                      height=32, font=(hud._F, hud._fsc(10), 'bold'),
                      fg_color=_blend(_AMBER, 0.08), hover_color=_blend(_AMBER, 0.2), text_color=_AMBER,
                      border_color=_blend(_AMBER, 0.35), border_width=1, corner_radius=8).pack(side='right')
