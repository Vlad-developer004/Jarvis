"""Tests for actions/mail_client.py's pure logic: Gmail defaulting, settings
persistence/password migration, and error-message formatting. No real IMAP/
SMTP connections are made — network-touching functions (unread_count,
list_recent_messages, send_message, etc.) aren't covered here since they'd
require a live mail server; this covers the config/parsing logic that was
previously entirely untested."""
import json
import logging

import pytest
from email.message import EmailMessage

import actions.mail_client as mail_client


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    settings_path = tmp_path / 'jarvis_settings.json'
    monkeypatch.setattr(mail_client, '_SETTINGS_PATH', settings_path)
    monkeypatch.setattr(mail_client, '_update_env_var', lambda k, v: None)
    monkeypatch.delenv('JARVIS_IMAP_PASS', raising=False)
    monkeypatch.delenv('JARVIS_IMAP_USER', raising=False)
    monkeypatch.delenv('JARVIS_IMAP_HOST', raising=False)
    monkeypatch.delenv('JARVIS_SMTP_HOST', raising=False)
    yield settings_path


# ── Gmail defaulting ─────────────────────────────────────────────────

def test_is_gmail_address_recognizes_gmail_and_googlemail():
    assert mail_client._is_gmail_address('User@Gmail.com')
    assert mail_client._is_gmail_address('user@googlemail.com')
    assert not mail_client._is_gmail_address('user@yahoo.com')


def test_apply_gmail_defaults_fills_hosts_and_ports_for_gmail():
    cfg = mail_client._apply_gmail_defaults({'email': 'me@gmail.com'})
    assert cfg['imap_host'] == 'imap.gmail.com'
    assert cfg['smtp_host'] == 'smtp.gmail.com'
    assert cfg['imap_port'] == 993
    assert cfg['smtp_port'] == 587


def test_apply_gmail_defaults_leaves_non_gmail_untouched():
    cfg = mail_client._apply_gmail_defaults({'email': 'me@yahoo.com'})
    assert 'imap_host' not in cfg


def test_apply_gmail_defaults_does_not_override_explicit_hosts():
    cfg = mail_client._apply_gmail_defaults({'email': 'me@gmail.com', 'imap_host': 'custom.example.com'})
    assert cfg['imap_host'] == 'custom.example.com'


# ── get_resolved_mail_config ────────────────────────────────────────

def test_get_resolved_mail_config_returns_none_when_unconfigured(_isolated_settings):
    assert mail_client.get_resolved_mail_config() is None


def test_get_resolved_mail_config_migrates_plaintext_password_to_env(_isolated_settings, monkeypatch):
    migrated = {}
    monkeypatch.setattr(mail_client, '_update_env_var', lambda k, v: migrated.setdefault(k, v))
    _isolated_settings.write_text(json.dumps({
        'mail_account': {'email': 'me@gmail.com', 'password': 'plaintext-secret'},
    }), encoding='utf-8')

    cfg = mail_client.get_resolved_mail_config()

    assert cfg['password'] == 'plaintext-secret'
    assert migrated['JARVIS_IMAP_PASS'] == 'plaintext-secret'
    on_disk = json.loads(_isolated_settings.read_text(encoding='utf-8'))
    assert on_disk['mail_account']['password'] == ''


def test_get_resolved_mail_config_logs_when_scrub_write_fails(_isolated_settings, monkeypatch, caplog):
    _isolated_settings.write_text(json.dumps({
        'mail_account': {'email': 'me@gmail.com', 'password': 'plaintext-secret'},
    }), encoding='utf-8')

    def _boom(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(type(_isolated_settings), 'write_text', _boom)

    with caplog.at_level(logging.ERROR, logger='mail'):
        cfg = mail_client.get_resolved_mail_config()

    assert cfg['password'] == 'plaintext-secret'  # migration still usable this run
    assert any('scrub' in r.message for r in caplog.records)


def test_get_resolved_mail_config_uses_env_password_when_already_migrated(_isolated_settings, monkeypatch):
    monkeypatch.setenv('JARVIS_IMAP_PASS', 'from-env')
    _isolated_settings.write_text(json.dumps({
        'mail_account': {'email': 'me@gmail.com', 'password': ''},
    }), encoding='utf-8')

    cfg = mail_client.get_resolved_mail_config()
    assert cfg['password'] == 'from-env'


def test_get_resolved_mail_config_defaults_smtp_host_from_imap_host(_isolated_settings):
    _isolated_settings.write_text(json.dumps({
        'mail_account': {
            'email': 'me@example.com', 'password': 'x',
            'imap_host': 'imap.example.com', 'smtp_host': '',
        },
    }), encoding='utf-8')
    cfg = mail_client.get_resolved_mail_config()
    assert cfg['smtp_host'] == 'smtp.example.com'


# ── save_mail_account ────────────────────────────────────────────────

def test_save_mail_account_never_writes_password_to_json(_isolated_settings, monkeypatch):
    sent_to_env = {}
    monkeypatch.setattr(mail_client, '_update_env_var', lambda k, v: sent_to_env.setdefault(k, v))

    mail_client.save_mail_account('me@gmail.com', 'super-secret')

    on_disk = json.loads(_isolated_settings.read_text(encoding='utf-8'))
    assert on_disk['mail_account']['password'] == ''
    assert sent_to_env['JARVIS_IMAP_PASS'] == 'super-secret'


def test_save_mail_account_applies_gmail_host_defaults(_isolated_settings):
    mail_client.save_mail_account('me@gmail.com', 'pw')
    on_disk = json.loads(_isolated_settings.read_text(encoding='utf-8'))
    assert on_disk['mail_account']['imap_host'] == 'imap.gmail.com'
    assert on_disk['mail_account']['smtp_host'] == 'smtp.gmail.com'


# ── error formatting ─────────────────────────────────────────────────

def test_format_mail_error_detects_gmail_app_password_case():
    msg = mail_client.format_mail_error(Exception(b'535-5.7.8 Username and Password not accepted. Learn more at\n535 5.7.8  https://support.google.com/mail/?p=BadCredentials g1-20020a1709065c8100b00a5d185833'))
    assert 'пароль приложения' in msg


def test_format_mail_error_detects_authentication_failure():
    msg = mail_client.format_mail_error(Exception('AUTHENTICATIONFAILED'))
    assert 'Ошибка входа' in msg


def test_format_mail_error_detects_dns_lookup_failure():
    msg = mail_client.format_mail_error(Exception('[Errno 11001] getaddrinfo failed'))
    assert 'сервер почты' in msg


def test_format_mail_error_falls_back_to_raw_text_for_unknown_errors():
    msg = mail_client.format_mail_error(Exception('some unrelated network blip'))
    assert msg == 'some unrelated network blip'


def test_raw_error_text_decodes_bytes_args():
    text = mail_client._raw_error_text(Exception(b'raw bytes error'))
    assert text == 'raw bytes error'


# ── header decoding ──────────────────────────────────────────────────

def test_decode_hdr_handles_plain_ascii():
    assert mail_client._decode_hdr('Hello World') == 'Hello World'


def test_decode_hdr_handles_none():
    assert mail_client._decode_hdr(None) == ''


def test_decode_hdr_handles_encoded_word():
    # RFC 2047 encoded "Привет" in UTF-8/base64
    encoded = '=?utf-8?b?0J/RgNC40LLQtdGC?='
    assert mail_client._decode_hdr(encoded) == 'Привет'


# ── body extraction ──────────────────────────────────────────────────

def test_extract_plain_body_from_simple_plain_message():
    msg = EmailMessage()
    msg.set_content('hello there')
    assert mail_client._extract_plain_body(msg).strip() == 'hello there'


def test_extract_plain_body_strips_html_tags_when_only_html_present():
    msg = EmailMessage()
    msg.set_content('<p>Hello <b>world</b></p>', subtype='html')
    body = mail_client._extract_plain_body(msg)
    assert '<' not in body
    assert 'Hello' in body and 'world' in body


def test_extract_plain_body_prefers_plain_part_in_multipart():
    msg = EmailMessage()
    msg.set_content('plain version')
    msg.add_alternative('<p>html version</p>', subtype='html')
    body = mail_client._extract_plain_body(msg)
    assert 'plain version' in body


def test_extract_plain_body_keeps_short_legitimate_plain_reply():
    # Regression: _is_boilerplate() used to flag anything under 40 chars as
    # boilerplate, so a real short reply like this got silently swapped for
    # the HTML alternative instead of showing the actual plain text.
    msg = EmailMessage()
    msg.set_content('Ok, спасибо')
    msg.add_alternative('<p>Ok, спасибо</p>', subtype='html')
    body = mail_client._extract_plain_body(msg)
    assert 'Ok, спасибо' in body


def test_extract_plain_body_falls_back_to_html_for_link_only_plain_stub():
    # Newsletters often leave a link-only text/plain fallback and put the
    # real content only in the HTML alternative — that stub must still be
    # treated as boilerplate and the HTML part used instead.
    msg = EmailMessage()
    msg.set_content('https://example.com/track/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    msg.add_alternative('<p>Real newsletter content goes here</p>', subtype='html')
    body = mail_client._extract_plain_body(msg)
    assert 'Real newsletter content' in body


# ── app-password provider links ─────────────────────────────────────

def test_app_password_url_for_gmail():
    assert 'google.com' in mail_client.app_password_url_for_email('me@gmail.com')


def test_app_password_url_for_yandex():
    assert 'yandex.ru' in mail_client.app_password_url_for_email('me@yandex.ru')


def test_app_password_url_for_mailru():
    assert 'mail.ru' in mail_client.app_password_url_for_email('me@mail.ru')


def test_app_password_url_is_case_insensitive():
    assert mail_client.app_password_url_for_email('ME@GMAIL.COM') == mail_client.app_password_url_for_email('me@gmail.com')


def test_app_password_url_falls_back_for_unknown_domain():
    url = mail_client.app_password_url_for_email('me@some-unknown-provider.example')
    assert url == mail_client._DEFAULT_APP_PASSWORD_PAGE


def test_app_password_url_handles_empty_input():
    url = mail_client.app_password_url_for_email('')
    assert url == mail_client._DEFAULT_APP_PASSWORD_PAGE
