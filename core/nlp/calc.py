"""Spoken arithmetic: "сколько будет 15 умножить на 7" -> 105.

Words are turned into operators first, then the expression goes through a small AST walker that only knows
+ - * / and parentheses, so no spoken text can ever be executed as code."""
import ast
import operator
import re

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
    t = normalize_numbers(text.lower().replace('ё', 'е'))
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
