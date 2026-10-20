"""Lookups that need neither yt_dlp nor key presses: YouTube's own search endpoint, and tab-title matching for the browser history."""
import re

import logging
_log = logging.getLogger(__name__)

_session = None
_TITLE_SUFFIX_RE = re.compile(r'(\s+[-–—]\s+(youtube|brave|google chrome|chrome|microsoft edge|edge|opera|mozilla firefox))+\s*$', re.IGNORECASE)


def search_direct(query: str, limit: int) -> list[dict]:
    """Videos for `query` straight from YouTube's own search endpoint: about 0.4 s and no yt_dlp import (~1.3 s through yt_dlp). Any failure
    returns [] so the callers fall back to yt_dlp. Items: {'id','title','url','thumbnail'}."""
    global _session
    try:
        if _session is None:
            import requests
            _session = requests.Session()
        body = {'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20240101.00.00', 'hl': 'ru', 'gl': 'RU'}},
                'query': query, 'params': 'EgIQAQ=='}               # the "videos only" filter
        r = _session.post('https://www.youtube.com/youtubei/v1/search?prettyPrint=false', json=body, timeout=8)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        _log.debug(f'[search_direct] failed: {e}')
        return []
    found = []

    def walk(node):
        if len(found) >= limit:
            return
        if isinstance(node, dict):
            video = node.get('videoRenderer')
            if video and video.get('videoId'):
                thumbs = (video.get('thumbnail') or {}).get('thumbnails') or []
                found.append({
                    'id': video['videoId'],
                    'title': ''.join(run.get('text', '') for run in (video.get('title') or {}).get('runs') or []),
                    'url': f"https://www.youtube.com/watch?v={video['videoId']}",
                    'thumbnail': thumbs[-1].get('url') if thumbs else None,
                })
            else:
                for child in node.values():
                    walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)
    walk(data)
    return found


def page_title_key(title: str) -> str:
    """A tab title reduced to the video's own title: no "(3) " notification count, no " - YouTube - Brave" tail, one case and spacing."""
    t = re.sub(r'^\(\d+\)\s*', '', title or '').strip()
    return re.sub(r'\s+', ' ', _TITLE_SUFFIX_RE.sub('', t)).lower()
