"""Directory listing for file and folder search: the Rust walker (native/jarvis_files), there is no Python walk.

Both paths return `(parent_dir, name, mtime)` sorted by path, with the same rules (see jarvis_files.walk in native/): entries up to
`max_depth` levels below a root (a root's children are level 1), folders named in `skip_dirs` or starting with "." are neither
listed nor entered, symbolic links are not followed.
"""
from __future__ import annotations

from typing import Iterable

from core import native

Entry = tuple[str, str, float]


def walk(roots: Iterable[str], max_depth: int, want: str = 'files', exts: Iterable[str] | None = None,
         skip_exts: Iterable[str] = (), skip_dirs: Iterable[str] = (), skip_hidden: bool = True) -> list[Entry]:
    """Raises native.NativeUnavailable when jarvis_files is not built."""
    exts = None if exts is None else sorted({e.lower() for e in exts})
    return native.require('files').walk(list(roots), max_depth, want, exts, sorted({e.lower() for e in skip_exts}),
                                        sorted({d.lower() for d in skip_dirs}), skip_hidden)
