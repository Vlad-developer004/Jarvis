// Mail screen: folders, the message list (filters, search, paging), a reader that shows HTML letters in a sandboxed frame (sanitized by the core)
// and plain-text letters formatted, flags, archive/delete, reply / reply all / forward, new message with attachments, received attachments.
// Talks to the core with the `mail` command (ui_next/bridge/mail.py: one long-lived IMAP connection and a cache, so opening is quick).
// Links in letters open in the browser through `open_url`. Without a core it shows demo letters. Relies on globals of app.html: $, J, m, ic, esc, VIEW, setBadge.
(() => {
  const NOW = Date.now() / 1000;
  const DEMO_ROWS = [
    { uid: 'd1', subject: 'Встреча по проекту в пятницу', name: 'Анна Ковальчук', addr: 'anna@example.com', ts: NOW - 3600, unread: true, flagged: true, att: true },
    { uid: 'd2', subject: 'Счёт за октябрь', name: 'Hosting Team', addr: 'billing@example.com', ts: NOW - 86400, unread: true, flagged: false, att: false, html: true },
    { uid: 'd3', subject: 'Re: Вопрос по договору', name: 'Максим Петренко', addr: 'max@example.com', ts: NOW - 86400 * 4, unread: false, flagged: false, att: false },
  ];
  const DEMO_TEXT = 'Здравствуйте!\n\nПодтверждаю встречу в пятницу в 15:00. Материалы: https://example.com/files/project-overview-and-timeline-for-the-next-quarter.pdf\n\nПожалуйста, посмотрите:\n- повестку\n- смету\n\nМаксим писал(а):\n> Давайте перенесём на вечер?\n> Мне так удобнее.\n\nС уважением,\nАнна\n-- \nАнна Ковальчук\nпроект-менеджер';
  const DEMO_HTML = '<!doctype html><meta charset=utf-8><style>body{margin:0;padding:18px 22px;background:#fff;color:#1c2733;font:14px/1.55 "Segoe UI",Arial,sans-serif}a{color:#0a63c9}.b{background:#eef4fb;border-radius:8px;padding:14px 16px;margin:12px 0}.n{font:700 26px Arial}.btn{display:inline-block;background:#0a63c9;color:#fff;padding:9px 16px;border-radius:6px;text-decoration:none}table{border-collapse:collapse;width:100%}td{padding:6px 8px;border-bottom:1px solid #dde6ef}</style><h2 style="margin:0 0 6px">Счёт за октябрь</h2><p>Здравствуйте! Сумма к оплате за хостинг:</p><div class=b><div class=n>1 240 ₽</div><div>оплатить до 25 октября</div></div><table><tr><td>Хостинг, тариф «Pro»</td><td align=right>990 ₽</td></tr><tr><td>Домен example.com</td><td align=right>250 ₽</td></tr></table><p><a class=btn href="#">Оплатить счёт</a></p><p style="color:#6b7c8d;font-size:12px">Это письмо создано автоматически.</p>';
  const FOLDER_NAMES = { inbox: 'Входящие', sent: 'Отправленные', drafts: 'Черновики', junk: 'Спам', trash: 'Корзина', archive: 'Архив' };
  const FILTERS = [['all', 'Все'], ['unread', 'Непрочитанные'], ['flagged', 'Помеченные']];
  const MONTHS = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const SVG = (d, w = 1.9) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const I = {
    reply: SVG('<path d="M10 8L4 13l6 5M4 13h9a7 7 0 0 1 7 7"/>'), all: SVG('<path d="M8 8L2 13l6 5M13 8L7 13l6 5M7 13h7a7 7 0 0 1 7 7"/>'), fwd: SVG('<path d="M14 8l6 5-6 5M20 13h-9a7 7 0 0 0-7 7"/>'),
    star: SVG('<path d="M12 3.5l2.6 5.4 5.9.8-4.3 4.1 1 5.9L12 17l-5.2 2.7 1-5.9L3.5 9.7l5.9-.8z"/>'), mail: SVG('<path d="M4 6h16v12H4zM4 7l8 6 8-6"/>'),
    open: SVG('<path d="M4 9l8-5 8 5v10H4zM4 9l8 6 8-6"/>'), archive: SVG('<path d="M4 5h16v4H4zM5 9v10h14V9M10 13h4"/>'), trash: SVG('<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6"/>'),
    clip: SVG('<path d="M20 11l-8.5 8.5a5 5 0 0 1-7-7L13 4a3.3 3.3 0 0 1 4.7 4.7L9.2 17.2a1.7 1.7 0 0 1-2.4-2.4L14.5 7"/>', 1.7), down: SVG('<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>'),
    tune: SVG('<path d="M4 7h9M17 7h3M4 17h3M11 17h9M13 5v4M7 15v4"/>'),
    img: SVG('<path d="M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M9 9h.01"/>'), more: SVG('<path d="M6 12h.01M12 12h.01M18 12h.01" stroke-width="3"/>'),
  };
  const root = $('mail'), listEl = $('ml-list'), readEl = $('ml-read'), toast = $('ml-toast'), modal = $('ml-modal'), mbox = $('ml-mbox');
  const S = { state: 'loading', email: '', folder: 'inbox', folders: ['inbox'], custom: [], picked: new Set(), filter: 'all', q: '', srv: '', rows: [], total: 0, more: false, unreadInbox: 0, sel: '', cur: null, reading: false, err: '',
    reply: null, drafts: {}, attach: [], sending: false, confirmDel: false, view: 'html', images: false, saved: {}, busy: false, loadingMore: false };
  let toastTimer = 0, comp = null, searchTimer = 0, seq = 0, poll = 0, ready = false;
  const TRUST_KEY = 'jarvis.mail.trusted';
  const trusted = () => { try { return new Set(JSON.parse(localStorage.getItem(TRUST_KEY) || '[]')); } catch (e) { return new Set(); } };
  const setTrust = (a, on) => { try { const t = trusted(); if (on) t.add(a); else t.delete(a); localStorage.setItem(TRUST_KEY, JSON.stringify([...t])); } catch (e) { /* storage unavailable */ } };
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3400); };
  const call = async (b) => (await J.send('mail', b)) || { ok: false, error: 'offline' };
  const p2 = (n) => String(n).padStart(2, '0');
  const hue = (s) => { let h = 0; for (const c of s || '?') h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
  const initials = (n) => { const w = (n || '?').replace(/[^\p{L}\p{N} ]/gu, '').trim().split(/\s+/); return ((w[0] || '?')[0] + (w[1] ? w[1][0] : '')).toUpperCase(); };
  function short(ts) {
    if (!ts) return '';
    const d = new Date(ts * 1000), t = new Date();
    if (d.toDateString() === t.toDateString()) return `${p2(d.getHours())}:${p2(d.getMinutes())}`;
    if (d.getFullYear() === t.getFullYear()) return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
    return `${p2(d.getDate())}.${p2(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)}`;
  }
  const full = (ts) => { if (!ts) return ''; const d = new Date(ts * 1000); return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${p2(d.getHours())}:${p2(d.getMinutes())}`; };
  const size = (b) => (b < 1024 ? `${b} Б` : b < 1048576 ? `${Math.round(b / 1024)} КБ` : `${(b / 1048576).toFixed(1)} МБ`);
  const plural = (n, a, b, c) => { const k = n % 100; return n % 10 === 1 && k !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (k < 10 || k >= 20) ? b : c; };
  const avatar = (name, addr) => `<span class="ml-av" style="--gh:${hue(addr || name)}">${esc(initials(name))}</span>`;

  // ---- plain text, formatted ----
  function inline(text) {
    return esc(text).replace(/https?:\/\/[^\s<>"&]+(?:&amp;[^\s<>"&]+)*|[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, (u) => {
      if (u.includes('@') && !u.startsWith('http')) return `<a href="#" class="ml-a" data-url="mailto:${esc(u)}">${esc(u)}</a>`;
      const raw = u.replace(/&amp;/g, '&'), shown = raw.length > 64 ? `${raw.slice(0, 48)}…` : raw;
      return `<a href="#" class="ml-a" data-url="${esc(raw)}" title="${esc(raw)}">${esc(shown)}</a>`;
    });
  }
  function fmtText(text) {
    const lines = String(text || '').replace(/\r/g, '').split('\n'), out = [];
    let para = [], quote = [], sig = false;
    const flushP = () => { if (para.length) { out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; } };
    const flushQ = () => { if (quote.length) { out.push(`<blockquote class="ml-bq">${quote.map(inline).join('<br>')}</blockquote>`); quote = []; } };
    for (const raw of lines) {
      if (!sig && /^--\s?$/.test(raw)) { flushP(); flushQ(); sig = true; out.push('<div class="ml-sig">'); continue; }
      const q = /^\s*>+\s?(.*)$/.exec(raw);
      if (q) { flushP(); quote.push(q[1]); continue; }
      flushQ();
      if (!raw.trim()) { flushP(); continue; }
      if (/(писал\(?а?\)?|wrote|написав\(?ла?\)?):\s*$/i.test(raw) && !para.length) { out.push(`<div class="ml-attr">${inline(raw)}</div>`); continue; }
      if (/^\s*[-*•]\s+/.test(raw)) { flushP(); out.push(`<div class="ml-li">${inline(raw.replace(/^\s*[-*•]\s+/, ''))}</div>`); continue; }
      para.push(raw);
    }
    flushP(); flushQ();
    return out.join('') + (sig ? '</div>' : '');
  }

  // ---- loading ----
  const keepSel = () => S.rows.some((x) => x.uid === S.sel);
  async function loadList(opts = {}) {
    if (window.MailX && window.MailX.pending()) { if (opts.silent) return; await window.MailX.flush(); }
    const n = ++seq, folder = S.folder, flt = S.filter;
    if (!m.connected) { S.state = 'ok'; S.email = 'demo@example.com'; S.folders = ['inbox', 'sent', 'drafts', 'junk', 'trash', 'archive']; S.custom = [{ id: 'f1', name: 'Работа' }, { id: 'f2', name: 'Билеты' }]; S.rows = DEMO_ROWS.map((r) => ({ ...r })); S.total = S.rows.length; S.more = false; S.unreadInbox = 2; paintAll(); return; }
    if (!opts.silent && !S.rows.length) { S.state = 'loading'; paintAll(); }
    if (!ready) {
      const [f, r] = await Promise.all([call({ op: 'folders' }), call({ op: 'list', folder, filter: flt })]);
      if (n !== seq) return;
      if (f.error === 'not_configured' || r.error === 'not_configured') { S.state = 'none'; paintAll(); return; }
      if (!f.ok || !r.ok) { S.state = 'error'; S.err = r.message || f.message || 'Jarvis ещё запускается'; paintAll(); return; }
      ready = true; S.folders = f.folders; S.custom = f.custom || []; S.unreadInbox = f.unread; S.email = r.email; applyList(r, opts); S.state = 'ok'; paintAll();
      if (r.cached) loadList({ silent: true, refresh: true });
      return;
    }
    const r = await call({ op: 'list', folder, filter: flt, q: S.srv, refresh: !!opts.refresh });
    if (n !== seq) return;
    if (!r.ok) { if (!opts.silent) { S.state = 'error'; S.err = r.message || 'Не удалось получить список писем'; paintAll(); } return; }
    S.email = r.email; applyList(r, opts); S.state = 'ok'; paintAll();
    if (r.cached && !opts.refresh && !S.srv) loadList({ silent: true, refresh: true });
    if (folder === 'inbox') refreshUnread();
  }
  function applyList(r, opts) {
    const extra = opts.silent && S.rows.length > r.rows.length ? S.rows.filter((x) => !r.rows.some((y) => y.uid === x.uid)) : [];
    S.rows = opts.silent && extra.length ? r.rows.concat(extra.filter((x) => +x.uid < +(r.rows[r.rows.length - 1] || { uid: 0 }).uid)) : r.rows;
    S.total = r.total; S.more = r.more;
    if (!keepSel()) { S.sel = ''; S.cur = null; S.reply = null; }
  }
  async function refreshUnread() {
    const f = await call({ op: 'folders' });
    if (f.ok) { S.unreadInbox = f.unread; S.folders = f.folders; S.custom = f.custom || []; paintFolders(); paintHead(); }
  }
  async function loadMore() {
    if (S.loadingMore || !S.more) return;
    S.loadingMore = true; paintItems();
    const r = await call({ op: 'list', folder: S.folder, filter: S.filter, q: S.srv, offset: S.rows.length });
    S.loadingMore = false;
    if (r.ok) { const have = new Set(S.rows.map((x) => x.uid)); S.rows = S.rows.concat(r.rows.filter((x) => !have.has(x.uid))); S.more = r.more; S.total = r.total; } else say(r.message || 'Не удалось загрузить ещё');
    paintItems(); paintHead();
  }
  function switchFolder(f) {
    if (f === S.folder) return;
    S.picked.clear(); S.folder = f; S.filter = 'all'; S.q = ''; S.srv = ''; S.sel = ''; S.cur = null; S.reply = null; S.rows = []; S.total = 0; S.more = false; clearTimeout(searchTimer);
    loadList(); paintAll();
  }

  async function openMsg(uid) {
    if (uid === S.sel && S.cur && !S.cur.error) return;
    const row = S.rows.find((x) => x.uid === uid) || {};
    S.sel = uid; S.reading = true; S.images = trusted().has((row.addr || '').toLowerCase()); S.qopen = false; S.view = 'html'; S.confirmDel = false;
    S.cur = { head: true, uid, subject: row.subject, name: row.name, addr: row.addr, ts: row.ts, files: [], to: [], cc: [] };
    S.reply = null; S.attach = []; paintItems(); buildReader();
    if (!m.connected) {
      const r = S.rows.find((x) => x.uid === uid), d = !!(r && r.html);
      S.cur = { ...r, uid, unsub: d ? { kind: 'oneclick', target: 'hosting.example' } : null, to: [{ name: 'Вы', addr: S.email }], cc: [], body: DEMO_TEXT, html: d ? DEMO_HTML : '', blocked: d ? 1 : 0, files: r && r.att ? [{ name: 'Повестка.pdf', size: 184320, type: 'application/pdf' }, { name: 'Смета.xlsx', size: 52400, type: 'x' }] : [], reply_to: r ? r.addr : '', message_id: '', references: '' };
      S.reading = false; markLocal(uid, false); buildReader(); return;
    }
    const folder = S.folder, r = await call({ op: 'read', folder, uid, images: S.images, mark: !window.MAIL_NO_MARK });
    if (S.sel !== uid) return;
    S.reading = false;
    if (r.ok) { S.cur = r; if (r.was_unread) { markLocal(uid, false); refreshUnread(); } } else S.cur = { error: r.message || 'Не удалось открыть письмо' };
    paintItems(); buildReader();
  }
  const markLocal = (uid, unread) => { const r = S.rows.find((x) => x.uid === uid); if (r) r.unread = unread; paintItems(); paintHead(); };

  // ---- rendering: list side ----
  function buildList() {
    listEl.innerHTML = '<div class="ml-selbar" id="ml-selbar" hidden></div><div class="ml-top" id="ml-top"><div class="ml-fds" id="ml-fds"></div><div class="ml-search"><input id="ml-q" placeholder="Поиск по письмам" autocomplete="off"><button type="button" class="ml-adv" data-menu="adv" title="Расширенный поиск" aria-label="Расширенный поиск">' + I.tune + '</button></div><div class="ml-flts" id="ml-flts"></div></div><div class="ml-items" id="ml-items"></div>';
  }
  function runSearch(q) {
    const i = $('ml-q'); i.value = q; i.dispatchEvent(new Event('input', { bubbles: true })); clearTimeout(searchTimer);
    S.q = q; S.srv = q.trim(); loadList({ silent: true }); paintItems();
  }
  function paintAll() { paintHead(); paintFolders(); paintItems(); if (!S.cur || S.state !== 'ok') buildReader(); }
  function paintHead() {
    const un = S.unreadInbox ? `непрочитанных ${S.unreadInbox}` : '';
    $('ml-count').textContent = S.state === 'ok' ? [`${folderName(S.folder)}: ${S.total} ${plural(S.total, 'письмо', 'письма', 'писем')}`, S.folder === 'inbox' || !un ? un : '', m.connected ? '' : 'пример, ядро не подключено'].filter(Boolean).join(' · ') : '';
    if (m.connected && S.state === 'ok') setBadge('Почта', S.unreadInbox);
  }
  function folderName(f) { if (FOLDER_NAMES[f]) return FOLDER_NAMES[f]; const c = S.custom.find((x) => x.id === f); return c ? c.name : 'Папка'; }
  function paintFolders() {
    const top = $('ml-top'); if (!top) return;
    top.hidden = S.state !== 'ok';
    const cur = S.custom.find((x) => x.id === S.folder);
    $('ml-fds').innerHTML = S.folders.map((f) => `<button type="button" class="ml-fd${f === S.folder ? ' on' : ''}" data-fd="${f}">${FOLDER_NAMES[f]}${f === 'inbox' && S.unreadInbox ? `<i>${S.unreadInbox}</i>` : ''}</button>`).join('')
      + (S.custom.length ? `<button type="button" class="ml-fd${cur ? ' on' : ''}" data-menu="labels">${esc(cur ? cur.name : 'Метки')}<b class="ml-caret"></b></button>` : '');
    $('ml-flts').innerHTML = FILTERS.map(([k, t]) => `<button type="button" class="ml-fl${k === S.filter ? ' on' : ''}" data-fl="${k}">${t}</button>`).join('') + `<span class="ml-sp"></span><button type="button" class="ml-fl more" data-menu="list" title="Ещё" aria-label="Ещё">${I.more}</button>`;
  }
  function visibleRows() {
    const q = S.q.trim().toLowerCase();
    return S.srv === S.q.trim() || !q || /\w:/.test(q) ? S.rows : S.rows.filter((r) => `${r.subject} ${r.name} ${r.addr}`.toLowerCase().includes(q));
  }
  const MONTH_FULL = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  function dayLabel(ts) {
    if (!ts) return 'Ранее';
    const d = new Date(ts * 1000), t = new Date(), day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()), diff = Math.round((day(t) - day(d)) / 864e5);
    if (diff <= 0) return 'Сегодня'; if (diff === 1) return 'Вчера'; if (diff < 7) return 'На этой неделе';
    return d.getFullYear() === t.getFullYear() ? MONTH_FULL[d.getMonth()] : `${MONTH_FULL[d.getMonth()]} ${d.getFullYear()}`;
  }
  const CHECK = SVG('<path d="M5 12.5l4.5 4.5L19 7.5"/>', 2.6);
  const rowHtml = (r) => `<div class="ml-it${r.uid === S.sel ? ' on' : ''}${r.unread ? ' un' : ''}${S.picked.has(r.uid) ? ' pk' : ''}" role="button" tabindex="0" data-uid="${esc(r.uid)}"><span class="ml-avw" data-chk title="Выбрать">${avatar(r.name, r.addr)}<span class="ml-ck">${CHECK}</span></span><span class="ml-tx"><span class="ml-l1"><b>${esc(r.name || '(без отправителя)')}</b><time>${short(r.ts)}</time></span><span class="ml-l2">${esc(r.subject || '(без темы)')}</span></span><span class="ml-mk"><em class="mst${r.flagged ? ' fl' : ''}" data-star title="${r.flagged ? 'Снять пометку' : 'Пометить'}">${I.star}</em>${r.att ? `<em>${I.clip}</em>` : ''}${r.unread ? '<i class="ml-dot" aria-label="Не прочитано"></i>' : ''}</span><span class="ml-hv"><em data-star class="${r.flagged ? 'fl' : ''}" title="${r.flagged ? 'Снять пометку' : 'Пометить'}">${I.star}</em><em data-q="archive" title="В архив">${I.archive}</em><em data-q="del" title="Удалить">${I.trash}</em><em data-q="seen" title="${r.unread ? 'Прочитано' : 'Не прочитано'}">${r.unread ? I.open : I.mail}</em></span></div>`;
  function paintItems() {
    const el = $('ml-items'); if (!el) return;
    if (S.state === 'loading') { el.innerHTML = Array.from({ length: 7 }, () => '<div class="ml-sk"><i></i><span><b></b><b></b></span></div>').join(''); return; }
    if (S.state === 'none') { el.innerHTML = '<div class="ml-empty"><b>Почта не подключена</b>Добавьте адрес и пароль приложения, и здесь появятся письма.<button class="cm-try primary" id="ml-connect">Подключить почту</button></div>'; return; }
    if (S.state === 'error') { el.innerHTML = `<div class="ml-empty"><b>Не удалось получить письма</b>${esc(S.err)}<button class="cm-try" id="ml-retry">Повторить</button></div>`; return; }
    const rows = visibleRows(), keep = el.scrollTop; let day = '';
    el.innerHTML = (rows.length ? rows.map((r) => { const g = dayLabel(r.ts), head = g !== day ? `<div class="ml-day">${g}</div>` : ''; day = g; return head + rowHtml(r); }).join('')
      : `<div class="ml-empty">${S.q.trim() ? 'Ничего не найдено' : S.filter !== 'all' ? 'В этом фильтре писем нет' : 'Здесь пусто'}</div>`)
      + (S.more && !S.q.trim() ? `<button type="button" class="ml-more" id="ml-more"${S.loadingMore ? ' disabled' : ''}>${S.loadingMore ? 'Загружаю…' : `Показать ещё (${Math.max(0, S.total - S.rows.length)})`}</button>` : '');
    if (window.MailX) window.MailX.paintSel();
    el.scrollTop = keep;
  }

  // ---- rendering: reader ----
  function buildReader() {
    if (S.state !== 'ok') { readEl.innerHTML = ''; return; }
    const c = S.cur;
    if (!c) { readEl.innerHTML = '<div class="ml-hint">' + ic('mail', 'var(--ic)', 40) + '<b>Выберите письмо слева</b><span>Текст появится здесь, отвечать можно сразу под ним.</span></div>'; return; }
    if (c.error) { readEl.innerHTML = `<div class="ml-empty"><b>Не удалось открыть письмо</b>${esc(c.error)}<button class="cm-try" id="ml-retry-msg">Повторить</button></div>`; return; }
    readEl.innerHTML = '<header class="ml-rh" id="ml-rh"></header><div class="ml-files" id="ml-files" hidden></div><div class="ml-note" id="ml-note" hidden></div><div class="ml-bd" id="ml-bd"></div><div class="ml-reply" id="ml-rp" hidden></div>';
    paintHeader(); paintFiles(); paintBody(); paintReply();
  }
  const toLine = (c) => { const l = (c.to || []).map((x) => x.name || x.addr); const cc = (c.cc || []).map((x) => x.name || x.addr); return (l.length ? `Кому: ${l.slice(0, 3).join(', ')}${l.length > 3 ? ` и ещё ${l.length - 3}` : ''}` : '') + (cc.length ? ` · Копия: ${cc.slice(0, 2).join(', ')}${cc.length > 2 ? '…' : ''}` : ''); };
  function paintHeader() {
    const h = $('ml-rh'); if (!h || !S.cur) return; const c = S.cur, row = S.rows.find((x) => x.uid === c.uid) || {}, loaded = !c.head;
    const can = { trash: S.folders.includes('trash') && S.folder !== 'trash', archive: S.folders.includes('archive') && S.folder !== 'archive' };
    const btn = (d, icon, label, cls = '', title = '') => `<button type="button" class="ml-ab ${cls}" data-do="${d}" title="${esc(title || label)}"${loaded ? '' : ' disabled'}>${icon}<span>${label}</span></button>`;
    h.innerHTML = `<h3>${esc(c.subject || '(без темы)')}</h3><div class="ml-from">${avatar(c.name, c.addr)}<div><span class="ml-nm"><b>${esc(c.name)}</b>${loaded && c.unsub ? '<button type="button" class="ml-unsub" data-do="unsub">Отписаться</button>' : ''}</span><small>${esc(c.addr)} · ${esc(full(c.ts))}</small>${loaded && toLine(c) ? `<small class="ml-to2">${esc(toLine(c))}</small>` : ''}</div></div>
      <div class="ml-bar">${S.folder === 'drafts' ? btn('edit', I.reply, 'Изменить', 'pri', 'Продолжить письмо') : `${btn('reply', I.reply, 'Ответить', 'pri')}${btn('all', I.all, 'Всем', '', 'Ответить всем')}${btn('fwd', I.fwd, 'Переслать')}`}<span class="ml-sp"></span>
        ${btn('star', I.star, '', `ic${row.flagged ? ' on' : ''}`, row.flagged ? 'Снять пометку' : 'Пометить')}${btn('seen', row.unread ? I.open : I.mail, '', 'ic', row.unread ? 'Отметить прочитанным' : 'Отметить непрочитанным')}
        ${can.archive ? btn('archive', I.archive, '', 'ic', 'В архив') : ''}${btn('del', I.trash, S.confirmDel ? 'Удалить навсегда?' : '', `ic${S.confirmDel ? ' ask' : ''}`, can.trash ? 'В корзину' : 'Удалить навсегда')}${btn('more', I.more, '', 'ic', 'Ещё')}</div>`;
  }
  function paintFiles() {
    const el = $('ml-files'); if (!el || !S.cur) return; const fs = S.cur.files || [];
    el.hidden = !fs.length;
    el.innerHTML = fs.map((f, i) => { const sv = S.saved[`${S.cur.uid}:${i}`]; return `<button type="button" class="ml-file${sv ? ' done' : ''}" data-save="${i}" title="${sv ? 'Показать в папке' : 'Сохранить в Загрузки'}">${I.clip}<b>${esc(f.name)}</b><small>${size(f.size)}</small><span>${sv ? 'в папке' : I.down}</span></button>`; }).join('');
  }
  function paintBody() {
    const bd = $('ml-bd'), c = S.cur; if (!bd || !c) return;
    const note = $('ml-note'), html = !!c.html;
    if (S.reading) { bd.innerHTML = '<div class="ml-skb"><i></i><i></i><i></i><i class="s"></i></div>'; return; }
    const showHtml = html && S.view === 'html';
    note.hidden = !html;
    if (html) {
      const addr = (c.addr || '').toLowerCase(), tr = trusted().has(addr);
      const left = !showHtml ? '<span></span>' : c.blocked && !S.images ? `<span>${I.img}Картинки скрыты (${c.blocked})</span><button type="button" class="ml-nb" data-do="images">Показать</button><button type="button" class="ml-nb" data-do="trust" title="Всегда показывать картинки от ${esc(addr)}">Всегда показывать</button>`
        : S.images && tr ? `<span>${I.img}Картинки показываются для ${esc(addr)}</span><button type="button" class="ml-nb" data-do="untrust">Не показывать</button>` : '<span></span>';
      note.innerHTML = `${left}<span class="ml-sp"></span><button type="button" class="ml-nb${showHtml ? ' on' : ''}" data-view="html">Оформление</button><button type="button" class="ml-nb${showHtml ? '' : ' on'}" data-view="text">Текст</button>`;
    }
    if (showHtml) {
      bd.className = 'ml-bd paper'; bd.innerHTML = ''; bd.appendChild(mkFrame(c.html));
    } else { bd.className = 'ml-bd'; bd.innerHTML = `<div class="ml-text">${c.body ? fmtText(c.body) : '<p class="ml-dim">(пустое письмо)</p>'}</div>`; }
  }
  function mkFrame(doc) {
    const f = document.createElement('iframe'); f.className = 'ml-frame'; f.setAttribute('sandbox', 'allow-same-origin'); f.setAttribute('referrerpolicy', 'no-referrer'); f.title = 'Текст письма';
    f.addEventListener('load', () => { try { const d = f.contentDocument; d.addEventListener('click', onLink); d.addEventListener('keydown', onFrameKey); const w = d.documentElement.scrollWidth, cw = f.clientWidth; if (w > cw + 2 && cw > 200) d.body.style.zoom = String(cw / w); } catch (e) { /* frame not reachable */ } });
    f.srcdoc = doc; return f;
  }
  const attachHtml = (list) => (list.length ? `<div class="ml-chips">${list.map((a) => `<span class="ml-chip">${esc(a.name)}<small>${size(a.size)}</small><button type="button" data-drop="${esc(a.id)}" aria-label="Убрать вложение">×</button></span>`).join('')}</div>` : '');
  function paintReply() {
    const el = $('ml-rp'), c = S.cur; if (!el || !c) return;
    const r = S.reply; el.hidden = !r; readEl.classList.toggle('replying', !!r); if (!r) { el.innerHTML = ''; return; }
    el.innerHTML = `<div class="ml-to"><span>${r.mode === 'all' ? 'Ответ всем' : 'Ответ'}</span> Кому: <b>${esc(c.reply_to)}</b></div>${r.mode === 'all' ? `<label class="ml-cc"><span>Копия</span><input id="ml-rcc" value="${esc(r.cc)}" placeholder="адреса через запятую" autocomplete="off"></label>` : ''}
      <div id="ml-rte"></div><div class="ml-qc"><span>К ответу приложится исходное письмо, с оформлением</span><button type="button" class="ml-nb" data-do="qshow">${S.qopen ? 'Скрыть' : 'Показать'}</button></div>${S.qopen ? '<div class="ml-qv" id="ml-qv"></div>' : ''}${attachHtml(S.attach)}<div class="ml-ract"><button class="cm-try" data-do="attach">Прикрепить файлы</button><span class="ml-sp"></span><button class="cm-try" data-do="cancel">Отмена</button><button class="cm-try primary" data-do="send"${S.sending ? ' disabled' : ''}>${S.sending ? 'Отправляю…' : 'Отправить'}</button></div>`;
    S.ed = window.MailC.mount($('ml-rte'), { html: S.drafts[c.uid] || '', placeholder: 'Ваш ответ', compact: true, onSubmit: () => doAction('send') }); S.ed.focus();
    const qv = $('ml-qv'); if (qv) { if (c.html) qv.appendChild(mkFrame(c.html)); else qv.innerHTML = `<div class="ml-text">${fmtText(c.body)}</div>`; }
  }

  // ---- actions ----
  function unsub() {
    const c = S.cur, u = c && c.unsub; if (!u) return;
    const text = u.kind === 'oneclick' ? `Jarvis отправит запрос на отписку на ${u.target}. Рассылки от этого отправителя прекратятся.`
      : u.kind === 'web' ? `Откроется страница отписки ${u.target} в браузере, там нужно подтвердить отписку.` : `Jarvis отправит письмо с просьбой об отписке на ${u.target}.`;
    window.MailX.dlg({ title: `Отписаться от ${c.name || c.addr}?`, body: text, ok: 'Отписаться', onOk: async () => {
      if (!m.connected) { say('Демо: отписка не выполняется'); return true; }
      const r = await call({ op: 'unsubscribe', folder: S.folder, uid: c.uid });
      if (!r.ok) { say(r.error === 'blocked_host' ? 'Адрес отписки выглядит небезопасным, отписка отменена' : r.message || 'Не удалось отписаться'); return false; }
      say(r.how === 'web' ? 'Страница отписки открыта в браузере' : r.how === 'mail' ? 'Письмо с просьбой об отписке отправлено' : 'Вы отписались от рассылки'); return true;
    } });
  }
  async function pick(into) {
    if (!m.connected) { say('Демо: здесь откроется выбор файлов'); return; }
    const r = await call({ op: 'pick' });
    if (r.added && r.added.length) into.push(...r.added);
    if (!r.ok) say(r.error === 'too_big' ? 'Вложения слишком большие (до 25 МБ)' : 'Не удалось добавить файл');
  }
  async function dropAttach(id, list) { const i = list.findIndex((a) => a.id === id); if (i >= 0) list.splice(i, 1); if (m.connected) await call({ op: 'drop', id }); }
  async function sendMail(payload, done) {
    if (!m.connected) { say('Демо: письмо не отправляется'); done(true); return; }
    const r = await call({ op: 'send', ...payload });
    const ERR = { bad_to: 'Укажите адрес получателя', empty: 'Введите текст письма или добавьте вложение', bad_attachment: 'Вложение потерялось, прикрепите его заново' };
    if (r.ok) { say('Письмо отправлено'); done(true); } else { say(ERR[r.error] || r.message || 'Не удалось отправить'); done(false); }
  }
  const rowOf = (uid) => S.rows.find((x) => x.uid === uid);
  function startReply(mode) {
    const c = S.cur, own = (S.email || '').toLowerCase(), first = (c.reply_to || '').toLowerCase();
    const cc = mode === 'all' ? [...(c.to || []), ...(c.cc || [])].map((x) => x.addr).filter((a, i, arr) => a.toLowerCase() !== own && a.toLowerCase() !== first && arr.indexOf(a) === i).join(', ') : '';
    S.reply = { mode, cc }; S.attach = []; paintReply();
  }
  function forward() {
    const c = S.cur, subj = /^(fwd?|пересл|fw):/i.test(c.subject || '') ? c.subject : `Fwd: ${c.subject || ''}`;
    openCompose({ subject: subj, quote: { folder: S.folder, uid: c.uid, mode: 'fwd' }, body: `\n\n---------- Пересланное письмо ----------\nОт: ${c.name} <${c.addr}>\nДата: ${c.date || full(c.ts)}\nТема: ${c.subject || ''}` });
  }
  function removeCur(to) { S.confirmDel = false; window.MailX.removeRows([S.sel], to, to === '' ? { now: true } : {}); }
  async function doAction(d) {
    const c = S.cur; if (!c && d !== 'cancel') return;
    if (d === 'reply' || d === 'all') startReply(d);
    else if (d === 'fwd') forward();
    else if (d === 'unsub') unsub();
    else if (d === 'edit') openCompose({ to: (c.to || []).map((x) => x.addr).join(', '), cc: (c.cc || []).map((x) => x.addr).join(', '), more: !!(c.cc || []).length, subject: c.subject || '', body: c.body || '', replace: c.uid });
    else if (d === 'more') window.MailX.headerMenu(document.querySelector('[data-do=more]'));
    else if (d === 'cancel') { for (const x of S.attach) if (m.connected) call({ op: 'drop', id: x.id }); S.reply = null; S.attach = []; paintReply(); }
    else if (d === 'attach') { S.drafts[c.uid] = S.ed.html(); await pick(S.attach); paintReply(); }
    else if (d === 'qshow') { if (S.ed) S.drafts[c.uid] = S.ed.html(); S.qopen = !S.qopen; paintReply(); }
    else if (d === 'trust') { setTrust((c.addr || '').toLowerCase(), true); await doAction('images'); }
    else if (d === 'untrust') {
      setTrust((c.addr || '').toLowerCase(), false); S.images = false;
      if (m.connected) { const r = await call({ op: 'read', folder: S.folder, uid: c.uid, images: false, mark: false }); if (r.ok) S.cur = { ...S.cur, html: r.html, blocked: r.blocked }; } else S.cur.blocked = 1;
      paintBody();
    }
    else if (d === 'images') { if (m.connected) { const r = await call({ op: 'read', folder: S.folder, uid: c.uid, images: true, mark: false }); if (r.ok) { S.cur = { ...S.cur, html: r.html, blocked: 0 }; } } S.images = true; if (!m.connected) S.cur.blocked = 0; paintBody(); }
    else if (d === 'star' || d === 'seen') {
      const row = rowOf(c.uid); if (!row) return;
      const flag = d === 'star' ? 'flagged' : 'seen', on = d === 'star' ? !row.flagged : !!row.unread;
      if (m.connected) { const r = await call({ op: 'flag', folder: S.folder, uid: c.uid, flag, on }); if (!r.ok) { say(r.message || 'Не удалось изменить'); return; } }
      if (d === 'star') row.flagged = on; else row.unread = !on;
      if (d === 'seen') say(on ? 'Отмечено прочитанным' : 'Отмечено непрочитанным');
      if (m.connected) refreshUnread();
      paintHeader(); paintItems(); paintHead();
    }
    else if (d === 'archive') await removeCur('archive');
    else if (d === 'del') {
      if (S.folders.includes('trash') && S.folder !== 'trash') { await removeCur('trash'); return; }
      if (!S.confirmDel) { S.confirmDel = true; paintHeader(); setTimeout(() => { if (S.confirmDel) { S.confirmDel = false; paintHeader(); } }, 3500); return; }
      await removeCur('');
    }
    else if (d === 'send') {
      const text = S.ed.text().trim(); S.drafts[c.uid] = S.ed.html();
      if (!text && !S.attach.length) { say('Введите текст ответа или добавьте вложение'); return; }
      S.sending = true; paintReply();
      await sendMail({ to: c.reply_to, cc: S.reply.mode === 'all' ? ($('ml-rcc') ? $('ml-rcc').value : S.reply.cc) : '', subject: /^re:/i.test(c.subject) ? c.subject : `Re: ${c.subject}`, body: text, html: S.ed.html(), quote: { folder: S.folder, uid: c.uid, mode: 'reply' }, in_reply_to: c.message_id, references: c.references, attach: S.attach.map((x) => x.id) },
        (ok) => { S.sending = false; if (ok) { S.reply = null; S.attach = []; delete S.drafts[c.uid]; } paintReply(); });
    }
  }
  async function saveFile(i) {
    const c = S.cur, key = `${c.uid}:${i}`;
    if (S.saved[key]) { if (m.connected) await call({ op: 'reveal', path: S.saved[key] }); return; }
    if (!m.connected) { say('Демо: файл сохранится в «Загрузки»'); return; }
    const r = await call({ op: 'save', folder: S.folder, uid: c.uid, idx: i });
    if (r.ok) { S.saved[key] = r.path; say(`Сохранено в «Загрузки»: ${r.name}`); paintFiles(); } else say(r.error === 'too_big' ? 'Файл слишком большой' : 'Не удалось сохранить файл');
  }
  function onLink(e) {
    const a = e.target.closest && e.target.closest('a[data-url]'); if (!a) return;
    e.preventDefault(); openLink(a.dataset.url);
  }
  function onFrameKey(e) { if (e.key === 'Escape') document.activeElement && document.activeElement.blur(); }
  async function openLink(url) {
    if (/^mailto:/i.test(url)) { openCompose({ to: url.slice(7).split('?')[0] }); return; }
    if (!/^https?:/i.test(url)) return;
    if (m.connected) await J.send('open_url', { url }); else say('Демо: ссылка откроется в браузере');
  }

  root.addEventListener('click', async (e) => {
    const a = e.target.closest('.ml-a'); if (a) { e.preventDefault(); openLink(a.dataset.url); return; }
    const it = e.target.closest('.ml-it'); if (it) { openMsg(it.dataset.uid); return; }
    const dr = e.target.closest('[data-drop]'); if (dr) { await dropAttach(dr.dataset.drop, S.attach); paintReply(); return; }
    const sv = e.target.closest('[data-save]'); if (sv) { saveFile(+sv.dataset.save); return; }
    const fd = e.target.closest('[data-fd]'); if (fd) { switchFolder(fd.dataset.fd); return; }
    const fl = e.target.closest('[data-fl]'); if (fl) { if (fl.dataset.fl !== S.filter) { S.filter = fl.dataset.fl; S.rows = S.rows; loadList({ silent: true }); paintFolders(); } return; }
    const vw = e.target.closest('.ml-nb[data-view]'); if (vw) { S.view = vw.dataset.view; paintBody(); return; }
    const b = e.target.closest('button'); if (!b) return;
    if (b.id === 'ml-connect') { window.openExtSetup({ id: 'feature_mail_client', name: 'Почта', setup: 'mail', installed: false }); return; }
    if (b.id === 'ml-retry') { ready = false; loadList(); return; }
    if (b.id === 'ml-retry-msg') { const u = S.sel; S.sel = ''; openMsg(u); return; }
    if (b.id === 'ml-refresh') { loadList({ refresh: true, silent: !!S.rows.length }); return; }
    if (b.id === 'ml-more') { loadMore(); return; }
    if (b.id === 'ml-new') { openCompose(); return; }
    if (b.dataset.do) doAction(b.dataset.do);
  });
  root.addEventListener('input', (e) => {
    if (e.target.id !== 'ml-q') return;
    S.q = e.target.value; paintItems(); clearTimeout(searchTimer);
    const q = S.q.trim();
    if (q === S.srv) return;
    if (!q) { S.srv = ''; loadList({ silent: true }); return; }
    if (q.length >= 2 && m.connected) searchTimer = setTimeout(() => { S.srv = q; loadList({ silent: true }); }, 550);
  });
  root.addEventListener('keydown', (e) => {
    const row = e.target.closest && e.target.closest('.ml-it'); if (row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openMsg(row.dataset.uid); return; }
    if (VIEW !== 'mail' || !modal.hidden || e.target.closest('input, textarea, select')) return;
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    const rows = visibleRows(); if (!rows.length) return;
    const i = rows.findIndex((r) => r.uid === S.sel), n = Math.min(rows.length - 1, Math.max(0, i + (e.key === 'ArrowDown' ? 1 : -1)));
    e.preventDefault(); openMsg(rows[n].uid);
    const el = $('ml-items') && $('ml-items').querySelector(`[data-uid="${rows[n].uid}"]`); if (el) el.scrollIntoView({ block: 'nearest' });
  });

  const openCompose = (init) => window.MailC.open(init);

  window.MailApp = { S, root, listEl, readEl, toast, call, say, esc, I, ic, paintAll, paintItems, paintHeader, paintHead, paintFolders, buildReader, openMsg, loadList, refreshUnread, switchFolder, doAction, rowOf, visibleRows,
    openCompose, folderName, FOLDER_NAMES, size: (b) => size(b), pick, dropAttach, sendMail, attachHtml, runSearch, modal, mbox };
  buildList();
  J.on('conn', () => { ready = false; if (VIEW === 'mail') loadList(); });
  clearInterval(poll);
  poll = setInterval(() => { if (VIEW === 'mail' && m.connected && S.state === 'ok' && !S.srv && !S.q && S.filter === 'all' && S.rows.length <= 40 && !document.hidden) loadList({ silent: true, refresh: true }); }, 75000);
  window.renderMail = () => { if (S.state === 'ok' && m.connected) { paintAll(); loadList({ silent: true }); } else loadList(); };
})();
