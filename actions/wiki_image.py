"""A picture for the subject of an answer: the first Wikipedia thumbnail that fits, downloaded to the temp folder."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import urllib.parse
import urllib.request

from core.system.version import APP_VERSION

_log = logging.getLogger(__name__)
_EXCLUDED = ('logo', 'icon', 'stub', 'flag', 'map', 'commons', 'star', 'approved', 'important', 'gear', 'wikisource', 'wikimedia', 'shield', 'portal', 'ambox', 'edit-clear')


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
    with urllib.request.urlopen(req, timeout=4) as response:      # nosec B310
        return json.loads(response.read().decode('utf-8'))


def _image_url(subject: str, lang: str) -> str | None:
    api = f'https://{lang}.wikipedia.org/w/api.php'
    data = _get_json(f'{api}?action=query&generator=search&gsrsearch={urllib.parse.quote(subject)}&gsrlimit=3&prop=pageimages&piprop=thumbnail&pithumbsize=400&format=json')
    pages = sorted(data.get('query', {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    if not pages:
        return None
    top = pages[0]
    if top.get('thumbnail', {}).get('source'):
        return top['thumbnail']['source']
    parsed = _get_json(f'{api}?action=parse&page={urllib.parse.quote(top["title"])}&prop=images&format=json')
    names = [n for n in parsed.get('parse', {}).get('images', []) if n.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')) and not any(x in n.lower() for x in _EXCLUDED)]
    if names:
        info = _get_json(f'{api}?action=query&titles=File:{urllib.parse.quote(names[0])}&prop=imageinfo&iiprop=url&format=json')
        for page in info.get('query', {}).get('pages', {}).values():
            files = page.get('imageinfo', [])
            if files and files[0].get('url'):
                return files[0]['url']
    for p in pages[1:]:
        if p.get('thumbnail', {}).get('source'):
            return p['thumbnail']['source']
    return None


def wiki_image_path(subject: str) -> str | None:
    """The local path of a picture for `subject`, or None. Certificates are verified (an unverifiable answer is no answer)."""
    try:
        from core.i18n import get_speech_language
        lang = get_speech_language()
    except Exception:
        lang = 'ru'
    try:
        url = _image_url(subject, lang)
    except Exception as e:
        _log.info('wikipedia search failed: %s', e)
        return None
    if not url or not url.lower().startswith('https://'):
        return None
    try:
        cache = os.path.join(tempfile.gettempdir(), 'jarvis_ai_images')
        os.makedirs(cache, exist_ok=True)
        path = os.path.join(cache, f"img_{hashlib.md5(url.encode('utf-8'), usedforsecurity=False).hexdigest()}{'.png' if '.png' in url.lower() else '.jpg'}")
        if not os.path.exists(path):
            req = urllib.request.Request(url, headers={'User-Agent': f'JarvisOS/{APP_VERSION}'})
            with urllib.request.urlopen(req, timeout=6) as response:      # nosec B310
                data = response.read(8_000_000)
            with open(path, 'wb') as f:
                f.write(data)
        return path
    except Exception as e:
        _log.info('picture download failed: %s', e)
        return None
