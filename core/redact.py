"""Masks secrets in text before it reaches a log or the console.

Network libraries put the full URL into exception text, and Telegram keeps the bot token inside the URL path,
so an unredacted ``repr(exc)`` leaks the token into the log file.
"""
from __future__ import annotations

import os
import re

MASK = '***'
_TELEGRAM_RE = re.compile(r'(?i)(/bot)\d{3,}:[\w-]{10,}')
_QUERY_RE = re.compile(r'(?i)([?&](?:key|api_key|apikey|token|access_token|password|pass|secret)=)[^&\s\'"]+')
_AUTH_RE = re.compile(r'(?i)(authorization["\']?\s*[:=]\s*["\']?(?:bearer|basic)\s+)[\w.~+/=-]+')
_SECRET_ENV_RE = re.compile(r'(?i)(pass(word|wd)?|token|secret|api[_-]?key)')
_MIN_SECRET_LEN = 6


def _env_secrets() -> list[str]:
    return [v for k, v in os.environ.items() if v and len(v) >= _MIN_SECRET_LEN and _SECRET_ENV_RE.search(k)]


def redact(text: object) -> str:
    """Returns ``text`` with bot tokens, secret query values, auth headers and the values of secret environment variables masked."""
    s = str(text)
    s = _TELEGRAM_RE.sub(r'\1' + MASK, s)
    s = _QUERY_RE.sub(r'\1' + MASK, s)
    s = _AUTH_RE.sub(r'\1' + MASK, s)
    for secret in _env_secrets():
        if secret in s:
            s = s.replace(secret, MASK)
    return s


def describe_error(exc: BaseException) -> str:
    """A log-safe one-liner for an exception: its type and the redacted message."""
    return f'{type(exc).__name__}: {redact(exc)}'
