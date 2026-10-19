// "Кино" screen: what is playing on this PC with its controls, a search for something to watch, and the viewing services Jarvis uses for it.
// Data: the `nowplaying` topic and the `media` command (Windows media sessions), the `cinema` command (services, search; ui_next/bridge/cinema.py).
// Without a core the screen shows sample services and refuses changes. Relies on globals of app.html: $, J, m, ic, esc, VIEW, and window.LOOK.ui and window.NP.
(() => {
  const body = $('ci-body'), toast = $('ci-toast'), U = window.LOOK.ui, NP = window.NP;
  const DEMO = { ok: true, default: 'youtube', services: [{ id: 'youtube', name: 'YouTube', domain: 'youtube.com', search: 'x', own_search: true }, { id: '1plus1', name: '1+1 video', domain: '1plus1.video', search: '', own_search: false }],
    presets: [{ id: 'netflix', name: 'Netflix', domain: 'netflix.com', own_search: true }, { id: 'megogo', name: 'Megogo', domain: 'megogo.net', own_search: false }, { id: 'teleportal', name: 'Телепортал', domain: 'teleportal.ua', own_search: false }] };
  const ERR = { required: 'Заполните название и сайт', bad_domain: 'Не похоже на адрес сайта, например example.com', exists: 'Этот сайт уже в списке', too_many: 'Сервисов уже слишком много', not_found: 'Записи уже нет', write_failed: 'Не удалось сохранить', not_a_folder: 'Это не папка', no_next: 'Следующая серия не анонсирована', bad_value: 'Значение не подошло', open_failed: 'Не получилось открыть файл', cancelled: '', no_handler: 'Jarvis ещё запускается' };
  let infoBox = null, LB = null, showAllMovies = false, scanning = false, C = null, kind = 'movie', toastTimer = 0, form = { q: '', season: '', episode: '', svc: '' }, custom = false;
  const say = (t, ms = 2800) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), ms); };
  const MON = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const day = (s) => { const d = new Date(s); return `${d.getDate()} ${MON[d.getMonth()]}`; };
  async function info(title) {
    if (!title || title.length < 2) { say('Введите название'); return; }
    say('Спрашиваю TVmaze…', 8000); const r = await call({ op: 'info', title }); toast.classList.remove('on'); if (!r.ok) { if (r.error !== 'offline') say(r.error === 'no_data' ? 'Сведений нет: нужен интернет и название как в TVmaze (чаще английское)' : 'Не получилось', 6000); return; }
    const e = r.next ? `следующая серия ${r.next.season}x${String(r.next.number).padStart(2, '0')} выйдет ${day(r.next.airstamp)}` : r.status === 'Ended' ? 'сериал завершён' : `дата следующей серии не объявлена${r.prev ? `, последняя вышла ${day(r.prev.airstamp)}` : ''}`;
    infoBox = { title, text: `${r.name}: ${e}`, cal: !!r.next, url: r.url }; render();
  }

  async function call(b) { if (!m.connected) { say('Без ядра изменить нельзя'); return { ok: false, error: 'offline' }; } return (await J.send('cinema', b)) || { ok: false }; }
  async function act(b, okText) { const r = await call(b); if (r.ok) { if (r.services) C = r; if (okText) say(okText); render(); } else if (r.error !== 'offline') say(ERR[r.error] || 'Не получилось'); return r; }
  async function load() { if (!m.connected) { C = DEMO; LB = null; render(); return; } const r = await call({ op: 'state' }); if (r.ok) { C = r; render(); } loadLib(false); }
  async function loadLib(force) { if (!m.connected) return; scanning = true; render(); const r = await call({ op: 'lib', force }); scanning = false; if (r.ok) LB = r; render(); }
  async function libAct(b, okText) { const r = await call(b); if (r.ok) { LB = r; if (okText) say(okText); render(); } else if (r.error !== 'offline') { const t = ERR[r.error] ?? 'Не получилось'; if (t) say(t); } return r; }

  const btn = (t, a, cls = '') => `<button type="button" class="cm-try ${cls}" ${a}>${t}</button>`;

  function sessionRow(s) {
    const playing = s.status === 'playing', p = NP.live(s);
    return `<div class="ci-s ${s.status}" data-id="${esc(s.id)}"><div class="np-top"><span class="np-eq" aria-hidden="true"><i></i><i></i><i></i></span><div class="np-t"><b title="${esc(s.title)}">${esc(s.title || 'Без названия')}</b><small>${esc([s.artist, s.app_name, playing ? '' : 'на паузе'].filter(Boolean).join(' · '))}</small></div>`
      + `<div class="np-ctl"><button type="button" data-a="prev" title="Предыдущий"${s.can.prev ? '' : ' disabled'}>${NP.svg('prev')}</button><button type="button" data-a="seek" data-s="-10" title="Назад на 10 секунд"${s.can.seek ? '' : ' disabled'}>${NP.svg('back')}<em>10</em></button>`
      + `<button type="button" class="np-main" data-a="toggle" title="${playing ? 'Пауза' : 'Играть'}">${NP.svg(playing ? 'pause' : 'play', 20)}</button><button type="button" data-a="seek" data-s="10" title="Вперёд на 10 секунд"${s.can.seek ? '' : ' disabled'}>${NP.svg('fwd')}<em>10</em></button>`
      + `<button type="button" data-a="next" title="Следующий"${s.can.next ? '' : ' disabled'}>${NP.svg('next')}</button></div></div>`
      + `<div class="np-bar${s.can.seek && s.dur ? '' : ' off'}" data-bar="1"><i style="width:${s.dur ? Math.min(100, p / s.dur * 100).toFixed(1) : 0}%"></i></div><div class="np-time"><span>${NP.fmt(p)}</span><span>${s.dur ? NP.fmt(s.dur) : ''}</span></div></div>`;
  }
  function nowCard() {
    const list = NP.list();
    const inner = list.length ? list.map(sessionRow).join('') : '<div class="vc-note">Сейчас ничего не играет. Запустите видео в браузере или плеере: оно появится здесь, и им можно управлять отсюда и голосом.</div>';
    return U.card('var(--cyan)', 'cam', 'Сейчас играет', `<div id="ci-now">${inner}</div>`);
  }
  function findCard() {
    const svcs = C.services, cur = form.svc && svcs.some((s) => s.id === form.svc) ? form.svc : C.default;
    return U.card('var(--green)', 'search', 'Найти и включить',
      `<small class="vc-note">Откроется страница поиска в браузере. Голосом то же самое: «включи фильм Дюна на Netflix» или «найди сериал Шерлок, сезон 2 серия 3».</small>`
      + `<div class="ci-form"><label>Название<input id="ci-q" maxlength="200" placeholder="Например: Матрица" value="${esc(form.q)}" autocomplete="off"></label>`
      + `<div class="ci-row"><div class="seg2 ci-kind" role="radiogroup" style="--n:2;--i:${kind === 'series' ? 1 : 0}"><button type="button" class="${kind === 'movie' ? 'on' : ''}" data-kind="movie" role="radio" aria-checked="${kind === 'movie'}">Фильм</button><button type="button" class="${kind === 'series' ? 'on' : ''}" data-kind="series" role="radio" aria-checked="${kind === 'series'}">Сериал</button></div>`
      + (kind === 'series' ? `<label class="ci-n">Сезон<input id="ci-se" type="number" min="1" max="99" value="${esc(form.season)}" placeholder="любой"></label><label class="ci-n">Серия<input id="ci-ep" type="number" min="1" max="999" value="${esc(form.episode)}" placeholder="любая"></label>` : '') + `</div>`
      + `<label>Где искать<select id="ci-svc">${svcs.length ? svcs.map((s) => `<option value="${esc(s.id)}"${s.id === cur ? ' selected' : ''}>${esc(s.name)}</option>`).join('') : '<option value="">Обычный поиск в интернете</option>'}</select></label>`
      + `<div class="vc-actions">${btn('Открыть поиск', 'data-go="1"', 'primary')}${kind === 'series' ? btn('Когда новая серия', 'data-info="1"') : ''}${btn('В список', 'data-later="1"')}</div>${infoBox ? `<div class="vc-prev">${esc(infoBox.text)}${infoBox.cal ? `<div class="vc-actions">${btn('Добавить в календарь', 'data-incal="1"')}</div>` : ''}</div>` : ''}</div>`);
  }
  function libCard() {
    if (!m.connected) return U.card('var(--green)', 'list', 'Моя библиотека', '<div class="vc-note">Без ядра библиотека недоступна.</div>');
    const add = `<div class="vc-actions">${btn('Добавить папку…', 'data-ladd="1"', 'primary')}${LB && LB.folders.length ? btn('Обновить', 'data-lscan="1"') : ''}</div>`;
    const note = '<small class="vc-note">Папки с вашими фильмами и сериалами. Номер сезона и серии читается из имени файла (S02E03, 2x03, «Сезон 2», «Серия 3»). Файлы открываются в плеере Windows по умолчанию, а Jarvis запоминает, где вы остановились: «продолжи сериал Шерлок».</small>';
    if (!LB) return U.card('var(--green)', 'list', 'Моя библиотека', `${note}<div class="vc-note">${scanning ? 'Ищу файлы…' : 'Загружаю…'}</div>`);
    const fol = LB.folders.map((f) => `<div class="tl-row"><div class="tl-t"><b title="${esc(f)}">${esc(f)}</b></div><div class="tl-b">${btn('Убрать', `data-lrm="${esc(f)}"`, 'tl-del')}</div></div>`).join('');
    const ser = LB.series.map((s) => `<div class="tl-row"><div class="tl-t"><b>${esc(s.title)}</b><small>${s.seasons} сез. · ${s.episodes} серий${s.last ? ` · остановились на ${esc(s.last)}` : ''}</small></div><div class="tl-b">${btn('Когда новая', `data-linfo="${esc(s.title)}"`)}${btn(s.last ? 'Дальше' : 'Смотреть', `data-lnext="${esc(s.key)}"`, 'primary')}</div></div>`).join('');
    const mv = showAllMovies ? LB.movies : LB.movies.slice(0, 12);
    const mov = LB.movies.length ? `<div class="ci-sub">Фильмы (${LB.movies_total})</div><div class="tl-chips">${mv.map((x) => `<button type="button" class="ci-pre" data-lplay="${esc(x.path)}" title="${esc(x.path)}">${esc(x.title)}${x.year ? ` (${x.year})` : ''}</button>`).join('')}${LB.movies.length > 12 ? `<button type="button" class="ci-pre" data-lmore="1">${showAllMovies ? 'Свернуть' : `Ещё ${LB.movies.length - 12}`}</button>` : ''}</div>` : '';
    const empty = !LB.folders.length ? '<div class="vc-note">Папки не добавлены.</div>' : (!LB.files ? '<div class="vc-note">В этих папках видеофайлов не нашлось.</div>' : '');
    return U.card('var(--green)', 'list', 'Моя библиотека', `${note}${fol ? `<div class="tl-list">${fol}</div>` : ''}${empty}${scanning ? '<div class="vc-note">Ищу файлы…</div>' : ''}${LB.series.length ? `<div class="ci-sub">Сериалы (${LB.series.length})</div><div class="tl-list">${ser}</div>` : ''}${mov}${add}`);
  }
  function laterCard() {
    const rows = (C.later || []).map((x) => `<div class="tl-row"><div class="tl-t"><b>${esc(x.title)}</b><small>${x.kind === 'series' ? 'Сериал' : 'Фильм'}</small></div><div class="tl-b">${btn('Искать', `data-lfind="${esc(x.id)}"`, 'primary')}${btn('Убрать', `data-lrmv="${esc(x.id)}"`, 'tl-del')}</div></div>`).join('');
    return U.card('var(--mag, #cc44ff)', 'check', 'Посмотреть позже', `<small class="vc-note">Что хотите посмотреть потом. Добавить можно кнопкой «В список» у формы поиска или голосом: «добавь Дюна в список просмотра».</small>${rows ? `<div class="tl-list">${rows}</div>` : '<div class="vc-note">Список пуст.</div>'}`);
  }
  function modeCard() {
    const md = C.mode || { active: false, level: 30 };
    return U.card('var(--amber)', 'theme', 'Режим кино', `<small class="vc-note">Приглушает яркость экрана для просмотра и возвращает прежнюю при выключении. Голосом: «включи режим кино», «выключи режим кино».</small>`
      + `<div class="ci-row"><label class="ci-n">Яркость, %<input id="ci-lv" type="number" min="5" max="80" value="${md.level}"></label><div class="vc-actions">${btn(md.active ? 'Выключить' : 'Включить', 'data-mode="1"', md.active ? '' : 'primary')}</div></div>${md.active ? '<div class="vc-note">Режим кино включён.</div>' : ''}`);
  }
  function servicesCard() {
    const rows = C.services.map((s) => `<div class="tl-row"><div class="tl-t"><b>${esc(s.name)}${s.id === C.default ? '<em class="ci-def">по умолчанию</em>' : ''}</b><small>${esc(s.domain)} · ${s.own_search ? 'свой поиск сервиса' : 'поиск по сайту через интернет'}</small></div><div class="tl-b">${s.id === C.default ? '' : btn('Основной', `data-def="${esc(s.id)}"`)}${btn('Убрать', `data-rm="${esc(s.id)}"`, 'tl-del')}</div></div>`).join('');
    const pre = C.presets.length ? `<div class="ci-sub">Добавить из списка</div><div class="tl-chips">${C.presets.map((p) => `<button type="button" class="ci-pre" data-pre="${esc(p.id)}" title="${esc(p.domain)}">+ ${esc(p.name)}</button>`).join('')}</div>` : '';
    const cform = custom ? `<div class="tl-form"><label>Название<input id="ci-nn" maxlength="40" placeholder="Мой сервис" autocomplete="off"></label><label>Сайт<input id="ci-nd" maxlength="100" placeholder="example.com" autocomplete="off"></label>`
      + `<label>Адрес поиска, если знаете<input id="ci-ns" maxlength="400" placeholder="https://example.com/search?q={q}" autocomplete="off"></label><small class="vc-note">В адресе {q} заменится названием. Без него Jarvis ищет по сайту через обычный поиск.</small><div class="vc-actions">${btn('Добавить', 'data-cadd="1"', 'primary')}${btn('Отмена', 'data-ccancel="1"')}</div></div>` : `<div class="vc-actions">${btn('Свой сайт…', 'data-custom="1"')}</div>`;
    return U.card('var(--amber)', 'ext', 'Где смотреть', `<small class="vc-note">Сервисы, в которых Jarvis ищет фильмы и сериалы. Ничего не нужно подключать: он открывает обычную страницу поиска, без аккаунтов и ключей.</small>${rows ? `<div class="tl-list">${rows}</div>` : '<div class="vc-note">Список пуст: поиск пойдёт по всему интернету.</div>'}${pre}${cform}`);
  }
  function tipsCard() {
    const t = ['«перемотай на 5 минут назад»', '«что сейчас играет»', '«сколько осталось до конца»', '«включи сериал Ивановы-Ивановы на Мегого»', '«где посмотреть Дюна»', '«продолжи сериал Шерлок»', '«когда выйдет следующая серия Шерлока»', '«пауза» и «продолжай»'];
    return U.card('var(--mag, #cc44ff)', 'mic', 'Что можно сказать', `<div class="tl-chips">${t.map((x) => `<span class="tl-chip ci-say">${x}</span>`).join('')}</div><small class="vc-note">Команды видео работают с любым плеером и вкладкой браузера, где идёт видео. Даты серий: данные <b>TVmaze</b> (tvmaze.com, CC BY-SA).</small>`);
  }
  function render() {
    if (!C) { body.innerHTML = '<div class="vc-note" style="padding:1rem">Загружаю…</div>'; return; }
    const keep = ['ci-q', 'ci-se', 'ci-ep', 'ci-svc'].map((id) => $(id)).filter(Boolean); for (const e of keep) { if (e.id === 'ci-q') form.q = e.value; else if (e.id === 'ci-se') form.season = e.value; else if (e.id === 'ci-ep') form.episode = e.value; else form.svc = e.value; }
    body.innerHTML = `<div class="vc-grid"><div class="vc-col">${nowCard()}${libCard()}${laterCard()}</div><div class="vc-col">${findCard()}${modeCard()}${servicesCard()}${tipsCard()}</div></div>`;
    if (window.fzDropdown) window.fzDropdown.watch(body);
  }
  function paintNow() {
    const box = $('ci-now'); if (!box || VIEW !== 'cinema') return;
    const list = NP.list(), ids = [...box.querySelectorAll('.ci-s')].map((e) => e.dataset.id + e.querySelector('.np-t b').textContent + (e.classList.contains('playing') ? 'p' : 'q')).join('|');
    const want = list.map((s) => s.id + (s.title || 'Без названия') + (s.status === 'playing' ? 'p' : 'q')).join('|');
    if (ids !== want || (!list.length && !box.querySelector('.vc-note'))) { render(); return; }
    list.forEach((s, i) => { const row = box.querySelectorAll('.ci-s')[i], p = NP.live(s); if (!row) return; row.querySelector('.np-bar i').style.width = s.dur ? `${Math.min(100, p / s.dur * 100).toFixed(1)}%` : '0%'; const t = row.querySelectorAll('.np-time span'); t[0].textContent = NP.fmt(p); t[1].textContent = s.dur ? NP.fmt(s.dur) : ''; });
  }

  body.addEventListener('click', async (e) => {
    const b = e.target.closest('button'), bar = e.target.closest('[data-bar]');
    const row = e.target.closest('.ci-s');
    if (bar && row && !bar.classList.contains('off')) { const s = NP.list().find((x) => x.id === row.dataset.id); if (s && s.dur) { const r = bar.getBoundingClientRect(); NP.control('seek_to', s.id, Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * s.dur); } return; }
    if (!b) return; const d = b.dataset;
    if (d.a && row) { if (d.a === 'seek') NP.control('seek_by', row.dataset.id, +d.s); else NP.control(d.a, row.dataset.id); return; }
    if (d.kind) { form.q = $('ci-q').value; kind = d.kind; render(); return; }
    if (d.go) {
      const q = $('ci-q').value.trim(); if (q.length < 2) { say('Введите название'); $('ci-q').focus(); return; }
      const r = await call({ op: 'watch', title: q, id: $('ci-svc').value, kind, season: $('ci-se') ? $('ci-se').value : '', episode: $('ci-ep') ? $('ci-ep').value : '' });
      if (r.ok) say(r.service ? `Открыл поиск: ${r.service}` : 'Открыл поиск в интернете'); else if (r.error !== 'offline') say(ERR[r.error] || 'Не получилось открыть поиск'); return;
    }
    if (d.later) { const q = $('ci-q').value.trim(); if (q.length < 2) { say('Введите название'); $('ci-q').focus(); return; } const r = await act({ op: 'later_add', title: q, kind }, 'Добавлено в список'); if (r.ok) { form.q = ''; render(); } return; }
    if (d.lrmv) { act({ op: 'later_remove', id: d.lrmv }, 'Убрано из списка'); return; }
    if (d.lfind) { const x = (C.later || []).find((i) => i.id === d.lfind); if (x) { const r = await call({ op: 'watch', title: x.title, id: $('ci-svc') ? $('ci-svc').value : '', kind: x.kind }); if (r.ok) say(r.service ? `Открыл поиск: ${r.service}` : 'Открыл поиск в интернете'); } return; }
    if (d.mode) {
      const md = C.mode || { active: false };
      const lv = parseInt($('ci-lv').value, 10); if (!md.active && lv !== md.level) { const lr = await act({ op: 'mode_level', value: lv }); if (!lr.ok) return; }
      const r = await act({ op: 'mode', on: !md.active }, md.active ? 'Яркость возвращена' : 'Режим кино включён'); if (!r.ok && r.error === 'no_brightness') say('Не удалось изменить яркость этого экрана'); return;
    }
    if (d.incal) { const r = await call({ op: 'info_calendar', title: infoBox.title }); if (r.ok) say(`Добавлено в календарь: ${r.title}`); else if (r.error === 'exists') say('Эта серия уже в календаре'); else if (r.error !== 'offline') say(ERR[r.error] || 'Не получилось'); return; }
    if (d.info) { info($('ci-q').value.trim()); return; }
    if (d.linfo) { info(d.linfo); return; }
    if (d.ladd) { libAct({ op: 'lib_add' }, 'Папка добавлена'); return; }
    if (d.lrm) { libAct({ op: 'lib_remove', path: d.lrm }, 'Папка убрана'); return; }
    if (d.lscan) { loadLib(true); return; }
    if (d.lmore) { showAllMovies = !showAllMovies; render(); return; }
    if (d.lnext) { libAct({ op: 'lib_play', key: d.lnext }, 'Включаю в плеере'); return; }
    if (d.lplay) { libAct({ op: 'lib_play', path: d.lplay }, 'Включаю в плеере'); return; }
    if (d.def) { act({ op: 'default', id: d.def }, 'Сервис выбран основным'); return; }
    if (d.rm) { act({ op: 'remove', id: d.rm }, 'Сервис убран'); return; }
    if (d.pre) { const p = C.presets.find((x) => x.id === d.pre); if (p) act({ op: 'add', name: p.name, domain: p.domain }, `Добавлено: ${p.name}`); return; }
    if (d.custom) { custom = true; render(); setTimeout(() => $('ci-nn') && $('ci-nn').focus(), 30); return; }
    if (d.ccancel) { custom = false; render(); return; }
    if (d.cadd) { const r = await act({ op: 'add', name: $('ci-nn').value, domain: $('ci-nd').value, search: $('ci-ns').value }, 'Сервис добавлен'); if (r.ok) { custom = false; render(); } }
  });
  body.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.matches('#ci-q, #ci-se, #ci-ep')) { e.preventDefault(); const g = body.querySelector('[data-go]'); if (g) g.click(); } });
  J.on('nowplaying', paintNow);
  setInterval(() => { if (!document.hidden) paintNow(); }, 500);
  window.renderCinema = () => { custom = false; load(); };
})();
