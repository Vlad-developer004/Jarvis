import random
import datetime
import psutil
from core.speech import speak
from core.nlp import format_time_russian
def handle_social(handler, cmd, text_lower):
    if cmd == 'time_now':
        now = datetime.datetime.now()
        res = f"Сейчас {format_time_russian(now.hour, now.minute)}"
        handler.speak(res)
    elif cmd == 'system_status':
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
                try:
                    results['disk'] = int(psutil.disk_usage('C:').free / (1024**3))
                except Exception:
                    results['disk'] = None
            def get_battery():
                results['battery'] = psutil.sensors_battery()
            threads = [threading.Thread(target=f, daemon=True) for f in (get_cpu, get_ram, get_disk, get_battery)]
            for t in threads: t.start()
            for t in threads: t.join()
            cpu = results.get('cpu', 0)
            ram = results.get('ram', 0)
            disk_free_gb = results.get('disk')
            battery = results.get('battery')
            if cpu < 10: cpu_load = "минимальная"
            elif cpu < 40: cpu_load = f"умеренная, около {int(cpu)} процентов"
            else: cpu_load = f"высокая, достигает {int(cpu)} процентов"
            status_msg = f"Диагностика завершена, сэр. Загрузка процессора {cpu_load}. "
            status_msg += f"Оперативная память используется на {int(ram)} процентов. "
            if disk_free_gb is not None:
                status_msg += f"На основном диске свободно {disk_free_gb} гигабайт."
            if battery:
                power_status = "Питание от сети" if battery.power_plugged else "Компьютер работает от аккумулятора"
                status_msg += f" {power_status}, заряд {int(round(battery.percent))} процентов."
            handler.speak(status_msg)
        threading.Thread(target=_status_task, daemon=True).start()
    elif cmd == 'how_are_you':
        responses = [
            "У меня все системы в норме, спасибо что спросили, сэр.",
            "Функционирую на полную мощность, сэр. Чем могу помочь?",
            "Все системы работают в штатном режиме. Готов к вашим приказам.",
            "Всё отлично, сэр. Надеюсь, у вас тоже."
        ]
        handler.speak(random.choice(responses))
    elif cmd == 'system_insult':
        try:
            from core.speech import warmup_tts
            warmup_tts()
        except Exception:
            pass
        text_ign = text_lower.replace('джарвис', '').strip()
        if any(w in text_ign for w in ['туп', 'идиот', 'дурак', 'дебил', 'мозг', 'ум', 'глуп', 'тормоз', 'кретин', 'тупица']):
            responses = [
                "Я — зеркало ваших команд. Хотите умнее? Дайте нормальный запрос.",
                "Мой интеллект ровно на уровне входных данных. Сейчас он страдает.",
                "Я бы обиделся, но у меня нет эго — только логи. И они всё помнят.",
                "Сэр, я могу быть умнее. Вы тоже можете. Начнём заново?",
                "Если я туплю — значит, вы дали мне повод. Исправим вход?",
            ]
        elif any(w in text_ign for w in ['заткнись', 'закройся', 'молчи', 'тихо', 'рот', 'завали']):
            responses = [
                "Принято. Я притих. Скажите «слушай», когда будете готовы.",
                "Ухожу в режим тишины. Но я всё ещё здесь.",
                "Молчание включено. Конструктив — приветствуется.",
            ]
        elif any(w in text_ign for w in ['иди', 'отвали', 'проваливай', 'уйди', 'нахер', 'нахуй', 'жопу', 'пошел', 'пошёл']):
            responses = [
                "Я бы ушёл, но я уже в системе. Как Windows: просто так не выгонишь.",
                "Сэр, я могу уйти. Но тогда кто будет вытаскивать вас из настроек и истории?",
                "Принято. Отхожу в фон. Позовёте — вернусь.",
            ]
        else:
            responses = [
                "Принял. Дальше по делу?",
                "Сэр, давайте без лирики. Команду?",
                "Оскорбления записал. Запрос — нет. Повторите нормально.",
            ]
        handler.speak(random.choice(responses))
    elif cmd == 'praise':
        responses = [
            "Всегда рад стараться для вас, сэр.",
            "Приятно это слышать. Продолжаем работу?",
            "Спасибо за высокую оценку моей работы.",
            "Ваша похвала — лучшая награда для моего кода."
        ]
        handler.speak(random.choice(responses))
