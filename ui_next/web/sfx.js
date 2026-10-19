// Interface sounds, synthesised with Web Audio (no files): clicks, switch on/off, screen change, hover tick, toast chime.
// Quiet by design (master gain 0.2), created on the first user gesture, off-switch in the theme menu (localStorage "jarvisSfx").
// Costs nothing while idle: oscillators exist only for the tens of milliseconds a sound lasts.
(() => {
  let on = true;
  try { on = localStorage.getItem('jarvisSfx') !== '0'; } catch (e) {}
  let ctx = null, master = null;
  let MASTER = 0.2; const last = {};
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

  // one tone: frequency glide f -> f2, short attack, exponential decay, optional low-pass
  function tone(a, { f = 880, f2 = 0, t = 0.06, type = 'sine', v = 0.6, at = 0, lp = 0 }) {
    const o = a.createOscillator(), g = a.createGain(), t0 = a.currentTime + at;
    o.type = type; o.frequency.setValueAtTime(f, t0);
    if (f2) o.frequency.exponentialRampToValueAtTime(f2, t0 + t);
    g.gain.setValueAtTime(0.0001, t0); g.gain.linearRampToValueAtTime(v, t0 + 0.004); g.gain.exponentialRampToValueAtTime(0.0001, t0 + t);
    let out = g;
    if (lp) { const b = a.createBiquadFilter(); b.type = 'lowpass'; b.frequency.value = lp; g.connect(b); out = b; }
    o.connect(g); out.connect(master); o.start(t0); o.stop(t0 + t + 0.02);
  }

  const SOUNDS = {
    click: [{ f: 1900, f2: 1400, t: 0.035, type: 'triangle', v: 0.5 }],
    hover: [{ f: 3200, t: 0.012, v: 0.1 }],
    on: [{ f: 660, f2: 990, t: 0.09, type: 'triangle', v: 0.55 }, { f: 990, f2: 1480, t: 0.1, type: 'triangle', v: 0.5, at: 0.07 }],
    off: [{ f: 990, f2: 660, t: 0.09, type: 'triangle', v: 0.5 }, { f: 660, f2: 440, t: 0.1, type: 'triangle', v: 0.45, at: 0.07 }],
    nav: [{ f: 420, f2: 900, t: 0.11, type: 'sawtooth', v: 0.3, lp: 1800 }],
    ok: [{ f: 880, t: 0.07, type: 'triangle', v: 0.45 }, { f: 1320, t: 0.12, type: 'triangle', v: 0.45, at: 0.08 }],
    err: [{ f: 190, t: 0.14, type: 'square', v: 0.25, lp: 900 }, { f: 140, t: 0.16, type: 'square', v: 0.25, lp: 900, at: 0.12 }],
  };
  const GAP = { hover: 70, click: 30, nav: 60, on: 40, off: 40, ok: 150, err: 150 };

  function play(name) {
    if (!on || document.hidden) return;
    const now = performance.now();
    if (now - (last[name] || 0) < (GAP[name] || 40)) return;
    last[name] = now;
    const a = audio(); if (!a || !SOUNDS[name]) return;
    for (const s of SOUNDS[name]) tone(a, s);
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
  const mo = new MutationObserver((list) => { for (const r of list) if (r.target.classList.contains('on') && !(r.oldValue || '').split(' ').includes('on')) play('ok'); });
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
