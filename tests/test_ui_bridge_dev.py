"""ui_next/bridge/dev.py: the Developer tab (IDE context, extensions, editors, projects)."""
import pytest

import core.settings_io as sio
from ui_next import bridge
from ui_next.bridge import dev


@pytest.fixture
def env(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    from actions import dev_projects
    monkeypatch.setattr(dev_projects, 'detect_installed_editors', lambda: [('code', 'VS Code'), ('pycharm', 'PyCharm')])
    monkeypatch.setattr(dev_projects, '_SETTINGS_PATH', str(path))
    monkeypatch.setattr(dev, '_detected', None)
    return tmp_path


def run(**kw):
    return bridge.run_command('dev', kw)


def test_state_has_the_old_defaults(env):
    r = run(op='state')
    assert r['ok'] and r['context_apps'] == dev.DEFAULT_CONTEXT_APPS and r['depth'] == 4 and not r['allow_parent'] and r['extensions'] == [] and r['projects'] == [] and r['default_editor'] == 'code'


def test_context_apps(env):
    assert run(op='ctx_add', app=' Rider64.EXE ')['context_apps'][-1] == 'rider64.exe'
    assert run(op='ctx_add', app='rider64.exe')['error'] == 'exists' and run(op='ctx_add', app='a/b')['error'] == 'bad_value'
    assert 'code.exe' not in run(op='ctx_remove', app='CODE.exe')['context_apps'] and run(op='ctx_remove', app='zz')['error'] == 'not_found'


def test_search_settings_are_validated(env):
    assert run(op='parent_search', on=True)['allow_parent'] is True
    assert run(op='depth', value=7)['depth'] == 7 and run(op='depth', value=11)['error'] == 'bad_value' and run(op='depth', value='x')['error'] == 'bad_value'


def test_extensions(env):
    assert run(op='ext_add', ext='.PY')['extensions'] == ['py']
    assert run(op='ext_add', ext='py')['error'] == 'exists' and run(op='ext_add', ext='a b')['error'] == 'bad_value'
    assert run(op='ext_remove', ext='py')['extensions'] == [] and run(op='ext_remove', ext='py')['error'] == 'not_found'


def test_editors_and_default(env):
    r = run(op='editors')
    assert [e['key'] for e in r['editors']] == ['code', 'pycharm'] and r['default'] == 'code'
    assert run(op='editor_default', key='pycharm')['default_editor'] == 'pycharm' and run(op='editor_default', key='nope')['error'] == 'not_found'


def test_custom_editor_lifecycle(env):
    exe = env / 'myedit.exe'
    exe.write_bytes(b'x')
    r = run(op='editor_add', path=str(exe), name='Мой')
    key = 'custom:' + str(exe)
    assert r['ok'] and r['default_editor'] == key and {'key': key, 'name': 'Мой', 'custom': True} in r['editors']
    assert run(op='editor_add', path=str(env / 'x.txt'))['error'] == 'bad_value'
    r = run(op='editor_remove', key=key)
    assert r['ok'] and r['default_editor'] == 'code' and key not in [e['key'] for e in r['editors']]
    assert run(op='editor_remove', key='code')['error'] == 'not_found'


def test_add_editor_dialog_cancel(env, monkeypatch):
    monkeypatch.setattr('ui_next.bridge.filepick.pick_files', lambda *a, **k: [])
    assert run(op='editor_add')['error'] == 'cancelled'


def test_projects(env):
    folder = env / 'proj'
    folder.mkdir()
    assert run(op='project_save', name='', path=str(folder))['error'] == 'required'
    assert run(op='project_save', name='A', path=str(env / 'none'))['error'] == 'path_missing'
    assert run(op='project_save', name='A', path=str(folder), editor='ghost')['error'] == 'not_found'
    r = run(op='project_save', name='A', path=str(folder), editor='pycharm')
    assert r['ok'] and r['projects'] == [{'name': 'A', 'path': str(folder), 'editor': 'pycharm', 'exists': True}]
    assert run(op='project_save', name='B', path=str(folder))['ok'] and run(op='project_save', name='b', path=str(folder))['error'] == 'exists'
    r = run(op='project_save', name='A2', path=str(folder), old_name='A')
    assert [p['name'] for p in r['projects']] == ['A2', 'B'] and run(op='project_save', name='B', path=str(folder), old_name='A2')['error'] == 'exists'
    assert [p['name'] for p in run(op='project_remove', name='a2')['projects']] == ['B'] and run(op='project_remove', name='zz')['error'] == 'not_found'


def test_project_open(env, monkeypatch):
    folder = env / 'proj'
    folder.mkdir()
    run(op='project_save', name='A', path=str(folder))
    from actions import dev_projects
    seen = []
    monkeypatch.setattr(dev_projects, 'open_project', lambda p: seen.append(p) or (True, ''))
    assert run(op='project_open', name='a')['ok'] and seen[0]['name'] == 'A' and run(op='project_open', name='zz')['error'] == 'not_found'
    monkeypatch.setattr(dev_projects, 'open_project', lambda p: (False, 'editor not found: code'))
    assert run(op='project_open', name='A')['error'] == 'no_editor'


def test_folder_pick_and_search(env, monkeypatch):
    monkeypatch.setattr('ui_next.bridge.filepick.pick_folder', lambda t: '')
    assert run(op='pick_folder')['error'] == 'cancelled'
    from actions import dev_projects
    monkeypatch.setattr(dev_projects, 'search_projects_on_disk', lambda q, n: ['C:/x/jarvis'])
    assert run(op='find', query='джарвис')['results'] == ['C:/x/jarvis'] and run(op='find', query='a')['error'] == 'required'


def test_other_settings_survive(env):
    run(op='ext_add', ext='py')
    run(op='depth', value=3)
    assert sio.read()['keep'] == 1
