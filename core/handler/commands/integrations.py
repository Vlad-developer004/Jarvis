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

def _calendar_add(handler, text_lower):
    """"Добавь в календарь завтра в 15:00 встреча с Аней": the phrase is parsed by actions/calendar_quick.py, the event goes to the user's own events."""
    from actions import calendar_hub, calendar_quick
    q = calendar_quick.parse_phrase(calendar_quick.voice_phrase(text_lower))
    if not q['title']:
        handler.speak('Не расслышал название. Скажите, например: добавь в календарь завтра в 15:00 встреча с Аней.')
        return
    if not q['date']:
        handler.speak(f'Когда это будет? Скажите, например: добавь в календарь завтра в 15:00 {q["title"].lower()}.')
        return
    try:
        calendar_hub.add_local({'title': q['title'], 'date': q['date'], 'time': q['time'], 'end_time': q['end_time'], 'all_day': not q['time'], 'repeat': q['repeat'], 'weekdays': q['weekdays']})
    except calendar_hub.CalendarError:
        handler.speak('Не получилось добавить событие. Проверьте дату и время.')
        return
    handler.speak(f'Добавил в календарь: {q["title"]}, {calendar_quick.spoken_when(q["date"], q["time"], q["repeat"])}.')

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
        from ui_next import host
        if not host.open_mail_compose():
            handler.speak(spk('mail.not_loaded'))
    except Exception:
        handler.speak(spk('mail.error_v2'))

_INTEGRATIONS_ACTIONS = {
    'net_profile_status': _net_profile_status,
    'net_profile_switch': _net_profile_switch,
    'vpn_reminder': _vpn_reminder,
    'health_disks': _health_disks,
    'calendar_next': _calendar_next,
    'calendar_add': _calendar_add,
    'inbox_unread': _inbox_unread,
    'mail_compose': _mail_compose,
}

def handle_integrations(handler, cmd: str, text_lower: str) -> None:
    action = _INTEGRATIONS_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower)
