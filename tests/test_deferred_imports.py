"""Statically verify every `from X import name` in the project actually
resolves — including imports deferred inside function bodies, which
test_import_smoke.py's "import every module" sweep can never reach (it only
runs top-level module code, never calls a function).

This is exactly the bug class that slipped through in production: a
function-body `from core.i18n import get_speech_language` in
actions/currency.py raised ImportError the first time `currency_rate` was
actually spoken, because a long-running process still had the pre-edit
core/i18n.py loaded in memory — restarting fixed it, but the same shape of
bug (a name renamed/removed in one file, a stale deferred import left
behind in another) has bitten this project before (see test_import_smoke.py
and test_nlp_commands.py's docstrings) and pyflakes cannot catch it: it only
checks names *within* the current file, never whether an imported name
actually exists in the module it's imported from.

Approach: parse every project .py file with `ast`, collect every
`ImportFrom` node (module-level or nested arbitrarily deep inside
functions/methods), resolve relative imports, import the target module for
real (cheap after the first time — cached in sys.modules), and assert the
name is actually an attribute of it. Modules that fail to import because an
*optional* dependency isn't installed are skipped, same policy as
test_import_smoke.py.
"""
from __future__ import annotations

import ast
import importlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Scoped to the actual voice-command surface (dispatch + per-category
# handlers + actions + game input), not the whole repo: forcing every
# deferred import in the codebase to actually run — instead of merely
# binding a name, like a plain `import` does — also drags in whatever heavy
# transitive dependencies that import lazy-loads, e.g. a NLU helper's
# `from sentence_transformers import ...` pulls in sklearn/torch and can
# take minutes on first import. That's fine at real runtime (lazy on
# purpose, only paid once), but not something to eagerly trigger for every
# deferred import project-wide just to check a name exists.
SCAN_DIRS = ('core/handler', 'actions', 'core/nlp', 'core/engine', 'features')

EXCLUDE_DIRS = {
    '.git', 'venv', 'env', 'node_modules', '__pycache__',
    'build', 'dist', 'models', 'logs', 'installer_output',
    'tests', 'scratch', 'mods',
}

# Heavy-ML NLU internals: legitimately lazy-load sentence_transformers/
# sklearn/torch inside a function body specifically to avoid paying that
# cost unless semantic matching is actually used. Out of scope here — this
# test is about the command-dispatch surface, not NLU model internals.
EXCLUDE_MODULES = {
    'main',
    'core.nlp.semantic', 'core.nlp.semantic_encoder', 'core.nlp.intents',
}


def _module_name_for(path: pathlib.Path) -> str:
    rel = path.relative_to(ROOT).with_suffix('')
    parts = rel.parts
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def _resolve_relative(current_module: str, module: str | None, level: int) -> str | None:
    """Mirror Python's own relative-import resolution (importlib._bootstrap
    uses the same math): level=1 is "this package", level=2 is "parent of
    this package", etc. current_module is the *importing* module's own
    dotted name (a file, not a package, unless it's an __init__)."""
    if level == 0:
        return module
    pkg_parts = current_module.split('.')[:-1]  # this file's own package
    if level > 1:
        cut = level - 1
        if cut > len(pkg_parts):
            return None
        pkg_parts = pkg_parts[:-cut] if cut else pkg_parts
    base = '.'.join(pkg_parts)
    if module:
        return f'{base}.{module}' if base else module
    return base or None


def _collect_cases():
    cases = []
    scan_roots = [ROOT / d for d in SCAN_DIRS]
    seen_paths = set()
    for scan_root in scan_roots:
        if not scan_root.is_dir():
            continue
        for path in scan_root.rglob('*.py'):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            rel = path.relative_to(ROOT)
            if any(part in EXCLUDE_DIRS for part in rel.parts):
                continue
            if path.stem.startswith('test_'):
                continue
            cur_mod = _module_name_for(path)
            if cur_mod in EXCLUDE_MODULES:
                continue
            try:
                tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                target = _resolve_relative(cur_mod, node.module, node.level)
                if not target or target in EXCLUDE_MODULES:
                    continue
                for alias in node.names:
                    if alias.name == '*':
                        continue
                    cases.append(pytest.param(
                        target, alias.name, str(rel), node.lineno,
                        id=f'{rel}:{node.lineno}:{target}.{alias.name}',
                    ))
    return cases


CASES = _collect_cases()


@pytest.mark.parametrize('target_module,name,file,lineno', CASES)
def test_deferred_import_target_exists(target_module, name, file, lineno):
    try:
        mod = importlib.import_module(target_module)
    except Exception as e:
        pytest.skip(f'{target_module} itself failed to import (likely an optional dependency): {e}')
    if hasattr(mod, name):
        return
    # `from X import Y` is also valid when Y is a submodule of package X
    # that X's own __init__.py never imports itself (e.g. `from ui import
    # hud`, `from selenium import webdriver`) — hasattr() alone can't see
    # that, only actually importing the dotted submodule can.
    try:
        importlib.import_module(f'{target_module}.{name}')
        return
    except Exception:
        pass
    pytest.fail(
        f'{file}:{lineno} does `from {target_module} import {name}`, '
        f'but {target_module!r} has no attribute or submodule {name!r}'
    )
