"""Ratchet: a broad `except Exception: pass` hides failures. New ones are not allowed; the old ones in native Win32/COM/audio code (left
untouched on purpose) are listed in tests/except_budget.json and the number may only go down. Elsewhere use `core.safe.swallow()`."""
import ast
import json
import logging
import os

import pytest

from core import safe

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIRS = ('core', 'actions', 'features', 'ui_next', 'config_pack')
BUDGET = json.load(open(os.path.join(os.path.dirname(__file__), 'except_budget.json'), encoding='utf-8'))


def _broad(handler):
    t = handler.type
    if t is None:
        return True
    names = [t] if not isinstance(t, ast.Tuple) else list(t.elts)
    return any(isinstance(n, ast.Name) and n.id in ('Exception', 'BaseException') for n in names)


def _counts():
    out = {}
    for d in DIRS:
        for base, _dirs, files in os.walk(os.path.join(ROOT, d)):
            if '__pycache__' in base:
                continue
            for name in files:
                if name.endswith('.py'):
                    path = os.path.join(base, name)
                    tree = ast.parse(open(path, encoding='utf-8').read())
                    n = sum(1 for x in ast.walk(tree) if isinstance(x, ast.ExceptHandler) and _broad(x) and len(x.body) == 1 and isinstance(x.body[0], ast.Pass))
                    if n:
                        out[os.path.relpath(path, ROOT).replace(os.sep, '/')] = n
    return out


def test_no_new_silent_broad_excepts():
    over = {f: (n, BUDGET.get(f, 0)) for f, n in _counts().items() if n > BUDGET.get(f, 0)}
    assert not over, f'silent `except Exception: pass` added (now, allowed): {over}; call core.safe.swallow() in the handler instead'


def test_the_budget_only_lists_files_that_still_need_it():
    counts = _counts()
    stale = {f: b for f, b in BUDGET.items() if counts.get(f, 0) < b}
    assert not stale, f'lower these numbers in tests/except_budget.json: {stale}'


def test_swallow_logs_once_per_place_and_never_raises(caplog):
    safe._seen.clear()
    with caplog.at_level(logging.DEBUG):
        for _ in range(10):
            try:
                raise ValueError('boom token=SECRETVALUE')
            except Exception:
                safe.swallow('demo')
    msgs = [r.getMessage() for r in caplog.records if 'ignored ValueError' in r.getMessage()]
    assert len(msgs) == 3 and 'demo' in msgs[0]
    assert all('SECRETVALUE' in m for m in msgs) or all('SECRETVALUE' not in m for m in msgs)
    assert list(safe.stats().values()) == [10]


def test_swallow_outside_an_except_block_is_a_noop():
    safe.swallow()


def test_swallow_masks_secrets(caplog, monkeypatch):
    safe._seen.clear()
    monkeypatch.setenv('SOME_API_KEY', 'abcdef123456')
    with caplog.at_level(logging.DEBUG):
        try:
            raise RuntimeError('failed with key abcdef123456 at /bot123456789:AAFxyzABCdef-ghiJKLmno_pqrSTUvwx/x')
        except Exception:
            safe.swallow()
    text = ' '.join(r.getMessage() for r in caplog.records)
    assert 'abcdef123456' not in text and 'AAFxyz' not in text


@pytest.mark.parametrize('src', ['import os\ntry:\n    os.x()\nexcept Exception:\n    pass\n'])
def test_the_detector_finds_the_pattern(src):
    tree = ast.parse(src)
    assert any(isinstance(x, ast.ExceptHandler) and _broad(x) and isinstance(x.body[0], ast.Pass) for x in ast.walk(tree))
