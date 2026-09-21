import os
import subprocess
import time
KILL_PROCESSES = ['firefox.exe', 'msedge.exe', 'opera.exe', 'WINWORD.EXE', 'EXCEL.EXE', 'POWERPNT.EXE', 'OUTLOOK.EXE', 'ONENOTE.EXE', 'Teams.exe', 'Telegram.exe', 'Viber.exe', 'Skype.exe', 'Spotify.exe', 'spotify.exe', 'SearchApp.exe', 'SearchHost.exe', 'Widgets.exe', 'WidgetService.exe', 'GameBar.exe', 'GameBarPresenceWriter.exe', 'PhoneExperienceHost.exe', 'YourPhone.exe', 'MicrosoftEdgeUpdate.exe', 'BraveUpdate.exe', 'GoogleUpdate.exe', 'jusched.exe', 'jucheck.exe']
_saved_power_plan = None
POWER_PLAN_FILE = os.path.join('data', 'previous_power_plan.txt')
def _run_system_async(func, *args):
    import threading
    t = threading.Thread(target=func, args=args, daemon=True)
    t.start()
def _get_active_power_plan() -> str | None:
    try:
        r = subprocess.run(['cmd', '/c', 'powercfg', '/getactivescheme'], capture_output=True, text=True, creationflags=134217728)
        import re as _re
        m = _re.search('([0-9a-f\\-]{36})', r.stdout)
        return m.group(1) if m else None
    except Exception:
        return None
def _save_current_plan():
    global _saved_power_plan
    plan = _get_active_power_plan()
    if plan:
        _saved_power_plan = plan
        try:
            with open(POWER_PLAN_FILE, 'w') as f:
                f.write(plan)
        except Exception:
            pass
def _restore_previous_plan():
    plan = None
    if os.path.exists(POWER_PLAN_FILE):
        try:
            with open(POWER_PLAN_FILE, 'r') as f:
                plan = f.read().strip()
        except Exception:
            pass
    if not plan:
        plan = '381b4222-f694-41f0-9685-ff5bb260df2e'
    try:
        subprocess.run(['cmd', '/c', 'powercfg', '/setactive', plan], creationflags=134217728)
    except Exception:
        pass
def shutdown_pc() -> tuple[bool, str]:
    try:
        subprocess.Popen(['cmd', '/c', 'shutdown', '/s', '/f', '/t', '5'], creationflags=134217728)
        return (True, 'Выключение через 5 секунд')
    except Exception as e:
        return (False, str(e))
def restart_pc() -> tuple[bool, str]:
    try:
        subprocess.Popen(['cmd', '/c', 'shutdown', '/r', '/t', '5'], creationflags=134217728)
        return (True, 'Перезагрузка через 5 секунд')
    except Exception as e:
        return (False, str(e))
def schedule_shutdown(seconds: int) -> tuple[bool, str]:
    try:
        subprocess.Popen(['shutdown', '/s', '/t', str(seconds)])
        return (True, f'Выключение через {seconds} сек')
    except Exception as e:
        return (False, str(e))
def cancel_shutdown() -> tuple[bool, str]:
    try:
        subprocess.Popen(['shutdown', '/a'])
        return (True, 'Таймер отменён')
    except Exception as e:
        return (False, str(e))
def _toggle_radio(kind_name: str, enabled: bool):
    """
    Toggle a Windows radio (WiFi or Bluetooth).
    Tier 1: winrt (if installed)
    Tier 2: PowerShell Get-PnpDevice / Enable-NetAdapter approach
    Tier 3: netsh (WiFi only) / PowerShell DeviceManagement
    """
    import asyncio

    # ── Tier 1: winrt ────────────────────────────────────────────────────
    try:
        import winrt.windows.devices.radios as _radios  # type: ignore

        async def _winrt_toggle():
            radio_list = await _radios.Radio.get_radios_async()
            target_kind = _radios.RadioKind.WI_FI if kind_name == 'wifi' else _radios.RadioKind.BLUETOOTH
            for r in radio_list:
                if r.kind == target_kind:
                    state = _radios.RadioState.ON if enabled else _radios.RadioState.OFF
                    await r.set_state_async(state)
                    print(f'[SYSTEM] {kind_name} toggled via winrt → {state}', flush=True)
                    return True
            return False

        ok = asyncio.run(_winrt_toggle())
        if ok:
            return
    except Exception:
        pass

    # ── Tier 2: PowerShell Enable/Disable-NetAdapter ─────────────────────
    try:
        verb = 'Enable' if enabled else 'Disable'
        if kind_name == 'wifi':
            ps_cmd = (
                f'Get-NetAdapter | Where-Object {{$_.PhysicalMediaType -eq "Native 802.11"}} | '
                f'{verb}-NetAdapter -Confirm:$false'
            )
        else:  # bluetooth
            ps_cmd = (
                f'Get-PnpDevice | Where-Object {{$_.Class -eq "Bluetooth"}} | '
                f'{verb}-PnpDevice -Confirm:$false'
            )
        subprocess.run(
            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
            capture_output=True, timeout=10, creationflags=134217728
        )
        print(f'[SYSTEM] {kind_name} toggled via PowerShell NetAdapter', flush=True)
        return
    except Exception:
        pass

    # ── Tier 3: netsh (WiFi only) ────────────────────────────────────────
    if kind_name == 'wifi':
        try:
            action = 'connect' if enabled else 'disconnect'
            subprocess.run(
                ['netsh', 'interface', 'set', 'interface', 'Wi-Fi', 'admin=', 'enabled' if enabled else 'disabled'],
                capture_output=True, timeout=5, creationflags=134217728
            )
            print(f'[SYSTEM] WiFi toggled via netsh', flush=True)
        except Exception as e:
            print(f'[SYSTEM] WiFi toggle failed all tiers: {e}', flush=True)
    else:
        print(f'[SYSTEM] Bluetooth toggle: no fallback available without winrt', flush=True)


def _toggle_wifi_worker(enabled: bool):
    _toggle_radio('wifi', enabled)

def toggle_wifi(enabled: bool) -> tuple[bool, str]:
    _run_system_async(_toggle_wifi_worker, enabled)
    return (True, f'Команда на {("включение" if enabled else "выключение")} Wi-Fi отправлена')
def _toggle_bluetooth_worker(enabled: bool):
    _toggle_radio('bluetooth', enabled)

def toggle_bluetooth(enabled: bool) -> tuple[bool, str]:
    _run_system_async(_toggle_bluetooth_worker, enabled)
    return (True, f'Команда на {("включение" if enabled else "выключение")} Bluetooth отправлена')
def change_brightness(direction: str, amount: int=15) -> tuple[bool, str]:
    import screen_brightness_control as sbc
    try:
        current = sbc.get_brightness()
        if isinstance(current, list):
            current = current[0]
        if direction == 'up':
            new_val = min(100, current + amount)
        elif direction == 'down':
            new_val = max(0, current - amount)
        else:
            new_val = amount
        sbc.set_brightness(new_val)
        return (True, f'Яркость установлена на {new_val}%')
    except Exception as e:
        return (False, str(e))
def check_internet_speed() -> str:
    import speedtest
    try:
        st = speedtest.Speedtest(secure=True)
        st.get_best_server()
        download_speed = st.download(threads=8)
        mb_speed = round(download_speed / 10 ** 6)
        return f'Сэр, текущая скорость интернета {mb_speed} мегабит.'
    except Exception:
        return 'Не удалось проверить скорость интернета. Возможно проблемы с DNS или таймаутом.'
def get_my_ip() -> str:
    import requests
    try:
        ip = requests.get('https://api.ipify.org', timeout=5).text
        return f"Ваш внешний IP адрес: {ip}"
    except Exception:
        return "Не удалось получить IP адрес. Проверьте соединение."
def clean_system() -> tuple[bool, str]:
    """
    High-level deep PC cleanup:
    - User & System %TEMP% folders
    - Windows Update cache (SoftwareDistribution\\Download)
    - Browser caches (Chrome, Brave, Firefox, Edge, Yandex)
    - Thumbnail cache (thumbcache_*.db)
    - Windows Prefetch files
    - Recycle Bin
    - DNS cache flush
    - Windows Event Logs clear
    - Memory standby list flush (EmptyStandbyList)
    Reports total MB freed.
    """
    import shutil
    import threading

    def _do_clean(speak_fn=None):
        import ctypes
        import glob

        freed_bytes = 0
        errors = 0
        local_app = os.environ.get('LOCALAPPDATA', '')
        app_data   = os.environ.get('APPDATA', '')
        sys_root   = os.environ.get('SystemRoot', r'C:\Windows')
        user_profile = os.environ.get('USERPROFILE', '')

        def _rm(path: str):
            nonlocal freed_bytes, errors
            try:
                if os.path.isfile(path) or os.path.islink(path):
                    freed_bytes += os.path.getsize(path)
                    os.unlink(path)
                elif os.path.isdir(path):
                    size = sum(
                        os.path.getsize(os.path.join(dp, f))
                        for dp, _, fs in os.walk(path)
                        for f in fs
                        if os.path.exists(os.path.join(dp, f))
                    )
                    freed_bytes += size
                    shutil.rmtree(path, ignore_errors=True)
            except Exception:
                errors += 1

        def _rm_dir_contents(path: str, skip_names: list = None):
            if not path or not os.path.isdir(path):
                return
            for item in os.listdir(path):
                if skip_names and item in skip_names:
                    continue
                if 'jarvis_tts_cache' in item:
                    continue
                _rm(os.path.join(path, item))

        # ── 1. TEMP folders ──────────────────────────────────────────────
        for tmp in [
            os.environ.get('TEMP'),
            os.path.join(sys_root, 'Temp'),
            os.path.join(local_app, 'Temp'),
        ]:
            _rm_dir_contents(tmp)

        # ── 2. Windows Update cache ──────────────────────────────────────
        _rm_dir_contents(os.path.join(sys_root, r'SoftwareDistribution\Download'))

        # ── 3. Browser caches ────────────────────────────────────────────
        browser_cache_paths = [
            # Chrome
            os.path.join(local_app, r'Google\Chrome\User Data\Default\Cache'),
            os.path.join(local_app, r'Google\Chrome\User Data\Default\Code Cache'),
            os.path.join(local_app, r'Google\Chrome\User Data\Default\GPUCache'),
            # Brave
            os.path.join(local_app, r'BraveSoftware\Brave-Browser\User Data\Default\Cache'),
            os.path.join(local_app, r'BraveSoftware\Brave-Browser\User Data\Default\Code Cache'),
            os.path.join(local_app, r'BraveSoftware\Brave-Browser\User Data\Default\GPUCache'),
            # Edge
            os.path.join(local_app, r'Microsoft\Edge\User Data\Default\Cache'),
            os.path.join(local_app, r'Microsoft\Edge\User Data\Default\Code Cache'),
            # Firefox
            os.path.join(local_app, r'Mozilla\Firefox\Profiles'),
            # Opera
            os.path.join(app_data,  r'Opera Software\Opera Stable\Cache'),
            # Yandex
            os.path.join(local_app, r'Yandex\YandexBrowser\User Data\Default\Cache'),
        ]
        for bp in browser_cache_paths:
            if 'Firefox' in bp:
                # Firefox keeps per-profile cache dirs
                if os.path.isdir(bp):
                    for prof in os.listdir(bp):
                        for sub in ('cache2', 'startupCache', 'OfflineCache'):
                            _rm_dir_contents(os.path.join(bp, prof, sub))
            else:
                _rm_dir_contents(bp)

        # ── 4. Thumbnail cache ───────────────────────────────────────────
        thumb_dir = os.path.join(local_app, r'Microsoft\Windows\Explorer')
        if os.path.isdir(thumb_dir):
            for f in glob.glob(os.path.join(thumb_dir, 'thumbcache_*.db')):
                _rm(f)
            for f in glob.glob(os.path.join(thumb_dir, 'iconcache_*.db')):
                _rm(f)

        # ── 5. Windows Prefetch ──────────────────────────────────────────
        prefetch = os.path.join(sys_root, r'Prefetch')
        _rm_dir_contents(prefetch)

        # ── 6. Recent / Jump-list spam ───────────────────────────────────
        for sub in [
            r'Microsoft\Windows\Recent\AutomaticDestinations',
            r'Microsoft\Windows\Recent\CustomDestinations',
        ]:
            _rm_dir_contents(os.path.join(app_data, sub))

        # ── 7. Recycle Bin (all drives) ──────────────────────────────────
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x0007)
        except Exception:
            pass

        # ── 8. DNS cache flush ───────────────────────────────────────────
        try:
            subprocess.run(['ipconfig', '/flushdns'], capture_output=True, creationflags=134217728, timeout=5)
        except Exception:
            pass

        # ── 9. Memory standby list flush (needs admin, fails gracefully) ──
        try:
            elist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools', 'EmptyStandbyList.exe')
            if os.path.exists(elist_path):
                subprocess.run([elist_path, 'standbylist'], capture_output=True, creationflags=134217728, timeout=10)
            else:
                # Fallback: use RAMMap CLI if available
                subprocess.run(['RAMMap.exe', '-Et'], capture_output=True, creationflags=134217728, timeout=5)
        except Exception:
            pass

        # ── 10. Windows Event Log clear (non-critical, best-effort) ──────
        try:
            logs_to_clear = ['Application', 'System', 'Setup']
            for log in logs_to_clear:
                subprocess.run(
                    ['wevtutil', 'cl', log],
                    capture_output=True, creationflags=134217728, timeout=5
                )
        except Exception:
            pass

        freed_mb = round(freed_bytes / (1024 * 1024))
        msg = f'Уборка завершена. Освобождено {freed_mb} МБ. Ошибок (занятые файлы): {errors}.'
        print(f'[CLEANUP] {msg}', flush=True)
        if speak_fn:
            speak_fn(msg)

    # Run in background so Jarvis can speak immediately
    import threading
    from core.speech import speak as _speak
    threading.Thread(target=_do_clean, args=(_speak,), daemon=True, name='jarvis-cleanup').start()
    return (True, '')
