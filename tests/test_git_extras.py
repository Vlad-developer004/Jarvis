"""The commit dialog's safety net, against real throwaway repositories: awkward file names, warnings, suggested message, undo, error messages."""
import subprocess

import pytest

import actions.git_commit as gc
from actions import git_extras as gx


def run(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True, encoding='utf-8').stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / 'проект с пробелом'
    r.mkdir()
    run(r, 'init', '-q')
    run(r, 'config', 'user.email', 't@t.local')
    run(r, 'config', 'user.name', 'T')
    run(r, 'config', 'commit.gpgsign', 'false')
    return r


def commit_msgs(repo):
    return run(repo, 'log', '--format=%s').split('\n')[:-1]


def test_status_keeps_spaces_quotes_unicode_and_new_folders(repo):
    (repo / 'папка').mkdir()
    (repo / 'папка' / 'файл с пробелом.txt').write_text('1', encoding='utf-8')
    (repo / "it's.txt").write_text('1', encoding='utf-8')
    (repo / 'sub').mkdir()
    (repo / 'sub' / 'a.txt').write_text('1', encoding='utf-8')
    names = {f['file'] for f in gc._get_status(str(repo))}
    assert names == {'папка/файл с пробелом.txt', "it's.txt", 'sub/a.txt'}


def test_status_follows_a_rename_to_the_new_path(repo):
    (repo / 'old.txt').write_text('same content\n' * 5, encoding='utf-8')
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'one')
    run(repo, 'mv', 'old.txt', 'новое имя.txt')
    st = gc._get_status(str(repo))
    assert [(f['status'], f['file']) for f in st] == [('R', 'новое имя.txt')]


def test_commit_of_chosen_files_only_with_awkward_names(repo, monkeypatch):
    for n in ('ключ.py', '-dash.py', 'two words.py', 'skip.py'):
        (repo / n).write_text('x', encoding='utf-8')
    monkeypatch.setattr(gc, 'detect_repo_and_status', lambda hwnd=None: (str(repo), gc._get_status(str(repo))))
    ok, msg = gc.git_commit_push(custom_msg='-weird subject', files_to_add=['ключ.py', '-dash.py', 'two words.py'], push_enabled=False)
    assert ok, msg
    assert commit_msgs(repo) == ['-weird subject']
    assert sorted(run(repo, '-c', 'core.quotepath=false', 'show', '--name-only', '--format=', 'HEAD').split('\n')[:-1]) == ['-dash.py', 'two words.py', 'ключ.py']
    assert [f['file'] for f in gc._get_status(str(repo))] == ['skip.py']


def test_missing_identity_and_hook_failures_get_readable_messages(repo, monkeypatch):
    (repo / 'a.txt').write_text('x', encoding='utf-8')
    monkeypatch.setattr(gc, 'detect_repo_and_status', lambda hwnd=None: (str(repo), gc._get_status(str(repo))))
    hook = repo / '.git' / 'hooks' / 'pre-commit'
    hook.write_text('#!/bin/sh\necho "lint failed: line 3" >&2\nexit 1\n', encoding='utf-8')
    ok, msg = gc.git_commit_push(custom_msg='x', push_enabled=False)
    assert not ok and 'lint failed: line 3' in msg
    assert 'кто вы' in gc.explain_error('*** Please tell me who you are.\n\nRun\n  git config --global user.email')
    assert 'index.lock' in gc.explain_error("fatal: Unable to create '.git/index.lock': File exists.")
    assert 'safe.directory' in gc.explain_error('fatal: detected dubious ownership in repository')


def test_index_lock_is_retried_once(repo, monkeypatch):
    (repo / 'a.txt').write_text('x', encoding='utf-8')
    run(repo, 'add', '.')
    real, calls = gc._git, []

    def flaky(r, *args, **kw):
        if args[0] == 'commit' and not calls:
            calls.append(1)
            return subprocess.CompletedProcess(args, 128, '', "fatal: Unable to create '.git/index.lock': File exists.")
        return real(r, *args, **kw)
    monkeypatch.setattr(gc, '_git', flaky)
    monkeypatch.setattr(gc.time, 'sleep', lambda s: None)
    gc._commit(str(repo), 'after lock')
    assert commit_msgs(repo) == ['after lock']


def test_unborn_repository_and_detached_head_branch_names(repo):
    assert gc.get_current_branch(str(repo)) in ('main', 'master')
    (repo / 'a.txt').write_text('x', encoding='utf-8')
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'one')
    run(repo, 'checkout', '-q', '--detach')
    assert gc.get_current_branch(str(repo)) == 'HEAD'
    assert all(not b.startswith('(') for b in gc.get_branches(str(repo)))


def test_inspect_flags_secrets_build_output_and_big_files(repo, monkeypatch):
    (repo / '.env').write_text('A=1', encoding='utf-8')
    (repo / 'target').mkdir()
    (repo / 'target' / 'x.rlib').write_text('1', encoding='utf-8')
    (repo / 'big.bin').write_bytes(b'0' * (gx.LARGE_BYTES + 1))
    (repo / 'cfg.py').write_text('TOKEN = "abcdefghijklmnopqrstuvwxyz123456"\n', encoding='utf-8')
    (repo / 'fine.py').write_text('print(1)\n', encoding='utf-8')
    files = gc._get_status(str(repo))
    got = {k: v['kind'] for k, v in gx.inspect_files(str(repo), files).items()}
    assert got == {'.env': 'secret_name', 'target/x.rlib': 'build', 'big.bin': 'large', 'cfg.py': 'secret_text'}


def test_line_counts_for_changed_and_new_files(repo):
    (repo / 'a.txt').write_text('1\n2\n3\n', encoding='utf-8')
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'one')
    (repo / 'a.txt').write_text('1\n2\nthree\nfour\n', encoding='utf-8')
    (repo / 'new.txt').write_text('a\nb\n', encoding='utf-8')
    counts = gx.line_counts(str(repo), gc._get_status(str(repo)))
    assert counts['a.txt'] == (2, 1) and counts['new.txt'] == (2, 0)


@pytest.mark.parametrize('files,want', [
    ([{'status': '??', 'file': 'tests/test_a.py'}], 'test(tests): add test_a.py'),
    ([{'status': 'M', 'file': 'docs/x.md'}, {'status': 'M', 'file': 'docs/y.md'}], 'docs(docs): update x.md, y.md'),
    ([{'status': '??', 'file': 'core/a.py'}, {'status': '??', 'file': 'core/b.py'}], 'feat(core): add a.py, b.py'),
    ([{'status': 'M', 'file': 'core/a.py'}, {'status': 'M', 'file': 'actions/b.py'}], 'fix: update a.py, b.py'),
    ([{'status': 'D', 'file': 'old.py'}], 'chore: remove old.py'),
])
def test_suggested_message(files, want):
    assert gx.suggest_message(files) == want


def test_undo_keeps_files_and_refuses_after_push(repo, tmp_path):
    (repo / 'a.txt').write_text('1', encoding='utf-8')
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'one')
    (repo / 'b.txt').write_text('2', encoding='utf-8')
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'two')
    ok, _ = gx.undo_last_commit(str(repo))
    assert ok and commit_msgs(repo) == ['one'] and (repo / 'b.txt').exists()
    run(repo, 'add', '.')
    run(repo, 'commit', '-q', '-m', 'two again')
    bare = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '-q', '--bare', str(bare)], check=True)
    run(repo, 'remote', 'add', 'origin', str(bare))
    run(repo, 'push', '-q', 'origin', 'HEAD')
    ok, msg = gx.undo_last_commit(str(repo))
    assert not ok and 'отправлен' in msg and commit_msgs(repo)[0] == 'two again'


def test_push_to_a_bare_remote_sets_upstream_and_force_uses_a_lease(repo, tmp_path, monkeypatch):
    bare = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '-q', '--bare', str(bare)], check=True)
    run(repo, 'remote', 'add', 'origin', str(bare))
    (repo / 'a.txt').write_text('1', encoding='utf-8')
    monkeypatch.setattr(gc, 'detect_repo_and_status', lambda hwnd=None: (str(repo), gc._get_status(str(repo))))
    seen = []
    real = gc._git
    monkeypatch.setattr(gc, '_git', lambda r, *a, **k: (seen.append(a), real(r, *a, **k))[1])
    ok, msg = gc.git_commit_push(custom_msg='first', push_enabled=True, force_push=True, set_upstream=True)
    assert ok, msg
    push = next(a for a in seen if a[0] == 'push')
    assert '--force-with-lease' in push and '--force' not in push and '--set-upstream' in push
    assert 'first' in run(bare, 'log', '--all', '--format=%s')
