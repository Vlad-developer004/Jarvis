from actions.screenshot import (
    screenshot_screen, screenshot_terminal, screenshot_full_page,
    start_video_recording, handle_stop_video_cmd
)
from actions.youtube import save_current_video, open_saved_video, download_youtube_video
from actions.system import open_latest_clipchamp_video, open_last_video_file, find_and_paste_file
def handle_video(handler, cmd, text_lower):
    print(f'[VIDEO] cmd={cmd!r}', flush=True)
    if cmd == 'screenshot':
        if screenshot_screen()[0]: handler.play_response()
    elif cmd == 'screenshot_terminal':
        if screenshot_terminal()[0]: handler.play_response()
    elif cmd == 'screenshot_site':
        if screenshot_full_page()[0]: handler.play_response()
    elif cmd == 'start_video':
        from actions.windows import get_monitors
        with_mic = any(w in text_lower for w in ['микрофон', 'звук'])
        mons = get_monitors()
        if len(mons) <= 1:
            if start_video_recording(with_mic, 0)[0]: handler.play_response()
        else:
            handler.speak('У вас несколько мониторов. На каком записывать?')
            handler._set_interactive({'type': 'video_monitor_select', 'with_mic': with_mic, 'monitors': mons})
    elif cmd == 'stop_video':
        is_cancel = any(w in text_lower for w in ['отмен'])
        handle_stop_video_cmd(is_cancel, handler.speak, handler._set_interactive)
    elif cmd == 'save_video':
        if save_current_video(): handler.play_response()
    elif cmd == 'open_saved':
        import re as _re
        from core.nlp.commands import WORDS_TO_NUM, normalize_numbers
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
        if open_saved_video(index): handler.play_response()
        else: handler.speak('Сохранённое видео не найдено')
    elif cmd == 'clipchamp_last':
        if open_latest_clipchamp_video()[0]: handler.play_response()
    elif cmd == 'download_video':
        handler.play_response('loading')
        ok, res = download_youtube_video()
        if ok: handler.play_response()
        else: handler.speak(f'Ошибка скачивания: {res}')
    elif cmd == 'open_last_video':
        app = 'clipchamp' if 'clip' in text_lower else ('vlc' if 'vlc' in text_lower else 'default')
        ok, res = open_last_video_file(app)
        if ok: handler.play_response()
        else: handler.speak(res)
    elif cmd == 'paste_file' or cmd == 'paste_video':
        ftype = 'video' if 'видео' in text_lower else ('photo' if 'фото' in text_lower else 'document')
        if find_and_paste_file(ftype)[0]: handler.play_response()
    elif cmd == 'ocr_screen':
        from actions.ocr import ocr_from_screenshot
        ok, res = ocr_from_screenshot()
        if ok:
            handler.speak(res)
            handler.play_response()
        else:
            handler.speak(f"Ошибка распознавания: {res}")
    elif cmd == 'ocr_last':
        from actions.ocr import ocr_from_last_screenshot
        ok, res = ocr_from_last_screenshot()
        if ok:
            handler.speak(res)
            handler.play_response()
        else:
            handler.speak(f"Ошибка распознавания: {res}")
