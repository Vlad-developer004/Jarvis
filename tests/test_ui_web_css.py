"""CSS class collisions in the window: a class that a script puts on a table row must not be a layout box anywhere else.

mail_compose.css once made every `.pf-r` (a row of the compose popover) a flex box; the process table used the same class on its <tr>, so its cells
stopped lining up with the column heads.
"""
import glob
import os
import re

WEB = os.path.join(os.path.dirname(__file__), '..', 'ui_next', 'web')
_LAYOUT = re.compile(r'(^|;)\s*display\s*:\s*(?!table)')


def _row_classes():
    out = {}
    for path in glob.glob(os.path.join(WEB, '*.js')):
        if os.path.basename(path) == 'i18n_uk.js':
            continue
        text = open(path, encoding='utf-8').read()
        for m in re.finditer(r'<tr\b[^>]*?class="([^"$]*)', text):
            for token in m.group(1).split():
                out.setdefault(token, os.path.basename(path))
    return out


def test_table_row_classes_are_not_layout_boxes_in_any_stylesheet():
    rows = _row_classes()
    assert rows, 'no <tr class> found: the pattern is stale'
    bad = []
    for path in glob.glob(os.path.join(WEB, '*.css')):
        css = re.sub(r'/\*.*?\*/', '', open(path, encoding='utf-8').read(), flags=re.S)
        for sel, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
            if not _LAYOUT.search(body):
                continue
            for part in sel.split(','):
                last = part.strip().split()[-1] if part.strip() else ''
                for token in re.findall(r'\.([A-Za-z_][\w-]*)', last):
                    if token in rows and not re.search(r'\b(tr|td|th)\b', last):
                        bad.append(f'{os.path.basename(path)}: {part.strip()} (row class of {rows[token]})')
    assert not bad, bad


_LAYOUT_PROPS = re.compile(r'(?:^|[;{\s])(?:width|height|min-width|min-height|top|left|right|bottom|margin[\w-]*|padding[\w-]*|inset|font-size|border-width|flex[\w-]*)\s*:')


def _keyframes():
    for path in glob.glob(os.path.join(WEB, '*.css')) + [os.path.join(WEB, 'app.html')]:
        text = open(path, encoding='utf-8').read()
        for m in re.finditer(r'@keyframes\s+([\w-]+)\s*\{', text):
            depth, i = 1, m.end()
            while depth and i < len(text):
                depth += (text[i] == '{') - (text[i] == '}')
                i += 1
            yield os.path.basename(path), m.group(1), text[m.end():i - 1]


def test_no_animation_changes_a_layout_property():
    """An animated width/height/margin re-runs layout and paint on every display frame (the now-playing equalizer animated `height` and kept the
    window at 75 frames a second while music played). Animate transform, opacity, filter or clip-path instead."""
    frames = list(_keyframes())
    assert len(frames) > 10, 'no @keyframes found: the pattern is stale'
    bad = ['%s: @keyframes %s' % (f, n) for f, n, body in frames if _LAYOUT_PROPS.search(body)]
    assert not bad, bad
