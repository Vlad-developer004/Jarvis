import threading
from core.system import app_state
def _fmt_delay(seconds: int) -> str:
    from core.nlp import format_duration_russian, get_russian_plural
    if seconds < 60:
        forms = ['секунду', 'секунды', 'секунд']
        return f'{seconds} {get_russian_plural(seconds, forms)}'
    return format_duration_russian(seconds // 60)
def handle_system(handler, cmd, text_lower, amount):
    if cmd == 'shutdown':
        from actions.system import shutdown_pc
        handler.play_response('shutdown'); shutdown_pc()
    elif cmd == 'restart':
        from actions.system import restart_pc
        handler.play_response(); restart_pc()
    elif cmd == 'dictation_on':
        from actions.dictation import start_dictation
        if start_dictation():
            app_state.dictation_mode = True; handler.play_response()
    elif cmd == 'system_cleanup':
        from actions.system import clean_system
        ok, msg = clean_system()
        if ok: handler.speak(msg)
    elif cmd == 'internet_speed':
        from actions.system import check_internet_speed
        handler.speak('Запускаю проверку скорости... Один момент.')
        threading.Thread(target=lambda: handler.speak(check_internet_speed()), daemon=True).start()
    elif cmd == 'brightness_set':
        from actions.system import change_brightness
        change_brightness('set', amount); handler.play_response()
    elif cmd == 'brightness_up':
        from actions.system import change_brightness
        change_brightness('up', amount or 20); handler.play_response()
    elif cmd == 'brightness_down':
        from actions.system import change_brightness
        change_brightness('down', amount or 20); handler.play_response()
    elif cmd == 'wifi_toggle':
        from actions.system import toggle_wifi
        enabled = not any(w in text_lower for w in ['отключи', 'выключи', 'выруби', 'офф', 'стоп'])
        if toggle_wifi(enabled): handler.play_response()
    elif cmd == 'bluetooth_toggle':
        from actions.system import toggle_bluetooth
        enabled = not any(w in text_lower for w in ['отключи', 'выключи', 'выруби', 'офф', 'стоп'])
        if toggle_bluetooth(enabled): handler.play_response()
    elif cmd == 'guard_on':
        from features.guard import start_guard
        handler.speak('Активирую режим охраны. Пожалуйста, смотрите в камеру.')
        ok, res = start_guard()
        if ok:
            handler.speak('Режим охраны включен. Я слежу за порядком, сэр.')
        else:
            handler.speak(f'Не удалось включить охрану: {res}')
    elif cmd == 'guard_off':
        from features.guard import stop_guard
        ok, res = stop_guard()
        if ok:
            handler.speak('Система охраны отключена. Вольно, сэр.')
        else:
            handler.speak('Охрана не была активна.')
    elif cmd == 'shutdown_timer':
        from core.nlp import extract_duration_seconds
        from actions.system_control import schedule_shutdown
        delay = extract_duration_seconds(text_lower)
        if delay > 0:
            schedule_shutdown(delay)
            handler.speak(f"Хорошо, компьютер выключится через {_fmt_delay(delay)}")
        else:
            handler.speak("Не удалось распознать время выключения.")
    elif cmd == 'keyboard_lock':
        from actions.system import disable_keyboards_hardware
        ok, res = disable_keyboards_hardware()
        handler.speak(res)
    elif cmd == 'keyboard_unlock':
        from actions.system import enable_keyboards_hardware
        ok, res = enable_keyboards_hardware()
        handler.speak(res)
    elif cmd == 'jarvis_exit':
        handler.speak("Завершаю работу. До встречи, сэр.")
        import os; os._exit(0)
    elif cmd == 'show_hud':
        try:
            from ui.hud import show_hud
            show_hud()
        except Exception:
            pass
    elif cmd == 'show_help':
        try:
            from ui.hud import _hud as _h
            from ui.dialogs.welcome_dlg import open_welcome
            if _h is not None:
                _h._hud_queue.put(lambda: open_welcome(_h, force=True))
        except Exception:
            pass
    elif cmd == 'restart_jarvis':
        handler.speak('Перезапускаю, сэр. Буду снова в строю через несколько секунд.')
        import time; time.sleep(1.8)
        import sys, subprocess, os as _os
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], creationflags=0x00000008)
            else:
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception:
            pass
        finally:
            _os._exit(0)
    elif cmd == 'listen_off':
        app_state.ignore_mode = True
        handler.speak('Режим тишины: команды не выполняю. Скажите «слушай меня», чтобы вернуться.')
    elif cmd == 'listen_on':
        app_state.ignore_mode = False
        handler.speak("Я снова слушаю вас, сэр.")
    elif cmd == 'economy_on':
        import subprocess
        subprocess.run(['powercfg', '/setactive', 'a1841308-3541-4fab-bc81-f71556f20b4a'], creationflags=134217728)
        handler.speak("Режим экономии энергии активирован.")
    elif cmd == 'economy_off':
        import subprocess
        subprocess.run(['powercfg', '/setactive', '381b4222-f694-41f0-9685-ff5bb260df2e'], creationflags=134217728)
        handler.speak("Режим максимальной производительности восстановлен.")
    elif cmd == 'cancel_timer':
        from actions.system_control import cancel_shutdown
        cancel_shutdown()
        handler.speak("Таймер выключения отменен.")
    elif cmd == 'reminder':
        from core.nlp import extract_duration_seconds
        from features.reminder import schedule_reminder, extract_reminder_text
        delay = extract_duration_seconds(text_lower)
        if delay <= 0:
            handler.speak("Не удалось распознать время напоминания.")
            return
        msg = extract_reminder_text(text_lower)
        hud = getattr(app_state, 'hud', None)
        schedule_reminder(delay, msg, handler.speak, hud)
        handler.speak(f"Хорошо, напомню через {_fmt_delay(delay)}.")
