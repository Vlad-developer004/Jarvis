// Interface sounds, synthesised with Web Audio (no files): clicks, switch on/off, screen change, hover tick, toast chime.
// Soft by design (master gain 0.3, sine bodies with a little noise for taps), created on the first user gesture, off-switch in the theme menu (localStorage "jarvisSfx").
// Costs nothing while idle: oscillators exist only for the tens of milliseconds a sound lasts.
(() => {
  let on = true;
  try { on = localStorage.getItem('jarvisSfx') !== '0'; } catch (e) {}
  let ctx = null, master = null;
  let MASTER = 0.3; const last = {};
  try { const v = parseFloat(localStorage.getItem('jarvisSfxVol')); if (v >= 0.05 && v <= 0.6) MASTER = v; } catch (e) {}

  function audio() {
    if (!ctx) {
      try {
        ctx = new (window.AudioContext || window.webkitAudioContext)();
        master = ctx.createGain(); master.gain.value = MASTER; master.connect(ctx.destination);
      } catch (e) { return null; }
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});
    return ctx;
  }

  // one tone: frequency glide f -> f2, soft attack, exponential decay, optional low-pass; `parts` adds partials [ratio, weight] for a rounder, bell-like body
  function tone(a, { f = 880, f2 = 0, t = 0.06, type = 'sine', v = 0.6, at = 0, lp = 0, atk = 0.004, parts = null }) {
    const t0 = a.currentTime + at, g = a.createGain();
    g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(v, t0 + atk); g.gain.exponentialRampToValueAtTime(0.0001, t0 + t);
    let out = g;
    if (lp) { const b = a.createBiquadFilter(); b.type = 'lowpass'; b.frequency.value = lp; g.connect(b); out = b; }
    out.connect(master);
    for (const [r, w] of parts || [[1, 1]]) {
      const o = a.createOscillator(), og = a.createGain(); og.gain.value = w; o.type = type; o.frequency.setValueAtTime(f * r, t0);
      if (f2) o.frequency.exponentialRampToValueAtTime(f2 * r, t0 + t);
      o.connect(og); og.connect(g); o.start(t0); o.stop(t0 + t + 0.03);
    }
  }
  // a band-passed noise burst (the "tap" of a key, the "air" of a swipe); bp2 sweeps the band
  let nbuf = null;
  function noise(a, { t = 0.03, v = 0.3, at = 0, bp = 2000, bp2 = 0, q = 1, atk = 0.002 }) {
    if (!nbuf) { nbuf = a.createBuffer(1, Math.floor(a.sampleRate * 0.4), a.sampleRate); const d = nbuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; }
    const t0 = a.currentTime + at, src = a.createBufferSource(), b = a.createBiquadFilter(), g = a.createGain();
    src.buffer = nbuf; b.type = 'bandpass'; b.Q.value = q; b.frequency.setValueAtTime(bp, t0); if (bp2) b.frequency.exponentialRampToValueAtTime(bp2, t0 + t);
    g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(v, t0 + atk); g.gain.exponentialRampToValueAtTime(0.0001, t0 + t);
    src.connect(b); b.connect(g); g.connect(master); src.start(t0, Math.random() * 0.2); src.stop(t0 + t + 0.03);
  }

  const BELL = [[1, 1], [2.76, 0.12], [4, 0.05]], SOFT = [[1, 1], [2, 0.22]];
  const SOUNDS = {
    click: [{ n: 1, bp: 2600, q: 0.9, t: 0.022, v: 0.3 }, { f: 260, f2: 150, t: 0.05, v: 0.4 }],
    hover: [{ f: 2400, t: 0.01, v: 0.035 }],
    on: [{ f: 523.25, t: 0.16, v: 0.38, parts: SOFT }, { f: 783.99, t: 0.24, v: 0.38, at: 0.07, parts: SOFT }],
    off: [{ f: 783.99, t: 0.14, v: 0.32, parts: SOFT }, { f: 523.25, t: 0.22, v: 0.32, at: 0.07, parts: SOFT }],
    nav: [{ n: 1, bp: 700, bp2: 2200, q: 0.7, t: 0.09, v: 0.22, atk: 0.02 }, { f: 330, f2: 440, t: 0.07, v: 0.16 }],
    ok: [{ f: 659.25, t: 0.38, v: 0.32, parts: BELL }, { f: 987.77, t: 0.5, v: 0.3, at: 0.09, parts: BELL }],
    err: [{ f: 196, f2: 150, t: 0.18, type: 'triangle', v: 0.4, lp: 700 }, { f: 174.6, f2: 130, t: 0.24, type: 'triangle', v: 0.4, lp: 700, at: 0.13 }],
    send: [{ n: 1, bp: 500, bp2: 3500, q: 0.6, t: 0.18, v: 0.28, atk: 0.04 }, { f: 659.25, t: 0.28, v: 0.28, at: 0.12, parts: BELL }, { f: 987.77, t: 0.4, v: 0.26, at: 0.2, parts: BELL }],
  };
  const GAP = { hover: 90, click: 30, nav: 60, on: 40, off: 40, ok: 150, err: 150, send: 300 };

  function play(name) {
    if (!on || document.hidden) return;
    const now = performance.now();
    if (now - (last[name] || 0) < (GAP[name] || 40)) return;
    last[name] = now;
    const a = audio(); if (!a || !SOUNDS[name]) return;
    for (const s of SOUNDS[name]) (s.n ? noise : tone)(a, s);
  }
  window.sfx = play;
  /* for the appearance screen: read or set the on/off state and the master volume */
  window.sfxOn = (v) => {
    if (v === undefined) return on;
    on = !!v; const s = document.getElementById('sfxsw'); if (s) { s.classList.toggle('on', on); s.setAttribute('aria-pressed', on); }
    try { localStorage.setItem('jarvisSfx', on ? '1' : '0'); } catch (x) {}
    return on;
  };
  window.sfxVolume = (v) => {
    if (v === undefined) return MASTER;
    MASTER = Math.max(0.05, Math.min(0.6, +v)); if (master) master.gain.value = MASTER;
    try { localStorage.setItem('jarvisSfxVol', String(MASTER)); } catch (x) {}
    return MASTER;
  };

  const KEYS = '.cm-try, .rm-chip, .cm-sug button, .btn, .ib, .cm-cat, .swb, #mic, .mswb, .ex-badge, .rm-x';
  document.addEventListener('pointerdown', (e) => {
    const t = e.target.closest && e.target.closest(KEYS + ', .ni');
    if (!t || t.disabled) return;
    play(t.matches('.ni') ? 'nav' : 'click');
  }, { passive: true });

  document.addEventListener('click', (e) => {
    const s = e.target.closest && e.target.closest('.tgl, .gmode');
    if (s) setTimeout(() => play(s.classList.contains('on') ? 'on' : 'off'), 0);
  });

  document.addEventListener('pointerover', (e) => {
    const t = e.target.closest && e.target.closest('.cm-card, .gm-g, .rm-item, .cm-try, .ni, .rm-chip');
    if (t && !(e.relatedTarget && t.contains(e.relatedTarget))) play('hover');
  }, { passive: true });

  // toast chime when any toast shows up
  const mo = new MutationObserver((list) => { for (const r of list) if (r.target.classList.contains('on') && !(r.oldValue || '').split(' ').includes('on')) play(/не удалось|ошибк|не получилось|слишком|нельзя|не найден/i.test(r.target.textContent) ? 'err' : 'ok'); });
  document.querySelectorAll('.cm-toast').forEach((t) => mo.observe(t, { attributes: true, attributeFilter: ['class'], attributeOldValue: true }));

  // off-switch in the theme menu
  const drop = document.getElementById('tdrop');
  if (drop) {
    drop.insertAdjacentHTML('beforeend', `<h4 style="margin-top:.8rem">Звук</h4><div class="sfxrow"><span>Звуки интерфейса</span><button class="tgl${on ? ' on' : ''}" id="sfxsw" aria-pressed="${on}" title="Включить или выключить звуки интерфейса"><span class="sw"><b>ВЫКЛ</b><b>ВКЛ</b></span></button></div>`);
    const sw = document.getElementById('sfxsw');
    sw.addEventListener('click', (e) => {
      on = !on; sw.classList.toggle('on', on); sw.setAttribute('aria-pressed', on);
      try { localStorage.setItem('jarvisSfx', on ? '1' : '0'); } catch (x) {}
    });
  }
})();
