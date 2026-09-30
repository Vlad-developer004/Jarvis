"""Periodic and pre-danger saves under Jarvis-owned names.

Uses three rotating slots (jarvis_auto_1..3) through the mod's `save` command, so
the player's own quick-save and manual slots are never overwritten. Rolling back
means loading one of these slots from the game's own load menu."""

import logging
import threading
import time

from . import commands, journal

_log = logging.getLogger(__name__)

_INTERVAL_S = 600
_EVENT_COOLDOWN_S = 90
_SLOTS = 3

_lock = threading.Lock()
_enabled = True
_last_save = 0.0
_slot = 0


def set_enabled(value: bool) -> str:
    global _enabled
    with _lock:
        _enabled = value
    return "Автосохранение включено." if value else "Автосохранение выключено."


def _save(reason: str) -> bool:
    global _last_save, _slot
    name = f"jarvis_auto_{_slot % _SLOTS + 1}"
    result = commands.execute("save", name)
    if not (result and result.get("code") == "ok"):
        _log.debug("Autosave skipped (%s): %s", reason, result)
        return False
    _slot += 1
    _last_save = time.time()
    journal.log(f"Автосохранение ({reason}): слот {name}.")
    return True


def save_now() -> str:
    return "Сохранено." if _save("по запросу") else "Сейчас сохранить нельзя."


def tick(data: dict, prev: dict) -> None:
    with _lock:
        if not _enabled:
            return
    if not data.get("_valid") or data.get("paused"):
        return

    now = time.time()
    since = now - _last_save
    danger = (
        (data.get("n_intruders", 0) > 0 and not prev.get("n_intruders", 0))
        or (data.get("any_disaster") and not prev.get("any_disaster"))
    )
    if danger and since >= _EVENT_COOLDOWN_S:
        _save("перед опасностью")
    elif since >= _INTERVAL_S:
        _save("по таймеру")
