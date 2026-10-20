// Mail screen, the "mailbox power" part (loaded after mail.js, uses window.MailApp): selecting many letters with bulk actions, delete / archive / move with
// an undo window, quick actions on a row, pop-up menus (labels, move to, list actions), signature, keyboard shortcuts and the dialogs behind them.
// Removals are written to the server after a short delay unless the user presses "Отменить", so an accidental click costs nothing.
(() => {
  const A = window.MailApp; if (!A) return;
  const { S, root, call, say, esc, I } = A;
  const UNDO_MS = 6000;
  const queue = [];
  let tm = 0, pop = null;
  const stop = (e) => { e.stopPropagation(); e.preventDefault(); };
  const plural = (n, a, b, c) => { const k = n % 100; return n % 10 === 1 && k !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (k < 10 || k >= 20) ? b : c; };
  const letters = (n) => (n === 1 ? 'Письмо' : `${n} ${plural(n, 'письмо', 'письма', 'писем')}`);
  const has = (role) => S.folders.includes(role);
  const rowOf = (uid) => S.rows.find((x) => x.uid === uid);

  // ---- undo toast ----
  function sayUndo(text, onUndo) {
    const t = A.toast; t.innerHTML = `${esc(text)}<button type="button" class="ml-ub">Отменить</button>`; t.classList.add('on', 'undo'); clearTimeout(tm);
    tm = setTimeout(() => t.classList.remove('on', 'undo'), UNDO_MS);
    t.querySelector('.ml-ub').onclick = () => { t.classList.remove('on', 'undo'); clearTimeout(tm); onUndo(); };
  }
  function restore(op) {
    if (S.folder !== op.folder) return;
    const have = new Set(S.rows.map((x) => x.uid));
    S.rows = S.rows.concat(op.rows.filter((r) => !have.has(r.uid))).sort((a, b) => +b.uid - +a.uid); S.total += op.rows.length; A.paintAll();
  }
  function removeRows(uids, to, opts = {}) {
    const folder = S.folder, rows = S.rows.filter((r) => uids.includes(r.uid)); if (!rows.length) return;
    S.rows = S.rows.filter((r) => !uids.includes(r.uid)); S.total = Math.max(0, S.total - rows.length);
    if (uids.includes(S.sel)) { S.sel = ''; S.cur = null; S.reply = null; }
    uids.forEach((u) => S.picked.delete(u)); A.paintAll();
    const op = { folder, uids, to, rows, done: false, t: 0 };
    op.run = async () => {
      if (op.done) return; op.done = true; clearTimeout(op.t); const i = queue.indexOf(op); if (i >= 0) queue.splice(i, 1);
      if (!m.connected) return;
      const r = await call({ op: 'remove', folder, uids, to });
      if (!r.ok) { say(r.error === 'no_folder' ? 'На сервере нет такой папки' : r.message || 'Не удалось выполнить'); restore(op); return; }
      A.refreshUnread();
    };
    if (opts.now || !to) { op.run(); say(`${letters(rows.length)} удалено`); return; }
    const where = to === 'trash' ? 'в корзину' : to === 'archive' ? 'в архив' : to === 'junk' ? 'в спам' : `в «${A.folderName(to)}»`;
    queue.push(op); op.t = setTimeout(op.run, UNDO_MS);
    sayUndo(`${letters(rows.length)} ${rows.length === 1 ? 'перемещено' : 'перемещены'} ${where}`, () => { op.done = true; clearTimeout(op.t); const i = queue.indexOf(op); if (i >= 0) queue.splice(i, 1); restore(op); });
  }
  const flush = () => Promise.all(queue.slice().map((o) => o.run()));
  addEventListener('pagehide', () => queue.slice().forEach((o) => o.run()));

  async function flagMany(uids, flag, on) {
    if (m.connected) { const r = await call({ op: 'flag', folder: S.folder, uids, flag, on }); if (!r.ok) { say(r.message || 'Не удалось изменить'); return false; } }
    for (const u of uids) { const r = rowOf(u); if (r) { if (flag === 'seen') r.unread = !on; else r.flagged = on; } }
    A.paintItems(); A.paintHead(); if (S.cur) A.paintHeader(); if (flag === 'seen' && m.connected) A.refreshUnread();
    return true;
  }
  const trashOrDelete = (uids) => {
    if (has('trash') && S.folder !== 'trash') removeRows(uids, 'trash');
    else dlg({ title: 'Удалить навсегда?', body: `${letters(uids.length)} будет удалено без возможности вернуть.`, ok: 'Удалить', danger: true, onOk: () => removeRows(uids, '', { now: true }) });
  };

  // ---- selection ----
  function toggle(uid) { if (S.picked.has(uid)) S.picked.delete(uid); else S.picked.add(uid); A.paintItems(); }
  function paintSel() {
    const el = $('ml-selbar'), top = $('ml-top'); if (!el) return;
    const n = S.picked.size; el.hidden = !n; if (top) top.style.display = n ? 'none' : '';
    if (!n) return;
    const b = (k, icon, title, cls = '') => `<button type="button" class="ml-ab ic ${cls}" data-sel="${k}" title="${title}">${icon}</button>`;
    el.innerHTML = `${b('clear', '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>', 'Снять выделение')}<b>Выбрано: ${n}</b><button type="button" class="ml-nb" data-sel="all">Все (${S.rows.length})</button><span class="ml-sp"></span>`
      + b('read', I.open, 'Прочитано') + b('unread', I.mail, 'Не прочитано') + b('star', I.star, 'Пометить')
      + (has('archive') && S.folder !== 'archive' ? b('archive', I.archive, 'В архив') : '') + b('move', I.fwd, 'Переместить в…') + b('del', I.trash, 'Удалить');
  }
  async function selAction(k, anchor) {
    const uids = [...S.picked];
    if (k === 'clear') { S.picked.clear(); A.paintItems(); }
    else if (k === 'tgl') { A.visibleRows().forEach((r) => S.picked.add(r.uid)); A.paintItems(); }
    else if (k === 'refresh') { anchor.classList.add('spin'); await A.loadList({ refresh: true, silent: true }); anchor.classList.remove('spin'); }
    else if (k === 'all') { A.visibleRows().forEach((r) => S.picked.add(r.uid)); A.paintItems(); }
    else if (k === 'read' || k === 'unread') { if (await flagMany(uids, 'seen', k === 'read')) { S.picked.clear(); A.paintItems(); } }
    else if (k === 'star') { if (await flagMany(uids, 'flagged', uids.some((u) => !(rowOf(u) || {}).flagged))) { S.picked.clear(); A.paintItems(); } }
    else if (k === 'archive') removeRows(uids, 'archive');
    else if (k === 'del') trashOrDelete(uids);
    else if (k === 'move') moveMenu(anchor, uids);
  }

  // ---- pop-up menus ----
  function closePop() { if (pop) { pop.remove(); pop = null; } }
  function place(el, anchor) {
    const r = anchor.getBoundingClientRect(), b = root.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    let x = r.left - b.left, y = r.bottom - b.top + 4;
    if (x + w > b.width - 8) x = Math.max(8, r.right - b.left - w); if (y + h > b.height - 8) y = Math.max(8, r.top - b.top - h - 4);
    el.style.left = `${x}px`; el.style.top = `${y}px`;
  }
  function popMenu(anchor, items) {
    closePop(); if (!anchor) return;
    const el = document.createElement('div'); el.className = 'ml-pop'; el.setAttribute('role', 'menu');
    el.innerHTML = items.map((it, i) => (it.sep ? '<div class="ml-ps"></div>' : it.head ? `<div class="ml-ph">${esc(it.head)}</div>` : `<button type="button" role="menuitem" class="ml-pi${it.danger ? ' dg' : ''}${it.on ? ' on' : ''}" data-pi="${i}">${esc(it.label)}</button>`)).join('');
    root.appendChild(el); pop = el; place(el, anchor);
    el.addEventListener('click', (e) => { const bt = e.target.closest('[data-pi]'); if (!bt) return; e.stopPropagation(); const it = items[+bt.dataset.pi]; closePop(); if (it.onPick) it.onPick(); });
  }
  document.addEventListener('mousedown', (e) => { if (pop && !e.target.closest('.ml-pop') && !e.target.closest('.dp-pop') && !e.target.closest('[data-menu], [data-do=more], [data-sel=move]')) closePop(); });
  function targets(uids) {
    const out = [];
    for (const r of ['inbox', 'archive', 'junk', 'trash']) if (has(r) && r !== S.folder) out.push({ id: r, label: A.FOLDER_NAMES[r] });
    for (const c of S.custom) if (c.id !== S.folder) out.push({ id: c.id, label: c.name });
    return out.map((t) => ({ label: t.label, onPick: () => removeRows(uids, t.id) }));
  }
  const moveMenu = (anchor, uids) => { const t = targets(uids); popMenu(anchor, t.length ? [{ head: 'Переместить в' }, ...t] : [{ head: 'Некуда переместить' }]); };
  function headerMenu(anchor) {
    const uids = [S.sel]; if (!S.sel) return;
    popMenu(anchor, [...(has('junk') && S.folder !== 'junk' ? [{ label: 'Это спам', onPick: () => removeRows(uids, 'junk') }, { sep: 1 }] : []), { head: 'Переместить в' }, ...targets(uids)]);
  }
  function listMenu(anchor) {
    const items = [{ label: 'Отметить все прочитанными', onPick: () => dlg({ title: 'Отметить всё прочитанным?', body: `Все письма в папке «${A.folderName(S.folder)}» будут отмечены прочитанными.`, ok: 'Отметить', onOk: markAll }) }];
    if (S.folder === 'trash' || S.folder === 'junk') items.push({ label: 'Очистить папку…', danger: true, onPick: () => dlg({ title: `Очистить «${A.folderName(S.folder)}»?`, body: 'Все письма в этой папке будут удалены навсегда.', ok: 'Очистить', danger: true, onOk: emptyFolder }) });
    items.push({ sep: 1 }, { label: A.logosOn() ? 'Логотипы отправителей: вкл' : 'Логотипы отправителей: выкл', onPick: () => { A.setLogos(!A.logosOn()); A.paintItems(); if (S.cur) A.paintHeader(); say(A.logosOn() ? 'Логотипы берутся с сайтов отправителей' : 'Логотипы отключены'); } }, { label: 'Подпись…', onPick: signatureDlg }, { label: 'Горячие клавиши', onPick: helpDlg });
    popMenu(anchor, items);
  }
  function advPanel(anchor) {
    closePop();
    const el = document.createElement('div'); el.className = 'ml-pop pf'; el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'Расширенный поиск');
    const row = (k, t, ph) => `<label class="pf-r"><span>${t}</span><input data-fld="1" data-f="${k}" placeholder="${ph}" autocomplete="off"></label>`;
    el.innerHTML = `${row('from', 'От', 'имя или адрес')}${row('subject', 'Тема', 'слово в теме')}${row('text', 'Текст', 'слово в письме')}
      <div class="pf-two"><label class="pf-r"><span>С</span><input data-fld="1" type="date" data-f="after"></label><label class="pf-r"><span>По</span><input data-fld="1" type="date" data-f="before"></label></div>
      <div class="pf-ck"><button type="button" class="ml-op" data-t="is:unread">Непрочитанные</button><button type="button" class="ml-op" data-t="is:starred">С пометкой</button><button type="button" class="ml-op" data-t="has:attachment">С вложением</button></div>
      <div class="ml-da"><button type="button" class="cm-try" data-a="reset">Сбросить</button><button type="button" class="cm-try primary" data-a="go">Найти</button></div>`;
    root.appendChild(el); pop = el; place(el, anchor);
    const f = (k) => el.querySelector(`[data-f="${k}"]`);
    el.addEventListener('click', (e) => {
      const t = e.target.closest('[data-t]'); if (t) { t.classList.toggle('on'); return; }
      const a = e.target.closest('[data-a]'); if (!a) return;
      if (a.dataset.a === 'reset') { closePop(); A.runSearch(''); return; }
      const q = (k, v) => (v.trim() ? [/\s/.test(v.trim()) ? `${k}:"${v.trim()}"` : `${k}:${v.trim()}`] : []);
      const parts = [...q('from', f('from').value), ...q('subject', f('subject').value), ...(f('after').value ? [`after:${f('after').value}`] : []), ...(f('before').value ? [`before:${f('before').value}`] : []),
        ...[...el.querySelectorAll('.ml-op.on')].map((b) => b.dataset.t), ...(f('text').value.trim() ? [f('text').value.trim()] : [])];
      closePop(); A.runSearch(parts.join(' '));
    });
    el.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.matches('input')) { e.preventDefault(); el.querySelector('[data-a=go]').click(); } });
    const first = f('from'); if (first) first.focus();
  }
  function labelsMenu(anchor) { popMenu(anchor, [{ head: 'Метки и папки' }, ...S.custom.map((c) => ({ label: c.name, on: c.id === S.folder, onPick: () => A.switchFolder(c.id) }))]); }
  async function markAll() {
    if (m.connected) { const r = await call({ op: 'read_all', folder: S.folder }); if (!r.ok) { say(r.message || 'Не удалось выполнить'); return; } A.refreshUnread(); }
    S.rows.forEach((r) => { r.unread = false; }); A.paintItems(); say('Все письма отмечены прочитанными');
  }
  async function emptyFolder() {
    if (m.connected) { const r = await call({ op: 'empty', folder: S.folder }); if (!r.ok) { say(r.message || 'Не удалось очистить'); return; } }
    S.rows = []; S.total = 0; S.more = false; S.sel = ''; S.cur = null; A.paintAll(); say('Папка очищена');
  }

  // ---- dialogs ----
  function dlg({ title, body, ok, danger, onOk, html, onOpen }) {
    document.querySelectorAll('.ml-dlg').forEach((x) => x.remove());
    const d = document.createElement('div'); d.className = 'ml-dlg';
    d.innerHTML = `<div class="ml-db" role="dialog" aria-modal="true"><h3>${esc(title)}</h3>${html || `<p>${esc(body || '')}</p>`}<div class="ml-da"><button type="button" class="cm-try" data-d="no">${ok ? 'Отмена' : 'Закрыть'}</button>${ok ? `<button type="button" class="cm-try ${danger ? 'danger' : 'primary'}" data-d="ok">${esc(ok)}</button>` : ''}</div></div>`;
    root.appendChild(d);
    const close = () => d.remove();
    d.addEventListener('mousedown', (e) => { if (e.target === d) close(); });
    d.addEventListener('click', async (e) => { const b = e.target.closest('[data-d]'); if (!b) return; if (b.dataset.d === 'ok' && onOk) { const keep = await onOk(d); if (keep === false) return; } close(); });
    if (onOpen) onOpen(d);
    const f = d.querySelector('textarea, .cm-try.primary, .cm-try.danger, .cm-try'); if (f) f.focus();
  }
  async function signatureDlg() {
    const cur = m.connected ? ((await call({ op: 'prefs' })).signature || '') : (S.demoSig || '');
    dlg({ title: 'Подпись', ok: 'Сохранить', html: '<p>Добавляется в конец каждого отправляемого письма и ответа.</p><textarea id="ml-sig" rows="5" maxlength="500" placeholder="Например: С уважением, Анна"></textarea>',
      onOpen: (d) => { d.querySelector('#ml-sig').value = cur; },
      onOk: async (d) => { const v = d.querySelector('#ml-sig').value; if (!m.connected) { S.demoSig = v; return true; } const r = await call({ op: 'prefs_set', signature: v }); if (!r.ok) { say('Не удалось сохранить подпись'); return false; } say(r.signature ? 'Подпись сохранена' : 'Подпись убрана'); return true; } });
  }
  function helpDlg() {
    const rows = [['j / k', 'следующее / предыдущее письмо'], ['r', 'ответить'], ['a', 'ответить всем'], ['f', 'переслать'], ['s', 'пометить звёздочкой'], ['u', 'прочитано / не прочитано'], ['e', 'в архив'], ['# или Delete', 'удалить'], ['x', 'выбрать письмо'], ['c', 'новое письмо'], ['/', 'поиск'], ['Esc', 'снять выделение, закрыть меню']];
    dlg({ title: 'Горячие клавиши', html: `<div class="ml-keys">${rows.map(([k, t]) => `<kbd>${esc(k)}</kbd><span>${esc(t)}</span>`).join('')}</div>` });
  }

  // ---- events (capture: these run before the list's own click handling) ----
  root.addEventListener('click', (e) => {
    const t = e.target, row = t.closest('.ml-it'), uid = row && row.dataset.uid;
    const chk = t.closest('[data-chk]'); if (chk && uid) { stop(e); toggle(uid); return; }
    const st = t.closest('[data-star]'); if (st && uid) { stop(e); const r = rowOf(uid); flagMany([uid], 'flagged', !(r && r.flagged)); return; }
    const q = t.closest('[data-q]'); if (q && uid) {
      stop(e); const r = rowOf(uid);
      if (q.dataset.q === 'seen') flagMany([uid], 'seen', !!(r && r.unread));
      else if (q.dataset.q === 'archive') { if (has('archive') && S.folder !== 'archive') removeRows([uid], 'archive'); else say('Архива у этой почты нет'); }
      else trashOrDelete([uid]);
      return;
    }
    const sel = t.closest('[data-sel]'); if (sel) { stop(e); selAction(sel.dataset.sel, sel); return; }
    const mn = t.closest('[data-menu]'); if (mn) { stop(e); ({ labels: labelsMenu, list: listMenu, adv: advPanel }[mn.dataset.menu])(mn); }
  }, true);

  document.addEventListener('keydown', (e) => {
    if (typeof VIEW === 'undefined' || VIEW !== 'mail' || e.ctrlKey || e.metaKey || e.altKey || S.state !== 'ok') return;
    if (!$('ml-modal').hidden || root.querySelector('.ml-dlg')) return;
    if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) return;
    const k = e.key, c = S.cur && !S.cur.error && !S.cur.head;
    if (k === 'Escape') { if (pop) closePop(); else if (S.picked.size) { S.picked.clear(); A.paintItems(); } return; }
    if (k === 'j' || k === 'k') {
      const rows = A.visibleRows(); if (!rows.length) return;
      const i = rows.findIndex((r) => r.uid === S.sel), n = Math.min(rows.length - 1, Math.max(0, i + (k === 'j' ? 1 : -1)));
      A.openMsg(rows[n].uid); const el = $('ml-items') && $('ml-items').querySelector(`[data-uid="${rows[n].uid}"]`); if (el) el.scrollIntoView({ block: 'nearest' }); e.preventDefault(); return;
    }
    if (k === 'c') { e.preventDefault(); A.openCompose(); return; }
    if (k === '/') { e.preventDefault(); const q = $('ml-q'); if (q) q.focus(); return; }
    if (k === '?') { e.preventDefault(); helpDlg(); return; }
    if (k === 'x' && S.sel) { toggle(S.sel); return; }
    if (!c) return;
    const act = { r: 'reply', a: 'all', f: 'fwd', s: 'star', u: 'seen', e: 'archive', '#': 'del', Delete: 'del' }[k];
    if (!act || (act === 'archive' && !(has('archive') && S.folder !== 'archive'))) return;
    if ((act === 'reply' || act === 'all' || act === 'fwd') && S.folder === 'drafts') return;
    e.preventDefault(); A.doAction(act);
  });

  window.MailX = { dlg, removeRows, flush, pending: () => queue.length > 0, paintSel, headerMenu, flagMany };
})();
