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

_COVER_SIZE = 84
_SOURCE_ACCENT = {'shazam': _CYAN, 'audd': _MAG}
_ROW_H_ESTIMATE = 128  # card height + spacing, for sizing the window to content


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


def _make_cover_photo(cover_path: str):
    """Loads and letterboxes cover art onto a fixed _COVER_SIZE square so
    every card lines up regardless of the source image's aspect ratio, or
    returns None if there's no usable art. Caller must keep a strong
    reference to the result — Tk drops a PhotoImage with no Python owner."""
    if not cover_path:
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(cover_path).convert('RGB')
        img.thumbnail((_COVER_SIZE, _COVER_SIZE), Image.Resampling.LANCZOS)
        canvas_img = Image.new('RGB', (_COVER_SIZE, _COVER_SIZE), _PANEL_RGB)
        off = ((_COVER_SIZE - img.width) // 2, (_COVER_SIZE - img.height) // 2)
        canvas_img.paste(img, off)
        return ImageTk.PhotoImage(canvas_img)
    except Exception:
        return None


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


_PANEL_RGB = _hex_to_rgb(_PANEL)


def open_songs_dialog(hud, reopen: bool = False) -> None:
    if not reopen and getattr(hud, '_songs_win', None) and hud._songs_win.winfo_exists():
        hud._songs_win.lift()
        return
    if reopen and getattr(hud, '_songs_win', None) and hud._songs_win.winfo_exists():
        hud._songs_win.destroy()

    from actions import song_cache
    songs = song_cache.list_recent()

    win = tk.Toplevel(hud.root)
    hud._songs_win = win
    win.title(i18n.tr('songs.window_title'))
    _set_dark_title_bar(win)
    win.after(100, lambda: _set_dark_title_bar(win))
    hud._track_subwin('songs', win, lambda: open_songs_dialog(hud, reopen=True))
    win.configure(bg=_BG)
    # Sized to content instead of always the max — an empty/near-empty
    # history doesn't need to open into a mostly-blank 780px scroll area.
    height = min(780, max(340, 190 + len(songs) * _ROW_H_ESTIMATE))
    _center_window(win, 720, height, hud.zoom_factor)
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
                      height=28, font=(hud._F, hud._fsc(9), 'bold'),
                      fg_color=_blend(col, 0.12), hover_color=_blend(col, 0.26), text_color=col,
                      border_color=_blend(col, 0.4), border_width=1, corner_radius=7).pack(side='left', padx=(0, 6))

    def _build_row(entry: dict) -> None:
        source = entry.get('source') or ''
        accent = _SOURCE_ACCENT.get(source, _CYAN)

        card = tk.Frame(list_frame, bg=_BG)
        card.pack(fill='x', pady=6, padx=2)
        row = tk.Frame(card, bg=_PANEL, highlightbackground=_blend(accent, 0.22), highlightthickness=1)
        row.pack(fill='x', side='left', expand=True)
        accent_bar = tk.Frame(row, bg=accent, width=4)
        accent_bar.pack(side='left', fill='y')
        inner = tk.Frame(row, bg=_PANEL)
        inner.pack(fill='x', expand=True, padx=(12, 14), pady=12)

        def _on_enter(_e=None):
            row.configure(highlightbackground=_blend(accent, 0.55))
        def _on_leave(_e=None):
            row.configure(highlightbackground=_blend(accent, 0.22))
        for w in (row, inner):
            w.bind('<Enter>', _on_enter)
            w.bind('<Leave>', _on_leave)

        cover_frame = tk.Frame(inner, bg=_blend(accent, 0.08), width=_COVER_SIZE, height=_COVER_SIZE,
                                highlightbackground=_blend(accent, 0.3), highlightthickness=1)
        cover_frame.pack_propagate(False)
        cover_frame.pack(side='left', padx=(0, 14))
        photo = _make_cover_photo(entry.get('cover_path'))
        if photo is not None:
            _images.append(photo)
            lbl = tk.Label(cover_frame, image=photo, bg=_PANEL, borderwidth=0)
            lbl.image = photo  # belt-and-suspenders against GC alongside _images
            lbl.place(relx=0.5, rely=0.5, anchor='center')
        else:
            tk.Label(cover_frame, text='♪', bg=_blend(accent, 0.08), fg=accent,
                     font=(hud._F, _sf(hud, 26))).place(relx=0.5, rely=0.5, anchor='center')

        text_col = tk.Frame(inner, bg=_PANEL)
        text_col.pack(side='left', fill='both', expand=True)
        title = entry.get('title') or i18n.tr('songs.unknown_title')
        artist = entry.get('artist') or ''
        tk.Label(text_col, text=title, bg=_PANEL, fg=_WHITE, font=(hud._F, hud._fsc(13), 'bold'),
                 anchor='w', justify='left').pack(fill='x')
        if artist:
            tk.Label(text_col, text=artist, bg=_PANEL, fg=_blend(accent, 0.85), font=(hud._F, hud._fsc(10)),
                     anchor='w', justify='left').pack(fill='x', pady=(1, 0))
        meta_bits = [_relative_time(entry.get('recognized_at', 0))]
        if source:
            meta_bits.append(source)
        tk.Label(text_col, text='  •  '.join(b for b in meta_bits if b), bg=_PANEL, fg=_DIM,
                 font=(hud._F, hud._fsc(9)), anchor='w').pack(fill='x', pady=(3, 8))

        links = tk.Frame(text_col, bg=_PANEL)
        links.pack(fill='x')
        if entry.get('spotify_url'):
            _link_btn(links, 'Spotify', entry['spotify_url'], _GREEN)
        if entry.get('apple_music_url'):
            _link_btn(links, 'Apple Music', entry['apple_music_url'], _WHITE)
        if entry.get('youtube_url'):
            _link_btn(links, 'YouTube', entry['youtube_url'], _RED)

    if not songs:
        empty = tk.Frame(list_frame, bg=_BG)
        empty.pack(fill='both', expand=True, pady=(60, 0))
        tk.Label(empty, text='♪', bg=_BG, fg=_blend(_CYAN, 0.3), font=(hud._F, _sf(hud, 40))).pack()
        tk.Label(empty, text=i18n.tr('songs.empty'), bg=_BG, fg=_DIM,
                  font=(hud._F, hud._fsc(11)), wraplength=600, justify='center').pack(pady=(10, 0))
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
