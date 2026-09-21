import threading
from actions.bluetooth import bt_connect, bt_disconnect, bt_list, _bt_handle_result
from actions.session_ghost import save_session, restore_session, delete_session
from actions.command_vault import save_command, get_command, delete_command
from actions.system import change_keyboard_layout, press_enter
from core.responses import spk

def _bt_connect(handler, text_lower):
    q = text_lower.replace('подключи', '').replace('блютуз', '').strip()
    if not q:
        names = bt_list()
        if names: handler.speak(spk('bt.devices_v2', names=', '.join(names[:5])))
        else: handler.speak(spk('bt.none'))
    else:
        def _connect_task():
            ok, res = bt_connect(q)
            _bt_handle_result(ok, res, 'connect', handler.speak, handler=handler)
        threading.Thread(target=_connect_task, daemon=True).start()

def _bt_disconnect(handler, text_lower):
    q = text_lower.replace('отключи', '').strip()
    if q:
        def _disconnect_task():
            ok, res = bt_disconnect(q)
            _bt_handle_result(ok, res, 'disconnect', handler.speak, handler=handler)
        threading.Thread(target=_disconnect_task, daemon=True).start()

def _bt_list(handler, text_lower):
    names = bt_list()
    handler.speak(spk('bt.paired_v2', names=', '.join(names)) if names else handler.speak(spk('bt.none_paired')))

def _session_save(handler, text_lower):
    name = text_lower
    for w in ['сохрани', 'запомни', 'сессию', 'рабочее']:
        name = name.replace(w, '')
    name = name.strip() or 'default'
    threading.Thread(target=save_session, args=(name, handler.speak, handler.play_response), daemon=True).start()

def _session_restore(handler, text_lower):
    name = text_lower
    for w in ['восстанови', 'востанови', 'возобнови', 'сессию', 'место']:
        name = name.replace(w, '')
    name = name.strip() or 'default'
    threading.Thread(target=restore_session, args=(name, handler.play_response), daemon=True).start()

def _session_delete(handler, text_lower):
    name = text_lower
    for w in ['удали', 'сотри', 'сессию']:
        name = name.replace(w, '')
    name = name.strip() or 'default'
    if delete_session(name): handler.play_response()

def _command_save(handler, text_lower):
    name = text_lower.replace('запомни', '').replace('команду', '').replace('как', '').strip()
    if name and save_command(name): handler.play_response()

def _command_get(handler, text_lower):
    name = text_lower.replace('выполни', '').replace('команду', '').strip()
    if get_command(name): handler.play_response()

def _command_delete(handler, text_lower):
    from ui.dialogs.name_dlg import ask_text
    name = text_lower.replace('удали', '').replace('команду', '').replace('сотри', '').strip()
    if not name:
        name = ask_text(
            title="УДАЛЕНИЕ МАКРОСА",
            header="КАКУЮ КОМАНДУ УДАЛИТЬ?",
            ok_text="УДАЛИТЬ",
            placeholder="Назовите имя макроса..."
        )
    if name:
        if delete_command(name): handler.play_response()

def _git_commit(handler, text_lower):
    from actions.git_commit import detect_repo_and_status, git_commit_push
    import win32gui
    fg_hwnd = win32gui.GetForegroundWindow()

    def _show_and_commit(hwnd=fg_hwnd):
        # 1. Detect environment
        repo, status = detect_repo_and_status(hwnd)
        if not repo:
            handler.speak(spk('git.no_repo'))
            return
        if not status:
            handler.speak(spk('git.nothing'))
            return

        # 2. Show dialog with file selection and options
        from ui.dialogs.git_stage_dlg import ask_git_stage
        dlg_res = ask_git_stage(repo, status)

        if dlg_res is None:
            handler.speak(spk('git.cancelled'))
            return

        if not dlg_res['files']:
            handler.speak(spk('git.no_files'))
            return

        # 3. Perform commit with options
        all_selected = (len(dlg_res['files']) == len(status))
        to_stage = dlg_res['files'] if not all_selected else None

        ok, msg = git_commit_push(
            active_hwnd=hwnd,
            custom_msg=dlg_res['message'],
            files_to_add=to_stage,
            target_branch=dlg_res['branch'],
            push_enabled=dlg_res['push'],
            force_push=dlg_res['force'],
            set_upstream=dlg_res['upstream']
        )
        handler.speak(msg)
        if ok:
            handler.play_response()
            if dlg_res.get('open_pr'):
                from actions.git_commit import open_pull_request_url
                open_pull_request_url(repo, dlg_res['branch'], dlg_res['pr_title'])

    threading.Thread(target=_show_and_commit, daemon=True).start()

def _today_summary(handler, text_lower):
    def _run():
        from features.morning_briefing import speak_daily_summary
        speak_daily_summary(handler)
    threading.Thread(target=_run, daemon=True).start()

def _change_layout(handler, text_lower):
    target = 'русский'
    if any(x in text_lower for x in ['англ', 'ингл', 'engl']): target = 'английский'
    elif any(x in text_lower for x in ['укр', 'мов']): target = 'украинский'
    elif any(x in text_lower for x in ['нем', 'герм']): target = 'немецкий'
    if change_keyboard_layout(target)[0]: handler.play_response()

def _press_enter(handler, text_lower):
    if press_enter()[0]: handler.play_response()

_UTILS_EXACT = {
    'bt_connect': _bt_connect,
    'bt_disconnect': _bt_disconnect,
    'bt_list': _bt_list,
    'session_save': _session_save,
    'session_restore': _session_restore,
    'session_delete': _session_delete,
    'command_save': _command_save,
    'command_get': _command_get,
    'command_delete': _command_delete,
    'git_commit': _git_commit,
    'today_summary': _today_summary,
    'change_layout': _change_layout,
    'press_enter': _press_enter,
}

def handle_utils(handler, cmd, text_lower):
    action = _UTILS_EXACT.get(cmd)
    if action:
        action(handler, text_lower)
