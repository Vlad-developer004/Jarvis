"""File size ratchet (project rule: about 500 lines is a prompt to look at splitting, above 600 is a stop).

Files already above 600 lines are listed in tests/file_size_budget.json with their current length. They may not grow, no new file may
cross 600, and once a file drops to 600 or below it has to leave the list. The split plan is in docs/split_plan.md."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LIMIT = 600
EXT = ('.py', '.js', '.html', '.css', '.rs')
SKIP_DIRS = {'.git', 'build', 'dist', 'models', 'logs', 'scratch', 'node_modules', '__pycache__', 'target', 'venv', '.venv', 'mods', 'installer_output',
             '.pytest_cache', '.claude', '_spike_tk', 'tests'}
SKIP_FILES = {'i18n_uk.js'}           # a data catalog, one line per text
BUDGET = json.load(open(os.path.join(os.path.dirname(__file__), 'file_size_budget.json'), encoding='utf-8'))


def _sizes():
    out = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith(EXT) and name not in SKIP_FILES:
                path = os.path.join(base, name)
                with open(path, encoding='utf-8', errors='replace') as f:
                    n = sum(1 for _ in f)
                if n > LIMIT:
                    out[os.path.relpath(path, ROOT).replace(os.sep, '/')] = n
    return out


def test_no_new_file_over_the_limit_and_listed_ones_do_not_grow():
    sizes = _sizes()
    bad = {f: (n, BUDGET.get(f)) for f, n in sizes.items() if f not in BUDGET or n > BUDGET[f]}
    assert not bad, f'over {LIMIT} lines (now, allowed): {bad}; propose a split plan instead of growing the file'


def test_budget_lists_only_files_that_are_still_too_long():
    sizes = _sizes()
    stale = {f: b for f, b in BUDGET.items() if f not in sizes}
    shrunk = {f: (sizes[f], b) for f, b in BUDGET.items() if f in sizes and sizes[f] < b}
    assert not stale, f'now within the limit, remove from tests/file_size_budget.json: {sorted(stale)}'
    assert not shrunk, f'shrunk: lower the numbers in tests/file_size_budget.json: {shrunk}'
