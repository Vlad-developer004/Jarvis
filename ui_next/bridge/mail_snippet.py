"""One-line previews for the mail list: built from the head of a letter's body (a few KB fetched with BODY.PEEK, nothing is marked read)."""
from __future__ import annotations

import base64
import html as _html
import re
from email import policy as email_policy
from email.parser import BytesParser

PREVIEW_BYTES = 4000
PREVIEW_CHARS = 140
_DROP_BLOCKS = re.compile(r'(?is)<(style|script|head|title)\b.*?(?:</\1\s*>|$)')
_TAGS = re.compile(r'(?s)<[^>]*>?')
_URLS = re.compile(r'https?://\S+')
_BAR = re.compile(r'[-=_*~#]{4,}')


def _text_of(part) -> str:
    if str(part.get('Content-Transfer-Encoding') or '').strip().lower() == 'base64':
        raw = re.sub(r'[^A-Za-z0-9+/]', '', str(part.get_payload()))
        try:
            data = base64.b64decode(raw[:len(raw) // 4 * 4])
            return data.decode(part.get_content_charset() or 'utf-8', errors='replace').rstrip('�')
        except Exception:
            return ''
    try:
        return str(part.get_content())
    except Exception:
        try:
            payload = part.get_payload(decode=True) or b''
            return payload.decode(part.get_content_charset() or 'utf-8', errors='replace')
        except Exception:
            return ''


def clean(text: str, is_html: bool = False) -> str:
    if is_html:
        text = _TAGS.sub(' ', _DROP_BLOCKS.sub(' ', text))
        text = _html.unescape(text)
    lines = [ln for ln in text.replace('\r', '').split('\n') if not ln.lstrip().startswith('>')]
    text = _BAR.sub(' ', _URLS.sub(' ', ' '.join(lines)))
    text = re.sub(r'[​-‏⁠­﻿͏]', '', text)
    text = ' '.join(text.split())
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS - 1].rstrip() + '…'


def snippet(head: bytes, body: bytes) -> str:
    """`head` holds Content-Type / Content-Transfer-Encoding, `body` is the first bytes of the (possibly multipart) body."""
    try:
        msg = BytesParser(policy=email_policy.default).parsebytes(bytes(head).rstrip() + b'\r\n\r\n' + bytes(body))
        part = msg.get_body(preferencelist=('plain', 'html'))
        if part is None:
            part = msg if msg.get_content_maintype() == 'text' else None
        if part is None:
            return ''
        return clean(_text_of(part), part.get_content_subtype() == 'html')
    except Exception:
        return ''


def parse_fetch(msgdata: list) -> dict[str, tuple[bytes, bytes]]:
    """uid -> (header bytes, text bytes) from `UID FETCH ... (UID BODY.PEEK[HEADER.FIELDS (...)] BODY.PEEK[TEXT]<0.N>)`."""
    out: dict[str, list] = {}
    cur = None
    for item in msgdata or []:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], (bytes, bytearray)):
            head = item[0].decode('ascii', errors='ignore') if isinstance(item[0], bytes) else str(item[0])
            m = re.search(r'UID\s+(\d+)', head, re.I)
            if 'HEADER.FIELDS' in head.upper():
                cur = [m.group(1) if m else '', bytes(item[1]), b'']
                out[id(cur)] = cur
            elif cur is not None:
                cur[2] = bytes(item[1])
        elif isinstance(item, bytes) and cur is not None and not cur[0]:
            m = re.search(rb'UID\s+(\d+)', item, re.I)
            if m:
                cur[0] = m.group(1).decode()
    return {v[0]: (v[1], v[2]) for v in out.values() if v[0]}
