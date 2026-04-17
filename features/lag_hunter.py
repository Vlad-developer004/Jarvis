import threading
import time
import os
from core.system import app_state
_ignored_pids: set[int] = set()
_ignored_names: set[str] = set()
_hunter_thread: threading.Thread | None = None
_stop_event = threading.Event()
_pending_heavy: dict | None = None
_CPU_THRESH = 92
_MEM_THRESH_GB = 6.0
_SYSTEM_PROCESS_NAMES = frozenset({'system', 'registry', 'smss.exe', 'csrss.exe', 'wininit.exe', 'services.exe', 'lsass.exe', 'svchost.exe', 'winlogon.exe', 'dwm.exe', 'explorer.exe', 'taskhostw.exe', 'runtimebroker.exe', 'shellexperiencehost.exe', 'startmenuexperiencehost.exe', 'searchhost.exe', 'searchindexer.exe', 'searchapp.exe', 'sihost.exe', 'fontdrvhost.exe', 'ctfmon.exe', 'conhost.exe', 'dashost.exe', 'dllhost.exe', 'applicationframehost.exe', 'systemsettings.exe', 'securityhealthservice.exe', 'securityhealthsystray.exe', 'ntoskrnl.exe', 'msmpeng.exe', 'mpcmdrun.exe', 'sgrmbroker.exe', 'spoolsv.exe', 'wudfhost.exe', 'wmiprvse.exe', 'audiodg.exe', 'idle', 'system idle process', 'tiworker.exe', 'textinputhost.exe', 'lockapp.exe', 'widgetsservice.exe', 'widgets.exe', 'gamebarpresencewriter.exe', 'python.exe', 'pythonw.exe'})
_handler = None
def _is_system_process(name: str) -> bool:
    return name.lower() in _SYSTEM_PROCESS_NAMES
def _check_once() -> dict | None:
    import psutil
    my_pid = os.getpid()
    procs = {}
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            pid = proc.info['pid']
            name = (proc.info['name'] or '').lower()
            if pid == my_pid or pid in _ignored_pids or name in _ignored_names:
                continue
            proc.cpu_percent(interval=0)
            procs[pid] = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    time.sleep(0.5)
    worst = None
    worst_score = 0
    for pid, proc in procs.items():
        try:
            name = proc.name() or ''
            if _is_system_process(name):
                continue
            try:
                if time.time() - proc.create_time() < 30:
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            cpu_raw = proc.cpu_percent(interval=0)
            cpu = cpu_raw / (psutil.cpu_count(logical=True) or 1)
            try:
                mem_bytes = proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            mem_gb = mem_bytes / 1024 ** 3
            is_heavy = cpu > _CPU_THRESH or mem_gb > _MEM_THRESH_GB
            if is_heavy:
                score = cpu + mem_gb * 50
                if score > worst_score:
                    worst_score = score
                    worst = {'pid': pid, 'name': name, 'cpu': round(cpu, 1), 'mem_gb': round(mem_gb, 2)}
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return worst
def _get_active_pids() -> set[int]:
    try:
        import win32gui, win32process, psutil
        hwnd = win32gui.GetForegroundWindow()
        _, active_pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            active_name = psutil.Process(active_pid).name().lower()
            return {p.pid for p in psutil.process_iter(['pid', 'name'])
                    if (p.info['name'] or '').lower() == active_name}
        except Exception:
            return {active_pid}
    except Exception:
        return set()
def _hunter_loop():
    global _pending_heavy
    while not _stop_event.is_set():
        for _ in range(60):
            if _stop_event.is_set():
                return
            time.sleep(1)
        if _stop_event.is_set():
            return
        if app_state.game_mode:
            _pending_heavy = None
            continue
        active_pids = _get_active_pids()
        try:
            heavy = _check_once()
            if not heavy or not _handler:
                _pending_heavy = None
                continue
            if heavy.get('pid') in active_pids:
                _pending_heavy = None
                continue
            if _pending_heavy and _pending_heavy.get('pid') == heavy.get('pid'):
                _notify_handler(heavy)
                _pending_heavy = None
            else:
                _pending_heavy = heavy
        except Exception:
            _pending_heavy = None
def _notify_handler(proc_info: dict):
    name = proc_info['name']
    cpu = proc_info['cpu']
    mem_gb = proc_info['mem_gb']
    from core.speech import normalize_for_tts
    nice_name = normalize_for_tts(name.replace('.exe', ''))
    msg = f'Сэр, {nice_name} чрезмерно нагружает систему. '
    if cpu > 85:
        msg += f'Процессор: {cpu}%. '
    if mem_gb > 1.0:
        msg += f'Память: {mem_gb} гигабайт. '
    msg += 'Желаете завершить его?'
    with _handler._state_lock:
        if _handler.interactive_state is not None:
            _ignored_pids.add(proc_info['pid'])
            return
        _handler.interactive_state = 'lag_hunter_confirm'
        _handler.interactive_data = {'proc_info': proc_info}
    _handler.speak(msg)
def handle_lag_response(text_lower: str, data: dict) -> dict:
    words = text_lower.split()
    proc_info = data.get('proc_info', {})
    pid = proc_info.get('pid', 0)
    name = proc_info.get('name', '???')
    if any((w in words for w in ['да', 'ага', 'давай', 'убей', 'заверши', 'конечно', 'убить'])):
        try:
            import psutil
            proc = psutil.Process(pid)
            proc.kill()
            return {'clear_state': True, 'speak': f'Процесс {name} завершён.'}
        except Exception as e:
            return {'clear_state': True, 'speak': f'Не удалось завершить {name}.'}
    else:
        if len(_ignored_pids) > 300:
            _ignored_pids.clear()
        if len(_ignored_names) > 300:
            _ignored_names.clear()
        _ignored_pids.add(pid)
        _ignored_names.add(name.lower())
        return {'clear_state': True, 'speak': f'Хорошо, {name} оставлен в покое до конца сессии.'}
def start_lag_hunter(handler):
    global _handler, _hunter_thread
    _handler = handler
    _stop_event.clear()
    _hunter_thread = threading.Thread(target=_hunter_loop, daemon=True)
    _hunter_thread.start()
def stop_lag_hunter():
    _stop_event.set()
