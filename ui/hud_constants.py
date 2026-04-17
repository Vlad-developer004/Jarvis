from __future__ import annotations
_BG = '#0a0b10'
_PANEL = '#0d0f1e'
_BRD = '#181b35'
_BRD_I = '#212448'
_SEP = '#1a1d38'
_CYAN = '#00ffff'
_MAG = '#f500ff'
_GREEN = '#00ff88'
_AMBER = '#ffcc00'
_RED = '#ff3333'
_WHITE = '#ffffff'
_TEXT = '#d1d7ef'
_DIM = '#8e98c9'
_GRID = '#121528'
_DYN = 'dynamic'
_STA = 'static'
_RU_MON = {1: 'ЯНВ', 2: 'ФЕВ', 3: 'МАЙ', 4: 'АПР', 5: 'МАЙ', 6: 'ИЮН', 7: 'ИЮЛ', 8: 'АВГ', 9: 'СЕН', 10: 'ОКТ', 11: 'НОЯ', 12: 'ДЕК'}
_RU_DAYS = {0: 'ПОНЕДЕЛЬНИК', 1: 'ВТОРНИК', 2: 'СРЕДА', 3: 'ЧЕТВЕРГ', 4: 'ПЯТНИЦА', 5: 'СУББОТА', 6: 'ВОСКРЕСЕНЬЕ'}
_LOW_PERF_MODE: bool = False
_DEFAULT_VIS: dict = {
    'cpu': True, 'storage': True, 'network': True, 'weather': True,
    'ram': True, 'camera': True, 'sysinfo': True, 'gamemode': True,
    'meetings_btn': True, 'videos_btn': True,
}
