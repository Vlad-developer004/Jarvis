"""features/qa/ai_router.py: backup provider, daily budget, spoken notices (providers are faked)."""
import json

import pytest

import core.settings_io as sio
from features.qa import ai_router as r


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"ai_provider": "groq", "ai_model": "m1"}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    keys = {'groq': True, 'openai': True, 'google': False, 'local': False}
    monkeypatch.setattr(r, 'has_key', lambda p: keys.get(p, False))
    monkeypatch.setattr(r, 'daily_limit', lambda p, m, st=None, primary='': {'groq': 10, 'openai': 100}.get(p, 0) if not (st or {}).get('ai_daily_limit') or p != 'groq' else int(st['ai_daily_limit']))
    said = []
    monkeypatch.setattr(r, '_announce', lambda key, **fmt: said.append((key, fmt)))
    return {'path': path, 'keys': keys, 'said': said}


def settings(env, **kw):
    d = json.loads(env['path'].read_text(encoding='utf-8'))
    d.update(kw)
    env['path'].write_text(json.dumps(d), encoding='utf-8')


def fake(replies, seen=None):
    def single(**kw):
        force = kw.pop('_force')
        if seen is not None:
            seen.append(force)
        out = replies.get(force[0], '')
        if isinstance(out, Exception):
            raise out
        return out
    return single


def run(env, replies, announce=True, stream=False, seen=None):
    return r.ask(fake(replies, seen), announce, stream, {'topic': 't', 'question': 'q', 'timeout': 10})


def test_chosen_provider_answers_and_is_counted(env):
    seen = []
    assert run(env, {'groq': 'ответ'}, seen=seen) == 'ответ' and seen == [('groq', 'm1')]
    assert r.usage()['counts'] == {'groq': 1} and env['said'] == []


def test_a_silent_provider_is_replaced_by_the_next_one_with_a_key(env):
    seen = []
    assert run(env, {'groq': '', 'openai': 'из openai'}, seen=seen) == 'из openai'
    assert seen == [('groq', 'm1'), ('openai', '')] and env['said'] == [('ai.switched_error', {'frm': 'Groq', 'to': 'OpenAI'})]
    assert r.usage()['last_switch']['to'] == 'openai'


def test_an_exception_counts_as_silence(env):
    assert run(env, {'groq': RuntimeError('x'), 'openai': 'ok'}) == 'ok'


def test_providers_without_a_key_are_not_tried(env):
    seen = []
    assert run(env, {'groq': ''}, seen=seen) == '' and seen == [('groq', 'm1'), ('openai', '')]


def test_backup_can_be_switched_off(env):
    settings(env, ai_fallback_enabled=False)
    seen = []
    assert run(env, {'groq': '', 'openai': 'x'}, seen=seen) == '' and seen == [('groq', 'm1')]


def test_the_order_is_the_users(env):
    env['keys']['google'] = True
    settings(env, ai_fallback_order=['google', 'openai'])
    seen = []
    run(env, {'groq': '', 'google': '', 'openai': 'x'}, seen=seen)
    assert [p for p, _ in seen] == ['groq', 'google', 'openai']


def test_no_notice_for_silent_callers(env):
    run(env, {'groq': '', 'openai': 'x'}, announce=False)
    assert env['said'] == []


def test_budget_off_ignores_the_limits(env):
    for _ in range(12):
        run(env, {'groq': 'a'})
    assert r.usage()['counts']['groq'] == 12 and env['said'] == []


def test_budget_warns_once_at_eighty_percent_then_moves_on_at_the_limit(env):
    settings(env, ai_budget_enabled=True)
    for _ in range(8):
        run(env, {'groq': 'a', 'openai': 'b'})
    assert env['said'] == [('ai.budget_warn', {'n': 8, 'limit': 10, 'what': 'запросов', 'provider': 'Groq'})]
    run(env, {'groq': 'a'})
    run(env, {'groq': 'a'})
    assert r.usage()['counts']['groq'] == 10 and len(env['said']) == 1
    seen = []
    assert run(env, {'groq': 'a', 'openai': 'b'}, seen=seen) == 'b' and seen == [('openai', '')]
    assert env['said'][-1] == ('ai.switched_limit', {'frm': 'Groq', 'to': 'OpenAI'})


def test_everything_used_up_still_tries_the_chosen_one(env):
    settings(env, ai_budget_enabled=True, ai_fallback_enabled=False)
    for _ in range(10):
        run(env, {'groq': 'a'})
    seen = []
    assert run(env, {'groq': 'still'}, seen=seen) == 'still' and seen == [('groq', 'm1')]


def test_users_own_limit_applies_to_the_chosen_provider(env):
    settings(env, ai_budget_enabled=True, ai_daily_limit=2)
    run(env, {'groq': 'a', 'openai': 'b'})
    run(env, {'groq': 'a', 'openai': 'b'})
    assert run(env, {'groq': 'a', 'openai': 'b'}) == 'b'


def test_a_stream_is_checked_by_its_first_piece(env):
    def gen(*parts):
        return iter(parts)
    out = run(env, {'groq': gen(), 'openai': gen('при', 'вет')}, stream=True)
    assert ''.join(out) == 'привет' and env['said'][0][0] == 'ai.switched_error'
    assert ''.join(run(env, {'groq': gen('a', 'b')}, stream=True)) == 'ab'


def test_all_failing_returns_the_empty_result_of_the_right_kind(env):
    assert run(env, {}) == '' and list(run(env, {}, stream=True)) == []


def test_a_new_day_starts_from_zero(env, monkeypatch):
    run(env, {'groq': 'a'})
    d = r.usage()
    d['date'] = '2000-01-01'
    r._save_usage(d)
    assert r.usage()['counts'] == {}


def test_reset(env):
    run(env, {'groq': 'a'})
    r.reset_usage()
    assert r.usage()['counts'] == {}


def test_ask_llm_goes_through_the_router(env, monkeypatch):
    from features.qa import llm_processor as lp
    monkeypatch.setattr(lp, '_ask_llm_single', lambda **kw: 'x' if kw['_force'][0] == 'groq' else '')
    assert lp.ask_llm('t', 'q') == 'x'


def test_tokens_are_estimated_counted_and_kept_per_day(env):
    r.ask(fake({'groq': 'x' * 300}), False, False, {'topic': 't', 'question': 'вопрос ' * 30, 'timeout': 10})
    d = r.usage()
    assert d['tokens']['groq']['in'] > 0 and d['tokens']['groq']['out'] >= 60
    h = d['history'][d['date']]['groq']
    assert h['req'] == 1 and h['in'] == d['tokens']['groq']['in'] and h['out'] == d['tokens']['groq']['out']
    r.reset_usage()
    assert r.usage()['tokens'] == {} and r.usage()['date'] not in r.usage()['history']


def test_a_stream_is_counted_when_it_ends(env):
    out = run(env, {'groq': iter(['а' * 90, 'б' * 90])}, stream=True)
    assert r.usage()['counts'] == {}
    assert ''.join(out) == 'а' * 90 + 'б' * 90
    assert r.usage()['counts'] == {'groq': 1} and r.usage()['tokens']['groq']['out'] >= 40


def test_token_limits_skip_the_chosen_provider_and_warn(env):
    settings(env, ai_budget_enabled=True, ai_token_limit_out=100)
    run(env, {'groq': 'я' * 600, 'openai': 'b'})
    assert [(k, f['what']) for k, f in env['said']] == [('ai.budget_warn', 'токенов на выход')]
    seen = []
    assert run(env, {'groq': 'a', 'openai': 'b'}, seen=seen) == 'b' and seen == [('openai', '')]


def test_old_history_is_trimmed(env):
    d = r.usage()
    d['history'] = {f'2000-01-{i:02d}': {'groq': {'req': 1, 'in': 1, 'out': 1}} for i in range(1, 29)} | {f'2000-02-{i:02d}': {'groq': {'req': 1, 'in': 1, 'out': 1}} for i in range(1, 10)}
    r._save_usage(d)
    run(env, {'groq': 'a'})
    assert len(r.usage()['history']) == r.HISTORY_DAYS
