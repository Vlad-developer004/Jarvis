"""Stand-in for the Jarvis core: serves scripted live data through the real bridge hub (for UI testing without the full app)."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from ui_next import bridge  # noqa: E402

from ui_next.bridge.hub import Hub  # noqa: E402

def main():
    hub = Hub()
    hub.start()
    hub.write_info()
    bridge._hub = hub
    print('fake core on port', hub.port, flush=True)
    hub.publish('weather', {'ok': True, 'city': 'Берлин', 'temp': 15, 'feels': 14, 'desc': 'Пасмурно', 'code': 3, 'sunrise': '07:12', 'sunset': '18:05', 'wind': 1.2, 'humidity': 77, 'pressure': 761})
    hub.publish('game', {'on': False})
    hub.publish('state', {'mode': 'IDLE'})
    from ui_next.bridge.catalog import build_catalog
    hub.publish('catalog', build_catalog())
    T0 = time.time()
    hub.publish('timers', {'timer': {'label': 'Чай', 'remaining': 600, 'total': 600}, 'reminders': [{'text': 'Созвон с командой', 'at': int((time.time() + 3900) * 1000)}]})
    hub.publish('answer', {'id': 1, 'visible': True, 'subject': 'Марс', 'text': 'Красная планета: четвёртая от Солнца', 'image': '', 'video': False})
    hub.publish('prompt', {'id': 7, 'kind': 'notice', 'open': True, 'timeout': 0, 'data': {'tone': 'info', 'title': 'Напоминание', 'text': 'позвонить маме', 'image': '', 'actions': [{'id': 'snooze5', 'label': 'Отложить на 5 минут'}]}})
    script = [
        ('открой календарь', 'Календарь открыт'),
        ('какая погода в Берлине', 'Сейчас пятнадцать градусов, пасмурно.'),
        ('включи игровой режим', 'Игровой режим включён'),
    ]
    try:
        while True:
            for said, did in script:
                time.sleep(4)
                hub.publish('state', {'mode': 'LISTENING'})
                time.sleep(1.5)
                bridge.heard(said)
                time.sleep(0.4)
                bridge.reply(did)
                hub.publish('state', {'mode': 'SPEAKING'})
                if 'игровой' in said:
                    hub.publish('game', {'on': True})
                time.sleep(2.5)
                hub.publish('state', {'mode': 'IDLE'})
            hub.publish('notices', [{'id': 'mic', 'text': 'Микрофон не отвечает: проверьте подключение', 'sev': 'err'}])
            time.sleep(6)
            hub.publish('notices', [])
            hub.publish('game', {'on': False})
    finally:
        hub.remove_info()


if __name__ == '__main__':
    main()
