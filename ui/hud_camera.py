from __future__ import annotations
from ui.hud_style import JStyle
import threading, time
import tkinter as tk
from core import i18n
from .hud_constants import _CYAN, _WHITE, _AMBER, _DIM, _RED
from .hud_utils import _blend
try:
    import cv2 as _cv2
    _CV2_OK = True
except ImportError:
    _cv2 = None
    _CV2_OK = False
try:
    from PIL import Image, ImageTk
    _PIL_OK = True
except ImportError:
    _PIL_OK = False
def draw_cam_standby(hud) -> None:
    if not hud._cam_placeholder:
        return
    c = hud._cam_placeholder
    c.delete('all')
    w, h = c.winfo_width(), c.winfo_height()
    if w < 10:
        w, h = hud._panel_w - 28, int((hud._panel_w - 28) * 3 / 4)
    cx, cy = w // 2, h // 2
    r = min(w, h) // 4
    c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=_CYAN, width=1, dash=(4, 4))
    _ext = hud._px(15)
    c.create_line(cx - r - _ext, cy, cx + r + _ext, cy, fill=_CYAN, width=1, dash=(2, 2))
    c.create_line(cx, cy - r - _ext, cx, cy + r + _ext, fill=_CYAN, width=1, dash=(2, 2))
    s = hud._px(20)
    for x, y, dx, dy in [(hud._px(10), hud._px(10), 1, 1), (w - hud._px(10), hud._px(10), -1, 1), (hud._px(10), h - hud._px(10), 1, -1), (w - hud._px(10), h - hud._px(10), -1, -1)]:
        c.create_line(x, y, x + dx * s, y, fill=_CYAN, width=2)
        c.create_line(x, y, x, y + dy * s, fill=_CYAN, width=2)
    c.create_text(cx, cy + r + hud._px(35), text=i18n.tr('hud.camera.status.waiting'), fill=_blend(_CYAN, 0.5), font=(hud._F, JStyle.TEXT_SMALL, 'bold'))
    c.create_text(cx, cy + r + hud._px(60), text=i18n.tr('hud.camera.status.signal_not_found'), fill=_RED, font=(hud._F, JStyle.TEXT_TINY))
def toggle_cam(hud) -> None:
    if not _CV2_OK or not _PIL_OK:
        return
    if hud._cam_run:
        hud._cam_run = False
        if hud._cam_btn:
            hud._cam_btn.hud_update(i18n.tr('hud.camera.activate') + ' ', '⦿', _CYAN, icon_fs=22)
        hud.root.after(100, lambda: draw_cam_standby(hud))
    else:
        hud._cam_run = True
        if hud._cam_btn:
            hud._cam_btn.hud_update(i18n.tr('hud.camera.deactivate') + ' ', '◎', _AMBER, icon_fs=22)
        threading.Thread(target=lambda: _cam_thread(hud), daemon=True).start()
def _cam_thread(hud) -> None:
    cap = _cv2.VideoCapture(0)
    if not cap.isOpened():
        hud._cam_run = False
        hud._hud_queue.put(lambda: hud._cam_btn.hud_update(i18n.tr('hud.camera.not_found'), '⚠', _RED))
        return
    cap.set(_cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, 240)
    cap.set(_cv2.CAP_PROP_FPS, 30)
    face_cascade = None
    try:
        import os
        cascade_path = _cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            face_cascade = _cv2.CascadeClassifier(cascade_path)
    except:
        pass
    last_ui_update = 0
    while hud._cam_run and hud.root.winfo_exists():
        ret, frame = cap.read()
        if not ret:
            break
        now = time.time()
        if now - last_ui_update < 0.04:
            continue
        frame = _cv2.flip(frame, 1)
        h_target = max(180, hud._cam_placeholder.winfo_height() - 20)
        aspect = frame.shape[1] / frame.shape[0]
        w_target = int(h_target * aspect)
        frame_small = _cv2.resize(frame, (w_target, h_target))
        frame_small = _cv2.addWeighted(frame_small, 0.8, frame_small, 0, 10)
        if face_cascade:
            gray = _cv2.cvtColor(frame_small, _cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            for (x, y, w, h) in faces:
                _cv2.rectangle(frame_small, (x, y), (x + w, y + h), (255, 255, 0), 1)
                _cv2.line(frame_small, (x, y), (x + 10, y), (255, 255, 0), 2)
                _cv2.line(frame_small, (x, y), (x, y + 10), (255, 255, 0), 2)
        rgb = _cv2.cvtColor(frame_small, _cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        def _update_ui(i=img):
            if not hud._cam_run or not hud.root.winfo_exists(): return
            try:
                hud._cam_img = ImageTk.PhotoImage(image=i)
                if hud._vis_box:
                    hud._vis_box.delete('all')
                    hud._vis_box.create_image(hud._vis_box.winfo_width()//2, hud._vis_box.winfo_height()//2, image=hud._cam_img)
            except: pass
        hud._hud_queue.put(_update_ui)
        last_ui_update = now
        time.sleep(0.01)
    cap.release()
    hud._cam_run = False
    hud._hud_queue.put(lambda: draw_cam_standby(hud))
