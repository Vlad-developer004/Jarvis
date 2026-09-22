from __future__ import annotations
import json
import re
from pathlib import Path
from config_pack.config import get_settings_path
# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\...) — a
# project-relative path here would never see this setting (and gets wiped
# by a rebuild).
_SETTINGS_PATH = Path(get_settings_path())
_DEFAULT = {
    'active': 'home',
    'profiles': {
        'home': {'label': 'Дом', 'vpn_hint': '', 'ssid_hint': ''},
        'office': {
            'label': 'Офис',
            'vpn_hint': 'Включите корпоративный VPN, если это требуется политикой доступа.',
            'ssid_hint': '',
        },
        'public': {
            'label': 'Публичная сеть',
            'vpn_hint': 'На публичном Wi‑Fi лучше использовать VPN.',
            'ssid_hint': '',
        },
    },
}
def _load_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            return json.loads(_SETTINGS_PATH.read_text(encoding='utf-8'))
    except Exception:
        pass
    return {}
def _save_settings(data: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
def merge_network_bundle(settings: dict | None) -> dict:
    base = json.loads(json.dumps(_DEFAULT))
    raw = (settings or {}).get('network_profiles')
    if not isinstance(raw, dict):
        return base
    if raw.get('active') in base['profiles']:
        base['active'] = str(raw['active'])
    profiles = raw.get('profiles')
    if isinstance(profiles, dict):
        for key in base['profiles']:
            if key in profiles and isinstance(profiles[key], dict):
                for fld in ('label', 'vpn_hint', 'ssid_hint'):
                    if fld in profiles[key] and isinstance(profiles[key][fld], str):
                        base['profiles'][key][fld] = profiles[key][fld]
    return base
def current_wifi_ssid() -> str | None:
    try:
        import subprocess
        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'interfaces'],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=0x08000000,
        )
        if r.returncode != 0 or not r.stdout:
            return None
        for line in r.stdout.splitlines():
            line = line.strip()
            m = re.match(r'^SSID\s*:\s*(.+)$', line, re.I)
            if m:
                return m.group(1).strip() or None
    except Exception:
        pass
    return None
def describe_network_state(settings: dict | None = None) -> str:
    if settings is None:
        settings = _load_settings()
    bundle = merge_network_bundle(settings)
    active = bundle['active']
    prof = bundle['profiles'].get(active, {})
    label = prof.get('label', active)
    ssid = current_wifi_ssid()
    parts = [f'Активный профиль: {label}.']
    if ssid:
        parts.append(f'Текущий Wi‑Fi SSID: {ssid}.')
    else:
        parts.append('Wi‑Fi SSID не удалось определить (возможно, не Wi‑Fi или нет прав).')
    hint = (prof.get('ssid_hint') or '').strip()
    if hint:
        parts.append(f'Подсказка по сети: {hint}')
    return ' '.join(parts)
def vpn_reminder_for_active(settings: dict | None = None) -> str:
    if settings is None:
        settings = _load_settings()
    bundle = merge_network_bundle(settings)
    active = bundle['active']
    prof = bundle['profiles'].get(active, {})
    label = prof.get('label', active)
    hint = (prof.get('vpn_hint') or '').strip()
    if not hint:
        return f'Для профиля «{label}» отдельная подсказка по VPN не задана. Отредактируйте vpn_hint в data/jarvis_settings.json в разделе network_profiles.'
    return f'Профиль «{label}». {hint}'
def parse_profile_target(text_lower: str) -> str | None:
    t = text_lower
    if any(x in t for x in ('офис', 'office', 'рабоч')):
        return 'office'
    if any(x in t for x in ('публич', 'public', 'гостев', 'кафе')):
        return 'public'
    if any(x in t for x in ('дом', 'home', 'домашн')):
        return 'home'
    return None
def set_active_profile(key: str) -> tuple[bool, str]:
    if key not in ('home', 'office', 'public'):
        return False, 'неизвестный профиль'
    data = _load_settings()
    bundle = data.get('network_profiles')
    if not isinstance(bundle, dict):
        bundle = {}
    merged = merge_network_bundle(data)
    bundle['active'] = key
    bundle['profiles'] = merged['profiles']
    data['network_profiles'] = bundle
    _save_settings(data)
    label = merged['profiles'][key].get('label', key)
    return True, f'Активный профиль сети: {label}.'
