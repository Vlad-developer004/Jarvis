"""Opens every screen of the real window and reports Content-Security-Policy violations and console errors."""
import json
import os
import subprocess
import sys
import time
import urllib.request

import websocket


def main():
    exe = sys.argv[1]
    VIEWS = os.environ.get('VIEWS', 'dash,commands,rems,games,exts,songs,voice,mail,calendar,cinema,perf,look,ai,dev,tools').split(',')
    env = dict(os.environ, JARVIS_PAGE='app', JARVIS_SIZE='1280x720', WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS='--remote-debugging-port=9334 --remote-allow-origins=http://127.0.0.1:9334')
    os.system('taskkill /F /IM jarvis-ui.exe >nul 2>&1')
    p = subprocess.Popen([exe], env=env)
    try:
        time.sleep(9)
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9334/json'))
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'])
        ws.settimeout(0.5)
        n = [0]
        events = []

        def call(m, **a):
            n[0] += 1
            ws.send(json.dumps({'id': n[0], 'method': m, 'params': a}))
            while True:
                try:
                    r = json.loads(ws.recv())
                except websocket.WebSocketTimeoutException:
                    continue
                if r.get('id') == n[0]:
                    return r
                if 'method' in r:
                    events.append(r)

        def drain():
            try:
                while True:
                    events.append(json.loads(ws.recv()))
            except websocket.WebSocketTimeoutException:
                pass

        def ev(js):
            return call('Runtime.evaluate', expression=js, returnByValue=True)['result']['result'].get('value')

        call('Log.enable')
        call('Runtime.enable')
        call('Page.enable')
        ev("document.querySelector('.wz')?.remove()")
        for v in VIEWS:
            ev(f"typeof showView==='function' && showView('{v}')")
            time.sleep(1.2)
            drain()
        drain()
        print('bridge connected:', ev('J.model.connected'), '| tauri ipc:', ev("typeof window.__TAURI__ !== 'undefined' && !!window.__TAURI__.core"))
        import base64
        for v in ('commands', 'calendar'):
            ev(f"showView('{v}')"); time.sleep(1.5)
            open(r'C:/Users/tanja/AppData/Local/Temp/claude/c--Users-tanja-OneDrive-Desktop-projects-Jarvis/3c3930e2-44ea-468c-9306-3d3d0353c8a4/scratchpad/csp_{}.png'.format(v), 'wb').write(base64.b64decode(call('Page.captureScreenshot', format='png')['result']['data']))
        print('external fetch blocked:', ev("fetch('https://example.com/').then(()=>'ALLOWED').catch(()=>'blocked')") )
        time.sleep(1); drain()
        print('views visited:', ev("document.querySelector('.view.on, .view.active, [data-view].on') ? 'ok' : 'n/a'"))
        print('invoke works:', ev("window.__TAURI__.core.invoke('get_renderer').then(()=>'yes').catch(e=>'no:'+e)") if False else 'skipped')
        bad = []
        for e in events:
            m = e.get('method')
            if m == 'Log.entryAdded':
                en = e['params']['entry']
                if en['level'] in ('error', 'warning') or 'Content Security Policy' in en.get('text', ''):
                    bad.append(f"{en['source']}/{en['level']}: {en['text'][:220]} {en.get('url', '')[:80]}")
            elif m == 'Runtime.exceptionThrown':
                bad.append('exception: ' + json.dumps(e['params']['exceptionDetails'].get('exception', {}).get('description', ''))[:220])
            elif m == 'Runtime.consoleAPICalled' and e['params']['type'] in ('error', 'warning'):
                bad.append('console.' + e['params']['type'] + ': ' + ' '.join(str(a.get('value', a.get('description', ''))) for a in e['params']['args'])[:220])
        seen = set()
        for b in bad:
            if b not in seen:
                seen.add(b)
                print(b)
        print('events:', len(events), 'problems:', len(seen))
    finally:
        os.system(f'taskkill /F /T /PID {p.pid} >nul 2>&1')


if __name__ == '__main__':
    main()
