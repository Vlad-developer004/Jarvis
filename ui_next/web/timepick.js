// Themed time field that replaces the browser's own time picker for <input type="time">. The input stays in the DOM, hidden, and keeps its
// value ("HH:MM", 24 hours) so code that reads or sets input.value and listens for "input" / "change" keeps working.
// The popup has a field to type a time ("1530", "15:30", "9") and a list in steps of data-step minutes (default 30).
// Usage: fzTime.watch(rootElement) enhances the time inputs now inside the root and every one added to it later.
(() => {
  const p2 = (n) => String(n).padStart(2, '0');
  const CLOCK = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3 2"/></svg>';
  const valueDesc = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  let open = null;                                  // { btn, inp, pop, items: [], idx }

  function close(focus) {
    if (!open) return; const { pop, btn } = open; open = null; pop.remove(); btn.classList.remove('open'); btn.setAttribute('aria-expanded', 'false');
    document.removeEventListener('mousedown', onAway, true); window.removeEventListener('resize', onResize);
    if (focus) btn.focus();
  }
  const onAway = (e) => { if (open && !open.pop.contains(e.target) && !open.btn.contains(e.target)) close(); };
  const onResize = () => close();

  // "1530" / "15:30" / "9" / "9.5" -> "HH:MM", or '' when it is not a time
  function typed(s) {
    const m = /^\s*(\d{1,2})(?:[:.\s]?(\d{2}))?\s*$/.exec(s || ''); if (!m) return '';
    const h = +m[1], mi = m[2] === undefined ? 0 : +m[2];
    return h < 24 && mi < 60 ? `${p2(h)}:${p2(mi)}` : '';
  }
  function pick(v) {
    const { inp } = open; valueDesc.set.call(inp, v);
    inp.dispatchEvent(new Event('input', { bubbles: true })); inp.dispatchEvent(new Event('change', { bubbles: true })); inp.__tpPaint(); close(true);
  }

  function show(btn, inp) {
    if (open) { const same = open.btn === btn; close(); if (same) return; }
    const step = Math.max(5, Math.min(120, +inp.dataset.step || 30)), cur = valueDesc.get.call(inp), items = [];
    for (let m = 0; m < 1440; m += step) items.push(`${p2(Math.floor(m / 60))}:${p2(m % 60)}`);
    if (cur && !items.includes(cur)) { items.push(cur); items.sort(); }
    const pop = document.createElement('div'); pop.className = 'tp-pop'; pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', 'Выбор времени');
    pop.innerHTML = `<input class="tp-in" data-fld="1" placeholder="чч:мм" autocomplete="off" spellcheck="false" aria-label="Время"><div class="tp-list" role="listbox">${items.map((t) => `<button type="button" class="tp-it${t === cur ? ' sel' : ''}" data-t="${t}" role="option">${t}</button>`).join('')}</div>`;
    document.body.appendChild(pop); open = { btn, inp, pop };
    btn.classList.add('open'); btn.setAttribute('aria-expanded', 'true');
    const r = btn.getBoundingClientRect(), h = pop.offsetHeight, below = window.innerHeight - r.bottom - 8, up = below < h && r.top > below;
    pop.style.left = `${Math.max(8, Math.min(r.left, window.innerWidth - pop.offsetWidth - 8))}px`; pop.style[up ? 'bottom' : 'top'] = up ? `${window.innerHeight - r.top + 4}px` : `${r.bottom + 4}px`;
    const list = pop.querySelector('.tp-list'), sel = list.querySelector('.sel') || list.querySelector(`[data-t="${typed(String(new Date().getHours()))}"]`);
    if (sel) list.scrollTop = Math.max(0, sel.offsetTop - list.clientHeight / 2 + sel.offsetHeight / 2);
    const inpEl = pop.querySelector('.tp-in'); inpEl.value = cur || ''; inpEl.focus(); inpEl.select();
    pop.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) pick(b.dataset.t); });
    inpEl.addEventListener('input', () => { const v = typed(inpEl.value); const hit = v && list.querySelector(`[data-t="${v}"]`); list.querySelectorAll('.hl').forEach((x) => x.classList.remove('hl')); if (hit) { hit.classList.add('hl'); list.scrollTop = hit.offsetTop - 60; } });
    pop.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); const v = typed(inpEl.value); if (v) pick(v); else inpEl.classList.add('bad'); }
      else if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(true); }
      else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); const cells = [...list.querySelectorAll('.tp-it')], i = cells.findIndex((x) => x.dataset.t === (typed(inpEl.value) || cur)), n = cells[Math.max(0, Math.min(cells.length - 1, i + (e.key === 'ArrowDown' ? 1 : -1)))];
        if (n) { inpEl.value = n.dataset.t; inpEl.dispatchEvent(new Event('input')); list.querySelectorAll('.sel').forEach((x) => x.classList.remove('sel')); n.classList.add('sel'); n.scrollIntoView({ block: 'nearest' }); }
      }
    });
    document.addEventListener('mousedown', onAway, true); window.addEventListener('resize', onResize);
  }

  function enhance(inp) {
    if (inp.dataset.tp) return; inp.dataset.tp = '1';
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'dd-btn dp-btn tp-btn'; btn.setAttribute('aria-haspopup', 'dialog'); btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', inp.getAttribute('aria-label') || 'Время'); btn.innerHTML = `<span></span>${CLOCK}`;
    const paintBtn = () => { const v = valueDesc.get.call(inp); btn.firstChild.textContent = v || 'чч:мм'; btn.firstChild.classList.toggle('ph', !v); btn.disabled = inp.disabled; };
    inp.__tpPaint = paintBtn;
    Object.defineProperty(inp, 'value', { configurable: true, get() { return valueDesc.get.call(inp); }, set(v) { valueDesc.set.call(inp, v); paintBtn(); } });
    new MutationObserver(paintBtn).observe(inp, { attributes: true, attributeFilter: ['disabled'] });
    btn.addEventListener('click', () => show(btn, inp));
    inp.classList.add('dd-native'); inp.tabIndex = -1; inp.setAttribute('aria-hidden', 'true');
    inp.insertAdjacentElement('afterend', btn); paintBtn();
  }

  function watch(root) {
    const SEL = 'input[type=time]:not([data-tp])', run = () => root.querySelectorAll(SEL).forEach(enhance);
    const added = (ms) => ms.some((m) => [...m.addedNodes].some((n) => n.nodeType === 1 && (n.matches(SEL) || n.querySelector(SEL))));   // text updates and unrelated nodes cost nothing
    run(); new MutationObserver((ms) => { if (added(ms)) run(); }).observe(root, { childList: true, subtree: true });
  }
  window.fzTime = { watch, enhance, close };
  watch(document.body);
})();
