import json
import re
import time
from pathlib import Path
try:
    import pydirectinput as _input
    _input.PAUSE = 0
except ImportError:
    import pyautogui as _input
PROFILES_DIR = Path('data') / 'game_profiles'
_profile_name: str = ''
_entries: list[dict] = []
_flat: list[tuple[str, dict]] = []
_bindings: dict = {}
_last_cast: dict[str, float] = {}
def press_robust(key: str, duration: float = 0.15):
    """
    Iron-clad key press for DirectX games.
    Holds the key for a short duration to ensure registration.
    """
    if not key:
        return
    try:
        _input.keyDown(key)
        time.sleep(duration)
        _input.keyUp(key)
    except Exception:
        # Fallback to simple press if keyDown/Up fails or not supported
        try:
            _input.press(key)
        except Exception:
            pass
def get_binding(name: str, default: str = '') -> str:
    return _bindings.get(name, default)
CAST_COOLDOWN = 1.0
def _telem_wiper_state() -> int | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return 1 if data.get("wipers") else 0
    except Exception:
        return None
def _telem_lights_low() -> bool | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return bool(data.get("lightsBeamLow"))
    except Exception:
        return None
def _telem_lights_high() -> bool | None:
    try:
        from actions.ets2_telemetry import get as _tget
        data = _tget()
        if data is None:
            return None
        return bool(data.get("lightsBeamHigh"))
    except Exception:
        return None
def _installed_profile_stems() -> set[str]:
    try:
        from core.extensions import ExtensionManager
        ext = ExtensionManager()
        installed_stems: set[str] = set()
        for e in ext.list_installed():
            fname = e.get('file', '')
            if fname.endswith('.json'):
                installed_stems.add(fname[:-5])
        return installed_stems
    except Exception:
        return {p.stem for p in PROFILES_DIR.glob('*.json')}
def get_available_profiles() -> list[str]:
    installed = _installed_profile_stems()
    return [p.stem for p in PROFILES_DIR.glob('*.json') if p.stem in installed]
def _strip_json_comments(text: str) -> str:
    pattern = r'(?x) "(?:\\.|[^"\\])*" | (?://[^\n]*) | (/\*.*?\*/)'
    def _replacer(match):
        s = match.group(0)
        if s.startswith('"'):
            return s
        return ""
    return re.sub(pattern, _replacer, text, flags=re.DOTALL)
def load_profile(profile_name: str) -> tuple[bool, str]:
    global _profile_name, _entries, _flat, _bindings
    if profile_name not in _installed_profile_stems():
        return (False, f"Расширение для профиля '{profile_name}' не установлено. Откройте Менеджер расширений в HUD и установите нужный профиль.")
    path = PROFILES_DIR / f'{profile_name}.json'
    if not path.exists():
        available = get_available_profiles()
        return (False, f"Профиль '{profile_name}' не найден. Доступны: {', '.join(available)}")
    try:
        raw_text = path.read_text(encoding='utf-8')
        clean_text = _strip_json_comments(raw_text)
        data = json.loads(clean_text)
        bindings: dict = data.get('bindings', {})
        _bindings = dict(bindings)
        _entries = data.get('spells', [])
        def _resolve(entry: dict) -> dict:
            e = dict(entry)
            if 'binding' in e and (not e.get('key')) and (not e.get('keys')):
                e['key'] = bindings.get(e['binding'], '')
            if 'sequence' in e:
                resolved_seq = []
                for step in e['sequence']:
                    s = dict(step)
                    if 'binding' in s and (not s.get('key')) and (not s.get('keys')):
                        s['key'] = bindings.get(s['binding'], '')
                    resolved_seq.append(s)
                e['sequence'] = resolved_seq
            return e
        _flat = []
        skipped = 0
        for raw_entry in _entries:
            entry = _resolve(raw_entry)
            has_action = (
                entry.get('key') or entry.get('keys') or entry.get('mouse') or
                entry.get('sequence') or entry.get('lights_target') or
                entry.get('wiper_target') or entry.get('response')
            )
            if not has_action:
                skipped += 1
                continue
            for variant in entry.get('variants', [entry['name']]):
                _flat.append((variant.lower().strip(), entry))
        _flat.sort(key=lambda x: len(x[0]), reverse=True)
        _profile_name = data.get('game', profile_name)
        return (True, _profile_name)
    except Exception as e:
        return (False, f'Ошибка загрузки профиля: {e}')
def unload_profile():
    global _profile_name, _entries, _flat, _bindings
    _profile_name = ''
    _entries = []
    _flat = []
    _bindings = {}
def match_command(text: str, threshold: float = 0.75) -> tuple[dict, float] | None:
    if not _flat:
        return None
    try:
        from rapidfuzz import fuzz as _fuzz
    except ImportError:
        _fuzz = None
    text_lower = text.lower().strip()
    if not text_lower:
        return None
    text_nospace = text_lower.replace(' ', '')
    for variant, entry in _flat:
        if text_lower == variant:
            return (entry, 1.0)
        if variant in text_lower and len(variant) > 4:
            return (entry, 1.0)
        variant_nospace = variant.replace(' ', '')
        if text_nospace == variant_nospace and len(variant_nospace) > 5:
            return (entry, 0.95)
        if len(variant_nospace) > 6 and variant_nospace in text_nospace:
            return (entry, 0.9)
    best_score = 0.0
    best_entry = None
    if _fuzz:
        for variant, entry in _flat:
            ratio = _fuzz.ratio(text_lower, variant) / 100.0
            partial = _fuzz.partial_ratio(text_lower, variant) / 100.0
            token_set = _fuzz.token_set_ratio(text_lower, variant) / 100.0
            score = (ratio + partial + token_set) / 3.0
            if score > best_score:
                best_score = score
                best_entry = entry
    else:
        for variant, entry in _flat:
            if variant in text_lower or text_lower in variant:
                score = min(len(variant), len(text_lower)) / max(len(variant), len(text_lower))
                if score > best_score:
                    best_score = score
                    best_entry = entry
    if best_entry and best_score >= threshold:
        return (best_entry, best_score)
    return None
def get_command_list() -> str:
    if not _entries:
        return 'Профиль не загружен.'
    active = [e['name'] for e in _entries if e.get('key') or e.get('keys') or e.get('sequence')]
    preview = ', '.join(active[:8])
    more = '...' if len(active) > 8 else ''
    return f'Доступно {len(active)} команд: {preview}{more}.'
def get_hotwords() -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for variant, _ in _flat:
        if variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result
