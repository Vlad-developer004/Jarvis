"""Song/video disambiguation picker.

Shown when "включи песню X" (core/handler/dispatch.py::_handle_play_yt)
finds several near-duplicate-titled YouTube results (official video / lyrics
/ live / audio versions of the same track, or several unrelated uploads with
near-identical titles — see actions.youtube.candidates_are_ambiguous()).
Click a card, or say "первое"/"второе"/... (core/handler/interactive.py's
'yt_pick_ask' state calls select_index() below) to choose. Falls back to the
top search result automatically if nothing is chosen before the timeout.
"""
from __future__ import annotations
import hashlib
import os
import tempfile
import threading
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

from ui.hud_style import JStyle
from ui.hud_constants import _BG, _PANEL, _CYAN, _TEXT, _DIM
from ui.hud_utils import _blend, _set_dark_title_bar, _apply_window_icon, _center_window
from core.logging_setup import get_logger as _get_logger
from core.system.version import APP_VERSION

_log = _get_logger('yt_picker')
_CACHE_DIR = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')

# Module-level "currently open picker" singleton — same pattern as
# ui/hud_ai_window.py's _window_instance, so the voice-driven interactive
# state (which runs on a different thread and has no reference to the
# window it needs to resolve) can find it via select_index()/cancel_picker().
_lock = threading.Lock()
_current: dict | None = None


def _download_thumb(url: str) -> str | None:
    if not url:
        print('[YT-PICKER] no thumbnail url on this candidate — nothing to download', flush=True)
        return None
    try:
        import requests
        os.makedirs(_CACHE_DIR, exist_ok=True)
        h = hashlib.md5(url.encode('utf-8')).hexdigest()
        path = os.path.join(_CACHE_DIR, f'ytpick_{h}.jpg')
        if not os.path.exists(path):
            print(f'[YT-PICKER] downloading thumbnail: {url}', flush=True)
            resp = requests.get(url, timeout=6.0, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
            if resp.status_code != 200:
                print(f'[YT-PICKER] thumbnail download HTTP {resp.status_code} for {url}', flush=True)
                _log.warning('thumbnail download HTTP %s for %s', resp.status_code, url)
                return None
            with open(path, 'wb') as f:
                f.write(resp.content)
            print(f'[YT-PICKER] thumbnail saved to {path}', flush=True)
        return path
    except Exception as e:
        print(f'[YT-PICKER] thumbnail download failed for {url}: {e}', flush=True)
        _log.warning('thumbnail download failed for %s: %s', url, e)
        return None


def select_index(i: int) -> bool:
    """Called from core/handler/interactive.py's 'yt_pick_ask' state when the
    user says an ordinal ("первое"/"второе"/...). Returns False if there's no
    picker open right now or the index is out of range."""
    with _lock:
        cur = _current
    if cur is None:
        return False
    candidates = cur['candidates']
    if i < 0 or i >= len(candidates):
        return False
    cur['finish'](candidates[i], i, False)
    return True


def is_picker_open() -> bool:
    with _lock:
        return _current is not None


def cancel_picker() -> None:
    """Close the picker without picking anything, e.g. user said 'отмена'.
    Deliberately does NOT fall back to on_timeout's "just play the top
    result" behavior — an explicit cancel means "don't play anything",
    unlike a real timeout (silence), where auto-playing a reasonable
    default is the more useful behavior."""
    with _lock:
        cur = _current
    if cur is not None:
        cur['finish'](None, None, cancelled=True)


def open_yt_picker(hud, candidates: list[dict], on_select, on_timeout=None, on_cancel=None, timeout_sec: float = 20.0) -> None:
    """Must already be running on the Tk UI thread — schedule it via
    hud._hud_queue.put(...) when calling from a background/dispatch thread.

    on_select(candidate, idx): user picked one, by click or voice.
    on_timeout(): 20s passed with no response — caller's choice of default
      (e.g. "just play the top result", which is what core/handler/yt_play.py
      does — silence probably still means "yes, play something").
    on_cancel(): user explicitly said no (titlebar X, or 'отмена' via
      cancel_picker()) — nothing should play."""
    global _current
    if not candidates or not hud or not hud.root or not hud.root.winfo_exists():
        if on_timeout:
            on_timeout()
        return

    win = tk.Toplevel(hud.root)
    win.title('JARVIS — Выбор видео')
    win.configure(bg=_BG)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    _apply_window_icon(win, hud)
    win.attributes('-topmost', True)
    win.resizable(False, False)
    try:
        # Proper WM-level "stay above my owner" hint, set once — unlike a
        # previous version of this dialog which re-asserted -topmost every
        # 500ms as a defensive measure against the window vanishing. That
        # loop turned out to be fighting the real bug (a crash in _finish()
        # that left the window in limbo — fixed separately) rather than
        # z-ordering, and repeatedly forcing -topmost against the main HUD
        # overlay's own always-on-top window is a plausible cause of the
        # thumbnail images briefly flashing in and then disappearing.
        win.transient(hud.root)
    except Exception:
        pass

    _done = [False]
    photos: list = []  # keep PhotoImage references alive for the window's lifetime
    timer_id = [None]

    def _finish(choice, idx, cancelled=False):
        global _current
        if _done[0]:
            return
        _done[0] = True
        with _lock:
            _current = None
        if timer_id[0] is not None:
            try:
                win.after_cancel(timer_id[0])
            except Exception:
                pass
        try:
            win.destroy()
        except Exception:
            pass
        try:
            if choice is not None:
                on_select(choice, idx)
            elif cancelled:
                if on_cancel is not None:
                    on_cancel()
            elif on_timeout is not None:
                on_timeout()
        except Exception:
            pass

    with _lock:
        _current = {'candidates': candidates, 'finish': _finish}

    tk.Frame(win, bg=_CYAN, height=2).pack(fill='x')
    tk.Label(
        win, text='НЕСКОЛЬКО ПОХОЖИХ РЕЗУЛЬТАТОВ — ВЫБЕРИТЕ', bg=_BG, fg=_CYAN,
        font=('Consolas', JStyle.TEXT_BODY, 'bold'),
    ).pack(pady=(18, 6), padx=28)
    tk.Label(
        win, text='Кликните карточку или скажите «первое» / «второе» / ...',
        bg=_BG, fg=_DIM, font=('Consolas', JStyle.TEXT_TINY),
    ).pack(pady=(0, 18))

    cards_row = tk.Frame(win, bg=_BG)
    cards_row.pack(padx=28, pady=(0, 26))

    _CARD_W, _CARD_H = 188, 192
    _THUMB_W, _THUMB_H = 160, 96

    def _make_card(i: int, cand: dict):
        card = ctk.CTkFrame(
            cards_row, fg_color=_PANEL, border_color=_blend(_CYAN, 0.25),
            border_width=1, corner_radius=JStyle.RAD_PANEL, width=_CARD_W, height=_CARD_H,
        )
        card.grid(row=0, column=i, padx=10)
        card.grid_propagate(False)

        num_lbl = tk.Label(card, text=str(i + 1), bg=_PANEL, fg=_CYAN, font=('Consolas', JStyle.TEXT_BODY, 'bold'))
        num_lbl.pack(anchor='nw', padx=10, pady=(8, 2))

        # Fixed-size reserved box for the thumbnail, so the card doesn't
        # visibly reflow once the async download finishes and swaps the
        # placeholder text for a real image — same footprint either way.
        img_box = tk.Frame(card, bg=_PANEL, width=_THUMB_W, height=_THUMB_H)
        img_box.pack(pady=(0, 8))
        img_box.pack_propagate(False)
        img_lbl = tk.Label(img_box, bg=_PANEL, text='···', fg=_DIM, font=('Consolas', JStyle.TEXT_BODY))
        img_lbl.pack(fill='both', expand=True)

        title = cand.get('title') or ''
        short = title if len(title) <= 64 else title[:61] + '...'
        title_lbl = tk.Label(
            card, text=short, bg=_PANEL, fg=_TEXT, font=('Consolas', JStyle.TEXT_TINY),
            wraplength=_CARD_W - 20, justify='left',
        )
        title_lbl.pack(padx=10, pady=(0, 8), fill='x')

        widgets = (card, num_lbl, img_lbl, title_lbl)

        def _select(_e=None):
            _finish(cand, i)

        def _hover_in(_e=None):
            card.configure(border_color=_CYAN, fg_color=_blend(_CYAN, 0.08))

        def _hover_out(_e=None):
            card.configure(border_color=_blend(_CYAN, 0.25), fg_color=_PANEL)

        for w in widgets:
            w.configure(cursor='hand2') if hasattr(w, 'configure') else None
            w.bind('<Button-1>', _select)
            w.bind('<Enter>', _hover_in)
            w.bind('<Leave>', _hover_out)

        def _load_thumb():
            path = _download_thumb(cand.get('thumbnail'))
            if not path:
                return
            # PIL's Image.open()/thumbnail() are fine off-thread, but
            # ImageTk.PhotoImage() talks directly to the Tcl interpreter and
            # is NOT safe to call outside the thread running the Tk mainloop
            # — doing so here (instead of inside _apply, below) corrupted
            # rendering across *all* cards, not just this one, the first
            # time this dialog shipped. Only the network download runs off
            # the main thread; every Tk/PIL-Tk call happens inside _apply()
            # via win.after(), same pattern as ui/hud_ai_window.py's
            # set_image() (called through window.after(0, ...)).
            def _apply():
                if not win.winfo_exists():
                    return
                try:
                    img = Image.open(path)
                    img.thumbnail((_THUMB_W - 4, _THUMB_H - 4), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                except Exception as e:
                    print(f'[YT-PICKER] failed to render downloaded thumbnail {path}: {e}', flush=True)
                    _log.warning('failed to render downloaded thumbnail %s: %s', path, e)
                    return
                photos.append(photo)
                img_lbl.configure(image=photo, text='')
                # The canonical Tkinter idiom — tie the PhotoImage's lifetime
                # directly to the widget that displays it, not just to a
                # list in the enclosing closure. ui/hud_ai_window.py's own
                # (working) set_image() does exactly this; this dialog only
                # copied the list half of that pattern, which is apparently
                # not sufficient here — the image would render for an
                # instant, then Tk would silently fall back to blank once
                # the PhotoImage got garbage-collected.
                img_lbl.image = photo
                print(f'[YT-PICKER] card {i + 1}: thumbnail applied', flush=True)
            try:
                win.after(0, _apply)
            except Exception as e:
                print(f'[YT-PICKER] failed to schedule thumbnail apply on the UI thread: {e}', flush=True)

        threading.Thread(target=_load_thumb, daemon=True).start()

    for i, cand in enumerate(candidates):
        _make_card(i, cand)

    win.update_idletasks()
    _center_window(win, win.winfo_reqwidth(), win.winfo_reqheight())
    win.protocol('WM_DELETE_WINDOW', lambda: _finish(None, None, cancelled=True))
    timer_id[0] = win.after(int(timeout_sec * 1000), lambda: _finish(None, None, cancelled=False))
