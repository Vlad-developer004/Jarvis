from __future__ import annotations
import json
import os
from config_pack.config import get_data_path
from core import i18n

def _get_catalog_path():
    """Get catalog path, preferring Ukrainian version if language is set to Ukrainian"""
    lang = i18n.get_language()
    if lang == 'uk':
        uk_path = get_data_path('extensions_catalog_uk.json')
        if os.path.exists(uk_path):
            return uk_path
    return get_data_path('extensions_catalog.json')

_CATALOG_PATH = _get_catalog_path()
_INSTALLED_PATH = get_data_path('extensions_installed.json')
class ExtensionManager:
    _instance: ExtensionManager | None = None
    def __new__(cls) -> ExtensionManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance
    def __init__(self) -> None:
        if self._ready:
            return
        self._catalog: list[dict] = []
        self._installed: set[str] = set()
        self._load()
        self._ready = True
    def _load(self) -> None:
        try:
            with open(_CATALOG_PATH, 'r', encoding='utf-8') as f:
                self._catalog = json.load(f).get('extensions', [])
        except Exception as e:
            self._catalog = []
        try:
            with open(_INSTALLED_PATH, 'r', encoding='utf-8') as f:
                self._installed = set(json.load(f).get('installed', []))
        except FileNotFoundError:
            self._installed = set()
            self._save()
        except Exception as e:
            self._installed = set()
    def _save(self) -> None:
        try:
            with open(_INSTALLED_PATH, 'w', encoding='utf-8') as f:
                json.dump({'installed': sorted(self._installed)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
    def is_installed(self, ext_id: str) -> bool:
        return ext_id in self._installed
    def has_feature(self, feature: str) -> bool:
        return any((feature in ext.get('features', []) for ext in self._catalog if ext['id'] in self._installed))
    def install(self, ext_id: str) -> bool:
        if not self._get(ext_id):
            return False
        self._installed.add(ext_id)
        self._save()
        return True
    def uninstall(self, ext_id: str) -> bool:
        if ext_id not in self._installed:
            return False
        self._installed.discard(ext_id)
        self._save()
        return True
    def list_all(self) -> list[dict]:
        return list(self._catalog)
    def list_installed(self) -> list[dict]:
        return [e for e in self._catalog if e['id'] in self._installed]
    def list_available(self) -> list[dict]:
        return [e for e in self._catalog if e['id'] not in self._installed]
    def is_bundled(self, ext_id: str) -> bool:
        ext = self._get(ext_id)
        return bool(ext and ext.get('bundled', False))
    def reload(self) -> None:
        self._ready = False
        self.__init__()
    def _get(self, ext_id: str) -> dict | None:
        return next((e for e in self._catalog if e['id'] == ext_id), None)
