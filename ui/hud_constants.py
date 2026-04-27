from __future__ import annotations
import json, os

# ──────────────────────────────────────────────────────────────────────────────
# Load theme colors from settings BEFORE defining defaults.
# ──────────────────────────────────────────────────────────────────────────────
def _load_theme_colors() -> dict:
    """Read the saved theme palette without importing other ui modules."""
    _THEMES = {
        # Фирменный неоновый стиль (Vibrant Neon)
        'cyber': {
            'BG': '#05060b',        # Ультра-черный с синим отливом
            'PANEL': '#0b0e1a',     # Глубокий темно-синий
            'BRD': '#1e2642',       # Цвет ночного неба
            'BRD_I': '#2a3660',     # Внутренние рамки
            'SEP': '#1a223f',       # Разделители
            'GRID': '#0d1326',      # Сетка фона
            'CYAN': '#00ffff',      # Чистый неон
            'MAG': '#ff00ff',       # Пурпурный акцент
            'GREEN': '#00ff9d',     # Изумрудный неон
            'AMBER': '#ffbd00',     # Теплое золото
            'RED': '#ff2d55',       # Агрессивный розово-красный
            'WHITE': '#ffffff',
            'TEXT': '#cbd5e1',      # Светло-серый текст
            'DIM': '#64748b',       # Приглушенный текст
        },
        # Обсидиановый строгий стиль (Ice Obsidian)
        'dark': {
            'BG': '#0a0a0a',        # Чистый антрацит
            'PANEL': '#121212',     # Темный графит
            'BRD': '#1f1f1f',       # Стальной темный
            'BRD_I': '#2d2d2d',     # Акцентный серый
            'SEP': '#181818',
            'GRID': '#0d0d0d',
            'CYAN': '#4fc3f7',      # Ледяной голубой
            'MAG': '#b39ddb',       # Мягкая лаванда
            'GREEN': '#81c784',     # Спокойный зеленый
            'AMBER': '#ffb74d',     # Мягкий оранжевый
            'RED': '#ef5350',       # Сдержанный красный
            'WHITE': '#f5f5f5',
            'TEXT': '#e0e0e0',      # Почти белый
            'DIM': '#757575',       # Серый
        },
        # Светлый технологичный стиль (Alabaster Stark)
        'light': {
            'BG': '#f1f5f9',        # Цвет холодного алебастра
            'PANEL': '#ffffff',     # Чистый белый
            'BRD': '#cbd5e1',       # Серебристо-стальной
            'BRD_I': '#94a3b8',     # Темная сталь
            'SEP': '#e2e8f0',       # Тонкий разделитель
            'GRID': '#f8fafc',      # Едва заметная сетка
            'CYAN': '#0369a1',      # Глубокий океанический синий
            'MAG': '#7e22ce',       # Насыщенный фиолетовый
            'GREEN': '#15803d',     # Лесной зеленый
            'AMBER': '#b45309',     # Жженая охра
            'RED': '#be123c',       # Винный красный
            'WHITE': '#0f172a',     # Контрастный темный (вместо белого)
            'TEXT': '#1e293b',      # Темно-сланцевый текст
            'DIM': '#64748b',       # Сланцевый приглушенный
        },
    }
    try:
        p = os.path.join('data', 'jarvis_settings.json')
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                name = settings.get('theme', 'cyber')
            if name in _THEMES:
                return name, _THEMES[name]
    except Exception:
        pass
    return 'cyber', _THEMES['cyber']

_CURRENT_THEME, _t = _load_theme_colors()

# Применяем константы палитры
_BG    = _t['BG']
_PANEL = _t['PANEL']
_BRD   = _t['BRD']
_BRD_I = _t['BRD_I']
_SEP   = _t['SEP']
_CYAN  = _t['CYAN']
_MAG   = _t['MAG']
_GREEN = _t['GREEN']
_AMBER = _t['AMBER']
_RED   = _t['RED']
_WHITE = _t['WHITE']
_TEXT  = _t['TEXT']
_DIM   = _t['DIM']
_GRID  = _t['GRID']

del _t  # Очистка временной переменной

_DYN = 'dynamic'
_STA = 'static'

# Месяцы (исправлено: 3 - МАРТ)
_RU_MON  = {1: 'ЯНВ', 2: 'ФЕВ', 3: 'МАР', 4: 'АПР', 5: 'МАЙ', 6: 'ИЮН',
             7: 'ИЮЛ', 8: 'АВГ', 9: 'СЕН', 10: 'ОКТ', 11: 'НОЯ', 12: 'ДЕК'}

_RU_DAYS = {0: 'ПОНЕДЕЛЬНИК', 1: 'ВТОРНИК', 2: 'СРЕДА', 3: 'ЧЕТВЕРГ',
             4: 'ПЯТНИЦА', 5: 'СУББОТА', 6: 'ВОСКРЕСЕНЬЕ'}

_LOW_PERF_MODE: bool = False

_DEFAULT_VIS: dict = {
    'cpu': True, 'storage': True, 'network': True, 'weather': True,
    'ram': True, 'camera': True, 'sysinfo': True, 'gamemode': True,
    'meetings_btn': True, 'videos_btn': True,
}