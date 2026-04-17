import os
import subprocess
import time
from core.system import app_state as _jarvis_state
KILL_PROCESSES = ['firefox.exe', 'msedge.exe', 'opera.exe', 'WINWORD.EXE', 'EXCEL.EXE', 'POWERPNT.EXE', 'OUTLOOK.EXE', 'ONENOTE.EXE', 'Teams.exe', 'Telegram.exe', 'Viber.exe', 'Skype.exe', 'Spotify.exe', 'spotify.exe', 'SearchApp.exe', 'SearchHost.exe', 'Widgets.exe', 'WidgetService.exe', 'GameBar.exe', 'GameBarPresenceWriter.exe', 'PhoneExperienceHost.exe', 'YourPhone.exe', 'MicrosoftEdgeUpdate.exe', 'BraveUpdate.exe', 'GoogleUpdate.exe', 'jusched.exe', 'jucheck.exe']
from actions.app_launcher import SYSTEM_WHITELIST
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
def _toggle_wifi_worker(enabled: bool):
    try:
        import asyncio
        from winsdk.windows.devices import radios
        async def _wifi_toggle():
            radios_list = await radios.Radio.get_radios_async()
            found = False
            for r in radios_list:
                if r.kind == radios.RadioKind.WI_FI:
                    state = radios.RadioState.ON if enabled else radios.RadioState.OFF
                    print(f"[SYSTEM] Toggling WiFi to {state} ({r.name})", flush=True)
                    res = await r.set_state_async(state)
                    print(f"[SYSTEM] WiFi toggle result: {res}", flush=True)
                    found = True
            if not found:
                print("[SYSTEM] No WiFi radio found via winsdk.", flush=True)
        asyncio.run(_wifi_toggle())
    except ImportError:
        print("[SYSTEM] winsdk not installed, WiFi toggle unavailable.", flush=True)
    except Exception as e:
        print(f"[SYSTEM] WiFi toggle error: {e}", flush=True)
def toggle_wifi(enabled: bool) -> tuple[bool, str]:
    _run_system_async(_toggle_wifi_worker, enabled)
    return (True, f'Команда на {("включение" if enabled else "выключение")} Wi-Fi отправлена')
def _toggle_bluetooth_worker(enabled: bool):
    try:
        import asyncio
        from winsdk.windows.devices import radios
        async def _bt_toggle():
            radios_list = await radios.Radio.get_radios_async()
            found = False
            for r in radios_list:
                if r.kind == radios.RadioKind.BLUETOOTH:
                    state = radios.RadioState.ON if enabled else radios.RadioState.OFF
                    print(f"[SYSTEM] Toggling Bluetooth to {state} ({r.name})", flush=True)
                    res = await r.set_state_async(state)
                    print(f"[SYSTEM] Bluetooth toggle result: {res}", flush=True)
                    found = True
            if not found:
                print("[SYSTEM] No Bluetooth radio found via winsdk.", flush=True)
        asyncio.run(_bt_toggle())
    except ImportError:
        print("[SYSTEM] winsdk not installed, Bluetooth toggle unavailable.", flush=True)
    except Exception as e:
        print(f"[SYSTEM] Bluetooth toggle error: {e}", flush=True)
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
    import shutil
    cleaned_dirs = 0
    errors = 0
    temp_paths = [os.environ.get('TEMP'), os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'Temp'), os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp')]
    for path in temp_paths:
        if not path or not os.path.exists(path):
            continue
        for item in os.listdir(path):
            if 'jarvis_tts_cache' in item:
                continue
            item_path = os.path.join(path, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                cleaned_dirs += 1
            except Exception:
                errors += 1
    try:
        subprocess.Popen(['cleanmgr', '/sagerun:1'], creationflags=134217728)
    except Exception:
        pass
    return (True, f'Уборка завершена. Очищено объектов: {cleaned_dirs}. Ошибок (занятые файлы): {errors}')
