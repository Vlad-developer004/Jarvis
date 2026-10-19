// Text fields with a frame of their own: a leading icon (by field kind), corner ticks, a charge line that runs along the bottom edge on focus
// and a clear button. The <input> stays the same element (same id, value and events); the frame is a wrapper added around it.
// Usage: fzFields.watch(rootElement) wraps the inputs now inside the root and every one added later.
(() => {
  const SVG = (d) => `<svg class="fi" viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
  const ICON = {
    search: SVG('M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM21 21l-4.5-4.5'),
    mail: SVG('M4 6h16v12H4zM4 7l8 6 8-6'),
    key: SVG('M14 10a4 4 0 1 1 1.5 3.1L9 19.5H6v-3l1.5-1.5H9v-1.5l2.4-2.4A4 4 0 0 1 14 10z'),
    link: SVG('M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1'),
    user: SVG('M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20c1-4 4-5 8-5s7 1 8 5'),
    server: SVG('M4 5h16v5H4zM4 14h16v5H4zM8 7.5h.01M8 16.5h.01'),
    edit: SVG('M4 20h4L19 9l-4-4L4 16zM13 7l4 4'),
  };
  const X = '<button type="button" class="fc" tabindex="-1" aria-label="Очистить"><svg viewBox="0 0 12 12" width="10" height="10"><path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg></button>';

  function kind(el) {
    if (el.inputMode === 'decimal') return '';             /* small numeric boxes (pause, hold) stay plain */
    const id = el.id || '', ph = (el.placeholder || '').toLowerCase();
    if (el.classList.contains('pe-search') || /search|(^|-)q$/.test(id)) return 'search';
    if (el.type === 'email') return 'mail';
    if (el.type === 'password') return 'key';
    if (/src|url|link/.test(id) || ph.includes('http')) return 'link';
    if (/imap|smtp|server/.test(id)) return 'server';
    if (/chat/.test(id)) return 'user';
    return 'edit';
  }

  function wrap(el) {
    if (el.dataset.fld || el.closest('.fld')) return; el.dataset.fld = '1';
    const w = document.createElement('span'); w.className = 'fld';
    const k = kind(el); if (k) w.classList.add('ic');
    el.replaceWith(w);
    if (k) w.insertAdjacentHTML('afterbegin', ICON[k]);
    w.appendChild(el);
    w.insertAdjacentHTML('beforeend', X);
    const sync = () => w.classList.toggle('has', el.value !== '');
    el.addEventListener('input', sync); sync();
    w.querySelector('.fc').addEventListener('mousedown', (e) => { e.preventDefault(); el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); el.focus(); });
  }

  function watch(root) {
    const sel = 'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=range]):not([type=time]):not([type=date]):not([data-fld])';
    const run = () => root.querySelectorAll(sel).forEach(wrap);
    run(); new MutationObserver(run).observe(root, { childList: true, subtree: true });
  }
  window.fzFields = { watch };
  for (const id of ['pe-box', 'ex-mbox', 'vc-body', 'mail', 'calpage', 'lk-tools', 'lk-mods', 'lk-dev', 'lk-ai', 'lk-mbox', 'ci-body']) { const r = document.getElementById(id); if (r) watch(r); }
})();
