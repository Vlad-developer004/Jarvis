"""Telegram remote control: only the owner's chat, only allow-listed commands, and the bot token never reaches a log."""
import logging

import pytest
import requests

from features.remote_control import client

TOKEN = '123456789:AAFxyzABCdef-ghiJKLmno_pqrSTUvwx'
CHAT = '4242'


class Handler:
    def __init__(self):
        self.calls = []

    def handle(self, cmd, text):
        self.calls.append((cmd, text))


def _update(uid, text, chat=CHAT):
    return {'update_id': uid, 'message': {'chat': {'id': int(chat) if str(chat).isdigit() else chat}, 'text': text}}


@pytest.fixture
def match(monkeypatch):
    table = {'тише': 'vol_down', 'выключи компьютер': 'shutdown', 'отключи охрану': 'guard_off', 'удали файл': 'delete_file', 'пауза': 'media_pause'}
    import core.nlp.commands as c
    monkeypatch.setattr(c, 'match_command', lambda t: table.get(t, ''))
    from core.system.state import app_state
    monkeypatch.setattr(app_state, 'remote_control_enabled', True, raising=False)
    return table


def test_allowed_command_from_the_owner_runs(match):
    h = Handler()
    off = client._handle_updates(h, [_update(7, 'тише')], 0, CHAT)
    assert h.calls == [('vol_down', 'тише')] and off == 8


@pytest.mark.parametrize('text', ['выключи компьютер', 'отключи охрану', 'удали файл'])
def test_dangerous_commands_never_run_from_the_chat(match, text):
    h = Handler()
    client._handle_updates(h, [_update(1, text)], 0, CHAT)
    assert h.calls == []


def test_foreign_chat_is_ignored(match):
    h = Handler()
    client._handle_updates(h, [_update(1, 'тише', chat='999')], 0, CHAT)
    assert h.calls == []


def test_empty_chat_id_runs_nothing_even_for_updates_without_a_message(match):
    h = Handler()
    ups = [{'update_id': 1, 'edited_message': {'text': 'тише'}}, _update(2, 'тише', chat='')]
    off = client._handle_updates(h, ups, 0, '')
    assert h.calls == [] and off == 3


def test_updates_without_message_or_text_are_skipped(match):
    h = Handler()
    client._handle_updates(h, [{'update_id': 1, 'callback_query': {}}, {'update_id': 2, 'message': {'chat': {'id': 4242}}}], 0, CHAT)
    assert h.calls == []


def test_remote_control_switch_off_stops_dispatch(match, monkeypatch):
    from core.system.state import app_state
    monkeypatch.setattr(app_state, 'remote_control_enabled', False, raising=False)
    h = Handler()
    client._handle_updates(h, [_update(1, 'тише')], 0, CHAT)
    assert h.calls == []


def test_the_allow_list_has_no_dangerous_command():
    banned = {'shutdown', 'restart', 'shutdown_timer', 'delete_file', 'delete_folder', 'empty_trash', 'guard_off', 'keyboard_lock', 'keyboard_unlock',
              'close_all_win', 'mail_compose', 'git_commit', 'jarvis_exit', 'restart_jarvis', 'system_cleanup', 'system_cleanup_deep', 'create_word_doc'}
    assert not (client.REMOTE_ALLOWED & banned)
    from ui_next.bridge.commands_meta import META
    assert client.REMOTE_ALLOWED <= set(META)


def test_network_error_never_puts_the_token_into_the_log(monkeypatch, caplog, capsys):
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN', TOKEN)

    def boom(url, **kw):
        raise requests.exceptions.ConnectionError(f'Max retries exceeded with url: /bot{TOKEN}/getUpdates')
    monkeypatch.setattr(client.requests, 'get', boom)
    with caplog.at_level(logging.DEBUG):
        assert client._get_updates(0, 1) is None
    out = capsys.readouterr()
    assert TOKEN not in caplog.text and TOKEN not in out.out + out.err
    assert 'ConnectionError' in caplog.text
