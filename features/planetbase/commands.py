"""Sends commands to the Planetbase mod and turns its answer into a spoken reply.

Protocol (see mods/PlanetbaseTelemetry): a 3-line text file (id, command,
argument) is dropped next to the telemetry JSON; the mod runs it on the Unity
main thread and answers with jarvis_command_result.json."""

import json
import logging
import os
import time

from . import telemetry

_log = logging.getLogger(__name__)

_CMD_FILE = telemetry._TELEMETRY_FILE.with_name("jarvis_command.txt")
_RESULT_FILE = telemetry._TELEMETRY_FILE.with_name("jarvis_command_result.json")
_TIMEOUT = 3.0

# ModuleType class suffix -> spoken name (accusative; game names come from the
# mod's `dump_modules`, so replies match what the player sees in the game)
_NAMES = {
    "SolarPanel": "солнечную панель",
    "WindTurbine": "ветровую турбину",
    "PowerCollector": "аккумулятор",
    "WaterExtractor": "экстрактор воды",
    "WaterTank": "водохранилище",
    "OxygenGenerator": "генератор кислорода",
    "BioDome": "гидропонную ферму",
    "Storage": "склад",
    "Canteen": "столовую",
    "Bar": "бар",
    "Dorm": "общую спальню",
    "Cabin": "каюту",
    "Airlock": "воздушный шлюз",
    "MultiDome": "мультимедиа",
    "ControlCenter": "контрольный центр",
    "LandingPad": "посадочную площадку",
    "Starport": "космопорт",
    "Mine": "шахту",
    "ProcessingPlant": "перерабатывающий завод",
    "RoboticsFacility": "центр роботехники",
    "SickBay": "лазарет",
    "Lab": "лабораторию",
    "Factory": "фабрику",
    "RadioAntenna": "радиоантенну",
    "Telescope": "обсерваторию",
    "Signpost": "указатель",
    "AntiMeteorLaser": "антиметеоритный лазер",
    "LightningRod": "молниеотвод",
    "BasePad": "простую платформу",
    "Pyramid": "пирамиду",
    "Monolith": "монолит",
}


def _send(command: str, arg: str = "") -> dict | None:
    """Write a command and wait for the mod's answer. None on timeout."""
    cmd_id = int(time.time() * 1000)
    tmp = _CMD_FILE.with_suffix(".tmp")
    try:
        _RESULT_FILE.unlink(missing_ok=True)
        tmp.write_text(f"{cmd_id}\n{command}\n{arg}\n", encoding="utf-8")
        os.replace(tmp, _CMD_FILE)
    except OSError as e:
        _log.debug("Planetbase command write failed: %s", e)
        return None

    deadline = time.time() + _TIMEOUT
    while time.time() < deadline:
        try:
            result = json.loads(_RESULT_FILE.read_text(encoding="utf-8"))
            if result.get("id") == cmd_id:
                return result
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    # The mod only runs commands while the game renders (window in focus). Drop an
    # unconsumed command so it can't fire unexpectedly when the player returns.
    try:
        _CMD_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    return None


def execute(command: str, arg: str = "") -> dict | None:
    """Public wrapper for callers that need the raw result (autopilot, autosave)."""
    return _send(command, arg)


def build(module_key: str) -> str:
    """Start placing a module (the game shows the ghost). Returns the reply text."""
    name = _NAMES.get(module_key, module_key)
    result = _send("build", module_key)
    if result is None:
        return "Мод не отвечает. Проверьте, что игра запущена и мод установлен."

    code = result.get("code")
    detail = result.get("detail", "")
    if code == "started":
        return f"Выберите место: {name}."
    if code == "not_in_game":
        return "Сейчас нельзя строить: откройте колонию."
    if code == "busy":
        return "Сначала завершите текущее действие в игре."
    if code == "requires":
        need = _NAMES.get(detail, detail)
        return f"Сначала нужно построить {need}."
    if code == "disabled":
        return f"В этом сценарии {name} недоступен."
    if code == "unknown_type":
        return f"Не нашёл в игре такую постройку: {name}."
    _log.warning("Planetbase build failed: %s %s", code, detail)
    return "Не удалось начать строительство."


_last_show = ""  # last "show:<kind>" spec, repeated by "next one"

_NO_MOD = "Мод не отвечает. Проверьте, что игра запущена и мод установлен."

_SHOW_NONE = {
    "sick": "Больных нет.",
    "ko": "Никто не без сознания.",
    "intruders": "Нарушителей не вижу.",
    "guards": "Охраны нет.",
    "damaged": "Серьёзных повреждений нет.",
    "unpowered": "Обесточенных зданий нет.",
    "unoperated": "Все здания обслуживаются.",
}

_LANDING_WHO = {
    "colonists": "колонистов",
    "visitors": "гостей",
    "merchants": "торговцев",
    "all": "всех кораблей",
}


def _reply_time(cmd: str, detail: str) -> str:
    if cmd == "pause":
        return "Пауза."
    if cmd == "unpause":
        return "Продолжаем."
    if detail == "paused":
        return "Пауза."
    return f"Скорость {detail}."


def run(spec: str) -> str:
    """Execute 'cmd[:arg]' (the part after 'cmd:' in a profile's telemetry_action)
    and return the reply text."""
    global _last_show
    if spec == "show_next":
        if not _last_show:
            return "Сначала попросите что-нибудь показать."
        spec = _last_show
    cmd, _, arg = spec.partition(":")
    if cmd == "show":
        _last_show = spec
    result = _send(cmd, arg)
    if result is None:
        return _NO_MOD

    code = result.get("code")
    detail = result.get("detail", "")
    if code == "not_in_game":
        return "Сейчас недоступно: откройте колонию."
    if code == "busy":
        return "Сначала завершите текущее действие в игре."
    if code == "unknown_command" or code == "bad_argument":
        _log.warning("Planetbase command rejected: %s %s (%s)", cmd, arg, code)
        return "Команда не поддерживается модом. Обновите мод."
    if code == "error":
        _log.warning("Planetbase command failed: %s %s: %s", cmd, arg, detail)
        return "Не удалось выполнить команду."

    if cmd in ("pause", "unpause", "speed_up", "speed_down", "speed_normal", "speed"):
        return _reply_time(cmd, detail)

    if cmd == "landing":
        who, _, state = arg.partition(":")
        verb = "Разрешена" if state == "on" else "Запрещена"
        return f"{verb} посадка {_LANDING_WHO.get(who, who)}."

    if cmd == "priority":
        if code == "nothing_selected":
            return "Ничего не выбрано."
        if code == "none":
            return "Таких построек нет."
        return "Приоритет включён." if arg.endswith("on") else "Приоритет снят."

    if cmd == "show":
        kind, _, key = arg.partition(":")
        if code == "none":
            if kind == "module":
                return f"Не нашёл: {_NAMES.get(key, key)}."
            return _SHOW_NONE.get(kind, "Ничего не найдено.")
        total = detail.split("/")[-1]
        return f"Показываю. Найдено: {total}." if total != "1" else "Показываю."

    return "Готово."
