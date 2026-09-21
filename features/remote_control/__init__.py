"""Telegram remote-control: receive text commands from your own bot's chat
and execute them like local voice commands. Uses the same
TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID as features.guard. No-ops if either is
unset so it never affects users who haven't set up Telegram.
"""
import logging
import os

from .client import start_remote_control as _start_client, stop_remote_control

_log = logging.getLogger(__name__)


def start_remote_control(handler) -> None:
    if not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
        return
    try:
        _start_client(handler)
    except Exception:
        _log.exception('remote_control: failed to start')


__all__ = ['start_remote_control', 'stop_remote_control']
