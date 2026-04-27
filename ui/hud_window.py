from __future__ import annotations
import os, sys
import threading
import tkinter as tk
from .hud_constants import _BG, _CYAN, _TEXT
import win32gui, win32api, win32con

class Win32Tray:
    def __init__(self, hud):
        self.hud = hud
        self.hwnd = None
        self.notify_id = None
        self._create_window()

    def _create_window(self):
        hinst = win32api.GetModuleHandle(None)
        
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == win32con.WM_COMMAND:
                self._on_command(hwnd, msg, wparam, lparam)
            elif msg == win32con.WM_DESTROY:
                self._on_destroy(hwnd, msg, wparam, lparam)
            elif msg == 0x20:
                self._on_tray_notify(hwnd, msg, wparam, lparam)
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = "JarvisTrayWindowV2"
        wc.lpfnWndProc = wnd_proc
        
        try:
            class_atom = win32gui.RegisterClass(wc)
        except:
            class_atom = "JarvisTrayWindowV2" # Already registered

        self.hwnd = win32gui.CreateWindow(
            class_atom, "JarvisTray", win32con.WS_OVERLAPPED,
            0, 0, 0, 0, 0, 0, hinst, None
        )
        win32gui.UpdateWindow(self.hwnd)
        
        # Icon
        icon_flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        
        if os.path.exists(self.hud._ico_path):
            try:
                hicon = win32gui.LoadImage(
                    hinst, self.hud._ico_path, win32con.IMAGE_ICON,
                    0, 0, win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
                )
            except: pass
        
        self.notify_id = (self.hwnd, 0, icon_flags, 0x20, hicon, "J.A.R.V.I.S.")
        win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self.notify_id)

    def _on_tray_notify(self, hwnd, msg, wparam, lparam):
        if lparam == win32con.WM_RBUTTONUP:
            self._show_menu()
        elif lparam == win32con.WM_LBUTTONDBLCLK:
            self.hud._hud_queue.put(lambda: show_main_win(self.hud))
        return True

    def _show_menu(self):
        menu = win32gui.CreatePopupMenu()
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1024, "Показать HUD")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1025, "Настройки")
        win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1026, "Перезапустить")
        win32gui.AppendMenu(menu, win32con.MF_STRING, 1027, "Выход")
        
        pos = win32api.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu, win32con.TPM_LEFTALIGN, pos[0], pos[1], 0, self.hwnd, None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def _on_command(self, hwnd, msg, wparam, lparam):
        id = win32api.LOWORD(wparam)
        if id == 1024: # Show
            self.hud._hud_queue.put(lambda: show_main_win(self.hud))
        elif id == 1025: # Settings
            self.hud._hud_queue.put(self.hud._open_settings)
        elif id == 1026: # Restart
            self._restart()
        elif id == 1027: # Exit
            win32gui.DestroyWindow(self.hwnd)
            self.hud.root.quit()

    def _restart(self):
        import subprocess
        exe = sys.executable
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([exe], creationflags=0x00000008)
            else:
                subprocess.Popen([exe] + sys.argv)
        except: pass
        finally: os._exit(0)

    def _on_destroy(self, hwnd, msg, wparam, lparam):
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, self.notify_id)
        win32gui.PostQuitMessage(0)

    def run(self):
        win32gui.PumpMessages()

def start_tray(hud) -> None:
    def _run():
        tray = Win32Tray(hud)
        hud._tray_icon = tray
        tray.run()
    threading.Thread(target=_run, daemon=True).start()
def hide_to_tray(hud) -> None:
    # 1. Track visible sub-windows to restore them later
    hud._hidden_subwins = []
    _subwin_attrs = ['_perf_win', '_deck_win', '_settings_win', '_ext_win', '_spell_win', '_keybind_win', '_mail_win']
    for attr in _subwin_attrs:
        win = getattr(hud, attr, None)
        if win and win.winfo_exists() and win.winfo_viewable():
            hud._hidden_subwins.append(attr)
            win.withdraw()
            
    # 2. Hide main window
    hud.root.withdraw()

def show_main_win(hud) -> None:
    # 1. Restore main window
    hud.root.deiconify()
    hud.root.attributes('-topmost', False)
    hud.root.lift()
    hud.root.focus_set()
    
    # 2. Restore previously visible sub-windows
    if hasattr(hud, '_hidden_subwins'):
        for attr in hud._hidden_subwins:
            win = getattr(hud, attr, None)
            if win and win.winfo_exists():
                win.deiconify()
                # Special handling for pinned windows: reapplying topmost helps on some Windows versions
                if attr == '_perf_win' and hasattr(win, '_pinned'):
                    if win._pinned.get():
                        win.attributes('-topmost', True)
        hud._hidden_subwins = []

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
