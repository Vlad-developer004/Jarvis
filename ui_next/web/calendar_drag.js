// Calendar screen, drag and drop: move your own events to another day (month view, the all-day strip) or to another day and time (week and day
// views, snapped to 15 minutes) and resize them by the bottom edge. The change itself goes through Cal.commitChange (calendar_edit.js), which
// asks "this event or the whole series" for repeating ones. Events from outside calendars are read-only and explain that when dragged.
(() => {
  const C = window.Cal; if (!C) return;
  const { S, main, iso, parse, p2, say } = C;
  const HH = 46, STEP = 15, THRESHOLD = 6;
  const mins = (t) => (t ? +t.slice(0, 2) * 60 + +t.slice(3, 5) : 0);
  const hm = (m) => `${p2(Math.floor(m / 60))}:${p2(m % 60)}`;
  let d = null;                                                // the drag in progress

  main.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || e.target.closest('input, textarea')) return;
    const el = e.target.closest('.cl-ev[data-ev], .wk-ev[data-ev]'); if (!el) return;
    const ev = C.evById(el.dataset.ev); if (!ev) return;
    d = { el, ev, resize: !!e.target.closest('.wk-rs'), x0: e.clientX, y0: e.clientY, on: false, grid: el.classList.contains('wk-ev'), warned: false };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up); window.addEventListener('pointercancel', cancel); window.addEventListener('keydown', key, true);
  });

  function colAt(x, y) { const t = document.elementFromPoint(x, y); return t && t.closest('.wk-col'); }
  function dayAt(x, y) { const t = document.elementFromPoint(x, y), c = t && t.closest('.cl-day[data-d], .wk-adc[data-d], .wk-col[data-col], .wk-dh[data-dh]'); return c ? c.dataset.d || c.dataset.col || c.dataset.dh : ''; }

  function move(e) {
    if (!d) return;
    const dx = e.clientX - d.x0, dy = e.clientY - d.y0;
    if (!d.on) {
      if (Math.hypot(dx, dy) < THRESHOLD) return;
      if (!(d.ev.local || d.ev.rw)) { if (!d.warned) { d.warned = true; say(d.ev.src ? 'Повторяющееся событие меняется в самом календаре' : 'События из внешнего календаря менять нельзя'); } return; }
      if (d.grid && d.ev.date !== d.ev.end_date) { if (!d.warned) { d.warned = true; say('Многодневное событие меняется через «Изменить»'); } return; }
      d.on = true; document.body.classList.add('cl-dragging'); d.el.classList.add('dragging');
      if (d.grid) { d.top = parseFloat(d.el.style.top); d.h = parseFloat(d.el.style.height); d.el.style.pointerEvents = 'none'; }
      else { d.ghost = document.createElement('div'); d.ghost.className = 'dg-ghost'; d.ghost.style.setProperty('--ec', getComputedStyle(d.el).getPropertyValue('--ec')); d.ghost.textContent = d.ev.title; document.body.appendChild(d.ghost); }
    }
    if (d.ghost) { d.ghost.style.left = `${e.clientX + 12}px`; d.ghost.style.top = `${e.clientY + 12}px`; }
    if (d.grid && !d.ev.all_day) {
      const snap = Math.round(dy / (HH * STEP / 60)) * (HH * STEP / 60);
      if (d.resize) { d.el.style.height = `${Math.max(22, d.h + snap)}px`; d.dm = Math.round(snap / (HH / 60)); }
      else {
        const col = colAt(e.clientX, e.clientY), from = d.el.closest('.wk-col');
        d.el.style.transform = `translate(${col ? col.getBoundingClientRect().left - from.getBoundingClientRect().left : 0}px, ${snap}px)`; d.col = col ? col.dataset.col : d.ev.date; d.dm = Math.round(snap / (HH / 60));
      }
    } else {
      const day = dayAt(e.clientX, e.clientY); d.day = day;
      for (const c of main.querySelectorAll('.drop')) c.classList.remove('drop');
      const tgt = day && main.querySelector(`.cl-day[data-d="${day}"], .wk-adc[data-d="${day}"], .wk-dh[data-dh="${day}"]`); if (tgt) tgt.classList.add('drop');
    }
  }

  function end() {
    window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', cancel); window.removeEventListener('keydown', key, true);
    document.body.classList.remove('cl-dragging');
    if (d && d.ghost) d.ghost.remove();
    for (const c of main.querySelectorAll('.drop')) c.classList.remove('drop');
  }
  function cancel() { if (d && d.on) { C.dragEnd = performance.now(); C.paint(); } end(); d = null; }
  function key(e) { if (e.key === 'Escape' && d) { e.stopPropagation(); cancel(); } }

  function up() {
    const cur = d; end(); d = null;
    if (!cur || !cur.on) return;
    C.dragEnd = performance.now();
    const ev = cur.ev;
    let f = null;
    if (cur.grid && !ev.all_day) {
      const dur = mins(ev.end_time || ev.time) - mins(ev.time);
      if (cur.resize) { const em = Math.max(mins(ev.time) + STEP, Math.min(1440, mins(ev.end_time || ev.time) + (cur.dm || 0))); f = { date: ev.date, time: ev.time, end_date: ev.end_date, end_time: hm(em % 1440) }; if (em === 1440) f.end_time = '23:59'; }
      else {
        const sm = Math.max(0, Math.min(1440 - Math.max(dur, STEP), mins(ev.time) + (cur.dm || 0))), day = cur.col || ev.date;
        f = { date: day, time: hm(sm), end_date: day, end_time: hm(Math.min(1439, sm + Math.max(dur, 0))) };
      }
      if (f.date === ev.date && f.time === ev.time && f.end_time === ev.end_time) { C.paint(); return; }
    } else {
      const day = cur.day; if (!day || day === ev.date) { C.paint(); return; }
      const delta = Math.round((parse(day) - parse(ev.date)) / 864e5), e1 = parse(ev.end_date); e1.setDate(e1.getDate() + delta);
      f = { date: day, time: ev.time, end_date: iso(e1), end_time: ev.end_time };
    }
    C.paint();
    C.commitChange(ev, f);
  }
})();
