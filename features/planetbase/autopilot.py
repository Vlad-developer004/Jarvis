"""Opt-in autopilot for the two situations where seconds matter.

- Intruders appear: red alert and no colonist landings; reverted when they are gone.
- A disaster starts while the game runs fast: back to normal speed; the previous
  speed is restored when it ends.

Only changes Jarvis itself made are reverted, so a manual override is never undone.
Disabled by default; toggled by voice."""

import logging
import threading

from . import commands, journal

_log = logging.getLogger(__name__)

_lock = threading.Lock()
_enabled = False
_red_by_us = False
_landing_closed_by_us = False
_scale_before: float | None = None


def set_enabled(value: bool) -> str:
    global _enabled
    with _lock:
        _enabled = value
    journal.log("Автопилот включён." if value else "Автопилот выключен.")
    if value:
        return ("Автопилот включён. При вторжении включу красный код и закрою посадку колонистов, "
                "при катастрофе сброшу скорость.")
    return "Автопилот выключен."


def status() -> str:
    with _lock:
        return "Автопилот включён." if _enabled else "Автопилот выключен."


def _say(text: str) -> None:
    journal.log(text)
    try:
        from core.speech.tts import speak
        speak(text)
    except Exception as e:
        _log.debug("Autopilot TTS error: %s", e)


def _ok(cmd: str, arg: str = "") -> bool:
    result = commands.execute(cmd, arg)
    return bool(result and result.get("code") == "ok")


def tick(data: dict, prev: dict) -> None:
    """Called on every monitor tick with the current and previous snapshots."""
    global _red_by_us, _landing_closed_by_us, _scale_before
    with _lock:
        if not _enabled:
            return
    if not data.get("_valid") or not prev.get("_valid"):
        return

    intruders = data.get("n_intruders", 0) > 0
    was_intruders = prev.get("n_intruders", 0) > 0

    if intruders and not was_intruders:
        did = []
        if data.get("alert_state", 0) != 2 and _ok("alert", "red"):
            _red_by_us = True
            did.append("красный код")
        if data.get("land_colonists", True) and _ok("landing", "colonists:off"):
            _landing_closed_by_us = True
            did.append("посадка колонистов закрыта")
        if did:
            _say("Автопилот: вторжение. " + ", ".join(did).capitalize() + ".")
    elif was_intruders and not intruders:
        did = []
        if _red_by_us and _ok("alert", "green"):
            did.append("зелёный код")
        if _landing_closed_by_us and _ok("landing", "colonists:on"):
            did.append("посадка колонистов открыта")
        _red_by_us = False
        _landing_closed_by_us = False
        if did:
            _say("Автопилот: нарушители устранены. " + ", ".join(did).capitalize() + ".")

    disaster = bool(data.get("any_disaster"))
    was_disaster = bool(prev.get("any_disaster"))
    scale = float(data.get("time_scale", 1.0) or 1.0)

    if disaster and not was_disaster and scale > 1.05 and _scale_before is None:
        if _ok("speed_normal"):
            _scale_before = scale
            _say("Автопилот: катастрофа, скорость сброшена до обычной.")
    elif was_disaster and not disaster and _scale_before is not None:
        target = _scale_before
        _scale_before = None
        if _ok("speed", f"{target:.1f}"):
            _say("Автопилот: катастрофа закончилась, скорость возвращена.")
