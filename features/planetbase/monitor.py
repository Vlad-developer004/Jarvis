"""Background monitor: голосовые уведомления по данным Planetbase telemetry."""

import logging
import random
import threading
import time

from features.planetbase import installer, telemetry

_log = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_running = False

# ── Пороги ───────────────────────────────────────────────────
_POWER_LOW_PCT        = 20
_POWER_CRIT_PCT       = 10
_WATER_LOW_PCT        = 20
_WATER_CRIT_PCT       = 10
_WATER_BALANCE_MARGIN = 1.5
_OXYGEN_MARGIN        = 10
_MEDICAL_LOW          = 5
_MEDICAL_CRIT         = 1
_MATERIALS_LOW        = 10
_FOOD_ITEM_LOW         = 15

# ── Кулдауны (секунды) ───────────────────────────────────────
_COOLDOWN = {
    "power_critical":    60,
    "power_low":        120,
    "water_critical":    60,
    "water_low":        120,
    "water_deficit":    120,
    "water_marginal":   300,
    "oxygen_critical":   60,
    "oxygen_low":       180,
    "medical_critical":  60,
    "medical_low":      300,
    "materials_low":    300,
    "food_low":         180,
    "food_veg_low":     300,
    "food_meat_low":    300,
    "food_meals_low":   300,
    "disaster":          30,
    "disaster_end":      10,
    "all_quiet":       1800,
}

_COLONIST_MILESTONES = [25, 50, 100, 150, 200, 300, 500]

_last_announced:       dict = {}
_announced_milestones: set  = set()
_prev:                 dict = {}
_first_tick                 = True
_quiet_streak               = 0
_auto_alert_engaged         = False


def _focus_planetbase() -> bool:
    try:
        import pygetwindow as gw
        from core.system import force_foreground
        for w in gw.getAllWindows():
            title = (getattr(w, 'title', '') or '').lower()
            if 'planetbase' not in title:
                continue
            if getattr(w, 'isMinimized', False):
                try:
                    w.restore()
                except Exception:
                    pass
            if hasattr(w, '_hWnd'):
                force_foreground(int(w._hWnd))
            return True
    except Exception as e:
        _log.debug("Focus Planetbase error: %s", e)
    return False


def _press_key(key: str):
    try:
        from actions.game_input_parts.profile import press_robust
        _focus_planetbase()
        time.sleep(0.1)
        press_robust(key)
    except Exception as e:
        _log.debug("Key press error (%s): %s", key, e)


def _engage_yellow_alert():
    """Жёлтый код (2) — эвакуация колони́стов внутрь."""
    global _auto_alert_engaged
    _press_key("2")
    _auto_alert_engaged = True


def _disengage_alert():
    """Зелёный код (1) — отбой тревоги."""
    global _auto_alert_engaged
    _press_key("1")
    _auto_alert_engaged = False


def _cooldown_ok(key: str) -> bool:
    now = time.time()
    if now - _last_announced.get(key, 0) >= _COOLDOWN.get(key, 60):
        _last_announced[key] = now
        return True
    return False


def _speak(text: str):
    try:
        from core.speech.tts import speak
        speak(text)
    except Exception as e:
        _log.debug("TTS error: %s", e)


def _addr() -> str:
    try:
        from core.address import get_address
        return get_address()
    except Exception:
        return ""


# ── Вступления по тональности ────────────────────────────────
_INTROS = {
    # Срочно, критично
    "critical": [
        "у нас критическая ситуация —",
        "незамедлительно примите меры —",
        "ситуация выходит из-под контроля —",
        "ахтунг, критический сбой системы —",
        "обнаружена серьёзная угроза —",
    ],
    # Предупреждение
    "warn": [
        "рекомендую обратить внимание на приборы —",
        "зафиксировано отклонение от нормы —",
        "сенсоры регистрируют неладное —",
        "не хочу вас отвлекать, но —",
        "похоже, назревают неприятности —",
    ],
    # Хорошие новости
    "good": [
        "небольшой повод для оптимизма —",
        "приятные новости с полей —",
        "рад сообщить следующее —",
        "ситуация стабилизируется —",
        "показатели пошли в гору —",
    ],
    # Поздравление (вехи)
    "congrats": [
        "мои искренние поздравления —",
        "это исторический момент для коло́нии —",
        "мы вышли на новый уровень развития —",
        "отличный повод откупорить бутылочку синтетического шампанского —",
        "замечательное достижение —",
    ],
    # Тревога (катастрофы)
    "alert": [
        "внимание, объявлена общая тревога —",
        "активирован защитный протокол —",
        "зафиксирована внешняя угроза —",
        "приготовьтесь, системы переходят в режим ЧС —",
    ],
    # Нейтральный доклад
    "info": [
        "очередная сводка данных —",
        "текущее положение дел таково —",
        "состояние систем в пределах нормы —",
        "краткий рапорт —",
    ],
}


def _alert(phrases: list[str], tone: str = "warn") -> None:
    """Произнести фразу с обращением и вступлением по тональности."""
    text  = random.choice(phrases)
    a     = _addr()
    intro = random.choice(_INTROS.get(tone, [""])).strip()

    # Первая буква фразы — строчная (продолжение после запятой/тире)
    body = text[0].lower() + text[1:] if text else text

    if a and intro:
        full = f"{a}, {intro} {body}"
    elif a:
        full = f"{a}, {body}"
    elif intro:
        full = f"{intro} {text}"
    else:
        full = text

    _speak(full)


# ── Банки фраз ───────────────────────────────────────────────

def _phrases_power_low(pct: int) -> list[str]:
    return [
        f"энергетическая сеть на пределе. Заряд накопителей просел до {pct} проце́нтов.",
        f"генера́торы шепчут о пощаде. Осталось {pct} проце́нтов энергии, стоит отключить лишние лампочки.",
        f"запасы энергии тают на глазах, сейчас на отметке {pct} проце́нтов.",
        f"наши батареи разряжаются быстрее, чем хотелось бы. Уровень заряда: {pct}%.",
    ]

def _phrases_power_critical(pct: int) -> list[str]:
    return [
        f"мы на грани тотального блэкаута! Энергии осталось всего {pct} проце́нтов.",
        f"аккумуляторы практически пусты — {pct}%. Если не принять меры, коло́ния превратится в склеп.",
        f"критический дефицит питания, у нас всего {pct} проце́нтов. Жизнеобеспечение под угрозой!",
        f"электричество почти всё. Ставлю на кон свою схему питания, что у нас осталось {pct} проце́нтов.",
    ]

def _phrases_water_low(pct: int) -> list[str]:
    return [
        f"запасы воды иссякают, резервуары заполнены всего на {pct} проце́нтов.",
        f"уровень воды упал до {pct} проце́нтов. Время экономить на гигиене.",
        f"датчики фиксируют снижение уровня воды до {pct} проце́нтов.",
        f"вода уходит, как сквозь песок. Резерв составляет {pct}%.",
    ]

def _phrases_water_critical(pct: int) -> list[str]:
    return [
        f"мы рискуем умереть от жажды! В резервуарах осталось жалкие {pct} проце́нтов воды.",
        f"критический уровень влаги, всего {pct}%. Водоснабжение на грани остановки.",
        f"вода почти закончилась — {pct} проце́нтов. Срочно перекройте все краны!",
    ]

def _phrases_water_deficit() -> list[str]:
    return [
        "потребление воды нагло превышает её добычу. Стоит построить дополнительный экстра́ктор.",
        "расход воды опережает её генерацию. Баланс отрицательный, нам нужно больше экстра́кторов.",
        "дефицит воды! Наша коло́ния выпивает больше, чем добывают насосы.",
    ]

def _phrases_water_marginal() -> list[str]:
    return [
        "водный баланс болтается на нуле. Добыча едва перекрывает сушняк колони́стов.",
        "вода на исходе, запаса нет. Экстра́кторы работают впритык к объёмам потребления.",
        "водный баланс держится на честном слове. Малейший сбой — и мы останемся ни с чем.",
    ]

def _phrases_oxygen_critical(colonists: int, cap: int) -> list[str]:
    return [
        f"воздух заканчивается! Кислородная система рассчитана максимум на {cap} ртов, а у нас их {colonists}.",
        f"критический избыток населения. Генера́торы тянут только {cap} человек, а на базе находится {colonists}.",
        f"мы задыхаемся! В коло́нии {colonists} жителей при лимите генерации кислорода в {cap} человек.",
    ]

def _phrases_oxygen_low(colonists: int, cap: int) -> list[str]:
    return [
        f"кислород на пределе возможностей. Генера́торы рассчитаны на {cap} человек, а жителей уже {colonists}.",
        f"свободного воздуха становится всё меньше. Нагрузка: {colonists} из {cap}. Рекомендую расширить генера́торы.",
        f"запас кислорода тает. Вентиляция едва справляется с {colonists} колони́стами при норме в {cap}.",
    ]

def _phrases_medical_critical() -> list[str]:
    return [
        "аптечки абсолютно пусты! Любая царапина станет фатальной, если не купить или не произвести медикаме́нты.",
        "запас медикаме́нтов равен нулю. Колони́сты молятся на подорожники, срочно займитесь поставками.",
        "лекарств не осталось совсем. В лазарете паника, лечить людей нечем.",
    ]

def _phrases_medical_low(amount: int) -> list[str]:
    return [
        f"запас медикаме́нтов тает на глазах, на складе осталось всего {amount} единиц.",
        f"лекарств критически мало — осталось {amount} штук. Пора запускать лабораторию.",
        f"медицинский резерв истощён, осталось всего {amount} единиц лекарств.",
    ]

def _phrases_materials_low() -> list[str]:
    return [
        "на складах мышь повесилась. Мета́лл и биопла́стик на исходе, стройка заморожена.",
        "запасы базовых строительных материалов стремятся к нулю. Добудьте руду или переработайте крахмал.",
        "нет сырья — нет прогресса. Строительные материалы закончились.",
    ]

def _phrases_food_low() -> list[str]:
    return [
        "наша коло́ния на пороге великого голода. Продовольствие заканчивается, пора сажать новые грядки.",
        "запасы еды стремительно приближаются к нулю. Колони́сты начинают косо поглядывать друг на друга.",
        "пустые тарелки по всей базе. Срочно расширяйте сельскохозяйственные купола.",
    ]

def _phrases_food_item_low(label: str, amount: int) -> list[str]:
    if amount <= 0:
        return [
            f"позиция «{label.lower()}» полностью исчерпана. Склад пуст.",
            f"кризис поставок: {label.lower()} закончились абсолютно.",
        ]
    return [
        f"запас по категории «{label.lower()}» снизился до {amount} единиц.",
        f"наши повара бьют тревогу: {label.lower()} на исходе, осталось всего {amount}.",
    ]

def _phrases_sandstorm_start() -> list[str]:
    return [
        "надвигается песчаная буря! Объявляю жёлтый код. Всем спрятаться под купол, если не хотите быть отпескоструенными.",
        "сенсоры зафиксировали стену песка. Включаю жёлтую тревогу, наружные работы приостановлены.",
        "начинается пылевой шторм. Активирую режим эвакуации, загоняю всех внутрь.",
    ]

def _phrases_sandstorm() -> list[str]:
    return [
        "песчаная буря бушует вовсю. За окном сплошной хаос и нулевая видимость.",
        "шторм не утихает. Сидим дома и надеемся, что купола выдержат.",
    ]

def _phrases_solar_flare() -> list[str]:
    return [
        "солнечная вспышка! Радиационный фон зашкаливает, выработка энергии скачет, как сумасшедшая.",
        "зарегистрирован мощный выброс на солнце. Ожидаются перебои в электросети и помехи связи.",
        "солнечная радиация бьет по панелям. Держитесь, возможны просадки по питанию.",
    ]

def _phrases_blizzard_start() -> list[str]:
    return [
        "начинается ледяная метель! Объявляю жёлтый код. Колони́сты, бегом греться внутрь купола.",
        "температура снаружи падает, летит снег. Активирую жёлтую тревогу, закрываю шлюзы.",
        "зафиксирована снежная буря. Включаю режим укрытия, на улице сейчас делать нечего.",
    ]

def _phrases_blizzard() -> list[str]:
    return [
        "метель в самом разгаре. Температура за бортом экстремально низкая, берегите обшивку.",
        "ледяной ветер не утихает, колонию заметает снегом.",
    ]

def _phrases_disaster_generic_start() -> list[str]:
    return [
        "приближается природный катаклизм. Включаю жёлтую тревогу для перестраховки.",
        "зарегистрирована погодная аномалия. Объявляю жёлтый код, всем укрыться.",
    ]

def _phrases_disaster_generic() -> list[str]:
    return [
        "стихия снаружи буйствует. Все системы работают в аварийном режиме.",
        "неблагоприятные погодные условия продолжаются. Рекомендуется не высовываться.",
    ]

def _phrases_disaster_end() -> list[str]:
    return [
        "небо прояснилось, стихия утихла! Снимаю жёлтый код, можно снова дышать свежим... точнее, купольным воздухом.",
        "буря прошла стороной. Отбой тревоги, все системы возвращаются в штатный режим.",
        "непогода закончилась. Разрешаю колонистам продолжить прогулки на свежем воздухе.",
    ]

def _phrases_arrival(n: int) -> list[str]:
    if n == 1:
        return [
            "к нам пристыковался корабль с новым колони́стом. Встречайте свежую рабочую силу.",
            "у нас пополнение в семействе! Один новобранец сошел на трап.",
            "база приняла нового жителя. Надеюсь, он умеет работать.",
        ]
    return [
        f"целая толпа! К нам прибыло сразу {n} новых колони́стов.",
        f"пополнение в рядах: {n} новых выживших зарегистрировано на шлюзе.",
        f"население коло́нии увеличилось на {n} человек. Надеюсь, коек на всех хватит.",
    ]

def _phrases_death(n: int) -> list[str]:
    if n == 1:
        return [
            "один из наших подопечных отправился в лучший мир. Естественный отбор в действии.",
            "грустная статистика: зафиксирована смерть одного колони́ста.",
            "минус один житель. Закажите гроб или подготовьте утилизатор.",
        ]
    return [
        f"у нас массовые потери! Погибло {n} колони́стов.",
        f"трагедия на базе — {n} человек не перенесли суровых условий выживания.",
        f"черный день для миссии: скончались {n} жителей.",
    ]

def _phrases_milestone(colonists: int) -> list[str]:
    return [
        f"круглая дата! Популяция коло́нии достигла отметки в {colonists} душ.",
        f"нас уже {colonists} человек! Скоро придется основывать собственное правительство.",
        f"исторический рубеж в {colonists} колони́стов успешно преодолен!",
    ]

def _phrases_all_quiet(colonists: int, modules: int) -> list[str]:
    return [
        f"всё спокойно. Население: {colonists} колони́стов, количество модулей: {modules}. Полная идиллия.",
        f"на базе тишь да гладь. Наша коло́ния из {modules} модулей функционирует безупречно.",
        f"все приборы в зеленой зоне. {colonists} колони́стов живы, сыты и относительно довольны жизнью.",
    ]



# ── Основная проверка ─────────────────────────────────────────

def _check(data: dict):
    global _prev, _first_tick, _quiet_streak

    if not data.get("_valid"):
        _quiet_streak = 0
        return

    colonists   = data.get("colonists", 0)
    modules     = data.get("module_count", 0)
    power_pct   = data.get("power_pct", 100)
    water_pct   = data.get("water_pct", 100)
    water_bal   = float(data.get("water_balance", 0))
    water_cap   = float(data.get("water_capacity", 0))
    oxygen_cap  = data.get("oxygen_gen", 0)
    medical     = data.get("res_medical", 0)
    metal       = data.get("res_metal", 0)
    bioplastic  = data.get("res_bioplastic", 0)
    veg         = data.get("res_vegetables", 0)
    meat        = data.get("res_meat", 0)
    meals       = data.get("res_meals", 0)
    low_food    = data.get("low_food", False)
    any_d       = data.get("any_disaster", False)
    sandstorm   = data.get("sandstorm", False)
    solar_flare = data.get("solar_flare", False)
    blizzard    = data.get("blizzard", False)

    alert_fired = False

    # ── Энергия ─────────────────────────────────────────────
    if power_pct <= _POWER_CRIT_PCT and _cooldown_ok("power_critical"):
        _alert(_phrases_power_critical(power_pct), tone="critical")
        alert_fired = True
    elif power_pct <= _POWER_LOW_PCT and _cooldown_ok("power_low"):
        _alert(_phrases_power_low(power_pct), tone="warn")
        alert_fired = True

    # ── Вода ────────────────────────────────────────────────
    if water_cap > 0:
        if water_pct <= _WATER_CRIT_PCT and _cooldown_ok("water_critical"):
            _alert(_phrases_water_critical(water_pct), tone="critical")
            alert_fired = True
        elif water_pct <= _WATER_LOW_PCT and _cooldown_ok("water_low"):
            _alert(_phrases_water_low(water_pct), tone="warn")
            alert_fired = True
        elif 0 < water_bal <= _WATER_BALANCE_MARGIN and _cooldown_ok("water_marginal"):
            _alert(_phrases_water_marginal(), tone="warn")
            alert_fired = True
    else:
        if water_bal < 0 and _cooldown_ok("water_deficit"):
            _alert(_phrases_water_deficit(), tone="warn")
            alert_fired = True
        elif 0 <= water_bal <= _WATER_BALANCE_MARGIN and _cooldown_ok("water_marginal"):
            _alert(_phrases_water_marginal(), tone="warn")
            alert_fired = True

    # ── Кислород ────────────────────────────────────────────
    if oxygen_cap > 0:
        if colonists > oxygen_cap and _cooldown_ok("oxygen_critical"):
            _alert(_phrases_oxygen_critical(colonists, oxygen_cap), tone="critical")
            alert_fired = True
        elif oxygen_cap - colonists < _OXYGEN_MARGIN and _cooldown_ok("oxygen_low"):
            _alert(_phrases_oxygen_low(colonists, oxygen_cap), tone="warn")
            alert_fired = True

    # ── Медикаме́нты ─────────────────────────────────────────
    if medical <= _MEDICAL_CRIT and _cooldown_ok("medical_critical"):
        _alert(_phrases_medical_critical(), tone="critical")
        alert_fired = True
    elif medical <= _MEDICAL_LOW and _cooldown_ok("medical_low"):
        _alert(_phrases_medical_low(medical), tone="warn")
        alert_fired = True

    # ── Стройматериалы ──────────────────────────────────────
    if metal <= _MATERIALS_LOW and bioplastic <= _MATERIALS_LOW and _cooldown_ok("materials_low"):
        _alert(_phrases_materials_low(), tone="warn")
        alert_fired = True

    # ── Еда ─────────────────────────────────────────────────
    if low_food and _cooldown_ok("food_low"):
        _alert(_phrases_food_low(), tone="warn")
        alert_fired = True

    if veg <= _FOOD_ITEM_LOW and _cooldown_ok("food_veg_low"):
        _alert(_phrases_food_item_low("Овощей", veg), tone="warn")
        alert_fired = True
    if meat <= _FOOD_ITEM_LOW and _cooldown_ok("food_meat_low"):
        _alert(_phrases_food_item_low("Мяса", meat), tone="warn")
        alert_fired = True
    if meals <= _FOOD_ITEM_LOW and _cooldown_ok("food_meals_low"):
        _alert(_phrases_food_item_low("Готовых блюд", meals), tone="warn")
        alert_fired = True

    # ── Катастрофы ──────────────────────────────────────────
    prev_any_d = _prev.get("any_disaster", False)
    is_weather_hazard = sandstorm or blizzard or (any_d and not solar_flare)

    if any_d and not prev_any_d:
        if is_weather_hazard:
            _engage_yellow_alert()
        if sandstorm:
            _alert(_phrases_sandstorm_start(), tone="alert")
        elif solar_flare:
            _alert(_phrases_solar_flare(), tone="alert")
        elif blizzard:
            _alert(_phrases_blizzard_start(), tone="alert")
        else:
            _alert(_phrases_disaster_generic_start(), tone="alert")
        alert_fired = True
    elif any_d and _cooldown_ok("disaster"):
        if sandstorm:
            _alert(_phrases_sandstorm(), tone="alert")
        elif solar_flare:
            _alert(_phrases_solar_flare(), tone="alert")
        elif blizzard:
            _alert(_phrases_blizzard(), tone="alert")
        else:
            _alert(_phrases_disaster_generic(), tone="alert")
        alert_fired = True
    elif not any_d and prev_any_d:
        _disengage_alert()
        if _cooldown_ok("disaster_end"):
            _alert(_phrases_disaster_end(), tone="good")
        alert_fired = True

    # ── Колони́сты ───────────────────────────────────────────
    prev_col = _prev.get("colonists", colonists)

    if not _first_tick:
        if colonists > prev_col:
            arrived = colonists - prev_col
            _alert(_phrases_arrival(arrived), tone="good")

        elif colonists < prev_col and prev_col > 0:
            lost = prev_col - colonists
            _alert(_phrases_death(lost), tone="warn")
            alert_fired = True

        for milestone in _COLONIST_MILESTONES:
            if prev_col < milestone <= colonists and milestone not in _announced_milestones:
                _announced_milestones.add(milestone)
                _alert(_phrases_milestone(milestone), tone="congrats")
                break

    # ── "Всё спокойно" ──────────────────────────────────────
    if not alert_fired and not any_d and colonists > 0:
        _quiet_streak += 1
    else:
        _quiet_streak = 0

    if _quiet_streak >= 6 and _cooldown_ok("all_quiet"):
        _alert(_phrases_all_quiet(colonists, modules), tone="info")

    _first_tick = False
    _prev = dict(data)


def _monitor_loop():
    while _running:
        try:
            data = telemetry.get()
            _check(data)
        except Exception as e:
            _log.debug("Monitor error: %s", e)
        time.sleep(5)


def start():
    global _thread, _running, _first_tick, _prev, _last_announced, _announced_milestones, _quiet_streak, _auto_alert_engaged

    if not installer.ensure_installed():
        _log.warning("Planetbase mod not installed — monitor running without telemetry")

    telemetry.start()

    if _thread and _thread.is_alive():
        return

    _first_tick           = True
    _prev                 = {}
    _last_announced       = {}
    _announced_milestones = set()
    _quiet_streak         = 0
    _auto_alert_engaged   = False

    _running = True
    _thread  = threading.Thread(target=_monitor_loop, daemon=True, name="PBMonitor")
    _thread.start()
    _log.info("Planetbase monitor started")


def stop():
    global _running
    _running = False
    telemetry.stop()
