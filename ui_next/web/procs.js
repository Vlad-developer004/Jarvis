// System screen, tabs "Процессы" and "Автозапуск": a Task Manager alternative. Data: bridge command `procs` (ui_next/bridge/procs.py), polled while the tab is open.
// Relies on globals of app.html: $, J, m, esc, VIEW. perf.js owns the "Обзор" tab (#pf-body); this file shows #pf-procs / #pf-start in its place.
(() => {
  const head = $('pf-tabs'), body = $('pf-body'), pbox = $('pf-procs'), sbox = $('pf-start'), vbox = $('pf-svc'), toast = $('pf-toast');
  const KB = 1024, MB = KB * KB, GB = MB * KB;
  const p1 = (n) => (Math.round(n * 10) / 10).toString().replace('.', ',');
  const bytes = (n) => (n >= GB ? `${p1(n / GB)} ГБ` : n >= MB ? `${Math.round(n / MB)} МБ` : `${Math.round(n / KB)} КБ`);
  const rate = (n) => (n >= MB ? `${p1(n / MB)} МБ/с` : n >= KB ? `${Math.round(n / KB)} КБ/с` : n > 0 ? '< 1 КБ/с' : '0');
  const ERR = { gone: 'Процесс уже завершён', protected: 'Системный процесс: завершать его нельзя', self: 'Это сам Jarvis', denied: 'Нет прав. Запустите Jarvis от имени администратора',
    no_path: 'Путь к файлу неизвестен', failed: 'Не получилось', bad_level: 'Неверный приоритет', timeout: 'Служба не успела ответить', disabled: 'Служба отключена: сначала задайте ручной или автоматический запуск', bad_act: 'Неизвестное действие', bad_cores: 'Неверный набор ядер',
    protected_svc: 'Без этой службы Windows не работает: её нельзя остановить или отключить' };
  const PRIO = [['low', 'Низкий'], ['below', 'Ниже обычного'], ['normal', 'Обычный'], ['above', 'Выше обычного'], ['high', 'Высокий']];
  const S = { tab: 'perf', key: 'cpu', dir: -1, q: '', sq: '', group: true, open: new Set(), chips: new Set(), me: '', sel: '', ask: '', loaded: false, order: null, procs: [], ram: null, cores: 1, items: null, tasks: null, svc: null, vq: '', vsel: '', vask: '', vbusy: false, beat: 0, busy: false };
  const HINT = { name: 'Имя программы. Стрелка слева раскрывает группу её процессов', cpu: 'Загрузка процессора. В шапке общая загрузка и график за последнюю минуту', mem: 'Оперативная память процесса. В шапке занято от всей памяти',
    io: 'Скорость чтения и записи на диск', thr: 'Потоки выполнения: чем их больше, тем сложнее программа', user: 'Учётная запись, от имени которой запущен процесс', pid: 'Номер процесса в Windows. У группы своего номера нет' };
  const SORT = { name: (r) => r.name.toLowerCase(), cpu: (r) => r.cpu, mem: (r) => r.mem, io: (r) => r.io, thr: (r) => r.threads, user: (r) => (r.user || '').toLowerCase(), pid: (r) => r.pid };
  // filter chips: all selected chips must match; "odd" = launched from Temp/Downloads, or an own process whose file cannot be read
  const SUSP = /\\(temp|downloads|\$recycle\.bin)\\/i;
  const CHIPS = [['mine', 'Только мои', (r) => !!S.me && (r.user || '').toLowerCase() === S.me.toLowerCase()],
    ['game', 'Игры', (r) => !!r.game],
    ['hot', 'Высокая нагрузка', (r) => r.cpu >= 5 || r.mem >= GB || r.io >= 10 * MB],
    ['odd', 'Подозрительные', (r) => !r.protected && !r.self && (r.exe ? SUSP.test(r.exe) : !!S.me && (r.user || '').toLowerCase() === S.me.toLowerCase())]];
  // 60 s of totals for the header sparklines (one point per 2 s poll); a row or group that holds >= HOG_CPU % of the CPU for HOG_MS starts to pulse
  const HIST = 30, HOG_CPU = 15, HOG_MS = 10000, hist = { cpu: [], mem: [], io: [] }, hogSince = new Map(), signs = new Map();
  const isHog = (k) => hogSince.has(k) && Date.now() - hogSince.get(k) >= HOG_MS;
  function track() {
    const now = Date.now(), sums = new Map();
    let cpu = 0, io = 0, mem = 0;
    for (const r of S.procs) {
      cpu += r.cpu; io += r.io; mem += r.mem;
      sums.set(idOf(r), r.cpu); const g = 'g:' + r.name.toLowerCase(); sums.set(g, (sums.get(g) || 0) + r.cpu);
    }
    for (const [k, v] of sums) { if (v < HOG_CPU) hogSince.delete(k); else if (!hogSince.has(k)) hogSince.set(k, now); }
    for (const k of [...hogSince.keys()]) if (!sums.has(k)) hogSince.delete(k);
    for (const [k, v] of [['cpu', Math.min(100, cpu)], ['mem', S.ram ? (S.ram.used / S.ram.total) : 0], ['io', io]]) { hist[k].push(v); if (hist[k].length > HIST) hist[k].shift(); }
  }
  // header graphs: 60 x 20 px, the last minute; CPU and disk start at zero, memory is scaled to its own range (it barely moves); a dashed line until 6 points exist
  const SPAN = { cpu: 10, mem: 0.02, io: MB };
  const spark = (a, k) => {
    if (a.length < 6) return '<svg class="sp empty" viewBox="0 0 60 20" aria-hidden="true"><line x1="0" y1="18" x2="60" y2="18"/></svg>';
    let lo = k === 'mem' ? Math.min(...a) : 0, hi = Math.max(...a);
    if (k !== 'mem') hi *= 1.15;
    if (hi - lo < SPAN[k]) { const mid = (hi + lo) / 2; lo = k === 'mem' ? mid - SPAN[k] / 2 : 0; hi = lo + SPAN[k]; }
    const xy = a.map((v, i) => [i / (a.length - 1) * 60, 18 - Math.max(0, Math.min(1, (v - lo) / (hi - lo))) * 16]);
    const pts = xy.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' '), last = xy[xy.length - 1];
    return `<svg class="sp" viewBox="0 0 60 20" aria-hidden="true"><polygon points="${xy[0][0].toFixed(1)},20 ${pts} 60,20"/><polyline points="${pts}"/><circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="1.8"/></svg>`;
  };
  // last paint's cell texts and CPU values: a changed number fades in, a row whose CPU jumped by JUMP_CPU points flashes for half a second
  const JUMP_CPU = 5; let prevT = new Map(), nextT = new Map(), prevC = new Map(), nextC = new Map();
  // the figure bright, the unit pale ("1,9 ГБ", "7,7%", "< 1 КБ/с")
  const nu = (t) => { const x = /^(<?\s?\d+(?:,\d+)?)\s*(.*)$/.exec(t); return x ? `<span class="n">${x[1]}</span>${x[2] ? `<span class="u${x[2] === '%' ? ' pc' : ''}">${x[2]}</span>` : ''}` : `<span class="n">${t}</span>`; };
  // Icons: the program's own icon (bridge op `icons`, kept as blob URLs per file). A program without one, or until it arrives, gets a glyph by kind
  // (gear = service, speaker = audio, chip = graphics, globe = network, shield = security, Windows logo = system, gamepad = game, window = other).
  const GLYPH = { lock: 'M7 11V8a5 5 0 0110 0v3M5 11h14v9H5z', app: 'M4 5h16v14H4zM4 9h16', user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4 21c0-4 4-6 8-6s8 2 8 6', bolt: 'M13 2L5 14h6l-1 8 8-12h-6z',
    audio: 'M4 9h4l5-4v14l-5-4H4zM16 9a4 4 0 010 6M18.5 6.5a8 8 0 010 11', net: 'M12 3a9 9 0 100 18 9 9 0 000-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18', win: 'M4 5l7-1v7H4zM13 4l7-1v8h-7zM4 13h7v7l-7-1zM13 13h7v8l-7-1z' };
  const gl = (k, s = 16) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${GLYPH[k]}"/></svg>`;
  const glyph = (k, s) => (GLYPH[k] ? gl(k, s) : ic(k, 'currentColor', s));
  const inWin = (p) => /^[a-z]:\\windows\\/i.test(p || '');
  function kindOf(r) {
    const n = r.name.toLowerCase();
    if (r.game) return 'pad';
    if (/audio|sound|realtek|nahimic|waves|speaker/.test(n)) return 'audio';
    if (/nvidia|nvcontainer|igfx|amd|radeon|dwm|gpu|display|graphics/.test(n)) return 'chip';
    if (/vpn|wireguard|tailscale|zerotier|network|wlan|dns|firewall/.test(n)) return 'net';
    if (/defender|msmpeng|nissrv|antimalware|smartscreen|security/.test(n)) return 'shield';
    if (/svc|service|host\.exe|broker|spool|updater|helper|agent/.test(n)) return 'gear';
    return r.protected || inWin(r.exe) ? 'win' : 'app';
  }
  const svcKind = (x) => { const k = kindOf({ name: `${x.display} ${x.name}`, exe: x.path, protected: false, game: false }); return k === 'app' || k === 'win' ? 'gear' : k; };   // a service is a gear unless its name says more
  const genIc = (kind, tint) => `<i class="pf-ic gen${tint ? ' ' + tint : ''}">${glyph(kind, 14)}</i>`;
  const icons = new Map(), iconWait = new Set(), picons = new Map(), pathWait = new Set();
  const exeKey = (r) => (r.exe || '').toLowerCase();
  const blobUrl = (b64) => { if (!b64) return ''; try { return URL.createObjectURL(new Blob([Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))], { type: 'image/png' })); } catch (e) { return ''; } };
  const ico = (r) => {
    const u = icons.get(exeKey(r));
    return u ? `<img class="pf-ic" src="${u}" alt="" draggable="false">` : genIc(kindOf(r), r.protected || inWin(r.exe) ? 'sys' : r.game ? 'game' : '');
  };
  const tags = (r) => (r.self ? '<span class="pf-tag me">Jarvis</span>' : '') + (r.game ? '<span class="pf-tag game">игра</span>' : '') + (r.protected ? `<i class="pf-lock" title="Системный процесс: завершать нельзя">${gl('lock', 12)}</i>` : '');
  function wantIcons(gs) {
    if (!m.connected) return;
    const need = [], seen = new Set();
    for (const g of gs) { const r = g.rows.find((x) => x.exe) || g.rows[0], k = exeKey(r); if (k && !icons.has(k) && !iconWait.has(k) && !seen.has(k)) { seen.add(k); need.push(r); if (need.length >= 24) break; } }
    if (!need.length) return;
    for (const r of need) iconWait.add(exeKey(r));
    J.send('procs', { op: 'icons', items: need.map((r) => ({ pid: r.pid, started: r.started })) }).then((x) => {
      let got = false;
      for (const r of need) {
        const url = blobUrl(x && x.ok && x.icons ? x.icons[idOf(r)] : ''), d = x && x.ok && x.desc ? x.desc[idOf(r)] : '';
        if (d) descs.set(exeKey(r), d);
        got = got || !!url || !!d; icons.set(exeKey(r), url); iconWait.delete(exeKey(r));
      }
      if ((got || need.length >= 24) && S.tab === 'procs' && VIEW === 'perf') paintProcs();
    }, () => { for (const r of need) iconWait.delete(exeKey(r)); });
  }
  // startup entries and services: the program is named by a path or command line; one icon per .exe, requested in batches while the list is on screen
  const exeOf = (cmd) => { const x = /^\s*"?([^"]+?\.exe)(?=[\s"]|$)/i.exec(cmd || ''); return x ? x[1] : ''; };
  const icoPath = (cmd, kind, tint) => { const u = picons.get(exeOf(cmd).toLowerCase()); return u ? `<img class="pf-ic" src="${u}" alt="" draggable="false">` : genIc(kind, tint); };
  function wantPaths(cmds, repaint) {
    if (!m.connected) return;
    const need = [...new Set(cmds.map(exeOf).filter(Boolean))].filter((p) => !picons.has(p.toLowerCase()) && !pathWait.has(p.toLowerCase())).slice(0, 24);
    if (!need.length) return;
    for (const p of need) pathWait.add(p.toLowerCase());
    J.send('procs', { op: 'icons', items: need.map((p) => ({ path: p })) }).then((x) => {
      let got = false;
      for (const p of need) { const url = blobUrl(x && x.ok && x.icons ? x.icons['p:' + p] : ''); got = got || !!url; picons.set(p.toLowerCase(), url); pathWait.delete(p.toLowerCase()); }
      if (got || need.length >= 24) repaint();
    }, () => { for (const p of need) pathWait.delete(p.toLowerCase()); });
  }
  const CHIP_IC = { mine: gl('user', 14), game: ic('pad', 'currentColor', 14), hot: gl('bolt', 14), odd: ic('shield', 'currentColor', 14) };
  const CHEV = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>';
  const DESC = { audio: 'Звук', chip: 'Видео и драйверы', net: 'Сеть', shield: 'Защита', gear: 'Служба', win: 'Системный процесс Windows', pad: 'Игра' };
  const descs = new Map();
  // the file's own description ("Host Process for Windows Services") when the bridge sent one, else a word by kind
  const descOf = (r) => { const d = descs.get(exeKey(r)); return d && d.toLowerCase() !== r.name.replace(/\.exe$/i, '').toLowerCase() ? d : (DESC[kindOf(r)] || ''); };
  const nameCell = (lead, r, name, extra, withDesc) => { const d = withDesc ? descOf(r) : ''; return `<div class="pf-nw">${lead}${ico(r)}<span class="pf-n2"><span class="pf-n1"><span class="pf-tx">${name}</span>${extra}</span>${d ? `<small class="pf-ds">${esc(d)}</small>` : ''}</span></div>`; };
  const kids = (r) => { const out = [], todo = [r.pid]; while (todo.length) { const p = todo.pop(); for (const x of S.procs) if (x.ppid === p && x.pid !== p && !out.includes(x)) { out.push(x); todo.push(x.pid); } } return out; };
  let toastTimer = 0;

  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3600); };
  const fail = (r) => say(ERR[r && r.error] || ERR.failed);
  const idOf = (r) => `${r.pid}:${r.started}`;
  // One heat scale for the three load columns, absolute (not relative to the heaviest row): the cell tint grows with the value, small values get none,
  // amber and red start at a real threshold (CPU 25 / 50 % of the machine, memory 18 / 30 % of the RAM, disk 20 / 60 MB/s)
  const cpuX = (v) => v / 100, memX = (v) => Math.min(1, v / (S.ram ? S.ram.total * 0.47 : 8 * GB)), ioX = (v) => v / (40 * MB);   // header cells only use these as "has a value"
  const scale = (k) => (k === 'cpu' ? [50, 25, 50] : k === 'io' ? [50 * MB, 20 * MB, 60 * MB] : [8 * GB, Math.max(2 * GB, (S.ram ? S.ram.total : 16 * GB) * 0.18), Math.max(4 * GB, (S.ram ? S.ram.total : 16 * GB) * 0.3)]);
  const cell = (k, v, txt, zero, id) => {
    const key = id + k, [max, warn, crit] = scale(k); nextT.set(key, txt);
    const chg = prevT.has(key) && prevT.get(key) !== txt, lvl = v >= crit ? ' crit' : v >= warn ? ' warn' : '', h = Math.min(1, v / max);
    return `<td class="num ld c-${k}${h >= 0.06 || lvl ? ' heat' : ''}${lvl}${zero ? ' z' : ''}${chg ? ' chg' : ''}" style="--heat:${(lvl ? Math.max(h, 0.85) : h).toFixed(2)}">${nu(txt)}</td>`;
  };
  const loadCells = (cpu, mem, io, id) => cell('cpu', cpu, cpu >= 0.05 ? p1(cpu) + '%' : '0%', cpu < 0.05, id) + cell('mem', mem, bytes(mem), mem <= 0, id) + cell('io', io, rate(io), io <= 0, id);

  /* ---- processes ---- */
  function groups(frozen) {
    const q = S.q.trim().toLowerCase(), map = new Map();
    const tests = CHIPS.filter((c) => S.chips.has(c[0])).map((c) => c[2]);
    for (const r of S.procs) {
      if (q && !(r.name.toLowerCase().includes(q) || String(r.pid) === q || r.exe.toLowerCase().includes(q))) continue;
      if (!tests.every((t) => t(r))) continue;
      const k = S.group ? r.name.toLowerCase() : idOf(r);
      let g = map.get(k);
      if (!g) map.set(k, g = { key: k, name: r.name, rows: [], cpu: 0, mem: 0, io: 0, thr: 0 });
      g.rows.push(r); g.cpu += r.cpu; g.mem += r.mem; g.io += r.io; g.thr += r.threads;
    }
    const f = SORT[S.key];
    const val = (g) => (g.rows.length === 1 || S.key === 'name' || S.key === 'user' ? f(g.rows[0]) : S.key === 'pid' ? g.rows[0].pid : g[S.key]);
    const list = [...map.values()].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * S.dir; });
    for (const g of list) g.rows.sort((a, b) => b.cpu - a.cpu || b.mem - a.mem);
    // while the cursor is over the table the rows keep their previous order (values still update), so nothing jumps under the mouse
    if (frozen && S.order) {
      const at = (k) => (S.order.has(k) ? S.order.get(k) : 1e9);
      list.sort((a, b) => at(a.key) - at(b.key));
      for (const g of list) g.rows.sort((a, b) => at(idOf(a)) - at(idOf(b)));
    } else {
      S.order = new Map(); let i = 0;
      for (const g of list) { S.order.set(g.key, i++); for (const r of g.rows) S.order.set(idOf(r), i++); }
    }
    return list;
  }
  // who owns the process: the account name; Windows hides it for system processes, which then show as "Система" (they live in the Windows folder)
  const ownerOf = (r) => r.user || (r.protected || inWin(r.exe) ? 'Система' : '');
  const ownerHtml = (v, inferred) => (v ? `<span${inferred ? ' title="Системный процесс или служба Windows"' : ''}>${esc(v)}</span>` : '<span class="pf-na" title="Windows не показывает владельца этого процесса">нет доступа</span>');
  const userCell = (r) => `<td class="dim w9 pf-us">${ownerHtml(ownerOf(r), !r.user && ownerOf(r) === 'Система')}</td>`;
  const groupUser = (g) => { const set = new Set(g.rows.map(ownerOf)); return `<td class="dim w9 pf-us">${set.size === 1 ? ownerHtml([...set][0], [...set][0] === 'Система' && !g.rows[0].user) : '<span title="Процессы группы запущены от разных учётных записей">разные</span>'}</td>`; };
  function rowHtml(r, label, cls, extra) {
    const id = idOf(r), hog = isHog(id), jump = prevC.has(id) && r.cpu - prevC.get(id) >= JUMP_CPU; nextC.set(id, r.cpu);
    return `<tr class="pt-row${cls}${S.sel === id ? ' sel' : ''}${hog ? ' hog' : ''}${jump ? ' jump' : ''}" data-r="${esc(id)}"${hog ? ` style="--ph:-${Date.now() % 2400}ms" title="Высокая нагрузка держится дольше ${HOG_MS / 1000} с"` : ''}${extra || ''}><td class="pf-nm">${label}</td>${loadCells(r.cpu, r.mem, r.io, id)}<td class="num dim w5">${r.threads}</td>${userCell(r)}<td class="num dim">${r.pid}</td></tr>`;
  }
  function groupHtml(g) {
    if (g.rows.length === 1) return rowHtml(g.rows[0], nameCell('<span class="pf-sp1"></span>', g.rows[0], esc(g.name), tags(g.rows[0]), true), '');
    const open = S.open.has(g.key), sum = { cpu: g.cpu, mem: g.mem, io: g.io };
    const gid = 'g:' + g.key, hog = isHog(gid), jump = prevC.has(gid) && g.cpu - prevC.get(gid) >= JUMP_CPU; nextC.set(gid, g.cpu);
    return `<tr class="pt-row grp${hog ? ' hog' : ''}${jump ? ' jump' : ''}" data-g="${esc(g.key)}" aria-expanded="${open}"${hog ? ` style="--ph:-${Date.now() % 2400}ms" title="Высокая нагрузка держится дольше ${HOG_MS / 1000} с"` : ''}><td class="pf-nm">${nameCell(`<span class="pf-car" aria-hidden="true">${CHEV}</span>`, g.rows.find((x) => x.exe) || g.rows[0], esc(g.name), ` <span class="dim pf-cnt">${g.rows.length}</span>${g.rows.some((x) => x.game) ? '<span class="pf-tag game">игра</span>' : ''}`, true)}</td>${loadCells(sum.cpu, sum.mem, sum.io, gid)}<td class="num dim w5">${g.thr}</td>${groupUser(g)}<td class="num dim" title="У группы нет своего PID: это ${g.rows.length} отдельных процессов. Раскройте её, чтобы увидеть их номера"><span class="pf-grp">группа</span></td></tr>`
      + (open ? g.rows.map((r) => rowHtml(r, nameCell('', r, esc(r.name), tags(r), false), ' ch')).join('') : '');
  }
  // signature of the selected program, asked once per process (PowerShell takes a moment) and shown in the bar
  function loadSign(r) {
    const id = idOf(r);
    if (!m.connected || !r.exe || signs.has(id)) return;
    signs.set(id, { status: 'pending' });
    J.send('procs', { op: 'sign', pid: r.pid, started: r.started }).then((x) => { signs.set(id, x && x.ok ? x : { status: 'unknown' }); if (S.sel === id && S.tab === 'procs') paintProcs(); });
  }
  function select(id) { S.sel = id; S.ask = ''; const r = S.procs.find((x) => idOf(x) === id); if (r) loadSign(r); }
  function sigBadge(r) {
    const s = signs.get(idOf(r));
    if (!s || s.status === 'unknown') return '';
    if (s.status === 'pending') return '<span class="pf-sig">Проверяю подпись…</span>';
    if (s.status === 'unsigned') return '<span class="pf-sig warn" title="У файла нет цифровой подписи">Без подписи</span>';
    if (s.status === 'invalid') return '<span class="pf-sig bad" title="Файл изменён или сертификат не принят">Подпись недействительна</span>';
    const win = /microsoft/i.test(s.signer) && /^[a-z]:\\windows\\/i.test(r.exe);
    return `<span class="pf-sig ok" title="Подпись проверена Windows">${win ? 'Системный файл Windows' : `Подписан: ${esc(s.signer || 'издатель неизвестен')}`} ✓</span>`;
  }
  function bar() {
    const r = S.procs.find((x) => idOf(x) === S.sel);
    if (!r) {
      const off = (cls, t) => `<button type="button" class="pf-btn${cls}" disabled>${t}</button>`;
      return `<div class="pf-bar idle"><div class="pf-bi"><b class="pf-who">Процесс не выбран</b><span class="dim">Нажмите на строку таблицы, чтобы увидеть действия</span></div><div class="pf-ba"><div class="pf-bd">${off(' bad', 'Завершить')}${off(' bad', 'Завершить дерево')}</div>`
        + `<div class="pf-bn">${off('', 'Найти в списке')}<label class="pf-prio off">Приоритет <select disabled><option>—</option></select></label>${off('', 'Показать файл')}</div></div><div class="pf-path dim">Путь к файлу появится здесь</div></div>`;
    }
    const ask = S.ask, lock = r.protected || r.self, why = r.self ? ERR.self : ERR.protected, dis = lock ? ' disabled' : '';
    const btn = (cls, a, t, extra) => `<button type="button" class="pf-btn${cls}" data-a="${a}"${extra || ''}>${t}</button>`;
    const tip = (on, text, html) => (on ? `<span class="pf-tip" title="${text}">${html}</span>` : html);   // a disabled button shows no tooltip of its own
    const n = ask === 'tree' ? kids(r).length : 0;
    const danger = ask && !lock
      ? `<span class="pf-conf">${ask === 'tree' ? `Завершить ${esc(r.name)} и ещё ${n} дочерних процессов?` : 'Завершить процесс?'}${btn(' bad solid', 'do-' + ask, 'Да')}${btn('', 'no', 'Нет')}</span>`
      : tip(lock, why, btn(' bad', 'end', 'Завершить', dis)) + tip(lock, why, btn(' bad', 'tree', 'Завершить дерево', dis));
    const prio = `<label class="pf-prio${r.protected ? ' off' : ''}"${r.protected ? ` title="${ERR.protected}"` : ''}>Приоритет <select data-a="prio"${r.protected ? ' disabled' : ''}>${PRIO.map(([k, t]) => `<option value="${k}"${r.prio === k ? ' selected' : ''}>${t}</option>`).join('')}${r.prio ? '' : '<option value="" selected>—</option>'}</select></label>`;
    return `<div class="pf-bar"><div class="pf-bi"><b class="pf-who">${ico(r)}${esc(r.name)}</b><span class="dim">PID ${r.pid}${r.user ? ` · ${esc(r.user)}` : ''} · потоков ${r.threads}</span>${sigBadge(r)}${lock ? `<span class="dim">${why}</span>` : ''}</div>`
      + `<div class="pf-ba"><div class="pf-bd">${danger}</div><div class="pf-bn">${btn('', 'find', 'Найти в списке', ' title="Прокрутить список к выбранному процессу"')}${prio}${tip(!r.exe, ERR.no_path, btn('', 'folder', 'Показать файл', r.exe ? '' : ' disabled'))}</div></div>`
      + (r.exe ? `<div class="pf-path dim" translate="no">${esc(r.exe)}</div>` : '') + '</div>';
  }
  const skeleton = () => Array.from({ length: 10 }, () => '<tr class="pf-sk"><td><i style="width:55%"></i></td><td><i></i></td><td><i></i></td><td><i></i></td><td><i></i></td><td><i></i></td><td><i></i></td></tr>').join('');
  const emptyRow = () => { const q = S.q.trim(); return `<tr class="pf-empty"><td colspan="7"><b>${q ? `Ничего не найдено по «${esc(q)}»` : 'Нет подходящих процессов'}</b>${q || S.chips.size ? '<button type="button" class="pf-btn" data-a="clear">Сбросить поиск и фильтры</button>' : ''}</td></tr>`; };
  const chipCount = (k) => { const n = S.procs.filter(CHIPS.find((c) => c[0] === k)[2]).length; return `<span class="pf-cn${n && k === 'hot' ? ' warn' : n && k === 'odd' ? ' bad' : ''}">${n}</span>`; };
  function paintProcs() {
    const cpu = Math.min(100, S.procs.reduce((a, r) => a + r.cpu, 0)), mem = S.procs.reduce((a, r) => a + r.mem, 0), io = S.procs.reduce((a, r) => a + r.io, 0), used = S.ram ? S.ram.used : mem;
    // the column heads carry the totals, like Task Manager: the big number is the whole machine, the small line names the column
    const keepW = pbox.querySelector('.pf-tbl-wrap');
    nextT = new Map(); nextC = new Map();
    const gs = S.loaded ? groups(!!(keepW && keepW.matches(':hover'))) : [], th = (k, t, c, top, x, sp) => `<th class="${c || ''}${x === undefined ? '' : ' c-' + k}" data-s="${k}" title="${HINT[k] || ''}" aria-sort="${S.key === k ? (S.dir < 0 ? 'descending' : 'ascending') : 'none'}">${top ? `<b>${nu(top)}</b>` : ''}${sp || ''}<span>${t}<em class="so">${S.key === k ? (S.dir < 0 ? '↓' : '↑') : '↕'}</em></span></th>`;
    const keep = pbox.querySelector('.pf-tbl-wrap'), top = keep ? keep.scrollTop : 0, hadFocus = document.activeElement && document.activeElement.id === 'pf-q';
    const shown = gs.reduce((a, g) => a + g.rows.length, 0);
    pbox.innerHTML = `<div class="pf-tools"><input id="pf-q" type="search" placeholder="Поиск по имени или PID" value="${esc(S.q)}" autocomplete="off"><label class="pf-chk"><input type="checkbox" id="pf-grp"${S.group ? ' checked' : ''}> Группировать по программам</label>`
      + `<span class="dim pf-sum">Процессов: ${shown === S.procs.length ? shown : `${shown} из ${S.procs.length}`}</span></div>`
      + `<div class="pf-chips">${CHIPS.map(([k, t]) => `<button type="button" class="pf-chip${S.chips.has(k) ? ' on' : ''}" data-c="${k}" aria-pressed="${S.chips.has(k)}">${CHIP_IC[k]}${t}${chipCount(k)}</button>`).join('')}</div>`
      + `<div class="pf-tbl-wrap"><table class="pf-tbl"><thead><tr>${th('name', 'Имя')}${th('cpu', 'Процессор', 'num', `${p1(cpu)}%`, cpuX(cpu), spark(hist.cpu, 'cpu'))}${th('mem', 'Память', 'num', S.ram ? `${Math.round(used / S.ram.total * 100)}%` : bytes(mem), S.ram ? used / S.ram.total : 0, spark(hist.mem, 'mem'))}${th('io', 'Диск', 'num', rate(io), ioX(io), spark(hist.io, 'io'))}${th('thr', 'Потоки', 'num w5', String(S.procs.reduce((a, r) => a + r.threads, 0)), undefined, '<span class="sp-pad"></span>')}${th('user', 'Пользователь', 'w9')}${th('pid', 'PID', 'num')}</tr></thead><tbody>${!S.loaded ? skeleton() : gs.map(groupHtml).join('') || emptyRow()}</tbody></table></div>${bar()}`;
    prevT = nextT; prevC = nextC; wantIcons(gs);
    const w = pbox.querySelector('.pf-tbl-wrap'); if (w) w.scrollTop = top;
    if (hadFocus) { const q = $('pf-q'); q.focus(); q.setSelectionRange(q.value.length, q.value.length); }
  }
  async function pull() {
    if (S.busy || VIEW !== 'perf' || S.tab !== 'procs') return;
    if (!m.connected) { demoProcs(); S.loaded = true; track(); paintProcs(); return; }
    S.busy = true;
    try { const r = await J.send('procs', { op: 'list' }); if (r && r.ok) { S.procs = r.procs; for (const x of S.procs) if (!x.name) x.name = 'Системный процесс'; S.loaded = true; S.cores = r.cores; S.ram = r.ram || null; S.me = r.me || ''; track(); const ae = document.activeElement; if (S.tab === 'procs' && !document.querySelector('.dd-pop') && !(ae && ae.tagName === 'SELECT' && pbox.contains(ae))) paintProcs(); } } finally { S.busy = false; }   // an open priority list is not redrawn under the cursor
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
      + (shown.length ? `<div class="pf-st">${shown.map((e) => `<div class="pf-si${e.enabled ? '' : ' off'}">${icoPath(e.path, 'app', '')}<div class="pf-sn"><b>${esc(e.name)}</b><span class="dim">${SCOPE[e.scope] || ''}</span><span class="pf-path dim" translate="no">${esc(e.path)}</span></div>`
        + `<button class="cm-try" data-f="${esc(e.id)}">Показать файл</button><button type="button" class="pf-sw${e.enabled ? ' on' : ''}" role="switch" aria-checked="${e.enabled}" aria-label="${esc(e.name)}" data-id="${esc(e.id)}"></button></div>`).join('')}</div>`
        : q ? '<div class="rm-empty"><b>Ничего не найдено</b></div>' : '<div class="rm-empty"><b>Список пуст</b>Ни одна программа не запускается вместе с Windows.</div>')
      + '<h3 class="pf-sub">Задачи планировщика при входе</h3>'
      + (tasks === null ? '<p class="pf-note dim">Читаю задачи…</p>' : tasks.length ? `<div class="pf-st">${tasks.map((t) => `<div class="pf-si${t.enabled ? '' : ' off'}">${icoPath(t.path, 'app', '')}<div class="pf-sn"><b>${esc(t.name)}</b><span class="pf-path dim" translate="no">${esc(t.path)}</span></div>`
        + `<button type="button" class="pf-sw${t.enabled ? ' on' : ''}" role="switch" aria-checked="${t.enabled}" aria-label="${esc(t.name)}" data-task="${esc(t.id)}"></button></div>`).join('')}</div>` : q ? '' : '<p class="pf-note dim">Таких задач нет.</p>');
    sbox.scrollTop = top;
    wantPaths([...shown.map((e) => e.path), ...(tasks || []).map((t) => t.path)], () => { if (S.tab === 'startup') paintStart(); });
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
      + `<div class="pf-tbl-wrap"><table class="pf-tbl"><thead><tr><th><span>Название</span></th><th class="w9"><span>Состояние</span></th><th class="w9"><span>Запуск</span></th><th class="num w5"><span>PID</span></th></tr></thead><tbody>${list.map((x) => `<tr class="pt-row${S.vsel === x.name ? ' sel' : ''}" data-sv="${esc(x.name)}"><td class="pf-nm">${icoPath(x.path, svcKind(x), x.critical ? 'sys' : '')}<span class="pf-tx">${esc(x.display)}</span>${x.critical ? '<i class="pf-lock" title="Системная служба">●</i>' : ''}</td><td class="${x.status === 'running' ? 'pf-ok' : 'dim'}"><i class="pf-dot ${esc(x.status)}"></i>${ST[x.status] || esc(x.status)}</td><td class="dim">${SS[x.start] || esc(x.start)}</td><td class="num dim">${x.pid || ''}</td></tr>`).join('') || '<tr><td colspan="4" class="dim">Ничего не найдено</td></tr>'}</tbody></table></div>${svcBar(items.find((x) => x.name === S.vsel))}`;
    const w = vbox.querySelector('.pf-tbl-wrap'); if (w) w.scrollTop = top;
    wantPaths(list.map((x) => x.path), () => { if (S.tab === 'services') paintSvc(); });
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
    S.tab = tab; clearInterval(S.beat); S.beat = 0; closeMenu();
    for (const b of head.querySelectorAll('[data-t]')) { const on = b.dataset.t === tab; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); }
    body.hidden = tab !== 'perf'; pbox.hidden = tab !== 'procs'; sbox.hidden = tab !== 'startup'; vbox.hidden = tab !== 'services';
    if (tab === 'procs') { if (!S.loaded) paintProcs(); pull(); S.beat = setInterval(pull, 2000); } else if (tab === 'startup') { S.items = null; S.tasks = null; paintStart(); loadStart(); } else if (tab === 'services') { S.vask = ''; paintSvc(); loadSvc(); } else if (typeof window.renderPerf === 'function') window.renderPerf();
  }
  if (window.fzDropdown) window.fzDropdown.watch(pbox);   // the priority select becomes the themed dropdown
  head.addEventListener('click', (e) => { const b = e.target.closest('[data-t]'); if (b) show(b.dataset.t); });
  pbox.addEventListener('click', async (e) => {
    const sort = e.target.closest('[data-s]');
    if (sort) { const k = sort.dataset.s; S.order = null; S.dir = S.key === k ? -S.dir : (k === 'name' || k === 'pid' || k === 'user' ? 1 : -1); S.key = k; paintProcs(); return; }
    const chip = e.target.closest('[data-c]');
    if (chip) { S.order = null; const k = chip.dataset.c; S.chips.has(k) ? S.chips.delete(k) : S.chips.add(k); paintProcs(); return; }
    const g = e.target.closest('[data-g]');
    if (g) { const k = g.dataset.g; S.open.has(k) ? S.open.delete(k) : S.open.add(k); paintProcs(); return; }
    const row = e.target.closest('[data-r]');
    if (row) { select(S.sel === row.dataset.r ? '' : row.dataset.r); paintProcs(); return; }
    const a = e.target.closest('[data-a]'); if (!a) return;
    const r = S.procs.find((x) => idOf(x) === S.sel), act = a.dataset.a;
    if (act === 'find') {
      if (!r) return;
      if (S.group) S.open.add(r.name.toLowerCase());
      paintProcs();
      const row = [...pbox.querySelectorAll('[data-r]')].find((x) => x.dataset.r === S.sel);
      if (row) row.scrollIntoView({ block: 'center' }); else say('Процесс скрыт поиском или фильтром');
      return;
    }
    if ((act === 'end' || act === 'tree' || act.startsWith('do-')) && r && (r.protected || r.self)) return;
    if (act === 'end' || act === 'tree') { S.ask = act; paintProcs(); return; }
    if (act === 'no') { S.ask = ''; paintProcs(); return; }
    if (act === 'clear') { S.q = ''; S.chips.clear(); S.order = null; paintProcs(); return; }
    if (!r) return;
    if (act === 'folder') { openFolder(r); return; }
    if (act.startsWith('do-')) {
      S.ask = ''; const x = await J.send('procs', { op: 'end', pid: r.pid, started: r.started, tree: act === 'do-tree' });
      if (x && x.ok) { say(`Завершено: ${r.name}`); S.sel = ''; S.busy = false; pull(); } else fail(x);
    }
  });
  pbox.addEventListener('change', async (e) => {
    if (e.target.id === 'pf-grp') { S.group = e.target.checked; S.order = null; paintProcs(); return; }
    if (e.target.dataset.a === 'prio') {
      const r = S.procs.find((x) => idOf(x) === S.sel); if (!r || !e.target.value) return;
      setPrio(r, e.target.value);
    }
  });
  async function openFolder(r) { const x = await J.send('procs', { op: 'folder', pid: r.pid, started: r.started }); if (!x || !x.ok) fail(x); }
  async function setPrio(r, level) {
    const x = await J.send('procs', { op: 'priority', pid: r.pid, started: r.started, level });
    if (x && x.ok) { r.prio = level; say('Приоритет изменён'); } else fail(x);
    paintProcs();
  }

  /* ---- right-click menu (lives in <body>, so the 2 s repaint of the table does not close it) ---- */
  let ctx = null, aff = null;
  const closeMenu = () => { if (ctx) { ctx.remove(); ctx = null; aff = null; } };
  function drawMenu() {
    const r = S.procs.find((x) => idOf(x) === S.sel); if (!ctx) return;
    if (!r) { closeMenu(); return; }
    const lock = r.protected || r.self, offl = r.protected ? ' disabled' : '', offk = lock ? ' disabled' : '';
    const affHtml = aff ? `<div class="cx-aff"><div class="cx-cores">${Array.from({ length: aff.total }, (_, i) => `<label><input type="checkbox" data-core="${i}"${aff.on.has(i) ? ' checked' : ''}>${i}</label>`).join('')}</div><div class="cx-row"><button data-m="aff-all">Все</button><button data-m="aff-ok" class="cx-go">Применить</button></div></div>` : '';
    ctx.innerHTML = `<div class="cx-h">${esc(r.name)} <small>PID ${r.pid}</small></div>`
      + `<button data-m="folder"${r.exe ? '' : ' disabled'}>Показать файл в папке</button><button data-m="search">Найти в интернете</button>`
      + `<div class="cx-sub">Приоритет</div><div class="cx-row cx-prio">${PRIO.map(([k, t]) => `<button data-m="prio" data-v="${k}" class="${r.prio === k ? 'on' : ''}"${offl}>${t}</button>`).join('')}</div>`
      + `<button data-m="aff"${offl}>Ядра процессора…</button>${affHtml}<hr>`
      + `<button data-m="end"${offk}>Завершить</button><button data-m="tree" class="cx-bad"${offk}>Завершить дерево</button>`
      + (lock ? `<div class="cx-note">${r.self ? ERR.self : ERR.protected}</div>` : '');
    const b = ctx.getBoundingClientRect(), x = Math.min(ctx.offsetLeft, innerWidth - b.width - 8), y = Math.min(ctx.offsetTop, innerHeight - b.height - 8);
    ctx.style.left = `${Math.max(8, x)}px`; ctx.style.top = `${Math.max(8, y)}px`;
  }
  function openMenu(x, y) {
    closeMenu();
    ctx = document.createElement('div'); ctx.id = 'pf-ctx'; ctx.setAttribute('role', 'menu'); ctx.style.left = `${x}px`; ctx.style.top = `${y}px`;
    document.body.appendChild(ctx); drawMenu();
    ctx.addEventListener('click', async (e) => {
      const b = e.target.closest('button[data-m]'); if (!b || b.disabled) return;
      const r = S.procs.find((p) => idOf(p) === S.sel), a = b.dataset.m; if (!r) { closeMenu(); return; }
      if (a === 'folder') { closeMenu(); openFolder(r); }
      else if (a === 'search') { closeMenu(); const x2 = await J.send('procs', { op: 'search', pid: r.pid, started: r.started }); if (!x2 || !x2.ok) fail(x2); }
      else if (a === 'prio') { closeMenu(); setPrio(r, b.dataset.v); }
      else if (a === 'end' || a === 'tree') { closeMenu(); S.ask = a; paintProcs(); }   // the confirmation stays in the bar, same as the buttons
      else if (a === 'aff') {
        if (aff) { aff = null; drawMenu(); return; }
        const x2 = await J.send('procs', { op: 'affinity', pid: r.pid, started: r.started });
        if (!x2 || !x2.ok) { closeMenu(); fail(x2); return; }
        aff = { total: x2.total, on: new Set(x2.cores) }; drawMenu();
      } else if (a === 'aff-all') { aff.on = new Set(Array.from({ length: aff.total }, (_, i) => i)); drawMenu(); }
      else if (a === 'aff-ok') {
        if (!aff.on.size) { say('Выберите хотя бы одно ядро'); return; }
        const x2 = await J.send('procs', { op: 'affinity', pid: r.pid, started: r.started, cores: [...aff.on] });
        closeMenu(); if (x2 && x2.ok) say('Ядра изменены'); else fail(x2);
      }
    });
    ctx.addEventListener('change', (e) => { const c = e.target.dataset.core; if (c !== undefined && aff) { e.target.checked ? aff.on.add(+c) : aff.on.delete(+c); } });
  }
  pbox.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    const row = e.target.closest('[data-r]'); if (!row) { closeMenu(); return; }
    select(row.dataset.r); paintProcs(); openMenu(e.clientX, e.clientY);
  });
  document.addEventListener('mousedown', (e) => { if (ctx && !ctx.contains(e.target)) closeMenu(); }, true);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeMenu(); });
  window.addEventListener('blur', closeMenu);
  pbox.addEventListener('scroll', closeMenu, true);
  pbox.addEventListener('input', (e) => { if (e.target.id === 'pf-q') { S.q = e.target.value; S.order = null; paintProcs(); } });
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
