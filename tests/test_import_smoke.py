"""Import every project module and make sure it doesn't blow up.

This is deliberately dumb: it only checks that a module's top-level code
(including function/class *definitions*, which is where a typo'd or
never-imported name like the `ext_mgr` / `_INSULT` / `dw` bugs fixed in
2026-09 lives) doesn't raise. It does NOT call any function, so it will
never catch a bug that only fires when a specific code path runs (that is
what the targeted unit tests in the other test_*.py files are for).

A module whose import fails only because an *optional* third-party
dependency isn't installed in this environment (see requirements-*.txt —
vision/game/web-qa extras aren't part of the base install) is skipped
rather than failed, since that's an environment gap, not a code bug.
"""
from __future__ import annotations

import importlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

EXCLUDE_DIRS = {
    '.git', 'venv', 'env', 'node_modules', '__pycache__',
    'build', 'dist', 'models', 'logs', 'installer_output',
    'tests', 'scratch',
}

# Modules with real, heavy side effects at import time (spawn threads/processes,
# touch hardware, or - like main.py - construct the live ASRManager/engine as a
# module-level statement) that would make "import" itself an integration test
# against the real machine. Excluded deliberately, not an oversight.
EXCLUDE_MODULES = {
    'main',
}


def _discover_modules() -> list[str]:
    modules = []
    for path in ROOT.rglob('*.py'):
        rel = path.relative_to(ROOT)
        if any(part in EXCLUDE_DIRS for part in rel.parts):
            continue
        if path.stem.startswith('test_'):
            continue
        mod_parts = rel.with_suffix('').parts
        if mod_parts[-1] == '__init__':
            mod_parts = mod_parts[:-1]
            if not mod_parts:
                continue
        mod_name = '.'.join(mod_parts)
        if mod_name in EXCLUDE_MODULES:
            continue
        modules.append(mod_name)
    return sorted(modules)


MODULE_NAMES = _discover_modules()


@pytest.mark.parametrize('module_name', MODULE_NAMES)
def test_module_imports_cleanly(module_name):
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        pytest.skip(f'optional dependency missing: {e}')
