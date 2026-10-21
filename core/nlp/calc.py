"""Spoken arithmetic: "сколько будет 15 умножить на 7" -> 105.

Words are turned into operators first, then the expression goes through a small AST walker that only knows
+ - * / and parentheses, so no spoken text can ever be executed as code."""
import ast
import operator
import re
import threading
import time

_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_LIMIT = 10 ** 15

# longest phrases first: "умножить на" must be replaced before a bare "на" could matter
_WORD_OPS = (
    (r'\bумножь(?:те)? на\b|\bумножить на\b|\bпомножить на\b|\bумножить\b|\bпомножь на\b|\bпомнож на\b|\bпомножити на\b|\bпомнож\b|\bразів на\b|\bраз на\b', '*'),
    (r'\bразделить на\b|\bподели на\b|\bподелить на\b|\bделить на\b|\bподілити на\b|\bподіли на\b|\bділити на\b', '/'),
    (r'\bплюс\b|\bприбавить\b|\bприбавь\b|\bдобавить\b', '+'),
    (r'\bминус\b|\bмінус\b|\bотнять\b|\bвычесть\b|\bвіднять\b', '-'),
    (r'\bскобка открывается\b|\bоткрыть скобку\b|\bдужка відкривається\b', '('),
    (r'\bскобка закрывается\b|\bзакрыть скобку\b|\bдужка закривається\b', ')'),
)
_FILLER = re.compile(r'\b(?:джарвис|джарвіс|сколько будет|сколько получится|сколько|скільки буде|скільки вийде|скільки|посчитай|посчитайте|подсчитай|вычисли|реши|порахуй|обчисли|розв.яжи|будет|буде|равно|дорівнює|пожалуйста|будь ласка)\b')
_PERCENT = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:процент(?:ов|а)?|відсотк(?:ів|а|и)?|%)\s*(?:от|від|з)\s*(\d+(?:[.,]\d+)?)')
_SAFE = re.compile(r'^[\d\s+\-*/().]+$')


# Compound spoken numbers ("двести двадцать пять", "сто пятьдесят два", "две тысячи пятьсот"): normalize_numbers maps single words only,
# which turns these into "двести 25" / "100 52", so the calculator composes them itself.
_UNITS = {'ноль': 0, 'нуль': 0, 'один': 1, 'одна': 1, 'одну': 1, 'одно': 1, 'два': 2, 'две': 2, 'дві': 2, 'три': 3, 'четыре': 4, 'чотири': 4, 'пять': 5, 'шесть': 6, 'шість': 6,
          'семь': 7, 'сім': 7, 'восемь': 8, 'вісім': 8, 'девять': 9, 'десять': 10, 'одиннадцать': 11, 'одинадцять': 11, 'двенадцать': 12, 'дванадцять': 12,
          'тринадцать': 13, 'тринадцять': 13, 'четырнадцать': 14, 'чотирнадцять': 14, 'пятнадцать': 15, 'пятнадцять': 15, 'шестнадцать': 16, 'шістнадцять': 16,
          'семнадцать': 17, 'сімнадцять': 17, 'восемнадцать': 18, 'вісімнадцять': 18, 'девятнадцать': 19, 'девятнадцять': 19}
_TENS = {'двадцать': 20, 'двадцять': 20, 'тридцать': 30, 'тридцять': 30, 'сорок': 40, 'пятьдесят': 50, 'пятдесят': 50, 'шестьдесят': 60, 'шістдесят': 60,
         'семьдесят': 70, 'сімдесят': 70, 'восемьдесят': 80, 'вісімдесят': 80, 'девяносто': 90, 'девяносто': 90}
_HUNDREDS = {'сто': 100, 'двести': 200, 'двісті': 200, 'триста': 300, 'четыреста': 400, 'чотириста': 400, 'пятьсот': 500, 'пятсот': 500, 'шестьсот': 600, 'шістсот': 600,
             'семьсот': 700, 'сімсот': 700, 'восемьсот': 800, 'вісімсот': 800, 'девятьсот': 900, 'девятсот': 900}
_SCALES = {'тысяча': 10 ** 3, 'тысячи': 10 ** 3, 'тысяч': 10 ** 3, 'тисяча': 10 ** 3, 'тисячі': 10 ** 3, 'тисяч': 10 ** 3,
           'миллион': 10 ** 6, 'миллиона': 10 ** 6, 'миллионов': 10 ** 6, 'мільйон': 10 ** 6, 'мільйона': 10 ** 6, 'мільйонів': 10 ** 6}
_NUM_WORDS = {**_UNITS, **_TENS, **_HUNDREDS, **_SCALES}


def _compose_run(words: list) -> list:
    """Integers spoken by a run of number words; a run that is not one number ("двадцать пять двадцать") comes out as several."""
    out, state = [], {'total': 0, 'cur': 0, 'rank': 4, 'closed': False}     # rank: 3 hundreds, 2 tens/teens, 1 units; closed: a teen takes no units

    def flush():
        out.append(state['total'] + state['cur'])
        state.update(total=0, cur=0, rank=4, closed=False)
    for w in words:
        if w in _SCALES:
            state['total'] += (state['cur'] or 1) * _SCALES[w]
            state.update(cur=0, rank=4, closed=False)
            continue
        if w in ('ноль', 'нуль'):
            if state['total'] or state['cur']:
                flush()
            out.append(0)
            continue
        val = _HUNDREDS.get(w) or _TENS.get(w) or _UNITS[w]
        rank = 3 if w in _HUNDREDS else 2 if (w in _TENS or val >= 10) else 1
        if rank >= state['rank'] or (state['closed'] and rank <= 2):
            flush()
        state['cur'] += val
        state.update(rank=rank, closed=val >= 10 and w in _UNITS)
    if state['total'] or state['cur'] or not out:
        flush()
    return out


def _compose_numbers(text: str) -> str:
    tokens = re.split(r'(\s+)', text.replace("'", '').replace('’', '').replace('ʼ', ''))
    out, run, gap = [], [], ''

    def end_run():
        if run:
            out.append(' '.join(str(n) for n in _compose_run(run)))
            run.clear()
    for tok in tokens:
        if tok in _NUM_WORDS:
            run.append(tok)
            gap = ''
        elif tok.isspace() and run:
            gap = tok
        else:
            end_run()
            out.append(gap + tok)
            gap = ''
    end_run()
    return ''.join(out)


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand)
        return v if isinstance(node.op, ast.UAdd) else -v
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        v = _OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if abs(v) > _LIMIT:
            raise OverflowError
        return v
    raise ValueError('unsupported expression')


def _expression(text: str) -> str:
    from core.nlp.commands import normalize_numbers
    t = normalize_numbers(_compose_numbers(text.lower().replace('ё', 'е')))
    t = _PERCENT.sub(lambda m: f"({m.group(1)}*{m.group(2)}/100)".replace(',', '.'), t)
    for pat, sym in _WORD_OPS:
        t = re.sub(pat, f' {sym} ', t)
    t = _FILLER.sub(' ', t)
    t = re.sub(r'(?<=\d)\s*[хx×]\s*(?=\d)', '*', t)   # "7 х 8" as recognised from speech
    t = t.replace('×', '*').replace('÷', '/').replace(':', '/')
    t = re.sub(r'(?<=\d),(?=\d)', '.', t)
    return re.sub(r'\s+', ' ', t).strip()


def evaluate(text: str):
    """Value of the spoken expression, or None when the phrase holds no arithmetic."""
    expr = _expression(text)
    if not expr or not re.search(r'\d', expr) or not _SAFE.match(expr):
        return None
    if not re.search(r'[+\-*/]', expr):
        return None   # a lone number is not a question
    try:
        return _eval(ast.parse(expr, mode='eval'))
    except ZeroDivisionError:
        raise
    except (SyntaxError, ValueError, OverflowError, RecursionError):
        return None


def spoken(value) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, float):
        return f'{round(value, 4):g}'.replace('.', ',')
    return str(value)


# ---- context: the last answer, so "и плюс сто тридцать три" continues it ----
TTL = 120.0
_lock = threading.Lock()
_last: tuple | None = None     # (value, monotonic time)
_CONNECT = r'(?:(?:и|а|ну|потом|теперь|ещё|еще|і|та)\s+)*'
_CONTINUE = re.compile(rf'^{_CONNECT}((?:плюс|минус|мінус|умнож\w*|помнож\w*|раздели\w*|подели\w*|делить|поділи\w*|поділ\w*|розділи\w*|добав\w*|прибав\w*|отними\w*|віднім\w*|вычти\w*).*)$')
_BINARY = re.compile(r'\d\s*[+\-*/]\s*\d')


def remember_result(value) -> None:
    global _last
    with _lock:
        _last = (value, time.monotonic())


def forget_result() -> None:
    global _last
    with _lock:
        _last = None


def _plain(value) -> str:
    if isinstance(value, float):
        return format(value, '.10f').rstrip('0').rstrip('.') if not value.is_integer() else str(int(value))
    return str(value)


def route(text: str):
    """('calc', phrase) when `text` is arithmetic on its own ("двести двадцать пять минус сто пятьдесят два") or continues the last answer
    ("и плюс сто тридцать три" after 73 -> "73 плюс сто тридцать три"); None otherwise. The whole phrase has to be arithmetic."""
    t = re.sub(r'\s+', ' ', text.lower().replace('ё', 'е').replace('?', ' ').replace('!', ' ').replace(',', ' ')).strip()
    if not t or len(t) > 120 or ':' in t:
        return None
    with _lock:
        prev = _last
    if prev is not None and time.monotonic() - prev[1] <= TTL:
        m = _CONTINUE.match(t)
        if m:
            phrase = f'{_plain(prev[0])} {m.group(1)}'
            try:
                return ('calc', phrase) if evaluate(phrase) is not None else None
            except ZeroDivisionError:
                return ('calc', phrase)
    try:
        if _BINARY.search(_expression(t)) and evaluate(t) is not None:
            return ('calc', t)
    except ZeroDivisionError:
        return ('calc', t)
    return None
