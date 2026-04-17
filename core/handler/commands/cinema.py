import threading
from features.cinema import parse_cinema_request, watch_media
def handle_cinema(handler, cmd, text_lower):
    res = parse_cinema_request(text_lower)
    title = res.get('title', '').strip()
    is_series = res.get('type') == 'series'
    season = res.get('season', 1)
    episode = res.get('episode', 1)
    if not title or len(title) < 2:
        handler.speak('Какой фильм или сериал вы хотите посмотреть, сэр?')
        return
    handler.play_response('loading')
    def _task():
        mtype = 'сериал' if is_series else 'фильм'
        handler.speak(f'Ищу {mtype} {title}...')
        ok, url = watch_media(title, is_series, season, episode)
        if not ok:
            handler.speak(f'Извините, сэр, я не смог найти {mtype} {title}.')
    threading.Thread(target=_task, daemon=True).start()
