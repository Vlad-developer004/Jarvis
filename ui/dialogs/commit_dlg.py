from __future__ import annotations
from ui.dialogs.name_dlg import ask_text
_VOICE_COMMIT_CONFIRM: tuple[str, ...] = (
    "коммит",
    "commit",
    "закоммить",
    "отправь",
    "залей",
    "пуш",
    "push",
    "подтверди",
    "готово",
    "создай",
    "сделай",
    "да",
    "окей",
    "okay",
    "ok",
)
def ask_commit_message() -> str | None:
    return ask_text(
        title="GIT COMMIT — J.A.R.V.I.S.",
        header="⬡  GIT COMMIT — СООБЩЕНИЕ",
        ok_text="КОММИТ",
        cancel_text="ОТМЕНА",
        placeholder="",
        width=650,
        height=340,
        hint_voice="Голосом: «коммит» / «отмена»  ·  Enter / Esc",
        voice_confirm_phrases=_VOICE_COMMIT_CONFIRM,
        require_message_to_confirm=True,
    )
