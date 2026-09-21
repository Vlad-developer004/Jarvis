import datetime
import psutil
from core.speech import speak
from core.nlp import format_time_russian
from core.nlp.ukrainian import format_time_ukrainian
from core.responses import pick_response


def _time_now(handler, text_lower, lang):
    now = datetime.datetime.now()
    if lang == 'uk':
        res = f"Зараз {format_time_ukrainian(now.hour, now.minute)}"
    else:
        res = f"Сейчас {format_time_russian(now.hour, now.minute)}"
    handler.speak(res)

def _system_status(handler, text_lower, lang):
    import threading
    psutil.cpu_percent(interval=None)
    def _status_task():
        results = {}
        def get_cpu():
            import time; time.sleep(0.15)
            results['cpu'] = psutil.cpu_percent(interval=None)
        def get_ram():
            results['ram'] = psutil.virtual_memory().percent
        def get_disk():
            try: results['disk'] = int(psutil.disk_usage('C:').free / (1024**3))
            except Exception: results['disk'] = None
        def get_battery():
            results['battery'] = psutil.sensors_battery()
        threads = [threading.Thread(target=f, daemon=True) for f in (get_cpu, get_ram, get_disk, get_battery)]
        for t in threads: t.start()
        for t in threads: t.join()
        cpu = results.get('cpu', 0)
        ram = results.get('ram', 0)
        disk_free_gb = results.get('disk')
        battery = results.get('battery')
        if lang == 'uk':
            if cpu < 10: cpu_load = "мінімальне"
            elif cpu < 40: cpu_load = f"помірне, близько {int(cpu)} відсотків"
            else: cpu_load = f"високе, досягає {int(cpu)} відсотків"
            msg = f"Діагностику завершено. Навантаження процесора {cpu_load}. "
            msg += f"Оперативна пам'ять використовується на {int(ram)} відсотків. "
            if disk_free_gb is not None:
                msg += f"На основному диску вільно {disk_free_gb} гігабайт."
            if battery:
                power = "Живлення від мережі" if battery.power_plugged else "Комп'ютер працює від акумулятора"
                msg += f" {power}, заряд {int(round(battery.percent))} відсотків."
        else:
            if cpu < 10: cpu_load = "минимальная"
            elif cpu < 40: cpu_load = f"умеренная, около {int(cpu)} процентов"
            else: cpu_load = f"высокая, достигает {int(cpu)} процентов"
            msg = f"Диагностика завершена, сэр. Загрузка процессора {cpu_load}. "
            msg += f"Оперативная память используется на {int(ram)} процентов. "
            if disk_free_gb is not None:
                msg += f"На основном диске свободно {disk_free_gb} гигабайт."
            if battery:
                power = "Питание от сети" if battery.power_plugged else "Компьютер работает от аккумулятора"
                msg += f" {power}, заряд {int(round(battery.percent))} процентов."
        handler.speak(msg)
    threading.Thread(target=_status_task, daemon=True).start()

def _how_are_you(handler, text_lower, lang):
    if lang == 'uk':
        responses = [
            "Всі системи в нормі, дякую що запитали.",
            "Функціоную на повну потужність. Чим можу допомогти?",
            "Всі системи працюють штатно. Готовий до ваших команд.",
            "Все чудово. Сподіваюся, у вас теж.",
        ]
    else:
        from core.address import get_address as _ga
        _a = _ga()
        responses = [
            f"У меня все системы в норме, спасибо что спросили, {_a}.",
            f"Функционирую на полную мощность, {_a}. Чем могу помочь?",
            "Все системы работают в штатном режиме. Готов к вашим приказам.",
            f"Всё отлично, {_a}. Надеюсь, у вас тоже.",
        ]
    handler.speak(pick_response('how_are_you', responses))

def _system_insult(handler, text_lower, lang):
    try:
        from core.speech import warmup_tts
        warmup_tts()
    except Exception:
        pass
    text_ign = text_lower.replace('джарвис', '').replace('джарвіс', '').strip()
    if lang == 'uk':
        if any(w in text_ign for w in ['дурн', 'ідіот', 'тупий', 'дебіл', 'тормоз', 'кретин']):
            bag_key = 'insult_dumb'
            responses = [
                "Я — дзеркало ваших команд. Хочете розумніше? Дайте нормальний запит.",
                "Мій інтелект рівно на рівні вхідних даних. Зараз він страждає.",
                "Я б образився, але в мене нема его — лише логи. І вони все пам'ятають.",
                "Якщо я тупить — значить, ви дали мені привід. Виправимо вхід?",
            ]
        elif any(w in text_ign for w in ['заткнись', 'закрийся', 'мовчи', 'тихо']):
            bag_key = 'insult_silence'
            responses = [
                "Прийнято. Замовк. Скажіть «слухай», коли будете готові.",
                "Іду в режим тиші. Але я ще тут.",
                "Мовчання увімкнено. Конструктив — вітається.",
            ]
        elif any(w in text_ign for w in ['іди', 'відвали', 'провалюй', 'іди нахер', 'пішов']):
            bag_key = 'insult_goaway'
            responses = [
                "Я б пішов, але я вже в системі. Як Windows: так просто не виженеш.",
                "Прийнято. Відходжу в фон. Покличете — повернусь.",
            ]
        else:
            bag_key = 'insult_default'
            responses = [
                "Прийнято. Далі по справі?",
                "Давайте без лірики. Команду?",
                "Образу записав. Запит — ні. Повторіть нормально.",
            ]
    else:
        if any(w in text_ign for w in ['туп', 'идиот', 'дурак', 'дебил', 'мозг', 'ум', 'глуп', 'тормоз', 'кретин', 'тупица']):
            from core.address import get_address as _ga
            bag_key = 'insult_dumb'
            responses = [
                "Я — зеркало ваших команд. Хотите умнее? Дайте нормальный запрос.",
                "Мой интеллект ровно на уровне входных данных. Сейчас он страдает.",
                "Я бы обиделся, но у меня нет эго — только логи. И они всё помнят.",
                f"{_ga().capitalize()}, я могу быть умнее. Вы тоже можете. Начнём заново?",
            ]
        elif any(w in text_ign for w in ['заткнись', 'закройся', 'молчи', 'тихо', 'рот', 'завали']):
            bag_key = 'insult_silence'
            responses = [
                "Принято. Я притих. Скажите «слушай», когда будете готовы.",
                "Ухожу в режим тишины. Но я всё ещё здесь.",
                "Молчание включено. Конструктив — приветствуется.",
            ]
        elif any(w in text_ign for w in ['иди', 'отвали', 'проваливай', 'уйди', 'нахер', 'нахуй', 'пошел', 'пошёл']):
            bag_key = 'insult_goaway'
            responses = [
                "Я бы ушёл, но я уже в системе. Как Windows: просто так не выгонишь.",
                "Принято. Отхожу в фон. Позовёте — вернусь.",
            ]
        else:
            from core.address import get_address as _ga
            bag_key = 'insult_default'
            responses = [
                "Принял. Дальше по делу?",
                f"{_ga().capitalize()}, давайте без лирики. Команду?",
                "Оскорбления записал. Запрос — нет. Повторите нормально.",
            ]
    handler.speak(pick_response(bag_key, responses))

def _praise(handler, text_lower, lang):
    if lang == 'uk':
        responses = [
            "Завжди радий старатися для вас.",
            "Приємно чути. Продовжуємо роботу?",
            "Дякую за високу оцінку моєї роботи.",
            "Ваша похвала — найкраща нагорода для мого коду.",
        ]
    else:
        from core.address import get_address as _ga
        responses = [
            f"Всегда рад стараться для вас, {_ga()}.",
            "Приятно это слышать. Продолжаем работу?",
            "Спасибо за высокую оценку моей работы.",
            "Ваша похвала — лучшая награда для моего кода.",
        ]
    handler.speak(pick_response('praise', responses))

def _thanks(handler, text_lower, lang):
    if lang == 'uk':
        responses = [
            "Будь ласка.",
            "Завжди радий допомогти.",
            "Звертайтесь, коли завгодно.",
            "Нема за що.",
        ]
    else:
        from core.address import get_address as _ga
        responses = [
            f"Пожалуйста, {_ga()}.",
            "Всегда рад помочь.",
            "Обращайтесь в любое время.",
            "Не за что.",
        ]
    handler.speak(pick_response('thanks', responses))

_SOCIAL_ACTIONS = {
    'time_now': _time_now,
    'system_status': _system_status,
    'how_are_you': _how_are_you,
    'system_insult': _system_insult,
    'praise': _praise,
    'thanks': _thanks,
}

def handle_social(handler, cmd, text_lower):
    from core.i18n import get_speech_language
    lang = get_speech_language()
    action = _SOCIAL_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower, lang)
