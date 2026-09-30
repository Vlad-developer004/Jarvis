"""Planet risk model: turns the mod's per-planet risk levels into alert thresholds
and advice. The mod reports each risk as the game's Quantity value:
None / Low / High / Variable."""

_LEVELS = {"none": 0, "low": 1, "variable": 2, "high": 3}
_LABEL_LEVEL = {0: "нет", 1: "низкий", 2: "переменный", 3: "высокий"}

RISKS = {
    "sandstorm": ("risk_sandstorm", "песчаные бури"),
    "solar_flare": ("risk_solar_flare", "солнечные вспышки"),
    "blizzard": ("risk_blizzard", "метели"),
    "meteor": ("risk_meteor", "метеориты"),
    "thunderstorm": ("risk_thunderstorm", "грозы"),
}

# Extra percentage points added to the "low" power/water alert thresholds when a
# weather risk that drains reserves is high; a storm is the worst time to be at 25%.
_RESERVE_POINTS = {2: 8, 3: 15}
_MAX_RESERVE_BONUS = 20
_WEATHER_DRAIN = ("sandstorm", "blizzard")


def level(data: dict, kind: str) -> int:
    """0 none/unknown, 1 low, 2 variable, 3 high."""
    field = RISKS[kind][0]
    return _LEVELS.get(str(data.get(field, "")).strip().lower(), 0)


def is_elevated(data: dict, kind: str) -> bool:
    return level(data, kind) >= 2


def reserve_bonus(data: dict) -> int:
    """Percentage points to add to the power/water 'low' thresholds."""
    bonus = sum(_RESERVE_POINTS.get(level(data, k), 0) for k in _WEATHER_DRAIN)
    return min(bonus, _MAX_RESERVE_BONUS)


def report(data: dict) -> str:
    """Spoken summary of the planet and its risks."""
    if not data.get("_valid"):
        return "Телеметрия недоступна. Убедитесь что игра запущена."
    # The mod's `difficulty` field carries an availability label ("Доступно"),
    # not a difficulty, so it is deliberately not spoken.
    name = data.get("planet") or "текущая планета"
    head = f"Планета {name}."
    parts = [f"{label} — {_LABEL_LEVEL[level(data, kind)]}" for kind, (_, label) in RISKS.items()]
    return f"{head} Риски: " + ", ".join(parts) + "."
