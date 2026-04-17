def handle_integrations(handler, cmd: str, text_lower: str) -> None:
    if cmd == 'net_profile_status':
        from actions.network_profiles import describe_network_state
        handler.speak(describe_network_state())
    elif cmd == 'net_profile_switch':
        from actions.network_profiles import parse_profile_target, set_active_profile
        key = parse_profile_target(text_lower)
        if not key:
            handler.speak('Скажите, например: переключи сеть на дом, на офис или на публичную сеть.')
            return
        ok, msg = set_active_profile(key)
        handler.speak(msg)
    elif cmd == 'vpn_reminder':
        from actions.network_profiles import vpn_reminder_for_active
        handler.speak(vpn_reminder_for_active())
    elif cmd == 'health_disks':
        from actions.system_health_extra import disk_health_voice
        handler.speak(disk_health_voice())
    elif cmd == 'calendar_next':
        from actions.calendar_ics import next_events_summary
        handler.speak(next_events_summary(None))
    elif cmd == 'inbox_unread':
        from actions.inbox_imap import unread_count_voice
        handler.speak(unread_count_voice())
    elif cmd == 'mail_compose':
        handler.speak('Открываю окно для нового письма.')
        try:
            from ui import hud as _hud_mod
            _h = _hud_mod._hud
            if _h and hasattr(_h, 'root'):
                from ui.dialogs.mail_dlg import open_compose_dialog
                _h.root.after(0, lambda: open_compose_dialog(_h, _h.root))
            else:
                handler.speak('Интерфейс ещё не загружен.')
        except Exception:
            handler.speak('Не удалось открыть окно. Попробуйте кнопку «Почта» в интерфейсе.')
