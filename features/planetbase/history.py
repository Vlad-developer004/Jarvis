"""Rolling telemetry history: trends and time-to-empty forecasts.

Rates are measured in real minutes at the current game speed, so an ETA is
"how long you have at the speed you are playing right now". Samples taken while
paused are dropped, and a change of game speed starts a fresh trend window."""

import threading
import time
from collections import deque

_lock = threading.Lock()
_samples: deque = deque(maxlen=240)  # ~20 min at the monitor's 5 s tick
_first: dict | None = None

_TRACKED = (
    "power_storage", "water_storage", "colonists",
    "res_vegetables", "res_meat", "res_meals", "res_starch",
    "res_metal", "res_ore", "res_bioplastic", "res_medical",
)
_MIN_SAMPLES = 4
_MIN_SPAN_S = 30.0
_WINDOW_S = 180.0
_MAX_ETA_MIN = 120.0

_LABELS = {
    "power_storage": "энергии",
    "water_storage": "воды",
    "food": "еды",
    "res_medical": "медикаментов",
    "res_metal": "металла",
    "res_bioplastic": "биопластика",
}


def reset() -> None:
    global _first
    with _lock:
        _samples.clear()
        _first = None


def add(data: dict, now: float | None = None) -> None:
    """Record one telemetry snapshot (ignored when invalid or paused)."""
    global _first
    if not data.get("_valid") or data.get("paused"):
        return
    values = {k: float(data.get(k, 0) or 0) for k in _TRACKED}
    values["food"] = values["res_vegetables"] + values["res_meat"] + values["res_meals"]
    sample = {
        "ts": time.time() if now is None else now,
        "scale": float(data.get("time_scale", 1.0) or 1.0),
        "v": values,
    }
    with _lock:
        _samples.append(sample)
        if _first is None:
            _first = sample


def _slope_per_min(field: str) -> float | None:
    with _lock:
        if not _samples:
            return None
        latest = _samples[-1]
        tail = []
        # contiguous tail at the same game speed, newest first
        for s in reversed(_samples):
            if latest["ts"] - s["ts"] > _WINDOW_S or s["scale"] != latest["scale"]:
                break
            tail.append(s)
    tail.reverse()
    if len(tail) < _MIN_SAMPLES or tail[-1]["ts"] - tail[0]["ts"] < _MIN_SPAN_S:
        return None

    n = len(tail)
    t0 = tail[0]["ts"]
    xs = [(s["ts"] - t0) / 60.0 for s in tail]
    ys = [s["v"][field] for s in tail]
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den


def eta_minutes(field: str) -> float | None:
    """Real minutes until `field` reaches zero at the current rate, or None
    when it is stable/growing, unknown, or further away than two hours."""
    slope = _slope_per_min(field)
    if slope is None or slope >= 0:
        return None
    with _lock:
        current = _samples[-1]["v"][field] if _samples else 0.0
    if current <= 0:
        return None
    eta = current / -slope
    return eta if eta <= _MAX_ETA_MIN else None


def forecast_report() -> str:
    """Spoken forecast for power, water and food."""
    parts = []
    for field in ("power_storage", "water_storage", "food", "res_medical"):
        eta = eta_minutes(field)
        if eta is not None:
            parts.append(f"{_LABELS[field]} хватит примерно на {int(round(eta))} мин")
    if not parts:
        with _lock:
            enough = len(_samples) >= _MIN_SAMPLES
        return ("Тревожных прогнозов нет: запасы не убывают быстро." if enough
                else "Данных для прогноза пока мало, подождите минуту.")
    return "Прогноз при текущей скорости: " + "; ".join(parts) + "."


def session_summary() -> str:
    """Change of key stocks since the first sample of this session."""
    with _lock:
        if _first is None or not _samples:
            return ""
        first, last = _first["v"], _samples[-1]["v"]
    items = []
    for field, label in (("colonists", "колонистов"), ("res_metal", "металла"),
                         ("res_medical", "медикаментов"), ("food", "еды")):
        delta = int(last[field] - first[field])
        if delta:
            items.append(f"{label} {'+' if delta > 0 else ''}{delta}")
    return ("С начала сессии: " + ", ".join(items) + ".") if items else ""
