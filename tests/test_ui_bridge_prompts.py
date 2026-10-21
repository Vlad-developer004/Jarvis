"""ui_next/bridge/prompts.py and dialogs.py: dialogs the core waits for, shown in the new window, with every answer checked against what was offered."""
import threading
import time

import pytest

from ui_next import bridge
from ui_next.bridge import dialogs, prompts


@pytest.fixture
def pr(monkeypatch):
    sent = []
    monkeypatch.setattr(prompts, '_publish', lambda topic, payload, sticky=True: sent.append((topic, payload)))
    monkeypatch.setattr(prompts, 'available', lambda: True)
    monkeypatch.setattr(prompts, '_cur', None)
    return sent


def run_bg(fn, *a, **kw):
    box = {}
    t = threading.Thread(target=lambda: box.setdefault('r', fn(*a, **kw)), daemon=True)
    t.start()
    end = time.time() + 2
    while time.time() < end and not prompts.current_id():
        time.sleep(0.005)
    time.sleep(0.05)                                   # the prompt is registered just before it is published
    return box, t


def answer(status, value=None, pid=None):
    return bridge.run_command('prompt', {'op': 'answer', 'id': pid or prompts.current_id(), 'status': status, 'value': value})


def opened(sent):
    return [p for t, p in sent if t == 'prompt' and p['open']][-1]


TEXT = dict(title='T', header='Создать папку', ok_text='ОК', cancel_text='Отмена', placeholder='', hint_voice='', voice_confirm=('создай',), voice_cancel=('отмена',))


def test_without_a_new_window_nothing_is_handled(monkeypatch):
    monkeypatch.setattr(prompts, 'available', lambda: False)
    assert dialogs.ask_text(**TEXT) is dialogs.NOT_HANDLED and dialogs.ask_git_stage('r', []) is dialogs.NOT_HANDLED
    assert dialogs.open_cleanup([], lambda p: None) is False and dialogs.open_yt_picker([], lambda c, i: None) is False and dialogs.show_guard_alert(None) is False


def test_plain_text(pr):
    box, t = run_bg(dialogs.ask_text, **TEXT)
    assert opened(pr)['kind'] == 'text' and opened(pr)['data']['path'] is None
    assert answer('ok', {'text': '  макрос  '})['ok'] and (t.join(2) or True) and box['r'] == 'макрос'
    box, t = run_bg(dialogs.ask_text, **TEXT)
    assert answer('cancel')['ok'] and (t.join(2) or True) and box['r'] is None


def test_required_text_cannot_be_empty(pr):
    box, t = run_bg(dialogs.ask_text, **{**TEXT, 'require_message_to_confirm': True})
    assert answer('ok', {'text': ' '})['error'] == 'bad_value' and prompts.current_id()
    assert answer('ok', {'text': 'fix'})['ok'] and (t.join(2) or True) and box['r'] == 'fix'


def test_folder_and_name_and_type(pr, tmp_path, monkeypatch):
    monkeypatch.setattr('actions.programming_extensions.get_programming_extensions', lambda: ['py'])   # the list comes from the user's settings file; CI has none
    box, t = run_bg(dialogs.ask_text, **{**TEXT, 'initial_path': str(tmp_path), 'show_extension_field': True, 'default_extension': 'py'})
    d = opened(pr)['data']
    assert d['with_ext'] and d['ext'] == 'py' and 'docx' in [e['ext'] for e in d['exts']]
    for bad in ({'text': '../evil', 'path': str(tmp_path), 'ext': 'py'}, {'text': 'a', 'path': str(tmp_path), 'ext': 'p y'}, {'text': '', 'path': str(tmp_path), 'ext': 'py'}, {'text': 'a:b', 'path': 'x', 'ext': 'py'}):
        assert answer('ok', bad)['error'] == 'bad_value'
    assert answer('ok', {'text': 'utils', 'path': str(tmp_path), 'ext': 'PY'})['ok'] and (t.join(2) or True) and box['r'] == (str(tmp_path), 'utils', 'py')


def test_folder_without_type_returns_a_pair(pr, tmp_path):
    box, t = run_bg(dialogs.ask_text, **{**TEXT, 'initial_path': str(tmp_path)})
    assert answer('ok', {'text': 'Новая', 'path': str(tmp_path)})['ok'] and (t.join(2) or True) and box['r'] == (str(tmp_path), 'Новая')


def test_git_answers_are_checked_against_the_listed_files(pr, monkeypatch):
    from actions import git_commit
    monkeypatch.setattr(git_commit, 'get_branches', lambda r: ['main', 'dev'])
    monkeypatch.setattr(git_commit, 'get_current_branch', lambda r: 'main')
    files = [{'file': 'a.py', 'status': 'M'}, {'file': 'b.py', 'status': '??'}]
    box, t = run_bg(dialogs.ask_git_stage, 'C:/repo', files)
    d = opened(pr)['data']
    assert d['current'] == 'main' and [f['file'] for f in d['files']] == ['a.py', 'b.py']
    assert answer('ok', {'files': ['a.py', '../../secret'], 'branch': 'main'})['error'] == 'bad_value'
    assert answer('ok', {'files': ['a.py'], 'branch': '--upload-pack=x'})['error'] == 'bad_value'
    assert answer('ok', {'files': ['a.py'], 'branch': 'a..b'})['error'] == 'bad_value'
    ok = answer('ok', {'files': ['a.py'], 'message': ' fix ', 'branch': 'feature/x', 'push': True, 'force': True, 'upstream': True, 'pr_title': ' PR '})
    t.join(2)
    assert ok['ok'] and box['r'] == {'files': ['a.py'], 'message': 'fix', 'branch': 'feature/x', 'push': True, 'force': True, 'upstream': True, 'open_pr': True, 'pr_title': 'PR'}


def test_git_options_need_push(pr, monkeypatch):
    from actions import git_commit
    monkeypatch.setattr(git_commit, 'get_branches', lambda r: ['main'])
    monkeypatch.setattr(git_commit, 'get_current_branch', lambda r: 'main')
    box, t = run_bg(dialogs.ask_git_stage, 'r', [{'file': 'a', 'status': 'M'}])
    answer('ok', {'files': ['a'], 'branch': 'main', 'push': False, 'force': True, 'upstream': True, 'pr_title': 'x'})
    t.join(2)
    assert box['r']['force'] is False and box['r']['upstream'] is False and box['r']['open_pr'] is False


def test_git_cancel(pr, monkeypatch):
    box, t = run_bg(dialogs.ask_git_stage, 'r', [])
    answer('cancel')
    t.join(2)
    assert box['r'] is None


def test_cleanup_deletes_only_listed_paths(pr):
    got = []
    cands = [{'path': 'C:/x/a', 'name': 'a', 'size_bytes': 100, 'age_days': 30}, {'path': 'C:/x/b', 'name': 'b', 'size_bytes': 5, 'age_days': 90}]
    assert dialogs.open_cleanup(cands, got.append)
    assert opened(pr)['data']['items'][0] == {'path': 'C:/x/a', 'name': 'a', 'size': 100, 'age': 30}
    assert answer('ok', ['C:/x/a', 'C:/Windows'])['error'] == 'bad_value'
    assert answer('ok', ['C:/x/b', 'C:/x/b'])['ok']
    time.sleep(0.2)
    assert got == [['C:/x/b']]


def test_cleanup_cancel_and_empty_do_nothing(pr):
    got = []
    dialogs.open_cleanup([{'path': 'p', 'name': 'n', 'size_bytes': 1, 'age_days': 1}], got.append)
    answer('cancel')
    dialogs.open_cleanup([{'path': 'p', 'name': 'n', 'size_bytes': 1, 'age_days': 1}], got.append)
    answer('ok', [])
    time.sleep(0.2)
    assert got == []


def picker(pr, monkeypatch, timeout=20.0):
    monkeypatch.setattr(dialogs, '_thumb_uri', lambda url: 'data:image/jpeg;base64,AAA')
    log = []
    cands = [{'title': 'A', 'url': 'u1', 'thumbnail': 't1'}, {'title': 'B', 'url': 'u2', 'thumbnail': ''}]
    assert dialogs.open_yt_picker(cands, lambda c, i: log.append(('pick', c['url'], i)), lambda: log.append('timeout'), lambda: log.append('cancel'), timeout_sec=timeout)
    return log


def test_picker_click_voice_cancel_and_timeout(pr, monkeypatch):
    log = picker(pr, monkeypatch)
    assert dialogs.yt_open() and answer('ok', 7)['error'] == 'bad_value' and answer('ok', 1)['ok']
    time.sleep(0.2)
    assert log == [('pick', 'u2', 1)] and not dialogs.yt_open()
    log = picker(pr, monkeypatch)
    assert dialogs.yt_select(0) is True
    time.sleep(0.2)
    assert log[-1] == ('pick', 'u1', 0)
    log = picker(pr, monkeypatch)
    assert dialogs.yt_select(9) is False and dialogs.yt_cancel() is True
    time.sleep(0.2)
    assert log == ['cancel'] and dialogs.yt_cancel() is False
    log = picker(pr, monkeypatch, timeout=0.15)
    time.sleep(0.5)
    assert log == ['timeout'] and not prompts.current_id()


def test_thumbnails_arrive_in_a_second_message(pr, monkeypatch):
    picker(pr, monkeypatch)
    end = time.time() + 2
    while time.time() < end and not any(p['data']['items'][0]['thumb'] for t, p in pr if t == 'prompt' and p['open']):
        time.sleep(0.01)
    assert opened(pr)['data']['items'][0]['thumb'].startswith('data:image/jpeg')
    answer('cancel')


def test_a_new_prompt_cancels_the_open_one(pr):
    got = []
    dialogs.open_cleanup([{'path': 'p', 'name': 'n', 'size_bytes': 1, 'age_days': 1}], got.append)
    first = prompts.current_id()
    assert dialogs.show_guard_alert(None) is True
    assert prompts.current_id() != first and answer('ok', None, pid=first)['error'] == 'expired'
    assert opened(pr)['kind'] == 'notice' and answer('ok')['ok']


def test_spoken_words_press_the_buttons_of_the_screen(pr):
    box, t = run_bg(dialogs.ask_text, **TEXT)
    from ui_next.voice_prompt import try_consume_voice_prompt
    assert try_consume_voice_prompt('создай') is True
    cmds = [p for topic, p in pr if topic == 'prompt_cmd']
    assert cmds == [{'id': prompts.current_id(), 'action': 'confirm'}]
    assert try_consume_voice_prompt('отмена') is True and pr[-1][1]['action'] == 'cancel'
    answer('cancel')
    t.join(2)
    assert try_consume_voice_prompt('создай') is False                    # the registration went with the prompt


def test_bad_requests_are_refused(pr):
    assert bridge.run_command('prompt', {'op': 'x'})['error'] == 'bad_op' and bridge.run_command('prompt', {'op': 'answer', 'id': 'zz'})['error'] == 'bad_value'
    assert answer('ok', 1, pid=99)['error'] == 'expired'
    dialogs.open_cleanup([], lambda p: None)
    assert answer('maybe')['error'] == 'bad_value'
    answer('cancel')


def test_the_core_text_dialog_reaches_the_window(pr, monkeypatch):
    from ui_next import host
    box, t = run_bg(host.ask_text, title='T', header='Имя', placeholder='x')
    assert opened(pr)['kind'] == 'text' and opened(pr)['data']['hint']
    answer('ok', {'text': 'готово'})
    t.join(2)
    assert box['r'] == 'готово'


def test_git_dialog_data_carries_warnings_counts_and_a_suggested_message(pr, monkeypatch, tmp_path):
    from actions import git_commit
    monkeypatch.setattr(git_commit, 'get_branches', lambda r: ['main'])
    monkeypatch.setattr(git_commit, 'get_current_branch', lambda r: 'main')
    (tmp_path / '.env').write_text('A=1', encoding='utf-8')
    (tmp_path / 'ok.py').write_text('print(1)\n', encoding='utf-8')
    files = [{'file': '.env', 'status': '??'}, {'file': 'ok.py', 'status': '??'}]
    box, t = run_bg(dialogs.ask_git_stage, str(tmp_path), files)
    d = opened(pr)['data']
    rows = {f['file']: f for f in d['files']}
    assert rows['.env']['warn'] == 'secret_name' and rows['ok.py']['warn'] == '' and rows['ok.py']['add'] == 1
    assert d['suggest'].startswith('feat')
    answer('cancel')
    t.join(2)
