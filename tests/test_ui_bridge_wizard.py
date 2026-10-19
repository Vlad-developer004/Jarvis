"""ui_next/bridge/wizard.py: the first-run flag."""
import json

import core.settings_io as sio
from ui_next import bridge


def test_flag_lifecycle(tmp_path, monkeypatch):
    path = tmp_path / 's.json'
    path.write_text('{"keep": 1}', encoding='utf-8')
    monkeypatch.setattr(sio, '_path', lambda: str(path))
    from core.system import app_state
    monkeypatch.setattr(app_state, 'hud', None, raising=False)
    run = lambda **kw: bridge.run_command('wizard', kw)
    assert run(op='state') == {'ok': True, 'done': False, 'old_welcome_done': False}
    r = run(op='done')
    assert r['ok'] and r['done'] is True and run(op='state')['old_welcome_done'] is True
    assert run(op='reset')['done'] is False and run(op='state')['done'] is False
    assert json.loads(path.read_text(encoding='utf-8'))['keep'] == 1 and run(op='x')['error'] == 'bad_op'
