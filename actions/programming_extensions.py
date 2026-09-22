from __future__ import annotations
import json
import re
from pathlib import Path
from config_pack.config import get_settings_path
# Same file the rest of the app reads/writes (%APPDATA%\Jarvis\...) — a
# project-relative path here would never see this setting (and gets wiped
# by a rebuild).
_SETTINGS_PATH = Path(get_settings_path())
SETTINGS_JSON_KEY = "programming_file_extensions"
_KEY = SETTINGS_JSON_KEY
_BAD = re.compile(r'[<>:"/\\|?*\s\x00-\x1F]')
def normalize_extension(s: str) -> str:
    t = (s or "").strip().lower().lstrip(".")
    if not t or _BAD.search(t):
        return ""
    if len(t) > 16:
        return ""
    return t
def get_programming_extensions() -> list[str]:
    out: list[str] = []
    try:
        if not _SETTINGS_PATH.exists():
            return out
        d = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return out
        raw = d.get(_KEY)
        if not isinstance(raw, list):
            return out
        for x in raw:
            if isinstance(x, str):
                n = normalize_extension(x)
                if n and n not in out:
                    out.append(n)
    except Exception:
        pass
    return out
def set_programming_extensions(exts: list[str]) -> None:
    seen: set[str] = set()
    clean: list[str] = []
    for x in exts:
        n = normalize_extension(str(x))
        if n and n not in seen:
            seen.add(n)
            clean.append(n)
    try:
        d: dict = {}
        if _SETTINGS_PATH.exists():
            got = json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(got, dict):
                d = got
        d[_KEY] = clean
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SETTINGS_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
