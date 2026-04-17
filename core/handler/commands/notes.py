from actions.notes import save_note, set_reminder, cancel_reminders
from core.nlp import extract_duration_seconds
def handle_notes(handler, cmd, text_lower, amount):
    if cmd == 'note_save':
        note = text_lower.replace('запиши', '').replace('запомни', '').replace('заметку', '').replace('идею', '').strip()
        if note:
            if save_note(note): handler.play_response()
        else: handler.speak('Сэр, что именно мне записать?')
    elif cmd == 'reminder':
        sec = extract_duration_seconds(text_lower)
        msg = text_lower.replace('напомни', '').replace('через', '').strip()
        if set_reminder(sec, msg): handler.play_response()
    elif cmd == 'cancel_reminder':
        if cancel_reminders(): handler.play_response()
