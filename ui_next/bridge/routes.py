"""The operation routers of the bridge commands that need no package state of their own: each takes the command body and calls the matching screen module.

Moved out of __init__.py to keep it small; the code is unchanged. Package state (the running handler, `publish`, the catalog refresh) is read at call time
with `from . import ...`, so the values the core set in __init__ (and the ones tests patch there) are the ones used.
"""
from __future__ import annotations

import threading


def extension(data: dict) -> dict:
    """Install / uninstall an extension that needs no setup. Extensions with a setup flow (Telegram chat id, mail account,
    calendar sources, the ETS2 telemetry DLL, the Planetbase mod) report `needs_setup`: the UI sends the user to the old dialog."""
    from . import publish, _publish_catalog_async
    from .extensions import SIMPLE, publish_extensions, set_installed
    ext_id = str(data.get('id', ''))
    if ext_id not in SIMPLE:
        return {'ok': False, 'error': 'needs_setup'}
    ok = set_installed(ext_id, bool(data.get('on')))
    publish_extensions(publish)
    _publish_catalog_async()
    return {'ok': ok}


def ext_setup(data: dict) -> dict:
    """Setup form of an extension that needs more than a flag (see ext_setup): op `get` | `save` | `act`."""
    from . import _publish_catalog_async, ext_setup, publish
    from .extensions import publish_extensions
    ext_id, op = str(data.get('id', '')), str(data.get('op', 'get'))
    if ext_id not in ext_setup.KINDS:
        return {'ok': False, 'error': 'unknown_extension'}
    if op == 'get':
        return {'ok': True, 'state': ext_setup.get_state(ext_id)}
    res = ext_setup.save(ext_id, data) if op == 'save' else ext_setup.act(ext_id, data) if op == 'act' else {'ok': False, 'error': 'bad_op'}
    if res.get('ok'):
        publish_extensions(publish)
        _publish_catalog_async()
        res['state'] = ext_setup.get_state(ext_id)
    return res


def profile(data: dict) -> dict:
    """Game profile editor (see profiles): op `games` | `get` | `set_key` | `test` | `macro_get` | `macro_save` | `macro_create` | `macro_delete` | `grid_set`."""
    from . import profiles as pr
    op, game = str(data.get('op', '')), str(data.get('game', ''))
    if op == 'games':
        return {'ok': True, 'games': pr.list_games()}
    if op == 'get':
        res = pr.get_game(game)
        return {'ok': True, **res} if res else {'ok': False, 'error': 'unknown_game'}
    if op == 'set_key':
        return pr.set_key(game, str(data.get('row', '')), data.get('key', ''))
    if op == 'test':
        return pr.test(game, str(data.get('row', '')))
    if op == 'macro_get':
        return pr.macro_get(game, data.get('idx'))
    if op == 'macro_save':
        return pr.macro_save(game, data.get('idx'), data.get('sequence'), data.get('variants'))
    if op == 'macro_create':
        return pr.macro_create(game, data.get('name', ''), data.get('variants'), data.get('first', ''))
    if op == 'macro_delete':
        return pr.macro_delete(game, data.get('idx'))
    if op == 'grid_set':
        return pr.grid_set(game, data.get('set'), data.get('slot'), data.get('name', ''))
    return {'ok': False, 'error': 'bad_op'}


def currency(data: dict) -> dict:
    """Exchange-rate settings: op `get` (home currency, supported list, followed list), `set` {base}, `watch` {codes}, `rates` (followed ones priced now)."""
    from actions import currency_pairs as cp
    from core import i18n
    uk = i18n.get_language() == 'uk'
    bitcoin = 'Біткоїн' if uk else 'Биткоин'
    op = str(data.get('op', 'get'))
    if op == 'set':
        ok = cp.set_base(str(data.get('base', '')))
        return {'ok': ok, 'base': cp.get_base()}
    if op == 'watch':
        ok = cp.set_watch(data.get('codes'))
        return {'ok': ok, 'watch': cp.get_watch()}
    if op == 'rates':
        base = cp.get_base()
        names = {c['code']: c['name'] for c in cp.supported(uk)}
        rows = []
        for code in cp.get_watch():
            try:
                value = cp.rate(code, base) if code != base else None
            except Exception:
                value = None
            rows.append({'code': code, 'name': bitcoin if code == 'BTC' else names.get(code, code), 'rate': value})
        return {'ok': True, 'base': base, 'rates': rows}
    return {'ok': True, 'base': cp.get_base(), 'list': cp.supported(uk) + [{'code': 'BTC', 'name': bitcoin}], 'watch': cp.get_watch()}


def voice(data: dict) -> dict:
    """Voice settings (see voice): op `get` | `set` {key, value} | `devices` | `set_devices` {input, output} | `calibrate` | `say`."""
    from . import _handler, _publish_catalog_async, publish, voice as vc
    op = str(data.get('op', 'get'))
    if op == 'get':
        return {'ok': True, 'values': vc.get_all()}
    if op == 'set':
        res = vc.set_value(str(data.get('key', '')), data.get('value'))
        if res.get('ok') and data.get('key') == 'language':
            _publish_catalog_async()        # the command list follows the language (game profiles are per language)
        return res
    if op == 'devices':
        return {'ok': True, **vc.scan_devices()}
    if op == 'set_devices':
        return vc.set_devices(data.get('input'), data.get('output'))
    if op == 'calibrate':
        return vc.calibrate(publish)
    if op == 'llm':
        sub = str(data.get('do', 'state'))
        fn = {'pick': vc.llm_pick, 'reset': vc.llm_reset, 'download': vc.llm_download, 'cancel': vc.llm_cancel}.get(sub)
        return fn() if fn else {'ok': True, 'llm': vc.llm_state()}
    if op == 'say':
        handler = _handler
        if handler is None:
            return {'ok': False, 'error': 'no_handler'}
        threading.Thread(target=lambda: handler.speak('Проверка голоса. Если вы меня слышите, всё настроено.'), daemon=True, name='ui-bridge-say').start()
        return {'ok': True}
    return {'ok': False, 'error': 'bad_op'}


def mail(data: dict) -> dict:
    """Mail screen (see mail): op `state` | `folders` | `list` {folder, filter, q, offset, refresh} | `read` {folder, uid, images, mark} | `flag` {folder, uids, flag, on} |
    `remove` {folder, uids, to} | `read_all` {folder} | `empty` {folder} | `save` {folder, uid, idx} | `reveal` {path} | `prefs` | `prefs_set` {signature} | `unsubscribe` {folder, uid} | `draft` {...} |
    `send` {to, cc, bcc, subject, body, quote, replace, in_reply_to, references, attach} | `pick` | `drop` {id}."""
    from . import mail as ml
    op = str(data.get('op', 'state'))
    folder = data.get('folder', 'inbox')
    if op == 'state':
        return {'ok': True, **ml.configured()}
    if op == 'folders':
        return ml.folders()
    if op == 'list':
        return ml.list_messages(folder, str(data.get('filter', 'all')), data.get('q', ''), data.get('offset', 0), data.get('limit', 40), bool(data.get('refresh')))
    if op == 'read':
        return ml.read_message(folder, data.get('uid', ''), bool(data.get('images')), data.get('mark', True) is not False)
    if op == 'flag':
        return ml.set_flag(folder, data.get('uids', data.get('uid', '')), str(data.get('flag', '')), bool(data.get('on')))
    if op == 'remove':
        return ml.remove(folder, data.get('uids', data.get('uid', '')), str(data.get('to', '')))
    if op == 'read_all':
        return ml.mark_all_read(folder)
    if op == 'empty':
        return ml.empty_folder(folder)
    if op == 'save':
        return ml.save_attachment(folder, data.get('uid', ''), data.get('idx'))
    if op == 'reveal':
        return ml.reveal(str(data.get('path', '')))
    if op == 'prefs':
        return ml.get_prefs()
    if op == 'prefs_set':
        return ml.set_prefs(data.get('signature', ''))
    if op == 'unsubscribe':
        return ml.unsubscribe(folder, data.get('uid', ''))
    if op == 'draft':
        return ml.save_draft(data)
    if op == 'send':
        return ml.send(data)
    if op == 'pick':
        return ml.pick_attachments()
    if op == 'drop':
        return ml.drop_attachment(str(data.get('id', '')))
    return {'ok': False, 'error': 'bad_op'}


def media(data: dict) -> dict:
    """What is playing and its controls (see actions/now_playing): op `state` | `control` {action: toggle|play|pause|stop|next|prev|seek_to|seek_by, id?, seconds?}."""
    from actions import now_playing as np
    op = str(data.get('op', 'state'))
    if op == 'state':
        return {'ok': True, 'sessions': np.snapshot()}
    if op == 'control':
        try:
            sec = float(data.get('seconds', 0) or 0)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'bad_value'}
        return np.control(str(data.get('action', '')), str(data.get('id', '')), sec)
    return {'ok': False, 'error': 'bad_op'}


def calendar(data: dict) -> dict:
    """Calendar screen (see calendar): op `state` | `events` {from, to} | `search` {q} | `quick` {text, date} | `add` {title, date, time, end_date, end_time, all_day, repeat, interval, weekdays, until, location, notes, color, remind} |
    `update` {eid, ...same fields} | `update_one` {eid, occ, ...fields} (one occurrence of a repeating event) | `reset_one` {eid, occ} | `delete` {eid, only_date} | `add_source` {ref, name} | `caldav_find` {server, user, password} | `caldav_add` {server, user, password, calendars} | `import_file` | `remove_source` {ref} | `source_set` {ref, name, color, hidden} | `remind` {enabled, minutes} | `refresh`."""
    from . import calendar as cal
    op = str(data.get('op', 'state'))
    if op == 'state':
        return {'ok': True, **cal.get_state()}
    if op == 'events':
        return cal.list_events(str(data.get('from', '')), str(data.get('to', '')))
    if op == 'search':
        return cal.search(data.get('q', ''))
    if op == 'quick':
        return cal.quick(data.get('text', ''), str(data.get('date', '')))
    if op == 'add':
        return cal.add_event(data)
    if op == 'update':
        return cal.update_event(str(data.get('eid', '')), data)
    if op == 'update_one':
        return cal.update_occurrence(str(data.get('eid', '')), str(data.get('occ', '')), data)
    if op == 'reset_one':
        return cal.reset_occurrence(str(data.get('eid', '')), str(data.get('occ', '')))
    if op == 'delete':
        return cal.delete_event(str(data.get('eid', '')), str(data.get('only_date', '')), str(data.get('src', '')), str(data.get('href', '')))
    if op == 'add_source':
        return cal.add_source(data.get('ref'), data.get('name', ''))
    if op == 'caldav_find':
        return cal.caldav_find(data.get('server'), data.get('user'), data.get('password'))
    if op == 'caldav_add':
        return cal.caldav_add(data.get('server'), data.get('user'), data.get('password'), data.get('calendars'))
    if op == 'import_file':
        return cal.import_file()
    if op == 'remove_source':
        return cal.remove_source(data.get('ref'))
    if op == 'source_set':
        return cal.source_set(data.get('ref'), data.get('name'), data.get('color'), data.get('hidden'))
    if op == 'remind':
        return cal.set_reminders(data.get('enabled'), data.get('minutes'))
    if op == 'refresh':
        cal.refresh()
        return {'ok': True}
    return {'ok': False, 'error': 'bad_op'}


def song_open(data: dict) -> dict:
    """Opens a recognized song on a streaming service in the default browser (the URL comes from the stored entry)."""
    import webbrowser
    from . import songs
    entry = songs.find(str(data.get('id', '')))
    url = songs.link(entry, str(data.get('service', ''))) if entry else ''
    if not url:
        return {'ok': False, 'error': 'no_link'}
    return {'ok': bool(webbrowser.open(url))}


def song_clear(data: dict) -> dict:
    from actions import song_cache
    from . import publish, songs
    song_cache.clear()
    songs.publish_songs(publish)
    return {'ok': True}


def answer(data: dict) -> dict:
    """The answer card: op `close` (the user dismissed it)."""
    from . import answer
    if data.get('op') == 'close':
        answer.close()
        return {'ok': True}
    return {'ok': False, 'error': 'bad_op'}


def open_url(data: dict) -> dict:
    from . import mail as ml
    return ml.open_url(data.get('url'))
