import threading
import time
import winsound
import os
import requests
from config_pack.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
GUARD_INTERVAL = 4
ALERT_FREQ = 2500
ALERT_DURATION = 1000
SIMILARITY_THRESH = 0.62
MOTION_THRESH = 4000
ALERT_COOLDOWN = 30
_OWNER_PATH = os.path.join('data', 'last_owner.jpg')
_INTRUDER_PATH = os.path.join('data', 'last_intruder.jpg')
_guard_active = False
_guard_thread = None
_stop_flag = False
_stop_event = threading.Event()
_owner_faces = []
def _cascade():
    import cv2
    path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    return cv2.CascadeClassifier(path)
def _capture():
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    time.sleep(0.4)
    ret, frame = cap.read()
    cap.release()
    return frame if ret else None
def _extract_faces(frame):
    import cv2
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    rects = _cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    crops = []
    for x, y, w, h in rects:
        crop = cv2.resize(gray[y:y + h, x:x + w], (128, 128))
        crops.append(cv2.equalizeHist(crop))
    return crops
def _similarity(a, b):
    import cv2
    def hist(img):
        h = cv2.calcHist([img], [0], None, [64], [0, 256])
        cv2.normalize(h, h)
        return h
    return cv2.compareHist(hist(a), hist(b), cv2.HISTCMP_CORREL)
def _is_owner(face):
    if not _owner_faces:
        return True
    return max((_similarity(ref, face) for ref in _owner_faces)) >= SIMILARITY_THRESH
def _motion(prev, curr):
    import cv2
    diff = cv2.absdiff(cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY), cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY))
    _, thr = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    return int(thr.sum()) // 255 > MOTION_THRESH
def _alert(image_path):
    from config_pack.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and image_path and os.path.exists(image_path):
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
            with open(image_path, 'rb') as photo:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': 'Обнаружен посторонний!'}, files={'photo': photo}, timeout=5)
        except Exception:
            pass
    for _ in range(3):
        winsound.Beep(ALERT_FREQ, ALERT_DURATION // 2)
        time.sleep(0.1)
    wav = os.path.join('audio', 'Чего вы пытаетесь добиться сэр.wav')
    if os.path.exists(wav):
        winsound.PlaySound(wav, winsound.SND_FILENAME | winsound.SND_NODEFAULT)
def _guard_loop():
    global _stop_flag
    import cv2
    prev = _capture()
    last_t = 0.0
    while not _stop_flag:
        if _stop_event.wait(timeout=GUARD_INTERVAL):
            break
        frame = _capture()
        if frame is None:
            continue
        if prev is not None and (not _motion(prev, frame)):
            prev = frame
            continue
        prev = frame
        faces = _extract_faces(frame)
        if not faces:
            continue
        if all((_is_owner(f) for f in faces)):
            continue
        now = time.time()
        if now - last_t < ALERT_COOLDOWN:
            continue
        last_t = now
        tmp = os.path.join('data', '_tmp_alert.jpg')
        cv2.imwrite(tmp, frame)
        import shutil
        shutil.move(tmp, _INTRUDER_PATH)
        threading.Thread(target=_alert, args=(_INTRUDER_PATH,), daemon=True).start()
def start_guard():
    global _guard_active, _guard_thread, _stop_flag, _owner_faces
    if _guard_active:
        return (False, 'already active')
    _owner_faces = []
    for attempt in range(4):
        frame = _capture()
        if frame is None:
            return (False, 'camera error')
        faces = _extract_faces(frame)
        if faces:
            _owner_faces.append(faces[0])
            if len(_owner_faces) >= 3:
                break
        time.sleep(0.6)
    if not _owner_faces:
        return (False, 'no face')
    _stop_flag = False
    _stop_event.clear()
    _guard_active = True
    _guard_thread = threading.Thread(target=_guard_loop, daemon=True)
    _guard_thread.start()
    return (True, 'OK')
def stop_guard():
    global _guard_active, _guard_thread, _stop_flag, _owner_faces
    if not _guard_active:
        return (False, 'not active')
    _stop_flag = True
    _stop_event.set()
    _guard_active = False
    _owner_faces = []
    _guard_thread = None
    if os.path.exists(_INTRUDER_PATH):
        try:
            os.remove(_INTRUDER_PATH)
        except Exception:
            pass
    return (True, 'OK')
