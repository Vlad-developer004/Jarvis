"""Shared "search YouTube, then either play the top hit or ask which one"
logic for the two places a song/video name reaches this app:
  - core/handler/dispatch.py's _handle_play_yt (name said up front, e.g.
    "включи песню X")
  - core/handler/interactive.py's _state_play_yt_ask (name given as the
    answer to a "что включить?" follow-up, e.g. plain "включи видео")
Kept in one place so both behave identically and a fix here fixes both —
before this module existed they each carried their own copy of this logic.

Call resolve_and_play_youtube() from your own background thread — it makes
a blocking network search.
"""
from __future__ import annotations
import urllib.parse as _up

from core.logging_setup import get_logger as _get_logger
from core.responses import spk

_log = _get_logger('yt_play')


def _scrape_fallback_url(orig_query: str, is_music: bool) -> str:
    """Old regex-scrape-the-search-page approach — kept as the last resort
    for when yt_dlp's search extraction itself fails (network hiccup,
    YouTube layout change, etc.), so this feature is never less reliable
    than it was before the disambiguation picker was added."""
    url = None
    try:
        import urllib.request as _ur
        import re as _re
        req = _ur.Request(
            f'https://www.youtube.com/results?search_query={_up.quote(orig_query)}',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                     'Accept-Language': 'en-US,en;q=0.9'})
        with _ur.urlopen(req, timeout=8) as r:
            html = r.read().decode('utf-8', errors='ignore')
        ids = list(dict.fromkeys(_re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', html)))
        if ids:
            url = f'https://www.youtube.com/watch?v={ids[0]}'
    except Exception as e:
        _log.warning('scrape-fallback error: %s', e)
    if not url:
        sp = '&sp=EgIQAQ%3D%3D' if is_music else ''
        url = f'https://www.youtube.com/results?search_query={_up.quote(orig_query)}{sp}'
    return url


def resolve_and_play_youtube(handler, query: str, is_music: bool, is_video: bool, background: bool) -> None:
    """Search YouTube for `query`. Plays the top result immediately unless
    several near-duplicate-titled candidates are found (official video /
    lyrics / live / audio versions of one song, or several unrelated
    uploads with near-identical titles) — in that case it speaks a short
    prompt and opens the disambiguation picker (ui/dialogs/yt_picker_dlg.py),
    accepting either a click or a spoken ordinal ("первое"/"второе"/...,
    handled by core/handler/interactive.py's 'yt_pick_ask' state)."""
    from actions.youtube import search_youtube_candidates, candidates_are_ambiguous, _open_youtube_url

    yt_query = query
    if is_music:
        yt_query += ' песня'
    elif is_video:
        yt_query += ' видео'

    candidates = []
    try:
        candidates = search_youtube_candidates(yt_query, limit=5)
    except Exception as e:
        _log.debug(f'[YT-PLAY] candidate search error: {e}')
        _log.warning('candidate search error: %s', e)
    if candidates:
        n_with_thumb = sum(1 for c in candidates if c.get('thumbnail'))
        _log.debug(f'[YT-PLAY] found {len(candidates)} candidates, {n_with_thumb} with a thumbnail url')
        _log.info('found %d candidates, %d with a thumbnail url', len(candidates), n_with_thumb)

    def _play_url(url: str) -> None:
        _open_youtube_url(url, background=background)
        handler.play_response()

    if not candidates:
        _play_url(_scrape_fallback_url(query, is_music))
        return

    if candidates_are_ambiguous(candidates):
        def _on_pick(candidate, idx):
            handler._set_interactive(None)
            handler.speak(spk('yt_picker.picked', n=idx + 1))
            _play_url(candidate['url'])

        def _on_pick_timeout():
            handler._set_interactive(None)
            _play_url(candidates[0]['url'])

        def _on_pick_cancel():
            # Explicit "no" (titlebar X, or 'отмена' by voice) — unlike a
            # real timeout, this must not fall back to playing anything.
            handler._set_interactive(None)

        try:
            from ui_next import host
            handler._set_interactive('yt_pick_ask', {}, timeout=20.0)
            if host.open_yt_picker(candidates, _on_pick, _on_pick_timeout, _on_pick_cancel, timeout_sec=20.0):
                handler.speak(spk('yt_picker.prompt'))
                return
            handler._set_interactive(None)
        except Exception as e:
            _log.warning('picker error: %s', e)
        # no window: fall through to instant top-result playback below.

    _play_url(candidates[0]['url'])
