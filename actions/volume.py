import time
from actions import keysend
from core.safe import swallow as _swallow
def send_hardware_key(vk_code):
    keysend.press(vk_code)
# All volume work goes to the native audio service (native/jarvis_audio, core/native_audio.py); there is no pycaw path.
_UNAVAILABLE = 'Сервис громкости недоступен'
def _service():
    from core import native_audio
    return native_audio.service()
def _master(level=None, muted=None):
    """Master volume through the service: {'level', 'muted'} after the change (or as it is), None when the service cannot answer."""
    req = {'op': 'master_get'}
    if level is not None or muted is not None:
        req = {'op': 'master_set', **({'level': level} if level is not None else {}), **({'muted': muted} if muted is not None else {})}
    ans = _service().request(**req)
    return ans if ans and ans.get('ok') else None
def change_volume(direction: str, amount: int=7) -> tuple[bool, str]:
    VK_VOLUME_UP = 175
    VK_VOLUME_DOWN = 174
    try:
        vk = VK_VOLUME_UP if direction == 'up' else VK_VOLUME_DOWN
        presses = max(1, amount // 2)
        for _ in range(presses):
            send_hardware_key(vk)
            time.sleep(0.02)
        return (True, f'Громкость {('увеличена' if direction == 'up' else 'уменьшена')} на {amount}%')
    except Exception as e:
        return (False, str(e))
def mute_volume(mute: bool=True) -> tuple[bool, str]:
    VK_VOLUME_MUTE = 173
    try:
        now = _master()
        if now is None:
            return (False, _UNAVAILABLE)
        current = now['muted']
        if mute and (not current) or (not mute and current):
            send_hardware_key(VK_VOLUME_MUTE)
        state = 'выключен' if mute else 'включён'
        return (True, f'Звук {state}')
    except Exception as e:
        return (False, str(e))
def set_volume_level(level: float) -> tuple[bool, str]:
    try:
        clamped = max(0.0, min(1.0, level))
        if _master(level=clamped, muted=False) is None:
            return (False, _UNAVAILABLE)
        send_hardware_key(174)
        time.sleep(0.03)
        send_hardware_key(175)
        time.sleep(0.05)
        _master(level=clamped)
        label = int(level * 100)
        return (True, f'Громкость {label}%')
    except Exception as e:
        return (False, str(e))
def force_unduck():
    """Give every lowered app its volume back (the service also does this on its own if Jarvis exits)."""
    try:
        _service().request(op='unduck')
    except Exception:
        _swallow()
def duck_volume(enable: bool):
    """Lower (enable) or restore the other apps' volume; nested calls are counted by the service."""
    from core import native_audio
    try:
        native_audio.duck(enable)
    except Exception:
        _swallow()
def _fuzzy_find_session(sessions, query: str):
    """Best audio session for a spoken app name: `sessions` are the service's rows ({'name': 'spotify.exe', ...})."""
    from features.gaming import transliterate_cyrillic_to_latin
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None
    query_lower = query.lower().strip()
    query_trans = transliterate_cyrillic_to_latin(query_lower)
    best_session, best_score = (None, 0)
    for s in sessions:
        if not s['name']:
            continue
        proc = s['name'].lower().replace('.exe', '')
        if _fuzz:
            score = max(_fuzz.partial_ratio(query_lower, proc), _fuzz.partial_ratio(query_trans, proc), _fuzz.token_set_ratio(query_trans, proc))
        else:
            score = 100 if (query_lower in proc or query_trans in proc) else 0
        if score > best_score:
            best_score = score
            best_session = s
    return (best_session, best_score) if best_score >= 45 else (None, 0)
def set_app_volume(app_name: str, direction: str, amount: int=20) -> tuple[bool, str]:
    try:
        svc = _service()
        listing = svc.request(op='sessions')
        if not listing or not listing.get('ok'):
            return (False, _UNAVAILABLE)
        session, _score = _fuzzy_find_session(listing['sessions'], app_name)
        if session is None:
            return (False, f'Приложение «{app_name}» не найдено среди активных аудио-сессий.')
        cur = session['volume']
        if direction == 'up':
            new_vol = min(1.0, cur + amount / 100.0)
        elif direction == 'down':
            new_vol = max(0.0, cur - amount / 100.0)
        else:
            new_vol = max(0.0, min(1.0, amount / 100.0))
        ans = svc.request(op='set_session', session=session['id'], level=new_vol)
        if not ans or not ans.get('ok'):
            return (False, _UNAVAILABLE)
        return (True, f"Громкость {session['name'].replace('.exe', '')}: {int(ans['volume'] * 100)} процентов")
    except Exception as e:
        return (False, str(e))
def switch_audio_output(target: str) -> tuple[bool, str]:
    import subprocess
    try:
        cmd = 'powershell -Command "Get-AudioDevice -List | Where-Object {$_.Type -eq \'Playback\'} | Select-Object Index, Name | ConvertTo-Json"'
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', creationflags=134217728)
        if not result.stdout.strip():
            return (False, 'Устройства воспроизведения не найдены.')
        import json
        devices = json.loads(result.stdout)
        if isinstance(devices, dict):
            devices = [devices]
        target = target.lower()
        found_index = None
        found_name = ''
        keywords = []
        if any((x in target for x in ['наушники', 'уши', 'headphones', 'headset', 'kopfhörer'])):
            keywords = ['headphones', 'headset', 'kopfhörer']
        elif any((x in target for x in ['колонки', 'динамики', 'speakers', 'lautsprecher', 'audio2.0'])):
            keywords = ['speakers', 'lautsprecher', 'realtek', 'usbaudio']
        elif any((x in target for x in ['монитор', 'экран', 'mnt', 'display'])):
            keywords = ['mnt', 'display', 'monitor', 'hd audio']
        if not keywords:
            return (False, f'Неизвестный тип устройства: {target}')
        for dev in devices:
            name = dev['Name'].lower()
            if any((k in name for k in keywords)):
                found_index = dev['Index']
                found_name = dev['Name']
                break
        if found_index is not None:
            set_cmd = f'powershell -Command "Set-AudioDevice -Index {found_index}"'
            subprocess.run(set_cmd, creationflags=134217728)
            return (True, found_name)
        else:
            return (False, f'Подходящее устройство ({target}) не найдено.')
    except Exception as e:
        return (False, str(e))
