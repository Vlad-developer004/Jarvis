"""How hard does the window work while nothing happens? Starts the bridge and the window with a debugging port, traces a few seconds and prints
frames drawn, layouts and paints per second plus the CSS animations that really run.

    python tools/ui_frames.py [STATE] [seconds]        STATE: IDLE (default), LISTENING, SPEAKING

The page is expected to be calm in IDLE: a few frames a second (canvases at ~11 fps), no layout. Anything near the display rate (60-75/s) means an
animation of a layout property or a loop that never sleeps. Needs `pip install websocket-client`; the window must have been built (cargo build --release).
"""
import collections
import ctypes
import ctypes.wintypes
import json
import os
import subprocess
import sys
import time
import urllib.request

import psutil
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 9334


def front(pids):
    """Chromium does not draw a covered window, so measure with the window on top."""
    user32 = ctypes.windll.user32
    callback = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

    def each(hwnd, _):
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd) and user32.GetWindowTextLengthW(hwnd):
            user32.ShowWindow(hwnd, 9)
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)
            user32.SetForegroundWindow(hwnd)
        return True
    user32.EnumWindows(callback(each), 0)


def main():
    state = sys.argv[1] if len(sys.argv) > 1 else 'IDLE'
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    from ui_next import bridge, host
    exe = os.path.join(ROOT, 'ui_next', 'shell', 'src-tauri', 'target', 'release', 'jarvis-ui.exe')
    host.STATE.mode = state
    bridge.start(None)
    env = dict(os.environ, JARVIS_PAGE='app', JARVIS_SIZE='1280x720', JARVIS_Q='',
               WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=%d --remote-allow-origins=http://127.0.0.1:%d' % (PORT, PORT))
    proc = subprocess.Popen([exe], env=env, cwd=os.path.dirname(exe))
    try:
        time.sleep(12)
        front({proc.pid} | {c.pid for c in psutil.Process(proc.pid).children(recursive=True)})
        time.sleep(2)
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json' % PORT))
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'], suppress_origin=True)
        ws.settimeout(20)
        seq = [0]

        def call(method, **params):
            seq[0] += 1
            ws.send(json.dumps({'id': seq[0], 'method': method, 'params': params}))
            while True:
                reply = json.loads(ws.recv())
                if reply.get('id') == seq[0]:
                    return reply.get('result', {})

        events = []
        call('Tracing.start', traceConfig={'includedCategories': ['devtools.timeline', 'cc', 'viz', 'gpu', 'disabled-by-default-devtools.timeline.frame']})
        time.sleep(secs)
        seq[0] += 1
        ws.send(json.dumps({'id': seq[0], 'method': 'Tracing.end'}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('method') == 'Tracing.dataCollected':
                events.extend(msg['params']['value'])
            if msg.get('method') == 'Tracing.tracingComplete':
                break
        count = collections.Counter(e['name'] for e in events)
        print('state %s, %.0f s: DrawFrame %.1f/s  Layout %.1f/s  Paint %.1f/s  rAF callbacks %.1f/s' % (
            state, secs, count['DrawFrame'] / secs, count['Layout'] / secs, count['Paint'] / secs, count['FireAnimationFrame'] / secs))
        running = call('Runtime.evaluate', expression="JSON.stringify(document.getAnimations().filter(a => a.playState === 'running').map(a => a.animationName || a.transitionProperty))", returnByValue=True)
        print('animations running:', running.get('result', {}).get('value'))
    finally:
        proc.kill()
        sys.stdout.flush()
        os._exit(0)


if __name__ == '__main__':
    main()
