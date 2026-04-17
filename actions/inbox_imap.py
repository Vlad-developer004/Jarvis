from __future__ import annotations
from actions.mail_client import unread_count as _unread_count
def unread_count_voice() -> str:
    ok, msg = _unread_count()
    return msg
