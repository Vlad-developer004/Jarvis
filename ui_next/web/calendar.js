// Calendar screen, core + month view: state, loading (per visible range), navigation, header, keyboard, demo data without a core.
// Other parts: calendar_views.js (week, day, agenda, search), calendar_edit.js (details, editor, quick add, side panel with sources and reminders).
// Talks to the core with the `calendar` command (ui_next/bridge/calendar.py, on top of actions/calendar_hub.py). Relies on globals of app.html: $, J, m, esc, VIEW, ic.
(() => {
  const root = $('calpage'), main = $('cl-main'), toast = $('cl-toast');
  const MONTHS = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
  const MONTHS_G = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const MON_S = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const DOW = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'], DOW_FULL = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'];
  const VIEWS = { month: 'Месяц', week: 'Неделя', day: 'День', agenda: 'Список' };
  const p2 = (n) => String(n).padStart(2, '0');
  const iso = (d) => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
  const parse = (s) => { const [y, mo, d] = String(s).split('-').map(Number); return new Date(y, mo - 1, d); };
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  const mondayOf = (d) => addDays(d, -((d.getDay() + 6) % 7));
  const dow = (d) => (d.getDay() + 6) % 7;
  const today = () => iso(new Date());
  let prefs = {}; try { prefs = JSON.parse(localStorage.getItem('jarvis.cal') || '{}'); } catch (e) { /* no storage */ }
  const savePrefs = () => { try { localStorage.setItem('jarvis.cal', JSON.stringify({ view: S.view === 'search' ? S.prev : S.view, side: S.side })); } catch (e) { /* no storage */ } };
  const S = { view: VIEWS[prefs.view] ? prefs.view : 'month', prev: 'month', cur: new Date(), sel: today(), events: [], status: [], state: null, loading: false, q: '', results: [], side: prefs.side !== false, key: '', rows: 3, find: false };
  let toastTimer = 0, demo = null, searchTimer = 0, seq = 0;
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3400); };
  const call = async (b) => (await J.send('calendar', b)) || { ok: false, error: 'offline' };
  const color = (e) => (/^#[0-9a-f]{6}$/i.test(e.color || '') ? e.color : '#3df5ac');

  // ---- ranges ----
  function range() {
    const c = S.cur;
    if (S.view === 'month') { const s = mondayOf(new Date(c.getFullYear(), c.getMonth(), 1)); return [s, addDays(s, 41)]; }
    if (S.view === 'week') { const s = mondayOf(c); return [s, addDays(s, 6)]; }
    if (S.view === 'agenda') return [new Date(c.getFullYear(), c.getMonth(), c.getDate()), addDays(c, 59)];
    return [new Date(c.getFullYear(), c.getMonth(), c.getDate()), new Date(c.getFullYear(), c.getMonth(), c.getDate())];
  }
  const title = () => {
    const c = S.cur;
    if (S.view === 'search') return `Поиск: «${esc(S.q)}»`;
    if (S.view === 'month') return `${MONTHS[c.getMonth()]} <span>${c.getFullYear()}</span>`;
    if (S.view === 'day') return `${DOW_FULL[dow(c)][0].toUpperCase() + DOW_FULL[dow(c)].slice(1)}, ${c.getDate()} ${MONTHS_G[c.getMonth()]} <span>${c.getFullYear()}</span>`;
    const [a, b] = range();
    if (S.view === 'agenda') return `Ближайшие дни <span>${a.getDate()} ${MON_S[a.getMonth()]} – ${b.getDate()} ${MON_S[b.getMonth()]}</span>`;
    return a.getMonth() === b.getMonth() ? `${a.getDate()} – ${b.getDate()} ${MONTHS_G[b.getMonth()]} <span>${b.getFullYear()}</span>` : `${a.getDate()} ${MON_S[a.getMonth()]} – ${b.getDate()} ${MON_S[b.getMonth()]} <span>${b.getFullYear()}</span>`;
  };

  // ---- demo data (no core) ----
  function demoEvents() {
    if (demo) return demo;
    const t = new Date(), at = (n) => iso(addDays(t, n)), mk = (id, title, n, time, end, o = {}) => ({ id, title, date: at(n), time, end_date: o.endN !== undefined ? at(o.endN) : at(n), end_time: end || '', all_day: !time, location: '', notes: '', source: 'Работа', ref: 'demo', color: '#4c8dff', local: false, ...o });
    demo = [mk('d1', 'Планёрка', 0, '10:00', '10:30'), mk('d2', 'Встреча по проекту', 0, '10:15', '11:30', { location: 'Zoom', notes: 'Обсудить сроки и бюджет. Ссылка: https://example.com/room/42' }),
      mk('d3', 'Обед с Анной', 0, '13:00', '14:00', { source: 'Мои события', local: true, eid: 'd3', repeat: 'none', color: '#3df5ac', location: 'Кафе «Лето»' }), mk('d4', 'Стоматолог', 2, '15:30', '16:30', { source: 'Мои события', local: true, eid: 'd4', repeat: 'none', color: '#ff6b6b', location: 'Клиника на Садовой' }),
      mk('d5', 'Поездка в Львов', 4, '', '', { endN: 6, color: '#ffa94d', source: 'Мои события', local: true, eid: 'd5', repeat: 'none' }), mk('d6', 'День рождения Максима', 7, '', '', { color: '#f783ac', source: 'Мои события', local: true, eid: 'd6', repeat: 'yearly' }),
      mk('d7', 'Спортзал', 1, '19:00', '20:30', { source: 'Мои события', local: true, eid: 'd7', repeat: 'weekly', color: '#b197fc' }), mk('d8', 'Релиз 2.0', 9, '12:00', '13:00'), mk('d9', 'Созвон с командой', 3, '11:00', '11:45')];
    return demo;
  }
  const DEMO_STATE = { installed: true, enabled: true, colors: ['#3df5ac', '#22d3ee', '#4c8dff', '#b197fc', '#f783ac', '#ff6b6b', '#ffa94d', '#ffd43b'], own_name: 'Мои события',
    sources: [{ ref: 'https://calendar.example.com/work.ics', name: 'Работа', color: '#4c8dff', hidden: false, status: 'ok' }, { ref: 'https://caldav.example.com/me/main/', name: 'Яндекс', color: '#ffd43b', hidden: false, status: 'ok', kind: 'caldav', id: 'dv1', writable: true }], remind: { enabled: true, minutes: 15 } };

  // ---- data ----
  const norm = (e) => ({ ...e, end_date: e.end_date || e.date });
  async function load(force) {
    const [a, b] = range(), key = `${S.view}|${iso(a)}|${iso(b)}`, n = ++seq;
    if (S.view === 'search') { paint(); return; }
    if (!m.connected) { S.state = DEMO_STATE; S.events = demoEvents().map(norm); S.status = []; S.key = key; paint(); return; }
    if (!force && key === S.key) { paint(); return; }
    S.loading = true; paintHead();
    const [st, ev] = await Promise.all([S.state && !force ? Promise.resolve({ ok: true, ...S.state }) : call({ op: 'state' }), call({ op: 'events', from: iso(a), to: iso(b) })]);
    if (n !== seq) return;
    S.loading = false;
    if (st.ok) S.state = st;
    if (ev.ok) { S.events = ev.events.map(norm); S.status = ev.status; S.key = key; }
    else say(ev.error === 'offline' ? 'Jarvis ещё запускается' : 'Не удалось получить события');
    paint();
  }
  const invalidate = () => { S.key = ''; };
  const byTime = (x, y) => (+y.all_day - +x.all_day) || (x.date < y.date ? -1 : x.date > y.date ? 1 : 0) || (x.time < y.time ? -1 : x.time > y.time ? 1 : 0) || x.title.localeCompare(y.title);
  const eventsOn = (ds, list = S.events) => list.filter((e) => e.date <= ds && e.end_date >= ds).sort(byTime);
  const evById = (id) => S.events.find((e) => e.id === id) || S.results.find((e) => e.id === id);
  const whenText = (e) => {
    const fd = (s) => { const d = parse(s); return `${d.getDate()} ${MON_S[d.getMonth()]}`; };
    if (e.all_day) return e.end_date > e.date ? `${fd(e.date)} – ${fd(e.end_date)}` : 'весь день';
    if (e.end_date > e.date) return `${fd(e.date)} ${e.time} – ${fd(e.end_date)} ${e.end_time}`;
    return e.end_time && e.end_time !== e.time ? `${e.time} – ${e.end_time}` : e.time;
  };

  // ---- header ----
  function paintHead() {
    $('cl-title').innerHTML = title();
    $('cl-title').classList.toggle('busy', S.loading);
    for (const b of root.querySelectorAll('[data-vw]')) b.classList.toggle('on', b.dataset.vw === S.view);
    $('cl-prev').disabled = $('cl-next').disabled = S.view === 'search';
    $('cl-sidebtn').classList.toggle('on', S.side); root.classList.toggle('noside', !S.side);
    const t = S.events.filter((e) => e.date <= today() && e.end_date >= today()).length;
    const info = [t ? `сегодня событий: ${t}` : '', m.connected ? '' : 'пример, ядро не подключено'].filter(Boolean).join(' · '); $('cl-count').textContent = info; $('cl-count').title = info;
  }
  const hintHtml = () => (m.connected && S.state && !S.state.sources.length && !S.events.length && S.view !== 'search' ? '<div class="cl-hint"><span>Календарь пока пуст. Создайте событие или подключите Google, Outlook, Яндекс: достаточно ссылки на .ics.</span><button type="button" class="cm-try" id="cl-hint-new">Новое событие</button></div>' : '');
  function paint() {
    paintHead();
    main.className = `cl-main v-${S.view}`;
    if (S.view === 'month') monthView(); else if (window.Cal.views[S.view]) window.Cal.views[S.view](main);
    if (S.view !== 'month') main.insertAdjacentHTML('afterbegin', hintHtml());
    if (window.Cal.paintSide) window.Cal.paintSide();
  }

  // ---- month ----
  function monthView() {
    const [a] = range(), cur = S.cur.getMonth(), td = today(), rows = S.rows;
    const days = Array.from({ length: 42 }, (_, i) => iso(addDays(a, i)));
    main.innerHTML = `${hintHtml()}<div class="cl-dow">${DOW.map((x, i) => `<span${i > 4 ? ' class="we"' : ''}>${x}</span>`).join('')}</div><div class="cl-cells" id="cl-cells">${days.map((ds) => {
      const d = parse(ds), list = eventsOn(ds), shown = list.slice(0, list.length > rows ? rows - 1 : rows), more = list.length - shown.length;
      return `<div class="cl-day${d.getMonth() !== cur ? ' other' : ''}${dow(d) > 4 ? ' we' : ''}${ds === td ? ' today' : ''}${ds === S.sel ? ' sel' : ''}" data-d="${ds}" tabindex="0" role="gridcell" aria-label="${d.getDate()} ${MONTHS_G[d.getMonth()]}">
        <b class="n">${d.getDate() === 1 ? `${d.getDate()} ${MON_S[d.getMonth()]}` : d.getDate()}</b>${shown.map((e) => chip(e, ds)).join('')}${more > 0 ? `<button type="button" class="cl-more" data-day="${ds}">ещё ${more}</button>` : ''}</div>`;
    }).join('')}</div>`;
    const cell = main.querySelector('.cl-day'); if (!cell) return;
    const fit = Math.max(1, Math.min(6, Math.floor((cell.clientHeight - 24) / 21)));
    if (fit !== S.rows && !monthView.again) { S.rows = fit; monthView.again = true; monthView(); monthView.again = false; }
  }
  function chip(e, ds) {
    const first = ds === e.date, last = ds === e.end_date, multi = e.end_date > e.date;
    return `<button type="button" class="cl-ev${e.all_day ? ' ad' : ''}${multi && !first ? ' cl' : ''}${multi && !last ? ' cr' : ''}${e.local || e.rw ? ' own' : ''}" data-ev="${esc(e.id)}" style="--ec:${color(e)}" title="${esc(e.title)} · ${esc(whenText(e))}">${!e.all_day && first ? `<i>${e.time}</i>` : ''}<span>${esc(e.title)}</span></button>`;
  }

  // ---- navigation ----
  function shift(n) {
    const c = S.cur;
    S.cur = S.view === 'month' ? new Date(c.getFullYear(), c.getMonth() + n, 1) : addDays(c, n * (S.view === 'week' ? 7 : S.view === 'agenda' ? 30 : 1));
    S.sel = S.view === 'month' ? iso(new Date(S.cur.getFullYear(), S.cur.getMonth(), Math.min(parse(S.sel).getDate(), 28))) : iso(S.cur);
    load();
  }
  function goto(d, view) {
    S.cur = d; S.sel = iso(d); if (view) { S.view = view; savePrefs(); } else if (S.view === 'search') S.view = S.prev;
    if (S.view === 'month') S.cur = new Date(d.getFullYear(), d.getMonth(), 1);
    S.find = false; $('cl-find').hidden = true; load();
  }
  function setView(v) {
    if (v === S.view) return;
    if (S.view === 'search') { S.find = false; $('cl-find').hidden = true; $('cl-q').value = ''; }
    S.view = v; savePrefs();
    const sel = parse(S.sel); S.cur = v === 'month' ? new Date(sel.getFullYear(), sel.getMonth(), 1) : sel;
    load();
  }
  function selectDay(ds) {
    S.sel = ds; const d = parse(ds);
    if (S.view === 'month' && d.getMonth() !== S.cur.getMonth()) { S.cur = new Date(d.getFullYear(), d.getMonth(), 1); load(); return; }
    for (const c of main.querySelectorAll('.cl-day')) c.classList.toggle('sel', c.dataset.d === ds);
    if (window.Cal.paintSide) window.Cal.paintSide();
  }

  // ---- search ----
  function openFind(on) {
    S.find = on; $('cl-find').hidden = !on;
    if (on) { if (S.view !== 'search') S.prev = S.view; $('cl-q').focus(); }
    else if (S.view === 'search') { S.view = S.prev; S.q = ''; $('cl-q').value = ''; load(); }
  }
  function runSearch(q) {
    S.q = q.trim(); clearTimeout(searchTimer);
    if (S.q.length < 2) { if (S.view === 'search') { S.view = S.prev; load(); } return; }
    searchTimer = setTimeout(async () => {
      const n = ++seq; S.view = 'search';
      const r = m.connected ? await call({ op: 'search', q: S.q }) : { ok: true, events: demoEvents().filter((e) => `${e.title} ${e.location} ${e.notes}`.toLowerCase().includes(S.q.toLowerCase())) };
      if (n !== seq) return; S.results = r.ok ? r.events.map(norm) : []; paint();
    }, 300);
  }

  // ---- events from the DOM ----
  root.addEventListener('click', (e) => {
    const t = e.target, ev = t.closest('[data-ev]');
    if (ev) { e.stopPropagation(); if (performance.now() - (window.Cal.dragEnd || 0) < 350) return; window.Cal.showDetails(ev.dataset.ev, ev); return; }
    const md = t.closest('[data-day]'); if (md) { e.stopPropagation(); goto(parse(md.dataset.day), 'day'); return; }
    const vw = t.closest('[data-vw]'); if (vw) { setView(vw.dataset.vw); return; }
    const day = t.closest('.cl-day'); if (day) { selectDay(day.dataset.d); return; }
    const b = t.closest('button'); if (!b) return;
    if (b.id === 'cl-prev') shift(-1); else if (b.id === 'cl-next') shift(1);
    else if (b.id === 'cl-today') goto(new Date());
    else if (b.id === 'cl-refresh') { invalidate(); if (m.connected) call({ op: 'refresh' }).then(() => load(true)); else say('Демо: нечего обновлять'); }
    else if (b.id === 'cl-new' || b.id === 'cl-hint-new') window.Cal.openEditor({ date: S.sel });
    else if (b.id === 'cl-sidebtn') { S.side = !S.side; savePrefs(); paint(); }
    else if (b.id === 'cl-find-btn') openFind(!S.find);
    else if (b.id === 'cl-find-x') openFind(false);
    else if (b.id === 'cl-title') { if (window.fzDate && S.view !== 'search') window.fzDate.pickAt(b, iso(S.cur), (v) => { if (v) goto(parse(v)); }); }
  });
  root.addEventListener('dblclick', (e) => { const day = e.target.closest('.cl-day'); if (day && !e.target.closest('[data-ev], [data-day]')) window.Cal.openEditor({ date: day.dataset.d }); });
  root.addEventListener('input', (e) => { if (e.target.id === 'cl-q') runSearch(e.target.value); });
  document.addEventListener('keydown', (e) => {
    if (typeof VIEW === 'undefined' || VIEW !== 'calendar' || e.ctrlKey || e.metaKey || e.altKey) return;
    if (!$('cl-modal').hidden || document.querySelector('.dp-pop, .tp-pop, .dd-pop, .cl-dlg')) return;
    if (e.target.closest && e.target.closest('input, textarea, select, [contenteditable]')) { if (e.key === 'Escape' && e.target.id === 'cl-q') openFind(false); return; }
    const k = e.key.toLowerCase(), views = { m: 'month', w: 'week', d: 'day', a: 'agenda' };
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); shift(e.key === 'ArrowLeft' ? -1 : 1); }
    else if (k === 't') goto(new Date()); else if (k === 'n') { e.preventDefault(); window.Cal.openEditor({ date: S.sel }); }
    else if (k === '/') { e.preventDefault(); openFind(true); }
    else if (views[k]) setView(views[k]);
    else if (e.key === 'Escape' && window.Cal.closePop) window.Cal.closePop();
  });
  new ResizeObserver(() => {
    const c = S.view === 'month' && VIEW === 'calendar' && main.querySelector('.cl-day'); if (!c) return;
    const fit = Math.max(1, Math.min(6, Math.floor((c.clientHeight - 24) / 21))); if (fit !== S.rows) { S.rows = fit; monthView(); }
  }).observe(main);

  window.Cal = { S, root, main, toast, modal: $('cl-modal'), mbox: $('cl-mbox'), call, say, esc, iso, parse, p2, addDays, mondayOf, dow, today, color, whenText, eventsOn, evById, byTime, load, paint, invalidate, selectDay, goto, MONTHS_G, MON_S, DOW, DOW_FULL, MONTHS, views: {}, chip, runSearch };
  J.on('conn', () => { if (VIEW === 'calendar') { S.state = null; load(true); } });
  window.renderCalendar = () => { S.sel = S.sel || today(); load(); };
})();
