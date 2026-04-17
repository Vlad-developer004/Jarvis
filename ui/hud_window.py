from __future__ import annotations
import os, sys
import threading
import tkinter as tk
from .hud_constants import _BG, _CYAN, _TEXT
def start_tray(hud) -> None:
    try:
        import pystray
        from PIL import Image
        if os.path.exists(hud._ico_path):
            img = Image.open(hud._ico_path)
        else:
            img = Image.new('RGB', (64, 64), (0, 255, 255))
        def _show_hud():
            hud._hud_queue.put(hud.root.deiconify)
            hud._hud_queue.put(hud.root.lift)
            hud._hud_queue.put(hud.root.focus_force)
        def _quit():
            hud._tray_icon.stop()
            hud.root.quit()
        def _restart():
            import subprocess
            exe = sys.executable
            try:
                if getattr(sys, 'frozen', False):
                    subprocess.Popen([exe], creationflags=0x00000008)
                else:
                    subprocess.Popen([exe] + sys.argv)
            except Exception:
                pass
            finally:
                import os as _os
                _os._exit(0)
        menu = pystray.Menu(
            pystray.MenuItem('Показать HUD', _show_hud, default=True),
            pystray.MenuItem('Настройки', hud._open_settings),
            pystray.MenuItem('Перезапустить', _restart),
            pystray.MenuItem('Выход', _quit)
        )
        hud._tray_icon = pystray.Icon('JarvisHUD', img, 'J.A.R.V.I.S.', menu)
        threading.Thread(target=hud._tray_icon.run, daemon=True).start()
    except Exception:
        pass
def hide_to_tray(hud) -> None:
    hud.root.withdraw()
def set_dark_title_bar(window: tk.Toplevel | tk.Tk) -> None:
    import ctypes
    window.update()
    hwnd_tk = window.winfo_id()
    hwnd = ctypes.windll.user32.GetAncestor(hwnd_tk, 2)
    if not hwnd: hwnd = hwnd_tk
    on = ctypes.c_int(1)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(on), 4)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(on), 4)
    caption_col = ctypes.c_int(0x00301C1A)
    text_col = ctypes.c_int(0x00FFFFFF)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(caption_col), 4)
    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 36, ctypes.byref(text_col), 4)
