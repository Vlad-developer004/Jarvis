import os
import re
import json
from rapidfuzz import fuzz
from typing import Optional, Dict
GAME_CACHE_FILE = os.path.join('data', 'game_cache.json')
def _load_game_cache() -> Dict[str, str]:
    if os.path.exists(GAME_CACHE_FILE):
        try:
            with open(GAME_CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}
def _save_game_cache(cache: Dict[str, str]):
    try:
        os.makedirs(os.path.dirname(GAME_CACHE_FILE), exist_ok=True)
        with open(GAME_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
_GAME_CACHE_MEM = _load_game_cache()
def find_game_executable(install_dir: str, game_name: str) -> Optional[str]:
    if not install_dir or not os.path.exists(install_dir):
        return None
    cache_key = f'{install_dir}|{game_name}'
    if cache_key in _GAME_CACHE_MEM:
        cached_path = _GAME_CACHE_MEM[cache_key]
        if os.path.exists(cached_path):
            return cached_path
    exes = []
    priority_dirs = ['bin', 'binaries', 'win64', 'win32', 'x64', 'game']
    for p_dir in priority_dirs:
        p_path = os.path.join(install_dir, p_dir)
        if os.path.exists(p_path):
            for f in os.listdir(p_path):
                if f.lower().endswith('.exe'):
                    exes.append(os.path.join(p_path, f))
    if not exes:
        for root, dirs, files in os.walk(install_dir):
            depth = root[len(install_dir):].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            for f in files:
                if f.lower().endswith('.exe'):
                    exes.append(os.path.join(root, f))
    if not exes:
        return None
    best_match = None
    max_score = 0
    clean_game_name = re.sub('[^a-zA-Z0-9\\s]', '', game_name).lower()
    avoid_words = ['launcher', 'setup', 'unins', 'crash', 'unity', 'eac', 'anticheat']
    potential_candidates = []
    for exe in exes:
        name = os.path.basename(exe).lower()
        if any((w in name for w in avoid_words)):
            continue
        potential_candidates.append(exe)
    if not potential_candidates:
        potential_candidates = exes
    for exe in potential_candidates:
        name = os.path.basename(exe).lower()
        score = fuzz.partial_ratio(clean_game_name, name)
        if score > max_score:
            max_score = score
            best_match = exe
    if max_score > 70:
        found_exe = best_match
    else:
        potential_candidates.sort(key=lambda x: os.path.getsize(x), reverse=True)
        found_exe = potential_candidates[0]
    if found_exe:
        _GAME_CACHE_MEM[cache_key] = found_exe
        _save_game_cache(_GAME_CACHE_MEM)
        return found_exe
    return None
def transliterate_cyrillic_to_latin(text: str) -> str:
    mapping = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'}
    text = text.lower().strip()
    replacements = {
        'нукляр': 'nuclear', 'нуклеар': 'nuclear', 'опшн': 'option', 'опшен': 'option',
        'планнет': 'planet', 'бэйс': 'base', 'тейл': 'tale', 'крафт': 'craft',
        'симулятор': 'simulator', 'симулятора': 'simulator',
        ' два': ' 2', ' три': ' 3', ' четыре': ' 4', ' пять': ' 5',
        'вар': 'war', 'сандер': 'thunder', 'сим': 'sim', 'зона': 'zone',
        'бэтл': 'battle', 'филд': 'field', 'сити': 'city', 'эйс': 'ase', 'айс': 'ice',
        'стар': 'star', 'филд': 'field', 'скайрим': 'skyrim', 'киберпанк': 'cyberpunk',
        'ведьмак': 'witcher', 'нид фор спид': 'need for speed', 'гта': 'gta',
        'стим': 'steam', 'брейв': 'brave', 'хром': 'chrome', 'дискорд': 'discord',
        'телеграм': 'telegram', 'телега': 'telegram', 'спотифай': 'spotify',
        'евротрак симулятор два': 'euro truck simulator 2',
        'евротрак симулятор 2': 'euro truck simulator 2',
        'евротрак': 'euro truck',
        'еврo трак': 'euro truck',
        'етс два': 'euro truck simulator 2',
        'ets два': 'euro truck simulator 2',
        'етс 2': 'euro truck simulator 2',
        'ets 2': 'euro truck simulator 2',
        'етс': 'euro truck simulator', 'ets': 'euro truck simulator'
    }
    for ru, en in replacements.items():
        text = text.replace(ru, en)
    res = []
    for char in text:
        res.append(mapping.get(char, char))
    trans = ''.join(res)
    trans = re.sub('(.)\\1+', '\\1', trans)
    return trans
def fuzzy_find_game(games, query: str):
    if not games:
        return None
    query = query.lower().strip()
    trans_query = transliterate_cyrillic_to_latin(query)
    best_match = None
    best_score = 0
    for game in games:
        name_lower = game.name.lower()
        clean_name = re.sub('(.)\\1+', '\\1', name_lower)
        score_raw = fuzz.token_set_ratio(query, name_lower)
        score_trans = fuzz.token_set_ratio(trans_query, name_lower)
        score_partial = fuzz.partial_ratio(trans_query, name_lower)
        score = max(score_raw, score_trans, score_partial)
        if score > best_score:
            best_score = score
            best_match = game
    if best_score >= 75:
        return best_match
    return None
