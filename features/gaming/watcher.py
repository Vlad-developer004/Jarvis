import threading
import time
from typing import Optional
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('gaming')
_GAME_EXE_MAP: dict[str, tuple[str, str, str]] = {
    'eurotrucks2.exe': ('euro_truck_simulator_2', 'Евро Трак Симулятор два', 'евро трак'),
    'euro_truck_simulator_2.exe': ('euro_truck_simulator_2', 'Евро Трак Симулятор два', 'евро трак'),
    'farmingsimulator22.exe': ('farming_simulator_22', 'Фарминг Симулятор двадцать два', 'фарминг'),
    'farmingsimulator25.exe': ('farming_simulator_22', 'Фарминг Симулятор двадцать пять', 'фарминг'),
    'fs22.exe': ('farming_simulator_22', 'Фарминг Симулятор двадцать два', 'фарминг'),
    'fs25.exe': ('farming_simulator_22', 'Фарминг Симулятор двадцать пять', 'фарминг'),
    'hogwartslegacy.exe': ('hogwarts_legacy', 'Хогвартс Легаси', 'хогвартс'),
    'hogwarts.exe': ('hogwarts_legacy', 'Хогвартс Легаси', 'хогвартс'),
    'planetbase.exe': ('planetbase', 'Планетбейз', 'планетбейз'),
}
_QUICK_ALIAS_MAP: dict[str, str] = {
    'евро трак симулятор':  'euro_truck_simulator_2',
    'евро трак':            'euro_truck_simulator_2',
    'euro truck':           'euro_truck_simulator_2',
    'евротрак':             'euro_truck_simulator_2',
    'truck simulator':      'euro_truck_simulator_2',
    'трак симулятор':       'euro_truck_simulator_2',
    'euro_truck':           'euro_truck_simulator_2',
    'ets2':                 'euro_truck_simulator_2',
    ' ets ':                'euro_truck_simulator_2',
    'etс':                  'euro_truck_simulator_2',
    'ets':                  'euro_truck_simulator_2',
    'етс':                  'euro_truck_simulator_2',
    'евро':                 'euro_truck_simulator_2',
    'трак':                 'euro_truck_simulator_2',
    'фарминг симулятор':    'farming_simulator_22',
    'farming simulator':    'farming_simulator_22',
    'фарминг':              'farming_simulator_22',
    'farming':              'farming_simulator_22',
    'ферму':                'farming_simulator_22',
    'ферма':                'farming_simulator_22',
    'фс22':                 'farming_simulator_22',
    'фс25':                 'farming_simulator_22',
    'fs22':                 'farming_simulator_22',
    'fs25':                 'farming_simulator_22',
    ' фс ':                 'farming_simulator_22',
    'фс':                   'farming_simulator_22',
    'хогвартс легаси':      'hogwarts_legacy',
    'hogwarts legacy':      'hogwarts_legacy',
    'хогвартс':             'hogwarts_legacy',
    'hogwarts':             'hogwarts_legacy',
    'хог':                  'hogwarts_legacy',
    'планетбейз':           'planetbase',
    'planetbase':           'planetbase',
    'планета':              'planetbase',
    'база на планете':      'planetbase',
}
_suggested_profiles: set[str] = set()
_suggestion_lock = threading.Lock()
_watcher_stop = threading.Event()
def is_profile_installed(profile_stem: str) -> bool:
    try:
        from core.extensions import ExtensionManager
        ext = ExtensionManager()
        for e in ext.list_installed():
            if e.get('file', '') == f'{profile_stem}.json':
                return True
    except Exception:
        pass
    from config_pack.config import get_data_dir
    from pathlib import Path
    return (Path(get_data_dir('game_profiles')) / f'{profile_stem}.json').exists()
def start_game_watcher(handler=None):
    def _watch():
        from core.system import get_foreground_process_name, app_state
        while not _watcher_stop.is_set():
            fg_name = get_foreground_process_name()
            
            # Continuous tracking of detected game
            if fg_name in _GAME_EXE_MAP:
                profile_stem = _GAME_EXE_MAP[fg_name][0]
                app_state.detected_game = profile_stem
                app_state.detected_exe = fg_name
            else:
                app_state.detected_game = ''
                app_state.detected_exe = ''

            if app_state.game_mode:
                if _watcher_stop.wait(timeout=5): break
                continue
                
            if not fg_name:
                if _watcher_stop.wait(timeout=3): break
                continue
                
            if fg_name in _GAME_EXE_MAP:
                game = _GAME_EXE_MAP[fg_name]
                profile_stem, display_name, alias = game
                
                # Suggestions logic (only once per game session)
                with _suggestion_lock:
                    is_new = profile_stem not in _suggested_profiles
                
                if is_new and is_profile_installed(profile_stem):
                    with _suggestion_lock:
                        _suggested_profiles.add(profile_stem)
                    try:
                        if handler:
                            handler._set_interactive('game_watcher_suggest', {'profile': profile_stem, 'name': display_name})
                            handler.asr.reset()
                            handler.speak(f'Сэр, я обнаружил, что вы запустили {display_name}. Желаете активировать профиль?')
                        else:
                            from core.speech import speak
                            speak(f'Обнаружена {display_name}. Желаете включить голосовое управление?')
                    except Exception as _e:
                        _log.warning('Game detection notify failed: %s', _e)

                    if profile_stem == 'euro_truck_simulator_2':
                        try:
                            from actions.ets2_telemetry import start_background_poll
                            start_background_poll()
                        except Exception as _e:
                            _log.warning('ETS2 telemetry poll start failed: %s', _e)
            
            if _watcher_stop.wait(timeout=3): break
    threading.Thread(target=_watch, daemon=True, name="Game-Watcher").start()
