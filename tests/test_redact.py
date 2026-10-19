"""core.redact: secrets never reach a log or the console through exception text."""
import pytest
import requests

from core.redact import MASK, describe_error, redact

TOKEN = '123456789:AAFxyzABCdef-ghiJKLmno_pqrSTUvwx'


def test_telegram_bot_token_is_masked_in_urls():
    out = redact(f'HTTPSConnectionPool: Max retries with url: /bot{TOKEN}/getUpdates?offset=1')
    assert TOKEN not in out and '/bot' + MASK + '/getUpdates' in out


@pytest.mark.parametrize('text', ['https://x.test/a?key=SECRETVALUE&b=1', 'https://x.test/a?b=1&api_key=SECRETVALUE', 'https://x.test/?access_token=SECRETVALUE'])
def test_secret_query_values_are_masked(text):
    assert 'SECRETVALUE' not in redact(text)
    assert 'x.test' in redact(text)


def test_authorization_header_is_masked():
    assert 'abc.def-ghi' not in redact("{'Authorization': 'Bearer abc.def-ghi'}")


def test_values_of_secret_environment_variables_are_masked(monkeypatch):
    monkeypatch.setenv('JARVIS_IMAP_PASS', 'hunter2-long-pass')
    monkeypatch.setenv('SOME_NAME', 'plain-value-here')
    out = redact('login failed for hunter2-long-pass and plain-value-here')
    assert 'hunter2-long-pass' not in out and 'plain-value-here' in out


def test_normal_text_is_untouched():
    assert redact('Привет, мир: 12:30 /bot is a word') == 'Привет, мир: 12:30 /bot is a word'


def test_a_real_requests_error_does_not_leak_the_token(monkeypatch):
    def boom(url, **kw):
        raise requests.exceptions.ConnectionError(f'HTTPSConnectionPool(host=api.telegram.org): url: /bot{TOKEN}/getUpdates')
    monkeypatch.setattr(requests, 'get', boom)
    try:
        requests.get(f'https://api.telegram.org/bot{TOKEN}/getUpdates')
    except Exception as e:
        text = describe_error(e)
    assert TOKEN not in text and text.startswith('ConnectionError')
