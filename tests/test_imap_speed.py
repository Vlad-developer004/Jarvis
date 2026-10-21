"""ui_next/bridge/imapsession.py: the Mail screen was slow on a big mailbox. These tests pin what makes it fast: no NOOP round trip per command,
a plain list that needs no SEARCH over every UID, a cached unread counter, and previews fetched in small batches."""
import pytest

from actions import mail_client
from ui_next.bridge import imapsession as ims
from ui_next.bridge import mail as ml
from test_ui_bridge_mail import FakeConn


@pytest.fixture
def conn(monkeypatch):
    c = FakeConn()
    c.pings = 0
    real_noop = c.noop

    def noop():
        c.pings += 1
        return real_noop()
    c.noop = noop
    monkeypatch.setattr(mail_client, '_connect_imap', lambda cfg, select_mailbox=True: c)
    monkeypatch.setattr(mail_client, 'get_resolved_mail_config', lambda: {'email': 'me@example.com', 'password': 'x', 'imap_host': 'h', 'imap_port': 993, 'mailbox': 'INBOX'})
    ims.SESSION.reset()
    yield c
    ims.SESSION.reset()


def calls(c, name):
    return [x for x in c.calls if x[0].lower() == name]


def test_commands_in_a_row_do_not_ping_the_server_each_time(conn):
    ml.folders()
    ml.list_messages()
    ml.read_message('inbox', '5', False, False)
    assert conn.pings == 0                                    # one connection, used a moment ago: no NOOP before every command
    ims.SESSION.last_io -= ims.IDLE_PING + 1                  # silent for a while: now it is checked
    ml.folders()
    assert conn.pings == 1


def test_a_plain_list_asks_for_the_count_and_the_newest_letters_not_for_every_uid(conn):
    r = ml.list_messages(limit=2)
    assert [x['uid'] for x in r['rows']] == ['5', '4'] and r['total'] == 5 and r['more'] is True
    assert not calls(conn, 'search') and calls(conn, 'seqfetch')[-1][1] == ('4:5',)
    r2 = ml.list_messages(offset=2, limit=2)
    assert [x['uid'] for x in r2['rows']] == ['3', '2'] and r2['more'] is True
    r3 = ml.list_messages(offset=4, limit=2)
    assert [x['uid'] for x in r3['rows']] == ['1'] and r3['more'] is False


def test_the_list_falls_back_to_search_when_the_server_will_not_give_a_count(conn, monkeypatch):
    monkeypatch.setattr(ims.Session, '_message_count', staticmethod(lambda c, raw: None))
    r = ml.list_messages(limit=2)
    assert [x['uid'] for x in r['rows']] == ['5', '4'] and calls(conn, 'search')


def test_filters_and_searches_still_use_search(conn):
    ml.list_messages(flt='unread')
    assert calls(conn, 'search')


def unread_queries(c):
    return [x for x in c.calls if x[0] == 'status' and x[1] == '(UNSEEN)']


def test_the_unread_counter_is_reused_until_a_letter_changes(conn):
    assert ml.folders()['unread'] == 3
    ml.folders()
    assert len(unread_queries(conn)) == 1
    ml.set_flag('inbox', ['5'], 'seen', True)
    ml.folders()
    assert len(unread_queries(conn)) == 2                      # marking a letter invalidates the cached counter
    ml.read_message('inbox', '4', False, True)
    ml.folders()
    assert len(unread_queries(conn)) == 3                      # so does opening an unread one


def test_the_first_screen_can_skip_the_unread_counter(conn):
    r = ml.folders(unread=False)
    assert r['ok'] and r['unread'] == 0 and not unread_queries(conn)
    assert ml.folders()['unread'] == 3 and len(unread_queries(conn)) == 1
    assert ml.folders(unread=False)['unread'] == 3             # afterwards the last known value is reported


def test_previews_are_fetched_in_small_batches(conn):
    uids = [str(i) for i in range(1, 26)]
    fetched = []
    real_uid = conn.uid

    def uid(cmd, *args):
        if cmd.lower() == 'fetch' and 'TEXT' in args[1]:
            fetched.append(args[0].split(b','))
            return 'OK', []
        return real_uid(cmd, *args)
    conn.uid = uid
    ml.snippets('inbox', uids)
    assert [len(b) for b in fetched] == [10, 10, 5] and sum(fetched, []) == [u.encode() for u in uids]


def test_a_recent_cached_page_is_fresh_so_the_window_does_not_refetch_it(conn):
    first = ml.list_messages()
    assert first['cached'] is False and first['fresh'] is True
    again = ml.list_messages()
    assert again['cached'] is True and again['fresh'] is True
    ims.SESSION.page_at['inbox'] -= ims.PAGE_FRESH + 1
    old = ml.list_messages()
    assert old['cached'] is True and old['fresh'] is False     # stale: shown at once, then refreshed in the background


def stores(c):
    return [x for x in c.calls if x[0] == 'STORE']


@pytest.fixture
def queued(monkeypatch):
    """The Seen flag is only queued (no worker thread), so a test can look at the exact moment before it is stored."""
    monkeypatch.setattr(ims.Session, '_mark_later', lambda self, role, uid: self.seen_todo.__setitem__((role, uid), None))


def test_opening_a_letter_does_not_wait_for_the_seen_flag(conn, queued):
    ml.list_messages()
    r = ml.read_message('inbox', '5')
    assert r['ok'] and r['was_unread'] is True
    assert not stores(conn) and ('inbox', '5') in ims.SESSION.seen_todo      # shown first, flagged afterwards
    assert ims.SESSION.pages['inbox']['rows'][0]['unread'] is False          # the cached list already shows it as read
    ims.SESSION.settle(0.05)
    ml.folders()                                                              # anything else that talks to the server stores it on the way
    assert len(stores(conn)) == 1 and not ims.SESSION.seen_todo


def test_the_unread_counter_is_asked_after_the_pending_flags_are_stored(conn, queued):
    ml.list_messages()
    ml.read_message('inbox', '5')
    ml.folders()
    order = [x[0] if x[0] != 'status' else x[1] for x in conn.calls if x[0] in ('STORE', 'status')]
    assert order.index('STORE') < order.index('(UNSEEN)')


def test_marking_it_unread_again_cancels_the_pending_flag(conn, queued):
    ml.list_messages()
    ml.read_message('inbox', '5')
    ml.set_flag('inbox', ['5'], 'seen', False)
    ml.folders()
    assert [x[1][1] for x in stores(conn)] == ['-FLAGS']                      # only the later change reached the server


def test_deleting_it_cancels_the_pending_flag(conn, queued):
    ml.list_messages()
    ml.read_message('inbox', '5')
    ml.remove('inbox', '5', 'trash')
    assert ('inbox', '5') not in ims.SESSION.seen_todo


def test_a_cached_letter_outside_the_listing_still_asks_the_server(conn):
    assert ml.read_message('inbox', '5', mark=False)['ok']                    # no listing loaded: the row is unknown
    r = ml.read_message('inbox', '5')
    ims.SESSION.settle()
    assert r['was_unread'] is True and len(stores(conn)) == 1
