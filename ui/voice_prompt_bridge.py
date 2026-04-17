from __future__ import annotations
import re
import threading
from typing import Callable, Iterable, Optional
_lock = threading.Lock()
_reg: Optional[dict] = None
def register_voice_prompt(
    root,
    *,
    on_confirm: Callable[[], None],
    on_cancel: Callable[[], None],
    confirm_phrases: Iterable[str] | None = None,
    cancel_phrases: Iterable[str] | None = None,
) -> None:
    global _reg
    c = tuple(
        p.lower().strip()
        for p in (confirm_phrases or ())
        if isinstance(p, str) and p.strip()
    )
    z = tuple(
        p.lower().strip()
        for p in (cancel_phrases or ())
        if isinstance(p, str) and p.strip()
    )
    with _lock:
        _reg = {
            'root': root,
            'on_confirm': on_confirm,
            'on_cancel': on_cancel,
            'confirm': c,
            'cancel': z,
        }
def unregister_voice_prompt(root) -> None:
    global _reg
    with _lock:
        if _reg is not None and _reg.get('root') is root:
            _reg = None
def try_consume_voice_prompt(text: str) -> bool:
    if not text or not text.strip():
        return False
    t = text.lower().strip()
    with _lock:
        reg = _reg
    if reg is None:
        return False
    def _hit(phrases: tuple[str, ...]) -> bool:
        words = set(re.findall(r"[0-9a-zа-яёіїєґ'-]+", t, re.I))
        words_l = {w.lower() for w in words}
        for p in phrases:
            if not p:
                continue
            if ' ' in p:
                if p in t:
                    return True
            else:
                if p in words_l or p == t:
                    return True
        return False
    action = None
    if _hit(reg['confirm']):
        action = 'confirm'
    elif _hit(reg['cancel']):
        action = 'cancel'
    else:
        return False
    root = reg['root']
    on_confirm: Callable[[], None] = reg['on_confirm']
    on_cancel: Callable[[], None] = reg['on_cancel']
    def _run():
        try:
            if not root.winfo_exists():
                unregister_voice_prompt(root)
                return
            if action == 'confirm':
                on_confirm()
            else:
                on_cancel()
        except Exception:
            pass
    try:
        root.after(0, _run)
    except Exception:
        try:
            _run()
        except Exception:
            pass
    return True
