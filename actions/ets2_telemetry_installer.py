import os
import re
import sys
import shutil
import tempfile
import threading
import winreg
from pathlib import Path
from typing import Optional
ETS2_APP_ID      = "227300"
PLUGIN_DLL_NAME  = "scs-telemetry.dll"
PLUGINS_SUBPATH  = Path("bin") / "win_x64" / "plugins"
GITHUB_API_URL   = "https://api.github.com/repos/truckermudgeon/scs-sdk-plugin/releases/latest"
GITHUB_FALLBACK_URL = "https://github.com/truckermudgeon/scs-sdk-plugin/releases/download/v1.12.2/scs-sdk-plugin-1.12.2.zip"
ZIP_DLL_PATH     = "Win64/scs-telemetry.dll"
ETS2_EXE_NAME    = "eurotrucks2.exe"
def _find_via_uninstall_key() -> Optional[str]:
    key_path = (
        f"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Steam App {ETS2_APP_ID}"
    )
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ) as k:
                val, _ = winreg.QueryValueEx(k, "InstallLocation")
                if val and Path(val).exists():
                    return val
        except OSError:
            pass
    return None
def _find_via_steam_manifests() -> Optional[str]:
    steam_path: Optional[str] = None
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in ("SOFTWARE\\WOW6432Node\\Valve\\Steam", "SOFTWARE\\Valve\\Steam"):
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as k:
                    steam_path, _ = winreg.QueryValueEx(k, "InstallPath")
                    break
            except OSError:
                pass
        if steam_path:
            break
    if not steam_path:
        return None
    lf_path = Path(steam_path) / "steamapps" / "libraryfolders.vdf"
    libraries = [Path(steam_path) / "steamapps"]
    if lf_path.exists():
        try:
            content = lf_path.read_text(encoding="utf-8")
            for p in re.findall(r'"path"\s+"([^"]+)"', content):
                lib = Path(p.replace("\\\\", "\\")) / "steamapps"
                if lib.exists() and lib not in libraries:
                    libraries.append(lib)
        except Exception:
            pass
    manifest_name = f"appmanifest_{ETS2_APP_ID}.acf"
    for lib in libraries:
        manifest = lib / manifest_name
        if not manifest.exists():
            continue
        try:
            data = manifest.read_text(encoding="utf-8")
            dir_match = re.search(r'"installdir"\s+"([^"]+)"', data)
            if dir_match:
                install_dir = lib / "common" / dir_match.group(1)
                if install_dir.exists():
                    return str(install_dir)
        except Exception:
            pass
    return None
def find_ets2_path() -> Optional[str]:
    return _find_via_uninstall_key() or _find_via_steam_manifests()
def validate_ets2_path(path: str) -> bool:
    p = Path(path)
    return (p / "bin" / "win_x64" / ETS2_EXE_NAME).exists() or           (p / ETS2_EXE_NAME).exists()
def _get_latest_zip_url() -> str:
    try:
        import requests
        r = requests.get(GITHUB_API_URL, timeout=10,
                         headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        for asset in r.json().get("assets", []):
            name: str = asset.get("name", "").lower()
            if "windows" in name and name.endswith(".zip"):
                return asset["browser_download_url"]
    except Exception:
        pass
    return GITHUB_FALLBACK_URL
def _download_file(url: str, dest: Path) -> bool:
    try:
        import requests
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
        return True
    except Exception:
        return False
def _extract_win64_dll(zip_path: Path, out_dir: Path) -> bool:
    import zipfile
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            target = next(
                (m for m in members
                 if m.lower().endswith(PLUGIN_DLL_NAME.lower())),
                None
            )
            if not target:
                return False
            data = zf.read(target)
            dll_dest = out_dir / PLUGIN_DLL_NAME
            dll_dest.write_bytes(data)
            return True
    except Exception:
        return False
def _unblock_file_ps(path: str) -> None:
    try:
        import subprocess
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command", f"Unblock-File -Path '{path}'"],
            capture_output=True, timeout=15
        )
    except Exception:
        pass
def _install_with_admin(dll_src: Path, plugins_dir: Path) -> bool:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    dest = plugins_dir / PLUGIN_DLL_NAME
    try:
        shutil.copy2(dll_src, dest)
        _unblock_file_ps(str(dest))
        return True
    except PermissionError:
        pass
    try:
        import subprocess
        ps_cmd = (
            f"New-Item -Force -ItemType Directory -Path '{plugins_dir}'; "
            f"Copy-Item -Force '{dll_src}' '{dest}'; "
            f"Unblock-File '{dest}'"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-Command",
             f"Start-Process powershell -Verb RunAs -Wait "
             f"-ArgumentList '-NoProfile','-NonInteractive','-Command',\"{ps_cmd}\""],
            capture_output=True, timeout=60
        )
        return dest.exists()
    except Exception:
        return False
class InstallResult:
    def __init__(self, ok: bool, message: str):
        self.ok = ok
        self.message = message
def install(game_path: str) -> InstallResult:
    plugins_dir = Path(game_path) / PLUGINS_SUBPATH
    dest_dll    = plugins_dir / PLUGIN_DLL_NAME
    url = _get_latest_zip_url()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir  = Path(tmp)
        zip_file = tmp_dir / "release.zip"
        if not _download_file(url, zip_file):
            return InstallResult(False, "download_error")
        if not _extract_win64_dll(zip_file, tmp_dir):
            return InstallResult(False, "extract_error")
        dll_src = tmp_dir / PLUGIN_DLL_NAME
        if not dll_src.exists():
            return InstallResult(False, "extract_error")
        if not _install_with_admin(dll_src, plugins_dir):
            return InstallResult(False, "copy_error")
    return InstallResult(True, "installed")
def show_path_dialog(callback) -> None:
    import tkinter as tk
    import tkinter.filedialog as fd
    try:
        import customtkinter as ctk
        _CTK = True
    except ImportError:
        _CTK = False
    from ui.hud_constants import (
        _BG, _PANEL, _BRD_I, _CYAN, _TEXT, _DIM, _RED
    )
    from ui.hud_utils import _set_dark_title_bar
    root = tk.Toplevel()
    _set_dark_title_bar(root)
    root.after(50, lambda: _set_dark_title_bar(root))
    root.title("ETS2 — Путь не найден")
    root.configure(bg=_BG)
    root.resizable(False, False)
    W = 460
    root.geometry(f"{W}x260")
    root.grab_set()
    tk.Label(root, text="Euro Truck Simulator 2 не найден",
             bg=_BG, fg=_CYAN,
             font=("Segoe UI", 13, "bold")).pack(pady=(20, 6), padx=20)
    tk.Label(root, text="Установите игру через Steam, или укажите\n"
                   "путь к директории Euro Truck Simulator 2 вручную.",
             bg=_BG, fg=_TEXT,
             font=("Segoe UI", 10),
             justify="center").pack(padx=20)
    _path_var = tk.StringVar()
    input_frame = tk.Frame(root, bg=_BG)
    input_frame.pack(fill="x", padx=20, pady=(16, 0))
    path_entry = tk.Entry(input_frame, textvariable=_path_var,
                          bg=_PANEL, fg=_TEXT, insertbackground=_CYAN,
                          relief="flat", bd=0,
                          font=("Segoe UI", 9),
                          highlightthickness=1,
                          highlightbackground=_BRD_I,
                          highlightcolor=_CYAN)
    path_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))
    def _browse():
        chosen = fd.askdirectory(title="Выберите папку с ETS2",
                                 parent=root)
        if chosen:
            _path_var.set(chosen.replace("/", "\\"))
            _validate()
    browse_btn = tk.Button(input_frame, text="Обзор",
                           bg=_PANEL, fg=_CYAN, activebackground=_BRD_I,
                           activeforeground=_CYAN, relief="flat", bd=0,
                           font=("Segoe UI", 9, "bold"), cursor="hand2",
                           padx=10, pady=4,
                           command=_browse)
    browse_btn.pack(side="left")
    hint_var = tk.StringVar()
    tk.Label(root, textvariable=hint_var, bg=_BG, fg=_RED,
             font=("Segoe UI", 8)).pack(pady=(4, 0))
    def _validate() -> bool:
        p = _path_var.get().strip()
        if not p:
            hint_var.set("")
            ok_btn.configure(state="disabled")
            return False
        if not validate_ets2_path(p):
            hint_var.set("eurotrucks2.exe не найден в указанной папке")
            ok_btn.configure(state="disabled")
            return False
        hint_var.set("")
        ok_btn.configure(state="normal")
        return True
    path_entry.bind("<KeyRelease>", lambda _e: _validate())
    btn_frame = tk.Frame(root, bg=_BG)
    btn_frame.pack(pady=(16, 20))
    def _confirm():
        p = _path_var.get().strip()
        if validate_ets2_path(p):
            root.grab_release()
            root.destroy()
            callback(p)
    def _cancel():
        root.grab_release()
        root.destroy()
        callback(None)
    cancel_btn = tk.Button(btn_frame, text="Отмена",
                           bg=_PANEL, fg=_DIM, activebackground=_BRD_I,
                           activeforeground=_TEXT, relief="flat", bd=0,
                           font=("Segoe UI", 10), cursor="hand2",
                           padx=18, pady=6, command=_cancel)
    cancel_btn.pack(side="left", padx=(0, 10))
    ok_btn = tk.Button(btn_frame, text="Установить",
                       bg=_CYAN, fg=_BG, activebackground="#00cccc",
                       activeforeground=_BG, relief="flat", bd=0,
                       font=("Segoe UI", 10, "bold"), cursor="hand2",
                       padx=18, pady=6, state="disabled",
                       command=_confirm)
    ok_btn.pack(side="left")
    root.protocol("WM_DELETE_WINDOW", _cancel)
def run_installer(tk_root=None, on_done=None) -> None:
    def _do_install(path: str):
        def _bg():
            result = install(path)
            if on_done:
                on_done(result)
        threading.Thread(target=_bg, daemon=True, name="ets2_installer").start()
    def _on_dialog(path: Optional[str]):
        if path is None:
            return
        _do_install(path)
    game_path = find_ets2_path()
    if game_path and validate_ets2_path(game_path):
        _do_install(game_path)
    else:
        if tk_root:
            tk_root.after(0, lambda: show_path_dialog(_on_dialog))
        else:
            show_path_dialog(_on_dialog)
def is_telemetry_installed() -> bool:
    game_path = find_ets2_path()
    if not game_path:
        return False
    plugins_dir = Path(game_path) / PLUGINS_SUBPATH
    dll_path = plugins_dir / PLUGIN_DLL_NAME
    return dll_path.exists()
