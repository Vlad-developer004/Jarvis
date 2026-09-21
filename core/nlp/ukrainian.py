import re
try:
    from num2words import num2words
except ImportError:
    num2words = None

def get_ukrainian_plural(n: int, titles: list[str]) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return titles[0]
    elif n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20):
        return titles[1]
    else:
        return titles[2]

def format_time_ukrainian(hours: int, minutes: int) -> str:
    h_titles = ["година", "години", "годин"]
    m_titles = ["хвилина", "хвилини", "хвилин"]
    if num2words:
        try:
            h_text = num2words(hours, lang='uk')
            h_form = get_ukrainian_plural(hours, h_titles)
            if minutes == 0: return f"{h_text} {h_form} рівно"
            m_text = num2words(minutes, lang='uk', gender='feminine')
            m_form = get_ukrainian_plural(minutes, m_titles)
            return f"{h_text} {h_form} {m_text} {m_form}"
        except Exception: pass
    h_form = get_ukrainian_plural(hours, h_titles)
    if minutes == 0: return f"{hours} {h_form}"
    m_form = get_ukrainian_plural(minutes, m_titles)
    return f"{hours} {h_form} {minutes} {m_form}"

