import sys
import types
def _mock(name):
    mod = types.ModuleType(name)
    mod.__path__ = []
    mod.__package__ = name
    sys.modules[name] = mod
    return mod
if 'jaraco' not in sys.modules:
    _mock('jaraco')
for sub in ['jaraco.text', 'jaraco.functools', 'jaraco.context', 'jaraco.classes', 'jaraco.classes.properties']:
    if sub not in sys.modules:
        _mock(sub)
_jt = sys.modules['jaraco.text']
if not hasattr(_jt, 'drop_comment'):
    def drop_comment(line):
        return line.partition('#')[0]
    _jt.drop_comment = drop_comment
if not hasattr(_jt, 'join_continuation'):
    def join_continuation(lines):
        lines = iter(lines)
        for item in lines:
            while item.endswith('\\'):
                try:
                    item = item[:-1] + next(lines)
                except StopIteration:
                    return
            yield item
    _jt.join_continuation = join_continuation
if not hasattr(_jt, 'strip_prefix'):
    def strip_prefix(text, prefix):
        return text[len(prefix):] if text.startswith(prefix) else text
    _jt.strip_prefix = strip_prefix
if not hasattr(_jt, 'FoldedCase'):
    class FoldedCase(str):
        def __lt__(self, other):
            return self.lower() < other.lower()
        def __gt__(self, other):
            return self.lower() > other.lower()
        def __eq__(self, other):
            return self.lower() == str(other).lower()
        def __hash__(self):
            return hash(self.lower())
    _jt.FoldedCase = FoldedCase
if not hasattr(_jt, 'yield_lines'):
    def yield_lines(iterable):
        for item in iterable:
            for line in item.splitlines():
                line = line.strip()
                if line:
                    yield line
    _jt.yield_lines = yield_lines
if not hasattr(_jt, 'join_lines'):
    def join_lines(lines):
        return ''.join(lines)
    _jt.join_lines = join_lines
_jf = sys.modules['jaraco.functools']
if not hasattr(_jf, 'compose'):
    import functools as _ft
    def compose(*funcs):
        return _ft.reduce(lambda f, g: lambda *a, **kw: f(g(*a, **kw)), funcs)
    _jf.compose = compose
if not hasattr(_jf, 'method_cache'):
    def method_cache(func):
        return func
    _jf.method_cache = method_cache
_jc = sys.modules['jaraco.context']
if not hasattr(_jc, 'suppress'):
    from contextlib import suppress as _suppress
    _jc.suppress = _suppress
_jcp = sys.modules['jaraco.classes.properties']
if not hasattr(_jcp, 'NonDataProperty'):
    class NonDataProperty:
        def __init__(self, fget):
            self.fget = fget
        def __get__(self, obj, cls):
            return self if obj is None else self.fget(obj)
    _jcp.NonDataProperty = NonDataProperty
