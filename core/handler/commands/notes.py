from actions.notes import save_note, cancel_reminders
from core.responses import spk
from core.safe import swallow as _swallow
def handle_notes(handler, cmd, text_lower, amount):
    if cmd == 'note_save':
        note = text_lower.replace('запиши', '').replace('запомни', '').replace('заметку', '').replace('идею', '').strip()
        if note:
            ok, msg = save_note(note)
            if ok:
                handler.play_response()
            else:
                handler.speak(spk('notes.save_error'))
        else:
            handler.speak(spk('notes.ask'))
            handler._set_interactive('note_ask', {}, timeout=30.0)
    elif cmd == 'cancel_reminder':
        ok, msg = cancel_reminders()
        if ok:
            handler.play_response()
        else:
            handler.speak(msg)
