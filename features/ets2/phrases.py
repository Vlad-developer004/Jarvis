def _fuel_phrase(km: float) -> str:
    km_int = int(round(km))
    if km_int <= 15:
        return "Топливо на исходе. Срочно найдите заправку."
    if km_int <= 30:
        return f"Критический уровень топлива. До пустого бака {km_int} километров."
    if km_int <= 50:
        return f"Внимание, запас хода {km_int} километров."
    if km_int <= 100:
        return f"Сэр, рекомендую заправиться. Запас хода {km_int} километров."
    if km_int <= 200:
        return f"Сэр, горючего хватит ещё на {km_int} километров."
    return f"Сэр, запас хода — {km_int} километров."
def _wear_phrase(component: str, pct: int) -> str:
    if pct >= 90:
        return (
            f"Сэр, критический износ! {component.capitalize()} изношен{'а' if component in ('коробка передач', 'кабина') else ''} "
            f"на {pct} процентов. Срочно в сервис."
        )
    if pct >= 75:
        return (
            f"Сэр, сильный износ. {component.capitalize()} изношен{'а' if component in ('коробка передач', 'кабина') else ''} "
            f"на {pct} процентов. Рекомендую посетить сервис."
        )
    if pct >= 50:
        return (
            f"Сэр, {component} изношен{'а' if component in ('коробка передач', 'кабина') else ''} "
            f"на {pct} процентов. Стоит запланировать техобслуживание."
        )
    return (
        f"Сэр, {component} изношен{'а' if component in ('коробка передач', 'кабина') else ''} "
        f"на {pct} процентов. Рекомендую заглянуть в сервис после рейса."
    )
