import platform
import os
import subprocess
from pathlib import Path
import shutil
from rapidfuzz import process, fuzz
from actions.explorer import open_in_explorer
USER_HOME = str(Path.home())
_FOLDER_QUERY_ALIASES: dict[str, str] = {
    'проджектс': 'projects',
    'проджетс': 'projects',
    'проекст': 'projects',
    'проектс': 'projects',
    'проджект': 'project',
    'проекты': 'projects',
    'даунлоадс': 'downloads',
    'даунлодс': 'downloads',
    'документс': 'documents',
    'десктоп': 'desktop',
    'десктопе': 'desktop',
}
def _fold(s: str) -> str:
    return (s or '').strip().casefold()
_CYR_TO_LAT = {
    'а':'a','б':'b','в':'v','г':'h','ґ':'g','д':'d','е':'e','ё':'e','є':'ye','ж':'zh','з':'z','и':'y','і':'i','ї':'yi',
    'й':'y','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
    'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
}
_LAT_TO_CYR = {
    'a':'а','b':'б','v':'в','h':'г','g':'г','d':'д','e':'е','z':'з','i':'и','y':'и','k':'к','l':'л','m':'м','n':'н',
    'o':'о','p':'п','r':'р','s':'с','t':'т','u':'у','f':'ф','c':'с','j':'й','q':'к','w':'в','x':'кс',
}
def _translit_cyr_to_lat(s: str) -> str:
    s = _fold(s)
    out = []
    for ch in s:
        out.append(_CYR_TO_LAT.get(ch, ch))
    return ''.join(out)
def _translit_lat_to_cyr_simple(s: str) -> str:
    s = _fold(s)
    out = []
    for ch in s:
        out.append(_LAT_TO_CYR.get(ch, ch))
    return ''.join(out)
def normalize_folder_voice_query(name: str) -> str:
    s = _fold((name or '').strip())
    return _FOLDER_QUERY_ALIASES.get(s, (name or '').strip())
def _name_variants(s: str) -> list[str]:
    s0 = _fold(s)
    if not s0:
        return []
    v = {s0}
    v.add(_translit_cyr_to_lat(s0))
    v.add(_translit_lat_to_cyr_simple(s0))
    v.add(s0.replace('дж', 'j').replace('ж', 'zh'))
    alias = _fold(normalize_folder_voice_query(s))
    if alias and alias != s0:
        v.add(_fold(alias))
        v.add(_translit_cyr_to_lat(_fold(alias)))
    return [x for x in v if x]
def _folder_match_score(q: str, e: str) -> int:
    return max(
        fuzz.token_set_ratio(q, e),
        fuzz.partial_ratio(q, e),
        fuzz.ratio(q, e),
        int(fuzz.WRatio(q, e)),
    )
def folder_search_roots_and_depth(base_ctx: str) -> tuple[list[str], int]:
    try:
        base = Path(base_ctx).resolve()
    except Exception:
        base = Path(base_ctx)
    if base.is_file():
        base = base.parent
    if not base.exists():
        base = Path(USER_HOME) / "Desktop"
    return ([str(base)], 24)
def _depth_limited_walk(root: str, max_depth: int):
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for cur, dirs, files in os.walk(root):
        depth = cur.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if not d.startswith('.')]
        yield cur, dirs
def _find_folder_anywhere(start_dirs: list[str], name: str, max_depth: int = 4) -> Path | None:
    name = normalize_folder_voice_query(name)
    query_vars = _name_variants(name)
    if not query_vars:
        return None
    best: tuple[int, str] | None = None
    for root in start_dirs:
        if not root or not os.path.isdir(root):
            continue
        try:
            for entry in Path(root).iterdir():
                if not entry.is_dir():
                    continue
                ev = _name_variants(entry.name)
                if any(q == e for q in query_vars for e in ev):
                    return entry
        except Exception:
            pass
        for cur, dirs in _depth_limited_walk(root, max_depth=max_depth):
            for d in dirs:
                dv = _name_variants(d)
                score = 0
                for q in query_vars:
                    for e in dv:
                        s = _folder_match_score(q, e)
                        if s > score:
                            score = s
                if score >= 88:
                    return Path(cur) / d
                if score >= 74:
                    full = str(Path(cur) / d)
                    if best is None or score > best[0]:
                        best = (score, full)
    if best:
        return Path(best[1])
    return None
def empty_recycle_bin() -> tuple[bool, str]:
    if platform.system().lower() != 'windows':
        return (False, 'unsupported-os')
    try:
        import ctypes
        from ctypes import wintypes
        HRESULT = ctypes.c_long
        flags = 1 | 2 | 4
        shell32 = ctypes.WinDLL('shell32')
        SHEmptyRecycleBinW = shell32.SHEmptyRecycleBinW
        SHEmptyRecycleBinW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.DWORD]
        SHEmptyRecycleBinW.restype = HRESULT
        hr = SHEmptyRecycleBinW(None, None, flags)
        if hr in (0, 1):
            return (True, 'ok')
    except Exception as e:
        pass
    try:
        cmd = ['powershell', '-NoProfile', '-Command', 'Clear-RecycleBin -Force -ErrorAction SilentlyContinue']
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            return (True, 'ok')
        return (False, f'ps_err={res.stderr.strip()}')
    except Exception as e:
        return (False, f'exc:{e}')
def create_folder_at(base_dir: str, folder_name: str) -> tuple[bool, str]:
    try:
        if not folder_name or folder_name.strip() in {'.', '..'}:
            return (False, 'Некорректное имя папки')
        base = Path(base_dir).resolve()
        full = (base / folder_name).resolve()
        try:
            full.relative_to(base)
        except ValueError:
            return (False, 'Папка вне разрешенного каталога')
        full.mkdir(exist_ok=False)
        return (True, str(full))
    except FileExistsError:
        return (False, 'Папка уже существует')
    except Exception as e:
        return (False, str(e))
def _find_existing_folder_case_insensitive(base_dir: str, name: str) -> Path | None:
    base = Path(base_dir)
    try:
        for entry in base.iterdir():
            if entry.is_dir() and entry.name.lower() == name.lower():
                return entry
    except Exception:
        pass
    return None
def delete_folder_at(base_dir: str, folder_name: str) -> tuple[bool, str]:
    try:
        if not folder_name or folder_name.strip() in {'.', '..'}:
            return (False, 'Некорректное имя папки')
        base = Path(base_dir).resolve()
        target = _find_existing_folder_case_insensitive(base, folder_name)
        if target is None:
            target = (base / folder_name).resolve()
            if not target.exists() or not target.is_dir():
                return (False, 'Папка не найдена')
        else:
            target = target.resolve()
        try:
            target.relative_to(base)
        except ValueError:
            return (False, 'Папка вне разрешенного каталога')
        try:
            shutil.rmtree(target)
        except PermissionError:
            cmd = ['powershell', '-NoProfile', '-Command', 'Remove-Item', '-LiteralPath', str(target), '-Recurse', '-Force']
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                return (False, f'ps_err={res.stderr.strip()}')
        return (True, str(target))
    except Exception as e:
        return (False, str(e))
def _list_subdirs(base: Path) -> list[Path]:
    try:
        return [p for p in base.iterdir() if p.is_dir()]
    except Exception:
        return []
def _find_subdir_ci_or_fuzzy(base_dir: str, name: str, fuzzy_threshold: int=80) -> Path | None:
    name = normalize_folder_voice_query((name or "").strip())
    if not name:
        return None
    query_vars = _name_variants(name)
    if not query_vars:
        return None
    base = Path(base_dir)
    best: tuple[int, Path] | None = None
    for entry in _list_subdirs(base):
        if entry.name.casefold() == name.casefold():
            return entry
        ev = _name_variants(entry.name)
        if any(q == e for q in query_vars for e in ev):
            return entry
        score = 0
        for q in query_vars:
            for e in ev:
                s = _folder_match_score(q, e)
                if s > score:
                    score = s
        if score >= 72 and (best is None or score > best[0]):
            best = (score, entry)
    if best is not None and best[0] >= fuzzy_threshold:
        return best[1]
    names = [p.name for p in _list_subdirs(base)]
    if not names:
        return None
    match = process.extractOne(name, names, scorer=fuzz.token_set_ratio)
    if match and match[1] >= fuzzy_threshold:
        return base / match[0]
    return None
def goto_folder(base_dir: str, folder_name: str) -> tuple[bool, str]:
    try:
        base = Path(base_dir).resolve()
        folder_name = normalize_folder_voice_query(folder_name)
        target = _find_subdir_ci_or_fuzzy(str(base), folder_name)
        if not target:
            roots, max_dep = folder_search_roots_and_depth(str(base))
            target = _find_folder_anywhere(roots, folder_name, max_depth=max_dep)
        if not target:
            return (False, f"Папка '{folder_name}' не найдена")
        ok = open_in_explorer(str(target))
        return (True, str(target)) if ok else (False, 'Ошибка Проводника')
    except Exception as e:
        return (False, str(e))
def resolve_folder_for_hint(folder_hint: str | None, base_ctx: str) -> tuple[Path, str | None]:
    import os
    base = Path(base_ctx).resolve()
    if not folder_hint or not str(folder_hint).strip():
        return (base, None)
    hint = normalize_folder_voice_query(str(folder_hint).strip().strip("/\\"))
    if not hint:
        return (base, None)
    hp = Path(hint)
    if hp.is_absolute() and hp.is_dir():
        return (hp.resolve(), None)
    direct = (base / hint).resolve()
    try:
        direct.relative_to(base)
    except ValueError:
        direct = base / hint
    if direct.is_dir():
        return (direct, None)
    try:
        sub = _find_subdir_ci_or_fuzzy(str(base), hint)
        if sub is not None and sub.is_dir():
            return (sub.resolve(), None)
    except Exception:
        pass
    roots, max_dep = folder_search_roots_and_depth(str(base_ctx))
    found = _find_folder_anywhere(roots, hint, max_depth=max_dep)
    if found is not None and found.is_dir():
        return (found.resolve(), None)
    warn = f"Папка «{hint}» не найдена, создаю в текущем расположении."
    return (base, warn)
