// Calendar screen, working with events: the details card, the editor (title, all day, start/end, repeat with interval, weekdays and end date,
// place, notes, colour, reminder), quick add from a phrase ("завтра в 15:00 встреча"), and the side panel (the selected day, quick add,
// calendars with name / colour / visibility / import, reminders). Uses window.Cal from calendar.js.
(() => {
  const C = window.Cal; if (!C) return;
  const { S, root, call, say, esc, iso, parse, p2, today, color, whenText, eventsOn, MONTHS_G, MON_S, DOW, DOW_FULL } = C;
  const sideEl = $('cl-side'), modal = C.modal, mbox = C.mbox;
  const SVG = (d, w = 1.9) => `<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const IC = { eye: SVG('<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'), eyeOff: SVG('<path d="M3 3l18 18M10.600 6.100A9.500 9.500 0 0 1 12 6c6 0 10 6 10 6a17 17 0 0 1-3.200 3.900M6.300 6.800A17 17 0 0 0 2 12s4 7 10 7c1.600 0 3-.4 4.300-1M9.900 9.900a3 3 0 0 0 4.200 4.200"/>'),
    pin: SVG('<path d="M12 21s7-6.100 7-11a7 7 0 0 0-14 0c0 4.900 7 11 7 11z"/><circle cx="12" cy="10" r="2.500"/>'), clock: SVG('<circle cx="12" cy="12" r="8.500"/><path d="M12 7v5l3 2"/>'), repeat: SVG('<path d="M4 11V9a3 3 0 0 1 3-3h11l-3-3M20 13v2a3 3 0 0 1-3 3H6l3 3"/>'),
    note: SVG('<path d="M5 4h14v16H5zM9 9h6M9 13h6"/>'), edit: SVG('<path d="M4 20h4L19 9l-4-4L4 16zM13 7l4 4"/>'), copy: SVG('<path d="M8 8h12v12H8zM4 16V4h12"/>'), trash: SVG('<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13"/>'), bell: SVG('<path d="M6 17V11a6 6 0 0 1 12 0v6l2 2H4zM10 21h4"/>') };
  const REPEATS = { none: 'Не повторять', daily: 'Каждый день', weekly: 'Каждую неделю', monthly: 'Каждый месяц', yearly: 'Каждый год' };
  const UNIT = { daily: 'дн.', weekly: 'нед.', monthly: 'мес.', yearly: 'г.' };
  const REMIND = [['def', 'По умолчанию'], ['none', 'Не напоминать'], ['5', 'За 5 минут'], ['10', 'За 10 минут'], ['15', 'За 15 минут'], ['30', 'За 30 минут'], ['60', 'За 1 час'], ['120', 'За 2 часа'], ['1440', 'За 1 день'], ['2880', 'За 2 дня']];
  const ERR = { changed: 'Событие изменилось на сервере, обновите календарь', recurring_readonly: 'Повторяющееся событие меняется в самом календаре', auth: 'Сервер не принял логин или пароль приложения', network: 'Нет связи с сервером календаря', no_title: 'Введите название события', bad_range: 'Конец раньше начала', bad_time: 'Укажите время', bad_date: 'Проверьте дату', bad_until: 'Дата окончания повтора раньше начала', bad_remind: 'Не удалось задать напоминание', too_many: 'Слишком много событий' };
  const plural = (n, a, b, c) => { const k = n % 100; return n % 10 === 1 && k !== 11 ? a : n % 10 >= 2 && n % 10 <= 4 && (k < 10 || k >= 20) ? b : c; };
  const fmtLong = (ds) => { const d = parse(ds); return `${DOW_FULL[(d.getDay() + 6) % 7]}, ${d.getDate()} ${MONTHS_G[d.getMonth()]}`; };
  const linkify = (t) => esc(t).replace(/https?:\/\/[^\s<>"]+/g, (u) => `<a href="#" class="cl-a" data-url="${u.replace(/&amp;/g, '&')}">${u.length > 50 ? u.slice(0, 48) + '…' : u}</a>`);
  let pop = null, form = null;

  // ---- dialogs and popovers ----
  function dlg({ title, body, html, ok, danger, onOk, extra }) {
    root.querySelectorAll('.cl-dlg').forEach((x) => x.remove());
    const d = document.createElement('div'); d.className = 'cl-dlg';
    d.innerHTML = `<div class="cl-db" role="dialog" aria-modal="true"><h3>${esc(title)}</h3>${html || `<p>${esc(body || '')}</p>`}<div class="cl-da"><button type="button" class="cm-try" data-d="no">${ok || extra ? 'Отмена' : 'Закрыть'}</button>${(extra || []).map((x, i) => `<button type="button" class="cm-try ${x.danger ? 'danger' : ''}" data-x="${i}">${esc(x.label)}</button>`).join('')}${ok ? `<button type="button" class="cm-try ${danger ? 'danger' : 'primary'}" data-d="ok">${esc(ok)}</button>` : ''}</div></div>`;
    root.appendChild(d); const close = () => d.remove();
    d.addEventListener('mousedown', (e) => { if (e.target === d) close(); });
    d.addEventListener('keydown', (e) => { if (e.key === 'Escape') { e.stopPropagation(); close(); } });
    d.addEventListener('click', async (e) => {
      const b = e.target.closest('[data-d], [data-x]'); if (!b) return;
      if (b.dataset.x !== undefined) { close(); extra[+b.dataset.x].run(); return; }
      if (b.dataset.d === 'ok' && onOk) { if ((await onOk()) === false) return; } close();
    });
    const f = d.querySelector('.cm-try.primary, .cm-try.danger') || d.querySelector('.cm-try'); if (f) f.focus();
  }
  const closePop = () => { if (pop) { pop.remove(); pop = null; } };
  C.closePop = closePop;
  document.addEventListener('mousedown', (e) => { if (pop && !e.target.closest('.cl-pop') && !e.target.closest('[data-ev]') && !e.target.closest('.dp-pop, .tp-pop')) closePop(); });
  function place(el, anchor) {
    const r = anchor.getBoundingClientRect(), b = root.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    let x = r.right - b.left + 8, y = r.top - b.top;
    if (x + w > b.width - 8) x = Math.max(8, r.left - b.left - w - 8);
    if (x < 8) x = Math.max(8, Math.min(b.width - w - 8, r.left - b.left));
    y = Math.max(8, Math.min(y, b.height - h - 8)); el.style.left = `${x}px`; el.style.top = `${y}px`;
  }

  // ---- details ----
  function repeatText(e) {
    if (!e.local || !e.repeat || e.repeat === 'none') return '';
    const n = e.interval || 1, base = n === 1 ? ({ daily: 'Каждый день', weekly: 'Каждую неделю', monthly: 'Каждый месяц', yearly: 'Каждый год' })[e.repeat] : `Каждые ${n} ${UNIT[e.repeat]}`;
    const days = e.repeat === 'weekly' && e.weekdays && e.weekdays.length ? ` (${e.weekdays.map((i) => DOW[i]).join(', ')})` : '';
    return `${base}${days}${e.until ? ` до ${e.until.split('-').reverse().join('.')}` : ''}`;
  }
  function showDetails(id, anchor) {
    const e = C.evById(id); if (!e) return; closePop();
    pop = document.createElement('div'); pop.className = 'cl-pop'; pop.style.setProperty('--ec', color(e)); pop.setAttribute('role', 'dialog'); pop.setAttribute('aria-label', e.title);
    const rep = repeatText(e), when = e.all_day ? (e.end_date > e.date ? `${fmtLong(e.date)} – ${fmtLong(e.end_date)}` : `${fmtLong(e.date)}, весь день`) : e.end_date > e.date ? `${fmtLong(e.date)} ${e.time} – ${fmtLong(e.end_date)} ${e.end_time}` : `${fmtLong(e.date)}, ${whenText(e)}`;
    const rem = e.local && e.remind !== undefined && e.remind !== null ? (e.remind.length ? `Напомнит: ${e.remind.map((x) => (x % 1440 === 0 ? `за ${x / 1440} дн.` : x % 60 === 0 ? `за ${x / 60} ч` : `за ${x} мин`)).join(', ')}` : 'Без напоминаний') : '';
    pop.innerHTML = `<button type="button" class="cl-px" aria-label="Закрыть" data-pop="x">×</button><h4>${esc(e.title)}</h4>
      <div class="cl-pr">${IC.clock}<span>${esc(when)}</span></div>${rep ? `<div class="cl-pr">${IC.repeat}<span>${esc(rep)}</span></div>` : ''}${e.location ? `<div class="cl-pr">${IC.pin}<span>${linkify(e.location)}</span></div>` : ''}${rem ? `<div class="cl-pr">${IC.bell}<span>${esc(rem)}</span></div>` : ''}
      ${e.notes ? `<div class="cl-pr nt">${IC.note}<span>${linkify(e.notes)}</span></div>` : ''}<div class="cl-src"><i style="background:${color(e)}"></i>${esc(e.source)}${canEdit(e) ? '' : '<small>только чтение</small>'}</div>
      ${e.src && !e.rw ? '<div class="cl-pr"><span>Повторяющееся событие этого календаря меняется только в нём самом.</span></div>' : ''}
      ${canEdit(e) ? `<div class="cl-pa"><button type="button" class="cm-try" data-pop="edit">${IC.edit}<span>Изменить</span></button><button type="button" class="cm-try" data-pop="dup" title="Создать копию">${IC.copy}</button><button type="button" class="cm-try danger" data-pop="del" title="Удалить">${IC.trash}</button></div>${e.changed ? '<button type="button" class="cl-reset" data-pop="reset">Изменено: вернуть как в серии</button>' : ''}` : ''}`;
    root.appendChild(pop); place(pop, anchor);
    pop.addEventListener('click', (ev) => {
      const a = ev.target.closest('[data-url]'); if (a) { ev.preventDefault(); openLink(a.dataset.url); return; }
      const b = ev.target.closest('[data-pop]'); if (!b) return; const k = b.dataset.pop; closePop();
      if (k === 'edit') askScope(e, (scope) => openEditor({ ev: e, scope: e.rw ? 'dav' : scope })); else if (k === 'dup') openEditor({ ev: e, dup: true }); else if (k === 'del') askDelete(e); else if (k === 'reset') resetOne(e);
    });
  }
  async function openLink(url) { if (!/^https?:/i.test(url)) return; if (m.connected) await J.send('open_url', { url }); else say('Демо: ссылка откроется в браузере'); }
  C.showDetails = showDetails;

  const isSeries = (e) => e.local && e.repeat && e.repeat !== 'none';
  const canEdit = (e) => e.local || e.rw;
  const davSource = (id) => ((S.state && S.state.sources) || []).find((x) => x.id === id);
  // repeating events: ask whether a change is for this day only or for the whole series (cb gets 'one' or 'all')
  function askScope(e, cb, title = 'Изменить повторяющееся событие?') {
    if (!isSeries(e)) { cb('all'); return; }
    dlg({ title, body: `«${e.title}» повторяется. Изменить только это событие или всю серию?`, extra: [{ label: 'Только это', run: () => cb('one') }, { label: 'Всю серию', run: () => cb('all') }] });
  }
  async function resetOne(e) {
    if (!m.connected) { say('Демо: изменения не сбрасываются'); return; }
    const r = await call({ op: 'reset_one', eid: e.eid, occ: e.occ });
    if (r.ok) { C.invalidate(); say('Событие снова как в серии'); C.load(true); } else say('Не удалось сбросить изменения');
  }
  const shift = (ds, tm, minutes) => { const d = parse(ds); d.setHours(tm ? +tm.slice(0, 2) : 0, tm ? +tm.slice(3, 5) + minutes : 0); if (!tm) d.setDate(d.getDate() + Math.round(minutes / 1440)); return [iso(d), tm ? `${p2(d.getHours())}:${p2(d.getMinutes())}` : '']; };
  const span = (d0, t0, d1, t1) => Math.round((parse(d1).setHours(t1 ? +t1.slice(0, 2) : 0, t1 ? +t1.slice(3, 5) : 0) - parse(d0).setHours(t0 ? +t0.slice(0, 2) : 0, t0 ? +t0.slice(3, 5) : 0)) / 60000);
  // an occurrence was moved or resized (drag and drop): f has its new date, time, end_date, end_time. A series moves by the same distance.
  function commitChange(e, f) {
    if (!canEdit(e)) { say(e.src ? ERR.recurring_readonly : 'События из внешнего календаря менять нельзя'); return; }
    const apply = async (scope) => {
      if (!m.connected) { say('Демо: событие не переносится'); return; }
      let r;
      if (e.rw) r = await call({ op: 'update', src: e.src, href: e.href, title: e.title, location: e.location, notes: e.notes, all_day: e.all_day, ...f });
      else if (scope === 'one') r = await call({ op: 'update_one', eid: e.eid, occ: e.occ, title: e.title, location: e.location, notes: e.notes, color: e.color, all_day: e.all_day, ...f });
      else {
        const sr = e.series || e, ds = span(e.date, e.time, f.date, f.time), de = span(e.end_date, e.end_time, f.end_date, f.end_time);
        const [d0, t0] = shift(sr.date, sr.time, ds), [d1, t1] = shift(sr.end_date, sr.end_time, de);
        r = await call({ op: 'update', eid: e.eid, date: d0, time: t0, end_date: d1, end_time: t1 });
      }
      if (r.ok) { C.invalidate(); say('Сохранено'); C.load(true); } else { say(r.message || ERR[r.error] || 'Не удалось сохранить'); C.load(true); }
    };
    askScope(e, apply, 'Перенести повторяющееся событие?');
  }
  C.commitChange = commitChange;

  function askDelete(e) {
    const gone = async (only) => {
      if (!m.connected) { say('Демо: событие не удаляется'); return; }
      const r = await call(e.rw ? { op: 'delete', src: e.src, href: e.href } : { op: 'delete', eid: e.eid, only_date: only ? (e.occ || e.date) : '' });
      if (r.ok) { C.invalidate(); say(only ? 'Это повторение удалено' : 'Событие удалено'); C.load(true); } else say(r.message || ERR[r.error] || 'Не удалось удалить событие');
    };
    if (e.repeat && e.repeat !== 'none') dlg({ title: 'Удалить повторяющееся событие?', body: `«${e.title}» повторяется. Что удалить?`, extra: [{ label: 'Только это', run: () => gone(true) }, { label: 'Все повторения', danger: true, run: () => gone(false) }] });
    else dlg({ title: 'Удалить событие?', body: `«${e.title}» будет удалено.`, ok: 'Удалить', danger: true, onOk: () => gone(false) });
  }

  // ---- editor ----
  const addMin = (ds, tm, delta) => { const d = parse(ds); d.setHours(+tm.slice(0, 2), +tm.slice(3, 5) + delta); return [iso(d), `${p2(d.getHours())}:${p2(d.getMinutes())}`]; };
  const diffMin = (d0, t0, d1, t1) => { const a = parse(d0); a.setHours(+t0.slice(0, 2), +t0.slice(3, 5)); const b = parse(d1); b.setHours(+t1.slice(0, 2), +t1.slice(3, 5)); return Math.round((b - a) / 60000); };
  function openEditor(o = {}) {
    const e = o.ev, edit = !!e && !o.dup, one = edit && o.scope === 'one', dav = edit && o.scope === 'dav', src = e && edit && e.series && !one ? e.series : e;       // a series is edited from its own times, one occurrence from its own
    const ts = o.time || '';
    const f = { eid: edit ? e.eid : '', occ: one ? e.occ : '', dav: dav ? { src: e.src, href: e.href } : null, title: e ? e.title : '', all_day: src ? !!src.all_day : false, date: src ? src.date : o.date || S.sel, time: src && !src.all_day ? src.time : ts || '09:00', end_date: src ? src.end_date : '', end_time: src && !src.all_day ? src.end_time || '' : '',
      repeat: e && e.local ? e.repeat || 'none' : 'none', interval: e && e.interval || 1, weekdays: e && e.weekdays || [], until: e && e.until || '', location: e ? e.location : '', notes: e ? e.notes : '', color: e && e.local ? e.color : '', remind: e && e.local && Array.isArray(e.remind) ? e.remind : null };
    if (!src) { [f.end_date, f.end_time] = addMin(f.date, f.time, 60); }
    else if (!f.all_day && !f.end_time) [f.end_date, f.end_time] = addMin(f.date, f.time, 60);
    form = { f, dur: f.all_day ? 60 : Math.max(0, diffMin(f.date, f.time, f.end_date, f.end_time)) };
    const cols = (S.state && S.state.colors) || ['#3df5ac'];
    const writable = ((S.state && S.state.sources) || []).filter((x) => x.writable && !x.hidden);
    const remVal = f.remind === null ? 'def' : f.remind.length === 0 ? 'none' : String(f.remind[0]);
    mbox.innerHTML = `<div class="xs-head"><h3>${one ? 'Только это событие' : edit ? 'Изменить событие' : 'Новое событие'}</h3><button type="button" class="xs-x" id="ce-close" aria-label="Закрыть">×</button></div>
      <div class="xs-body ce-body"><input id="ce-title" class="ce-title" data-fld="1" placeholder="Название события" maxlength="120" value="${esc(f.title)}" autocomplete="off" aria-label="Название">
        ${!edit && writable.length ? `<div class="ce-line"><span>Календарь</span><select id="ce-cal"><option value="own">${esc((S.state && S.state.own_name) || 'Мои события')}</option>${writable.map((x) => `<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></div>` : ''}
        <div class="ce-line"><span>Весь день</span><button type="button" class="tgl${f.all_day ? ' on' : ''}" id="ce-ad" aria-pressed="${f.all_day}"><span class="sw"></span></button></div>
        <div class="ce-grid"><label>Начало</label><div class="ce-dt"><input type="date" id="ce-d0" value="${f.date}" aria-label="Дата начала"><span class="ce-t"><input type="time" id="ce-t0" data-step="15" value="${f.time}" aria-label="Время начала"></span></div>
          <label>Конец</label><div class="ce-dt"><input type="date" id="ce-d1" value="${f.end_date}" aria-label="Дата конца"><span class="ce-t"><input type="time" id="ce-t1" data-step="15" value="${f.end_time}" aria-label="Время конца"></span></div>
          ${one || dav ? '' : `<label class="own-only">Повтор</label><div class="ce-rp own-only"><select id="ce-rep">${Object.entries(REPEATS).map(([k, v]) => `<option value="${k}"${k === f.repeat ? ' selected' : ''}>${v}</option>`).join('')}</select><span class="ce-int" id="ce-intw">каждые <input class="rm-in num" data-fld="1" id="ce-int" type="number" min="1" max="99" value="${f.interval}" aria-label="Интервал"> <em id="ce-unit"></em></span></div>
          <label class="ce-wl own-only">Дни</label><div class="ce-wd own-only" id="ce-wd">${DOW.map((d, i) => `<button type="button" class="ce-w${f.weekdays.includes(i) ? ' on' : ''}" data-w="${i}">${d}</button>`).join('')}</div>
          <label class="ce-ul own-only">До</label><div class="ce-dt ce-ud own-only"><input type="date" id="ce-until" value="${f.until}" aria-label="Повторять до"><button type="button" class="ce-clr" id="ce-uclr">без конца</button></div>`}
          <label>Место</label><input id="ce-loc" data-fld="1" class="ce-in" placeholder="Где пройдёт" maxlength="200" value="${esc(f.location)}" autocomplete="off">
          <label class="top">Заметки</label><textarea id="ce-notes" class="ce-ta" rows="3" maxlength="2000" placeholder="Что взять, о чём договориться, ссылка на встречу">${esc(f.notes)}</textarea>
          ${dav ? '' : `<label class="own-only">Цвет</label><div class="ce-sw own-only" id="ce-sw">${cols.map((c) => `<button type="button" class="ce-s${(f.color || cols[0]) === c ? ' on' : ''}" data-c="${c}" style="--c:${c}" aria-label="${c}"></button>`).join('')}</div>`}
          ${one || dav ? '' : `<label class="own-only">Напомнить</label><select id="ce-rem" class="own-only">${REMIND.map(([k, v]) => `<option value="${k}"${k === remVal ? ' selected' : ''}>${v}</option>`).join('')}</select>`}</div></div>
      <div class="xs-err" id="ce-err" role="alert"></div>
      <div class="xs-foot">${edit && !one ? '<button type="button" class="cm-try danger" id="ce-del">Удалить</button>' : ''}<span class="xs-sp"></span><button type="button" class="cm-try" id="ce-cancel">Отмена</button><button type="button" class="cm-try primary" id="ce-save">${edit ? 'Сохранить' : 'Создать'}</button></div>`;
    modal.hidden = false;
    if (window.fzDropdown) window.fzDropdown.watch(mbox);
    if (window.fzStepper) window.fzStepper.enhance(mbox);
    sync(); setTimeout(() => $('ce-title').focus(), 40);
  }
  C.openEditor = openEditor;
  const val = (id) => $(id).value;
  function sync() {
    const ad = $('ce-ad').classList.contains('on'), rep = $('ce-rep') ? val('ce-rep') : 'none';
    mbox.querySelector('.ce-grid').classList.toggle('nown', !!form.f.dav || ($('ce-cal') && val('ce-cal') !== 'own'));
    mbox.querySelectorAll('.ce-t').forEach((x) => { x.hidden = ad; });
    if (!$('ce-rep')) return;
    $('ce-intw').hidden = rep === 'none';
    mbox.querySelector('.ce-wl').hidden = rep !== 'weekly'; $('ce-wd').hidden = rep !== 'weekly';
    mbox.querySelector('.ce-ul').hidden = mbox.querySelector('.ce-ud').hidden = rep === 'none';
    if (UNIT[rep]) $('ce-unit').textContent = UNIT[rep];
    $('ce-uclr').hidden = !val('ce-until');
  }
  const bodyFields = () => {
    const ad = $('ce-ad').classList.contains('on'), rep = $('ce-rep') ? val('ce-rep') : 'none', rv = $('ce-rem') ? val('ce-rem') : 'def', sw = mbox.querySelector('.ce-s.on');
    const base = { title: val('ce-title'), all_day: ad, date: val('ce-d0'), time: ad ? '' : val('ce-t0'), end_date: val('ce-d1') || val('ce-d0'), end_time: ad ? '' : val('ce-t1'), location: val('ce-loc'), notes: val('ce-notes') };
    if (form.f.dav) return base;
    if ($('ce-cal') && val('ce-cal') !== 'own') return { ...base, calendar: val('ce-cal') };
    if (form.f.occ) return { title: val('ce-title'), all_day: ad, date: val('ce-d0'), time: ad ? '' : val('ce-t0'), end_date: val('ce-d1') || val('ce-d0'), end_time: ad ? '' : val('ce-t1'), location: val('ce-loc'), notes: val('ce-notes'), color: sw ? sw.dataset.c : '' };
    return { title: val('ce-title'), all_day: ad, date: val('ce-d0'), time: ad ? '' : val('ce-t0'), end_date: val('ce-d1') || val('ce-d0'), end_time: ad ? '' : val('ce-t1'), repeat: rep, interval: rep === 'none' ? 1 : Math.max(1, +val('ce-int') || 1),
      weekdays: rep === 'weekly' ? [...mbox.querySelectorAll('.ce-w.on')].map((b) => +b.dataset.w) : [], until: rep === 'none' ? '' : val('ce-until'), location: val('ce-loc'), notes: val('ce-notes'), color: sw ? sw.dataset.c : '', remind: rv === 'def' ? null : rv === 'none' ? [] : [+rv] };
  };
  const closeEditor = () => { modal.hidden = true; mbox.innerHTML = ''; form = null; };
  async function save() {
    const f = bodyFields(), err = $('ce-err');
    if (!f.title.trim()) { err.textContent = ERR.no_title; $('ce-title').focus(); return; }
    if (!f.all_day && (!f.time || !f.end_time)) { err.textContent = ERR.bad_time; return; }
    if (f.date > f.end_date || (!f.all_day && f.date === f.end_date && f.end_time < f.time)) { err.textContent = ERR.bad_range; return; }
    err.textContent = '';
    const edit = form.f.eid || (form.f.dav ? 'dav' : ''), b = $('ce-save'); b.disabled = true;
    if (!m.connected) { say('Демо: событие не сохраняется'); closeEditor(); return; }
    const r = await call(form.f.dav ? { op: 'update', src: form.f.dav.src, href: form.f.dav.href, ...f } : form.f.occ ? { op: 'update_one', eid: edit, occ: form.f.occ, ...f } : edit ? { op: 'update', eid: edit, ...f } : { op: 'add', ...f });
    b.disabled = false;
    if (!r.ok) { err.textContent = r.message || ERR[r.error] || 'Не удалось сохранить событие'; return; }
    if (r.state) S.state = { ...S.state, ...r.state };
    closeEditor(); C.invalidate(); say(edit ? 'Изменения сохранены' : 'Событие создано'); if (!edit) C.selectDay(f.date); C.load(true);
  }
  mbox.addEventListener('click', (e) => {
    const t = e.target, b = t.closest('button'); if (!b || !form) return;
    if (b.id === 'ce-close' || b.id === 'ce-cancel') closeEditor();
    else if (b.id === 'ce-save') save();
    else if (b.id === 'ce-del') { const ev = form.f; closeEditor(); askDelete({ eid: ev.eid, title: ev.title, repeat: 'none', date: ev.date }); }
    else if (b.id === 'ce-ad') { b.classList.toggle('on'); b.setAttribute('aria-pressed', String(b.classList.contains('on'))); sync(); }
    else if (b.id === 'ce-uclr') { $('ce-until').value = ''; sync(); }
    else if (b.dataset.w !== undefined) b.classList.toggle('on');
    else if (b.dataset.c) { mbox.querySelectorAll('.ce-s').forEach((x) => x.classList.toggle('on', x === b)); }
  });
  mbox.addEventListener('change', (e) => {
    const id = e.target.id;
    if (id === 'ce-cal') sync();
    else if (id === 'ce-rep' && $('ce-rep')) { if (val('ce-rep') === 'weekly' && !mbox.querySelector('.ce-w.on')) { const w = (parse(val('ce-d0')).getDay() + 6) % 7; mbox.querySelector(`.ce-w[data-w="${w}"]`).classList.add('on'); } sync(); }
    else if (id === 'ce-d0' || id === 'ce-t0') {
      if (!$('ce-ad').classList.contains('on')) { const [d, t] = addMin(val('ce-d0'), val('ce-t0') || '00:00', form.dur); $('ce-d1').value = d; $('ce-t1').value = t; }
      else if (val('ce-d1') < val('ce-d0')) $('ce-d1').value = val('ce-d0');
    } else if (id === 'ce-d1' || id === 'ce-t1') { if (!$('ce-ad').classList.contains('on')) form.dur = Math.max(0, diffMin(val('ce-d0'), val('ce-t0') || '00:00', val('ce-d1'), val('ce-t1') || '00:00')); }
    else if (id === 'ce-until') sync();
  });
  mbox.addEventListener('input', (e) => { if (e.target.id === 'ce-int') sync(); });
  mbox.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.id === 'ce-title') { e.preventDefault(); save(); } });
  modal.addEventListener('mousedown', (e) => { if (e.target === modal) closeEditor(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden && !document.querySelector('.dp-pop, .tp-pop, .dd-pop')) closeEditor(); });

  // ---- quick add ("завтра в 15:00 встреча с Аней, каждую неделю") ----
  // the phrase is parsed by the core (one parser for this field and for the voice command); without a core only the title is taken
  const fetchQuick = async (text) => (m.connected ? call({ op: 'quick', text, date: S.sel }) : { ok: true, title: text.trim(), date: S.sel, time: '', end_time: '', repeat: 'none', weekdays: [] });
  let quickTimer = 0;
  const quickLabel = (q) => {
    if (!q.title && !q.date) return '';
    const d = q.date ? parse(q.date) : null;
    return [d ? `${DOW_FULL[(d.getDay() + 6) % 7].slice(0, 2)}, ${d.getDate()} ${MON_S[d.getMonth()]}` : 'без даты', d ? (q.time ? (q.end_time ? `${q.time}–${q.end_time}` : q.time) : 'весь день') : '', q.repeat !== 'none' ? REPEATS[q.repeat].toLowerCase() : ''].filter(Boolean).join(' · ');
  };
  async function quickAdd() {
    const inp = $('cl-quick'), q = await fetchQuick(inp.value);
    if (!q.title) { say('Добавьте название: «завтра в 15:00 встреча»'); return; }
    if (!q.date) q.date = S.sel;
    const f = { title: q.title, date: q.date, time: q.time, all_day: !q.time, end_time: q.end_time, repeat: q.repeat, weekdays: q.weekdays };
    if (!m.connected) { say('Демо: событие не сохраняется'); inp.value = ''; return; }
    const r = await call({ op: 'add', ...f });
    if (!r.ok) { say(ERR[r.error] || 'Не удалось добавить событие'); return; }
    inp.value = ''; $('cl-qprev').textContent = ''; C.invalidate(); say(`Добавлено: ${q.title}`); C.selectDay(q.date); C.load(true);
  }

  // ---- side panel ----
  const dayRows = (ds) => {
    const list = eventsOn(ds);
    return list.length ? list.map((e) => `<button type="button" class="sd-row" data-ev="${esc(e.id)}" style="--ec:${color(e)}"><span class="sd-t">${e.all_day ? 'весь день' : e.time}${!e.all_day && e.end_time && e.end_time !== e.time ? `<small>${e.end_time}</small>` : ''}</span><i></i><span class="sd-x"><b>${esc(e.title)}</b><small>${[e.location, e.source].filter(Boolean).map(esc).join(' · ')}</small></span></button>`).join('')
      : '<div class="cl-none">В этот день событий нет.</div>';
  };
  function sourcesHtml() {
    const st = S.state || {}, srcs = st.sources || [], bad = Object.fromEntries((S.status || []).map((x) => [x.ref, x]));
    const row = (s) => { const b = bad[s.ref], tag = s.hidden ? '' : b && !b.ok ? '<em class="bad">не загружается</em>' : b && b.stale ? '<em class="stale">старые данные</em>' : s.status === 'error' ? '<em class="bad">не загружается</em>' : '';
      return `<div class="sc-row${s.hidden ? ' off' : ''}" data-ref="${esc(s.ref)}"><button type="button" class="sc-dot" data-sc="color" style="--c:${s.color}" title="Цвет"></button><span class="sc-name" data-sc="rename" title="${esc(s.ref)}">${esc(s.name)}</span>${s.writable ? '<em class="rw">запись</em>' : ''}${tag}<button type="button" class="sc-b" data-sc="hide" title="${s.hidden ? 'Показать события' : 'Скрыть события'}" aria-pressed="${!s.hidden}">${s.hidden ? IC.eyeOff : IC.eye}</button><button type="button" class="sc-b x" data-sc="rm" title="Отключить календарь" aria-label="Отключить календарь">×</button></div>`; };
    return `<div class="sc-row own"><i class="sc-dot" style="--c:${(st.colors || ['#3df5ac'])[0]}"></i><span class="sc-name">${esc(st.own_name || 'Мои события')}</span><small>Jarvis напомнит вслух</small></div>${srcs.map(row).join('')}`;
  }
  function paintSide() {
    if (!S.side) { sideEl.innerHTML = ''; return; }
    const keepQ = $('cl-quick') ? $('cl-quick').value : '', hadFocus = document.activeElement && document.activeElement.id === 'cl-quick', st = S.state || { remind: { enabled: true, minutes: 15 } }, rm = st.remind || { enabled: true, minutes: 15 };
    const d = parse(S.sel);
    sideEl.innerHTML = `<section class="cm-card cl-card"><h3>${d.getDate()} ${MONTHS_G[d.getMonth()]}<small>${DOW_FULL[(d.getDay() + 6) % 7]}${S.sel === today() ? ' · сегодня' : ''}</small></h3><div class="cl-list">${dayRows(S.sel)}</div><button type="button" class="cm-try primary cl-add" id="cl-add">Добавить событие</button></section>
      <section class="cm-card cl-card"><h3>Быстро</h3><label class="cl-q"><input id="cl-quick" data-fld="1" placeholder="завтра в 15:00 встреча с Аней" autocomplete="off" value="${esc(keepQ)}" aria-label="Быстро добавить событие"></label><div class="cl-qprev" id="cl-qprev"></div></section>
      <section class="cm-card cl-card"><h3>Календари</h3><div class="sc-list" id="sc-list">${sourcesHtml()}</div>
        <div class="cl-addsrc"><label><input id="cl-src" placeholder="Ссылка на .ics" autocomplete="off" aria-label="Ссылка на календарь"></label><button type="button" class="cm-try primary" id="cl-srcgo">Добавить</button></div>
        <div class="cl-srcrow"><button type="button" class="cm-try" id="cl-file">Файл .ics…</button><button type="button" class="cm-try" id="cl-dav" title="Календарь, в который можно и записывать: Яндекс, iCloud, Nextcloud">CalDAV…</button><span class="cl-srcmsg" id="cl-srcmsg"></span></div>
        <details class="cl-how"><summary>Как подключить Google, Outlook, Яндекс</summary><ol><li>Google: calendar.google.com, настройки нужного календаря, «Секретный адрес в формате iCal».</li><li>Outlook: Календарь, «Общий доступ», «Опубликовать», ссылка ICS.</li><li>Яндекс: настройки календаря, «Экспорт», ссылка ICS.</li></ol><p>Ссылка даёт только чтение. Чтобы создавать и менять события отсюда, подключите календарь через CalDAV (Яндекс, iCloud, Nextcloud): нужен пароль приложения. Google и Outlook для записи требуют отдельного приложения OAuth, поэтому у них только чтение.</p><button type="button" class="cm-try" id="cl-gset">Открыть настройки Google</button></details></section>
      <section class="cm-card cl-card cl-rem"><div><span>Напоминать вслух</span><small>Jarvis скажет за ${rm.minutes} ${plural(rm.minutes, 'минуту', 'минуты', 'минут')} до события</small></div><select id="cl-rm" aria-label="За сколько минут напомнить">${[5, 10, 15, 30, 45, 60, 90, 120].map((n) => `<option value="${n}"${n === rm.minutes ? ' selected' : ''}>за ${n} мин</option>`).join('')}</select><button type="button" class="tgl${rm.enabled ? ' on' : ''}" id="cl-rmsw" aria-pressed="${rm.enabled}"><span class="sw"></span></button></section>`;
    if (window.fzDropdown) window.fzDropdown.watch(sideEl);
    if (keepQ) { previewQuick(keepQ); if (hadFocus) $('cl-quick').focus(); }
  }
  C.paintSide = paintSide;

  async function srcAction(act, row, btn) {
    const ref = row.dataset.ref;
    if (act === 'hide') { const s = S.state.sources.find((x) => x.ref === ref), r = m.connected ? await call({ op: 'source_set', ref, hidden: !s.hidden }) : { ok: true, state: { ...S.state, sources: S.state.sources.map((x) => (x.ref === ref ? { ...x, hidden: !x.hidden } : x)) } }; if (r.ok) { S.state = { ...S.state, ...r.state }; C.invalidate(); C.load(true); } }
    else if (act === 'rm') dlg({ title: 'Отключить календарь?', body: 'Его события исчезнут отсюда и из ответов Jarvis. Сам календарь не удаляется.', ok: 'Отключить', danger: true, onOk: async () => { const r = m.connected ? await call({ op: 'remove_source', ref }) : null; if (r && r.ok) { S.state = { ...S.state, ...r.state }; C.invalidate(); C.load(true); } else if (!r) say('Демо: календарь не отключается'); } });
    else if (act === 'color') {
      closePop(); pop = document.createElement('div'); pop.className = 'cl-pop sw'; const cols = S.state.colors || [];
      pop.innerHTML = cols.map((c) => `<button type="button" class="ce-s" data-c="${c}" style="--c:${c}" aria-label="${c}"></button>`).join(''); root.appendChild(pop); place(pop, btn);
      pop.addEventListener('click', async (e) => { const b = e.target.closest('[data-c]'); if (!b) return; closePop(); if (!m.connected) { say('Демо: цвет не сохраняется'); return; } const r = await call({ op: 'source_set', ref, color: b.dataset.c }); if (r.ok) { S.state = { ...S.state, ...r.state }; C.invalidate(); C.load(true); } });
    } else if (act === 'rename') {
      const nm = row.querySelector('.sc-name'), cur = nm.textContent, inp = document.createElement('input'); inp.className = 'sc-edit'; inp.value = cur; inp.maxLength = 40; inp.setAttribute('data-fld', '1'); nm.replaceWith(inp); inp.focus(); inp.select();
      let done = false; const fin = async (ok) => { if (done) return; done = true; const v = inp.value.trim(); if (ok && v !== cur && m.connected) { const r = await call({ op: 'source_set', ref, name: v }); if (r.ok) S.state = { ...S.state, ...r.state }; C.invalidate(); C.load(true); } else paintSide(); };
      inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') fin(true); else if (e.key === 'Escape') { e.stopPropagation(); fin(false); } }); inp.addEventListener('blur', () => fin(true));
    }
  }
  const srcMsg = (t, bad) => { const el = $('cl-srcmsg'); if (el) { el.textContent = t; el.classList.toggle('bad', !!bad); } };
  sideEl.addEventListener('click', async (e) => {
    const t = e.target, b = t.closest('button'); if (!b) return;
    const sc = b.dataset.sc; if (sc) { srcAction(sc, b.closest('.sc-row'), b); return; }
    if (b.id === 'cl-add') openEditor({ date: S.sel });
    else if (b.id === 'cl-srcgo') {
      const ref = $('cl-src').value.trim(); if (!ref) { srcMsg('Вставьте ссылку на календарь', true); return; }
      if (!m.connected) { srcMsg('Демо: календарь не подключается'); return; }
      b.disabled = true; const r = await call({ op: 'add_source', ref }); b.disabled = false;
      if (r.ok) { S.state = { ...S.state, ...r.state }; C.invalidate(); say('Календарь подключён'); C.load(true); } else srcMsg(r.error === 'exists' ? 'Этот календарь уже подключён' : 'Не удалось подключить календарь', true);
    } else if (b.id === 'cl-dav') { if (window.CalDav) window.CalDav.open(); }
    else if (b.id === 'cl-file') {
      if (!m.connected) { srcMsg('Демо: выбор файла'); return; }
      const r = await call({ op: 'import_file' });
      if (r.ok) { S.state = { ...S.state, ...r.state }; C.invalidate(); say('Календарь из файла добавлен'); C.load(true); } else if (r.error !== 'cancelled') srcMsg('Нужен файл .ics до 8 МБ', true);
    } else if (b.id === 'cl-gset') openLink('https://calendar.google.com/calendar/u/0/r/settings');
    else if (b.id === 'cl-rmsw') { const on = !b.classList.contains('on'), r = m.connected ? await call({ op: 'remind', enabled: on, minutes: +$('cl-rm').value }) : { ok: true, state: { remind: { enabled: on, minutes: +$('cl-rm').value } } }; if (r.ok) { S.state = { ...S.state, ...r.state }; paintSide(); } }
  });
  sideEl.addEventListener('change', async (e) => {
    if (e.target.id !== 'cl-rm') return;
    const on = $('cl-rmsw').classList.contains('on'), r = m.connected ? await call({ op: 'remind', enabled: on, minutes: +e.target.value }) : { ok: true, state: { remind: { enabled: on, minutes: +e.target.value } } };
    if (r.ok) { S.state = { ...S.state, ...r.state }; paintSide(); }
  });
  async function previewQuick(text) { const q = text.trim() ? await fetchQuick(text) : null, el = $('cl-qprev'); if (el && $('cl-quick') && $('cl-quick').value === text) el.textContent = q && q.ok ? quickLabel(q) : ''; }
  sideEl.addEventListener('input', (e) => { if (e.target.id === 'cl-quick') { clearTimeout(quickTimer); const t = e.target.value; quickTimer = setTimeout(() => previewQuick(t), 180); if (!t.trim()) $('cl-qprev').textContent = ''; } });
  sideEl.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.id === 'cl-quick') { e.preventDefault(); quickAdd(); } else if (e.key === 'Enter' && e.target.id === 'cl-src') { e.preventDefault(); $('cl-srcgo').click(); } });
  C.sideEl = sideEl;
})();
