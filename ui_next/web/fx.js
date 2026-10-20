// Polish layer (see fx.css): background field, screen entrance, pointer light, press feedback, number tweening.
// Cheap by design: one rAF-throttled pointer handler, short one-shot animations, nothing runs while the window is hidden.
(() => {
  const root = document.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const setLite = (on) => { root.dataset.fx = on ? 'lite' : 'full'; };
  const pref = (() => { try { return localStorage.getItem('jarvisFx'); } catch (e) { return null; } })();   // 'full' | 'lite' | null = decide from the system
  setLite(pref === 'lite' || (pref !== 'full' && (reduce || /[?&]lite\b/.test(location.search))));
  if (window.__TAURI__) window.__TAURI__.core.invoke('get_quality').then((q) => { if (q === 'lite' && pref !== 'full') setLite(true); }).catch(() => {});
  window.fzDebug = (q) => { const m = /nx=([a-z,]+)/.exec(q || ''); if (m) m[1].split(',').forEach((k) => { root.classList.add('nx-' + k); (window.NX ||= new Set()).add(k); if ((k === 'idle' || k === 'speak') && typeof J !== 'undefined') J.setState(k === 'idle' ? 'IDLE' : 'SPEAKING'); }); };
  if (window.__TAURI__) window.__TAURI__.core.invoke('get_quality').then(window.fzDebug).catch(() => {});
  const lite = () => root.dataset.fx === 'lite';

  // gate switches: both words are always visible, the CSS lights the active one
  document.querySelectorAll('.tgl .sw, .gmode .sw').forEach((s) => { if (!s.firstChild) s.innerHTML = '<b>ВЫКЛ</b><b>ВКЛ</b>'; });

  // Ctrl+Shift+D shows the debug line (window size, zoom)
  document.addEventListener('keydown', (e) => { if (e.ctrlKey && e.shiftKey && (e.key === 'D' || e.key === 'd')) root.classList.toggle('dbg'); });

  // background field
  const app = document.getElementById('app');
  if (app) app.insertAdjacentHTML('afterbegin', '<div id="fzbg" aria-hidden="true"><i class="a"></i><i class="b"></i><svg class="r" viewBox="-100 -100 200 200"><circle r="96"/><circle r="78" stroke-dasharray="2 5"/><circle r="58"/><path d="M-96 0H96M0 -96V96" stroke-dasharray="1 6"/><path d="M0 -96A96 96 0 0 1 82 -50" stroke-width="2.4"/></svg></div>');
  document.querySelectorAll('.panel').forEach((p) => p.insertAdjacentHTML('beforeend', '<i class="fz-rule" aria-hidden="true"></i>'));
  document.addEventListener('visibilitychange', () => root.classList.toggle('fz-paused', document.hidden));

  // number tween: counts from the shown value to the new one (ease-out, 450 ms)
  const tweens = new WeakMap();
  window.fzNum = (el, to, suffix = '') => {
    const put = (v) => { el.innerHTML = Math.round(v) + suffix; };
    const from = Number.isFinite(el._fzv) ? el._fzv : to;
    el._fzv = to;
    cancelAnimationFrame(tweens.get(el));
    if (lite() || document.hidden || Math.abs(to - from) < 4 || root.dataset.st === 'IDLE' || !el.offsetParent) { put(to); return; }   // calm, small moves and values on another screen are set at once: a tween costs a layout per frame
    const t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / 450), e = 1 - Math.pow(1 - k, 3); put(from + (to - from) * e); if (k < 1) tweens.set(el, requestAnimationFrame(step)); };
    tweens.set(el, requestAnimationFrame(step));
  };

  // heading decode: random glyphs resolve into the real title, once per screen entrance
  const GL = '01<>/\\#%&=+*';
  function decode(el) {
    if (!el || lite()) return;
    const text = el.dataset.fzText || (el.dataset.fzText = el.textContent);
    let n = 0; const total = 12;
    const id = setInterval(() => {
      n++; const keep = Math.floor(text.length * n / total);
      el.textContent = text.slice(0, keep) + [...text.slice(keep)].map((c) => (c === ' ' ? ' ' : GL[Math.floor(Math.random() * GL.length)])).join('');
      if (n >= total) { clearInterval(id); el.textContent = text; }
    }, 30);
  }

  // screen entrance: wrap showView so every non-dashboard screen reveals itself
  const SECTION = { commands: 'cmds', rems: 'rems', games: 'games', exts: 'exts', songs: 'songs', voice: 'voice', mail: 'mail', calendar: 'calpage' };
  const wrap = () => {
    if (typeof window.showView !== 'function' || window.showView.fz) return;
    const orig = window.showView;
    const patched = function (v) {
      const r = orig.apply(this, arguments);
      const sec = document.getElementById(SECTION[v]);
      if (sec && !lite()) {
        requestAnimationFrame(() => {
          sec.querySelectorAll('.cm-card, .gm-g, .rm-item, .cm-cat, .cm-sec h3').forEach((e, i) => e.style.setProperty('--i', Math.min(i, 14)));
          sec.classList.remove('fz-in'); void sec.offsetWidth; sec.classList.add('fz-in');
          clearTimeout(sec._fzt); sec._fzt = setTimeout(() => sec.classList.remove('fz-in'), 1400);
          decode(sec.querySelector('h2'));
        });
      }
      return r;
    };
    patched.fz = true;
    window.showView = patched;
  };
  wrap();

  // background parallax: the pointer position (-1..1) shifts the light fields; the CSS transition eases it, so nothing runs when the pointer rests
  const bg = document.getElementById('fzbg');
  let praf = 0, px = 0, py = 0;
  document.addEventListener('pointermove', (e) => {
    if (lite() || !bg) return;
    px = e.clientX / innerWidth * 2 - 1; py = e.clientY / innerHeight * 2 - 1;
    if (!praf) praf = requestAnimationFrame(() => { praf = 0; bg.style.setProperty('--px', px.toFixed(3)); bg.style.setProperty('--py', py.toFixed(3)); });
  }, { passive: true });

  // pointer light: write the pointer position into the hovered card (one rAF per frame)
  let raf = 0, last = null;
  document.addEventListener('pointermove', (e) => {
    if (lite()) return;
    const el = e.target.closest && e.target.closest('.cm-card, .gm-g, .rm-item');
    if (!el) return;
    last = [el, e.clientX, e.clientY];
    if (!raf) raf = requestAnimationFrame(() => { raf = 0; const [t, x, y] = last, r = t.getBoundingClientRect(); t.style.setProperty('--mx', (x - r.left) + 'px'); t.style.setProperty('--my', (y - r.top) + 'px'); });
  }, { passive: true });

  // press feedback: a quick brightness flash on buttons, a halo on switches
  document.addEventListener('pointerdown', (e) => {
    if (lite()) return;
    const b = e.target.closest && e.target.closest('.cm-try, .rm-chip, .cm-sug button, .btn');
    if (b) { b.classList.remove('fz-zap'); void b.offsetWidth; b.classList.add('fz-zap'); setTimeout(() => b.classList.remove('fz-zap'), 300); }
  }, { passive: true });
  document.addEventListener('click', (e) => {
    if (lite()) return;
    const s = e.target.closest && e.target.closest('.tgl, .gmode');
    if (s) { s.classList.remove('fz-flip'); void s.offsetWidth; setTimeout(() => { s.classList.add('fz-flip'); setTimeout(() => s.classList.remove('fz-flip'), 520); }, 0); }
  });
})();
