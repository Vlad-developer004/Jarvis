from actions.screenshot import (
    screenshot_screen, screenshot_terminal, screenshot_full_page,
    start_video_recording, handle_stop_video_cmd
)
from actions.youtube import save_current_video, open_saved_video, download_youtube_video
from actions.system import open_latest_clipchamp_video, open_last_video_file, find_and_paste_file
from core.responses import spk
from core.logging_setup import get_logger as _get_logger
_log = _get_logger('video')

def _screenshot(handler, text_lower):
    if screenshot_screen()[0]: handler.play_response()

def _screenshot_terminal(handler, text_lower):
    if screenshot_terminal()[0]: handler.play_response()

def _screenshot_site(handler, text_lower):
    if screenshot_full_page()[0]: handler.play_response()

def _start_video(handler, text_lower):
    from actions.windows import get_monitors
    with_mic = any(w in text_lower for w in ['микрофон', 'звук'])
    mons = get_monitors()
    if len(mons) <= 1:
        if start_video_recording(with_mic, 0)[0]: handler.play_response()
    else:
        handler.speak(spk('video.ask_monitor_v2'))
        handler._set_interactive({'type': 'video_monitor_select', 'with_mic': with_mic, 'monitors': mons})

def _stop_video(handler, text_lower):
    is_cancel = any(w in text_lower for w in ['отмен'])
    handle_stop_video_cmd(is_cancel, handler.speak, handler._set_interactive)

def _save_video(handler, text_lower):
    if save_current_video(): handler.play_response()

def _open_saved(handler, text_lower):
    import re as _re
    from core.nlp.commands import WORDS_TO_NUM, normalize_numbers
    from core.system import app_state as _app_state
    index = -1
    norm = normalize_numbers(text_lower)
    m = _re.search(r'\b(\d+)\b', norm)
    if m:
        index = int(m.group(1))
    else:
        _extra = {'четвёртое': 4, 'четвертое': 4, 'пятое': 5, 'шестое': 6,
                  'седьмое': 7, 'восьмое': 8, 'девятое': 9, 'десятое': 10,
                  'последнее': -1}
        all_words = sorted(list(WORDS_TO_NUM.items()) + list(_extra.items()),
                           key=lambda x: len(x[0]), reverse=True)
        for word, num in all_words:
            if word in text_lower:
                try:
                    index = int(num)
                    break
                except (ValueError, TypeError):
                    pass
    if open_saved_video(index, background=_app_state.game_mode): handler.play_response()
    else: handler.speak(spk('video.no_saved_v2'))

def _clipchamp_last(handler, text_lower):
    if open_latest_clipchamp_video()[0]: handler.play_response()

def _download_video(handler, text_lower):
    handler.play_response('loading')
    ok, res = download_youtube_video()
    if ok: handler.play_response()
    else: handler.speak(spk('video.download_error_v2', res=res))

def _open_last_video(handler, text_lower):
    app = 'clipchamp' if 'clip' in text_lower else ('vlc' if 'vlc' in text_lower else 'default')
    ok, res = open_last_video_file(app)
    if ok: handler.play_response()
    else: handler.speak(res)

def _paste_file(handler, text_lower):
    ftype = 'video' if 'видео' in text_lower else ('photo' if 'фото' in text_lower else 'document')
    query = text_lower
    for kw in ['вставь файл', 'скинь документ', 'отправь фото', 'прикрепи картинку',
               'вставь фото', 'скинь скрин', 'вставь картинку', 'отправь скриншот',
               'вставь документ', 'вставь', 'скинь', 'закинь', 'прикрепи']:
        if query.startswith(kw):
            query = query[len(kw):].strip()
            break
    if query in ('это', 'последний', 'последнее', 'последнюю', 'крайнее', ''):
        query = None
    if find_and_paste_file(ftype, target_filename=query)[0]:
        handler.play_response()

def _ocr_screen(handler, text_lower):
    from actions.ocr import ocr_from_screenshot
    ok, res = ocr_from_screenshot()
    if ok:
        handler.speak(res)
        handler.play_response()
    else:
        handler.speak(spk('video.ocr_error_v2', res=res))

def _ocr_last(handler, text_lower):
    from actions.ocr import ocr_from_last_screenshot
    ok, res = ocr_from_last_screenshot()
    if ok:
        handler.speak(res)
        handler.play_response()
    else:
        handler.speak(spk('video.ocr_error_v2', res=res))

_VIDEO_ACTIONS = {
    'screenshot': _screenshot,
    'screenshot_terminal': _screenshot_terminal,
    'screenshot_site': _screenshot_site,
    'start_video': _start_video,
    'stop_video': _stop_video,
    'save_video': _save_video,
    'open_saved': _open_saved,
    'clipchamp_last': _clipchamp_last,
    'download_video': _download_video,
    'open_last_video': _open_last_video,
    'paste_file': _paste_file,
    'paste_video': _paste_file,
    'ocr_screen': _ocr_screen,
    'ocr_last': _ocr_last,
}

def handle_video(handler, cmd, text_lower):
    _log.debug('video cmd=%r', cmd)
    action = _VIDEO_ACTIONS.get(cmd)
    if action:
        action(handler, text_lower)
