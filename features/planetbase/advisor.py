"""Rule-based colony advisor: turns telemetry + forecasts into ranked advice.

Deliberately not LLM-driven: advice must be fast and traceable to real numbers.
The top buildable advice is remembered so "build the recommended one" can start
placement without naming the module."""

import threading
from dataclasses import dataclass

from . import history, planet

_lock = threading.Lock()
_pending_build: str | None = None

_ETA_URGENT_MIN = 10.0
_MAX_SPOKEN = 3
_ORDINALS = ("Первое", "Второе", "Третье")


@dataclass
class Advice:
    priority: int
    text: str
    build: str | None = None


def collect(data: dict) -> list[Advice]:
    """All applicable advice, most urgent first."""
    out: list[Advice] = []
    colonists = int(data.get("colonists", 0) or 0)

    # Security first: it can end the colony fastest.
    if data.get("n_intruders", 0) > 0:
        text = "На базе нарушители, включите красный код."
        if data.get("n_guards", 0) == 0:
            text = "На базе нарушители, а охраны нет. Красный код и держите колонистов внутри."
        out.append(Advice(95, text))
    elif data.get("any_disaster") and data.get("alert_state", -1) == 0:
        out.append(Advice(90, "Идёт катастрофа, а код тревоги зелёный. Включите жёлтый, чтобы колонисты ушли внутрь."))

    # Oxygen
    oxygen = int(data.get("oxygen_gen", 0) or 0)
    if oxygen > 0 and colonists > oxygen:
        out.append(Advice(100, f"Кислорода не хватает: {colonists} колонистов на {oxygen} единиц генерации. "
                               "Постройте генератор кислорода.", "OxygenGenerator"))
    elif oxygen > 0 and oxygen - colonists < 10:
        out.append(Advice(60, "Запас кислорода мал. Перед следующим кораблём колонистов постройте генератор.",
                          "OxygenGenerator"))

    # Water
    water_eta = history.eta_minutes("water_storage")
    if water_eta is not None and water_eta < _ETA_URGENT_MIN:
        out.append(Advice(90, f"Воды хватит примерно на {int(round(water_eta))} минут. Постройте экстрактор воды.",
                          "WaterExtractor"))
    elif float(data.get("water_balance", 0) or 0) < 0 and float(data.get("water_capacity", 0) or 0) > 0:
        out.append(Advice(70, "Водный баланс отрицательный: воды расходуется больше, чем добывается. "
                              "Нужен ещё экстрактор воды.", "WaterExtractor"))

    # Power
    power_eta = history.eta_minutes("power_storage")
    if power_eta is not None and power_eta < _ETA_URGENT_MIN:
        out.append(Advice(90, f"Энергии хватит примерно на {int(round(power_eta))} минут. Постройте солнечную панель.",
                          "SolarPanel"))
    elif data.get("power_capacity", 0) > 0 and data.get("power_pct", 100) < 25:
        out.append(Advice(70, "Запас энергии ниже четверти. Нужны новые панели или аккумулятор.", "SolarPanel"))

    # Food
    food_eta = history.eta_minutes("food")
    if food_eta is not None and food_eta < _ETA_URGENT_MIN:
        out.append(Advice(85, f"Еды хватит примерно на {int(round(food_eta))} минут. Постройте гидропонную ферму.",
                          "BioDome"))
    elif data.get("low_food"):
        out.append(Advice(75, "Еды мало. Постройте гидропонную ферму или проверьте столовую.", "BioDome"))

    # Health
    sick = int(data.get("n_sick", 0) or 0)
    if sick > 0 and data.get("n_medics", 0) == 0:
        out.append(Advice(80, f"Больных: {sick}, а медиков нет. Постройте лазарет и назначьте медиков.", "SickBay"))
    medical_floor = max(5, round(colonists * 0.1))
    if data.get("res_medical", 0) <= medical_floor:
        out.append(Advice(60, "Медикаментов мало. Наладьте их производство."))

    if data.get("mod_vital_down", 0) > 0:
        out.append(Advice(65, "Есть повреждённые жизненно важные здания. Скажите «где сломано», я покажу."))

    # Planet-specific risks (levels come from the mod: none/low/variable/high)
    storm = max(planet.level(data, "sandstorm"), planet.level(data, "blizzard"))
    if storm >= 2 and data.get("power_capacity", 0) > 0 and data.get("power_pct", 100) < 60 + planet.reserve_bonus(data):
        word = "высокий" if storm == 3 else "переменный"
        out.append(Advice(55, f"На планете {word} риск бурь, а запас энергии {data.get('power_pct', 0)}%. "
                              "Добавьте аккумуляторы заранее.", "PowerCollector"))
    if planet.is_elevated(data, "meteor") and data.get("n_anti_meteor", 1) == 0 and data.get("module_count", 0) >= 10:
        out.append(Advice(55, "Есть риск метеоритов, а антиметеоритного лазера нет. Постройте лазер.",
                          "AntiMeteorLaser"))
    if planet.is_elevated(data, "thunderstorm") and data.get("n_lightning_rod", 1) == 0 and data.get("module_count", 0) >= 10:
        out.append(Advice(50, "Есть риск гроз, а молниеотвода нет. Постройте молниеотвод.", "LightningRod"))
    if (planet.is_elevated(data, "solar_flare") and not data.get("any_disaster")
            and data.get("alert_state", 0) == 0 and data.get("colonists", 0) > 0):
        out.append(Advice(15, "На планете бывают солнечные вспышки: при вспышке включайте жёлтый код, "
                              "колонисты снаружи в опасности."))

    if data.get("welfare_level", 4) in (0, 1):
        out.append(Advice(30, "Благосостояние колонистов низкое. Поможет бар или столовая.", "Bar"))

    if (not data.get("land_colonists", True) and data.get("alert_state", 0) == 0
            and data.get("n_intruders", 0) == 0):
        out.append(Advice(20, "Посадка колонистов всё ещё запрещена. Скажите «разреши посадку колонистов», если опасность прошла."))

    out.sort(key=lambda a: a.priority, reverse=True)
    return out


def advise(data: dict) -> str:
    """Spoken top advice; remembers the top buildable item as pending."""
    global _pending_build
    if not data.get("_valid"):
        return "Телеметрия недоступна. Убедитесь что игра запущена."

    items = collect(data)
    top = items[:_MAX_SPOKEN]
    with _lock:
        _pending_build = next((a.build for a in top if a.build), None)

    if not top:
        return "Критичных проблем не вижу. Колония в порядке."

    parts = [f"{_ORDINALS[i]}: {a.text}" for i, a in enumerate(top)]
    reply = " ".join(parts)
    if _pending_build:
        reply += " Скажите «построй рекомендованное», и я запущу строительство."
    return reply


def build_pending() -> str:
    global _pending_build
    with _lock:
        key = _pending_build
        _pending_build = None
    if not key:
        return "Нечего строить: сначала спросите, что делать."
    from . import commands
    return commands.build(key)
