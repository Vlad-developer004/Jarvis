"""Long-poll Telegram's own getUpdates API directly with the bot's own
token (one bot per user => exactly one consumer per token, no router
needed). Messages from chat_id == TELEGRAM_CHAT_ID are matched through the
same intent path normal voice text takes after ASR.

Only commands in REMOTE_ALLOWED run from the chat: a hijacked Telegram account must not be able to power off the PC,
delete files or switch the guard off. Everything else needs the owner at the computer.
"""
import json
import logging
import os
import threading

import requests

from config_pack.config import get_data_path
from core.redact import describe_error
from core.safe import swallow as _swallow

_log = logging.getLogger(__name__)

_MAX_BACKOFF = 60
_OFFSET_FILE = 'remote_telegram_offset.json'

# Safe from afar: media, volume, brightness, timers, information. No power, files, windows, mail, guard or typing.
REMOTE_ALLOWED = frozenset({
    'media_pause', 'media_play', 'media_pause_browser', 'media_play_browser', 'media_pause_youtube', 'media_play_youtube',
    'yt_next', 'yt_prev', 'yt_fwd', 'yt_bwd',
    'vol_up', 'vol_down', 'vol_set', 'vol_max', 'vol_zero', 'vol_mute', 'vol_unmute',
    'brightness_up', 'brightness_down', 'brightness_set',
    'timer_set', 'timer_add', 'timer_sub', 'timer_cancel', 'cancel_timer', 'timer_status', 'reminder', 'cancel_reminder',
    'time_now', 'weather', 'today_summary', 'system_status', 'calendar_next', 'inbox_unread', 'my_ip', 'internet_speed',
    'game_mode_on', 'game_mode_off', 'economy_on', 'economy_off',
})

_stop_event = threading.Event()
_thread: threading.Thread | None = None
_active = False


def _load_offset() -> int:
    try:
        p = get_data_path(_OFFSET_FILE)
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return int(json.load(f).get('offset', 0))
    except Exception:
        _swallow()
    return 0


def _save_offset(offset: int) -> None:
    try:
        with open(get_data_path(_OFFSET_FILE), 'w', encoding='utf-8') as f:
            json.dump({'offset': offset}, f)
    except Exception:
        _swallow()


def _dispatch(handler, text: str) -> bool:
    """Runs the command the text means when it is allowed from afar; returns whether the handler was called."""
    from core.nlp.commands import match_command
    cmd = match_command(text)
    if not cmd:
        _log.info('remote: no command matched')
        return False
    if cmd not in REMOTE_ALLOWED:
        _log.info('remote: command %r is not allowed from the chat', cmd)
        return False
    _log.info('remote: dispatching %r', cmd)
    handler.handle(cmd, text)
    return True


def _get_updates(offset: int, timeout: int) -> list | None:
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    try:
        r = requests.get(url, params={'offset': offset, 'timeout': timeout}, timeout=timeout + 5)  # nosec B113
        if r.status_code == 200:
            data = r.json()
            if data.get('ok'):
                return data.get('result', [])
        _log.warning('remote: getUpdates HTTP %s', r.status_code)
    except Exception as e:
        _log.warning('remote: getUpdates failed: %s', describe_error(e))
    return None


def _handle_updates(handler, updates: list, offset: int, chat_id_expected: str) -> int:
    """Processes one batch and returns the next offset. Nothing runs without a configured chat id."""
    from core.system.state import app_state
    for update in updates:
        offset = max(offset, update.get('update_id', 0) + 1)
        if not chat_id_expected:
            continue
        message = update.get('message') or {}
        chat_id = str(message.get('chat', {}).get('id', ''))
        if not chat_id or chat_id != str(chat_id_expected):
            continue
        text = (message.get('text') or '').strip()
        if not text:
            continue
        if not getattr(app_state, 'remote_control_enabled', True):
            continue
        try:
            _dispatch(handler, text)
        except Exception:
            _log.exception('remote_control: failed to dispatch command')
    return offset


def _poll_loop(handler) -> None:
    offset = _load_offset()
    backoff = 1
    while not _stop_event.is_set():
        updates = _get_updates(offset, timeout=25)
        if updates is None:
            _log.warning('remote: poll failed, backing off %ss', backoff)
            if _stop_event.wait(timeout=backoff):
                break
            backoff = min(backoff * 2, _MAX_BACKOFF)
            continue
        backoff = 1
        offset = _handle_updates(handler, updates, offset, os.environ.get('TELEGRAM_CHAT_ID', '').strip())
        _save_offset(offset)


def start_remote_control(handler) -> None:
    global _thread, _active
    if _active:
        return
    _stop_event.clear()
    _active = True
    _thread = threading.Thread(target=_poll_loop, args=(handler,), daemon=True)
    _thread.start()


def stop_remote_control() -> None:
    global _active
    _stop_event.set()
    _active = False
