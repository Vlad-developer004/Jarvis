import threading
from actions.bluetooth import bt_connect, bt_disconnect, bt_list, _bt_handle_result
from actions.session_ghost import save_session, restore_session, delete_session
from actions.command_vault import save_command, get_command, delete_command
from actions.system import change_keyboard_layout, press_enter
def handle_utils(handler, cmd, text_lower):
    if cmd == 'bt_connect':
        q = text_lower.replace('подключи', '').replace('блютуз', '').strip()
        if not q:
            names = bt_list()
            if names: handler.speak('Доступные устройства: ' + ', '.join(names[:5]))
            else: handler.speak('Bluetooth устройств не найдено.')
        else:
            def _connect_task():
                ok, res = bt_connect(q)
                _bt_handle_result(ok, res, 'connect', handler.speak, handler=handler)
            threading.Thread(target=_connect_task, daemon=True).start()
    elif cmd == 'bt_disconnect':
        q = text_lower.replace('отключи', '').strip()
        if q:
            def _disconnect_task():
                ok, res = bt_disconnect(q)
                _bt_handle_result(ok, res, 'disconnect', handler.speak, handler=handler)
            threading.Thread(target=_disconnect_task, daemon=True).start()
    elif cmd == 'bt_list':
        names = bt_list()
        handler.speak('Спаренные устройства: ' + ', '.join(names) if names else 'Устройств не найдено.')
    elif cmd == 'session_save':
        name = text_lower
        for w in ['сохрани', 'запомни', 'сессию', 'рабочее']:
            name = name.replace(w, '')
        name = name.strip() or 'default'
        threading.Thread(target=save_session, args=(name, handler.speak, handler.play_response), daemon=True).start()
    elif cmd == 'session_restore':
        name = text_lower
        for w in ['восстанови', 'востанови', 'возобнови', 'сессию', 'место']:
            name = name.replace(w, '')
        name = name.strip() or 'default'
        threading.Thread(target=restore_session, args=(name, handler.play_response), daemon=True).start()
    elif cmd == 'session_delete':
        name = text_lower
        for w in ['удали', 'сотри', 'сессию']:
            name = name.replace(w, '')
        name = name.strip() or 'default'
        if delete_session(name): handler.play_response()
    elif cmd == 'command_save':
        name = text_lower.replace('запомни', '').replace('команду', '').replace('как', '').strip()
        if name and save_command(name): handler.play_response()
    elif cmd == 'command_get':
        name = text_lower.replace('выполни', '').replace('команду', '').strip()
        if get_command(name): handler.play_response()
    elif cmd == 'command_delete':
        name = text_lower.replace('удали', '').replace('команду', '').replace('сотри', '').strip()
        if delete_command(name): handler.play_response()
    elif cmd == 'git_commit':
        from actions.git_commit import git_commit_push
        import win32gui
        fg_hwnd = win32gui.GetForegroundWindow()
        def _show_and_commit(hwnd=fg_hwnd):
            from ui.dialogs.commit_dlg import ask_commit_message
            msg_input = ask_commit_message()
            if msg_input is None:
                handler.speak('Коммит отменён.')
                return
            ok, msg = git_commit_push(active_hwnd=hwnd, custom_msg=msg_input)
            handler.speak(msg)
            if ok:
                handler.play_response()
        threading.Thread(target=_show_and_commit, daemon=True).start()
    elif cmd == 'today_summary':
        def _run():
            from features.morning_briefing import speak_daily_summary
            speak_daily_summary(handler)
        threading.Thread(target=_run, daemon=True).start()
    elif cmd == 'change_layout':
        target = 'русский'
        if any(x in text_lower for x in ['англ', 'ингл', 'engl']): target = 'английский'
        elif any(x in text_lower for x in ['укр', 'мов']): target = 'украинский'
        elif any(x in text_lower for x in ['нем', 'герм']): target = 'немецкий'
        if change_keyboard_layout(target)[0]: handler.play_response()
    elif cmd == 'press_enter':
        if press_enter()[0]: handler.play_response()
    elif cmd == 'reminder':
        from core.nlp import extract_duration_seconds
        import re
        delay = extract_duration_seconds(text_lower)
        if delay > 0:
            msg = text_lower
            msg = re.sub(r'.*напомни\s+(?:мне\s+)?(через\s+)?\d+\s+(?:минут|час|секунд)\w*', '', msg).strip()
            if msg == text_lower or len(msg) < 3:
                 msg = re.sub(r'.*напомни\s+(?:мне\s+)?(через\s+)?\w+\s+(?:минут|час|секунд)\w*', '', text_lower).strip()
            if not msg or len(msg) < 2:
                msg = "Вы просили напомнить о чем-то, сэр."
            def _remind():
                handler.speak(f"Сэр, вы просили напомнить: {msg}")
            threading.Timer(delay, _remind).start()
            handler.play_response()
            from core.nlp import format_duration_russian
            handler.speak(f"Хорошо, напомню через {format_duration_russian(delay // 60)}")
        else:
            handler.speak("Я не понял, через какое время нужно напомнить.")
    elif cmd == 'bluetooth_toggle':
        from actions.system_control import toggle_bluetooth
        enabled = 'выключ' not in text_lower and 'отключ' not in text_lower
        toggle_bluetooth(enabled)
        handler.play_response()
