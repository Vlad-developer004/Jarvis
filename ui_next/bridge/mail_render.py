"""Turns a received message into what the Mail screen shows: a sanitized HTML document for the sandboxed reading frame, the plain text
(used for quoting in replies) and the list of attachments.

The HTML is never trusted. Scripts, frames, forms and event attributes are dropped, links are rewritten so that only the bridge opens them
(`data-url`, http(s)/mailto only), remote images stay blocked until the user asks for them, and the frame itself is sandboxed with a CSP
meta tag as a second layer.
"""
from __future__ import annotations

import base64
import re
from html import escape
from html.parser import HTMLParser
from core.safe import swallow as _swallow

MAX_HTML = 1_500_000
MAX_INLINE_IMG = 1_500_000
MAX_INLINE_TOTAL = 6_000_000

_DROP_WITH_CONTENT = {'script', 'iframe', 'frame', 'frameset', 'object', 'embed', 'form', 'title', 'head', 'noscript', 'svg', 'math', 'video',
                      'audio', 'applet', 'template', 'button', 'select', 'textarea', 'canvas', 'map'}
_VOID = {'br', 'hr', 'img', 'col', 'wbr'}
_ALLOWED = {'a', 'abbr', 'b', 'big', 'blockquote', 'br', 'caption', 'center', 'code', 'col', 'colgroup', 'dd', 'div', 'dl', 'dt', 'em', 'font',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i', 'img', 'li', 'ol', 'p', 'pre', 'small', 'span', 'strike', 'strong', 'style', 'sub',
            'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'tr', 'u', 'ul', 's', 'tt', 'wbr', 'section', 'article', 'header', 'footer',
            'main', 'nav', 'aside', 'figure', 'figcaption', 'address', 'cite', 'q', 'mark', 'ins', 'del', 'dfn', 'kbd', 'samp', 'var', 'time'}
_ATTRS = {'alt', 'title', 'width', 'height', 'class', 'align', 'valign', 'bgcolor', 'color', 'face', 'size', 'border', 'cellpadding', 'cellspacing',
          'colspan', 'rowspan', 'dir', 'lang', 'nowrap', 'start', 'type', 'span', 'abbr', 'scope', 'headers'}
_BAD_STYLE = re.compile(r'expression\s*\(|javascript:|behavior\s*:|-moz-binding|position\s*:\s*(?:fixed|absolute)|@import', re.I)
_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/bmp'}
_LINK_SCHEMES = ('http://', 'https://', 'mailto:', 'tel:')

_BASE_CSS = ('html{background:#fff}body{margin:0;padding:18px 22px;background:#fff;color:#1c2733;font:14px/1.55 "Segoe UI",system-ui,Arial,sans-serif;'
             'overflow-wrap:anywhere;word-break:break-word}img{max-width:100%;height:auto}table{max-width:100%}a{color:#0a63c9;text-decoration:underline;cursor:pointer}'
             'blockquote{margin:.6em 0;padding-left:12px;border-left:3px solid #c5d3e0;color:#516273}pre{white-space:pre-wrap}'
             '::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-thumb{background:#b8c6d4;border-radius:6px}')


_CSS_COMMENT = re.compile(r'/\*.*?\*/', re.S)
_CSS_ESCAPE = re.compile(r'\\([0-9a-fA-F]{1,6})\s?|\\(.)', re.S)
_REMOTE_CSS = re.compile(r'url\s*\(|image-set\s*\(|@import|src\s*:', re.I)


def _plain_css(value: str) -> str:
    """The CSS as the browser reads it: comments gone, backslash escapes decoded (hex escapes inside the word url still mean url), so a filter cannot be dodged by spelling."""
    value = _CSS_COMMENT.sub('', value or '')
    return _CSS_ESCAPE.sub(lambda m: chr(int(m.group(1), 16) % 0x110000) if m.group(1) else m.group(2), value).replace(chr(0), '')


def _style_ok(value: str, remote_ok: bool = True) -> bool:
    plain = _plain_css(value)
    if _BAD_STYLE.search(plain):
        return False
    return remote_ok or not _REMOTE_CSS.search(plain)


def _clean_css(css: str) -> str:
    css = re.sub(r'(?i)@import[^;]*;?', '', _plain_css(css))
    return re.sub(r'(?i)[^;{}]*(?:expression\s*\(|javascript:|behavior\s*:|-moz-binding|position\s*:\s*(?:fixed|absolute))[^;}]*;?', '', css)


class _Cleaner(HTMLParser):
    def __init__(self, cids: dict[str, str], allow_images: bool, quote: bool = False):
        super().__init__(convert_charrefs=True)
        self.quote = quote                      # fragment for a reply: real links, no <style>
        self.out: list[str] = []
        self.cids = cids
        self.allow_images = allow_images
        self.blocked = 0
        self._skip_tag = ''
        self._skip_depth = 0
        self._in_style = False

    # -- tags --
    def handle_starttag(self, tag, attrs):
        self._start(tag, attrs, False)

    def handle_startendtag(self, tag, attrs):
        self._start(tag, attrs, True)

    def _start(self, tag, attrs, selfclosing):
        if self._skip_tag:
            if tag == self._skip_tag and not selfclosing:
                self._skip_depth += 1
            return
        if tag in _DROP_WITH_CONTENT:
            if not selfclosing and tag not in _VOID:
                self._skip_tag, self._skip_depth = tag, 1
            return
        if tag not in _ALLOWED:
            return
        if tag == 'style' and self.quote:
            self._skip_tag, self._skip_depth = 'style', 1
            return
        if tag == 'style':
            self._in_style = True
            self.out.append('<style>')
            return
        parts = [tag]
        for name, value in attrs:
            name = (name or '').lower()
            value = value or ''
            if name.startswith('on'):
                continue
            if name == 'style':
                if _style_ok(value, remote_ok=not self.quote):
                    parts.append(f'style="{escape(value, quote=True)}"')
            elif name == 'href' and tag == 'a':
                if value.strip().lower().startswith(_LINK_SCHEMES) and len(value) < 2000:
                    parts.append(f'href="{escape(value.strip(), quote=True)}"' if self.quote else f'href="#" data-url="{escape(value.strip(), quote=True)}"')
            elif name == 'src' and tag == 'img':
                src = self._image(value.strip())
                if src is not None:
                    parts.append(f'src="{escape(src, quote=True)}"')
            elif name in _ATTRS:
                parts.append(f'{name}="{escape(value, quote=True)}"')
        self.out.append('<' + ' '.join(parts) + '>')

    def _image(self, src: str) -> str | None:
        low = src.lower()
        if low.startswith('cid:'):
            return self.cids.get(src[4:].strip('<>'))
        if low.startswith('data:'):
            return src if low.split(';', 1)[0].split(',', 1)[0][5:] in _IMAGE_TYPES else None
        if low.startswith(('http://', 'https://')):
            if self.allow_images:
                return src
            self.blocked += 1
        return None

    def handle_endtag(self, tag):
        if self._skip_tag:
            if tag == self._skip_tag:
                self._skip_depth -= 1
                if self._skip_depth <= 0:
                    self._skip_tag = ''
            return
        if tag == 'style':
            self._in_style = False
            self.out.append('</style>')
        elif tag in _ALLOWED and tag not in _VOID:
            self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._skip_tag:
            return
        self.out.append(_clean_css(data) if self._in_style else escape(data, quote=False))


def sanitize(html: str, cids: dict[str, str] | None = None, allow_images: bool = False) -> tuple[str, int]:
    """Returns (document for the reading frame, number of remote images that were blocked)."""
    p = _Cleaner(cids or {}, allow_images)
    try:
        p.feed(html[:MAX_HTML])
        p.close()
    except Exception:
        return '', 0
    img = "img-src data: http: https:" if allow_images else "img-src data:"
    csp = f"default-src 'none'; {img}; style-src 'unsafe-inline'; font-src data:"
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{csp}">'
           f'<style>{_BASE_CSS}</style></head><body>{"".join(p.out)}</body></html>')
    return doc, p.blocked


# ---- message parsing ----

def _decode_payload(part) -> str:
    try:
        return part.get_content()
    except Exception:
        raw = part.get_payload(decode=True) or b''
        return raw.decode(part.get_content_charset() or 'utf-8', errors='replace')


def _cid_images(msg, wanted: set[str]) -> dict[str, str]:
    out, total = {}, 0
    for part in msg.walk():
        cid = (part.get('Content-ID') or '').strip().strip('<>')
        if not cid or cid not in wanted or part.get_content_maintype() != 'image':
            continue
        ctype = part.get_content_type()
        data = part.get_payload(decode=True) or b''
        if ctype not in _IMAGE_TYPES or len(data) > MAX_INLINE_IMG or total + len(data) > MAX_INLINE_TOTAL:
            continue
        total += len(data)
        out[cid] = f'data:{ctype};base64,{base64.b64encode(data).decode("ascii")}'
    return out


def attachments(msg, referenced: set[str] | None = None) -> list[dict]:
    """Attachment parts in a stable order; the index in this list is how the UI refers to one."""
    referenced = referenced or set()
    out = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        name = part.get_filename()
        disp = (part.get_content_disposition() or '').lower()
        cid = (part.get('Content-ID') or '').strip().strip('<>')
        if cid and cid in referenced:
            continue
        if not name and disp != 'attachment':
            continue
        if part.get_content_type() in ('text/plain', 'text/html') and not name and disp != 'attachment':
            continue
        data = part.get_payload(decode=True) or b''
        out.append({'part': part, 'name': name or 'вложение', 'size': len(data), 'ctype': part.get_content_type()})
    return out


def render(msg, text: str, allow_images: bool = False) -> dict:
    """`text` is the plain version already extracted by actions.mail_client; returns html/blocked/attachments for the UI."""
    html_part = None
    try:
        html_part = msg.get_body(preferencelist=('html',))
    except Exception:
        _swallow()
    doc, blocked, referenced = '', 0, set()
    if html_part is not None:
        raw = _decode_payload(html_part)
        if raw and len(raw) <= MAX_HTML * 2:
            referenced = {m.strip('<>') for m in re.findall(r'(?i)cid:([^"\'\s)>]+)', raw)}
            doc, blocked = sanitize(raw, _cid_images(msg, referenced), allow_images)
    files = [{'name': a['name'], 'size': a['size'], 'type': a['ctype']} for a in attachments(msg, referenced)]
    return {'html': doc, 'blocked': blocked, 'files': files, 'text': text}


def fragment(raw: str) -> str:
    """Sanitizes HTML (a received letter or what the editor produced) into a fragment safe to put into an outgoing message: real links,
    no scripts, frames, forms or <style>."""
    p = _Cleaner({}, True, True)
    try:
        p.feed((raw or '')[:MAX_HTML])
        p.close()
    except Exception:
        return ''
    return ''.join(p.out)


def quote_fragment(msg) -> str:
    """The HTML part of a received message as a fragment to quote inside a reply or forward ('' when it has none)."""
    try:
        part = msg.get_body(preferencelist=('html',))
    except Exception:
        part = None
    if part is None:
        return ''
    raw = _decode_payload(part)
    if not raw or len(raw) > MAX_HTML * 2:
        return ''
    return fragment(raw)
