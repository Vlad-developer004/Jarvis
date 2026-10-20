"""User scenarios: one spoken phrase runs a list of ordinary voice commands ("режим работы" -> open the editor, lower the volume, ...).

Stored in jarvis_settings.json under `scenarios`: [{name, phrase, steps: [spoken command, ...]}]. Each step is parsed like a phrase the user said,
so any command that works by voice works as a step; a step "пауза N" waits N seconds (at most 10)."""
from __future__ import annotations

import re
import threading
import time

from core import settings_io
from core.safe import swallow as _swallow

MAX_SCENARIOS = 20
MAX_STEPS = 12
_PAUSE_RE = re.compile(r'^пауза\s+(\d{1,2})$')
_WAKE_WORDS = re.compile(r'\b(?:джарвис|jarvis|жарвис)\w*\b')
FUZZY = 0.9


class ScenarioError(ValueError):
    """`code` is a short machine-readable reason (required, too_many, exists, bad_steps)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _norm(text: str) -> str:
    t = _WAKE_WORDS.sub(' ', str(text).lower().replace('ё', 'е'))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', ' ', t)).strip()


def load() -> list[dict]:
    out = []
    for s in settings_io.read().get('scenarios', []):
        if isinstance(s, dict) and s.get('name') and s.get('phrase') and isinstance(s.get('steps'), list):
            out.append({'name': str(s['name']), 'phrase': str(s['phrase']), 'steps': [str(x) for x in s['steps']]})
    return out


def clean(name, phrase, steps) -> dict:
    """The validated scenario for the given fields; raises ScenarioError."""
    name, phrase = str(name or '').strip()[:40], str(phrase or '').strip()[:60]
    if isinstance(steps, str):
        steps = steps.splitlines()
    steps = [str(x).strip()[:120] for x in (steps or []) if str(x).strip()]
    if not name or not phrase:
        raise ScenarioError('required')
    if not steps or len(steps) > MAX_STEPS:
        raise ScenarioError('bad_steps')
    return {'name': name, 'phrase': phrase, 'steps': steps}


def save(old: str, name, phrase, steps) -> list[dict]:
    """Adds a scenario, or replaces the one called `old`. Names and phrases are unique."""
    sc = clean(name, phrase, steps)
    items = [s for s in load() if s['name'] != old]
    if any(s['name'].lower() == sc['name'].lower() or _norm(s['phrase']) == _norm(sc['phrase']) for s in items):
        raise ScenarioError('exists')
    if len(items) >= MAX_SCENARIOS:
        raise ScenarioError('too_many')
    items.append(sc)
    if not settings_io.update({'scenarios': items}):
        raise ScenarioError('write_failed')
    return items


def delete(name: str) -> list[dict]:
    items = [s for s in load() if s['name'] != name]
    if not settings_io.update({'scenarios': items}):
        raise ScenarioError('write_failed')
    return items


def match(text: str) -> dict | None:
    """The scenario the utterance asks for: the whole phrase, said alone or with a few extra words ("включи режим работы"), or a close match."""
    t = _norm(text)
    if not t:
        return None
    best, best_len = None, 0
    for s in load():
        p = _norm(s['phrase'])
        if not p:
            continue
        if t == p:
            return s
        if re.search(rf'(?<!\w){re.escape(p)}(?!\w)', t) and len(t) <= len(p) + 16 and len(p) > best_len:
            best, best_len = s, len(p)
    if best:
        return best
    try:
        from rapidfuzz import fuzz
        scored = [(fuzz.ratio(t, _norm(s['phrase'])) / 100.0, s) for s in load()]
        score, s = max(scored, key=lambda x: x[0], default=(0.0, None))
        return s if s and score >= FUZZY else None
    except ImportError:
        return None


def run(handler, scenario: dict, parse) -> None:
    """Runs the steps in order on a background thread; `parse` turns a phrase into [(command, segment)] (the recognizer's own parser)."""
    def _go():
        steps = scenario['steps']
        handler.silent_mode = len(steps) > 1
        try:
            for step in steps:
                pause = _PAUSE_RE.match(_norm(step))
                if pause:
                    time.sleep(min(10, int(pause.group(1))))
                    continue
                for cmd, seg in parse(step):
                    if cmd not in ('wake', 'reported_speech'):
                        handler.handle(cmd, seg)
                time.sleep(0.1)
        except Exception:
            _swallow()
        finally:
            if handler.silent_mode:
                handler.silent_mode = False
                handler.play_response('confirm', override_silent=True)
    threading.Thread(target=_go, name='scenario', daemon=True).start()
