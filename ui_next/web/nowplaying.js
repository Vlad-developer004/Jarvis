// "Now playing": a capsule under the core on the overview (shown while something plays, or just after it was paused) and the shared helpers for the media screen.
// Data: the `nowplaying` topic from the core (Windows media sessions, see actions/now_playing.py); controls go through the `media` command.
// Relies on globals of app.html: $, J, m, esc.
(() => {
  const el = $('np'), root = document.documentElement;
  const fmt = (s) => { s = Math.max(0, Math.floor(s)); const h = Math.floor(s / 3600), mi = Math.floor(s % 3600 / 60), se = s % 60; return (h ? `${h}:${String(mi).padStart(2, '0')}` : String(mi)) + ':' + String(se).padStart(2, '0'); };
  const I = {
    prev: '<path d="M6 5v14M19 5v14L9 12z" />', next: '<path d="M18 5v14M5 5v14l10-7z" />', play: '<path d="M7 4.5v15l13-7.5z" />', pause: '<path d="M8 5v14M16 5v14" />',
    back: '<path d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5" />', fwd: '<path d="M21 12a9 9 0 1 1-3-6.7M21 4v5h-5" />' };
  const svg = (k, n = 18) => `<svg viewBox="0 0 24 24" width="${n}" height="${n}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${I[k]}</svg>`;
  let lastPlaying = 0, shownId = '';

  /* the session a command goes to: the one playing, else the one Windows calls current, else the first */
  const pickSession = (list) => list.find((s) => s.status === 'playing') || list.find((s) => s.current) || list[0] || null;
  const live = (s) => { const base = m.np && m.np.at ? m.np.at : Date.now(); return s.status === 'playing' ? Math.min(s.dur || 1e9, s.pos + (Date.now() - base) / 1000) : s.pos; };
  async function control(action, id, seconds) { if (!m.connected) return { ok: false, error: 'offline' }; return (await J.send('media', { op: 'control', action, id: id || '', seconds: seconds || 0 })) || { ok: false }; }

  function paint() {
    const list = (m.connected && m.np && m.np.sessions) || [];
    const s = pickSession(list);
    if (s && s.status === 'playing') lastPlaying = Date.now();
    const show = !!s && (s.status === 'playing' || Date.now() - lastPlaying < 120000);
    el.hidden = !show; if (show) root.dataset.np = '1'; else delete root.dataset.np;
    if (!show) { shownId = ''; return; }
    const playing = s.status === 'playing', sub = [s.artist, s.app_name].filter(Boolean).join(' · ');
    if (shownId !== s.id + s.title) {
      shownId = s.id + s.title;
      el.innerHTML = `<div class="np-top"><span class="np-eq" aria-hidden="true"><i></i><i></i><i></i></span><div class="np-t"><b id="np-title"></b><small id="np-sub"></small></div>`
        + `<div class="np-ctl"><button type="button" data-a="prev" title="Предыдущий">${svg('prev')}</button><button type="button" data-a="seek" data-s="-10" title="Назад на 10 секунд">${svg('back')}<em>10</em></button>`
        + `<button type="button" class="np-main" data-a="toggle" id="np-tg"></button><button type="button" data-a="seek" data-s="10" title="Вперёд на 10 секунд">${svg('fwd')}<em>10</em></button><button type="button" data-a="next" title="Следующий">${svg('next')}</button></div></div>`
        + `<div class="np-bar" id="np-bar" role="slider" aria-label="Положение" tabindex="0"><i id="np-fill"></i></div><div class="np-time"><span id="np-pos"></span><span id="np-dur"></span></div>`;
    }
    el.dataset.state = s.status; el.dataset.id = s.id;
    $('np-title').textContent = s.title || 'Без названия'; $('np-title').title = s.title; $('np-sub').textContent = sub;
    $('np-tg').innerHTML = svg(playing ? 'pause' : 'play', 20); $('np-tg').title = playing ? 'Пауза' : 'Играть';
    for (const b of el.querySelectorAll('[data-a]')) { const a = b.dataset.a; b.disabled = (a === 'prev' && !s.can.prev) || (a === 'next' && !s.can.next) || (a === 'seek' && !s.can.seek) || (a === 'toggle' && !(s.can.play || s.can.pause)); }
    $('np-bar').classList.toggle('off', !s.can.seek || !s.dur);
    tick(s);
  }
  function tick(s) {
    if (el.hidden) return;
    s = s || pickSession((m.np && m.np.sessions) || []); if (!s) return;
    const p = live(s); $('np-pos').textContent = fmt(p); $('np-dur').textContent = s.dur ? fmt(s.dur) : ''; $('np-fill').style.width = s.dur ? `${Math.min(100, p / s.dur * 100).toFixed(1)}%` : '0%';
  }
  el.addEventListener('click', async (e) => {
    const b = e.target.closest('button[data-a]'); const s = pickSession((m.np && m.np.sessions) || []); if (!s) return;
    if (b) { if (b.dataset.a === 'seek') control('seek_by', s.id, +b.dataset.s); else control(b.dataset.a, s.id); return; }
    const bar = e.target.closest('#np-bar'); if (bar && s.can.seek && s.dur) { const r = bar.getBoundingClientRect(); control('seek_to', s.id, Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * s.dur); }
  });
  J.on('nowplaying', paint);
  setInterval(() => { if (!document.hidden) { paint(); } }, 1000);
  setInterval(() => { if (!document.hidden) tick(); }, 250);
  window.NP = { fmt, svg, pickSession, live, control, list: () => (m.connected && m.np && m.np.sessions) || [], paint };
})();
