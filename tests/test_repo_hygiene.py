"""Source-level guards: patterns that leak secrets or open code-execution holes must not come back."""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), '..')
DIRS = ('core', 'actions', 'features', 'ui_next', 'config_pack')


def _sources():
    for d in DIRS:
        for base, _dirs, files in os.walk(os.path.join(ROOT, d)):
            if '__pycache__' in base:
                continue
            for name in files:
                if name.endswith('.py'):
                    path = os.path.join(base, name)
                    yield os.path.relpath(path, ROOT).replace('\\', '/'), open(path, encoding='utf-8', errors='replace').read()


def _hits(pattern, flags=0):
    rx = re.compile(pattern, flags)
    return [f'{rel}:{n}' for rel, text in _sources() for n, line in enumerate(text.splitlines(), 1) if rx.search(line) and not line.lstrip().startswith('#')]


def test_no_print_of_secrets():
    assert _hits(r'\bprint\(.*(?:TOKEN|PASSWORD|passwd|api_key|APIKEY|SECRET)', re.I) == []


def test_no_shell_true_or_disabled_tls_verification():
    assert _hits(r'shell\s*=\s*True') == []
    assert _hits(r'verify\s*=\s*False') == []


def test_no_eval_exec_or_pickle_loads():
    assert _hits(r'(?<![\w.])(?:eval|exec)\(') == []
    assert _hits(r'pickle\.loads?\(') == []
    assert _hits(r'yaml\.load\(') == []


def test_no_secret_file_is_tracked():
    import subprocess
    out = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    bad = [f for f in out if re.search(r'(^|/)(secrets\.env|\.env)$|\.pem$|\.key$', f)]
    assert bad == []
