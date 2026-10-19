"""What the assistant may ask the internet about itself.

Weather needs the place you are in, and "my IP address" needs a service that echoes it back. Both send your address to a third party,
so a setting (`allow_ip_lookup`, on by default, as before) can switch them off: the weather then works only with a city that was named
or a location Windows provides, and the IP command says it is disabled.
"""
from __future__ import annotations


def ip_lookup_allowed() -> bool:
    from core import settings_io
    return bool(settings_io.read().get('allow_ip_lookup', True))
