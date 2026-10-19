"""Where does the page spend its time? Launches the shell with WebView2 remote debugging and diffs Performance.getMetrics
over a window, so script / style / layout / paint time can be told apart.

Usage: cdp_profile.py --secs 15 -- <exe>     (JARVIS_PAGE / JARVIS_Q go through the environment)
Optional: --eval "js" runs a snippet in the page before measuring (e.g. to switch a view).
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request

import websocket

PORT = 9333


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=int, default=15)
    ap.add_argument('--warmup', type=int, default=10)
    ap.add_argument('--eval', default='')
    ap.add_argument('--profile', action='store_true', help='also print the top self-time JS functions')
    ap.add_argument('cmd', nargs='*')
    a = ap.parse_args()
    env = dict(os.environ, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=f'--remote-debugging-port={PORT} --remote-allow-origins=http://127.0.0.1:{PORT}')
    proc = subprocess.Popen(a.cmd, env=env)
    try:
        time.sleep(a.warmup)
        tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json', timeout=5))
        page = next(t for t in tabs if t.get('type') == 'page')
        ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=10)
        n = 0

        def call(method, **params):
            nonlocal n
            n += 1
            ws.send(json.dumps({'id': n, 'method': method, 'params': params}))
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == n:
                    return r.get('result', {})
        call('Performance.enable')
        if a.eval:
            r = call('Runtime.evaluate', expression=a.eval, returnByValue=True)
            print('eval ->', json.dumps(r.get('result', {}).get('value'), ensure_ascii=False)[:1500])
            time.sleep(2)

        def metrics():
            return {m['name']: m['value'] for m in call('Performance.getMetrics')['metrics']}
        if a.profile:
            call('Profiler.enable')
            call('Profiler.start')
        m0, t0 = metrics(), time.time()
        time.sleep(a.secs)
        m1, t1 = metrics(), time.time()
        prof = call('Profiler.stop')['profile'] if a.profile else None
        dt = t1 - t0
        print(f'window {dt:.1f}s')
        for k in ('TaskDuration', 'ScriptDuration', 'LayoutDuration', 'RecalcStyleDuration', 'LayoutCount', 'RecalcStyleCount', 'JSEventListeners'):
            d = m1.get(k, 0) - m0.get(k, 0)
            if k.endswith('Duration'):
                print(f'{k:22s} {d / dt * 100:6.2f} % of one core   ({d * 1000:.0f} ms)')
            else:
                print(f'{k:22s} {d / dt:6.1f} per second')
        if prof:
            nodes = {n['id']: n for n in prof['nodes']}
            self_us = {}
            for nid, delta in zip(prof['samples'], prof['timeDeltas']):
                cf = nodes[nid]['callFrame']
                key = f"{cf['functionName'] or '(anon)'} {cf['url'].rsplit('/', 1)[-1]}:{cf['lineNumber'] + 1}"
                self_us[key] = self_us.get(key, 0) + delta
            total = sum(self_us.values()) or 1
            print('--- top self time (share of sampled time; idle excluded) ---')
            for k, v in sorted(self_us.items(), key=lambda kv: -kv[1])[:14]:
                if k.startswith('(idle)'):
                    continue
                print(f'{v / dt / 1e4:6.2f} % of one core  {k}')
    finally:
        os.system(f'taskkill /F /T /PID {proc.pid} >nul 2>&1')


if __name__ == '__main__':
    main()
