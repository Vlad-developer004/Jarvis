"""The quality gates themselves: they exist, they are wired into CI, and they pass on the current tree."""
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


def test_gate_files_exist_and_ci_runs_every_gate():
    ci = _read('.github/workflows/ci.yml')
    for needle in ('ruff check .', 'bandit -c bandit.yaml', 'pytest', 'pip-audit'):
        assert needle in ci, needle
    assert 'select' in _read('ruff.toml') and 'skips' in _read('bandit.yaml')
    dev = _read('requirements-dev.txt')
    assert all(tool in dev for tool in ('ruff', 'bandit', 'pip-audit'))


def test_audit_requirements_are_the_exact_pins_of_the_base_file():
    base = {line.split('==')[0].strip().lower() for line in _read('requirements-base.txt').splitlines() if '==' in line and not line.lstrip().startswith('#')}
    audit = {line.split('==')[0].strip().lower() for line in _read('requirements-audit.txt').splitlines() if '==' in line and not line.startswith('#')}
    assert base == audit


def test_text_file_line_endings_are_pinned_in_gitattributes():
    attrs = _read('.gitattributes')
    assert '*.py text eol=lf' in attrs


def _has(mod):
    return importlib.util.find_spec(mod) is not None


@pytest.mark.skipif(not _has('ruff'), reason='ruff is not installed')
def test_ruff_defect_rules_pass():
    r = subprocess.run([sys.executable, '-m', 'ruff', 'check', '.', '--output-format', 'concise'], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]


@pytest.mark.skipif(not _has('bandit'), reason='bandit is not installed')
def test_bandit_medium_and_above_pass():
    r = subprocess.run([sys.executable, '-m', 'bandit', '-c', 'bandit.yaml', '-r', 'core', 'actions', 'features', 'ui_next', 'config_pack', 'main.py', 'tools', '-ll', '-q'],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-2000:]
