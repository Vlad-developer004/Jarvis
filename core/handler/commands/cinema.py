import threading
from features.cinema import parse_cinema_request, watch_media
from core.responses import spk
def _title(row):
    t = (row.get('title') or '').strip()
    return t if len(t) <= 90 else t[:87].rstrip() + '...'


def _handle_media(handler, cmd, text):
    """What is playing, how long is left, rewind: the player side is actions/now_playing.py, the words are actions/media_phrases.py."""
    from actions import now_playing
    from actions.media_phrases import parse_seek, spoken_duration
    row = now_playing.pick(now_playing.snapshot())
    if row is None:
        handler.speak(spk('cinema.nothing'))
        return
    if cmd == 'cinema_now':
        if row['status'] == 'playing':
            handler.speak(spk('cinema.now_app', title=_title(row), app=row['app_name']) if row['app_name'] and row['app_name'] not in _title(row) else spk('cinema.now', title=_title(row)))
        else:
            handler.speak(spk('cinema.paused', title=_title(row)))
    elif cmd == 'cinema_left':
        if not row['dur']:
            handler.speak(spk('cinema.left_unknown'))
        else:
            handler.speak(spk('cinema.left', left=spoken_duration(max(0.0, row['dur'] - row['pos']))))
    elif cmd == 'cinema_seek':
        req = parse_seek(text)
        if req is None:
            handler.speak(spk('cmd.not_supported'))
            return
        res = now_playing.control('seek_to' if req['mode'] == 'to' else 'seek_by', row['id'], req['seconds'])
        if res.get('ok'):
            amount = spoken_duration(req['seconds'])
            handler.speak(spk('cinema.seek_to' if req['mode'] == 'to' else 'cinema.seek_back' if req['seconds'] < 0 else 'cinema.seek_fwd', amount=amount))
        elif res.get('error') == 'cannot_seek':
            handler.speak(spk('cinema.cannot_seek'))
        else:
            handler.speak(spk('cinema.nothing'))


def _play_local(handler, ep):
    """Starts a library file in the default player; says what it is."""
    from actions import media_library as ml
    if ep.get('episode') is None:
        handler.speak(spk('cinema.local_movie', title=ep['title']))
    else:
        handler.speak(spk('cinema.local_play', title=ep['title'], season=ep['season'], episode=ep['episode']))
    if not ml.play(ep):
        handler.speak(spk('cinema.local_fail', title=ep['title']))


def describe_when(info, title, lang):
    """One spoken sentence about a series from actions/tv_info.lookup (None = no data)."""
    from actions.tv_info import spoken_date
    if not info:
        return spk('cinema.when_nodata', title=title)
    name = info['name']
    if info['next']:
        n = info['next']
        return spk('cinema.when_next', title=name, season=n['season'], episode=n['number'], date=spoken_date(n['airstamp'], lang))
    if info['status'] == 'Ended':
        return spk('cinema.when_ended', title=name)
    p = info['prev']
    return spk('cinema.when_unknown', title=name, date=spoken_date(p['airstamp'], lang) if p else '')


def _handle_when(handler, text):
    """"когда выйдет следующая серия X": the date from TVmaze; without a title, the last series watched from the library."""
    from actions import media_library as ml, tv_info
    from actions.media_phrases import parse_when
    from core.i18n import get_speech_language
    title = (parse_when(text) or {}).get('title', '')
    if not title:
        key = ml.last_series_key()
        ep = ml.next_episode(key) if key else None
        title = ep['title'] if ep else ''
    if not title:
        handler.speak(spk('cinema.when_ask'))
        return
    handler.speak(describe_when(tv_info.lookup(title), title, get_speech_language()))


def _handle_mode(handler, text):
    from actions import cinema_mode
    from actions.media_phrases import parse_mode
    if parse_mode(text) == 'off':
        res = cinema_mode.disable()
        handler.speak(spk('cinema.mode_not_on') if res.get('already') else spk('cinema.mode_off') if res.get('ok') else spk('cinema.mode_fail'))
        return
    res = cinema_mode.enable()
    handler.speak(spk('cinema.mode_already') if res.get('already') else spk('cinema.mode_on', level=cinema_mode.level()) if res.get('ok') else spk('cinema.mode_fail'))


def _handle_later(handler, cmd, text):
    from actions import watch_later
    from actions.media_phrases import parse_later
    if cmd == 'cinema_later_list':
        titles = [i['title'] for i in watch_later.load()]
        handler.speak(spk('cinema.later_list', titles=', '.join(titles[:6])) if titles else spk('cinema.later_empty'))
        return
    req = parse_later(text)
    if req is None:
        handler.speak(spk('cmd.not_supported'))
        return
    res = watch_later.add(req['title'], req['kind'])
    handler.speak(spk('cinema.later_added', title=req['title']) if res.get('ok') else spk('cinema.later_exists', title=req['title']) if res.get('error') == 'exists' else spk('cmd.not_supported'))


def _handle_continue(handler, text):
    """"продолжи сериал X": the episode after the last watched one, from the user's own folders."""
    from actions import media_library as ml
    from actions.media_phrases import parse_continue
    if not ml.folders():
        handler.speak(spk('cinema.local_empty'))
        return
    title = (parse_continue(text) or {}).get('title', '')
    items = ml.scan()
    key = ml.find(title, items) if title else ml.last_series_key()
    if not key:
        handler.speak(spk('cinema.local_none', title=title) if title else spk('cinema.local_no_last'))
        return
    ep = ml.next_episode(key, items)
    if ep is None:
        handler.speak(spk('cinema.local_none', title=title or key))
        return
    _play_local(handler, ep)


def _local_match(title, is_series, season, episode, hint):
    """A library file for "включи фильм X" when the title is in the user's folders and no online service was named; else None."""
    from actions import media_library as ml, cinema_services as cs
    if not ml.folders() or cs.find_service([{'id': p['id'], 'name': p['name'], 'domain': p['domain']} for p in cs.PRESETS], hint):
        return None
    items = ml.scan()
    key = ml.find(title, items)
    if not key:
        return None
    if season or episode:
        return ml.pick_episode(key, season, episode, items)
    return ml.movie_for(key, items) if not is_series and ml.movie_for(key, items) else ml.next_episode(key, items)


def handle_cinema(handler, cmd, text_lower):
    if cmd in ('cinema_now', 'cinema_left', 'cinema_seek'):
        _handle_media(handler, cmd, text_lower)
        return
    if cmd == 'cinema_mode':
        threading.Thread(target=_handle_mode, args=(handler, text_lower), daemon=True).start()
        return
    if cmd in ('cinema_later', 'cinema_later_list'):
        _handle_later(handler, cmd, text_lower)
        return
    if cmd == 'cinema_when':
        threading.Thread(target=_handle_when, args=(handler, text_lower), daemon=True).start()
        return
    if cmd == 'cinema_continue':
        threading.Thread(target=_handle_continue, args=(handler, text_lower), daemon=True).start()
        return
    res = parse_cinema_request(text_lower)
    title = res.get('title', '').strip()
    is_series = res.get('type') == 'series'
    season = res.get('season')
    episode = res.get('episode')
    if not title or len(title) < 2:
        handler.speak(spk('cinema.ask'))
        handler._set_interactive('cinema_ask', {'is_series': is_series, 'season': season, 'episode': episode}, timeout=20.0)
        return
    handler.play_response('loading')
    def _task():
        from features.cinema import plan
        local = _local_match(title, is_series, season, episode, res.get('hint', ''))
        if local:
            _play_local(handler, local)
            return
        mtype = 'сериал' if is_series else ('фильм' if res.get('type') == 'movie' else 'видео')
        svc = plan(title, is_series, season, episode, res.get('hint', ''))['service']
        handler.speak(spk('cinema.searching_on', type=mtype, title=title, service=svc['name']) if svc else spk('cinema.searching', type=mtype, title=title))
        ok, url = watch_media(title, is_series, season, episode, res.get('hint', ''))
        if not ok:
            handler.speak(spk('cinema.not_found', type=mtype, title=title))
    threading.Thread(target=_task, daemon=True).start()
