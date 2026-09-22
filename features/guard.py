import threading
import time
import os
import requests
from config_pack.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, get_project_root
GUARD_INTERVAL = 4
ALERT_COOLDOWN = 30
DNN_CONF_THRESH = 0.6
# LBPH predict() returns a distance, not a similarity — lower means closer
# match. Values above this are treated as "not the owner".
LBPH_CONF_THRESH = 75.0
_OWNER_PATH = os.path.join('data', 'last_owner.jpg')
_INTRUDER_PATH = os.path.join('data', 'last_intruder.jpg')
_DNN_DIR = os.path.join(get_project_root(), 'models', 'guard_dnn')
_DNN_PROTOTXT = os.path.join(_DNN_DIR, 'deploy.prototxt')
_DNN_WEIGHTS = os.path.join(_DNN_DIR, 'res10_300x300_ssd_iter_140000.caffemodel')
_DNN_PROTOTXT_URL = 'https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt'
_DNN_WEIGHTS_URL = 'https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel'
_guard_active = False
_guard_thread = None
_stop_flag = False
_stop_event = threading.Event()
_owner_faces = []
_recognizer = None
_dnn_net = None
def _ensure_dnn_downloaded():
    # Model files live under models/, which is gitignored like the other
    # speech models (asr.py follows the same download-on-first-use pattern)
    # — they aren't checked into the repo.
    import urllib.request
    os.makedirs(_DNN_DIR, exist_ok=True)
    for path, url in ((_DNN_PROTOTXT, _DNN_PROTOTXT_URL), (_DNN_WEIGHTS, _DNN_WEIGHTS_URL)):
        if os.path.exists(path):
            continue
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        tmp = path + '.part'
        with urllib.request.urlopen(req, timeout=90) as r, open(tmp, 'wb') as f:
            import shutil as _shutil
            _shutil.copyfileobj(r, f, length=1024 * 1024)
        os.replace(tmp, path)
def _face_net():
    global _dnn_net
    import cv2
    if _dnn_net is None:
        _ensure_dnn_downloaded()
        _dnn_net = cv2.dnn.readNetFromCaffe(_DNN_PROTOTXT, _DNN_WEIGHTS)
    return _dnn_net
def _capture():
    import cv2
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        return None
    # Cheap webcams need a few frames to settle exposure/white balance after
    # opening; a single read right away is often dark or garbled.
    frame = None
    for _ in range(3):
        time.sleep(0.2)
        ret, f = cap.read()
        if ret:
            frame = f
    cap.release()
    return frame
def _clahe_gray(gray):
    import cv2
    # Adaptive histogram equalization compensates uneven/low light far better
    # than a global equalizeHist, which washes out contrast in dark frames.
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    return clahe.apply(gray)
def _extract_faces(frame):
    import cv2
    # The SSD face detector is far more tolerant of poor lighting, off-angle
    # faces and partial occlusion than a Haar cascade — the biggest source of
    # the "misjudged owner as stranger" complaints was faces the cascade
    # missed or mislocated on a dim frame, not the comparison step itself.
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    net = _face_net()
    net.setInput(blob)
    detections = net.forward()
    gray_full = _clahe_gray(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    crops = []
    for i in range(detections.shape[2]):
        confidence = float(detections[0, 0, i, 2])
        if confidence < DNN_CONF_THRESH:
            continue
        box = detections[0, 0, i, 3:7] * [w, h, w, h]
        x1, y1, x2, y2 = box.astype(int)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 - x1 < 40 or y2 - y1 < 40:
            continue
        crop = cv2.resize(gray_full[y1:y2, x1:x2], (128, 128))
        crops.append(cv2.equalizeHist(crop))
    return crops
def _train_recognizer(faces):
    import cv2
    import numpy as np
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces, np.array([0] * len(faces)))
    return recognizer
def _is_owner(face):
    if _recognizer is None:
        return True
    _label, confidence = _recognizer.predict(face)
    return confidence <= LBPH_CONF_THRESH
def _alert(image_path):
    from config_pack.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and image_path and os.path.exists(image_path):
        try:
            url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto'
            with open(image_path, 'rb') as photo:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': 'Обнаружен посторонний!'}, files={'photo': photo}, timeout=5)
        except Exception:
            pass
    try:
        from ui import hud as _hud_mod
        h = getattr(_hud_mod, '_hud', None)
        if h:
            from ui.dialogs.guard_alert_dlg import show_guard_alert
            h._hud_queue.put(lambda: show_guard_alert(h, image_path))
    except Exception:
        pass
    from core.speech.sound import play_alert_sound
    play_alert_sound('red_alert')
    from core.speech import speak
    from core.i18n import get_speech_language
    if get_speech_language() == 'uk':
        speak("Порушення зафіксовано. Ви під повним наглядом, дані вже передано власнику. Раджу зникнути — просто зараз.")
    else:
        speak("Нарушение зафиксировано. Вы под полным наблюдением, данные уже переданы владельцу. Советую исчезнуть — сейчас же.")
STRANGER_CONFIRM_FRAMES = 2

def _guard_loop():
    global _stop_flag
    import cv2
    last_t = 0.0
    consec_stranger = 0
    while not _stop_flag:
        if _stop_event.wait(timeout=GUARD_INTERVAL):
            break
        frame = _capture()
        if frame is None:
            print('[GUARD] poll: no camera frame', flush=True)
            continue
        faces = _extract_faces(frame)
        if not faces:
            print('[GUARD] poll: no face detected', flush=True)
            consec_stranger = 0
            continue
        if all((_is_owner(f) for f in faces)):
            print(f'[GUARD] poll: {len(faces)} face(s), recognized as owner', flush=True)
            consec_stranger = 0
            continue
        # A single frame here can still be misjudged on a bad angle or a
        # transient glare. Require it to happen on STRANGER_CONFIRM_FRAMES
        # separate polls (~GUARD_INTERVAL apart) before alerting, instead of
        # firing on the very first miss.
        consec_stranger += 1
        print(f'[GUARD] poll: stranger face ({consec_stranger}/{STRANGER_CONFIRM_FRAMES})', flush=True)
        if consec_stranger < STRANGER_CONFIRM_FRAMES:
            continue
        now = time.time()
        if now - last_t < ALERT_COOLDOWN:
            continue
        last_t = now
        consec_stranger = 0
        tmp = os.path.join('data', '_tmp_alert.jpg')
        cv2.imwrite(tmp, frame)
        import shutil
        shutil.move(tmp, _INTRUDER_PATH)
        threading.Thread(target=_alert, args=(_INTRUDER_PATH,), daemon=True).start()
def start_guard():
    global _guard_active, _guard_thread, _stop_flag, _owner_faces, _recognizer
    if _guard_active:
        return (False, 'already active')
    try:
        _ensure_dnn_downloaded()
    except Exception:
        return (False, 'model download error')
    _owner_faces = []
    camera_failures = 0
    for attempt in range(6):
        frame = _capture()
        if frame is None:
            camera_failures += 1
            time.sleep(0.6)
            continue
        faces = _extract_faces(frame)
        if faces:
            _owner_faces.append(faces[0])
            if len(_owner_faces) >= 3:
                break
        time.sleep(0.6)
    if camera_failures >= 6:
        return (False, 'camera error')
    if not _owner_faces:
        return (False, 'no face')
    _recognizer = _train_recognizer(_owner_faces)
    _stop_flag = False
    _stop_event.clear()
    _guard_active = True
    _guard_thread = threading.Thread(target=_guard_loop, daemon=True)
    _guard_thread.start()
    return (True, 'OK')
def stop_guard():
    global _guard_active, _guard_thread, _stop_flag, _owner_faces, _recognizer
    if not _guard_active:
        return (False, 'not active')
    _stop_flag = True
    _stop_event.set()
    _guard_active = False
    _owner_faces = []
    _recognizer = None
    _guard_thread = None
    if os.path.exists(_INTRUDER_PATH):
        try:
            os.remove(_INTRUDER_PATH)
        except Exception:
            pass
    return (True, 'OK')
