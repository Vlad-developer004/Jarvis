from __future__ import annotations
from core import i18n
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
        title=i18n.tr('dialogs.commit.title'),
        header=i18n.tr('dialogs.commit.header'),
        ok_text=i18n.tr('dialogs.commit.button_commit'),
        cancel_text=i18n.tr('dialogs.commit.button_cancel'),
        placeholder="",
        width=650,
        height=340,
        hint_voice=i18n.tr('dialogs.commit.hint'),
        voice_confirm_phrases=_VOICE_COMMIT_CONFIRM,
        require_message_to_confirm=True,
    )
