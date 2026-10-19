"""Feeds hostile text through every bridge payload and reports views where it lands in the DOM as markup (unescaped)."""
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
    WRAP = r"""
(() => {
  const P = '"\'><i data-xss=1></i><img data-xss=2 src=x>';
  const taint = (v) => typeof v === 'string' ? (v.length > 3 && !/^[A-Za-z0-9_.:\-\/#]+$/.test(v) ? v + P : v)
    : Array.isArray(v) ? v.map(taint) : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, taint(x)])) : v;
  const ael = EventSource.prototype.addEventListener;
  EventSource.prototype.addEventListener = function (t, fn, o) {
    return ael.call(this, t, (e) => { let d = e.data; try { d = JSON.stringify(taint(JSON.parse(e.data))); } catch (_) {} fn({ data: d, type: e.type }); }, o);
  };
  const of = window.fetch;
  window.fetch = async (u, opt) => {
    const r = await of(u, opt);
    if (!String(u).includes('/cmd')) return r;
    const txt = await r.text(); let b = txt; try { b = JSON.stringify(taint(JSON.parse(txt))); } catch (_) {}
    return new Response(b, { status: r.status, headers: r.headers });
  };
})();
"""
    try:
        time.sleep(9)
        tabs = json.load(urllib.request.urlopen('http://127.0.0.1:9334/json'))
        ws = websocket.create_connection(next(t for t in tabs if t['type'] == 'page')['webSocketDebuggerUrl'])
        ws.settimeout(1)
        n = [0]

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

        def ev(js):
            return call('Runtime.evaluate', expression=js, returnByValue=True)['result']['result'].get('value')

        call('Page.enable')
        call('Page.addScriptToEvaluateOnNewDocument', source=WRAP)
        call('Page.reload')
        time.sleep(9)
        ev("document.querySelector('.wz')?.remove()")
        print('tainted payload seen in model:', ev("JSON.stringify(J.model).includes('data-xss')"))
        found = {}
        for v in VIEWS:
            ev(f"typeof showView==='function' && showView('{v}')")
            time.sleep(2.0)
            hits = ev("""(() => Array.from(document.querySelectorAll('[data-xss]')).filter(e => !e.closest('#wxr')).slice(0, 12).map(e => (e.parentElement ? e.parentElement.outerHTML : e.outerHTML).slice(0, 260)))()""")
            if hits:
                found[v] = hits
        print('views with injected markup:', list(found))
        for v, hits in found.items():
            print('---', v)
            for h in hits:
                print('   ', h.replace('\n', ' '))
    finally:
        os.system(f'taskkill /F /T /PID {p.pid} >nul 2>&1')


if __name__ == '__main__':
    main()
