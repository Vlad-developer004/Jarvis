import re
from core.safe import swallow as _swallow
try:
    from num2words import num2words
except ImportError:
    num2words = None
def get_russian_plural(n: int, titles: list[str]) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return titles[0]
    elif n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return titles[1]
    else:
        return titles[2]
def format_time_russian(hours: int, minutes: int, add_stress: bool = True) -> str:
    h_titles = ["час", "часа", "часов"]
    m_titles = ["минута", "минуты", "минут"]
    if num2words:
        try:
            h_text = num2words(hours, lang='ru')
            h_form = get_russian_plural(hours, h_titles)
            if minutes == 0: return f"{h_text} {h_form} ровно"
            m_text = num2words(minutes, lang='ru', gender='feminine')
            m_form = get_russian_plural(minutes, m_titles)
            return f"{h_text} {h_form} {m_text} {m_form}"
        except Exception: _swallow()
    h_form = get_russian_plural(hours, h_titles)
    if minutes == 0: return f"{hours} {h_form}"
    m_form = get_russian_plural(minutes, m_titles)
    return f"{hours} {h_form} {minutes} {m_form}"
def format_remaining_russian(total_sec: int) -> str:
    """Exact time left, e.g. 291 -> "четыре минуты пятьдесят одна секунда". Seconds are dropped from an hour up."""
    total_sec = max(0, int(total_sec))
    hours, rest = divmod(total_sec, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        seconds = 0

    def words(n, gender):
        return num2words(n, lang='ru', gender=gender) if num2words else str(n)
    parts = []
    if hours:
        parts.append(f"{words(hours, 'masculine')} {get_russian_plural(hours, ['час', 'часа', 'часов'])}")
    if minutes:
        parts.append(f"{words(minutes, 'feminine')} {get_russian_plural(minutes, ['минута', 'минуты', 'минут'])}")
    if seconds or not parts:
        parts.append(f"{words(seconds, 'feminine')} {get_russian_plural(seconds, ['секунда', 'секунды', 'секунд'])}")
    return " ".join(parts)
def format_duration_russian(minutes_total: int, add_stress: bool = True) -> str:
    hours = minutes_total // 60
    minutes = minutes_total % 60
    parts = []
    if hours > 0:
        h_titles = ["час", "часа", "часов"]
        h_text = num2words(hours, lang='ru') if num2words else str(hours)
        parts.append(f"{h_text} {get_russian_plural(hours, h_titles)}")
    if minutes > 0 or not parts:
        m_titles = ["минута", "минуты", "минут"]
        m_text = num2words(minutes, lang='ru', gender='feminine') if num2words else str(minutes)
        parts.append(f"{m_text} {get_russian_plural(minutes, m_titles)}")
    return " ".join(parts)
