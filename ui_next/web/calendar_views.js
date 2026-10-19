// Calendar screen, the other views: week and day (a time grid with an all-day strip, overlapping events side by side, the current-time line,
// a click on an empty slot creates an event), the agenda list and the search results. Registered into Cal.views by name.
(() => {
  const C = window.Cal; if (!C) return;
  const { S, esc, iso, parse, addDays, mondayOf, today, color, whenText, eventsOn, MONTHS_G, MON_S, DOW, DOW_FULL } = C;
  const HH = 46;                                       // px per hour
  const mins = (t) => (t ? +t.slice(0, 2) * 60 + +t.slice(3, 5) : 0);
  let nowTimer = 0;

  // ---- time grid ----
  function layout(items) {
    // items: [{s, e, ev}] sorted by start; returns the same with col and cols (columns inside an overlapping cluster)
    const out = []; let cluster = [], end = -1;
    const flush = () => { const cols = []; for (const it of cluster) { let c = cols.findIndex((last) => last <= it.s); if (c < 0) { c = cols.length; cols.push(0); } cols[c] = it.e; it.col = c; } for (const it of cluster) it.cols = cols.length; out.push(...cluster); cluster = []; };
    for (const it of items) { if (cluster.length && it.s >= end) { flush(); end = -1; } cluster.push(it); end = Math.max(end, it.e); }
    if (cluster.length) flush();
    return out;
  }
  function segments(ds) {
    return eventsOn(ds).filter((e) => !e.all_day).map((e) => {
      const s = e.date === ds ? mins(e.time) : 0; let en = e.end_date === ds ? mins(e.end_time || e.time) : 1440;
      if (en <= s) en = Math.min(1440, s + 30);
      return { s, e: en, ev: e };
    }).sort((a, b) => a.s - b.s || b.e - a.e);
  }
  function grid(main, days) {
    const td = today(), n = days.length, now = new Date(), nowMin = now.getHours() * 60 + now.getMinutes();
    const keep = main.querySelector('.wk-scroll') ? main.querySelector('.wk-scroll').scrollTop : -1;
    const ad = days.map((ds) => eventsOn(ds).filter((e) => e.all_day));
    main.innerHTML = `<div class="wk-head" style="--n:${n}"><i class="gut"></i>${days.map((ds) => { const d = parse(ds), w = (d.getDay() + 6) % 7; return `<button type="button" class="wk-dh${ds === td ? ' today' : ''}${w > 4 ? ' we' : ''}${ds === S.sel ? ' sel' : ''}" data-dh="${ds}"><span>${DOW[w]}</span><b>${d.getDate()}</b></button>`; }).join('')}</div>
      <div class="wk-ad" style="--n:${n}"${ad.some((l) => l.length) ? '' : ' hidden'}><i class="gut">весь день</i>${ad.map((l, i) => `<div class="wk-adc" data-d="${days[i]}">${l.map((e) => C.chip(e, days[i])).join('')}</div>`).join('')}</div>
      <div class="wk-scroll" id="wk-scroll"><div class="wk-grid" style="--n:${n};height:${24 * HH}px"><div class="wk-hours">${Array.from({ length: 24 }, (_, h) => `<span style="top:${h * HH}px">${h ? String(h).padStart(2, '0') + ':00' : ''}</span>`).join('')}</div>${days.map((ds) => {
        const blocks = layout(segments(ds)).map((it) => { const e = it.ev, h = Math.max(22, (it.e - it.s) * HH / 60 - 2), step = it.cols > 1 ? Math.min(24, 60 / (it.cols - 1)) : 0, w = 100 - step * (it.cols - 1);
          return `<button type="button" class="wk-ev${e.local || e.rw ? ' own' : ''}${h < 34 ? ' tight' : ''}" data-ev="${esc(e.id)}" style="--ec:${color(e)};top:${it.s * HH / 60}px;height:${h}px;left:calc(${it.col * step}% + 1px);width:calc(${w}% - 3px);z-index:${it.col + 1}" title="${esc(e.title)} · ${esc(whenText(e))}"><b>${esc(e.title)}</b><small>${e.time}${e.end_time && e.end_time !== e.time ? '–' + e.end_time : ''}${e.location ? ' · ' + esc(e.location) : ''}</small>${(e.local || e.rw) && e.date === e.end_date ? '<i class="wk-rs"></i>' : ''}</button>`; }).join('');
        return `<div class="wk-col${ds === td ? ' today' : ''}" data-col="${ds}">${blocks}${ds === td ? `<i class="wk-now" style="top:${nowMin * HH / 60}px"></i>` : ''}</div>`;
      }).join('')}</div></div>`;
    const sc = main.querySelector('.wk-scroll');
    sc.scrollTop = keep >= 0 ? keep : Math.max(0, (days.includes(td) ? nowMin - 90 : 7.5 * 60) * HH / 60);
    clearInterval(nowTimer);
    nowTimer = setInterval(() => { const el = main.querySelector('.wk-now'); if (!el || VIEW !== 'calendar') { clearInterval(nowTimer); return; } const d = new Date(); el.style.top = `${(d.getHours() * 60 + d.getMinutes()) * HH / 60}px`; }, 60000);
  }
  C.views.week = (main) => grid(main, Array.from({ length: 7 }, (_, i) => iso(addDays(mondayOf(S.cur), i))));
  C.views.day = (main) => grid(main, [iso(S.cur)]);

  // ---- agenda and search ----
  function dayLabel(ds) {
    const d = parse(ds), t = parse(today()), diff = Math.round((d - t) / 864e5), w = DOW_FULL[(d.getDay() + 6) % 7];
    const base = `${d.getDate()} ${MONTHS_G[d.getMonth()]}${d.getFullYear() !== t.getFullYear() ? ` ${d.getFullYear()}` : ''}, ${w}`;
    return diff === 0 ? `Сегодня · ${base}` : diff === 1 ? `Завтра · ${base}` : diff === -1 ? `Вчера · ${base}` : base;
  }
  function list(main, events, days, empty) {
    const groups = days.map((ds) => [ds, eventsOn(ds, events)]).filter(([, l]) => l.length);
    main.innerHTML = groups.length ? `<div class="ag">${groups.map(([ds, l]) => `<section class="ag-g${ds === today() ? ' today' : ''}"><h4>${dayLabel(ds)}</h4>${l.map((e) => `<button type="button" class="ag-row${e.local ? ' own' : ''}" data-ev="${esc(e.id)}" style="--ec:${color(e)}">
        <span class="ag-t">${e.all_day ? '<em>весь день</em>' : `${e.time}${e.end_time && e.end_time !== e.time ? `<small>${e.end_time}</small>` : ''}`}</span><i></i><span class="ag-x"><b>${esc(e.title)}</b><small>${[e.location, e.source].filter(Boolean).map(esc).join(' · ')}</small></span></button>`).join('')}</section>`).join('')}</div>`
      : `<div class="cl-empty"><b>${empty.title}</b><span>${empty.text}</span>${empty.button ? '<button type="button" class="cm-try primary" id="cl-empty-new">Создать событие</button>' : ''}</div>`;
  }
  C.views.agenda = (main) => {
    const [a, b] = [S.cur, addDays(S.cur, 59)], days = []; for (let d = new Date(a); d <= b; d = addDays(d, 1)) days.push(iso(d));
    list(main, S.events, days, { title: 'Событий в ближайшие дни нет', text: 'Добавьте событие или подключите календарь справа: Google, Outlook, любой .ics.', button: true });
  };
  C.views.search = (main) => {
    const dates = [...new Set(S.results.map((e) => e.date))].sort();
    list(main, S.results, dates, { title: S.q.length < 2 ? 'Введите хотя бы два символа' : 'Ничего не найдено', text: 'Ищу по названию, месту и заметкам за год назад и год вперёд.', button: false });
  };

  // ---- clicks ----
  C.main.addEventListener('click', (e) => {
    const dh = e.target.closest('[data-dh]'); if (dh) { if (S.view === 'week') C.goto(parse(dh.dataset.dh), 'day'); else C.selectDay(dh.dataset.dh); return; }
    if (e.target.closest('#cl-empty-new')) { C.openEditor({ date: S.sel }); return; }
    const col = e.target.closest('.wk-col');
    if (col && !e.target.closest('[data-ev]')) {
      const r = col.getBoundingClientRect(), m = Math.max(0, Math.min(23 * 60 + 30, Math.floor(((e.clientY - r.top) * 60 / HH) / 30) * 30));
      C.selectDay(col.dataset.col); C.openEditor({ date: col.dataset.col, time: `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}` });
    }
  });
})();
