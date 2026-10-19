"""Mail sanitizer: hostile HTML never reaches the reading frame or an outgoing quote as script, remote loads or tricks."""
import re

import pytest

from ui_next.bridge import mail_render as mr

BS = chr(92)


def _doc(html, **kw):
    return mr.sanitize(html, **kw)[0]


def _body(html, **kw):
    doc = _doc(html, **kw)
    return doc[doc.index('<body>'):]


@pytest.mark.parametrize('html', [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '<a href="javascript:alert(1)">x</a>',
    '<a href=" JaVaScRiPt:alert(1)">x</a>',
    '<a href="&#106;avascript:alert(1)">x</a>',
    '<a href="data:text/html;base64,PHNjcmlwdD4=">x</a>',
    '<iframe src="https://evil.test"></iframe>',
    '<svg onload=alert(1)><circle/></svg>',
    '<math><mi xlink:href="javascript:alert(1)">x</mi></math>',
    '<object data="x"></object><embed src="x">',
    '<form action="https://evil.test"><input name=p></form>',
    '<meta http-equiv="refresh" content="0;url=https://evil.test">',
    '<base href="https://evil.test/">',
    '<link rel="stylesheet" href="https://evil.test/x.css">',
    '<body onload=alert(1)>hi',
    '<div onclick="alert(1)">x</div>',
    '<button formaction="x">b</button>',
    '<video src=x onerror=alert(1)></video>',
    '<template><script>alert(1)</script></template>',
])
def test_active_content_is_removed(html):
    body = _body(html).lower()
    for needle in ('<script', 'onerror', 'onload', 'onclick', 'javascript:', '<iframe', '<svg', '<object', '<embed', '<form', '<meta', '<base', '<link', 'formaction', '<video'):
        assert needle not in body, (html, needle)
    assert 'data:text/html' not in body


def test_links_are_rewritten_so_only_the_bridge_opens_them():
    body = _body('<a href="https://ok.test/a?b=1">x</a><a href="mailto:a@b.test">m</a><a href="file:///c:/x">f</a><a href="ftp://x">g</a>')
    assert 'data-url="https://ok.test/a?b=1"' in body and 'data-url="mailto:a@b.test"' in body
    assert 'file:' not in body and 'ftp:' not in body
    assert 'href="https://' not in body


def test_remote_images_are_blocked_until_the_user_asks():
    html = '<img src="https://track.test/p.gif"><img src="data:image/png;base64,AAAA"><img src="data:text/html;base64,AAAA">'
    doc, blocked = mr.sanitize(html)
    assert blocked == 1 and 'track.test' not in doc and 'data:image/png' in doc and 'text/html' not in doc
    assert "img-src data:" in doc and 'http:' not in doc.split('Content-Security-Policy')[1].split('>')[0]
    doc2, blocked2 = mr.sanitize(html, allow_images=True)
    assert blocked2 == 0 and 'track.test' in doc2


def test_the_frame_document_carries_a_locked_down_csp():
    doc = _doc('<p>hi</p>')
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', doc).group(1)
    assert "default-src 'none'" in csp and 'script-src' not in csp and 'connect-src' not in csp


@pytest.mark.parametrize('style', [
    'background:url(https://track.test/p.gif)',
    'background:u' + BS + '72l(https://track.test/p.gif)',
    'background:ur' + BS + '6c(https://track.test/p.gif)',
    'background:u/**/rl(https://track.test/p.gif)'.replace('u/**/rl', 'url'),
    'width:expression(alert(1))',
    'width:exp' + BS + '72 ession(alert(1))',
    'behavior:url(x.htc)',
    '-moz-binding:url(x)',
    'position:fixed;top:0',
    'background:image-set("https://track.test/a.png" 1x)',
])
def test_outgoing_quotes_drop_styles_that_load_or_escape(style):
    out = mr.fragment(f'<div style="{style}">x</div>')
    assert 'track.test' not in out and 'expression' not in out.lower() and 'url(' not in out.lower() and 'fixed' not in out
    assert 'x' in out


@pytest.mark.parametrize('style', ['width:exp' + BS + '72 ession(alert(1))', 'position:fixed', 'behavior:url(x)'])
def test_display_styles_with_escapes_are_dropped_too(style):
    assert 'style=' not in _body(f'<div style="{style}">x</div>')


def test_harmless_styles_survive():
    assert 'color:red' in mr.fragment('<p style="color:red;font-size:14px">x</p>')
    assert 'color:red' in _body('<p style="color:red">x</p>')


def test_style_blocks_are_cleaned_for_display_and_dropped_in_quotes():
    html = '<style>@import url(https://evil.test/x.css); p{color:red} q{width:expression(alert(1))} r{background:ur' + BS + '6c(x)}</style><p>x</p>'
    body = _body(html).lower()
    assert '@import' not in body and 'expression' not in body and 'evil.test' not in body
    assert '<style' not in mr.fragment(html).lower()


def test_cid_images_map_to_inline_data_and_unknown_cids_vanish():
    html = '<img src="cid:logo"><img src="cid:other">'
    doc, _ = mr.sanitize(html, {'logo': 'data:image/png;base64,AAAA'})
    assert doc.count('src=') == 1 and 'data:image/png;base64,AAAA' in doc and 'cid:' not in doc


def test_oversized_or_broken_html_does_not_crash():
    assert mr.sanitize('<' * 50)[0] is not None
    assert mr.sanitize('<p>' + 'x' * (mr.MAX_HTML + 10))[0] is not None
    assert mr.fragment(None) == ''


def test_text_is_escaped():
    body = _body('<p>1 < 2 &amp; "q" <b>bold</b></p>')
    assert '<b>bold</b>' in body and '1 &lt; 2' in body
