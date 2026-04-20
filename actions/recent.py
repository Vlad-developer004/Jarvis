import os
from pathlib import Path
from rapidfuzz import fuzz, process
from actions.filesystem import get_name_variants, calculate_match_score

USER_HOME = os.path.expanduser('~')
SCAN_DIRS = [os.path.join(USER_HOME, 'Documents'), os.path.join(USER_HOME, 'Desktop'), os.path.join(USER_HOME, 'Downloads'), os.path.join(USER_HOME, 'OneDrive', 'Documents'), os.path.join(USER_HOME, 'OneDrive', 'Desktop')]
FILE_TYPES = {'document': {'.docx', '.doc', '.odt', '.pdf'}, 'spreadsheet': {'.xlsx', '.xls', '.ods'}, 'presentation': {'.pptx', '.ppt', '.odp'}, 'any': None}
def _scan_recent_files(file_type: str='any', limit: int=5) -> list[str]:
    extensions = FILE_TYPES.get(file_type)
    found = []
    for scan_dir in SCAN_DIRS:
        if not os.path.isdir(scan_dir):
            continue
        try:
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                depth = root.replace(scan_dir, '').count(os.sep)
                if depth >= 3:
                    dirs.clear()
                    continue
                for f in files:
                    fp = os.path.join(root, f)
                    ext = Path(fp).suffix.lower()
                    if extensions is not None and ext not in extensions:
                        continue
                    if extensions is None and ext in {'.ini', '.db', '.tmp', '.log', '.lnk', '.sys'}:
                        continue
                    try:
                        mtime = os.path.getmtime(fp)
                        found.append((fp, mtime))
                    except Exception:
                        continue
        except Exception:
            continue
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
    
    for scan_dir in SCAN_DIRS:
        if not os.path.isdir(scan_dir):
            continue
        try:
            for root, dirs, files in os.walk(scan_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                depth = root.replace(scan_dir, '').count(os.sep)
                if depth >= 3:
                    dirs.clear()
                    continue
                for f in files:
                    p_obj = Path(f)
                    ext = p_obj.suffix.lower()
                    if extensions is not None and ext not in extensions:
                        continue
                        
                    stem = p_obj.stem
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
                if best_score >= 98:
                    break
        except Exception:
            continue
            
    if best_path and best_score >= 75:
        try:
            os.startfile(best_path)
            return (True, f'Открываю: {best_name}')
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
        os.startfile(target)
        name = Path(target).name
        prefix = 'Последний' if offset == 0 else 'Предпоследний'
        return (True, f'{prefix}: {name}')
    except Exception as e:
        return (False, str(e))
