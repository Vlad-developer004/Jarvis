import time
from core.nlp import extract_duration_seconds
def handle_yt_control(handler, cmd, text_lower):
    from actions.youtube import control_youtube, open_last_watched_video, open_youtube_channel
    if cmd == 'yt_full':
        control_youtube('fullscreen'); handler.play_response()
    elif cmd == 'yt_fwd':
        control_youtube('forward', extract_duration_seconds(text_lower))
    elif cmd == 'yt_bwd':
        control_youtube('backward', extract_duration_seconds(text_lower))
    elif cmd == 'yt_next':
        if control_youtube('next_video'): handler.play_response()
    elif cmd == 'yt_prev':
        if control_youtube('prev_video'): handler.play_response()
    elif cmd == 'yt_last_watched':
        if open_last_watched_video(): handler.play_response()
    elif cmd == 'yt_channel':
        q = text_lower
        for sw in ['открой канал', 'запусти канал', 'найди канал', 'покажи канал', 'канал']:
            q = q.replace(sw, '')
        q = q.strip()
        if q:
            open_youtube_channel(q); handler.play_response()
        else:
            handler.speak('Какой канал открыть, сэр?')
def handle_volume(handler, cmd, text_lower, amount):
    from actions.volume import change_volume, set_volume_level, mute_volume, switch_audio_output, set_app_volume
    if cmd == 'vol_up':
        change_volume('up', amount or 7); handler.play_response()
    elif cmd == 'vol_down':
        change_volume('down', amount or 7); handler.play_response()
    elif cmd == 'vol_mute':
        mute_volume(True); handler.play_response()
    elif cmd == 'vol_unmute':
        mute_volume(False); handler.play_response()
    elif cmd in ['vol_set', 'vol_max', 'vol_zero']:
        level = 100 if cmd == 'vol_max' else (0 if cmd == 'vol_zero' else amount)
        set_volume_level(level / 100.0); handler.play_response()
    elif cmd == 'audio_switch':
        if switch_audio_output(text_lower): handler.play_response()
        else: handler.speak('Не удалось найти устройство вывода.')
    elif cmd in ['app_vol_up', 'app_vol_down', 'app_vol_set']:
        q = text_lower
        for sw in ['приложения', 'приложение', 'громкость', 'звук', 'сделай', 'установи', 'на', 'в']:
            q = q.replace(sw, '')
        for sw in ['громче', 'тише', 'увеличь', 'убавь', 'поставь', 'минимум', 'максимум']:
            q = q.replace(sw, '')
        app_name = q.strip()
        direction = 'up' if 'up' in cmd else ('down' if 'down' in cmd else 'set')
        if set_app_volume(app_name, direction, amount or 20)[0]: handler.play_response()
