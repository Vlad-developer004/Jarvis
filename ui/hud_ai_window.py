import os
import sys
import threading
import time
import urllib.request
import urllib.parse
import json
import hashlib
import tempfile
import ssl
import math
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
from core.system.version import APP_VERSION

def _theme():
    try:
        import ui.hud_constants as _c
        return _c
    except Exception:
        class _Fallback:
            _BG = '#0c1014'; _PANEL = '#111'; _CYAN = '#00f0ff'
            _TEXT = '#ffffff'; _DIM = '#8a9aae'; _MAG = '#ff007f'
            _BRD_I = '#1e2a30'
        return _Fallback()

def _BG_COLOR():   return _theme()._BG
def _PANEL_COLOR():return _theme()._PANEL
def _BORDER_COLOR():return _theme()._CYAN
def _TEXT_COLOR(): return _theme()._TEXT
def _DIM_COLOR():  return _theme()._DIM
def _ACCENT_COLOR():return _theme()._AMBER if hasattr(_theme(), '_AMBER') else _theme()._CYAN

_window_instance = None
_lock = threading.Lock()
_hide_cancel = threading.Event()  # set when a new window replaces the current one

def get_zoom_factor():
    try:
        from core.system import app_state
        hud = getattr(app_state, 'hud', None)
        if hud and hasattr(hud, 'zoom_factor'):
            return float(hud.zoom_factor)
    except Exception:
        pass
    # Fallback auto detect based on screen width
    try:
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        if sw >= 3800: return 2.0   # 4K
        if sw >= 2500: return 1.5   # 2K / QHD
        if sw >= 1900: return 1.2   # Full HD (slight boost)
        if sw >= 1600: return 1.1
    except Exception:
        pass
    return 1.0

class ArcReactorPlaceholder(tk.Canvas):
    """A beautiful, retro-futuristic holographic canvas drawing that serves as a fallback placeholder."""
    def __init__(self, parent, size=150, **kwargs):
        super().__init__(parent, width=size, height=size, bg=_BG_COLOR(), highlightthickness=0, **kwargs)
        self.size = size
        self.angle = 0
        self.draw_reactor()
        self.animate()

    def draw_reactor(self):
        self.delete("all")
        c = self.size / 2
        sf = self.size / 150.0
        
        # Outer ring
        self.create_oval(c - 60 * sf, c - 60 * sf, c + 60 * sf, c + 60 * sf, outline=_BORDER_COLOR(), width=max(1, int(1 * sf)))
        # Inner dashed ring
        self.create_oval(c - 45 * sf, c - 45 * sf, c + 45 * sf, c + 45 * sf, outline=_BORDER_COLOR(), width=max(1, int(1 * sf)), dash=(4, 4))
        # Central core
        self.create_oval(c - 15 * sf, c - 15 * sf, c + 15 * sf, c + 15 * sf, fill=_BG_COLOR(), outline=_BORDER_COLOR(), width=max(1, int(2 * sf)))
        self.create_oval(c - 8 * sf, c - 8 * sf, c + 8 * sf, c + 8 * sf, fill=_BORDER_COLOR(), outline=_BORDER_COLOR())

        # Rotating segment arcs
        for i in range(8):
            ang = self.angle + i * 45
            rad = math.radians(ang)
            x1 = c + 25 * sf * math.cos(rad)
            y1 = c + 25 * sf * math.sin(rad)
            x2 = c + 40 * sf * math.cos(rad)
            y2 = c + 40 * sf * math.sin(rad)
            self.create_line(x1, y1, x2, y2, fill=_BORDER_COLOR(), width=max(1, int(2 * sf)))
            
        # UI corner markings
        pad = 5 * sf
        line_len = 15 * sf
        self.create_line(pad, pad, pad + line_len, pad, fill=_BORDER_COLOR(), width=1)
        self.create_line(pad, pad, pad, pad + line_len, fill=_BORDER_COLOR(), width=1)
        self.create_line(self.size - pad, pad, self.size - pad - line_len, pad, fill=_BORDER_COLOR(), width=1)
        self.create_line(self.size - pad, pad, self.size - pad, pad + line_len, fill=_BORDER_COLOR(), width=1)

    def animate(self):
        if not self.winfo_exists():
            return
        self.angle = (self.angle + 3) % 360
        self.draw_reactor()
        self.after(50, self.animate)

class HUD_AI_Window(tk.Toplevel):
    def __init__(self, parent, subject="J.A.R.V.I.S."):
        super().__init__(parent)
        self.title("AI INFO")
        self.configure(bg=_BG_COLOR())
        
        # Get dynamic zoom scaling factor
        self.zoom = get_zoom_factor()
        
        # Borderless, topmost, transparent background
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.92)
        
        # Position at bottom-right above taskbar - scaled dimensions
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(550 * self.zoom)
        h = int(180 * self.zoom)
        x = sw - w - int(40 * self.zoom)
        y = sh - h - int(70 * self.zoom)
        self.geometry(f"{w}x{h}+{x}+{y}")

        # Double thin borders using frames
        self.main_frame = tk.Frame(self, bg=_BG_COLOR(), highlightbackground=_BORDER_COLOR(), highlightthickness=1)
        self.main_frame.pack(fill="both", expand=True)

        # Left panel: Image or Placeholder - scaled
        self.left_panel = tk.Frame(self.main_frame, bg=_BG_COLOR(), width=int(160 * self.zoom), height=int(180 * self.zoom))
        self.left_panel.pack(side="left", fill="y", padx=int(10 * self.zoom), pady=int(10 * self.zoom))
        self.left_panel.pack_propagate(False)

        self.placeholder = ArcReactorPlaceholder(self.left_panel, size=int(150 * self.zoom))
        self.placeholder.pack(fill="both", expand=True)
        self.img_label = None
        self._video_cap = None
        self._video_gen = 0

        # Right panel: Subject and streamed text
        self.right_panel = tk.Frame(self.main_frame, bg=_BG_COLOR())
        self.right_panel.pack(side="left", fill="both", expand=True, padx=(int(5 * self.zoom), int(15 * self.zoom)), pady=int(10 * self.zoom))

        # Subject title
        self.sub_lbl = tk.Label(
            self.right_panel,
            text=subject.upper(),
            bg=_BG_COLOR(),
            fg=_BORDER_COLOR(),
            font=("Consolas", int(14 * self.zoom), "bold"),
            anchor="w"
        )
        self.sub_lbl.pack(fill="x", pady=(int(2 * self.zoom), int(4 * self.zoom)))

        # Horizontal divider
        div = tk.Frame(self.right_panel, bg=_BORDER_COLOR(), height=max(1, int(1 * self.zoom)))
        div.pack(fill="x", pady=(0, int(6 * self.zoom)))

        # Streamed text box
        self.text_box = tk.Text(
            self.right_panel,
            bg=_BG_COLOR(),
            fg=_TEXT_COLOR(),
            font=("Consolas", int(10 * self.zoom)),
            bd=0,
            highlightthickness=0,
            wrap="word",
            padx=int(2 * self.zoom),
            pady=int(2 * self.zoom),
            height=4
        )
        self.text_box.pack(fill="both", expand=True)
        self.text_box.configure(state="disabled")

        # Bottom status indicator
        self.status_lbl = tk.Label(
            self.right_panel,
            text=f"SYSTEM STATUS: STREAMING  ·  API CORE v{APP_VERSION}",
            bg=_BG_COLOR(),
            fg=_DIM_COLOR(),
            font=("Consolas", int(7 * self.zoom)),
            anchor="e"
        )
        self.status_lbl.pack(fill="x", pady=(int(2 * self.zoom), 0))

        # Close button in the top-right corner - scaled
        self.close_btn = tk.Button(
            self,
            text="×",
            bg=_BG_COLOR(),
            fg=_BORDER_COLOR(),
            activebackground=_BG_COLOR(),
            activeforeground=_ACCENT_COLOR(),
            bd=0,
            font=("Consolas", int(14 * self.zoom), "bold"),
            command=self.close_window,
            cursor="hand2"
        )
        btn_size = int(20 * self.zoom)
        self.close_btn.place(relx=1.0, rely=0.0, x=-int(25 * self.zoom), y=int(5 * self.zoom), width=btn_size, height=btn_size)
        self.close_btn.bind("<Enter>", lambda e: self.close_btn.configure(fg=_ACCENT_COLOR()))
        self.close_btn.bind("<Leave>", lambda e: self.close_btn.configure(fg=_BORDER_COLOR()))

        # Corner brackets decoration directly on main frame
        self.bind("<Map>", lambda e: self.draw_decorations())

    def draw_decorations(self):
        pass

    def close_window(self):
        global _window_instance
        self._stop_video()
        with _lock:
            if _window_instance == self:
                _window_instance = None
            try:
                self.destroy()
            except:
                pass

    def adjust_height(self):
        if not self.winfo_exists():
            return
        # Force a layout pass so that the text box calculates wrapping and geometry accurately
        self.update_idletasks()
        try:
            # Get actual display line count from text widget
            lines_tuple = self.text_box.count("1.0", "end-1c", "displaylines")
            num_lines = lines_tuple[0] if lines_tuple else 1
        except Exception:
            text_content = self.text_box.get("1.0", "end-1c")
            num_lines = max(1, text_content.count('\n') + 1)
            
        display_lines = max(4, min(20, num_lines))
        self.text_box.configure(height=display_lines)
        
        self.update_idletasks()
        req_h = self.winfo_reqheight()
        
        # Keep a minimum height so reactor placeholder / image doesn't get clipped
        min_h = int(180 * self.zoom)
        h = max(min_h, req_h)
        
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = int(550 * self.zoom)
        x = sw - w - int(40 * self.zoom)
        y = sh - h - int(70 * self.zoom)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def update_text(self, text):
        if not self.winfo_exists():
            return
        self.text_box.configure(state="normal")
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert(tk.END, text)
        self.text_box.configure(state="disabled")
        self.text_box.see("1.0")
        self.adjust_height()

    def _stop_video(self):
        """Invalidate any in-flight _next_video_frame() after()-loop and
        release the decoder. Safe to call even if no video is playing."""
        self._video_gen += 1
        if self._video_cap is not None:
            try:
                self._video_cap.release()
            except Exception:
                pass
            self._video_cap = None

    def set_video(self, video_path):
        """Play a local video file silently (no audio) on a loop, reusing
        the same thumbnail box as set_image(). Silent because piping the
        clip's audio through this app's TTS/pygame.mixer pipeline would mean
        touching core/speech/tts.py's playback locking — CLAUDE.md flags
        that whole area as crash-sensitive, disproportionate for a rare
        NASA "video of the day" — the still-frame loop already conveys it."""
        if not self.winfo_exists() or not video_path or not os.path.exists(video_path):
            return
        self._stop_video()
        try:
            import cv2
        except Exception as e:
            print(f"[AI-WINDOW] cv2 unavailable, cannot preview video: {e}", flush=True)
            return
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        interval_ms = max(33, int(1000 / fps))  # cap at ~30fps, this is a thumbnail-sized preview
        self._video_cap = cap
        gen = self._video_gen
        box_size = int(150 * self.zoom)

        if self.placeholder:
            self.placeholder.pack_forget()
            self.placeholder.destroy()
            self.placeholder = None
        if self.img_label is None:
            self.img_label = tk.Label(self.left_panel, bg=_BG_COLOR())
            self.img_label.pack(fill="both", expand=True)
        self.status_lbl.configure(text=f"SYSTEM STATUS: VIDEO PREVIEW (MUTED)  ·  API CORE v{APP_VERSION}")

        def _next_frame():
            if gen != self._video_gen or not self.winfo_exists():
                return  # superseded by a newer set_image/set_video/reset, or window closed
            ok, frame = cap.read()
            if not ok:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # loop back to the start
                self.after(interval_ms, _next_frame)
                return
            try:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                img.thumbnail((box_size, box_size), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.img_label.configure(image=photo)
                self.img_label.image = photo  # keep reference
            except Exception as e:
                print(f"[AI-WINDOW] Video frame error: {e}", flush=True)
            self.after(interval_ms, _next_frame)

        self.adjust_height()
        _next_frame()

    def set_image(self, img_path):
        if not self.winfo_exists() or not img_path or not os.path.exists(img_path):
            return
        self._stop_video()
        try:
            # Load and resize image keeping aspect ratio
            img = Image.open(img_path)
            box_size = int(150 * self.zoom)
            img.thumbnail((box_size, box_size), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Hide placeholder
            if self.placeholder:
                self.placeholder.pack_forget()
                self.placeholder.destroy()
                self.placeholder = None
                
            # Create or update label
            if self.img_label is None:
                self.img_label = tk.Label(self.left_panel, image=photo, bg=_BG_COLOR())
                self.img_label.image = photo  # keep reference
                self.img_label.pack(fill="both", expand=True)
            else:
                self.img_label.configure(image=photo)
                self.img_label.image = photo
                
            self.status_lbl.configure(text=f"SYSTEM STATUS: ACTIVE  ·  API CORE v{APP_VERSION}")
            self.adjust_height()
        except Exception as e:
            print(f"[AI-WINDOW] Error setting image: {e}", flush=True)

    def reset_image(self):
        if not self.winfo_exists():
            return
        self._stop_video()
        # Hide/destroy old image label if it exists
        if self.img_label is not None:
            try:
                self.img_label.pack_forget()
                self.img_label.destroy()
            except Exception:
                pass
            self.img_label = None
        # Recreate placeholder if it doesn't exist
        if self.placeholder is None:
            try:
                self.placeholder = ArcReactorPlaceholder(self.left_panel, size=int(150 * self.zoom))
                self.placeholder.pack(fill="both", expand=True)
            except Exception as e:
                print(f"[AI-WINDOW] Error resetting placeholder: {e}", flush=True)
        self.status_lbl.configure(text=f"SYSTEM STATUS: STREAMING  ·  API CORE v{APP_VERSION}")

def _async_wiki_search(window, subject):
    """Runs in background to fetch wikipedia thumbnail image."""
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'

    url = f"https://{lang}.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(subject)}&gsrlimit=3&prop=pageimages&piprop=thumbnail&pithumbsize=400&format=json"
    
    img_url = None
    try:
        context = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
        with urllib.request.urlopen(req, timeout=4, context=context) as response:
            data = json.loads(response.read().decode('utf-8'))
            pages = data.get('query', {}).get('pages', {})
            sorted_pages = sorted(pages.values(), key=lambda p: p.get('index', 99))
            
            if sorted_pages:
                top_page = sorted_pages[0]
                # If top page has a thumbnail, use it
                if 'thumbnail' in top_page and top_page['thumbnail'].get('source'):
                    img_url = top_page['thumbnail']['source']
                else:
                    # Try fallback to parsing images of the top page
                    top_page_title = top_page['title']
                    parse_url = f"https://{lang}.wikipedia.org/w/api.php?action=parse&page={urllib.parse.quote(top_page_title)}&prop=images&format=json"
                    req2 = urllib.request.Request(parse_url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
                    with urllib.request.urlopen(req2, timeout=4, context=context) as res2:
                        pdata = json.loads(res2.read().decode('utf-8'))
                        images = pdata.get('parse', {}).get('images', [])
                        
                        exclusions = ['logo', 'icon', 'stub', 'flag', 'map', 'commons', 'star', 'approved', 'important', 'gear', 'wikisource', 'wikimedia', 'shield', 'portal', 'ambox', 'edit-clear']
                        candidates = []
                        for img in images:
                            img_low = img.lower()
                            if any(x in img_low for x in exclusions):
                                continue
                            if img_low.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                candidates.append(img)
                                
                        if candidates:
                            first_img = candidates[0]
                            info_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&titles=File:{urllib.parse.quote(first_img)}&prop=imageinfo&iiprop=url&format=json"
                            req3 = urllib.request.Request(info_url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
                            with urllib.request.urlopen(req3, timeout=4, context=context) as res3:
                                idata = json.loads(res3.read().decode('utf-8'))
                                ipages = idata.get('query', {}).get('pages', {})
                                for ip_data in ipages.values():
                                    info = ip_data.get('imageinfo', [])
                                    if info and info[0].get('url'):
                                        img_url = info[0]['url']
                                        break
                                        
                # If top page resolution failed, check if subsequent pages have thumbnails
                if not img_url:
                    for p in sorted_pages[1:]:
                        if 'thumbnail' in p and p['thumbnail'].get('source'):
                            img_url = p['thumbnail']['source']
                            break
    except Exception as e:
        print(f"[AI-WIKI] Search failed: {e}", flush=True)

    if not img_url:
        return # Fallback reactor drawing remains visible

    # Download image
    try:
        cache_dir = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')
        os.makedirs(cache_dir, exist_ok=True)
        h = hashlib.md5(img_url.encode('utf-8')).hexdigest()
        ext = '.jpg'
        if '.png' in img_url.lower(): ext = '.png'
        path = os.path.join(cache_dir, f'img_{h}{ext}')
        
        if not os.path.exists(path):
            context = ssl._create_unverified_context()
            req = urllib.request.Request(img_url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
            with urllib.request.urlopen(req, timeout=6, context=context) as response:
                with open(path, 'wb') as f:
                    f.write(response.read())
                    
        # Update UI on main thread safely
        if window and window.winfo_exists():
            window.after(0, lambda: window.set_image(path))
    except Exception as e:
        print(f"[AI-WIKI] Download failed: {e}", flush=True)

def cancel_hide_ai_window():
    """Cancel any pending window closure immediately (e.g., when a new query starts)."""
    global _hide_cancel
    _hide_cancel.set()
    _hide_cancel = threading.Event()

def show_ai_window(subject, fetch_image=True):
    """Safely show the AI response mini window from any thread.

    fetch_image=False skips the Wikipedia thumbnail lookup — used for the
    placeholder call before the model's [Subject: ...] tag is parsed, so we
    don't fire a Wikipedia search for the raw question text just to throw it
    away a moment later when the real subject arrives."""
    global _window_instance, _hide_cancel

    # Check settings first
    try:
        from config_pack.config import get_settings_path
        p = get_settings_path()
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                d = json.load(f)
                if not d.get('ai_mini_window', True):
                    return
    except Exception:
        pass

    from core.system import app_state
    hud = getattr(app_state, 'hud', None)
    if not hud or not hud.root:
        return

    # Reset the hide-timer immediately so the window stays open for the new answer
    _hide_cancel.set()
    _hide_cancel = threading.Event()

    def _ui_action():
        global _window_instance
        with _lock:
            if _window_instance and _window_instance.winfo_exists():
                # Reuse existing window — just update the subject label
                try:
                    _window_instance.sub_lbl.configure(text=subject.upper())
                    if fetch_image:
                        _window_instance.reset_image()
                        threading.Thread(target=_async_wiki_search, args=(_window_instance, subject), daemon=True).start()
                except Exception as e:
                    print(f"[AI-WINDOW] Error reusing window: {e}", flush=True)
            else:
                _window_instance = HUD_AI_Window(hud.root, subject)
                if fetch_image:
                    threading.Thread(target=_async_wiki_search, args=(_window_instance, subject), daemon=True).start()

    hud.root.after(0, _ui_action)

def update_ai_window_text(text):
    """Safely update text in the AI response mini window."""
    global _window_instance
    if _window_instance and _window_instance.winfo_exists():
        _window_instance.after(0, lambda: _window_instance.update_text(text))

def set_ai_window_image(img_path):
    """Safely set the AI window's thumbnail to an already-downloaded local
    file — for callers (e.g. NASA APOD) that already have their own image
    URL and don't need the Wikipedia thumbnail search in _async_wiki_search."""
    global _window_instance
    if _window_instance and _window_instance.winfo_exists():
        _window_instance.after(0, lambda: _window_instance.set_image(img_path))

def set_ai_window_video(video_path):
    """Safely play a local video file (silent, looping) in the AI window's
    thumbnail box — see HUD_AI_Window.set_video() for why it's muted."""
    global _window_instance
    if _window_instance and _window_instance.winfo_exists():
        _window_instance.after(0, lambda: _window_instance.set_video(video_path))

def hide_ai_window(delay_ms=5000):
    """Wait for TTS to finish, then close the window after delay_ms ms of reading time.
    Cancelled immediately if show_ai_window() is called again (new question)."""
    global _window_instance, _hide_cancel
    win = _window_instance
    if not win:
        return
    cancel = _hide_cancel  # capture: this event is set when a new window opens

    def _wait_and_close():
        # Give TTS a moment to start
        time.sleep(1.0)
        if cancel.is_set():
            return

        # Wait until TTS playback finishes (or window/cancel)
        try:
            from core.speech.tts import TTSManager
            mgr = TTSManager()
            while (mgr.active_playback or not mgr.queue.empty()):
                if cancel.is_set():
                    return
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return
                time.sleep(0.3)
        except Exception:
            pass

        # Reading buffer: honour delay_ms, abort on cancel
        deadline = time.time() + delay_ms / 1000.0
        while time.time() < deadline:
            if cancel.is_set():
                return
            time.sleep(0.1)

        if cancel.is_set():
            return

        def _close():
            global _window_instance
            with _lock:
                if _window_instance is win:
                    try:
                        if win.winfo_exists():
                            win.destroy()
                    except Exception:
                        pass
                    _window_instance = None

        try:
            if win.winfo_exists() and not cancel.is_set():
                win.after(0, _close)
        except Exception:
            pass

    threading.Thread(target=_wait_and_close, daemon=True).start()
