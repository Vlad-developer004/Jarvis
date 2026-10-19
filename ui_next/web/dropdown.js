// Themed dropdown that replaces a native <select> (the browser's own list cannot be styled). The <select> stays in the DOM, hidden, and keeps
// its value: code that reads select.value or listens for "change" keeps working. Lists longer than 8 items get a search field.
// Usage: fzDropdown.watch(rootElement) enhances the selects now inside the root and every one added to it later.
(() => {
  let open = null;      // { btn, sel, pop, items, idx }

  function close() { if (!open) return; open.pop.remove(); open.btn.classList.remove('open'); open.btn.setAttribute('aria-expanded', 'false'); document.removeEventListener('keydown', onKey, true); document.removeEventListener('mousedown', onAway, true); window.removeEventListener('resize', close); document.removeEventListener('scroll', onScroll, true); open = null; }
  function onScroll(e) { if (open && !open.pop.contains(e.target)) close(); }
  function onAway(e) { if (open && !open.pop.contains(e.target) && !open.btn.contains(e.target)) close(); }
  function setIdx(i, scroll = true) {
    if (!open) return;
    open.idx = Math.max(0, Math.min(open.items.length - 1, i));
    open.items.forEach((it, k) => it.el.classList.toggle('hl', k === open.idx));
    const el = open.items[open.idx] && open.items[open.idx].el; if (el && scroll) el.scrollIntoView({ block: 'nearest' });
  }
  function choose(i) {
    const it = open.items[i]; if (!it) return;
    const { sel, btn } = open; close();
    if (sel.value !== it.value) { sel.value = it.value; sel.dispatchEvent(new Event('change', { bubbles: true })); }
    btn.firstChild.textContent = it.label; btn.focus();
  }
  function onKey(e) {
    if (!open) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); const b = open.btn; close(); b.focus(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setIdx(open.idx + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setIdx(open.idx - 1); }
    else if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); choose(open.idx); }
  }

  function show(btn, sel) {
    if (open) { const same = open.btn === btn; close(); if (same) return; }
    const opts = [...sel.options].map((o) => ({ value: o.value, label: o.textContent }));
    const pop = document.createElement('div'); pop.className = 'dd-pop'; pop.setAttribute('role', 'listbox');
    const search = opts.length > 8;
    pop.innerHTML = (search ? '<input class="dd-q" placeholder="Поиск" autocomplete="off" spellcheck="false">' : '') + '<div class="dd-list"></div>';
    const list = pop.querySelector('.dd-list');
    const state = { btn, sel, pop, items: [], idx: 0 };
    function fill(q) {
      list.innerHTML = ''; state.items = [];
      for (const o of opts) {
        if (q && !o.label.toLowerCase().includes(q)) continue;
        const el = document.createElement('div'); el.className = 'dd-it' + (o.value === sel.value ? ' sel' : ''); el.textContent = o.label; el.setAttribute('role', 'option');
        const i = state.items.length; state.items.push({ ...o, el });
        el.addEventListener('mousemove', () => { if (open && open.idx !== i) setIdx(i, false); });
        el.addEventListener('mousedown', (e) => { e.preventDefault(); choose(i); });
        list.appendChild(el);
      }
      if (!state.items.length) list.innerHTML = '<div class="dd-none">Ничего не найдено</div>';
    }
    fill('');
    document.body.appendChild(pop);
    open = state; btn.classList.add('open'); btn.setAttribute('aria-expanded', 'true');
    const r = btn.getBoundingClientRect(), ph = Math.min(pop.offsetHeight, 288), below = window.innerHeight - r.bottom - 8, above = r.top - 8;
    const up = below < Math.min(ph, 200) && above > below, h = Math.min(288, up ? above : below);
    pop.style.cssText = `left:${r.left}px;min-width:${r.width}px;max-width:${Math.max(r.width, 360)}px;${up ? `bottom:${window.innerHeight - r.top + 4}px` : `top:${r.bottom + 4}px`};max-height:${Math.max(120, h)}px`;
    const cur = state.items.findIndex((it) => it.value === sel.value); setIdx(cur < 0 ? 0 : cur);
    document.addEventListener('keydown', onKey, true); document.addEventListener('mousedown', onAway, true); window.addEventListener('resize', close); document.addEventListener('scroll', onScroll, true);
    const q = pop.querySelector('.dd-q');
    if (q) { q.focus(); q.addEventListener('input', () => { fill(q.value.trim().toLowerCase()); setIdx(0); }); }
  }

  function enhance(sel) {
    if (sel.dataset.dd) return; sel.dataset.dd = '1';
    const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'dd-btn'; btn.setAttribute('aria-haspopup', 'listbox'); btn.setAttribute('aria-expanded', 'false');
    const cur = sel.options[sel.selectedIndex]; btn.innerHTML = '<span></span><svg viewBox="0 0 12 8" width="12" height="8" aria-hidden="true"><path d="M1 1.5l5 5 5-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    btn.firstChild.textContent = cur ? cur.textContent : '';
    btn.addEventListener('click', () => show(btn, sel));
    sel.classList.add('dd-native'); sel.tabIndex = -1; sel.setAttribute('aria-hidden', 'true');
    sel.insertAdjacentElement('afterend', btn);
  }

  function watch(root) {
    const run = () => root.querySelectorAll('select:not([data-dd])').forEach(enhance);
    run(); new MutationObserver(run).observe(root, { childList: true, subtree: true });
  }
  window.fzDropdown = { watch, enhance, close };
})();
