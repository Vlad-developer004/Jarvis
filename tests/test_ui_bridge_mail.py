import pytest

from actions import mail_client
from ui_next import bridge
from ui_next.bridge import mail as ml
from ui_next.bridge import imapsession as ims
from ui_next.bridge import mail_render


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    ml._attach.clear()
    ml._saved.clear()
    ims.SESSION.pages.clear()
    ims.SESSION.bodies.clear()
    monkeypatch.setattr(mail_client, 'get_resolved_mail_config', lambda: {'email': 'me@example.com', 'password': 'x', 'imap_host': 'h', 'imap_port': 993, 'mailbox': 'INBOX'})


def hdr(uid, flags, subject, frm, date='Tue, 14 Oct 2025 10:00:00 +0000', extra=''):
    raw = f'Subject: {subject}\r\nFrom: {frm}\r\nTo: me@example.com\r\nDate: {date}\r\n{extra}\r\n'.encode()
    return (f'1 (UID {uid} FLAGS ({flags}) BODY[HEADER.FIELDS (SUBJECT FROM TO DATE MESSAGE-ID CONTENT-TYPE)] {{{len(raw)}}}'.encode(), raw)


class FakeConn:
    def __init__(self):
        self.calls = []
        self.literal = None

    def list(self):
        return 'OK', [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "[Gmail]/Sent Mail"', b'(\\HasNoChildren \\Trash) "/" "[Gmail]/Trash"',
                      b'(\\HasNoChildren) "/" "Junk E-mail"']

    def select(self, name):
        self.calls.append(('select', name))
        return 'OK', [b'1']

    def status(self, name, what):
        return 'OK', [b'"INBOX" (UNSEEN 3)']

    def noop(self):
        return 'OK', []

    def uid(self, cmd, *args):
        self.calls.append((cmd, args))
        if cmd.upper() == 'SEARCH':
            return 'OK', [b'1 2 3 4 5']
        if cmd.lower() == 'fetch' and 'HEADER' in args[1]:
            wanted = args[0].split(b',')
            return 'OK', [hdr(u.decode(), '\\Seen' if u == b'2' else '', f'S{u.decode()}', 'Anna K <anna@x.org>') for u in wanted]
        if cmd.lower() == 'fetch':
            return 'OK', [(b'1 (UID 5 FLAGS () BODY[] {10}', b'Subject: Hi\r\nFrom: A <a@b.c>\r\nMessage-ID: <1@x>\r\n\r\nhello\r\n'), b')']
        return 'OK', []

    def expunge(self):
        self.calls.append(('expunge',))
        return 'OK', []


@pytest.fixture
def conn(monkeypatch):
    c = FakeConn()
    monkeypatch.setattr(mail_client, '_connect_imap', lambda cfg, select_mailbox=True: c)
    ims.SESSION.reset()
    yield c
    ims.SESSION.reset()


def test_not_configured(monkeypatch):
    monkeypatch.setattr(mail_client, 'get_resolved_mail_config', lambda: None)
    assert ml.configured() == {'configured': False, 'email': ''}
    assert ml.list_messages() == {'ok': False, 'error': 'not_configured'}
    assert ml.folders() == {'ok': False, 'error': 'not_configured'}


def test_folder_roles_come_from_special_use_flags_and_names():
    m = ims.parse_folders([b'(\\HasNoChildren) "/" "INBOX"', b'(\\Sent) "/" "[Gmail]/Sent Mail"', b'(\\Noselect) "/" "[Gmail]"', '() "/" "Корзина"',
                           b'() "/" "Archive"', b'() "/" "Junk E-mail"'])
    assert m == {'inbox': 'INBOX', 'sent': '[Gmail]/Sent Mail', 'trash': 'Корзина', 'archive': 'Archive', 'junk': 'Junk E-mail'}


def test_list_uses_one_connection_and_caches_the_first_page(conn):
    r = ml.list_messages()
    assert r['ok'] and [x['uid'] for x in r['rows']] == ['5', '4', '3', '2', '1'] and r['total'] == 5 and r['more'] is False and r['cached'] is False
    assert r['rows'][0] == {'uid': '5', 'subject': 'S5', 'name': 'Anna K', 'addr': 'anna@x.org', 'ts': 1760436000, 'unread': True, 'flagged': False, 'att': False}
    assert [x['unread'] for x in r['rows']] == [True, True, True, False, True]
    n = len(conn.calls)
    again = ml.list_messages()
    assert again['cached'] is True and len(conn.calls) == n                          # served from memory, no IMAP traffic
    assert ml.list_messages(refresh=True)['cached'] is False


def test_paging_filtering_and_non_ascii_search(conn):
    r = ml.list_messages(limit=2)
    assert [x['uid'] for x in r['rows']] == ['5', '4'] and r['more'] is True
    r2 = ml.list_messages(offset=2, limit=2)
    assert [x['uid'] for x in r2['rows']] == ['3', '2']
    ml.list_messages(q='счёт', flt='unread')
    search = [c for c in conn.calls if c[0].upper() == 'SEARCH'][-1]
    assert search[1] == ('CHARSET', 'UTF-8', 'UNSEEN', 'TEXT')


def test_folder_and_uid_are_validated(conn):
    assert ml.list_messages('../etc')['error'] == 'bad_folder'
    assert ml.read_message('inbox', '5; drop')['error'] == 'bad_uid'
    assert ml.set_flag('inbox', '5', 'deleted', True)['error'] == 'bad_flag'
    assert ml.remove('inbox', '5', 'nowhere')['error'] == 'bad_target'


def test_read_marks_seen_once_and_caches(conn):
    ml.list_messages()
    r = ml.read_message('inbox', '5')
    assert r['ok'] and r['body'] == 'hello' and r['name'] == 'A' and r['reply_to'] == 'a@b.c' and r['was_unread'] is True
    stores = [c for c in conn.calls if c[0] == 'STORE']
    assert len(stores) == 1 and stores[0][1][1:] == ('+FLAGS', r'(\Seen)')
    assert ims.SESSION.pages['inbox']['rows'][0]['unread'] is False                  # the cached list follows
    ml.read_message('inbox', '5')
    assert len([c for c in conn.calls if c[0] == 'STORE']) == 1


def test_read_without_mark_leaves_the_letter_unread(conn):
    assert ml.read_message('inbox', '5', mark=False)['ok']
    assert not [c for c in conn.calls if c[0] == 'STORE']


def test_remove_moves_to_trash_or_deletes_for_good(conn):
    ml.list_messages()
    assert ml.remove('inbox', '5', 'trash') == {'ok': True, 'where': 'trash'}
    assert [c for c in conn.calls if c[0] == 'COPY'][0][1][1] == '"[Gmail]/Trash"'
    assert [x['uid'] for x in ims.SESSION.pages['inbox']['rows']] == ['4', '3', '2', '1']
    assert ml.remove('trash', '4', 'trash') == {'ok': True, 'where': 'gone'}       # already in the trash: no copy
    assert ml.remove('inbox', '3', 'archive')['error'] == 'no_folder'


def test_send_validates_and_resolves_attachment_ids(monkeypatch, tmp_path):
    f = tmp_path / 'a.txt'
    f.write_text('hello')
    ml._attach['id1'] = f
    sent = []
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.append((to, subject, body, kw)) or (True, 'Отправлено.'))
    assert ml.send({'to': 'nope', 'body': 'x'})['error'] == 'bad_to'
    assert ml.send({'to': 'a@b.c', 'body': '  '})['error'] == 'empty'
    assert ml.send({'to': 'a@b.c', 'body': 'x', 'attach': ['unknown']})['error'] == 'bad_attachment'
    assert ml.send({'to': 'a@b.c', 'subject': 'S', 'body': 'hi', 'cc': 'c@d.e', 'attach': ['id1']}) == {'ok': True, 'message': 'Отправлено.'}
    assert sent[0][3]['attachments'] == [f] and sent[0][3]['cc'] == 'c@d.e' and 'id1' not in ml._attach     # used attachments are released
    assert ml.send({'to': 'a@b.c', 'body': '', 'attach': []})['error'] == 'empty'


def test_attachment_picker_registers_files_and_limits_size(monkeypatch, tmp_path):
    a, b = tmp_path / 'a.bin', tmp_path / 'b.bin'
    a.write_bytes(b'1' * 10)
    b.write_bytes(b'1' * 20)
    monkeypatch.setattr(ml, '_pick_paths', lambda: [str(a), str(b), str(tmp_path / 'missing')])
    r = ml.pick_attachments()
    assert r['ok'] and [x['name'] for x in r['added']] == ['a.bin', 'b.bin'] and len(ml._attach) == 2
    assert ml.drop_attachment(r['added'][0]['id']) == {'ok': True} and len(ml._attach) == 1
    monkeypatch.setattr(ml, 'MAX_ATTACH_BYTES', 25)
    assert ml.pick_attachments()['error'] == 'too_big'


def test_received_attachment_is_saved_by_index_with_a_safe_name(conn, monkeypatch, tmp_path):
    from email.message import EmailMessage
    from email.policy import default
    m = EmailMessage(policy=default)
    m['Subject'] = 's'
    m.set_content('body')
    m.add_attachment(b'DATA', maintype='application', subtype='pdf', filename='..\\evil:name.pdf')
    ims.SESSION.bodies[('inbox', '9')] = m
    monkeypatch.setattr(ml, '_downloads', lambda: tmp_path)
    r = ml.save_attachment('inbox', '9', 0)
    assert r['ok'] and (tmp_path / r['name']).read_bytes() == b'DATA' and '..' not in r['name'] and ':' not in r['name']
    assert ml.save_attachment('inbox', '9', 3)['error'] == 'bad_attachment'
    assert ml.reveal('C:\\Windows\\notepad.exe') == {'ok': False, 'error': 'unknown_file'}


def test_open_url_accepts_only_web_links(monkeypatch):
    import webbrowser
    opened = []
    monkeypatch.setattr(webbrowser, 'open', lambda u: opened.append(u) or True)
    assert ml.open_url('https://example.com/a?b=1')['ok'] and opened == ['https://example.com/a?b=1']
    for bad in ('file:///C:/Windows/notepad.exe', 'javascript:alert(1)', 'https://x.com/a b', 'ftp://x', '', 'https://x.com/\nfoo'):
        assert ml.open_url(bad) == {'ok': False, 'error': 'bad_url'}


def test_command_routing(monkeypatch):
    assert bridge.run_command('mail', {'op': 'state'})['configured'] is True
    assert bridge.run_command('mail', {'op': 'zzz'})['error'] == 'bad_op'
    assert bridge.run_command('open_url', {'url': 'file:///x'})['error'] == 'bad_url'


# ---- HTML rendering ----

def test_sanitizer_drops_active_content_and_rewrites_links():
    html = ('<p onclick="x()">Hi <b>there</b></p><script>alert(1)</script><iframe src="http://e"></iframe><form action="x"><input></form>'
            '<a href="javascript:alert(1)">bad</a><a href="https://ok.example/p?a=1&b=2" target="_blank">good</a><a href="mailto:a@b.c">mail</a>'
            '<div style="color:red;position:fixed">z</div><div style="color:blue">y</div>')
    doc, blocked = mail_render.sanitize(html)
    assert '<script' not in doc and 'alert(1)' not in doc and '<iframe' not in doc and '<form' not in doc and 'onclick' not in doc
    assert 'javascript:' not in doc and 'target=' not in doc
    assert 'data-url="https://ok.example/p?a=1&amp;b=2"' in doc and 'data-url="mailto:a@b.c"' in doc
    assert 'position:fixed' not in doc and 'style="color:blue"' in doc
    assert "default-src 'none'" in doc and 'Hi <b>there</b>' in doc and blocked == 0


def test_remote_images_are_blocked_until_allowed():
    html = '<img src="https://track.example/p.gif" width="1" height="1"><img src="data:image/png;base64,AAAA"><img src="data:image/svg+xml;base64,AAAA">'
    doc, blocked = mail_render.sanitize(html)
    assert blocked == 1 and 'track.example' not in doc and 'data:image/png' in doc and 'svg' not in doc.split('<body>')[1]
    assert "img-src data:;" in doc
    doc2, blocked2 = mail_render.sanitize(html, allow_images=True)
    assert blocked2 == 0 and 'https://track.example/p.gif' in doc2 and 'img-src data: http: https:' in doc2


def test_style_blocks_lose_imports_and_expressions():
    doc, _ = mail_render.sanitize('<style>@import url(http://e/x.css); p{color:red;width:expression(alert(1))} h1{margin:0}</style><p>x</p>')
    assert '@import' not in doc and 'expression' not in doc and 'color:red' in doc and 'h1{margin:0}' in doc


def test_inline_cid_images_are_embedded_and_not_listed_as_attachments():
    from email.message import EmailMessage
    from email.policy import default
    m = EmailMessage(policy=default)
    m['Subject'] = 's'
    m.set_content('plain')
    m.add_alternative('<p>pic <img src="cid:logo1"></p>', subtype='html')
    m.get_payload()[1].add_related(b'\x89PNG', 'image', 'png', cid='<logo1>')
    m.add_attachment(b'x', maintype='application', subtype='pdf', filename='a.pdf')
    r = mail_render.render(m, 'plain')
    assert 'data:image/png;base64,' in r['html'] and [f['name'] for f in r['files']] == ['a.pdf']


def _stored_letter():
    from email.message import EmailMessage
    from email.policy import default
    m = EmailMessage(policy=default)
    m['From'] = 'Anna K <anna@x.org>'
    m['Date'] = 'Tue, 14 Oct 2025 10:00:00 +0000'
    m.set_content('plain original\nsecond line')
    m.add_alternative('<style>p{color:red}</style><p>Hello <a href="https://ok.example/x">link</a><script>x()</script></p>', subtype='html')
    ims.SESSION.bodies[('inbox', '9')] = m


def test_reply_carries_the_original_as_html_and_quoted_text(monkeypatch):
    _stored_letter()
    sent = {}
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.update(body=body, **kw) or (True, 'ok'))
    assert ml.send({'to': 'a@b.c', 'body': 'my answer', 'quote': {'folder': 'inbox', 'uid': '9', 'mode': 'reply'}})['ok']
    assert sent['body'].startswith('my answer\n\n') and 'Anna K <anna@x.org> написал(а):' in sent['body'] and '> plain original' in sent['body']
    h = sent['html']
    assert 'my answer' in h and '<blockquote' in h and 'href="https://ok.example/x"' in h and '<script' not in h and '<style' not in h and 'data-url' not in h


def test_forward_appends_the_original_without_quote_marks(monkeypatch):
    _stored_letter()
    sent = {}
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.update(body=body, **kw) or (True, 'ok'))
    assert ml.send({'to': 'a@b.c', 'body': 'FYI', 'quote': {'folder': 'inbox', 'uid': '9', 'mode': 'fwd'}})['ok']
    assert sent['body'] == 'FYI\n\nplain original\nsecond line' and '<blockquote' not in sent['html'] and 'Hello' in sent['html']
    assert ml.send({'to': 'a@b.c', 'body': 'x', 'quote': {'folder': 'inbox', 'uid': 'zz'}})['error'] == 'bad_uid'


def test_html_alternative_is_added_to_the_outgoing_message(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def ehlo(self): pass
        def starttls(self, context=None): pass
        def login(self, *a): pass
        def send_message(self, msg, to_addrs=None): sent.append(msg)

    monkeypatch.setattr(mail_client, 'get_resolved_mail_config', lambda: {'email': 'me@x.org', 'password': 'p', 'smtp_host': 'h', 'smtp_port': 587})
    monkeypatch.setattr(mail_client.smtplib, 'SMTP', FakeSMTP)
    assert mail_client.send_message('a@b.c', 'S', 'plain', html='<p>rich</p>')[0]
    assert sent[0].get_body(('html',)).get_content().strip() == '<p>rich</p>' and sent[0].get_body(('plain',)).get_content().strip() == 'plain'


# ---- search operators, labels, bulk changes, signature, drafts ----

def test_gmail_style_query_becomes_imap_criteria():
    crit, text = ims.parse_query('from:anna is:unread after:2025-10-01 has:attachment счёт from:Иван "two words"')
    assert crit == ['FROM', '"anna"', 'UNSEEN', 'SINCE', '01-Oct-2025', 'HEADER', 'CONTENT-TYPE', '"multipart/mixed"']
    assert text == 'счёт Иван "two words"'.replace('"two words"', '"two words"') or text.startswith('счёт Иван')
    assert ims.parse_query('before:2025-13-40 is:read')[0] == ['SEEN']
    assert ims.parse_query('from:a"b')[0] == []                                      # no quotes smuggled into the command


def test_custom_folders_are_listed_with_readable_names_and_ids(conn, monkeypatch):
    lines = [b'(\HasNoChildren) "/" "INBOX"', b'(\Sent) "/" "Sent"', b'(\HasNoChildren) "/" "Work"', b'(\HasNoChildren) "/" "&BB4EQgQ,BEAEMAQyBDsENQQ9BDgENQ-"',
             b'(\Noselect \HasChildren) "/" "[Gmail]"', b'(\HasNoChildren \Important) "/" "[Gmail]/Important"']
    monkeypatch.setattr(conn, 'list', lambda: ('OK', lines))
    r = ml.folders()
    assert r['custom'] == [{'id': 'f1', 'name': 'Work'}, {'id': 'f2', 'name': 'Отправление'}]
    assert ml.list_messages('f2')['ok'] and ('select', '"&BB4EQgQ,BEAEMAQyBDsENQQ9BDgENQ-"') in conn.calls
    assert ml.list_messages('f9')['error'] == 'no_folder'
    assert ml.list_messages('f123')['error'] == 'bad_folder'
    assert ml.remove('inbox', ['5'], 'f1') == {'ok': True, 'where': 'f1'}


def test_bulk_flags_and_removal_use_one_command(conn):
    ml.list_messages()
    assert ml.set_flag('inbox', ['5', '4'], 'flagged', True) == {'ok': True}
    assert [c for c in conn.calls if c[0] == 'STORE'][-1][1] == (b'5,4', '+FLAGS', '(\Flagged)')
    assert ml.remove('inbox', ['5', '4'], 'trash') == {'ok': True, 'where': 'trash'}
    assert [x['uid'] for x in ims.SESSION.pages['inbox']['rows']] == ['3', '2', '1']
    assert ml.set_flag('inbox', [], 'seen', True)['error'] == 'bad_uid'
    assert ml.set_flag('inbox', ['1; x'], 'seen', True)['error'] == 'bad_uid'


def test_mark_all_read_and_empty_only_where_allowed(conn):
    ml.list_messages()
    assert ml.mark_all_read('inbox') == {'ok': True} and not any(r['unread'] for r in ims.SESSION.pages['inbox']['rows'])
    assert [c for c in conn.calls if c[0] == 'STORE'][-1][1][0] == '1:*'
    assert ml.empty_folder('inbox')['error'] == 'bad_folder'
    assert ml.empty_folder('trash') == {'ok': True} and ('expunge',) in conn.calls


def test_signature_is_stored_and_appended_on_send(monkeypatch, tmp_path):
    import core.settings_io as sio
    f = tmp_path / 's.json'
    f.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(f))
    assert ml.set_prefs('  Anna\nDev  ')['signature'] == 'Anna\nDev'
    sent = {}
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.update(body=body) or (True, 'ok'))
    assert ml.send({'to': 'a@b.c', 'body': 'hi'})['ok']
    assert sent['body'] == 'hi\n\n-- \nAnna\nDev'
    ml.send({'to': 'a@b.c', 'body': 'hi', 'sign': False})
    assert sent['body'] == 'hi'


def test_draft_is_appended_to_drafts_and_replaces_the_old_one(monkeypatch):
    c = FakeConn()
    c.appended = []
    c.append = lambda box, flags, when, raw: c.appended.append((box, flags, raw)) or ('OK', [])
    c.list = lambda: ('OK', [b'(\Drafts) "/" "Drafts"', b'(\HasNoChildren) "/" "INBOX"'])
    monkeypatch.setattr(mail_client, '_connect_imap', lambda cfg, select_mailbox=True: c)
    ims.SESSION.reset()
    r = ml.save_draft({'to': 'a@b.c', 'subject': 'Plan', 'body': 'text', 'replace': '7'})
    assert r == {'ok': True} and c.appended[0][0] == '"Drafts"' and b'Subject: Plan' in c.appended[0][2] and b'To: a@b.c' in c.appended[0][2]
    assert ('STORE', (b'7', '+FLAGS', '(\Deleted)')) in c.calls
    ims.SESSION.reset()


# ---- unsubscribe and rich text ----

def _newsletter(headers):
    from email.message import EmailMessage
    from email.policy import default
    m = EmailMessage(policy=default)
    m['Subject'] = 'News'
    for k, v in headers.items():
        m[k] = v
    m.set_content('body')
    ims.SESSION.bodies[('inbox', '5')] = m
    return m


def test_unsubscribe_options_are_read_from_the_headers():
    assert ml._unsub_public(ml._unsub_info(_newsletter({}))) is None
    one = ml._unsub_public(ml._unsub_info(_newsletter({'List-Unsubscribe': '<https://news.example/u?x=1>, <mailto:u@news.example>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'})))
    assert one == {'kind': 'oneclick', 'target': 'news.example'}
    assert ml._unsub_public(ml._unsub_info(_newsletter({'List-Unsubscribe': '<http://news.example/u>'}))) == {'kind': 'web', 'target': 'news.example'}
    assert ml._unsub_public(ml._unsub_info(_newsletter({'List-Unsubscribe': '<mailto:leave@news.example?subject=bye>'}))) == {'kind': 'mail', 'target': 'leave@news.example'}
    assert 'url' not in one                                                          # the raw link never reaches the UI


def test_one_click_unsubscribe_posts_to_the_letters_own_link(monkeypatch):
    _newsletter({'List-Unsubscribe': '<https://news.example/u?x=1>', 'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'})
    seen = []
    monkeypatch.setattr(ml, '_http_post', lambda url: seen.append(url) or 200)
    assert ml.unsubscribe('inbox', '5') == {'ok': True, 'how': 'oneclick', 'code': 200} and seen == ['https://news.example/u?x=1']
    monkeypatch.setattr(ml, '_http_post', lambda url: 500)
    assert ml.unsubscribe('inbox', '5')['ok'] is False


def test_unsubscribe_refuses_private_hosts():
    import socket
    real = socket.getaddrinfo
    socket.getaddrinfo = lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))]
    try:
        with pytest.raises(ims.MailError) as ex:
            ml._http_post('https://evil.example/u')
        assert ex.value.code == 'blocked_host'
        with pytest.raises(ims.MailError):
            ml._http_post('http://news.example/u')
    finally:
        socket.getaddrinfo = real


def test_web_and_mailto_unsubscribe(monkeypatch):
    import webbrowser
    opened = []
    monkeypatch.setattr(webbrowser, 'open', lambda u: opened.append(u) or True)
    _newsletter({'List-Unsubscribe': '<https://news.example/page>'})
    assert ml.unsubscribe('inbox', '5') == {'ok': True, 'how': 'web'} and opened == ['https://news.example/page']
    sent = []
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.append((to, subject, body)) or (True, 'ok'))
    _newsletter({'List-Unsubscribe': '<mailto:leave@news.example?subject=bye%20now>'})
    assert ml.unsubscribe('inbox', '5')['ok'] and sent == [('leave@news.example', 'bye now', 'unsubscribe')]
    _newsletter({})
    assert ml.unsubscribe('inbox', '5')['error'] == 'no_unsubscribe'


def test_editor_html_is_sanitized_and_sent_with_the_plain_text(monkeypatch):
    sent = {}
    monkeypatch.setattr(mail_client, 'send_message', lambda to, subject, body, **kw: sent.update(body=body, **kw) or (True, 'ok'))
    monkeypatch.setattr(ml, 'get_prefs', lambda: {'ok': True, 'signature': 'Anna'})
    r = ml.send({'to': 'a@b.c', 'body': 'Hello bold', 'html': 'Hello <b onclick="x()">bold</b><script>x()</script><a href="https://ok.example">l</a>'})
    assert r['ok'] and sent['body'] == 'Hello bold\n\n-- \nAnna'
    assert '<b>bold</b>' in sent['html'] and '<script' not in sent['html'] and 'onclick' not in sent['html'] and 'href="https://ok.example"' in sent['html'] and '-- <br>Anna' in sent['html']
    sent.clear()
    ml.send({'to': 'a@b.c', 'body': 'plain only'})
    assert sent['html'] == ''
