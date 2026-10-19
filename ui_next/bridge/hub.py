"""Local push channel from the Python core to the new UI (Server-Sent Events, stdlib only).

The UI process (Tauri window) connects to ``/events`` on 127.0.0.1 and receives one
SSE event per published topic. New clients first get the last value of every topic,
so a late-started window shows the current state at once.

Security: loopback only, a random per-run token in the query string, Host and Origin
checks (a web page in a browser cannot read the stream: DNS rebinding and cross-site
requests are rejected).
"""
from __future__ import annotations

import hmac
import json
import os
import queue
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse
from core.safe import swallow as _swallow

ALLOWED_ORIGINS = {'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'}
_PING_SEC = 15.0
_CLIENT_QUEUE = 256
_MAX_CLIENTS = 16         # open event streams: the windows plus streams of reloaded pages that are not yet noticed as closed


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # a window closed mid-request is normal; do not print its traceback to the core's console
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


class Hub:
    def __init__(self) -> None:
        self.token = secrets.token_urlsafe(18)
        self.port = 0
        self._lock = threading.Lock()
        self._clients: set[queue.Queue] = set()
        self._last: dict[str, str] = {}
        self._server: ThreadingHTTPServer | None = None
        self.command_handler = None   # callable(cmd: str, data: dict) -> dict | None, set by the bridge

    # ---- publishing ------------------------------------------------------
    def publish(self, topic: str, payload: Any, *, sticky: bool = True) -> None:
        """Send one event to every client. ``sticky`` keeps it as the topic's last value for new clients."""
        msg = f'event: {topic}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n'
        with self._lock:
            if sticky:
                self._last[topic] = msg
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:  # slow reader: drop its oldest message instead of blocking the core
                    q.get_nowait()
                    q.put_nowait(msg)
                except Exception:
                    _swallow()

    def _subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=_CLIENT_QUEUE)
        with self._lock:
            for msg in self._last.values():
                q.put_nowait(msg)
            self._clients.add(q)
        return q

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def has_clients(self) -> bool:
        with self._lock:
            return bool(self._clients)

    def _unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._clients.discard(q)

    # ---- server ----------------------------------------------------------
    def start(self) -> int:
        if self._server is not None:
            return self.port
        hub = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            timeout = 60   # a client that stalls mid-request is dropped instead of holding a thread

            def log_message(self, *args):  # silence the default stderr logging
                pass

            def _authorized(self) -> str | None:
                """Returns the Origin to echo (or '' for no Origin), None when the request is rejected."""
                host = (self.headers.get('Host') or '').lower()
                if host not in (f'127.0.0.1:{hub.port}', f'localhost:{hub.port}'):
                    return None
                origin = self.headers.get('Origin') or ''
                if origin and origin not in ALLOWED_ORIGINS:
                    return None
                got = (parse_qs(urlparse(self.path).query).get('token') or [''])[0]
                if not hmac.compare_digest(got, hub.token):
                    return None
                return origin

            def _reply_json(self, code: int, body: dict, origin: str = '') -> None:
                raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(raw)))
                if origin:
                    self.send_header('Access-Control-Allow-Origin', origin)
                self.end_headers()
                self.wfile.write(raw)

            def do_OPTIONS(self):   # CORS preflight for POST /cmd
                origin = self._authorized()
                if origin is None:
                    self.send_error(403)
                    return
                self.send_response(204)
                if origin:
                    self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Access-Control-Allow-Methods', 'POST')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_POST(self):
                """UI -> core command: body {"cmd": name, ...}; only commands registered by the bridge run."""
                origin = self._authorized()
                if origin is None:
                    self.send_error(403)
                    return
                if urlparse(self.path).path != '/cmd':
                    self.send_error(404)
                    return
                try:
                    n = int(self.headers.get('Content-Length') or 0)
                    if not 0 < n <= 400_000:
                        raise ValueError('bad length')
                    data = json.loads(self.rfile.read(n).decode('utf-8'))
                    cmd = str(data.pop('cmd'))
                except (ValueError, KeyError, TypeError, AttributeError):
                    self._reply_json(400, {'ok': False, 'error': 'bad request'}, origin)
                    return
                handler = hub.command_handler
                try:
                    result = handler(cmd, data) if handler else None
                except Exception as e:   # a failing command must not take the server down
                    self._reply_json(500, {'ok': False, 'error': type(e).__name__}, origin)
                    return
                if result is None:
                    self._reply_json(404, {'ok': False, 'error': 'unknown command'}, origin)
                else:
                    self._reply_json(200, result, origin)

            def do_GET(self):
                origin = self._authorized()
                if origin is None:
                    self.send_error(403)
                    return
                if urlparse(self.path).path != '/events':
                    self.send_error(404)
                    return
                if hub.client_count() >= _MAX_CLIENTS:
                    self.send_error(429)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                if origin:
                    self.send_header('Access-Control-Allow-Origin', origin)
                self.end_headers()
                q = hub._subscribe()
                try:
                    self.wfile.write(b': connected\n\n')
                    self.wfile.flush()
                    while True:
                        try:
                            msg = q.get(timeout=_PING_SEC)
                        except queue.Empty:
                            msg = ': ping\n\n'
                        self.wfile.write(msg.encode('utf-8'))
                        self.wfile.flush()
                except (OSError, ValueError):
                    pass
                finally:
                    hub._unsubscribe(q)

        srv = _Server(('127.0.0.1', 0), Handler)
        self._server = srv
        self.port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, name='ui-bridge-http', daemon=True).start()
        return self.port

    def stop(self) -> None:
        srv, self._server = self._server, None
        if srv is not None:
            srv.shutdown()
            srv.server_close()

    # ---- discovery file read by the UI shell ------------------------------
    def info_path(self) -> str:
        base = os.environ.get('APPDATA') or os.environ.get('LOCALAPPDATA') or os.getcwd()
        return os.path.join(base, 'Jarvis', 'ui_bridge.json')

    def write_info(self) -> str:
        path = self.info_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'port': self.port, 'token': self.token, 'pid': os.getpid()}, f)
        return path

    def remove_info(self) -> None:
        try:
            os.remove(self.info_path())
        except OSError:
            pass
