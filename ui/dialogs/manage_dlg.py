from __future__ import annotations
import os
import threading
import tkinter as tk
import customtkinter as ctk
from ..hud_constants import _BG, _PANEL, _CYAN, _GREEN, _AMBER, _RED, _WHITE, _TEXT, _DIM
from ..hud_utils import _blend, _set_dark_title_bar, _apply_window_icon
from ..hud_widgets import _HudScrollbar, make_dlg_btn
def _base_win(hud, title: str, w: int = 620, h: int = 560) -> tk.Toplevel:
    win = tk.Toplevel(hud.root)
    _set_dark_title_bar(win)
    win.after(150, lambda: _set_dark_title_bar(win))
    win.title(title)
    win.configure(bg=_BG)
    _apply_window_icon(win, hud)
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry("")
    win.minsize(400, 300)
    win.resizable(True, True)
    
    def _recenter():
        win.update_idletasks()
        rw, rh = win.winfo_reqwidth(), win.winfo_reqheight()
        win.geometry(f"{rw}x{rh}+{(sw-rw)//2}+{(sh-rh)//2}")
    win._recenter = _recenter
    
    return win
def _add_context_menu(win, entry, _hud, accent):
    menu = tk.Menu(win, tearoff=0, bg=_PANEL, fg=_WHITE, activebackground=accent, activeforeground=_BG, font=(_hud._F, _hud._fs(12)))
    def _paste():
        try:
            import pyperclip
            txt = pyperclip.paste()
            if txt:
                if entry.selection_present():
                    entry.delete('sel.first', 'sel.last')
                entry.insert(tk.INSERT, txt)
        except Exception: pass
    def _copy():
        try:
            if entry.selection_present():
                win.clipboard_clear()
                win.clipboard_append(entry.selection_get())
        except Exception: pass
    def _select_all():
        entry.select_range(0, 'end')
        entry.icursor('end')
    menu.add_command(label='Вставить (Ctrl+V)', command=_paste)
    menu.add_command(label='Копировать (Ctrl+C)', command=_copy)
    menu.add_separator()
    menu.add_command(label='Выделить всё (Ctrl+A)', command=_select_all)
    entry.bind('<Button-3>', lambda e: menu.tk_popup(e.x_root, e.y_root))
    entry.bind('<Control-v>', lambda e: (_paste(), 'break'))
    entry.bind('<Control-V>', lambda e: (_paste(), 'break'))
    entry.bind('<Control-a>', lambda e: (_select_all(), 'break'))
    entry.bind('<Control-A>', lambda e: (_select_all(), 'break'))
def _scrollable(win, _hud, accent):
    tk.Frame(win, bg=accent, height=3).pack(fill='x')
    canvas = tk.Canvas(win, bg=_BG, highlightthickness=0)
    vsb = _HudScrollbar(win, canvas, color=accent)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side='left', fill='both', expand=True)
    inner = tk.Frame(canvas, bg=_BG)
    cw = canvas.create_window((0, 0), window=inner, anchor='nw')
    inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda e: canvas.itemconfig(cw, width=e.width))
    win.bind('<MouseWheel>', lambda e: canvas.yview_scroll(-1*(e.delta//120), 'units'))
    return inner
def _fmt_date(ts: str) -> str:
    _MON = {1:'янв',2:'фев',3:'мар',4:'апр',5:'май',6:'июн',
            7:'июл',8:'авг',9:'сен',10:'окт',11:'ноя',12:'дек'}
    try:
        from datetime import datetime
        dt = datetime.strptime(ts.strip(), '%Y-%m-%d %H:%M:%S')
        return f'{dt.day} {_MON[dt.month]} {dt.year}  {dt.strftime("%H:%M")}'
    except Exception:
        return ts
def _meeting_icon(url: str) -> str:
    u = url.lower()
    if 'zoom.us' in u:           return '📹'
    if 'teams.microsoft' in u:   return '💼'
    if 'meet.google' in u:       return '🎦'
    if 'discord' in u:           return '🎮'
    if 'telegram' in u or 't.me' in u: return '✈'
    if 'youtube' in u or 'youtu.be' in u: return '▶'
    if 'moodle' in u:            return '📚'
    return '🔗'
def open_meetings_manager(hud) -> None:
    win = _base_win(hud, 'БЫСТРЫЕ ССЫЛКИ — управление', w=620, h=540)
    inner = _scrollable(win, hud, _GREEN)
    _sf = lambda n: hud._fs(n + 6)
    from actions.meetings import get_meetings, save_meetings
    meetings: list[dict] = list(get_meetings())
    _editing: list[int | None] = [None]
    hdr = tk.Frame(inner, bg=_BG)
    hdr.pack(fill='x', padx=20, pady=(16, 4))
    tk.Label(hdr, text='🔗  БЫСТРЫЕ ССЫЛКИ', bg=_BG, fg=_GREEN,
             font=(hud._F, _sf(13), 'bold')).pack(side='left')
    count_lbl = tk.Label(hdr, text='', bg=_BG, fg=_DIM, font=(hud._F, _sf(9)))
    count_lbl.pack(side='right')
    status_lbl = tk.Label(inner, text='', bg=_BG, fg=_DIM, font=(hud._F, _sf(8)))
    status_lbl.pack(anchor='w', padx=20, pady=(0, 6))
    cards_frame = tk.Frame(inner, bg=_BG)
    cards_frame.pack(fill='x', padx=20, pady=(0, 16))
    def _rebuild():
        for w in cards_frame.winfo_children():
            w.destroy()
        count_lbl.configure(text=f'{len(meetings)} записей')
        if not meetings:
            tk.Label(cards_frame, text='Нет сохранённых ссылок', bg=_BG, fg=_DIM,
                     font=(hud._F, _sf(10))).pack(pady=20)
            return
        for i, m in enumerate(meetings):
            card = tk.Frame(cards_frame, bg=_PANEL,
                            highlightbackground=_blend(_GREEN, 0.18), highlightthickness=1)
            card.pack(fill='x', pady=4)
            tk.Frame(card, bg=_GREEN, width=3).pack(side='left', fill='y')
            if _editing[0] == i:
                body = tk.Frame(card, bg=_PANEL)
                body.pack(side='left', fill='both', expand=True, padx=12, pady=10)
                _ekw = dict(font=(hud._F, _sf(9)), fg_color=_BG, text_color=_WHITE,
                            border_color=_blend(_GREEN, 0.25), border_width=2,
                            corner_radius=8, height=36,
                            placeholder_text_color=_blend(_WHITE, 0.3))
                _lkw = dict(bg=_PANEL, fg=_DIM, font=(hud._F, _sf(8)), anchor='w')
                tk.Label(body, text='Голосовая фраза', **_lkw).pack(fill='x')
                e_phrase = ctk.CTkEntry(body, placeholder_text='например: заходим на пару', **_ekw)
                e_phrase.insert(0, m.get('phrase', ''))
                e_phrase.pack(fill='x', pady=(2, 8))
                tk.Label(body, text='Ссылка', **_lkw).pack(fill='x')
                e_url = ctk.CTkEntry(body, placeholder_text='https://...', **_ekw)
                e_url.insert(0, m.get('url', ''))
                e_url.pack(fill='x', pady=(2, 8))
                tk.Label(body, text='Название (необязательно)', **_lkw).pack(fill='x')
                e_name = ctk.CTkEntry(body, placeholder_text='например: Высшая математика', **_ekw)
                e_name.insert(0, m.get('name', ''))
                e_name.pack(fill='x', pady=(2, 0))
                _add_context_menu(win, e_phrase, hud, _GREEN)
                _add_context_menu(win, e_url, hud, _GREEN)
                _add_context_menu(win, e_name, hud, _GREEN)
                br = tk.Frame(body, bg=_PANEL)
                br.pack(anchor='w', pady=(10, 0))
                def _save(idx=i, ep=e_phrase, eu=e_url, en=e_name):
                    phrase = ep.get().strip().lower()
                    url = eu.get().strip()
                    name = en.get().strip() or phrase
                    if not phrase or not url:
                        status_lbl.configure(text='Фраза и ссылка обязательны.', fg=_AMBER)
                        return
                    meetings[idx] = {'name': name, 'phrase': phrase, 'url': url}
                    save_meetings(meetings)
                    _editing[0] = None
                    status_lbl.configure(text='Сохранено  ✓', fg=_GREEN)
                    _rebuild()
                def _cancel():
                    _editing[0] = None
                    _rebuild()
                make_dlg_btn(hud, br, 'СОХРАНИТЬ', '✓', _GREEN, _save, height=36, width=118).pack(side='left', padx=(0, 6))
                make_dlg_btn(hud, br, 'ОТМЕНА', '✕', _DIM, _cancel, height=36, width=88).pack(side='left')
            else:
                btn_col = tk.Frame(card, bg=_PANEL)
                btn_col.pack(side='right', padx=14, pady=14)
                def _edit(idx=i):
                    _editing[0] = idx
                    _rebuild()
                def _delete(idx=i):
                    meetings.pop(idx)
                    save_meetings(meetings)
                    _editing[0] = None
                    status_lbl.configure(text='Удалено.', fg=_AMBER)
                    _rebuild()
                make_dlg_btn(hud, btn_col, 'ИЗМЕНИТЬ', '◈', _CYAN, _edit, height=44, width=136).pack(fill='x', pady=(0, 6))
                make_dlg_btn(hud, btn_col, 'УДАЛИТЬ', '✕', _RED, _delete, height=44, width=136).pack(fill='x')
                body = tk.Frame(card, bg=_PANEL)
                body.pack(side='left', fill='both', expand=True, padx=14, pady=14)
                name_row = tk.Frame(body, bg=_PANEL)
                name_row.pack(fill='x')
                raw_url = m.get('url', '')
                svc_icon = _meeting_icon(raw_url)
                if svc_icon:
                    tk.Label(name_row, text=svc_icon, bg=_PANEL, fg=_GREEN,
                             font=(hud._F, _sf(10))).pack(side='left', padx=(0, 4))
                tk.Label(name_row, text=m.get('name', m.get('phrase', '')), bg=_PANEL, fg=_GREEN,
                         font=(hud._F, _sf(10), 'bold'), anchor='w').pack(side='left', fill='x', expand=True)
                tk.Label(body, text=f'«{m.get("phrase", "")}»', bg=_PANEL, fg=_TEXT,
                         font=(hud._F, _sf(9)), anchor='w').pack(fill='x')
                url_lbl = tk.Label(body, text=raw_url, bg=_PANEL,
                                   fg=_blend(_GREEN, 0.45),
                                   font=(hud._F, _sf(7)), anchor='w',
                                   justify='left', wraplength=1, cursor='hand2')
                url_lbl.pack(fill='x', pady=(2, 0))
                url_lbl.bind('<Button-1>', lambda e, u=raw_url: __import__('webbrowser').open(u))
                def _upd_url_wrap(e, l=url_lbl):
                    l.configure(wraplength=max(60, e.width - 4))
                body.bind('<Configure>', _upd_url_wrap, add='+')
    _rebuild()
    win.lift()
    win.focus_force()
    if hasattr(win, '_recenter'): win._recenter()
def _parse_saved_videos() -> list[dict]:
    save_path = os.path.join(os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')
    if not os.path.exists(save_path):
        return []
    result = []
    with open(save_path, 'r', encoding='utf-8') as f:
        for line in f.read().splitlines():
            line = line.strip()
            if not line or ' - ' not in line:
                continue
            ts, url = line.split(' - ', 1)
            result.append({'ts': ts.strip(), 'url': url.strip()})
    return result
def _save_videos(videos: list[dict]) -> None:
    save_path = os.path.join(os.path.expanduser('~'), 'Jarvis_YT_Saved.txt')
    with open(save_path, 'w', encoding='utf-8') as f:
        for v in videos:
            f.write(f'{v["ts"]} - {v["url"]}\n')
def _yt_id(url: str) -> str | None:
    import re
    m = re.search(r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None
def _fetch_yt_meta(video_id: str) -> dict:
    result = {'title': '', 'author': '', 'thumb': '', 'duration': ''}
    try:
        import urllib.request, json as _json
        url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = _json.loads(r.read())
        result['title'] = data.get('title', '')
        result['author'] = data.get('author_name', '')
        result['thumb'] = f'https://i.ytimg.com/vi/{video_id}/mqdefault.jpg'
    except Exception:
        pass
    try:
        import urllib.request, re as _re
        req2 = urllib.request.Request(
            f'https://www.youtube.com/watch?v={video_id}',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'en'})
        buf = b''
        with urllib.request.urlopen(req2, timeout=8) as r2:
            while True:
                chunk = r2.read(32_768)
                if not chunk:
                    break
                buf += chunk
                text_chunk = buf.decode('utf-8', errors='ignore')
                m = _re.search(r'"lengthSeconds"\s*:\s*"(\d+)"', text_chunk)
                if m:
                    dur = int(m.group(1))
                    h, rem = divmod(dur, 3600)
                    m2, s = divmod(rem, 60)
                    result['duration'] = f'{h}:{m2:02d}:{s:02d}' if h else f'{m2}:{s:02d}'
                    break
                if len(buf) > 800_000:
                    break
    except Exception:
        pass
    return result
def _open_url(url: str) -> None:
    from actions.youtube import _open_youtube_url
    _open_youtube_url(url)
def _load_thumb(url: str):
    try:
        import urllib.request, io
        from PIL import Image, ImageTk
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert('RGB').resize((112, 63), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None
def open_videos_manager(hud) -> None:
    win = _base_win(hud, 'СОХРАНЁННЫЕ ВИДЕО — управление', w=680, h=580)
    inner = _scrollable(win, hud, _CYAN)
    _sf = lambda n: hud._fs(n + 6)
    videos: list[dict] = list(reversed(_parse_saved_videos()))
    hdr = tk.Frame(inner, bg=_BG)
    hdr.pack(fill='x', padx=20, pady=(16, 4))
    tk.Label(hdr, text='▶  СОХРАНЁННЫЕ ВИДЕО', bg=_BG, fg=_CYAN,
             font=(hud._F, _sf(13), 'bold')).pack(side='left')
    count_lbl = tk.Label(hdr, text='', bg=_BG, fg=_DIM, font=(hud._F, _sf(9)))
    count_lbl.pack(side='right')
    status_lbl = tk.Label(inner, text='', bg=_BG, fg=_DIM, font=(hud._F, _sf(8)))
    status_lbl.pack(anchor='w', padx=20, pady=(0, 6))
    cards_frame = tk.Frame(inner, bg=_BG)
    cards_frame.pack(fill='x', padx=20, pady=(0, 16))
    _meta_cache: dict[str, dict] = {}
    _thumb_refs: dict[str, object] = {}
    def _rebuild():
        for w in cards_frame.winfo_children():
            w.destroy()
        count_lbl.configure(text=f'{len(videos)} видео')
        if not videos:
            tk.Label(cards_frame, text='Нет сохранённых видео', bg=_BG, fg=_DIM,
                     font=(hud._F, _sf(10))).pack(pady=20)
            return
        for i, v in enumerate(videos):
            vid_id = _yt_id(v['url'])
            meta = _meta_cache.get(vid_id or '', {})
            title = meta.get('title', '') or '...'
            author = meta.get('author', '')
            duration = meta.get('duration', '')
            card = tk.Frame(cards_frame, bg=_PANEL,
                            highlightbackground=_blend(_CYAN, 0.18), highlightthickness=1)
            card.pack(fill='x', pady=4)
            tk.Frame(card, bg=_CYAN, width=3).pack(side='left', fill='y')
            btn_col = tk.Frame(card, bg=_PANEL)
            btn_col.pack(side='right', padx=14, pady=14)
            def _open(url=v['url']):
                _open_url(url)
            def _del(idx=i):
                videos.pop(idx)
                _save_videos(list(reversed(videos)))
                status_lbl.configure(text='Удалено.', fg=_AMBER)
                _rebuild()
            make_dlg_btn(hud, btn_col, 'ОТКРЫТЬ', '▶', _CYAN, _open, height=44, width=128).pack(fill='x', pady=(0, 6))
            make_dlg_btn(hud, btn_col, 'УДАЛИТЬ', '🗑', _RED, _del, height=44, width=128).pack(fill='x')
            thumb_w = hud._px(112)
            thumb_h = hud._px(63)
            thumb_frame = tk.Frame(card, bg=_BG, width=thumb_w, height=thumb_h)
            thumb_frame.pack(side='left', padx=(10, 0), pady=14)
            thumb_frame.pack_propagate(False)
            thumb_lbl = tk.Label(thumb_frame, bg=_BG, text='▶',
                                 fg=_blend(_CYAN, 0.4), font=(hud._F, _sf(20)))
            thumb_lbl.place(relx=0.5, rely=0.5, anchor='center')
            if vid_id and vid_id in _thumb_refs:
                img = _thumb_refs[vid_id]
                thumb_lbl.configure(image=img, text='')
                thumb_lbl.image = img
            if duration:
                dur_lbl = tk.Label(thumb_frame, text=duration, bg='#000000',
                                   fg='white', font=(hud._F, hud._fs(8), 'bold'))
                dur_lbl.place(relx=1.0, rely=1.0, anchor='se', x=-3, y=-3)
            body = tk.Frame(card, bg=_PANEL)
            body.pack(side='left', fill='both', expand=True, padx=12, pady=14)
            title_lbl = tk.Label(body, text=title, bg=_PANEL, fg=_WHITE,
                                 font=(hud._F, _sf(9), 'bold'), anchor='w',
                                 justify='left', wraplength=300)
            title_lbl.pack(fill='x')
            def _upd_wrap(e, l=title_lbl):
                l.configure(wraplength=max(60, e.width - 4))
            body.bind('<Configure>', _upd_wrap, add='+')
            if author:
                tk.Label(body, text=author, bg=_PANEL, fg=_DIM,
                         font=(hud._F, _sf(8)), anchor='w').pack(fill='x')
            date_str = _fmt_date(v['ts'])
            tk.Label(body, text=date_str, bg=_PANEL, fg=_blend(_CYAN, 0.45),
                     font=(hud._F, _sf(7)), anchor='w').pack(fill='x', pady=(2, 0))
    _rebuild()
    def _load_meta():
        for v in videos:
            vid_id = _yt_id(v['url'])
            if not vid_id or vid_id in _meta_cache:
                continue
            meta = _fetch_yt_meta(vid_id)
            _meta_cache[vid_id] = meta
            if meta.get('thumb'):
                img = _load_thumb(meta['thumb'])
                if img:
                    _thumb_refs[vid_id] = img
            try:
                win.after(0, _rebuild)
            except Exception:
                break
    threading.Thread(target=_load_meta, daemon=True).start()
    win.lift()
    win.focus_force()
    if hasattr(win, '_recenter'): win._recenter()
