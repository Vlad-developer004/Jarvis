import time
import threading
try:
    import psutil as _psutil
except ImportError:
    _psutil = None

last_alert_percent = None
last_alert_time = 0


def get_battery_phrase(percent, lang):
    from core.address import get_address as _ga
    addr = _ga(lang)
    if percent == 90:
        return "Пі 90. Заряд хороший." if lang == 'uk' else "Пи 90. Батарея почти полная."
    elif percent == 50:
        return "Пі 50. Рівно половина заряду." if lang == 'uk' else "Пи 50. Ровно половина заряда."
    elif percent == 20:
        return (
            f"Пі 20. {addr.capitalize()}, виявлено низький рівень заряду. Рекомендую підключити живлення."
            if lang == 'uk' else
            f"Пи 20. {addr.capitalize()}, обнаружен низкий уровень заряда. Рекомендую подключить питание."
        )
    elif percent == 10:
        return (
            "Пі 10. Увага, критичний рівень заряду. Підключіть зарядний пристрій, мої реактори згасають."
            if lang == 'uk' else
            "Пи 10. Внимание, критический уровень заряда. Подключите зарядное устройство, мои реакторы гаснут."
        )
    elif percent == 5:
        return (
            f"Пі 5. Системи на межі, {addr}. Ще трохи, і я засну. Врятуйте мене, підключіть кабель!"
            if lang == 'uk' else
            f"Пи 5. Системы на пределе, {addr}. Ещё немного, и я усну. Спасите меня, подключите кабель!"
        )
    return None


def check_battery_alerts():
    global last_alert_percent, last_alert_time
    was_plugged = True
    from actions.system import activate_economy_mode
    from core.speech import speak
    from core.i18n import get_speech_language

    if _psutil is not None:
        init_bat = _psutil.sensors_battery()
        if init_bat:
            was_plugged = init_bat.power_plugged

    while True:
        try:
            if _psutil is None:
                break
            battery = _psutil.sensors_battery()
            if battery:
                percent = int(battery.percent)
                plugged = battery.power_plugged
                lang = get_speech_language()

                if was_plugged and (not plugged):
                    activate_economy_mode()
                    speak(
                        "Живлення відключено від мережі. Комп'ютер переведено в режим економії енергії."
                        if lang == 'uk' else
                        "Питание отключено от сети. Компьютер переведён в режим экономии энергии."
                    )

                was_plugged = plugged

                if not plugged:
                    if percent in [90, 50, 20, 10, 5] and percent != last_alert_percent:
                        if time.time() - last_alert_time > 300:
                            phrase = get_battery_phrase(percent, lang)
                            if phrase:
                                speak(phrase)
                                last_alert_percent = percent
                                last_alert_time = time.time()
                else:
                    last_alert_percent = None
        except Exception:
            pass
        time.sleep(5)


def start_battery_monitor():
    t = threading.Thread(target=check_battery_alerts, daemon=True)
    t.start()
