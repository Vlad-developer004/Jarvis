"""ui_next/bridge/ai.py: the AI tab (provider, model, keys that never come back, parameters, test request)."""
import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import ai


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    from features.qa import model_fetcher, llm_processor
    catalog = {'groq': {'llama-a': {'ctx': '128k', 'rpm': 30, 'rpd': 1000, 'alias': 'fast'}, 'llama-b': {'ctx': '8k', 'rpm': 10, 'rpd': 100, 'alias': ''}}, 'openai': {'gpt-x': {'ctx': '1M', 'rpm': 5, 'rpd': 50, 'alias': ''}}}
    monkeypatch.setattr(model_fetcher, 'get_models_for_ui', lambda p: catalog.get(p, {}))
    keys = {}
    monkeypatch.setattr(llm_processor, '_load_api_key', lambda p: keys.get(p, ''))
    monkeypatch.setattr(llm_processor, 'invalidate_clients', lambda p=None: keys.setdefault('_inv', []).append(p))
    written = {}
    import actions.mail_client as mc

    def fake_update(k, v):
        written[k] = v
        keys[{'GROQ_API_KEY': 'groq', 'OPENAI_API_KEY': 'openai'}.get(k, k)] = v
    monkeypatch.setattr(mc, '_update_env_var', fake_update)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    return {'keys': keys, 'written': written, 'fetch': model_fetcher}


def run(**kw):
    return bridge.run_command('ai', kw)


def test_state_defaults_and_no_key_in_it(env):
    r = run(op='state')
    assert r['ok'] and r['provider'] == 'groq' and [m['id'] for m in r['models']] == ['llama-a', 'llama-b'] and r['temperature'] == 0.3 and r['max_tokens'] == 250 and r['top_k'] == 40
    assert r['mini_window'] is True and r['web_search'] is False and r['local_url'] == ai.DEFAULT_LOCAL_URL
    assert next(p for p in r['providers'] if p['id'] == 'local')['needs_key'] is False and not any(p['has_key'] for p in r['providers'])


def test_switching_provider_fixes_a_foreign_model(env):
    run(op='model', id='llama-b')
    r = run(op='provider', id='openai')
    assert r['provider'] == 'openai' and r['model'] == 'gpt-x'
    assert run(op='provider', id='nope')['error'] == 'not_found'
    assert run(op='provider', id='groq')['model'] == 'llama-a'


def test_model_keeps_a_custom_id_but_rejects_junk(env):
    assert run(op='model', id='my/custom-model:7b')['model'] == 'my/custom-model:7b'
    assert run(op='model', id='bad id')['error'] == 'bad_value' and run(op='model', id='')['error'] == 'bad_value'


def test_key_is_stored_but_never_returned(env):
    secret = 'gsk_' + 'a1b2c3d4' * 4
    r = run(op='key_save', provider='groq', key=secret)
    assert r['ok'] and next(p for p in r['providers'] if p['id'] == 'groq')['has_key'] is True
    assert env['written'] == {'GROQ_API_KEY': secret} and secret not in repr(r) and secret not in repr(run(op='state'))
    assert None in env['keys']['_inv'] or 'groq' in env['keys']['_inv']
    r = run(op='key_clear', provider='groq')
    assert r['ok'] and env['written']['GROQ_API_KEY'] == '' and not next(p for p in r['providers'] if p['id'] == 'groq')['has_key']


@pytest.mark.parametrize('bad', ['short', 'has space in the middle of it', 'line\nbreak12345', 'ключ-по-русски-12345', 'x' * 500])
def test_key_validation(env, bad):
    assert run(op='key_save', provider='groq', key=bad)['error'] == 'bad_value' and env['written'] == {}


def test_local_url(env):
    assert run(op='local_url', url='http://192.168.1.5:8080/v1')['local_url'] == 'http://192.168.1.5:8080/v1'
    assert run(op='local_url', url='ftp://x')['error'] == 'bad_value' and run(op='local_url', url='http://a b')['error'] == 'bad_value'
    assert run(op='local_url', url='')['local_url'] == ai.DEFAULT_LOCAL_URL


def test_params_are_ranged(env):
    r = run(op='params', temperature=0.55, max_tokens=500, top_k=20)
    assert (r['temperature'], r['max_tokens'], r['top_k']) == (0.55, 500, 20)
    assert run(op='params', temperature=1.5)['error'] == 'bad_value' and run(op='params', max_tokens=10)['error'] == 'bad_value' and run(op='params', top_k=0)['error'] == 'bad_value'
    assert run(op='params')['error'] == 'bad_value' and run(op='params', temperature='x')['error'] == 'bad_value'
    assert run(op='params', max_tokens=300)['temperature'] == 0.55


def test_the_show_everything_switch_reaches_the_fetcher(env, monkeypatch):
    seen = []
    monkeypatch.setattr(env['fetch'], 'fetch_and_cache', lambda p, k, b='', show_all=False: seen.append(show_all) or True)
    env['keys']['groq'] = 'gsk_' + 'z' * 20
    run(op='refresh', provider='groq')
    assert run(op='models_all', on=True)['models_all'] is True
    run(op='refresh', provider='groq')
    assert seen == [False, True]


def test_routing_state_and_switches(env):
    r = run(op='state')
    assert r['fallback']['enabled'] is True and r['budget']['enabled'] is False and r['budget']['usage'][0]['id'] == 'groq'
    assert run(op='fallback', on=False)['fallback']['enabled'] is False
    b = run(op='budget', on=True, limit=50)['budget']
    assert b['enabled'] is True and b['limit'] == 50
    b = run(op='budget', limit_in=5000, limit_out='800')['budget']
    assert (b['limit_in'], b['limit_out'], b['limit']) == (5000, 800, 50) and len(b['days']) == 14 and b['days'][-1]['date'] == __import__('datetime').date.today().isoformat()
    assert run(op='budget', limit_in=-5)['error'] == 'bad_value'
    assert run(op='budget', limit=-1)['error'] == 'bad_value' and run(op='budget', limit='x')['error'] == 'bad_value' and run(op='budget')['error'] == 'bad_value'
    assert run(op='usage_reset')['ok']


def test_flags_and_other_settings_survive(env):
    assert run(op='web_search', on=True)['web_search'] is True and run(op='mini_window', on=False)['mini_window'] is False
    assert sio.read()['keep'] == 1


def test_refresh_needs_a_key_except_for_local(env, monkeypatch):
    assert run(op='refresh', provider='groq')['error'] == 'no_key'
    calls = []
    monkeypatch.setattr(env['fetch'], 'fetch_and_cache', lambda p, k, b='', show_all=False: calls.append((p, k, b)) or True)
    env['keys']['groq'] = 'gsk_' + 'z' * 20
    r = run(op='refresh', provider='groq')
    assert r['ok'] and r['count'] == 2 and calls == [('groq', 'gsk_' + 'z' * 20, '')]
    assert run(op='refresh', provider='local')['ok'] and calls[-1][0] == 'local' and calls[-1][2] == ai.DEFAULT_LOCAL_URL
    monkeypatch.setattr(env['fetch'], 'fetch_and_cache', lambda p, k, b='', show_all=False: False)
    assert run(op='refresh', provider='local')['error'] == 'unreachable' and run(op='refresh', provider='groq')['error'] == 'fetch_failed'


def test_test_request(env, monkeypatch):
    assert run(op='test')['error'] == 'no_key'
    env['keys']['groq'] = 'gsk_' + 'z' * 20
    from features.qa import llm_processor
    monkeypatch.setattr(llm_processor, '_ask_llm_single', lambda *a, **k: 'Готов.')
    r = run(op='test')
    assert r['ok'] and r['reply'] == 'Готов.' and r['ms'] >= 0
    monkeypatch.setattr(llm_processor, '_ask_llm_single', lambda *a, **k: None)
    assert run(op='test')['error'] == 'empty'

    def boom(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(llm_processor, '_ask_llm_single', boom)
    assert run(op='test')['error'] == 'failed'
