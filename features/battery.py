import os
import time
import threading
try:
    import psutil as _psutil
except ImportError:
    _psutil = None
try:
    import pygame as _pygame
except ImportError:
    _pygame = None
last_alert_percent = None
last_alert_time = 0
BATTERY_AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'audio', 'Заряд батареи, %')
BATTERY_FILES = {48: 'Энергия 48% и падает сэр.wav', 19: 'Сэр, энергия 19 %.wav', 15: 'Энергия 15 %.wav', 13: 'Энергия 13%.wav', 11: '11 %.wav', 7: '7 %.wav', 2: '2 %.wav'}
def check_battery_alerts():
    global last_alert_percent, last_alert_time
    was_plugged = True
    from actions.system import activate_economy_mode
    while True:
        try:
            if _psutil is None or _pygame is None:
                break
            battery = _psutil.sensors_battery()
            if battery:
                percent = int(battery.percent)
                plugged = battery.power_plugged
                if was_plugged and (not plugged):
                    activate_economy_mode()
                was_plugged = plugged
                if not plugged:
                    if percent in BATTERY_FILES and percent != last_alert_percent:
                        if time.time() - last_alert_time > 300:
                            file_name = BATTERY_FILES[percent]
                            file_path = os.path.join(BATTERY_AUDIO_DIR, file_name)
                            if os.path.exists(file_path):
                                try:
                                    snd = _pygame.mixer.Sound(file_path)
                                    snd.play()
                                    last_alert_percent = percent
                                    last_alert_time = time.time()
                                except Exception as e:
                                    pass
                else:
                    last_alert_percent = None
        except Exception as e:
            pass
        time.sleep(60)
def start_battery_monitor():
    t = threading.Thread(target=check_battery_alerts, daemon=True)
    t.start()
