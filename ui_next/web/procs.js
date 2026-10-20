// System screen, tabs "Процессы" and "Автозапуск": a Task Manager alternative. Data: bridge command `procs` (ui_next/bridge/procs.py), polled while the tab is open.
// Relies on globals of app.html: $, J, m, esc, VIEW. perf.js owns the "Обзор" tab (#pf-body); this file shows #pf-procs / #pf-start in its place.
(() => {
  const head = $('pf-tabs'), body = $('pf-body'), pbox = $('pf-procs'), sbox = $('pf-start'), vbox = $('pf-svc'), toast = $('pf-toast');
  const KB = 1024, MB = KB * KB, GB = MB * KB;
  const p1 = (n) => (Math.round(n * 10) / 10).toString().replace('.', ',');
  const bytes = (n) => (n >= GB ? `${p1(n / GB)} ГБ` : n >= MB ? `${Math.round(n / MB)} МБ` : `${Math.round(n / KB)} КБ`);
  const rate = (n) => (n >= MB ? `${p1(n / MB)} МБ/с` : n >= KB ? `${Math.round(n / KB)} КБ/с` : n > 0 ? '< 1 КБ/с' : '0');
  const ERR = { gone: 'Процесс уже завершён', protected: 'Системный процесс: завершать его нельзя', self: 'Это сам Jarvis', denied: 'Нет прав. Запустите Jarvis от имени администратора',
    no_path: 'Путь к файлу неизвестен', failed: 'Не получилось', bad_level: 'Неверный приоритет', timeout: 'Служба не успела ответить', disabled: 'Служба отключена: сначала задайте ручной или автоматический запуск', bad_act: 'Неизвестное действие',
    protected_svc: 'Без этой службы Windows не работает: её нельзя остановить или отключить' };
  const PRIO = [['low', 'Низкий'], ['below', 'Ниже обычного'], ['normal', 'Обычный'], ['above', 'Выше обычного'], ['high', 'Высокий']];
  const S = { tab: 'perf', key: 'cpu', dir: -1, q: '', sq: '', group: true, open: new Set(), sel: '', ask: '', procs: [], ram: null, cores: 1, items: null, tasks: null, svc: null, vq: '', vsel: '', vask: '', vbusy: false, beat: 0, busy: false };
  const SORT = { name: (r) => r.name.toLowerCase(), cpu: (r) => r.cpu, mem: (r) => r.mem, io: (r) => r.io, pid: (r) => r.pid };
  let toastTimer = 0;

  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3600); };
  const fail = (r) => say(ERR[r && r.error] || ERR.failed);
  const idOf = (r) => `${r.pid}:${r.started}`;
  // Task Manager style shading: a load share 0..1 becomes one of six steps (square root, so small loads still show), drawn by the .hx1-.hx5 classes
  const heat = (x) => `hx${x > 0 ? Math.min(5, Math.ceil(Math.sqrt(Math.min(1, x)) * 5)) : 0}`;
  const cpuX = (v) => v / 100, memX = (v) => Math.min(1, v / (S.ram ? S.ram.total / 3 : 4 * GB)), ioX = (v) => v / (40 * MB);
  // --x drives the thin load bar under the number (.ld in procs.css); same square-root scale as the shading
  const cell = (k, x, txt, zero) => `<td class="num ld ${k} ${heat(x)}${zero ? ' z' : ''}" style="--x:${Math.sqrt(Math.max(0, Math.min(1, x))).toFixed(2)}">${txt}</td>`;
  const loadCells = (cpu, mem, io) => cell('c-cpu', cpuX(cpu), cpu >= 0.05 ? p1(cpu) + '%' : '0%', cpu < 0.05) + cell('c-mem', memX(mem), bytes(mem), mem <= 0) + cell('c-io', ioX(io), rate(io), io <= 0);

  /* ---- processes ---- */
  function groups() {
    const q = S.q.trim().toLowerCase(), map = new Map();
    for (const r of S.procs) {
      if (q && !(r.name.toLowerCase().includes(q) || String(r.pid) === q || r.exe.toLowerCase().includes(q))) continue;
      const k = S.group ? r.name.toLowerCase() : idOf(r);
      let g = map.get(k);
      if (!g) map.set(k, g = { key: k, name: r.name, rows: [], cpu: 0, mem: 0, io: 0 });
      g.rows.push(r); g.cpu += r.cpu; g.mem += r.mem; g.io += r.io;
    }
    const f = SORT[S.key];
    const val = (g) => (g.rows.length === 1 || S.key === 'name' ? f(g.rows[0]) : S.key === 'pid' ? g.rows[0].pid : g[S.key]);
    const list = [...map.values()].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * S.dir; });
    for (const g of list) g.rows.sort((a, b) => b.cpu - a.cpu || b.mem - a.mem);
    return list;
  }
  function rowHtml(r, label, cls, extra) {
    const id = idOf(r);
    return `<tr class="pt-row${cls}${S.sel === id ? ' sel' : ''}" data-r="${esc(id)}"${extra || ''}><td class="pf-nm">${label}</td>${loadCells(r.cpu, r.mem, r.io)}<td class="num dim">${r.pid}</td></tr>`;
  }
  function groupHtml(g) {
    if (g.rows.length === 1) return rowHtml(g.rows[0], `<span class="pf-sp1"></span>${esc(g.name)}${g.rows[0].protected ? '<i class="pf-lock" title="Системный процесс">●</i>' : ''}`, '');
    const open = S.open.has(g.key), sum = { cpu: g.cpu, mem: g.mem, io: g.io };
    return `<tr class="pt-row grp" data-g="${esc(g.key)}" aria-expanded="${open}"><td class="pf-nm"><span class="pf-car">${open ? '▾' : '▸'}</span>${esc(g.name)} <span class="dim">(${g.rows.length})</span></td>${loadCells(sum.cpu, sum.mem, sum.io)}<td class="num dim"></td></tr>`
      + (open ? g.rows.map((r) => rowHtml(r, `<span class="pf-sp1 ch"></span>${esc(r.name)}`, ' ch')).join('') : '');
  }
  function bar() {
    const r = S.procs.find((x) => idOf(x) === S.sel);
    if (!r) return '<div class="pf-bar dim">Выберите процесс, чтобы завершить его, сменить приоритет или открыть папку.</div>';
    const ask = S.ask;
    const act = r.protected || r.self
      ? `<span class="dim">${r.self ? ERR.self : ERR.protected}</span>`
      : ask ? `<span class="cm-confirm">${ask === 'tree' ? 'Завершить вместе с дочерними процессами?' : 'Завершить процесс?'}<button class="cm-try danger" data-a="do-${ask}">Да</button><button class="cm-try" data-a="no">Нет</button></span>`
        : '<button class="cm-try danger" data-a="end">Завершить</button><button class="cm-try" data-a="tree">Завершить дерево</button>';
    return `<div class="pf-bar"><b class="pf-who">${esc(r.name)}</b><span class="dim">PID ${r.pid}${r.user ? ` · ${esc(r.user)}` : ''} · потоков ${r.threads}</span>${act}`
      + `<label class="pf-prio">Приоритет <select data-a="prio">${PRIO.map(([k, t]) => `<option value="${k}"${r.prio === k ? ' selected' : ''}>${t}</option>`).join('')}${r.prio ? '' : '<option value="" selected>—</option>'}</select></label>`
      + `<button class="cm-try" data-a="folder"${r.exe ? '' : ' disabled'}>Показать файл</button></div>`
      + (r.exe ? `<div class="pf-path dim" translate="no">${esc(r.exe)}</div>` : '');
  }
  function paintProcs() {
    const cpu = Math.min(100, S.procs.reduce((a, r) => a + r.cpu, 0)), mem = S.procs.reduce((a, r) => a + r.mem, 0), io = S.procs.reduce((a, r) => a + r.io, 0), used = S.ram ? S.ram.used : mem;
    // the column heads carry the totals, like Task Manager: the big number is the whole machine, the small line names the column
    const gs = groups(), th = (k, t, c, top, x) => `<th class="${c || ''}${x === undefined ? '' : ' ' + heat(x)}${x === undefined ? '' : ' c-' + k}" data-s="${k}" aria-sort="${S.key === k ? (S.dir < 0 ? 'descending' : 'ascending') : 'none'}">${top ? `<b>${top}</b>` : ''}<span>${t}${S.key === k ? (S.dir < 0 ? ' ↓' : ' ↑') : ''}</span></th>`;
    const keep = pbox.querySelector('.pf-tbl-wrap'), top = keep ? keep.scrollTop : 0, hadFocus = document.activeElement && document.activeElement.id === 'pf-q';
    pbox.innerHTML = `<div class="pf-tools"><input id="pf-q" type="search" placeholder="Поиск по имени или PID" value="${esc(S.q)}" autocomplete="off"><label class="pf-chk"><input type="checkbox" id="pf-grp"${S.group ? ' checked' : ''}> Группировать по программам</label>`
      + `<span class="dim pf-sum">Процессов: ${S.procs.length}</span></div>`
      + `<div class="pf-tbl-wrap"><table class="pf-tbl"><thead><tr>${th('name', 'Имя')}${th('cpu', 'Процессор', 'num', `${p1(cpu)}%`, cpuX(cpu))}${th('mem', 'Память', 'num', S.ram ? `${Math.round(used / S.ram.total * 100)}%` : bytes(mem), S.ram ? used / S.ram.total : 0)}${th('io', 'Диск', 'num', rate(io), ioX(io))}${th('pid', 'PID', 'num')}</tr></thead><tbody>${gs.map(groupHtml).join('') || '<tr><td colspan="5" class="dim">Ничего не найдено</td></tr>'}</tbody></table></div>${bar()}`;
    const w = pbox.querySelector('.pf-tbl-wrap'); if (w) w.scrollTop = top;
    if (hadFocus) { const q = $('pf-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
  }
  async function pull() {
    if (S.busy || VIEW !== 'perf' || S.tab !== 'procs') return;
    if (!m.connected) { demoProcs(); paintProcs(); return; }
    S.busy = true;
    try { const r = await J.send('procs', { op: 'list' }); if (r && r.ok) { S.procs = r.procs; S.cores = r.cores; S.ram = r.ram || null; const ae = document.activeElement; if (S.tab === 'procs' && !(ae && ae.tagName === 'SELECT' && pbox.contains(ae))) paintProcs(); } } finally { S.busy = false; }   // an open priority list is not redrawn under the cursor
  }
  function demoProcs() {
    const mk = (pid, name, cpu, mem, extra) => ({ pid, ppid: 1, name, exe: `C:\\Program Files\\${name}`, user: 'user', mem: mem * MB, cpu, threads: 12, started: 1, prio: 'normal', io: cpu * 2e4, protected: false, self: false, ...extra });
    S.procs = [mk(100, 'chrome.exe', 8.2, 410), mk(101, 'chrome.exe', 3.1, 220), mk(102, 'chrome.exe', .4, 140), mk(200, 'Jarvis.exe', 2.0, 320, { self: true }), mk(300, 'explorer.exe', .8, 95), mk(4, 'System', .3, 0, { protected: true })];
  }

  /* ---- startup ---- */
  const SCOPE = { user: 'Только для вас', machine: 'Для всех пользователей' };
  function paintStart() {
    const items = S.items;
    if (!items) { sbox.innerHTML = '<div class="rm-empty"><b>Читаю список…</b></div>'; return; }
    const q = S.sq.trim().toLowerCase(), hit = (e) => !q || e.name.toLowerCase().includes(q) || (e.path || '').toLowerCase().includes(q), shown = items.filter(hit), tasks = S.tasks === null ? null : S.tasks.filter(hit);
    const top = sbox.scrollTop, had = document.activeElement && document.activeElement.id === 'st-q';
    sbox.innerHTML = `<div class="pf-tools"><input id="st-q" type="search" placeholder="Поиск по имени или пути" value="${esc(S.sq)}" autocomplete="off"><span class="dim pf-sum">Программ: ${items.length}, включено ${items.filter((e) => e.enabled).length}</span></div><p class="pf-note dim">Программы, которые запускаются вместе с Windows. Выключенные остаются в списке и включаются обратно одним нажатием; ничего не удаляется.</p>`
      + (shown.length ? `<div class="pf-st">${shown.map((e) => `<div class="pf-si${e.enabled ? '' : ' off'}"><div class="pf-sn"><b>${esc(e.name)}</b><span class="dim">${SCOPE[e.scope] || ''}</span><span class="pf-path dim" translate="no">${esc(e.path)}</span></div>`
        + `<button class="cm-try" data-f="${esc(e.id)}">Показать файл</button><button type="button" class="pf-sw${e.enabled ? ' on' : ''}" role="switch" aria-checked="${e.enabled}" aria-label="${esc(e.name)}" data-id="${esc(e.id)}"></button></div>`).join('')}</div>`
        : q ? '<div class="rm-empty"><b>Ничего не найдено</b></div>' : '<div class="rm-empty"><b>Список пуст</b>Ни одна программа не запускается вместе с Windows.</div>')
      + '<h3 class="pf-sub">Задачи планировщика при входе</h3>'
      + (tasks === null ? '<p class="pf-note dim">Читаю задачи…</p>' : tasks.length ? `<div class="pf-st">${tasks.map((t) => `<div class="pf-si${t.enabled ? '' : ' off'}"><div class="pf-sn"><b>${esc(t.name)}</b><span class="pf-path dim" translate="no">${esc(t.path)}</span></div>`
        + `<button type="button" class="pf-sw${t.enabled ? ' on' : ''}" role="switch" aria-checked="${t.enabled}" aria-label="${esc(t.name)}" data-task="${esc(t.id)}"></button></div>`).join('')}</div>` : q ? '' : '<p class="pf-note dim">Таких задач нет.</p>');
    sbox.scrollTop = top;
    if (had) { const q2 = $('st-q'); q2.focus(); q2.setSelectionRange(q2.value.length, q2.value.length); }
  }
  async function loadTasks() {
    if (!m.connected) { S.tasks = []; return; }
    const r = await J.send('services', { op: 'tasks' }); S.tasks = r && r.ok ? r.items : [];
    if (S.tab === 'startup') paintStart();
  }
  async function loadStart() {
    if (!m.connected) { S.items = [{ id: 'd|1', name: 'Пример', cmd: '', path: 'C:\\Program Files\\Example\\example.exe', scope: 'user', enabled: true }, { id: 'd|2', name: 'Updater', cmd: '', path: 'C:\\Program Files\\Updater\\up.exe', scope: 'machine', enabled: false }]; paintStart(); return; }
    const r = await J.send('procs', { op: 'startup' });
    if (r && r.ok) { S.items = r.items; paintStart(); } else fail(r);
    loadTasks();
  }

  /* ---- services ---- */
  const ST = { running: 'Работает', stopped: 'Остановлена', paused: 'Приостановлена', start_pending: 'Запускается', stop_pending: 'Останавливается' };
  const SS = { automatic: 'Автоматически', manual: 'Вручную', disabled: 'Отключена' };
  function svcBar(sel) {
    if (!sel) return '<div class="pf-bar dim">Выберите службу, чтобы запустить, остановить или изменить тип запуска.</div>';
    const run = sel.status === 'running', q = { stop: 'Остановить службу?', restart: 'Перезапустить службу?' }[S.vask];
    const act = sel.critical ? `<span class="dim">${ERR.protected_svc}</span>` : q ? `<span class="cm-confirm">${q}<button class="cm-try danger" data-v="do">Да</button><button class="cm-try" data-v="no">Нет</button></span>`
      : run ? '<button class="cm-try danger" data-v="stop">Остановить</button><button class="cm-try" data-v="restart">Перезапустить</button>' : '<button class="cm-try" data-v="start">Запустить</button>';
    return `<div class="pf-bar"><b class="pf-who">${esc(sel.display)}</b><span class="dim" translate="no">${esc(sel.name)}</span>${act}<label class="pf-prio">Запуск <select data-v="type">${['automatic', 'manual', 'disabled'].map((k) => `<option value="${k === 'automatic' ? 'auto' : k}"${sel.start === k ? ' selected' : ''}>${SS[k]}</option>`).join('')}</select></label></div>`
      + (sel.desc ? `<div class="pf-path dim">${esc(sel.desc)}</div>` : '') + (sel.path ? `<div class="pf-path dim" translate="no">${esc(sel.path)}</div>` : '');
  }
  function paintSvc() {
    const items = S.svc;
    if (!items) { vbox.innerHTML = '<div class="rm-empty"><b>Читаю список…</b></div>'; return; }
    const q = S.vq.trim().toLowerCase(), list = items.filter((x) => !q || x.display.toLowerCase().includes(q) || x.name.toLowerCase().includes(q));
    const keep = vbox.querySelector('.pf-tbl-wrap'), top = keep ? keep.scrollTop : 0, hadFocus = document.activeElement && document.activeElement.id === 'sv-q';
    vbox.innerHTML = `<div class="pf-tools"><input id="sv-q" type="search" placeholder="Поиск по названию" value="${esc(S.vq)}" autocomplete="off"><button class="cm-try" data-v="reload">Обновить</button><span class="dim pf-sum">Служб: ${items.length}, работает ${items.filter((x) => x.status === 'running').length}</span></div>`
      + `<div class="pf-tbl-wrap"><table class="pf-tbl"><thead><tr><th><span>Название</span></th><th class="w9"><span>Состояние</span></th><th class="w9"><span>Запуск</span></th><th class="num w5"><span>PID</span></th></tr></thead><tbody>${list.map((x) => `<tr class="pt-row${S.vsel === x.name ? ' sel' : ''}" data-sv="${esc(x.name)}"><td class="pf-nm">${esc(x.display)}${x.critical ? '<i class="pf-lock" title="Системная служба">●</i>' : ''}</td><td class="${x.status === 'running' ? 'pf-ok' : 'dim'}"><i class="pf-dot ${esc(x.status)}"></i>${ST[x.status] || esc(x.status)}</td><td class="dim">${SS[x.start] || esc(x.start)}</td><td class="num dim">${x.pid || ''}</td></tr>`).join('') || '<tr><td colspan="4" class="dim">Ничего не найдено</td></tr>'}</tbody></table></div>${svcBar(items.find((x) => x.name === S.vsel))}`;
    const w = vbox.querySelector('.pf-tbl-wrap'); if (w) w.scrollTop = top;
    if (hadFocus) { const q2 = $('sv-q'); q2.focus(); q2.setSelectionRange(q2.value.length, q2.value.length); }
  }
  async function loadSvc() {
    if (!m.connected) { S.svc = [{ name: 'Spooler', display: 'Диспетчер печати', status: 'running', start: 'automatic', pid: 1204, path: 'C:\\Windows\\System32\\spoolsv.exe', desc: 'Пример', critical: false }, { name: 'RpcSs', display: 'Удалённый вызов процедур (RPC)', status: 'running', start: 'automatic', pid: 900, path: '', desc: '', critical: true }]; paintSvc(); return; }
    const r = await J.send('services', { op: 'list' });
    if (r && r.ok) { S.svc = r.items; paintSvc(); } else fail(r);
  }
  async function svcDo(name, act) {
    if (S.vbusy) return; S.vbusy = true; say('Выполняю…');
    try { const r = await J.send('services', { op: 'action', name, act }); if (r && r.ok) { say('Готово'); await loadSvc(); } else fail(r && r.error === 'protected' ? { error: 'protected_svc' } : r); } finally { S.vbusy = false; }
  }

  /* ---- tabs and events ---- */
  function show(tab) {
    S.tab = tab; clearInterval(S.beat); S.beat = 0;
    for (const b of head.querySelectorAll('[data-t]')) { const on = b.dataset.t === tab; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); }
    body.hidden = tab !== 'perf'; pbox.hidden = tab !== 'procs'; sbox.hidden = tab !== 'startup'; vbox.hidden = tab !== 'services';
    if (tab === 'procs') { pull(); S.beat = setInterval(pull, 2000); } else if (tab === 'startup') { S.items = null; S.tasks = null; paintStart(); loadStart(); } else if (tab === 'services') { S.vask = ''; paintSvc(); loadSvc(); } else if (typeof window.renderPerf === 'function') window.renderPerf();
  }
  head.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) show(b.dataset.t); });
  pbox.addEventListener('click', async (e) => {
    const sort = e.target.closest('[data-s]');
    if (sort) { const k = sort.dataset.s; S.dir = S.key === k ? -S.dir : (k === 'name' || k === 'pid' ? 1 : -1); S.key = k; paintProcs(); return; }
    const g = e.target.closest('[data-g]');
    if (g) { const k = g.dataset.g; S.open.has(k) ? S.open.delete(k) : S.open.add(k); paintProcs(); return; }
    const row = e.target.closest('[data-r]');
    if (row) { S.sel = S.sel === row.dataset.r ? '' : row.dataset.r; S.ask = ''; paintProcs(); return; }
    const a = e.target.closest('[data-a]'); if (!a) return;
    const r = S.procs.find((x) => idOf(x) === S.sel), act = a.dataset.a;
    if (act === 'end' || act === 'tree') { S.ask = act; paintProcs(); return; }
    if (act === 'no') { S.ask = ''; paintProcs(); return; }
    if (!r) return;
    if (act === 'folder') { const x = await J.send('procs', { op: 'folder', pid: r.pid, started: r.started }); if (!x || !x.ok) fail(x); return; }
    if (act.startsWith('do-')) {
      S.ask = ''; const x = await J.send('procs', { op: 'end', pid: r.pid, started: r.started, tree: act === 'do-tree' });
      if (x && x.ok) { say(`Завершено: ${r.name}`); S.sel = ''; S.busy = false; pull(); } else fail(x);
    }
  });
  pbox.addEventListener('change', async (e) => {
    if (e.target.id === 'pf-grp') { S.group = e.target.checked; paintProcs(); return; }
    if (e.target.dataset.a === 'prio') {
      const r = S.procs.find((x) => idOf(x) === S.sel); if (!r || !e.target.value) return;
      const x = await J.send('procs', { op: 'priority', pid: r.pid, started: r.started, level: e.target.value });
      if (x && x.ok) { r.prio = e.target.value; say('Приоритет изменён'); } else { fail(x); paintProcs(); }
    }
  });
  pbox.addEventListener('input', (e) => { if (e.target.id === 'pf-q') { S.q = e.target.value; paintProcs(); } });
  vbox.addEventListener('click', (e) => {
    const row = e.target.closest('[data-sv]');
    if (row) { S.vsel = S.vsel === row.dataset.sv ? '' : row.dataset.sv; S.vask = ''; paintSvc(); return; }
    const b = e.target.closest('button[data-v]'); if (!b) return;
    const a = b.dataset.v;
    if (a === 'reload') loadSvc();
    else if (a === 'stop' || a === 'restart') { S.vask = a; paintSvc(); }
    else if (a === 'no') { S.vask = ''; paintSvc(); }
    else if (a === 'start') svcDo(S.vsel, 'start');
    else if (a === 'do') { const act = S.vask; S.vask = ''; svcDo(S.vsel, act); }
  });
  vbox.addEventListener('change', (e) => { if (e.target.dataset.v === 'type' && S.vsel) svcDo(S.vsel, e.target.value); });
  vbox.addEventListener('input', (e) => { if (e.target.id === 'sv-q') { S.vq = e.target.value; paintSvc(); } });
  sbox.addEventListener('input', (e) => { if (e.target.id === 'st-q') { S.sq = e.target.value; paintStart(); } });
  sbox.addEventListener('click', async (e) => {
    const tk = e.target.closest('[data-task]');
    if (tk) {
      const t = S.tasks.find((x) => x.id === tk.dataset.task); if (!t) return;
      const x = await J.send('services', { op: 'task_set', id: t.id, enabled: !t.enabled });
      if (x && x.ok) { t.enabled = !t.enabled; paintStart(); say(t.enabled ? `Включено: ${t.name}` : `Выключено: ${t.name}`); } else fail(x);
      return;
    }
    const f = e.target.closest('[data-f]');
    if (f) { const x = await J.send('procs', { op: 'startup_folder', id: f.dataset.f }); if (!x || !x.ok) fail(x); return; }
    const sw = e.target.closest('[data-id]'); if (!sw) return;
    const it = S.items.find((x) => x.id === sw.dataset.id); if (!it) return;
    if (!m.connected) { it.enabled = !it.enabled; paintStart(); return; }
    const x = await J.send('procs', { op: 'startup_set', id: it.id, enabled: !it.enabled });
    if (x && x.ok) { it.enabled = !it.enabled; paintStart(); say(it.enabled ? `Включено: ${it.name}` : `Выключено: ${it.name}`); } else fail(x);
  });
  // leaving the System screen stops the polling; coming back to it opens the tab that was last used
  new MutationObserver(() => { if (VIEW !== 'perf') { clearInterval(S.beat); S.beat = 0; } else if (S.tab !== 'perf' && !S.beat && S.tab === 'procs') show('procs'); }).observe(document.getElementById('app'), { attributes: true, attributeFilter: ['data-view'] });
  J.on('conn', () => { if (VIEW === 'perf' && S.tab === 'startup') loadStart(); });
})();
