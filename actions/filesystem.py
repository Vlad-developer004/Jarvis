import platform
import os
import subprocess
from pathlib import Path
import shutil
from rapidfuzz import process, fuzz
from actions.explorer import open_in_explorer
USER_HOME = str(Path.home())
# Минимальные алиасы только для числовых обозначений и аббревиатур
_SPECIAL_ALIASES: dict[str, str] = {
    'лр': 'LR',
    'лаб': 'Lab',
}
_NUM_MAP = {
    'один': '1', 'одна': '1', 'первая': '1', 'первый': '1',
    'два': '2', 'две': '2', 'вторая': '2', 'второй': '2',
    'три': '3', 'третья': '3', 'третий': '3',
    'четыре': '4', 'четвертая': '4', 'четвертый': '4',
    'пять': '5', 'пятая': '5', 'пятый': '5',
    'шесть': '6', 'шестая': '6', 'шестой': '6',
    'семь': '7', 'седьмая': '7', 'седьмой': '7',
    'восемь': '8', 'восьмая': '8', 'восьмой': '8',
    'девять': '9', 'девятая': '9', 'девятый': '9',
    'десять': '10', 'десятая': '10', 'десятый': '10',
}
_PHONETIC_ALIASES = {
    'аусбил': 'ausbil',
    'аутбил': 'ausbil',
    'аутбри': 'ausbil',
    'сбилд': 'ausbil',
    'аусбиль': 'ausbil',
    'аутбиль': 'ausbil',
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
    if not s:
        return s

    # 1. Replace number words (один -> 1)
    words = s.split()
    for i, w in enumerate(words):
        if w in _NUM_MAP:
            words[i] = _NUM_MAP[w]
    s = ' '.join(words)

    # 2. Apply special abbreviation aliases (лр -> LR)
    for alias, replacement in _SPECIAL_ALIASES.items():
        if s == alias or s.startswith(alias + ' '):
            s = s.replace(alias, replacement, 1)

    return s
def _english_to_cyrillic_phonetic(s: str) -> list[str]:
    s = s.lower().strip()
    rules_base = [
        ('tion', 'шн'),
        ('sion', 'шн'),
        ('ture', 'чер'),
        ('ch', 'ч'),
        ('sh', 'ш'),
        ('ph', 'ф'),
        ('th', 'т'),
        ('kh', 'х'),
        ('ck', 'к'),
        ('qu', 'кв'),
        ('c', 'к'),
        ('x', 'кс'),
        ('j', 'дж'),
        ('w', 'в'),
    ]
    temp = s
    for eng, rus in rules_base:
        temp = temp.replace(eng, rus)
        
    variants = []
    
    # 1. Standard vowels
    vow1 = [('ea', 'и'), ('ee', 'и'), ('oo', 'у'), ('ou', 'у'), ('ai', 'ей'), ('ay', 'ей'), ('y', 'и'), ('u', 'у'), ('a', 'э'), ('e', 'е'), ('i', 'и'), ('o', 'о')]
    res1 = temp
    for eng, rus in vow1: res1 = res1.replace(eng, rus)
    variants.append(res1)
    
    # 2. Alternative: "ea" -> "ью" (covers "features" -> "фьючерс")
    vow2 = [('ea', 'ью'), ('ee', 'и'), ('oo', 'у'), ('ou', 'у'), ('ai', 'ей'), ('ay', 'ей'), ('y', 'и'), ('u', 'у'), ('a', 'э'), ('e', 'е'), ('i', 'и'), ('o', 'о')]
    res2 = temp
    for eng, rus in vow2: res2 = res2.replace(eng, rus)
    variants.append(res2)
    
    # 3. Alternative: "u" -> "ю" (covers "utils" -> "ютилс")
    vow3 = [('ea', 'и'), ('ee', 'и'), ('oo', 'у'), ('ou', 'у'), ('ai', 'ей'), ('ay', 'ей'), ('y', 'и'), ('u', 'ю'), ('a', 'э'), ('e', 'е'), ('i', 'и'), ('o', 'о')]
    res3 = temp
    for eng, rus in vow3: res3 = res3.replace(eng, rus)
    variants.append(res3)
    
    return list(set(variants))

def get_name_variants(s: str) -> list[str]:
    s0 = _fold(s)
    if not s0:
        return []
    v = {s0}
    v.add(_translit_cyr_to_lat(s0))
    v.add(_translit_lat_to_cyr_simple(s0))
    v.add(s0.replace('дж', 'j').replace('ж', 'zh'))
    
    # Common English-Russian technical homophones
    if s0 == 'спич': v.add('speech')
    if s0 == 'speech': v.add('спич')
    
    # Generic English-to-Cyrillic phonetic mapping to support pronouncing any English folder in Cyrillic
    if any(ord(c) < 128 and c.isalpha() for c in s0):
        for var in _english_to_cyrillic_phonetic(s0):
            v.add(var)

    # Phonetic normalization for Slavic 'i' variations
    # 1. Normalize 'slavic' letters (i/y variants) to Russian 'и'
    s_norm = s0.replace('і', 'и').replace('ы', 'и')
    if s_norm != s0:
        v.add(s_norm)
        v.add(_translit_cyr_to_lat(s_norm))
        
    # 2. Try the reverse (normalizing towards 'i' lattice for Ukrainian/English)
    s_norm_i = s0.replace('и', 'і').replace('ы', 'і')
    if s_norm_i != s0:
        v.add(s_norm_i)
        v.add(_translit_cyr_to_lat(s_norm_i))

    # 3. Explicit coverage for 'и' -> 'i' (English-style phonetic)
    s_norm_en = s0.replace('и', 'i').replace('ы', 'i').replace('і', 'i')
    if s_norm_en != s0:
        v.add(s_norm_en)

    # Cross-language phonetic normalization
    for k, p in _PHONETIC_ALIASES.items():
        if k in s0:
            v.add(s0.replace(k, p))
            v.add(_translit_cyr_to_lat(s0.replace(k, p)))

    alias = _fold(normalize_folder_voice_query(s))
    if alias and alias != s0:
        v.add(_fold(alias))
        v.add(_translit_cyr_to_lat(_fold(alias)))

    # Strip common Russian/Ukrainian case endings so that the voice query
    # "диплома" (genitive) fast-matches the folder "Диплом" without fuzzy walk.
    # Ordered longest-first so we don't over-strip multi-char endings.
    # Minimum stem length 4 prevents stripping short words like "лаб" → "л".
    _CYR_CASE_SUFFIXES = ('ами', 'ями', 'ого', 'его', 'ому', 'ему',
                          'ом', 'ем', 'ой', 'ей', 'ах', 'ях',
                          'а', 'я', 'ы', 'и', 'у', 'е')
    for suffix in _CYR_CASE_SUFFIXES:
        if s0.endswith(suffix) and len(s0) - len(suffix) >= 4:
            stem = s0[: -len(suffix)]
            v.add(stem)
            v.add(_translit_cyr_to_lat(stem))
            break  # only strip the longest matching suffix

    return [x for x in v if x]
def calculate_match_score(q: str, e: str) -> int:
    score = max(
        fuzz.token_set_ratio(q, e),
        fuzz.partial_ratio(q, e),
        fuzz.ratio(q, e),
        int(fuzz.WRatio(q, e)),
    )
    # Penalize substring length mismatches
    q_len = len(q)
    e_len = len(e)
    if q_len > 0 and e_len > 0:
        ratio = min(q_len, e_len) / max(q_len, e_len)
        if ratio < 0.8:
            score = int(score * (ratio ** 0.5))
    return int(score)
def _get_search_depth() -> int:
    """Read folder search depth from settings (default 4, range 1-10)."""
    try:
        import json
        from config_pack.config import get_settings_path
        p = get_settings_path()
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return max(1, min(int(json.load(f).get('folder_search_depth', 4)), 10))
    except Exception:
        pass
    return 4

def folder_search_roots_and_depth(base_ctx: str) -> tuple[list[str], int]:
    depth = _get_search_depth()
    try:
        base = Path(base_ctx).resolve()
    except Exception:
        base = Path(base_ctx)
    if base.is_file():
        base = base.parent
    if not base.exists():
        from core.system.windows import get_known_folder_path
        dk = get_known_folder_path('desktop')
        if dk:
            base = Path(dk)
        else:
            base = Path(USER_HOME) / "Desktop"
    return ([str(base)], depth)
def _depth_limited_walk(root: str, max_depth: int):
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for cur, dirs, files in os.walk(root):
        depth = cur.rstrip(os.sep).count(os.sep) - base_depth
        if depth >= max_depth:
            dirs[:] = []
        else:
            dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in (
                'dist', 'build', 'node_modules', 'venv', '.venv', '__pycache__', 'out', 'bin', 'obj'
            )]
        yield cur, dirs
def _find_folder_anywhere(start_dirs: list[str], name: str, max_depth: int = 4) -> Path | None:
    name = normalize_folder_voice_query(name)
    query_vars = get_name_variants(name)
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
                ev = get_name_variants(entry.name)
                if any(q == e for q in query_vars for e in ev):
                    return entry
        except Exception:
            pass
        for cur, dirs in _depth_limited_walk(root, max_depth=max_depth):
            for d in dirs:
                dv = get_name_variants(d)
                score = 0
                for q in query_vars:
                    for e in dv:
                        s = calculate_match_score(q, e)
                        if s > score:
                            score = s
                if score >= 90:
                    return Path(cur) / d
                if score >= 85:
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
# Кеш результатов поиска папок (директория -> {имя -> путь})
_FOLDER_SEARCH_CACHE: dict[str, dict[str, Path]] = {}
_CACHE_TIMESTAMPS: dict[str, float] = {}

def _normalize_for_comparison(s: str) -> str:
    """Нормализует строку для сравнения (убирает пробелы, подчёркивания, дефисы)"""
    s = s.casefold().strip()
    for char in [' ', '_', '-']:
        s = s.replace(char, '')
    return s

def _invalidate_folder_cache_if_needed(base_dir: str) -> None:
    """Инвалидирует кеш если директория была изменена"""
    import time
    base_path = Path(base_dir)
    if not base_path.exists():
        return

    try:
        # Получаем время последнего изменения директории
        mod_time = base_path.stat().st_mtime
        cached_time = _CACHE_TIMESTAMPS.get(base_dir)

        # Если директория изменилась - очищаем кеш
        if cached_time is None or mod_time > cached_time:
            if base_dir in _FOLDER_SEARCH_CACHE:
                del _FOLDER_SEARCH_CACHE[base_dir]
            _CACHE_TIMESTAMPS[base_dir] = time.time()
    except Exception:
        pass

def _find_subdir_ci_or_fuzzy(base_dir: str, name: str, fuzzy_threshold: int=75) -> Path | None:
    """
    Динамический поиск папки без хардкодированных алиасов (с кешированием).

    Стратегия:
    1. Точное совпадение (case-insensitive, пробелы/подчёркивания игнорируются)
    2. Транслитерационные варианты (русский <-> латиница)
    3. Fuzzy matching на основе токенов

    Результаты кешируются для улучшения производительности.
    """
    name = normalize_folder_voice_query((name or "").strip())
    if not name:
        return None

    base = Path(base_dir)
    base_str = str(base)

    # Инвалидируем кеш если директория изменилась
    _invalidate_folder_cache_if_needed(base_str)

    # Проверяем кеш
    if base_str in _FOLDER_SEARCH_CACHE:
        cache = _FOLDER_SEARCH_CACHE[base_str]
        name_normalized = _normalize_for_comparison(name)
        # Проверяем точное совпадение в кеше
        if name_normalized in cache:
            return cache[name_normalized]

    subdirs = _list_subdirs(base)
    if not subdirs:
        return None

    # Нормализуем запрос для сравнения
    name_normalized = _normalize_for_comparison(name)

    # Шаг 1: Точное совпадение (case-insensitive, игнорируем пробелы/подчёркивания)
    for entry in subdirs:
        if _normalize_for_comparison(entry.name) == name_normalized:
            # Кешируем результат
            if base_str not in _FOLDER_SEARCH_CACHE:
                _FOLDER_SEARCH_CACHE[base_str] = {}
            _FOLDER_SEARCH_CACHE[base_str][name_normalized] = entry
            return entry

    # Шаг 2: Проверяем транслитерационные варианты
    query_vars = get_name_variants(name)
    for entry in subdirs:
        entry_vars = get_name_variants(entry.name)
        if any(q == e for q in query_vars for e in entry_vars):
            if base_str not in _FOLDER_SEARCH_CACHE:
                _FOLDER_SEARCH_CACHE[base_str] = {}
            _FOLDER_SEARCH_CACHE[base_str][name_normalized] = entry
            return entry

    # Шаг 3: Fuzzy matching на основе транслитерационных вариантов
    best_match: tuple[Path, int] | None = None
    for entry in subdirs:
        entry_vars = get_name_variants(entry.name)
        for q in query_vars:
            for e in entry_vars:
                score = calculate_match_score(q, e)
                if best_match is None or score > best_match[1]:
                    best_match = (entry, score)

    if best_match and best_match[1] >= 80:
        if base_str not in _FOLDER_SEARCH_CACHE:
            _FOLDER_SEARCH_CACHE[base_str] = {}
        _FOLDER_SEARCH_CACHE[base_str][name_normalized] = best_match[0]
        return best_match[0]

    # Шаг 4: Fuzzy matching по нормализованным именам
    dir_names_normalized = [(p.name, _normalize_for_comparison(p.name)) for p in subdirs]
    best_fuzzy = None
    best_score = 0
    for orig_name, norm_name in dir_names_normalized:
        score = fuzz.token_set_ratio(name_normalized, norm_name)
        if score > best_score:
            best_score = score
            best_fuzzy = orig_name

    if best_fuzzy and best_score >= fuzzy_threshold:
        result = base / best_fuzzy
        if base_str not in _FOLDER_SEARCH_CACHE:
            _FOLDER_SEARCH_CACHE[base_str] = {}
        _FOLDER_SEARCH_CACHE[base_str][name_normalized] = result
        return result

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
    # Strictly forward search unless permitted in settings
    try:
        import json, os
        settings_path = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(settings_path):
            with open(settings_path, encoding='utf-8') as f:
                allow_parent = json.load(f).get('allow_parent_search', False)
        else:
            allow_parent = False
    except Exception:
        allow_parent = False
        
    roots, max_dep = folder_search_roots_and_depth(str(base_ctx))
    if not allow_parent:
        # Filter roots to only include the base itself for searching deeper
        roots = [str(base)] 

    found = _find_folder_anywhere(roots, hint, max_depth=max_dep)
    if found is not None and found.is_dir():
        return (found.resolve(), None)
    warn = f"Папка «{hint}» не найдена, создаю в текущем расположении."
    return (base, warn)
