import time
import ctypes
import win32con
def send_hardware_key(vk_code):
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
def _get_volume_interface():
    import pythoncom
    pythoncom.CoInitialize()
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return interface.QueryInterface(IAudioEndpointVolume)
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
        vol = _get_volume_interface()
        current = vol.GetMute()
        if mute and (not current) or (not mute and current):
            send_hardware_key(VK_VOLUME_MUTE)
        state = 'выключен' if mute else 'включён'
        return (True, f'Звук {state}')
    except Exception as e:
        return (False, str(e))
def set_volume_level(level: float) -> tuple[bool, str]:
    try:
        vol = _get_volume_interface()
        if vol.GetMute():
            vol.SetMute(0, None)
        clamped = max(0.0, min(1.0, level))
        vol.SetMasterVolumeLevelScalar(clamped, None)
        send_hardware_key(174)
        time.sleep(0.03)
        send_hardware_key(175)
        time.sleep(0.05)
        vol.SetMasterVolumeLevelScalar(clamped, None)
        label = int(level * 100)
        return (True, f'Громкость {label}%')
    except Exception as e:
        return (False, str(e))
_saved_sessions = {}
_duck_count = 0
_duck_lock = __import__('threading').Lock()
def force_unduck():
    global _saved_sessions, _duck_count
    with _duck_lock:
        if not _saved_sessions:
            _duck_count = 0
            return
        snap = dict(_saved_sessions)
        _saved_sessions.clear()
        _duck_count = 0
    try:
        import pythoncom
        pythoncom.CoInitialize()
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
        for session in sessions:
            try:
                s_key = session.ProcessId
                if s_key in snap:
                    vol = session.SimpleAudioVolume
                    if vol is not None:
                        vol.SetMasterVolume(snap[s_key], None)
            except Exception:
                continue
    except Exception:
        pass
    finally:
        try:
            import pythoncom as _pc
            _pc.CoUninitialize()
        except Exception:
            pass
def duck_volume(enable: bool):
    global _saved_sessions, _duck_count
    try:
        import os
        import pythoncom
        from pycaw.pycaw import AudioUtilities
        pythoncom.CoInitialize()
        my_pid = os.getpid()
        with _duck_lock:
            if enable:
                _duck_count += 1
                if _duck_count == 1:
                    _saved_sessions.clear()
                    try:
                        sessions = AudioUtilities.GetAllSessions()
                    except Exception:
                        sessions = []
                    for session in sessions:
                        try:
                            # Skip common system/idle sessions immediately
                            if not session.Process or session.ProcessId == my_pid:
                                continue
                            pid = session.ProcessId
                            volume = session.SimpleAudioVolume
                            if volume:
                                current_vol = volume.GetMasterVolume()
                                if current_vol > 0.02:
                                    if pid not in _saved_sessions:
                                        _saved_sessions[pid] = current_vol
                                    target = min(current_vol, 0.45)
                                    if target < current_vol:
                                        volume.SetMasterVolume(target, None)
                        except Exception:
                            continue
            else:
                if _duck_count > 0:
                    _duck_count -= 1
                if _duck_count == 0 and _saved_sessions:
                    snap = dict(_saved_sessions)
                    _saved_sessions.clear()
                    try:
                        sessions = AudioUtilities.GetAllSessions()
                    except Exception:
                        sessions = []
                    for session in sessions:
                        try:
                            pid = session.ProcessId
                            if pid in snap:
                                volume = session.SimpleAudioVolume
                                if volume:
                                    volume.SetMasterVolume(snap[pid], None)
                        except Exception:
                            continue
    except Exception:
        pass
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass
def _fuzzy_find_session(sessions, query: str):
    from features.gaming import transliterate_cyrillic_to_latin
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None
    query_lower = query.lower().strip()
    query_trans = transliterate_cyrillic_to_latin(query_lower)
    best_session, best_score = (None, 0)
    for s in sessions:
        if not s.Process:
            continue
        proc = s.Process.name().lower().replace('.exe', '')
        if _fuzz:
            score = max(_fuzz.partial_ratio(query_lower, proc), _fuzz.partial_ratio(query_trans, proc), _fuzz.token_set_ratio(query_trans, proc))
        else:
            score = 100 if (query_lower in proc or query_trans in proc) else 0
        if score > best_score:
            best_score = score
            best_session = s
    return (best_session, best_score) if best_score >= 45 else (None, 0)
def set_app_volume(app_name: str, direction: str, amount: int=20) -> tuple[bool, str]:
    import pythoncom
    pythoncom.CoInitialize()
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = [s for s in AudioUtilities.GetAllSessions() if s.Process]
        session, score = _fuzzy_find_session(sessions, app_name)
        if session is None:
            return (False, f'Приложение «{app_name}» не найдено среди активных аудио-сессий.')
        vol = session.SimpleAudioVolume
        cur = vol.GetMasterVolume()
        if direction == 'up':
            new_vol = min(1.0, cur + amount / 100.0)
        elif direction == 'down':
            new_vol = max(0.0, cur - amount / 100.0)
        else:
            new_vol = max(0.0, min(1.0, amount / 100.0))
        vol.SetMasterVolume(new_vol, None)
        proc_name = session.Process.name().replace('.exe', '')
        label = int(vol.GetMasterVolume() * 100)
        return (True, f'Громкость {proc_name}: {label} процентов')
    except Exception as e:
        return (False, str(e))
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass
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
