// Themed date picker that replaces the browser's own calendar for <input type="date">. The input stays in the DOM, hidden, and keeps its
// value (ISO yyyy-mm-dd) so code that reads or sets input.value and listens for "input" / "change" keeps working.
// Usage: fzDate.watch(rootElement) enhances the date inputs now inside the root and every one added to it later.
(() => {
  const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  const MON_SHORT = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const DOW = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const p2 = (n) => String(n).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
  const parse = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || ''); return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null; };
  const label = (s) => { const d = parse(s); return d ? `${p2(d.getDate())}.${p2(d.getMonth() + 1)}.${d.getFullYear()}` : ''; };
  const CAL = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/></svg>';
  const ARW = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
  const valueDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  let open = null;                                  // { btn, inp, pop, view: Date (first of month), mode: 'days'|'months', cur: Date }

  function close(focus) {
    if (!open) return; const { pop, btn } = open; open = null; pop.remove(); btn.classList.remove('open'); btn.setAttribute('aria-expanded', 'false');
    document.removeEventListener('keydown', onKey, true); document.removeEventListener('mousedown', onAway, true); window.removeEventListener('resize', onResize);
    if (focus) btn.focus();
  }
  const onAway = (e) => { if (open && !open.pop.contains(e.target) && !open.btn.contains(e.target)) close(); };
  const onResize = () => close();

  function pick(d) {
    const { inp } = open; valueDesc.set.call(inp, d ? iso(d) : '');
    inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true }));
    inp.__dpPaint(); close(true);
  }
  function move(days) { const d = new Date(open.cur); d.setDate(d.getDate() + days); open.cur = d; if (d.getMonth() !== open.view.getMonth() || d.getFullYear() !== open.view.getFullYear()) open.view = new Date(d.getFullYear(), d.getMonth(), 1); paint(); }
  function onKey(e) {
    if (!open) return; const k = e.key;
    if (k === 'Escape') { e.preventDefault(); e.stopPropagation(); close(true); return; }
    if (open.mode !== 'days') return;
    const map = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (k in map) { e.preventDefault(); e.stopPropagation(); move(map[k]); }
    else if (k === 'PageUp' || k === 'PageDown') { e.preventDefault(); e.stopPropagation(); const d = new Date(open.cur); d.setMonth(d.getMonth() + (k === 'PageDown' ? 1 : -1)); open.cur = d; open.view = new Date(d.getFullYear(), d.getMonth(), 1); paint(); }
    else if (k === 'Enter') { e.preventDefault(); e.stopPropagation(); pick(open.cur); }
  }

  function paint() {
    const o = open; if (!o) return; const v = o.view, sel = parse(valueDesc.get.call(o.inp)), today = new Date(), min = o.inp.min ? parse(o.inp.min) : null, max = o.inp.max ? parse(o.inp.max) : null;
    let body;
    if (o.mode === 'months') {
      body = `<div class="dp-months">${MON_SHORT.map((m, i) => `<button type="button" class="dp-m${i === v.getMonth() ? ' on' : ''}" data-m="${i}">${m}</button>`).join('')}</div>`;
    } else {
      const first = (v.getDay() + 6) % 7, start = new Date(v.getFullYear(), v.getMonth(), 1 - first), cells = [];
      for (let i = 0; i < 42; i++) {
        const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i), off = d.getMonth() !== v.getMonth(), we = d.getDay() === 0 || d.getDay() === 6;
        const dis = (min && d < min) || (max && d > max);
        cells.push(`<button type="button" class="dp-d${off ? ' off' : ''}${we ? ' we' : ''}${iso(d) === iso(today) ? ' today' : ''}${sel && iso(d) === iso(sel) ? ' sel' : ''}${iso(d) === iso(o.cur) ? ' cur' : ''}" data-d="${iso(d)}"${dis ? ' disabled' : ''}>${d.getDate()}</button>`);
      }
      body = `<div class="dp-dow">${DOW.map((x, i) => `<span${i > 4 ? ' class="we"' : ''}>${x}</span>`).join('')}</div><div class="dp-days">${cells.join('')}</div>`;
    }
    o.pop.innerHTML = `<div class="dp-head"><button type="button" class="dp-nav" data-n="-1" aria-label="${o.mode === 'months' ? 'Предыдущий год' : 'Предыдущий месяц'}">${ARW('M15 6l-6 6 6 6')}</button>
      <button type="button" class="dp-title" data-t>${o.mode === 'months' ? v.getFullYear() : `${MONTHS[v.getMonth()]} <span>${v.getFullYear()}</span>`}</button>
      <button type="button" class="dp-nav" data-n="1" aria-label="${o.mode === 'months' ? 'Следующий год' : 'Следующий месяц'}">${ARW('M9 6l6 6-6 6')}</button></div>${body}
      <div class="dp-foot"><button type="button" data-clear>Очистить</button><button type="button" data-today>Сегодня</button></div>`;
  }

  function show(btn, inp) {
    if (open) { const same = open.btn === btn; close(); if (same) return; }
    const sel = parse(valueDesc.get.call(inp)), cur = sel || new Date();
    const pop = document.createElement('div'); pop.className = 'dp-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Выбор даты');
    document.body.appendChild(pop);
    open = { btn, inp, pop, cur: new Date(cur.getFullYear(), cur.getMonth(), cur.getDate()), view: new Date(cur.getFullYear(), cur.getMonth(), 1), mode: 'days' };
    paint(); btn.classList.add('open'); btn.setAttribute('aria-expanded', 'true');
    const r = btn.getBoundingClientRect(), h = pop.offsetHeight, w = pop.offsetWidth, below = window.innerHeight - r.bottom - 8, up = below < h && r.top > below;
    pop.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - w - 8))}px`; pop.style[up ? 'bottom' : 'top'] = up ? `${window.innerHeight - r.top + 4}px` : `${r.bottom + 4}px`;
    pop.addEventListener('mousedown', (e) => e.preventDefault());
    pop.addEventListener('click', (e) => {
      const o = open; if (!o) return; const t = e.target;
      const d = t.closest('[data-d]'); if (d) { pick(parse(d.dataset.d)); return; }
      const n = t.closest('[data-n]'); if (n) { const s = +n.dataset.n; o.view = o.mode === 'months' ? new Date(o.view.getFullYear() + s, o.view.getMonth(), 1) : new Date(o.view.getFullYear(), o.view.getMonth() + s, 1); paint(); return; }
      if (t.closest('[data-t]')) { o.mode = o.mode === 'days' ? 'months' : 'days'; paint(); return; }
      const mm = t.closest('[data-m]'); if (mm) { o.view = new Date(o.view.getFullYear(), +mm.dataset.m, 1); o.cur = new Date(o.view); o.mode = 'days'; paint(); return; }
      if (t.closest('[data-today]')) { pick(new Date()); return; }
      if (t.closest('[data-clear]')) pick(null);
    });
    document.addEventListener('keydown', onKey, true); document.addEventListener('mousedown', onAway, true); window.addEventListener('resize', onResize);
  }

  function enhance(inp) {
    if (inp.dataset.dp) return; inp.dataset.dp = '1';
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'dd-btn dp-btn'; btn.setAttribute('aria-haspopup', 'dialog'); btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', inp.getAttribute('aria-label') || 'Дата'); btn.innerHTML = `<span></span>${CAL}`;
    const paintBtn = () => { const v = label(valueDesc.get.call(inp)); btn.firstChild.textContent = v || 'дд.мм.гггг'; btn.firstChild.classList.toggle('ph', !v); };
    inp.__dpPaint = paintBtn;
    Object.defineProperty(inp, 'value', { configurable: true, get() { return valueDesc.get.call(inp); }, set(v) { valueDesc.set.call(inp, v); paintBtn(); } });
    btn.addEventListener('click', () => show(btn, inp));
    inp.classList.add('dd-native'); inp.tabIndex = -1; inp.setAttribute('aria-hidden', 'true');
    inp.insertAdjacentElement('afterend', btn); paintBtn();
  }

  function watch(root) {
    const run = () => root.querySelectorAll('input[type=date]:not([data-dp])').forEach(enhance);
    run(); new MutationObserver(run).observe(root, { childList: true, subtree: true });
  }
  // opens the calendar under any element for a value that is not a form field (jump to a date); cb gets "yyyy-mm-dd" or ''
  function pickAt(anchor, value, cb) {
    const inp = document.createElement('input'); inp.type = 'date'; valueDesc.set.call(inp, value || ''); inp.__dpPaint = () => {};
    inp.addEventListener('change', () => cb(valueDesc.get.call(inp))); show(anchor, inp);
  }
  window.fzDate = { watch, enhance, close, pickAt };
  watch(document.body);
})();
