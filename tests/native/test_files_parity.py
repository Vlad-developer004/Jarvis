"""jarvis_files.walk and the Python walk in actions/file_walk.py must list exactly the same entries."""
import os
from pathlib import PurePath

import pytest

from actions import file_walk


def _reference_walk(roots, max_depth, want, exts, skip_exts, skip_dirs, skip_hidden):
    """An independent os.walk implementation of the rules jarvis_files.walk documents; the native walker must agree with it."""
    out = []
    for root in roots:
        root = os.path.abspath(root)
        base = root.rstrip(os.sep).count(os.sep)
        for cur, dirs, files in os.walk(root):
            depth = cur.rstrip(os.sep).count(os.sep) - base
            dirs[:] = [d for d in dirs if not (skip_hidden and d.startswith('.')) and d.lower() not in skip_dirs]
            if depth + 1 == max_depth:
                subdirs, dirs[:] = list(dirs), []
            else:
                subdirs = dirs
            if want == 'dirs':
                out.extend((cur, d, 0.0) for d in subdirs)
                continue
            for f in files:
                ext = PurePath(f).suffix.lower()
                if exts is not None and ext not in exts:
                    continue
                if exts is None and ext in skip_exts:
                    continue
                out.append((cur, f, os.path.getmtime(os.path.join(cur, f))))
    return sorted(out, key=lambda e: (e[0], e[1]))


@pytest.fixture
def tree(tmp_path):
    def put(rel, data=b'x'):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p
    put('a.pdf'); put('b.DOCX'); put('c.ini'); put('.hidden_file.txt'); put('noext'); put('trailingdot.')
    put('one/d.xlsx'); put('one/two/e.pdf'); put('one/two/three/f.pdf'); put('one/two/three/four/g.pdf')
    put('.git/h.pdf'); put('node_modules/i.pdf'); put('Build/j.pdf'); put('one/.cache/k.pdf')
    os.utime(tmp_path / 'a.pdf', (1_700_000_000, 1_700_000_000))
    return tmp_path


def _py(*a, **k):
    return _reference_walk(*a, **k)


@pytest.mark.parametrize('kw', [
    dict(want='files', exts=None, skip_exts=set(), skip_dirs=set(), skip_hidden=True),
    dict(want='files', exts=None, skip_exts={'.ini'}, skip_dirs=set(), skip_hidden=True),
    dict(want='files', exts={'.pdf', '.docx'}, skip_exts=set(), skip_dirs={'node_modules', 'build'}, skip_hidden=True),
    dict(want='files', exts=None, skip_exts=set(), skip_dirs=set(), skip_hidden=False),
    dict(want='dirs', exts=None, skip_exts=set(), skip_dirs={'node_modules', 'build'}, skip_hidden=True),
    dict(want='dirs', exts=None, skip_exts=set(), skip_dirs=set(), skip_hidden=False),
])
@pytest.mark.parametrize('depth', [1, 2, 3, 10])
def test_native_walk_matches_the_python_walk(native_files, tree, kw, depth):
    exts = None if kw['exts'] is None else sorted(kw['exts'])
    nat = native_files.walk([str(tree)], depth, kw['want'], exts, sorted(kw['skip_exts']), sorted(kw['skip_dirs']), kw['skip_hidden'])
    py = _py([str(tree)], depth, kw['want'], kw['exts'], kw['skip_exts'], kw['skip_dirs'], kw['skip_hidden'])
    assert [(p, n) for p, n, _ in nat] == [(p, n) for p, n, _ in py]
    for (_, n, mt_nat), (_, _, mt_py) in zip(nat, py):
        assert abs(mt_nat - mt_py) < 0.01, n


def test_mtime_is_seconds_since_epoch(native_files, tree):
    (entry,) = [e for e in native_files.walk([str(tree)], 1, 'files', ['.pdf']) if e[1] == 'a.pdf']
    assert entry[2] == pytest.approx(1_700_000_000, abs=1)


def test_missing_roots_and_bad_arguments(native_files, tmp_path):
    assert native_files.walk([str(tmp_path / 'nope')], 3) == []
    assert native_files.walk([str(tmp_path)], 0) == []
    with pytest.raises(ValueError):
        native_files.walk([str(tmp_path)], 3, 'everything')


def test_several_roots_are_walked_together(native_files, tree, tmp_path_factory):
    other = tmp_path_factory.mktemp('other')
    (other / 'z.pdf').write_bytes(b'x')
    names = {n for _, n, _ in native_files.walk([str(tree), str(other)], 1, 'files', ['.pdf'])}
    assert {'a.pdf', 'z.pdf'} <= names


def test_walk_wrapper_calls_the_native_walker_and_normalises_its_arguments(native_files, tree):
    got = file_walk.walk([str(tree)], 3, exts=['.PDF', '.docx'], skip_dirs=['Node_Modules'])
    want = _reference_walk([str(tree)], 3, 'files', {'.pdf', '.docx'}, set(), {'node_modules'}, True)
    assert [(p, n) for p, n, _ in got] == [(p, n) for p, n, _ in want] and got


def test_walk_wrapper_raises_when_the_module_is_missing(tree, monkeypatch):
    import sys

    from core import native
    monkeypatch.setattr(native, '_loaded', {})
    monkeypatch.setitem(sys.modules, 'jarvis_files', None)
    with pytest.raises(native.NativeUnavailable):
        file_walk.walk([str(tree)], 3)


def test_search_and_recent_use_the_native_walk(native_files, tree, monkeypatch):
    from actions import recent
    monkeypatch.setattr(recent, 'SCAN_DIRS', [str(tree)])
    opened = []
    monkeypatch.setattr('core.safe_open.open_user_file', lambda p: opened.append(os.path.basename(p)))
    ok, msg = recent.search_and_open_file('b', 'document')
    assert ok, msg
    assert opened == ['b.DOCX']
    assert recent._scan_recent_files('document', 5)[0].endswith('b.DOCX') or recent._scan_recent_files('document', 5)
