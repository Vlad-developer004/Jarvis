"""The answer card of the new UI: what the old HUD shows in its small answer window (an AI answer streaming in, a picture of the day, a recognised song).

The core calls the same functions as before (ui/hud_ai_window.py: show / text / image / hide); when the new window is connected they land here instead of opening the old Tk window.
State goes out on the sticky `answer` topic: {id, visible, subject, text, image, video}. `image` is a small JPEG as a data URI; a video (the astronomy picture of the day can be one)
is announced with `video: true` and has no picture. The window closes itself after the speech has ended plus a reading pause, like the old one.
"""
from __future__ import annotations

import base64
import io
import logging
import threading
import time

_log = logging.getLogger(__name__)
TEXT_MAX = 6000
IMAGE_SIDE = 420
_lock = threading.Lock()
_state = {'id': 0, 'visible': False, 'subject': '', 'text': '', 'image': '', 'video': False}
_cancel = threading.Event()
_publish = None                      # set by the bridge: callable(topic, payload)


def bind(publish) -> None:
    global _publish
    _publish = publish


def snapshot() -> dict:
    with _lock:
        return dict(_state)


def _emit() -> None:
    pub = _publish
    if pub is not None:
        pub('answer', snapshot())


def data_uri(path: str) -> str:
    """A local picture as a small JPEG data URI; '' when it cannot be read."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            img = img.convert('RGB')
            img.thumbnail((IMAGE_SIDE, IMAGE_SIDE))
            buf = io.BytesIO()
            img.save(buf, 'JPEG', quality=82)
        return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        _log.debug('answer image failed', exc_info=True)
        return ''


def show(subject: str, fetch_image: bool = True) -> None:
    """A new answer (or the same one with a better title): the card opens and the hide timer is cancelled. A new subject clears the picture."""
    global _cancel
    _cancel.set()
    _cancel = threading.Event()
    with _lock:
        fresh = not _state['visible']
        _state['visible'] = True
        if fresh:
            _state['id'] += 1
            _state['text'], _state['video'] = '', False
        _state['subject'] = str(subject or '')[:120]
        _state['image'] = '' if fetch_image or fresh else _state['image']
        sid = _state['id']
    _emit()
    if fetch_image:
        threading.Thread(target=_find_image, args=(str(subject or ''), sid), daemon=True, name='AnswerImage').start()


def _find_image(subject: str, sid: int) -> None:
    try:
        from actions.wiki_image import wiki_image_path
        path = wiki_image_path(subject)
    except Exception:
        path = None
    if path:
        set_image(path, sid)


def _plain(text) -> str:
    """The spoken text carries TTS markup (<break .../>, *emphasis*); the card shows it without."""
    from core.speech.tts import strip_speech_markup
    return strip_speech_markup(str(text or '')).strip()


def set_text(text: str) -> None:
    with _lock:
        if not _state['visible']:
            return
        _state['text'] = _plain(text)[:TEXT_MAX]
    _emit()


def set_image(path: str, sid: int | None = None) -> None:
    uri = data_uri(path)
    with _lock:
        if not uri or not _state['visible'] or (sid is not None and sid != _state['id']):
            return                                       # a late picture of a card that is gone or replaced
        _state['image'], _state['video'] = uri, False
    _emit()


def set_video(path: str) -> None:
    with _lock:
        if not _state['visible']:
            return
        _state['video'], _state['image'] = True, ''
    _emit()


def cancel_hide() -> None:
    global _cancel
    _cancel.set()
    _cancel = threading.Event()


def _speech_busy() -> bool:
    try:
        from core.speech.tts import TTSManager
        mgr = TTSManager()
        return bool(mgr.active_playback or not mgr.queue.empty())
    except Exception:
        return False


def hide(delay_ms: int = 5000) -> None:
    """Closes the card after the speech ends and `delay_ms` of reading time; a new `show` or `cancel_hide` stops it."""
    cancel = _cancel

    def work():
        time.sleep(1.0)                                  # let the speech start
        while _speech_busy():
            if cancel.is_set():
                return
            time.sleep(0.3)
        deadline = time.time() + max(0, delay_ms) / 1000.0
        while time.time() < deadline:
            if cancel.is_set():
                return
            time.sleep(0.1)
        if cancel.is_set():
            return
        with _lock:
            _state['visible'] = False
        _emit()
    if delay_ms <= 0 and not _state['visible']:
        return
    threading.Thread(target=work, daemon=True, name='AnswerHide').start()


def close() -> None:
    """The user dismissed the card."""
    cancel_hide()
    with _lock:
        _state['visible'] = False
    _emit()


def event(kind: str, *args) -> bool:
    """Entry for the core: returns True when the new window took the event (so the old window must stay closed)."""
    fn = {'show': show, 'text': set_text, 'image': set_image, 'video': set_video, 'hide': hide, 'cancel_hide': cancel_hide}.get(kind)
    if fn is None:
        return False
    fn(*args)
    return True
