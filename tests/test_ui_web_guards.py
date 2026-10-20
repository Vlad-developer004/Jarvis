"""Static guards for the new window's scripts: no code-from-string, no raw markup sinks for data that comes from outside.

The live check (hostile text pushed through every bridge payload) is `ui_next/devtools/cdp_xss.py`; the CSP check is `ui_next/devtools/cdp_csp.py`.
"""
import glob
import os
import re

WEB = os.path.join(os.path.dirname(__file__), '..', 'ui_next', 'web')


def _files():
    for path in sorted(glob.glob(os.path.join(WEB, '*.js')) + glob.glob(os.path.join(WEB, '*.html'))):
        if os.path.basename(path) != 'i18n_uk.js':
            yield os.path.basename(path), open(path, encoding='utf-8').read()


def _page():
    """The window page: markup plus its main script (moved to app.js)."""
    return ''.join(open(os.path.join(WEB, n), encoding='utf-8').read() for n in ('app.html', 'app.js'))


def _hits(pattern):
    rx = re.compile(pattern)
    return [f'{name}:{n}' for name, text in _files() for n, line in enumerate(text.splitlines(), 1) if rx.search(line)]


def test_no_code_from_strings():
    assert _hits(r'(?<![\w.])eval\(') == []
    assert _hits(r'new Function\(') == []
    assert _hits(r'document\.write\(') == []
    assert _hits(r'set(?:Timeout|Interval)\(\s*[\'"`]') == []


def test_no_javascript_urls_or_window_open():
    assert _hits(r'javascript:') == []
    assert _hits(r'window\.open\(') == []


def test_esc_escapes_every_character_that_can_leave_an_attribute_or_tag():
    src = _page()
    line = next(l for l in src.splitlines() if l.startswith('const esc = '))
    for ch in ('&', '<', '>', '"', "'"):
        assert ch in line, ch
    assert "'&#39;'" in line or '"&#39;"' in line or "&#39;" in line


def test_known_external_strings_go_through_esc():
    html = _page()
    assert "innerHTML = esc(WX.city)" in html, 'the weather city comes from a geolocation service'
    assert 'innerHTML = WX.city' not in html
    rems = open(os.path.join(WEB, 'rems.js'), encoding='utf-8').read()
    assert 'data-cancel="${esc(r.id)}"' in rems
    songs = open(os.path.join(WEB, 'songs.js'), encoding='utf-8').read()
    assert 'data:image\\/jpeg;base64,[A-Za-z0-9+/=]+$' in songs, 'a cover is shown only when it is a plain jpeg data URL'


def test_mail_frame_is_sandboxed_without_scripts():
    mail = open(os.path.join(WEB, 'mail.js'), encoding='utf-8').read()
    m = re.search(r"setAttribute\('sandbox', '([^']*)'\)", mail)
    assert m and 'allow-scripts' not in m.group(1) and 'allow-top-navigation' not in m.group(1) and 'allow-popups' not in m.group(1)


def test_notice_text_is_escaped_where_it_is_drawn():
    html = _page()
    assert '${n.text}' not in html and '${first.text}' not in html, 'a notice text comes from the core and may carry data'
    assert html.count('esc(n.text)') >= 2 and 'esc(first.text)' in html


def test_prompt_buttons_from_the_core_are_escaped():
    src = open(os.path.join(WEB, 'prompts.js'), encoding='utf-8').read()
    assert 'label: esc(a.label)' in src and 'id: esc(a.id)' in src


def test_window_scripts_parse():
    import shutil
    import subprocess
    node = shutil.which('node')
    if not node:
        import pytest
        pytest.skip('node is not installed')
    bad = [name for name, _ in _files() if name.endswith('.js') and subprocess.run([node, '--check', os.path.join(WEB, name)], capture_output=True).returncode]
    assert bad == []
