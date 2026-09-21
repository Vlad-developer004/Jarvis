from core.logging_setup import get_logger

_log = get_logger('ets2.llm')

_SYS_RU = (
    "Ты — бортовой компьютер J.A.R.V.I.S. в ETS2. Умный, харизматичный, чуть саркастичный штурман.\n"
    "Формат: без Markdown; без вводных слов (Конечно/Отлично/Понял/Принято); 3-5 коротких предложений; только русский.\n"
    "Деньги — словами с валютой: «триста евро» (никогда €). Города — кириллицей: Гамбург, Берлин. Числа — цифрами.\n"
    "СТАРТ: коротко оцени груз, ставку и маршрут с учётом времени суток, дай практичный или ироничный совет.\n"
    "ФИНИШ: оцени аккуратность доставки, скорость, заработок и тягач — похвали или мягко подколи за штрафы."
)

_SYS_UK = (
    "Ти — бортовий комп'ютер J.A.R.V.I.S. в ETS2. Розумний, харизматичний, трохи іронічний штурман.\n"
    "Формат: без Markdown; без вступних слів (Звичайно/Чудово/Зрозумів/Добре); 3-5 коротких речень; тільки українська.\n"
    "Гроші — словами з валютою: «триста євро» (ніколи €). Міста — кирилицею: Гамбург, Берлін. Числа — цифрами.\n"
    "СТАРТ: коротко оціни вантаж, ставку і маршрут з урахуванням часу доби, дай практичну або іронічну пораду.\n"
    "ФІНІШ: оціни акуратність доставки, швидкість, заробіток і тягач — похвали або м'яко підколи за штрафи."
)

def _sys_prompt() -> str:
    try:
        from core.i18n import get_speech_language
        return _SYS_UK if get_speech_language() == 'uk' else _SYS_RU
    except Exception:
        return _SYS_RU


def _load_ets2_settings() -> dict:
    try:
        import json, os
        from config_pack.config import get_settings_path
        sp = get_settings_path()
        if os.path.exists(sp):
            with open(sp, encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def has_api_key() -> bool:
    """True if any LLM API key is configured (regardless of ets2_llm_enabled)."""
    try:
        settings = _load_ets2_settings()
        provider = settings.get('ai_provider', 'groq')
        from features.qa.llm_processor import _load_api_key
        return bool(_load_api_key(provider))
    except Exception:
        return False


def has_llm_configured() -> bool:
    """True if API key exists and ETS2 AI is not explicitly disabled."""
    try:
        settings = _load_ets2_settings()
        if not settings.get('ets2_llm_enabled', True):
            return False
        provider = settings.get('ai_provider', 'groq')
        from features.qa.llm_processor import _load_api_key
        return bool(_load_api_key(provider))
    except Exception:
        return False


def build_job_start_prompt(data: dict) -> str:
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'

    uk = lang == 'uk'

    # Job basics
    cargo      = str(data.get("cargo", "")).strip()
    mass_kg    = float(data.get("cargoMass", 0))
    mass_t     = round(mass_kg / 1000, 1) if mass_kg >= 500 else None
    city_src   = str(data.get("citySrc", "")).strip()
    city_dst   = str(data.get("cityDst", "")).strip()
    comp_src   = str(data.get("compSrc", "")).strip()
    comp_dst   = str(data.get("compDst", "")).strip()
    income     = int(data.get("jobIncome", 0))
    planned_km = int(data.get("plannedDistanceKm", 0))
    special    = bool(data.get("specialJob", False))
    route_s    = float(data.get("routeTime", 0))

    from_str = f"{comp_src}, {city_src}" if comp_src else city_src
    to_str   = f"{comp_dst}, {city_dst}" if comp_dst else city_dst

    # Game time
    time_abs_min = int(data.get("time_abs", 0)) % 1440
    hour  = time_abs_min // 60
    minute = time_abs_min % 60
    game_time_str = f"{hour:02d}:{minute:02d}"

    if uk:
        time_ctx = ("раннє ранко, дороги вільні" if 5 <= hour <= 7 else
                    "глибока ніч" if hour <= 3 else "ніч" if hour >= 22 else
                    "вечірній час пік" if 17 <= hour <= 20 else "день")
    else:
        time_ctx = ("раннее утро, дороги свободны" if 5 <= hour <= 7 else
                    "глубокая ночь" if hour <= 3 else "ночь" if hour >= 22 else
                    "вечерний час пик" if 17 <= hour <= 20 else "день")

    # Deadline remaining (game time). time_abs/time_abs_delivery are both
    # absolute in-game minutes (not wrapped to 24h like time_abs_min above).
    time_abs_full = int(data.get("time_abs", 0))
    deadline_abs = int(data.get("time_abs_delivery", 0))
    deadline_line = ""
    if deadline_abs > 0 and time_abs_full > 0:
        remaining_min = deadline_abs - time_abs_full
        if remaining_min > 0:
            d_h, d_m = remaining_min // 60, remaining_min % 60
            if uk:
                deadline_line = (f"Дедлайн: {d_h} год {d_m} хв." if d_h > 0 else f"Дедлайн: {d_m} хв — поспішай!")
            else:
                deadline_line = (f"Дедлайн: {d_h} ч {d_m} мин." if d_h > 0 else f"Дедлайн: {d_m} мин — торопись!")

    # Pay rate
    rate = income / planned_km if planned_km > 0 and income > 0 else 0
    if uk:
        rate_label = ("дуже вигідна ставка" if rate >= 95 else
                      "гарна ставка"        if rate >= 70  else
                      "середня ставка"      if rate >= 45  else
                      "низька ставка"       if rate > 0    else "")
    else:
        rate_label = ("очень выгодная ставка" if rate >= 95 else
                      "хорошая ставка"        if rate >= 70  else
                      "средняя ставка"        if rate >= 45  else
                      "низкая ставка"         if rate > 0    else "")

    # Mass label
    if mass_t:
        if uk:
            mass_label = ("максимальне навантаження" if mass_t >= 40 else
                          "важке навантаження"       if mass_t >= 24 else
                          "середнє навантаження"     if mass_t >= 10 else
                          "легке навантаження")
        else:
            mass_label = ("максимальная загрузка" if mass_t >= 40 else
                          "тяжёлая загрузка"      if mass_t >= 24 else
                          "средняя загрузка"      if mass_t >= 10 else
                          "лёгкая загрузка")
    else:
        mass_label = ""

    # Route duration
    route_h = route_s / 3600 if route_s > 300 else (planned_km / 80) if planned_km > 0 else 0
    if uk:
        if route_h < 1.5:   route_label = f"короткий маршрут, ~{max(1, round(route_h))} год"
        elif route_h < 5.0: route_label = f"середній маршрут, ~{round(route_h)} год"
        else:               route_label = f"довгий маршрут, ~{round(route_h)} год"
    else:
        if route_h < 1.5:   route_label = f"короткий маршрут, ~{max(1, round(route_h))} ч"
        elif route_h < 5.0: route_label = f"средний маршрут, ~{round(route_h)} ч"
        else:               route_label = f"длинный маршрут, ~{round(route_h)} ч"

    # Cargo type classification
    cargo_lower = cargo.lower()
    if uk:
        if any(k in cargo_lower for k in ("лекарств", "вакцин", "електрон", "комп'ют", "скл", "fragile", "техніка", "телевіз")):
            cargo_type = "крихкий вантаж — потрібна обережність"
        elif any(k in cargo_lower for k in ("кислот", "бензин", "топлив", "газ", "хімі", "acid", "fuel", "flamm", "вибух", "небезп")):
            cargo_type = "небезпечний вантаж, клас ADR"
        elif any(k in cargo_lower for k in ("food", "молок", "м'ясо", "фрукт", "риба", "рефриж", "milk", "meat", "fish", "продукт")):
            cargo_type = "швидкопсувний, температурний режим"
        elif any(k in cargo_lower for k in ("машин", "трактор", "екскаватор", "автомоб", "car", "truck", "tractor", "excavator")):
            cargo_type = "великогабаритна техніка"
        elif any(k in cargo_lower for k in ("пісок", "граві", "руда", "вугіл", "камін", "sand", "ore", "coal")):
            cargo_type = "сипучий вантаж, стежити за стійкістю"
        else:
            cargo_type = ""
    else:
        if any(k in cargo_lower for k in ("лекарств", "вакцин", "электрон", "компьют", "стекл", "fragile", "хрупк", "техник", "телевиз")):
            cargo_type = "хрупкий груз — требует осторожности"
        elif any(k in cargo_lower for k in ("кислот", "бензин", "топлив", "газ", "хими", "acid", "fuel", "flamm", "взрыв", "опасн")):
            cargo_type = "опасный груз, класс ADR"
        elif any(k in cargo_lower for k in ("food", "молок", "мясо", "фрукт", "рыба", "рефриж", "milk", "meat", "fish", "продукт")):
            cargo_type = "скоропортящийся, температурный режим"
        elif any(k in cargo_lower for k in ("машин", "трактор", "экскаватор", "автомоб", "car", "truck", "tractor", "excavator")):
            cargo_type = "крупногабаритная техника"
        elif any(k in cargo_lower for k in ("песок", "грави", "руда", "уголь", "камен", "sand", "ore", "coal")):
            cargo_type = "сыпучий груз, следить за устойчивостью"
        else:
            cargo_type = ""

    # Fuel
    fuel_l       = float(data.get("fuel", 0))
    fuel_cap_l   = float(data.get("fuelCapacity", 0))
    fuel_range_km = int(float(data.get("fuelRange", 0)))
    fuel_line = ""
    if fuel_range_km > 0:
        fuel_pct = round(fuel_l / fuel_cap_l * 100) if fuel_cap_l > 0 else 0
        fuel_info = f"{int(fuel_l)} л ({fuel_pct}%)" if fuel_l > 0 and fuel_cap_l > 0 else f"{fuel_range_km} км"
        if uk:
            fuel_status = "заправка!" if fuel_range_km < 100 else ("заправка в дорозі" if planned_km and fuel_range_km < planned_km else "вистачить")
            fuel_line = f"Паливо: {fuel_info}, {fuel_range_km} км ({fuel_status})."
        else:
            fuel_status = "заправка!" if fuel_range_km < 100 else ("заправка в пути" if planned_km and fuel_range_km < planned_km else "хватит")
            fuel_line = f"Топливо: {fuel_info}, {fuel_range_km} км ({fuel_status})."

    # Truck identity
    truck_brand = str(data.get("truckBrand", "")).strip()
    truck_name  = str(data.get("truckName", "")).strip()
    truck_id = " ".join(filter(None, [truck_brand, truck_name])) or ""

    # Truck wear — individual components ≥15%
    _wear_map = [
        ("wearEngine",       "двигатель"  if not uk else "двигун"),
        ("wearTransmission", "КПП"),
        ("wearChassis",      "шасси"      if not uk else "шасі"),
        ("wearCabin",        "кабина"     if not uk else "кабіна"),
        ("wearWheels",       "колёса"     if not uk else "колеса"),
        ("wearTrailer",      "прицеп"     if not uk else "причіп"),
    ]
    wear_detail = [(name, round(float(data.get(field, 0)) * 100, 1))
                   for field, name in _wear_map
                   if float(data.get(field, 0)) * 100 >= 15]
    wear_str = ", ".join(f"{name} {pct}%" for name, pct in wear_detail) if wear_detail else ""
    avg_wear = sum(pct for _, pct in wear_detail) / len(wear_detail) if wear_detail else 0

    if wear_str:
        if uk:
            wear_warn = (" — критичний стан!" if avg_wear >= 60 else
                         " — рекомендовано ТО." if avg_wear >= 35 else ".")
            truck_wear_line = f"Знос тягача: {wear_str}{wear_warn}"
        else:
            wear_warn = (" — критическое состояние!" if avg_wear >= 60 else
                         " — рекомендован ТО." if avg_wear >= 35 else ".")
            truck_wear_line = f"Износ тягача: {wear_str}{wear_warn}"
    else:
        truck_wear_line = ""

    # Rest stop (restStop = game minutes until rest required)
    rest_min = int(float(data.get("restStop", 0)))
    rest_line = ""
    if rest_min > 0:
        rest_h, rest_m = rest_min // 60, rest_min % 60
        if uk:
            rest_line = (f"Відпочинок: через {rest_h} год {rest_m} хв." if rest_h > 0 else f"Відпочинок: {rest_m} хв — водій втомлений!")
        else:
            rest_line = (f"Отдых: через {rest_h} ч {rest_m} мин." if rest_h > 0 else f"Отдых: {rest_m} мин — водитель устал!")

    lines: list[str] = []

    # — Cargo & route
    cargo_str = cargo
    if mass_t:
        cargo_str += f", {mass_t} т"
        if mass_label:
            cargo_str += f" ({mass_label})"
    if cargo_str:
        lines.append(("Вантаж: " if uk else "Груз: ") + cargo_str + ("  [СПЕЦПЕРЕВЕЗЕННЯ]" if special else "") + ".")
    if cargo_type:
        lines.append(("Тип: " if uk else "Тип: ") + cargo_type + ".")
    if from_str and to_str:
        lines.append(("Маршрут: " if uk else "Маршрут: ") + f"{from_str} → {to_str}.")

    # — Distance & duration
    if planned_km:
        lines.append(("Відстань: " if uk else "Расстояние: ") + f"{planned_km} км, {route_label}.")

    # — Pay
    if income:
        _eur = 'євро' if uk else 'евро'
        pay_str = f"{income} {_eur}"
        if rate_label and rate > 0:
            pay_str += f" ({rate_label}, {rate:.0f} {_eur}/км)"
        lines.append(("Оплата: " if uk else "Оплата: ") + pay_str + ".")

    # — Game time & deadline
    lines.append(("Час в грі: " if uk else "Время в игре: ") + f"{game_time_str} ({time_ctx}).")
    if deadline_line:
        lines.append(deadline_line)

    # — Fuel
    if fuel_line:
        lines.append(fuel_line)

    # — Rest stop warning
    if rest_line:
        lines.append(rest_line)

    # — Truck wear
    if truck_wear_line:
        lines.append(truck_wear_line)

    # — Instruction
    if uk:
        instruction = (f"Тягач: {truck_id}. " if truck_id else "") + \
            "Проведи брифінг: оціни вантаж, маршрут, дедлайн і паливо. Дай конкретну пораду і побажай вдалої дороги."
    else:
        instruction = (f"Тягач: {truck_id}. " if truck_id else "") + \
            "Проведи брифинг: оцени груз, маршрут, дедлайн и топливо. Дай конкретный совет и пожелай удачной дороги."
    lines.append(instruction)

    return "\n".join(l for l in lines if l)


def build_job_delivered_prompt(
    data: dict,
    cargo_dmg: float,
    dist_km: float,
    revenue: int,
    xp: int,
    elapsed_min: float,
    autopark: bool,
    fines: list | None = None,
    planned_income: int = 0,
    driving_stats: dict | None = None,
) -> str:
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'

    fines     = fines or []
    driving_stats = driving_stats or {}
    fine_key  = 'uk' if lang == 'uk' else 'ru'
    uk        = lang == 'uk'

    # Route context
    cargo     = str(data.get("cargo", "")).strip()
    mass_kg   = float(data.get("cargoMass", 0))
    mass_t    = round(mass_kg / 1000, 1) if mass_kg >= 500 else None
    city_src  = str(data.get("citySrc", "")).strip()
    city_dst  = str(data.get("cityDst", "")).strip()
    comp_dst  = str(data.get("compDst", "")).strip()
    planned_km = int(data.get("plannedDistanceKm", 0))

    to_str = f"{comp_dst}, {city_dst}" if comp_dst else city_dst

    # Timing: jobDeliveredTimeDifference > 0 = ahead of schedule (seconds)
    time_diff_s = int(data.get("jobDeliveredTimeDifference", 0))
    time_diff_min = abs(time_diff_s) // 60
    if uk:
        timing_line = (f"Прибув на {time_diff_min} хв раніше — бонус до оплати." if time_diff_s > 120 else
                       "Прибув вчасно." if time_diff_s >= -120 else
                       f"Запізнення {time_diff_min} хв — штраф до оплати.")
    else:
        timing_line = (f"Прибыл на {time_diff_min} мин раньше — бонус к оплате." if time_diff_s > 120 else
                       "Прибыл вовремя." if time_diff_s >= -120 else
                       f"Опоздание {time_diff_min} мин — штраф к оплате.")

    # Speed
    avg_speed = (dist_km / (elapsed_min / 60)) if elapsed_min > 0 and dist_km > 0 else 0
    if uk:
        speed_label = ("відмінний темп" if avg_speed > 90 else
                       "гарний темп"   if avg_speed > 75 else
                       "спокійний темп" if avg_speed > 55 else
                       "повільно"      if avg_speed > 0  else "")
    else:
        speed_label = ("отличный темп" if avg_speed > 90 else
                       "хороший темп"  if avg_speed > 75 else
                       "спокойный темп" if avg_speed > 55 else
                       "медленно"      if avg_speed > 0  else "")

    # Cargo damage
    if uk:
        dmg_label = ("без пошкоджень, ідеально" if cargo_dmg < 0.1 else
                     "мінімальні подряпини"      if cargo_dmg < 3   else
                     "помітні пошкодження"       if cargo_dmg < 10  else
                     "серйозні пошкодження"      if cargo_dmg < 25  else
                     "критичні втрати вантажу")
    else:
        dmg_label = ("без повреждений, идеально" if cargo_dmg < 0.1 else
                     "минимальные царапины"       if cargo_dmg < 3   else
                     "заметные повреждения"       if cargo_dmg < 10  else
                     "серьёзные повреждения"      if cargo_dmg < 25  else
                     "критические потери груза")

    # Financial breakdown
    total_fines = sum(f.get('amount', 0) for f in fines)
    deduction = planned_income - revenue if planned_income > 0 and revenue > 0 else 0
    # Damage-only loss = deduction minus fines (fines are separate from job revenue)
    dmg_loss = max(0, deduction - total_fines) if deduction > 0 else 0

    # Truck wear — show each component with exact %
    _wear_map = [
        ("wearEngine",       "двигатель"  if not uk else "двигун"),
        ("wearTransmission", "КПП"),
        ("wearChassis",      "шасси"      if not uk else "шасі"),
        ("wearCabin",        "кабина"     if not uk else "кабіна"),
        ("wearWheels",       "колёса"     if not uk else "колеса"),
        ("wearTrailer",      "прицеп"     if not uk else "причіп"),
    ]
    wear_detail = [(name, round(float(data.get(field, 0)) * 100, 1))
                   for field, name in _wear_map
                   if float(data.get(field, 0)) * 100 >= 20]
    wear_str = ", ".join(f"{name} {pct}%" for name, pct in wear_detail) if wear_detail else ""

    # Fines list
    fines_line = ""
    _eur = 'євро' if uk else 'евро'
    if fines:
        parts = [f"{f.get(fine_key, f.get('ru', ''))} −{f.get('amount', 0)} {_eur}" for f in fines]
        if uk:
            fines_line = f"Штрафи ДАІ: {', '.join(parts)}. Разом: −{total_fines} {_eur}."
        else:
            fines_line = f"Штрафы ГИБДД: {', '.join(parts)}. Итого: −{total_fines} {_eur}."

    # Autoload note
    autoload = bool(data.get("jobDeliveredAutoloadUsed", False))

    lines: list[str] = []

    # — Route recap
    recap = ""
    if cargo:
        recap = cargo
        if mass_t:
            recap += f", {mass_t} т"
    if city_src and city_dst:
        route_recap = f"{city_src} → {to_str}" if to_str else f"{city_src} → {city_dst}"
        if recap:
            recap += f" | {route_recap}"
        else:
            recap = route_recap
    if recap:
        lines.append(("Рейс завершено: " if uk else "Рейс завершён: ") + recap + ".")

    # — Distance & time
    if dist_km and elapsed_min >= 5:
        dist_extra = ""
        if planned_km > 0 and abs(dist_km - planned_km) > 10:
            diff_km = int(round(dist_km - planned_km))
            dist_extra = (f" (план {planned_km} км, відхилення {'+' if diff_km > 0 else ''}{diff_km} км)"
                          if uk else
                          f" (план {planned_km} км, отклонение {'+' if diff_km > 0 else ''}{diff_km} км)")
        time_str = (f"{int(round(dist_km))} км за {int(elapsed_min // 60)} год {int(elapsed_min % 60)} хв"
                    if uk and elapsed_min >= 60 else
                    f"{int(round(dist_km))} км за {int(elapsed_min // 60)} ч {int(elapsed_min % 60)} мин"
                    if not uk and elapsed_min >= 60 else
                    f"{int(round(dist_km))} км за {int(round(elapsed_min))} хв"
                    if uk else
                    f"{int(round(dist_km))} км за {int(round(elapsed_min))} мин")
        speed_part = f" ({speed_label}, {avg_speed:.0f} {'км/год' if uk else 'км/ч'})" if speed_label else ""
        lines.append(time_str + dist_extra + speed_part + ".")

    # — Timing (early/late)
    lines.append(timing_line)

    # — Cargo damage
    if cargo_dmg < 0.1:
        lines.append("Вантаж цілий, без пошкоджень." if uk else "Груз целый, без повреждений.")
    else:
        dmg_str = f"{dmg_label} ({cargo_dmg:.2f}%)"
        if dmg_loss > 0:
            dmg_str += f" — вирахувано {dmg_loss} євро" if uk else f" — вычтено {dmg_loss} евро"
        lines.append(("Стан вантажу: " if uk else "Состояние груза: ") + dmg_str + ".")

    # — Financial result
    if revenue:
        if planned_income > 0:
            if uk:
                lines.append(f"Фінансовий підсумок: заплановано {planned_income} євро, нараховано {revenue} євро, досвід {xp} XP.")
            else:
                lines.append(f"Финансовый итог: запланировано {planned_income} евро, начислено {revenue} евро, опыт {xp} XP.")
        else:
            lines.append(f"{'Нараховано' if uk else 'Начислено'} {revenue} {_eur}, {'досвід' if uk else 'опыт'} {xp} XP.")

    # — Fines
    if fines_line:
        lines.append(fines_line)

    # — Truck wear
    if wear_str:
        lines.append(("Знос вузлів тягача: " if uk else "Износ узлов тягача: ") + wear_str + ".")

    # — Misc flags
    if autopark:
        lines.append("Використано автопарковку." if uk else "Использована автопарковка.")

    # — Driving style (harsh braking / speeding / RPM-abuse counts collected
    # over the whole job by features/ets2/monitor.py's bump_driving_stat)
    harsh_brakes = int(driving_stats.get('harsh_brakes', 0))
    speeding_events = int(driving_stats.get('speeding_events', 0))
    gear_warnings = int(driving_stats.get('gear_warnings', 0))
    total_incidents = harsh_brakes + speeding_events + gear_warnings
    if total_incidents == 0:
        lines.append(
            "Стиль водіння: бездоганний — жодного різкого гальмування чи перевищення за весь рейс." if uk else
            "Стиль вождения: безупречный — ни одного резкого торможения или превышения за весь рейс."
        )
    else:
        if uk:
            bits = []
            if harsh_brakes: bits.append(f"різких гальмувань — {harsh_brakes}")
            if speeding_events: bits.append(f"перевищень швидкості — {speeding_events}")
            if gear_warnings: bits.append(f"зловживань обертами двигуна — {gear_warnings}")
            lines.append("Стиль водіння за рейс: " + ", ".join(bits) + ".")
        else:
            bits = []
            if harsh_brakes: bits.append(f"резких торможений — {harsh_brakes}")
            if speeding_events: bits.append(f"превышений скорости — {speeding_events}")
            if gear_warnings: bits.append(f"злоупотреблений оборотами двигателя — {gear_warnings}")
            lines.append("Стиль вождения за рейс: " + ", ".join(bits) + ".")

    # — Instruction
    lines.append(
        "Підведи підсумок рейсу: оціни доставку вантажу, фінанси, штрафи, знос тягача і стиль водіння. Зроби висновок і підбадьор або підколи водія." if uk else
        "Подведи итог рейса: оцени доставку груза, финансы, штрафы, износ тягача и стиль вождения. Сделай вывод и похвали или подколи водителя."
    )

    return "\n".join(l for l in lines if l)


def build_live_commentary_prompt(data: dict) -> str:
    """A short ambient remark during a long, uneventful highway stretch —
    not a status report, just flavor. Kept deliberately thin on context so
    the model doesn't turn it into another full briefing."""
    try:
        from core.i18n import get_speech_language
        uk = get_speech_language() == 'uk'
    except Exception:
        uk = False

    city_dst = str(data.get("cityDst", "")).strip()
    cargo = str(data.get("cargo", "")).strip()
    route_dist_km = int(float(data.get("routeDistance", 0)) / 1000)
    time_abs_min = int(data.get("time_abs", 0)) % 1440
    hour = time_abs_min // 60

    if uk:
        time_ctx = ("глибока ніч" if hour <= 3 else "ніч" if hour >= 22 else
                    "раннє ранок" if hour <= 7 else "вечір" if hour >= 18 else "день")
        lines = [f"Їдемо по трасі, {time_ctx}, ще ~{route_dist_km} км до {city_dst or 'мети'}."]
        if cargo:
            lines.append(f"Веземо: {cargo}.")
        lines.append(
            "Кинь одну коротку (1-2 речення) невимушену репліку в дорогу — спостереження, жарт "
            "чи легка порада. Без привітань і без повторення цифр з контексту."
        )
    else:
        time_ctx = ("глубокая ночь" if hour <= 3 else "ночь" if hour >= 22 else
                    "раннее утро" if hour <= 7 else "вечер" if hour >= 18 else "день")
        lines = [f"Едем по трассе, {time_ctx}, ещё ~{route_dist_km} км до {city_dst or 'цели'}."]
        if cargo:
            lines.append(f"Везём: {cargo}.")
        lines.append(
            "Брось одну короткую (1-2 предложения) непринуждённую реплику в дорогу — наблюдение, "
            "шутку или лёгкий совет. Без приветствий и без повторения цифр из контекста."
        )
    return "\n".join(lines)


def ask_ets2(prompt: str, timeout: int = 12) -> str:
    """Call the configured LLM with ETS2 context. Returns '' on any failure."""
    try:
        from features.qa.llm_processor import ask_llm, _clean
        result = ask_llm(
            topic='',
            question=prompt,
            timeout=timeout,
            sys_prompt=_sys_prompt(),
            max_tokens=450,
        )
        if isinstance(result, str) and result.strip():
            return _clean(result)
    except Exception as e:
        _log.warning('ETS2 LLM error: %s', e)
    return ''
