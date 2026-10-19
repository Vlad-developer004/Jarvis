"""Game profile editor backend: key bindings, macros and Hogwarts spell slots, the same edits the old keybind / spell editors made.

Profiles are the JSON files in actions.game_input.PROFILES_DIR (`<game>.json`, `<game>_uk.json`). Rows and macros are addressed by a
row id (`b:<binding>` or `s:<index>` into the profile's spell list); the UI refetches after every change, so indexes never go stale.
Every write goes through the same rules as the old dialog (a real key set on a spell drops its macro sequence, a deleted macro is
removed by name) and reloads the profile when it is the active game.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading

_log = logging.getLogger(__name__)
_lock = threading.RLock()

# extension id -> words of the profile name (same mapping the old editor used to decide which games are installed)
_EXT_GAME_MAP = {
    'game_ets2': ('euro truck', 'ets2', 'ets'),
    'game_fs22': ('farming simulator', 'fs22', 'farming'),
    'game_hogwarts': ('hogwarts', 'harry potter'),
    'game_planetbase': ('planetbase',),
}
_SHORT = (('EURO TRUCK SIMULATOR', 'ETS 2'), ('FARMING SIMULATOR', 'FS 22'), ('HOGWARTS LEGACY', 'HOGWARTS'))
_LABELS_RU = {
    'engine': 'Двигатель', 'handbrake': 'Стояночный тормоз', 'cruise': 'Круиз-контроль', 'cruise_up': 'Круиз: больше', 'cruise_down': 'Круиз: меньше',
    'differential': 'Дифференциал', 'axle_lift': 'Подъём оси', 'trailer': 'Прицеп', 'lights_main': 'Фары ближний', 'lights_high': 'Фары дальний',
    'strobe': 'Проблесковые огни', 'turn_left': 'Поворотник левый', 'turn_right': 'Поворотник правый', 'hazard': 'Аварийка', 'horn': 'Клаксон',
    'air_horn': 'Пневмосигнал', 'wipers': 'Дворники', 'info': 'Инфо', 'navigator': 'Навигатор', 'action': 'Действие', 'gear_up': 'Передача выше',
    'gear_down': 'Передача ниже', 'refuel': 'Заправка',
}
_LABELS_UK = {
    'engine': 'Двигун', 'handbrake': 'Стоянкове гальмо', 'cruise': 'Круїз-контроль', 'cruise_up': 'Круїз: більше', 'cruise_down': 'Круїз: менше',
    'differential': 'Диференціал', 'axle_lift': 'Підйом осі', 'trailer': 'Причіп', 'lights_main': 'Фари ближнє', 'lights_high': 'Фари дальнє',
    'strobe': 'Проблискові вогні', 'turn_left': 'Поворотник лівий', 'turn_right': 'Поворотник правий', 'hazard': 'Аварійка', 'horn': 'Клаксон',
    'air_horn': 'Пневмосигнал', 'wipers': 'Двірники', 'info': 'Інфо', 'navigator': 'Навігатор', 'action': 'Дія', 'gear_up': 'Передача вище',
    'gear_down': 'Передача нижче', 'refuel': 'Заправка',
}
_TELEMETRY = {
    'cruise_set': 'Установка скорости круиза (через API)', 'cruise_adjust': 'Подстройка скорости круиза (через API)', 'cruise_limit': 'Круиз по ограничению (через API)',
    'auto_cruise_on': 'Активация адаптивного круиза (AI)', 'auto_cruise_off': 'Деактивация адаптивного круиза (AI)', 'go_to_sleep': 'Симуляция сна (через API)',
    'close_game': 'Экстренный выход из игры', 'gear_set': 'Установка передачи (через API)',
}
_SHORT_LABEL = {
    'Запуск двигателя': 'Двигатель', 'Запуск / Остановка Двигателя': 'Двигатель', 'Газ / Ускорение': 'Газ', 'Тормоз / Остановка': 'Тормоз',
    'Покинуть / Сесть в технику': 'Техника', 'Следующая машина в списке': 'След. техника', 'Предыдущая машина в списке': 'Пред. техника',
    'Передача: Выше': 'Передача +', 'Передача: Ниже': 'Передача -',
    'Запуск двигуна': 'Двигун', 'Запуск / Зупинка Двигуна': 'Двигун', 'Газ / Прискорення': 'Газ', 'Гальмо / Зупинка': 'Гальмо',
    'Покинути / Сісти в техніку': 'Техніка', 'Наступна машина в списку': 'Наст. техніка', 'Попередня машина в списку': 'Попер. техніка',
    'Передача: Вище': 'Передача +', 'Передача: Нижче': 'Передача -',
}
_KEY_RE = re.compile(r"^(?:[a-z0-9_]{1,16}|[\[\];'`\-=\\,./])$")
_MAX_STEPS = 60


def _lang_uk() -> bool:
    try:
        from core import i18n
        return i18n.get_language() == 'uk'
    except Exception:
        return False


def _labels() -> dict:
    return _LABELS_UK if _lang_uk() else _LABELS_RU


def _dir():
    from actions.game_input import PROFILES_DIR
    return PROFILES_DIR


def _clean(name: str) -> str:
    t = re.sub(r'\s*\([^)]*\)', '', name or '')
    t = t.split(' / ')[0].strip()
    return _SHORT_LABEL.get(name, _SHORT_LABEL.get(t, t))


def _profiles() -> dict:
    """game name -> (path, data) for the current language."""
    uk = _lang_uk()
    out = {}
    try:
        files = sorted(_dir().glob('*.json'))
    except OSError:
        return out
    for p in files:
        if uk != p.stem.endswith('_uk'):
            continue
        try:
            d = json.loads(p.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            continue
        name = str(d.get('game', p.stem))
        out[name[:-3] if name.endswith('_uk') else name] = (p, d)
    return out


def _installed_ids() -> set:
    try:
        from core.extensions import ExtensionManager
        return {e['id'] for e in ExtensionManager().list_installed()}
    except Exception:
        return set()


def _kind(name: str) -> str:
    low = name.lower()
    return 'hogwarts' if 'hogwarts' in low else ''


def _short(name: str) -> str:
    up = name.upper()
    return next((s for k, s in _SHORT if k in up), up)


def _active() -> tuple[str, bool]:
    m = sys.modules.get('__main__')
    return (getattr(m, '_game_profile', '') if m else '', bool(getattr(m, '_game_mode', False)) if m else False)


def _grid_slot(s: dict) -> bool:
    return s.get('set') in (1, 2, 3, 4) and str(s.get('key', '')) in ('1', '2', '3', '4')


def list_games() -> list[dict]:
    ids, active = _installed_ids(), _active()[0]
    profs = _profiles()
    shown = [g for g in profs if any(e in ids and any(w in g.lower() for w in words) for e, words in _EXT_GAME_MAP.items())]
    if not shown and not ids:
        shown = list(profs)                                    # extension manager unavailable: show everything, like the old editor
    shown.sort(key=lambda g: (0 if 'euro truck' in g.lower() or 'ets' in g.lower() else 1, g))
    return [{'game': g, 'short': _short(g), 'active': g == active, 'kind': _kind(g)} for g in shown]


def _row_key(spell: dict) -> str:
    return ','.join(spell['keys']) if spell.get('keys') else str(spell.get('key') or '')


def get_game(game: str) -> dict | None:
    prof = _profiles().get(game)
    if prof is None:
        return None
    data = prof[1]
    lab = _labels()
    hog = _kind(game) == 'hogwarts'
    rows = [{'id': 'b:' + b, 'label': lab.get(b, b.replace('_', ' ').capitalize()), 'key': '' if v in ('MACRO', '—', 'ИНФО') else str(v or ''), 'kind': 'binding'}
            for b, v in (data.get('bindings') or {}).items()]
    macros, grid = [], {s: {} for s in (1, 2, 3, 4)}
    spells = data.get('spells') or []
    for i, s in enumerate(spells):
        name = str(s.get('name') or '')
        if hog and _grid_slot(s):
            grid[s['set']][int(s['key'])] = name
        has_seq = bool(s.get('sequence'))
        if hog and _grid_slot(s):
            continue
        direct = bool(s.get('key') or s.get('keys')) and not s.get('mouse')
        if direct:
            key = _row_key(s)
            rows.append({'id': f's:{i}', 'label': _clean(name), 'key': '' if key == 'MACRO' else key, 'kind': 'entry', 'macro': has_seq})
        elif has_seq:
            macros.append({'idx': i, 'name': name, 'variants': [str(v) for v in (s.get('variants') or [])][:8], 'steps': len(s['sequence']),
                           'telemetry': _TELEMETRY.get(s.get('telemetry_action'), '') if s.get('telemetry_action') else ''})
    slottable = [str(s['name']) for s in spells if s.get('name') and not s.get('mouse') and (not s.get('key') or str(s.get('key')) in ('1', '2', '3', '4'))]
    return {'game': game, 'kind': _kind(game), 'rows': rows, 'macros': macros, 'grid': {str(k): {str(a): b for a, b in v.items()} for k, v in grid.items()},
            'slottable': slottable, 'binds': [{'id': b, 'label': lab.get(b, b)} for b in (data.get('bindings') or {})]}


def _write(game: str, path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    name, mode = _active()
    if mode and name == game:
        try:
            from actions.game_input import load_profile
            load_profile(path.stem)
        except Exception:
            _log.debug('profile reload failed', exc_info=True)


def _spell(data: dict, idx) -> dict | None:
    spells = data.get('spells') or []
    try:
        i = int(idx)
    except (TypeError, ValueError):
        return None
    return spells[i] if 0 <= i < len(spells) else None


def set_key(game: str, row: str, key: str) -> dict:
    key = str(key or '').strip().lower()
    if key and not _KEY_RE.match(key):
        return {'ok': False, 'error': 'bad_key'}
    with _lock:
        prof = _profiles().get(game)
        if prof is None:
            return {'ok': False, 'error': 'unknown_game'}
        path, data = prof
        if row.startswith('b:') and row[2:] in (data.get('bindings') or {}):
            data['bindings'][row[2:]] = key
        elif row.startswith('s:') and (sp := _spell(data, row[2:])) is not None:
            sp['key'] = key
            if key and 'sequence' in sp and not sp.get('telemetry_action'):
                sp.pop('sequence', None)                      # a real key replaces the macro, as in the old editor
        else:
            return {'ok': False, 'error': 'unknown_row'}
        _write(game, path, data)
    return {'ok': True}


def test(game: str, row: str) -> dict:
    prof = _profiles().get(game)
    if prof is None:
        return {'ok': False, 'error': 'unknown_game'}
    data = prof[1]
    if row.startswith('s:') and (sp := _spell(data, row[2:])) is not None:
        name = str(sp.get('name') or '')
    elif row.startswith('b:') and row[2:] in (data.get('bindings') or {}):
        name = _labels().get(row[2:], row[2:])
    else:
        return {'ok': False, 'error': 'unknown_row'}
    from actions.game_input import execute_by_name
    threading.Thread(target=lambda: execute_by_name(name), name='ui-bridge-keytest', daemon=True).start()
    return {'ok': True}


def macro_get(game: str, idx) -> dict:
    prof = _profiles().get(game)
    sp = _spell(prof[1], idx) if prof else None
    if sp is None:
        return {'ok': False, 'error': 'unknown_macro'}
    data = prof[1]
    seq = []
    for st in sp.get('sequence') or []:
        if st.get('key') == 'MACRO':                           # placeholder: the entry's own binding or key
            if sp.get('binding'):
                st = {'binding': sp['binding'], 'hold': st.get('hold', 0.1)}
            elif sp.get('key') and sp['key'] != 'MACRO':
                st = {'key': sp['key'], 'hold': st.get('hold', 0.1)}
            else:
                real = (data.get('bindings') or {}).get(sp.get('binding', ''), '')
                if real and real != 'MACRO':
                    st = {'key': real, 'hold': st.get('hold', 0.1)}
        seq.append(st)
    if not seq and sp.get('key') and sp['key'] != 'MACRO':
        seq = [{'key': sp['key'], 'hold': 0.1}]
    elif not seq and sp.get('binding'):
        seq = [{'binding': sp['binding']}]
    return {'ok': True, 'name': sp.get('name', ''), 'variants': [str(v) for v in (sp.get('variants') or [])], 'sequence': seq,
            'telemetry': _TELEMETRY.get(sp.get('telemetry_action'), '') if sp.get('telemetry_action') else ''}


def _clean_sequence(raw, binds: set) -> list | None:
    if not isinstance(raw, list) or len(raw) > _MAX_STEPS:
        return None
    out = []
    for st in raw:
        if not isinstance(st, dict):
            return None
        s = {}
        try:
            if 'wait' in st:
                s['wait'] = min(60.0, max(0.0, float(st['wait'])))
            elif 'binding' in st:
                if st['binding'] not in binds:
                    return None
                s['binding'] = st['binding']
                if 'hold' in st:
                    s['hold'] = min(10.0, max(0.0, float(st['hold'])))
            elif 'key' in st:
                k = str(st['key']).strip().lower()
                if not _KEY_RE.match(k):
                    return None
                s['key'] = k
                s['hold'] = min(10.0, max(0.0, float(st.get('hold', 0.1))))
            else:
                return None
        except (TypeError, ValueError):
            return None
        if st.get('_disabled'):
            s['_disabled'] = True
        out.append(s)
    return out


def macro_save(game: str, idx, sequence, variants=None) -> dict:
    with _lock:
        prof = _profiles().get(game)
        sp = _spell(prof[1], idx) if prof else None
        if sp is None:
            return {'ok': False, 'error': 'unknown_macro'}
        path, data = prof
        seq = _clean_sequence(sequence, set((data.get('bindings') or {}).keys()))
        if seq is None:
            return {'ok': False, 'error': 'bad_sequence'}
        sp['sequence'] = seq
        if isinstance(variants, list):
            v = [str(x).strip().lower()[:60] for x in variants if str(x).strip()][:30]
            if v:
                sp['variants'] = v
        _write(game, path, data)
    return {'ok': True}


def macro_create(game: str, name: str, variants, first: str) -> dict:
    name = str(name or '').strip()[:60]
    if not name:
        return {'ok': False, 'error': 'no_name'}
    vs = [str(v).strip().lower()[:60] for v in (variants if isinstance(variants, list) else []) if str(v).strip()][:30] or [name.lower()]
    with _lock:
        prof = _profiles().get(game)
        if prof is None:
            return {'ok': False, 'error': 'unknown_game'}
        path, data = prof
        first = str(first or '')
        step = {'binding': first} if first in (data.get('bindings') or {}) else {'wait': 0.5}
        data.setdefault('spells', []).append({'name': name, 'variants': vs, 'sequence': [step]})
        _write(game, path, data)
        return {'ok': True, 'idx': len(data['spells']) - 1}


def macro_delete(game: str, idx) -> dict:
    with _lock:
        prof = _profiles().get(game)
        sp = _spell(prof[1], idx) if prof else None
        if sp is None:
            return {'ok': False, 'error': 'unknown_macro'}
        path, data = prof
        data['spells'] = [s for s in data['spells'] if s.get('name') != sp.get('name')]     # by name, as the old editor did
        _write(game, path, data)
    return {'ok': True}


def grid_set(game: str, set_num, slot, name: str) -> dict:
    """Puts a spell into F<set> slot <slot> (name '' or '—' empties it); a spell that sat in another slot leaves it."""
    try:
        sn, sl = int(set_num), int(slot)
    except (TypeError, ValueError):
        return {'ok': False, 'error': 'bad_slot'}
    if sn not in (1, 2, 3, 4) or sl not in (1, 2, 3, 4):
        return {'ok': False, 'error': 'bad_slot'}
    name = '' if name == '—' else str(name or '')
    with _lock:
        prof = _profiles().get(game)
        if prof is None or _kind(game) != 'hogwarts':
            return {'ok': False, 'error': 'unknown_game'}
        path, data = prof
        spells = data.get('spells') or []
        for s in spells:                                       # empty the target slot
            if s.get('set') == sn and str(s.get('key')) == str(sl):
                s.pop('set', None)
                s.pop('key', None)
        if name:
            target = next((s for s in spells if s.get('name') == name and not s.get('mouse')), None)
            if target is None:
                return {'ok': False, 'error': 'unknown_spell'}
            target['set'], target['key'] = sn, str(sl)
        _write(game, path, data)
    return {'ok': True}
