import os
import time
import subprocess
import pygetwindow as gw
from core.system import app_state as _jarvis_state
from actions.app_launcher import open_app, SYSTEM_WHITELIST
from actions.system_control import _get_active_power_plan, KILL_PROCESSES
POWER_PLAN_FILE = os.path.join('data', 'previous_power_plan.txt')
_GAME_PREFS_PATH = os.path.join('data', 'game_mode_prefs.json')
def _load_game_mode_prefs() -> dict:
    try:
        if os.path.exists(_GAME_PREFS_PATH):
            import json
            with open(_GAME_PREFS_PATH, 'r', encoding='utf-8') as f:
                d = json.load(f)
                return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}
def _game_keep_title(title_lower: str, prefs: dict) -> bool:
    try:
        keep = prefs.get('keep_titles', [])
        if isinstance(keep, list):
            for s in keep:
                if isinstance(s, str) and s.strip() and s.strip().lower() in title_lower:
                    return True
    except Exception:
        pass
    return False
def open_work() -> tuple[bool, str]:
    ok, msg = open_app('antigravity')
    if ok:
        return (True, 'Рабочее место готово')
    return (False, msg)
def activate_game_mode() -> tuple[bool, str]:
    try:
        results: list[str] = []
        closed = 0
        prefs = _load_game_mode_prefs()
        for w in gw.getAllWindows():
            if not w.title or not w.visible:
                continue
            title_lower = w.title.lower()
            if any((wl in title_lower for wl in SYSTEM_WHITELIST)):
                continue
            if _game_keep_title(title_lower, prefs):
                continue
            try:
                w.close()
                closed += 1
            except Exception:
                pass
        if closed:
            results.append(f'Закрыто окон: {closed}')
            time.sleep(0.5)
        killed = 0
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name']
                if pname in KILL_PROCESSES:
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            results.append(f'Завершено процессов: {killed}')
        try:
            subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-Process | Where-Object {$_.WorkingSet64 -gt 50MB} | ForEach-Object { try { $_.MinWorkingSet = 1 } catch {} }'],
                capture_output=True,
                timeout=5,
                creationflags=134217728,
            )
            results.append('RAM очищена')
        except Exception:
            pass
        current_plan = _get_active_power_plan()
        high_perf_guid = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
        if current_plan and current_plan != high_perf_guid:
            try:
                with open(POWER_PLAN_FILE, 'w') as f:
                    f.write(current_plan)
            except Exception:
                pass
        try:
            subprocess.run(['powercfg', '/setactive', high_perf_guid], capture_output=True, creationflags=134217728)
            results.append('Питание: высокая производительность')
        except Exception:
            pass
        summary = '; '.join(results) if results else 'Готово'
        _jarvis_state.game_mode = True
        try:
            from core.system import set_process_priority
            set_process_priority('high')
        except Exception:
            pass
        return (True, summary)
    except Exception as e:
        return (False, str(e))
def deactivate_game_mode() -> tuple[bool, str]:
    try:
        results = []
        plan_to_restore = None
        try:
            if os.path.exists(POWER_PLAN_FILE):
                with open(POWER_PLAN_FILE, 'r') as f:
                    plan_to_restore = f.read().strip()
        except Exception:
            pass
        if plan_to_restore:
            try:
                subprocess.run(['powercfg', '/setactive', plan_to_restore], capture_output=True, creationflags=134217728)
                results.append(f'Питание восстановлено ({plan_to_restore})')
                if os.path.exists(POWER_PLAN_FILE):
                    os.remove(POWER_PLAN_FILE)
            except Exception:
                pass
        else:
            try:
                r = subprocess.run(['powercfg', '/list'], capture_output=True, text=True, creationflags=134217728)
                acer_guid = None
                balanced_guid = '381b4222-f694-41f0-9685-ff5bb260df2e'
                import re as _re
                for line in r.stdout.splitlines():
                    if 'Acer' in line or 'acer' in line.lower():
                        m = _re.search('([0-9a-f\\-]{36})', line)
                        if m:
                            acer_guid = m.group(1)
                            break
                target_guid = acer_guid if acer_guid else balanced_guid
                plan_name = 'Acer' if acer_guid else 'сбалансированный'
                subprocess.run(['powercfg', '/setactive', target_guid], capture_output=True, creationflags=134217728)
                results.append(f'Питание: {plan_name}')
            except Exception:
                pass
        summary = '; '.join(results) if results else 'Готово'
        try:
            from features.ets2 import monitor as ets2_monitor
            ets2_monitor.stop()
        except Exception:
            pass
        try:
            from features.planetbase import monitor as pb_monitor
            pb_monitor.stop()
        except Exception:
            pass
        try:
            from core.system import set_process_priority
            set_process_priority('normal')
        except Exception:
            pass
        _jarvis_state.game_mode = False
        try:
            from actions.game_input import unload_profile
            unload_profile()
        except Exception:
            pass
        return (True, summary)
    except Exception as e:
        return (False, str(e))
