"""core.secrets_store: values survive the dotenv parser, cannot inject variables, and a crash keeps the old file."""
import os

import pytest
from dotenv import dotenv_values

from core import secrets_store as ss


def test_round_trip_through_dotenv_with_awkward_characters(tmp_path):
    p = tmp_path / 'secrets.env'
    for value in ['plain', 'with "quotes"', 'back\\slash', 'spaces and #hash', "it's", 'пароль-ё', '', 'a"\\"b']:
        assert ss.set_secret('T_ROUND', value, p)
        assert dotenv_values(p)['T_ROUND'] == value
    os.environ.pop('T_ROUND', None)


def test_a_value_cannot_add_a_second_variable(tmp_path):
    p = tmp_path / 'secrets.env'
    ss.set_secret('A_KEY', 'ok', p)
    assert not ss.set_secret('GROQ_API_KEY', 'x"\nEVIL="1', p)
    assert not ss.set_secret('GROQ_API_KEY', 'x\r\nEVIL=1', p)
    assert dotenv_values(p) == {'A_KEY': 'ok'}
    os.environ.pop('A_KEY', None)


def test_two_keys_with_awkward_values_stay_separate(tmp_path):
    p = tmp_path / 'secrets.env'
    ss.set_secret('A_KEY', 'a"\\"b', p)
    ss.set_secret('B_KEY', 'tail', p)
    assert dotenv_values(p) == {'A_KEY': 'a"\\"b', 'B_KEY': 'tail'}
    for k in ('A_KEY', 'B_KEY'):
        os.environ.pop(k, None)


@pytest.mark.parametrize('bad', ['', '1ABC', 'A B', 'A=B', 'A-B', 'A\nB'])
def test_invalid_names_are_refused(tmp_path, bad):
    assert not ss.set_secret(bad, 'v', tmp_path / 's.env')
    assert not (tmp_path / 's.env').exists()


def test_exact_key_match_only(tmp_path):
    p = tmp_path / 'secrets.env'
    p.write_text('# comment\nJARVIS_IMAP_PASS_2="second"\nexport JARVIS_IMAP_PASS="old"\n\nOTHER=1\n', encoding='utf-8')
    ss.set_secret('JARVIS_IMAP_PASS', 'new', p)
    text = p.read_text(encoding='utf-8')
    assert '# comment' in text and 'OTHER=1' in text
    assert dotenv_values(p) == {'JARVIS_IMAP_PASS_2': 'second', 'JARVIS_IMAP_PASS': 'new', 'OTHER': '1'}
    assert text.count('JARVIS_IMAP_PASS=') == 1
    os.environ.pop('JARVIS_IMAP_PASS', None)


def test_a_crash_while_replacing_keeps_the_old_file_and_leaves_no_temp(tmp_path, monkeypatch):
    p = tmp_path / 'secrets.env'
    p.write_text('KEEP="me"\n', encoding='utf-8')

    def boom(src, dst):
        raise OSError('disk full')
    monkeypatch.setattr(ss.os, 'replace', boom)
    assert not ss.set_secret('NEW_KEY', 'v', p)
    assert p.read_text(encoding='utf-8') == 'KEEP="me"\n'
    assert [f.name for f in tmp_path.iterdir()] == ['secrets.env']
    assert 'NEW_KEY' not in os.environ


def test_environment_is_updated_after_a_successful_write(tmp_path, monkeypatch):
    monkeypatch.delenv('T_KEY', raising=False)
    assert ss.set_secret('T_KEY', 'v1', tmp_path / 's.env') and os.environ['T_KEY'] == 'v1'
    monkeypatch.delenv('T_KEY')


def test_mail_client_helper_uses_the_store(tmp_path, monkeypatch):
    from actions import mail_client
    monkeypatch.setattr(mail_client, 'get_secrets_path', lambda: str(tmp_path / 's.env'))
    assert mail_client._update_env_var('JARVIS_IMAP_USER', 'me@x.test') is True
    assert dotenv_values(tmp_path / 's.env')['JARVIS_IMAP_USER'] == 'me@x.test'
    monkeypatch.delenv('JARVIS_IMAP_USER', raising=False)
