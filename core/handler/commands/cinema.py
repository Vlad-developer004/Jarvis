import threading
from features.cinema import parse_cinema_request, watch_media
from core.responses import spk
def handle_cinema(handler, cmd, text_lower):
    res = parse_cinema_request(text_lower)
    title = res.get('title', '').strip()
    is_series = res.get('type') == 'series'
    season = res.get('season', 1)
    episode = res.get('episode', 1)
    if not title or len(title) < 2:
        handler.speak(spk('cinema.ask'))
        handler._set_interactive('cinema_ask', {'is_series': is_series, 'season': season, 'episode': episode}, timeout=20.0)
        return
    handler.play_response('loading')
    def _task():
        mtype = 'сериал' if is_series else 'фильм'
        handler.speak(spk('cinema.searching', type=mtype, title=title))
        ok, url = watch_media(title, is_series, season, episode)
        if not ok:
            handler.speak(spk('cinema.not_found', type=mtype, title=title))
    threading.Thread(target=_task, daemon=True).start()
