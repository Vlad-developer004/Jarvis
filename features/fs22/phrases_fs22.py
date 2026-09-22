"""RU/UA phrase bank for the FS22 monitor's real-break reminder and voice
session report. Split out purely for file-size consistency with ETS2/Planetbase,
mirroring their phrases_*.py convention."""
import random

from core.i18n import get_language

_REAL_BREAK_90_RU = [
    'Вы уже полтора часа за штурвалом трактора. Разомните спину.',
    'Полтора часа непрерывной игры. Самое время встать и потянуться.',
]
_REAL_BREAK_150_RU = [
    'Два с половиной часа без перерыва. Серьёзно, сделайте паузу.',
    'Вы играете уже два с половиной часа подряд. Пора отдохнуть по-настоящему.',
]
_REAL_BREAK_90_UK = [
    'Ви вже півтори години за трактором. Розімніть спину.',
    'Півтори години безперервної гри. Час встати й потягнутися.',
]
_REAL_BREAK_150_UK = [
    'Дві з половиною години без перерви. Справді, зробіть паузу.',
    'Ви граєте вже дві з половиною години поспіль. Час відпочити по-справжньому.',
]

def event_real_break_reminder(minutes: int) -> str:
    uk = get_language() == 'uk'
    if minutes >= 150:
        bank = _REAL_BREAK_150_UK if uk else _REAL_BREAK_150_RU
    else:
        bank = _REAL_BREAK_90_UK if uk else _REAL_BREAK_90_RU
    return random.choice(bank)

def session_report_text(elapsed_min: float, prev_min: float) -> str:
    uk = get_language() == 'uk'
    mins = int(elapsed_min)
    if uk:
        text = f'Поточна сесія триває {mins} хвилин.'
        if prev_min > 0:
            if elapsed_min > prev_min:
                text += f' Це довше за минулу сесію — {int(prev_min)} хвилин.'
            elif elapsed_min < prev_min:
                text += f' Минула сесія була довшою — {int(prev_min)} хвилин.'
            else:
                text += ' Точно як минулого разу.'
        return text
    text = f'Текущая сессия идёт {mins} минут.'
    if prev_min > 0:
        if elapsed_min > prev_min:
            text += f' Это дольше прошлой сессии — {int(prev_min)} минут.'
        elif elapsed_min < prev_min:
            text += f' Прошлая сессия была дольше — {int(prev_min)} минут.'
        else:
            text += ' Ровно как в прошлый раз.'
    return text
