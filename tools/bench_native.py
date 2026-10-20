"""Before/after timings for the native parts (docs/native.md): python tools/bench_native.py [name ...] [-n 20] [--json out.json].

Each benchmark times one native call. Stages add theirs to BENCHES; `baseline` only measures the loader so the numbers have a floor.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def measure(fn, n: int) -> dict:
    fn()   # warm-up: first call pays imports and caches
    times = []
    for _ in range(n):
        t = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    return {'n': n, 'p50_ms': round(statistics.median(times), 3), 'p95_ms': round(times[min(n - 1, int(n * 0.95))], 3), 'max_ms': round(times[-1], 3)}


def _baseline():
    from core import native
    return {'native': lambda: native.status()}


def _files_pair(roots, depth, **kw):
    from core import native
    mod = native.require('files')
    return {'native': lambda: mod.walk(roots, depth, kw.get('want', 'files'), kw.get('exts'), sorted(kw.get('skip_exts', ())), sorted(kw.get('skip_dirs', ())), True)}


def _files_scan_dirs():
    from actions import recent
    return _files_pair(recent.SCAN_DIRS, 3, skip_exts={'.ini', '.db', '.tmp', '.log', '.lnk', '.sys'})


def _files_large_tree():
    import sysconfig
    return _files_pair([sysconfig.get_paths()['purelib']], 4)


def _files_dirs():
    import os
    return _files_pair([os.path.join(os.path.expanduser('~'), 'OneDrive', 'Desktop')], 4, want='dirs', skip_dirs={'dist', 'build', 'node_modules', 'venv', '.venv', '__pycache__', 'out', 'bin', 'obj'})


def _audio_output():
    from core import native_audio
    return {'native': native_audio.query_output}


def _windows():
    from core import native
    mod = native.require('windows')
    return {'native': lambda: mod.list_windows(False)}


# name -> factory returning {'native': callable}; the Python implementations are gone, older numbers are in docs/native.md
BENCHES = {'baseline': _baseline, 'files_scan_dirs': _files_scan_dirs, 'files_large_tree': _files_large_tree, 'files_dirs': _files_dirs, 'audio_output': _audio_output, 'windows': _windows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('names', nargs='*', help=f'benchmarks to run (default: all of {", ".join(BENCHES)})')
    ap.add_argument('-n', type=int, default=20, help='calls per measurement')
    ap.add_argument('--json', help='also write the results to this file')
    args = ap.parse_args(argv)
    unknown = [x for x in args.names if x not in BENCHES]
    if unknown:
        print(f'unknown benchmark: {", ".join(unknown)}', file=sys.stderr)
        return 2
    results = {}
    for name in args.names or BENCHES:
        pair = BENCHES[name]()
        results[name] = {side: (measure(fn, args.n) if fn else None) for side, fn in pair.items()}
        for side, r in results[name].items():
            print(f'{name:12} {side:7} ' + (f"p50 {r['p50_ms']:9.3f} ms   p95 {r['p95_ms']:9.3f} ms   max {r['max_ms']:9.3f} ms" if r else 'not available'))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
