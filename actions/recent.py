import os
from pathlib import Path
from rapidfuzz import fuzz, process
from actions.file_walk import walk
from actions.filesystem import get_name_variants, calculate_match_score

USER_HOME = os.path.expanduser('~')
SCAN_DIRS = [os.path.join(USER_HOME, 'Documents'), os.path.join(USER_HOME, 'Desktop'), os.path.join(USER_HOME, 'Downloads'), os.path.join(USER_HOME, 'OneDrive', 'Documents'), os.path.join(USER_HOME, 'OneDrive', 'Desktop')]
FILE_TYPES = {'document': {'.docx', '.doc', '.odt', '.pdf'}, 'spreadsheet': {'.xlsx', '.xls', '.ods'}, 'presentation': {'.pptx', '.ppt', '.odp'}, 'any': None}
_SCAN_DEPTH = 3   # levels below each scan folder
_IGNORED_EXTS = ('.ini', '.db', '.tmp', '.log', '.lnk', '.sys')
def _scan_recent_files(file_type: str='any', limit: int=5) -> list[str]:
    extensions = FILE_TYPES.get(file_type)
    try:
        entries = walk(SCAN_DIRS, _SCAN_DEPTH, 'files', exts=extensions, skip_exts=_IGNORED_EXTS)
    except Exception:
        return []
    found = [(os.path.join(parent, name), mtime) for parent, name, mtime in entries]
    found.sort(key=lambda x: x[1], reverse=True)
    return [fp for fp, _ in found[:limit]]
def search_and_open_file(query: str, file_type: str='any') -> tuple[bool, str]:
    query = (query or "").strip()
    if not query:
        return (False, "Пустой запрос")
        
    query_vars = get_name_variants(query)
    if not query_vars:
        return (False, "Некорректный запрос")
        
    extensions = FILE_TYPES.get(file_type)
    best_score = 0
    best_path = None
    best_name = None
    
    # Thresholds: 88+ is very likely a match, 72+ is a candidate
    # We collect all candidates and pick the one with the highest absolute score
    
    try:
        entries = walk(SCAN_DIRS, _SCAN_DEPTH, 'files', exts=extensions)
    except Exception:
        entries = []
    for root, f, _mtime in entries:
        stem = Path(f).stem
        # Generate variants for the filename too (translit etc)
        file_vars = get_name_variants(stem)

        current_file_best = 0
        for q in query_vars:
            for ev in file_vars:
                # Use token_set_ratio as it's better for multi-word queries
                # and WRatio for general fuzzy matching
                s = max(
                    calculate_match_score(q, ev),
                    int(fuzz.token_set_ratio(q, ev))
                )
                if s > current_file_best:
                    current_file_best = s

        if current_file_best > best_score:
            best_score = current_file_best
            best_path = os.path.join(root, f)
            best_name = f

        # Early exit for near-perfect match to save time
        if best_score >= 98:
            break
            
    if best_path and best_score >= 75:
        try:
            from core.safe_open import open_user_file
            open_user_file(best_path)
            return (True, f'Открываю: {best_name}')
        except PermissionError:
            return (False, 'Исполняемые файлы я не запускаю по команде')
        except Exception as e:
            return (False, str(e))
            
    return (False, f"Файл '{query}' не найден")
def open_recent_file(file_type: str='any', offset: int=0) -> tuple[bool, str]:
    files = _scan_recent_files(file_type, limit=offset + 3)
    if offset >= len(files):
        type_names = {'document': 'документов', 'spreadsheet': 'таблиц', 'presentation': 'презентаций', 'any': 'файлов'}
        return (False, f'Нет недавних {type_names.get(file_type, 'файлов')}')
    target = files[offset]
    try:
        from core.safe_open import open_user_file
        open_user_file(target)
        name = Path(target).name
        prefix = 'Последний' if offset == 0 else 'Предпоследний'
        return (True, f'{prefix}: {name}')
    except Exception as e:
        return (False, str(e))
