"""Long-poll Telegram's own getUpdates API directly with the bot's own
token (one bot per user => exactly one consumer per token, no router
needed). Messages from chat_id == TELEGRAM_CHAT_ID are matched through the
same intent path normal voice text takes after ASR.
"""
import json
import logging
import os
import threading

import requests

from config_pack.config import get_data_path

_log = logging.getLogger(__name__)

_MAX_BACKOFF = 60
_OFFSET_FILE = 'remote_telegram_offset.json'

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
        pass
    return 0


def _save_offset(offset: int) -> None:
    try:
        with open(get_data_path(_OFFSET_FILE), 'w', encoding='utf-8') as f:
            json.dump({'offset': offset}, f)
    except Exception:
        pass


def _dispatch(handler, text: str) -> None:
    from core.nlp.commands import match_command
    cmd = match_command(text)
    if not cmd:
        print(f'[REMOTE] no command match for: {text!r}', flush=True)
        return
    print(f'[REMOTE] dispatching cmd={cmd!r} text={text!r}', flush=True)
    handler.handle(cmd, text)


def _get_updates(offset: int, timeout: int) -> list | None:
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    try:
        r = requests.get(url, params={'offset': offset, 'timeout': timeout}, timeout=timeout + 5)
        if r.status_code == 200:
            data = r.json()
            if data.get('ok'):
                return data.get('result', [])
        print(f'[REMOTE] getUpdates HTTP {r.status_code}: {r.text[:200]}', flush=True)
    except Exception as e:
        print(f'[REMOTE] getUpdates failed: {e!r}', flush=True)
    return None


def _poll_loop(handler) -> None:
    from core.system.state import app_state

    offset = _load_offset()
    backoff = 1
    while not _stop_event.is_set():
        updates = _get_updates(offset, timeout=25)
        if updates is None:
            print(f'[REMOTE] poll failed, backing off {backoff}s', flush=True)
            if _stop_event.wait(timeout=backoff):
                break
            backoff = min(backoff * 2, _MAX_BACKOFF)
            continue
        backoff = 1
        chat_id_expected = os.environ.get('TELEGRAM_CHAT_ID', '')
        for update in updates:
            offset = max(offset, update.get('update_id', 0) + 1)
            message = update.get('message') or {}
            chat_id = str(message.get('chat', {}).get('id', ''))
            if chat_id != str(chat_id_expected):
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
