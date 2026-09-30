"""Glue for the Planetbase helpers: per-tick hooks and voice-action dispatch.

Kept out of monitor.py (already at the project's file-size limit)."""

import logging
import time

from . import advisor, autopilot, autosave, history, journal, knowledge, planet, telemetry

_log = logging.getLogger(__name__)

_prev: dict = {}


def start() -> None:
    """Reset per-session state; called when the monitor starts."""
    global _prev
    _prev = {}
    history.reset()
    journal.reset()
    autosave._last_save = time.time()  # first save one interval after start
    knowledge.refresh_async()


def tick(data: dict) -> None:
    """Called by the monitor on every telemetry tick."""
    global _prev
    if data.get("_stale"):
        return  # game not rendering (minimised): nothing is advancing, don't feed trends
    history.add(data)
    if _prev:
        autopilot.tick(data, _prev)
        autosave.tick(data, _prev)
    _prev = dict(data)


def _with_data(fn) -> str:
    data = telemetry.get()
    if not data.get("_valid"):
        return "Телеметрия недоступна. Убедитесь что игра запущена."
    return fn(data)


def census(data: dict) -> str:
    """Spoken breakdown of the colony by specialty, plus bots and unhappy colonists."""
    if not data.get("_valid"):
        return "Телеметрия недоступна. Убедитесь что игра запущена."
    colonists = int(data.get("colonists", 0) or 0)
    parts = [
        f"колонистов {colonists}",
        f"рабочих {data.get('n_workers', 0)}",
        f"биологов {data.get('n_biologists', 0)}",
        f"инженеров {data.get('n_engineers', 0)}",
        f"медиков {data.get('n_medics', 0)}",
        f"охраны {data.get('n_guards', 0)}",
        f"роботов {data.get('n_bots', 0)}",
    ]
    low = int(data.get("n_low_status", 0) or 0)
    if colonists and low:
        parts.append(f"с плохим состоянием {low}, это {round(100 * low / colonists)} процентов")
    if data.get("n_sick", 0):
        parts.append(f"больных {data.get('n_sick')}")
    return "В колонии: " + ", ".join(parts) + "."


def handle(action: str) -> str | None:
    """Reply text for a voice action, or None when the action isn't ours."""
    if action == "advise":
        return advisor.advise(telemetry.get())
    if action == "advisor_build":
        return advisor.build_pending()
    if action == "forecast":
        return _with_data(lambda d: history.forecast_report())
    if action == "census":
        return census(telemetry.get())
    if action == "planet_risks":
        return planet.report(telemetry.get())
    if action == "journal":
        return journal.summary()
    if action == "autopilot_on":
        return autopilot.set_enabled(True)
    if action == "autopilot_off":
        return autopilot.set_enabled(False)
    if action == "autopilot_status":
        return autopilot.status()
    if action == "autosave_on":
        return autosave.set_enabled(True)
    if action == "autosave_off":
        return autosave.set_enabled(False)
    if action == "autosave_now":
        return autosave.save_now()
    return None
