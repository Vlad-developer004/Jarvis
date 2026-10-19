"""First-run wizard of the new UI: only remembers whether it was finished. The steps themselves use the voice, modules and ai commands.

`ui_wizard_done` in jarvis_settings.json (through core.settings_io). Finishing also sets `first_run_done`, the flag of the old window's welcome dialog, so that one does not show up afterwards.
"""
from __future__ import annotations

from core import settings_io

KEY = 'ui_wizard_done'


def state() -> dict:
    s = settings_io.read()
    return {'ok': True, 'done': bool(s.get(KEY)), 'old_welcome_done': bool(s.get('first_run_done'))}


def run(data: dict) -> dict:
    """op `state` | `done` | `reset` (show the wizard again on the next start)."""
    op = str(data.get('op', 'state'))
    if op == 'state':
        return state()
    if op == 'done':
        return {**state(), 'ok': settings_io.update({KEY: True, 'first_run_done': True})} | {'done': True}
    if op == 'reset':
        return {**state(), 'ok': settings_io.update({KEY: False})} | {'done': False}
    return {'ok': False, 'error': 'bad_op'}
