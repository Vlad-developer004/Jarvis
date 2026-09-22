"""Tests for actions/git_commit.py's pure/self-contained logic —
repo discovery, status parsing, commit-message generation, and PR-URL
construction (SSH-to-HTTPS remote normalization, GitHub vs GitLab URL
shape). _find_git_repo/_get_status run against a real, throwaway git repo
in tmp_path (safe, isolated, no network) rather than mocking git itself.
"""
import subprocess

import actions.git_commit as git_cmd


def _run_git(repo, *args):
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)


def _init_repo(tmp_path):
    repo = tmp_path / 'proj'
    repo.mkdir()
    _run_git(repo, 'init', '-q')
    _run_git(repo, 'config', 'user.email', 'test@test.local')
    _run_git(repo, 'config', 'user.name', 'Test')
    return repo


# ── _find_git_repo ────────────────────────────────────────────────────────

def test_find_git_repo_at_exact_path(tmp_path):
    repo = _init_repo(tmp_path)
    assert git_cmd._find_git_repo(str(repo)) == str(repo)


def test_find_git_repo_walks_up_from_subdirectory(tmp_path):
    repo = _init_repo(tmp_path)
    sub = repo / 'src' / 'nested'
    sub.mkdir(parents=True)
    assert git_cmd._find_git_repo(str(sub)) == str(repo)


def test_find_git_repo_returns_none_outside_any_repo(tmp_path):
    outside = tmp_path / 'not_a_repo'
    outside.mkdir()
    assert git_cmd._find_git_repo(str(outside)) is None


# ── _get_status (real git subprocess against a throwaway repo) ───────────

def test_get_status_reports_untracked_file(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / 'new_file.txt').write_text('hello', encoding='utf-8')

    status = git_cmd._get_status(str(repo))

    assert any(f['file'] == 'new_file.txt' and f['status'] == '??' for f in status)


def test_get_status_reports_modified_file(tmp_path):
    repo = _init_repo(tmp_path)
    f = repo / 'existing.txt'
    f.write_text('v1', encoding='utf-8')
    _run_git(repo, 'add', '.')
    _run_git(repo, 'commit', '-q', '-m', 'initial')
    f.write_text('v2', encoding='utf-8')

    status = git_cmd._get_status(str(repo))

    assert any(s['file'] == 'existing.txt' and 'M' in s['status'] for s in status)


def test_get_status_first_entry_filename_not_truncated(tmp_path):
    # Regression: porcelain's leading space-prefixed status code (' M', ' D',
    # etc.) on the FIRST reported file used to get eaten by an outer
    # .strip() on the whole stdout blob, shifting the fixed line[3:] slice
    # and dropping the filename's first character (e.g. "existing.txt" ->
    # "xisting.txt").
    repo = _init_repo(tmp_path)
    f = repo / 'existing.txt'
    f.write_text('v1', encoding='utf-8')
    _run_git(repo, 'add', '.')
    _run_git(repo, 'commit', '-q', '-m', 'initial')
    f.write_text('v2', encoding='utf-8')

    status = git_cmd._get_status(str(repo))

    filenames = [s['file'] for s in status]
    assert 'existing.txt' in filenames
    assert 'xisting.txt' not in filenames


def test_get_status_clean_repo_returns_empty(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / 'a.txt').write_text('x', encoding='utf-8')
    _run_git(repo, 'add', '.')
    _run_git(repo, 'commit', '-q', '-m', 'initial')

    assert git_cmd._get_status(str(repo)) == []


# ── _short_names ──────────────────────────────────────────────────────────

def test_short_names_under_limit_lists_all():
    assert git_cmd._short_names(['a.py', 'b.py']) == 'a.py, b.py'


def test_short_names_over_limit_shows_count_of_remainder():
    result = git_cmd._short_names(['a.py', 'b.py', 'c.py', 'd.py', 'e.py'], limit=3)
    assert result == 'a.py, b.py, c.py, и ещё 2'


def test_short_names_uses_basename_not_full_path():
    result = git_cmd._short_names(['src/deep/nested/file.py'])
    assert result == 'file.py'


# ── _generate_message ──────────────────────────────────────────────────────

def test_generate_message_added_only():
    changed = [{'status': '??', 'file': 'new.py'}]
    assert git_cmd._generate_message(changed) == 'Добавлено: new.py'


def test_generate_message_combines_added_modified_deleted():
    changed = [
        {'status': '??', 'file': 'new.py'},
        {'status': 'M', 'file': 'existing.py'},
        {'status': 'D', 'file': 'old.py'},
    ]
    msg = git_cmd._generate_message(changed)
    # First part's leading letter is capitalized by _generate_message
    assert 'обавлено: new.py' in msg
    assert 'изменено: existing.py' in msg
    assert 'удалено: old.py' in msg
    assert msg[0].isupper()


def test_generate_message_empty_changelist_returns_generic_message():
    assert git_cmd._generate_message([]) == 'обновление кода'


# ── open_pull_request_url ────────────────────────────────────────────────

def test_open_pr_url_github_https_remote(monkeypatch):
    monkeypatch.setattr(git_cmd.subprocess, 'run',
                         lambda *a, **k: type('R', (), {'stdout': 'https://github.com/user/repo.git\n'})())
    opened = []
    monkeypatch.setattr(git_cmd.webbrowser, 'open', lambda url: opened.append(url))

    git_cmd.open_pull_request_url('/repo', 'feature-branch')

    assert opened == ['https://github.com/user/repo/compare/feature-branch?expand=1']


def test_open_pr_url_normalizes_ssh_remote_to_https(monkeypatch):
    monkeypatch.setattr(git_cmd.subprocess, 'run',
                         lambda *a, **k: type('R', (), {'stdout': 'git@github.com:user/repo.git\n'})())
    opened = []
    monkeypatch.setattr(git_cmd.webbrowser, 'open', lambda url: opened.append(url))

    git_cmd.open_pull_request_url('/repo', 'feature-branch')

    assert opened == ['https://github.com/user/repo/compare/feature-branch?expand=1']


def test_open_pr_url_gitlab_remote_uses_merge_request_shape(monkeypatch):
    monkeypatch.setattr(git_cmd.subprocess, 'run',
                         lambda *a, **k: type('R', (), {'stdout': 'https://gitlab.com/user/repo.git\n'})())
    opened = []
    monkeypatch.setattr(git_cmd.webbrowser, 'open', lambda url: opened.append(url))

    git_cmd.open_pull_request_url('/repo', 'feature-branch')

    assert opened and 'gitlab.com/user/repo/-/merge_requests/new' in opened[0]


def test_open_pr_url_unknown_host_does_not_open_browser(monkeypatch):
    monkeypatch.setattr(git_cmd.subprocess, 'run',
                         lambda *a, **k: type('R', (), {'stdout': 'https://bitbucket.org/user/repo.git\n'})())
    monkeypatch.setattr(git_cmd.webbrowser, 'open',
                         lambda url: (_ for _ in ()).throw(AssertionError('must not open unknown host')))

    git_cmd.open_pull_request_url('/repo', 'feature-branch')


def test_open_pr_url_no_remote_does_nothing(monkeypatch):
    monkeypatch.setattr(git_cmd.subprocess, 'run',
                         lambda *a, **k: type('R', (), {'stdout': ''})())
    monkeypatch.setattr(git_cmd.webbrowser, 'open',
                         lambda url: (_ for _ in ()).throw(AssertionError('must not open with no remote')))

    git_cmd.open_pull_request_url('/repo', 'feature-branch')
