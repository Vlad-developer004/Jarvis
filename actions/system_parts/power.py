import subprocess
from actions.system_control import _save_current_plan, _restore_previous_plan
def activate_economy_mode() -> tuple[bool, str]:
    try:
        _save_current_plan()
        subprocess.run(['cmd', '/c', 'powercfg', '/setactive', 'a1841308-3541-4fab-bc81-f71556f20b4a'], creationflags=134217728)
        ps_cmd = 'powercfg /setdcvalueindex SCHEME_CURRENT e5a06314-41d1-460d-85ee-f56f145f6534 bf393661-bc47-49f2-8ef7-3165b610c436 100; powercfg /setacvalueindex SCHEME_CURRENT e5a06314-41d1-460d-85ee-f56f145f6534 bf393661-bc47-49f2-8ef7-3165b610c436 100; powercfg /setactive SCHEME_CURRENT'
        subprocess.run(['cmd', '/c', 'powershell', '-NoProfile', '-Command', ps_cmd], creationflags=134217728)
        return (True, 'Режим экономии и системный тумблер активированы')
    except Exception as e:
        return (False, str(e))
def deactivate_economy_mode() -> tuple[bool, str]:
    try:
        _restore_previous_plan()
        ps_cmd = 'powercfg /setdcvalueindex SCHEME_CURRENT e5a06314-41d1-460d-85ee-f56f145f6534 bf393661-bc47-49f2-8ef7-3165b610c436 20; powercfg /setacvalueindex SCHEME_CURRENT e5a06314-41d1-460d-85ee-f56f145f6534 bf393661-bc47-49f2-8ef7-3165b610c436 0; powercfg /setactive SCHEME_CURRENT'
        subprocess.run(['cmd', '/c', 'powershell', '-NoProfile', '-Command', ps_cmd], creationflags=134217728)
        return (True, 'Режим экономии отключен')
    except Exception as e:
        return (False, str(e))
