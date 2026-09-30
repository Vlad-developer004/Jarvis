"""Game knowledge for the chat LLM while a Planetbase session is active.

Module data comes from the game itself (mod command `dump_modules` writes
jarvis_modules.json), never from the model's memory, so answers about costs and
requirements match the installed game version."""

import json
import logging
import threading
import time

from . import advisor, commands, planet, telemetry

_log = logging.getLogger(__name__)

_MODULES_FILE = telemetry._TELEMETRY_FILE.with_name("jarvis_modules.json")

_lock = threading.Lock()
_modules_text = ""
_refresh_started = False


def _format_modules(rows: list[dict]) -> str:
    lines = []
    for m in rows:
        cost = ", ".join(f"{k} {v}" for k, v in (m.get("cost") or {}).items()) or "нет данных"
        req = m.get("requires")
        size = (f"{m['min_size']}-{m['max_size']}" if m.get("min_size") != m.get("max_size")
                else str(m.get("max_size")))
        line = (f"{m.get('key')} ({m.get('name')}): "
                f"{'наружный' if m.get('exterior') else 'внутренний'}, размер {size}, "
                f"стоимость {cost}")
        if req:
            line += f", требует {req}"
        if m.get("max_users"):
            line += f", пользователей {m['max_users']}"
        lines.append(line)
    return "\n".join(lines)


def refresh() -> bool:
    """Ask the mod to dump module data and load it. Blocks up to a few seconds."""
    global _modules_text
    result = commands.execute("dump_modules")
    if not (result and result.get("code") == "ok"):
        return False
    try:
        rows = json.loads(_MODULES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _log.debug("Planetbase modules file unreadable: %s", e)
        return False
    with _lock:
        _modules_text = _format_modules(rows)
    _log.info("Planetbase knowledge loaded: %d module types", len(rows))
    return True


def refresh_async() -> None:
    """Retry in the background until the game is in a colony and answers."""
    global _refresh_started
    with _lock:
        if _refresh_started:
            return
        _refresh_started = True

    def _run():
        global _refresh_started
        for _ in range(60):  # ~10 minutes
            if telemetry.is_valid() and refresh():
                return
            time.sleep(10)
        with _lock:
            _refresh_started = False

    threading.Thread(target=_run, daemon=True, name="PBKnowledge").start()


def _snapshot(data: dict) -> str:
    if not data.get("_valid"):
        return ""
    return (
        f"{planet.report(data)} "
        f"Колонистов {data.get('colonists', 0)}, энергия {data.get('power_pct', 0)}%, "
        f"вода {data.get('water_pct', 0)}%, генерация кислорода {data.get('oxygen_gen', 0)}, "
        f"больных {data.get('n_sick', 0)}, нарушителей {data.get('n_intruders', 0)}, "
        f"код тревоги {data.get('alert_state', -1)} (0 зелёный, 1 жёлтый, 2 красный)."
    )


def prompt_context() -> str:
    """Extra system-prompt text; empty unless a Planetbase session is active."""
    try:
        from core.system.state import app_state
        if not app_state.game_mode or 'planetbase' not in (app_state.game_profile or '').lower():
            return ""
    except Exception:
        return ""

    data = telemetry.get()
    parts = ["\nКонтекст: пользователь играет в Planetbase. Отвечай по игре, опираясь на данные ниже. "
             "Если данных нет — так и скажи, числа не выдумывай."]
    snap = _snapshot(data)
    if snap:
        parts.append("Состояние колонии: " + snap)
        top = advisor.collect(data)[:3]
        if top:
            parts.append("Текущие проблемы: " + " ".join(a.text for a in top))
    with _lock:
        modules = _modules_text
    if modules:
        parts.append("Постройки игры (из данных игры):\n" + modules)
    return "\n".join(parts)
