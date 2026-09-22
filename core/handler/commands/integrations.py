from core.responses import spk

def _net_profile_status(handler, text_lower):
    from actions.network_profiles import describe_network_state
    handler.speak(describe_network_state())

def _net_profile_switch(handler, text_lower):
    from actions.network_profiles import parse_profile_target, set_active_profile
    key = parse_profile_target(text_lower)
    if not key:
        handler.speak(spk('net.ask_profile_v2'))
        handler._set_interactive('net_profile_ask', {}, timeout=20.0)
        return
    ok, msg = set_active_profile(key)
    handler.speak(msg)

def _vpn_reminder(handler, text_lower):
    from actions.network_profiles import vpn_reminder_for_active
    handler.speak(vpn_reminder_for_active())

def _health_disks(handler, text_lower):
    from actions.system_health_extra import disk_health_voice
    handler.speak(disk_health_voice())

def _calendar_next(handler, text_lower):
    from actions.calendar_ics import next_events_summary
    handler.speak(next_events_summary(None))

def _inbox_unread(handler, text_lower):
    import threading
    handler.speak("Проверяю почту...")
    def work():
        from actions.inbox_imap import unread_count_voice
        msg = unread_count_voice()
        handler.speak(msg)
    threading.Thread(target=work, daemon=True).start()

def _mail_compose(handler, text_lower):
    handler.speak(spk('mail.opening'))
    try:
        from ui import hud as _hud_mod
        _h = _hud_mod._hud
        if _h and hasattr(_h, 'root'):
            from ui.dialogs.mail_compose_dlg import open_compose_dialog
            _h.root.after(0, lambda: open_compose_dialog(_h, _h.root))
        else:
            handler.speak(spk('mail.not_loaded'))
    except Exception:
        handler.speak(spk('mail.error_v2'))

_INTEGRATIONS_ACTIONS = {
    'net_profile_status': _net_profile_status,
    'net_profile_switch': _net_profile_switch,
    'vpn_reminder': _vpn_reminder,
    'health_disks': _health_disks,
    'calendar_next': _calendar_next,
    'inbox_unread': _inbox_unread,
    'mail_compose': _mail_compose,
}

def handle_integrations(handler, cmd: str, text_lower: str) -> None:
    action = _INTEGRATIONS_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower)
