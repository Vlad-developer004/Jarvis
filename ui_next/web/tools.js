// Settings > Tools: saved videos, quick links (voice phrase to a link), apps that stay open in game mode, how apps are launched, Telegram remote control, updates.
// Data comes from the `tools` bridge command (ui_next/bridge/tools.py); every change is applied and saved at once and the core answers with the fresh state.
// Without a core the tab shows sample data and refuses changes. Relies on globals of app.html: $, J, m, esc, and window.LOOK.ui from look.js.
(() => {
  const root = $('lk-tools'), modal = $('lk-modal'), mbox = $('lk-mbox'), U = window.LOOK.ui;
  const DEMO = { ok: true, max_videos: 10, videos: [{ ts: '2026-10-18 21:40', url: 'https://youtu.be/dQw4w9WgXcQ' }, { ts: '2026-10-17 09:12', url: 'https://www.youtube.com/watch?v=aqz-KE-bpKQ' }], videos_total: 2,
    meetings: [{ name: 'Математика', phrase: 'заходим на пару по математике', url: 'https://zoom.us/j/1234567890' }], keep: ['discord', 'spotify'], launch: { chrome: 'switch', code: 'new' },
    remote: { token_set: false, chat_id: '', enabled: false }, update: { auto: true, version: '0.1.0', available: '', staged: false }, ip_lookup: true, scenarios: [{ name: 'Работа', phrase: 'режим работы', steps: ['открой хром', 'громкость тридцать'] }] };
  const ERR = { required: 'Заполните все поля', bad_url: 'Нужна ссылка, которая начинается с http:// или https://', exists: 'Такая запись уже есть', too_many: 'Записей уже слишком много', bad_steps: 'Нужен хотя бы один шаг, не больше двенадцати', bad_value: 'Значение не подошло',
    write_failed: 'Не удалось сохранить', not_found: 'Записи уже нет', not_ready: 'Обновление ещё не загружено', failed: 'Не получилось', no_handler: 'Jarvis ещё запускается' };
  const UIKEYS = ['jarvisTheme', 'jarvisCustom', 'jarvisAuto', 'uiScale', 'jarvisSfx', 'jarvisSfxVol', 'jarvisHide', 'jarvisFx'];   // appearance choices live in the browser storage: they go into the backup from here
  let scEditing = null, bk = null, T = null, apps = null, picking = null, editRemote = false, allVideos = false, timer = 0, busy = false, vm = {}, vq = '', metaTry = 0, editing = null;
  const say = (t) => U.say(t);
  if (!P.lock) P.lock = 'M6 11h12v9H6zM8 11V8a4 4 0 0 1 8 0v3';

  async function call(body) { if (!m.connected) { say('Без ядра изменить нельзя'); return { ok: false, error: 'offline' }; } return (await J.send('tools', body)) || { ok: false }; }
  async function act(body, okText) {
    const r = await call(body);
    if (r.ok) { if (r.state !== undefined) T = r.state; else if (r.max_videos !== undefined) T = r; if (okText) say(okText); render(); } else if (r.error !== 'offline') say(ERR[r.error] || 'Не получилось сохранить');
    return r;
  }
  async function load() {
    if (!m.connected) { T = DEMO; render(); return; }
    const r = await call({ op: 'state' }); if (r.ok) { T = r; render(); metaTry = 0; fetchMeta(); }
  }
  // titles, authors, thumbnails and lengths of the saved videos: the core fetches them in the background, ask again until nothing is pending
  async function fetchMeta() {
    if (!m.connected || !T || !T.videos.length) return;
    const r = await J.send('tools', { op: 'video_meta', urls: T.videos.map((v) => v.url) }); if (!r || !r.ok) return;
    Object.assign(vm, r.items); const l = $('tl-vlist'); if (l) l.innerHTML = videoRows();
    if (r.pending > 0 && metaTry++ < 10) setTimeout(fetchMeta, 1500);
  }
  const short = (u) => (u.length > 46 ? u.slice(0, 44) + '…' : u);
  const row = (main, sub, btns) => `<div class="tl-row"><div class="tl-t"><b>${main}</b>${sub ? `<small>${sub}</small>` : ''}</div><div class="tl-b">${btns}</div></div>`;
  const btn = (txt, attrs, cls = '') => `<button type="button" class="cm-try ${cls}" ${attrs}>${txt}</button>`;

  const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  const vdate = (ts) => { const r = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)/.exec(ts); return r ? `${+r[3]} ${MON[+r[2] - 1]} ${r[1]}, ${r[4]}` : ts; };
  const thumbOk = (t) => /^data:image\/jpeg;base64,[A-Za-z0-9+\/=]+$/.test(t || '');
  function videoRows() {
    const q = vq.trim().toLowerCase();
    let vs = T.videos;
    if (q) vs = vs.filter((v) => { const x = vm[v.url] || {}; return `${x.title || ''} ${x.author || ''} ${v.url}`.toLowerCase().includes(q); }); else if (!allVideos) vs = vs.slice(0, 5);
    if (!vs.length) return `<div class="vc-note">${q ? 'Ничего не найдено.' : 'Пока ничего не сохранено. Скажите «сохрани видео», когда оно играет.'}</div>`;
    return vs.map((v) => { const x = vm[v.url] || {};
      return `<div class="tl-row tl-v"><span class="tl-th"${thumbOk(x.thumb) ? ` style="background-image:url('${x.thumb}')"` : ''}>${x.duration ? `<em>${esc(x.duration)}</em>` : ''}</span><div class="tl-t"><b>${esc(x.title || short(v.url))}</b><small>${x.author ? esc(x.author) + ' · ' : ''}${esc(vdate(v.ts))}</small></div>`
        + `<div class="tl-b">${btn('Открыть', `data-open="${esc(v.url)}"`)}${btn('Удалить', `data-vdel="${esc(v.ts)}" data-url="${esc(v.url)}"`, 'tl-del')}</div></div>`; }).join('');
  }
  function videosCard() {
    const list = videoRows();
    return U.card('var(--cyan)', 'music', 'Сохранённые видео',
      U.slider('max_videos', 'Сколько видео хранить', 1, 50, 1, T.max_videos, String(T.max_videos), 'Старые записи удаляются сами, когда лимит превышен.')
      + `<div class="tl-sub">Сохранено: ${T.videos_total}</div>${T.videos.length > 5 ? `<input id="tl-vq" class="tl-vq" maxlength="80" placeholder="Поиск по названию или автору" autocomplete="off" aria-label="Поиск по сохранённым видео" value="${esc(vq)}">` : ''}<div class="tl-list" id="tl-vlist">${list}</div>`
      + (T.videos.length > 5 && !vq.trim() ? `<div class="vc-actions">${btn(allVideos ? 'Свернуть' : `Показать все (${T.videos.length})`, 'data-more="1"')}</div>` : ''));
  }
  const clearForm = () => { for (const id of ['tl-ph', 'tl-url', 'tl-nm']) if ($(id)) $(id).value = ''; };
  const SVC = [['zoom.us', 'Zoom'], ['teams.microsoft', 'Teams'], ['meet.google', 'Google Meet'], ['discord', 'Discord'], ['t.me', 'Telegram'], ['telegram', 'Telegram'], ['youtube', 'YouTube'], ['youtu.be', 'YouTube'], ['moodle', 'Moodle']];
  const svc = (u) => { const l = u.toLowerCase(); const s = SVC.find(([k]) => l.includes(k)); return s ? s[1] : ''; };
  function linksCard() {
    const list = T.meetings.length ? T.meetings.map((x) => row(esc(x.phrase), `${svc(x.url) ? `<b class="tl-svc">${svc(x.url)}</b> · ` : ''}${x.name && x.name !== x.phrase ? esc(x.name) + ' · ' : ''}${esc(short(x.url))}`, btn('Открыть', `data-open="${esc(x.url)}"`) + btn('Изменить', `data-medit="${esc(x.phrase)}"`) + btn('Удалить', `data-mdel="${esc(x.phrase)}"`, 'tl-del'))).join('') : '';
    return U.card('var(--green)', 'ext', 'Быстрые ссылки',
      `<small class="vc-note">Пара, совещание, конференция: скажите фразу, и Jarvis откроет ссылку.</small>${list ? `<div class="tl-list">${list}</div>` : ''}`
      + `<div class="tl-form"><label>Фраза<input id="tl-ph" maxlength="60" placeholder="заходим на пару по математике" autocomplete="off"></label><label>Ссылка<input id="tl-url" maxlength="2000" placeholder="https://zoom.us/j/123…" autocomplete="off"></label>`
      + `<label>Название, если нужно<input id="tl-nm" maxlength="60" placeholder="Высшая математика" autocomplete="off"></label><div class="vc-actions">${editing !== null ? btn('Сохранить изменения', 'data-msave="1"', 'primary') + btn('Отмена', 'data-mcancel="1"') : btn('Добавить ссылку', 'data-madd="1"', 'primary')}</div></div>`);
  }
  function scenariosCard() {
    const list = T.scenarios.length ? T.scenarios.map((x) => row(esc(x.name), `«${esc(x.phrase)}» · шагов: ${x.steps.length}`, btn('Изменить', `data-sedit="${esc(x.name)}"`) + btn('Удалить', `data-sdel="${esc(x.name)}"`, 'tl-del'))).join('') : '';
    return U.card('var(--cyan)', 'list', 'Сценарии',
      `<small class="vc-note">Одна фраза запускает несколько команд подряд. Шаги пишите так, как сказали бы голосом: «открой хром», «громкость тридцать». «пауза 3» ждёт три секунды.</small>${list ? `<div class="tl-list">${list}</div>` : ''}`
      + `<div class="tl-form"><label>Название<input id="tl-sn" maxlength="40" placeholder="Работа" autocomplete="off"></label><label>Фраза<input id="tl-sp" maxlength="60" placeholder="режим работы" autocomplete="off"></label>`
      + `<label>Шаги, по одному в строке<textarea id="tl-ss" rows="4" maxlength="1500" placeholder="открой хром&#10;громкость тридцать"></textarea></label><div class="vc-actions">${scEditing !== null ? btn('Сохранить изменения', 'data-ssave="1"', 'primary') + btn('Отмена', 'data-scancel="1"') : btn('Добавить сценарий', 'data-ssave="1"', 'primary')}</div></div>`);
  }
  function chips(items, attr) { return items.length ? `<div class="tl-chips">${items.map((k) => `<span class="tl-chip">${esc(k)}<button type="button" ${attr}="${esc(k)}" aria-label="Убрать ${esc(k)}">×</button></span>`).join('')}</div>` : ''; }
  function keepCard() {
    return U.card('var(--amber)', 'pad', 'Игровой режим: что не закрывать',
      `<small class="vc-note">При включении игрового режима Jarvis закрывает лишние окна. Эти останутся: введите часть заголовка окна или выберите программу.</small>`
      + (T.keep.length ? chips(T.keep, 'data-kdel') : '<div class="vc-note">Список пуст: закроются все окна, кроме системных.</div>')
      + `<div class="vc-add"><input id="tl-keep" maxlength="80" placeholder="например: discord" autocomplete="off">${btn('Добавить', 'data-kadd="1"')}${btn('Из установленных', 'data-pick="keep"')}</div>`);
  }
  function launchCard() {
    const rules = Object.entries(T.launch);
    const list = rules.length ? rules.map(([a, mode]) => row(esc(a), mode === 'new' ? 'всегда новое окно' : 'переключаться на открытое', `<div class="seg2" role="radiogroup" style="--n:2;--i:${mode === 'new' ? 1 : 0}">${[['switch', 'Открытое', 'Переключаться на уже открытое окно'], ['new', 'Новое', 'Всегда открывать новое окно']].map(([v, t, tip]) => `<button type="button" class="${mode === v ? 'on' : ''}" data-lset="${esc(a)}" data-mode="${v}" role="radio" aria-checked="${mode === v}" title="${tip}">${t}</button>`).join('')}</div>`+ btn('Убрать', `data-ldel="${esc(a)}"`, 'tl-del'))).join('') : '<div class="vc-note">Правил нет: Jarvis сам решает, открыть новое окно или переключиться.</div>';
    return U.card('var(--cyan)', 'ext', 'Запуск приложений',
      `<small class="vc-note">Для каждой программы можно выбрать: переключаться на уже открытое окно или всегда открывать новое.</small><div class="tl-list">${list}</div>`
      + `<div class="vc-add"><input id="tl-app" maxlength="60" placeholder="например: chrome" autocomplete="off">${btn('Добавить', 'data-ladd="1"')}${btn('Из установленных', 'data-pick="launch"')}</div>`);
  }
  function remoteCard() {
    const r = T.remote, on = r.token_set && r.enabled;
    const status = on ? `<div class="tl-ok">Бот подключён, Chat ID: ${esc(r.chat_id)}</div>` : r.token_set ? '<div class="tl-warn">Бот сохранён, но удалённое управление выключено.</div>' : '';
    const form = (!on || editRemote) ? `<div class="tl-form"><label>Bot Token<input id="tl-tok" type="password" maxlength="120" placeholder="${r.token_set ? 'Уже сохранён: оставьте пустым, чтобы не менять' : '123456:ABC-DEF…'}" autocomplete="new-password"></label>`
      + `<label>Chat ID<input id="tl-chat" maxlength="30" value="${esc(r.chat_id)}" placeholder="123456789" autocomplete="off"></label><div class="vc-actions">${btn('Сохранить и включить', 'data-rsave="1"', 'primary')}${editRemote ? btn('Отмена', 'data-redit="0"') : ''}</div></div>`
      : `<div class="vc-actions">${btn('Изменить', 'data-redit="1"')}${btn('Выключить', 'data-roff="1"', 'tl-del')}</div>`;
    return U.card('var(--mag, #cc44ff)', 'bell', 'Удалённое управление',
      `<small class="vc-note">Управляйте Jarvis из Telegram. Создайте бота через @BotFather, свой Chat ID узнайте, например, у @userinfobot. Тот же бот работает и для охранной камеры.</small>${status}${form}`);
  }
  function updateCard() {
    const u = T.update; let st = `Установлена актуальная версия ${esc(u.version)}`, cls = '';
    if (u.staged && u.available) { st = `Версия ${esc(u.available)} готова к установке`; cls = 'tl-ok'; } else if (u.available) { st = `Доступна версия ${esc(u.available)}, загружается…`; cls = 'tl-warn'; }
    return U.card('var(--green)', 'home', 'Обновления',
      U.sw('auto_update', 'Устанавливать обновления сами', 'Jarvis периодически проверяет новую версию и ставит её при перезапуске. Работает только в собранной версии (.exe).', u.auto)
      + `<div class="tl-status ${cls}">${st}</div><div class="vc-actions">${btn('Проверить сейчас', 'data-ucheck="1"')}${u.staged ? btn('Установить и перезапустить', 'data-uinst="1"', 'primary') : ''}</div>`);
  }

  function privacyCard() {
    return U.card('var(--cyan)', 'lock', 'Приватность',
      U.sw('ip_lookup', 'Определять место по IP-адресу', 'Нужно для команды «мой IP» и как запасной способ узнать город для погоды, когда геолокация Windows выключена. Если выключить, погода работает только с названным городом.', T.ip_lookup));
  }

  function backupCard() {
    const pv = bk ? `<div class="md-note"><span>Файл от ${esc((bk.created || '').replace('T', ' ').slice(0, 16) || 'неизвестной даты')}: настроек ${bk.settings}${bk.events ? `, событий календаря ${bk.events}` : ''}. Текущие настройки сохранятся рядом, в файле jarvis_settings.before_restore.json. Применить?</span><span class="tl-b">${btn('Применить', 'data-bapply="1"', 'primary')}${btn('Отмена', 'data-bcancel="1"')}</span></div>` : '';
    return U.card('var(--green)', 'doc', 'Резервная копия',
      `<small class="vc-note">Все настройки одним файлом: для переезда на другой компьютер или переустановки. Ключи ИИ, пароли и токены в файл не попадают, их придётся ввести заново. Устройства звука и размеры окна тоже не переносятся.</small>`
      + `<div class="vc-actions">${btn('Сохранить все настройки в файл', 'data-bexport="1"', 'primary')}${btn('Восстановить из файла…', 'data-bpick="1"')}</div>${pv}`);
  }
  function wizardCard() {
    return U.card('var(--cyan)', 'home', 'Мастер первой настройки', `<small class="vc-note">Пять коротких шагов: язык, микрофон, обращение, набор функций и ИИ. Можно пройти снова в любой момент: текущие значения уже выбраны, ничего не сбросится.</small><div class="vc-actions">${btn('Пройти мастер', 'data-wizard="1"', 'primary')}</div>`);
  }
  async function backupCall(body) { if (!m.connected) { say('Без ядра резервную копию не сделать'); return { ok: false, error: 'offline' }; } return (await J.send('backup', body)) || { ok: false }; }
  function render() {
    if (!T) { root.innerHTML = '<div class="vc-note" style="padding:1rem">Загружаю…</div>'; return; }
    const keep = ['tl-ph', 'tl-url', 'tl-nm', 'tl-keep', 'tl-app', 'tl-chat'], vals = {}; for (const id of keep) { const e = $(id); if (e) vals[id] = e.value; }
    root.innerHTML = `<div class="vc-grid"><div class="vc-col">${videosCard()}${linksCard()}${scenariosCard()}${keepCard()}</div><div class="vc-col">${launchCard()}${remoteCard()}${updateCard()}${privacyCard()}${backupCard()}${wizardCard()}</div></div>`;
    for (const id of keep) { const e = $(id); if (e && vals[id] !== undefined && vals[id] !== '') e.value = vals[id]; }
  }

  // ---- installed programs picker (same source as the old window: the Windows uninstall registry) ----
  const PK = { keep: ['Что не закрывать в игровом режиме', 'Выберите программу, окна которой должны остаться открытыми.'], launch: ['Правило запуска', 'Выберите программу, для которой задать, как её открывать.'] };
  let pf = { q: '', all: false, ide: false }, pSel = 0, pRows = [], ext = null;   // ext: a picker opened by another tab (window.toolsPickApp)
  const hue = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
  const appKey = (a) => ((a.exe || a.name).toLowerCase().replace(/\.(exe|lnk)$/, ''));
  const added = (a) => (picking === 'ext' ? ext.isAdded(a) : picking === 'keep' ? T.keep.includes(a.name.toLowerCase()) : Object.prototype.hasOwnProperty.call(T.launch, appKey(a)));
  function openPicker(kind) {
    picking = kind; pf = { q: '', all: false, ide: false }; pSel = 0; modal.hidden = false;
    mbox.innerHTML = `<div class="xs-head tl-ph"><div><h3>${PK[kind][0]}</h3><p>${PK[kind][1]}</p></div><button type="button" class="xs-x" data-pclose="1" aria-label="Закрыть">×</button></div>
      <div class="xs-body tl-pb"><div class="tl-pbar"><span class="tl-pse"><input id="tl-pq" placeholder="Название программы или файла" autocomplete="off" aria-label="Поиск программы"></span>
      <div class="tl-pf" role="group" aria-label="Фильтры"><button type="button" class="on" data-pf="all">Все</button><button type="button" data-pf="ide">Среды разработки</button><button type="button" data-pf="sys" aria-pressed="false">Системные</button></div></div>
      <div class="tl-plist" id="tl-plist" role="listbox"></div></div><div class="tl-pfoot"><span id="tl-pcount"></span><span class="tl-keys"><kbd>↑</kbd><kbd>↓</kbd> выбор <kbd>Enter</kbd> добавить <kbd>Esc</kbd> закрыть</span></div>`;
    paintList(); setTimeout(() => $('tl-pq') && $('tl-pq').focus(), 30);
    if (!apps) call({ op: 'apps' }).then((r) => { if (!r.ok) { closePick(); return; } apps = r.apps; if (picking) paintList(); });
  }
  function paintList() {
    const box = $('tl-plist'); if (!box) return;
    if (!apps) { box.innerHTML = '<div class="tl-pempty"><i class="tl-spin"></i>Ищу установленные программы…</div>'; $('tl-pcount').textContent = ''; pRows = []; return; }
    const q = pf.q.trim().toLowerCase();
    pRows = apps.filter((a) => (pf.all || !a.noise) && (!pf.ide || a.ide) && (!q || a.name.toLowerCase().includes(q) || a.exe.toLowerCase().includes(q)));
    pSel = Math.min(pSel, Math.max(0, pRows.length - 1));
    let html = '', last = '';
    pRows.forEach((a, i) => {
      const grp = q || pf.ide ? '' : a.ide ? 'Среды разработки' : (a.name[0] || '#').toUpperCase();
      if (grp !== last) { last = grp; if (grp) html += `<div class="tl-pg">${esc(grp)}</div>`; }
      const hh = hue(a.name), on = added(a);
      html += `<button type="button" class="tl-pi${i === pSel ? ' sel' : ''}${on ? ' done' : ''}" data-pi="${i}" role="option" aria-selected="${i === pSel}" style="--ah:${hh}"><i class="tl-av">${esc((a.name[0] || '?').toUpperCase())}</i><span class="tl-pn"><b>${esc(a.name)}</b><small>${esc(a.exe || 'без файла запуска')}</small></span>${on ? '<em>уже в списке</em>' : ''}</button>`;
    });
    box.innerHTML = html || '<div class="tl-pempty">Ничего не найдено. Попробуйте часть названия или включите «Системные».</div>';
    $('tl-pcount').textContent = pRows.length ? `Найдено: ${pRows.length}` : '';
    const s = box.querySelector('.sel'); if (s) s.scrollIntoView({ block: 'nearest' });
  }
  window.toolsPickApp = (title, hint, isAdded, onPick) => { ext = { isAdded, onPick }; PK.ext = [title, hint]; openPicker('ext'); };
  const closePick = () => { modal.hidden = true; mbox.innerHTML = ''; picking = null; };
  function choose(i) {
    const a = pRows[i]; if (!a || added(a)) return; const kind = picking; closePick();
    if (kind === 'keep') act({ op: 'keep_add', title: a.name }, `Добавлено: ${a.name}`); else if (kind === 'launch') act({ op: 'launch_set', app: a.exe || a.name, mode: 'switch' }, `Добавлено: ${a.name}`); else if (kind === 'ext') ext.onPick(a);
  }
  mbox.addEventListener('click', (e) => {
    if (e.target.closest('[data-pclose]')) { closePick(); return; }
    const f = e.target.closest('[data-pf]');
    if (f) {
      if (f.dataset.pf === 'sys') { pf.all = !pf.all; f.setAttribute('aria-pressed', pf.all); f.classList.toggle('on', pf.all); } else { pf.ide = f.dataset.pf === 'ide'; for (const b of mbox.querySelectorAll('[data-pf="all"],[data-pf="ide"]')) b.classList.toggle('on', b.dataset.pf === f.dataset.pf); }
      pSel = 0; paintList(); return;
    }
    const b = e.target.closest('[data-pi]'); if (b) choose(+b.dataset.pi);
  });
  mbox.addEventListener('input', (e) => { if (e.target.id === 'tl-pq') { pf.q = e.target.value; pSel = 0; paintList(); } });
  mbox.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); if (pRows.length) { pSel = (pSel + (e.key === 'ArrowDown' ? 1 : -1) + pRows.length) % pRows.length; paintList(); } } else if (e.key === 'Enter' && e.target.id === 'tl-pq') { e.preventDefault(); choose(pSel); }
  });
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) { e.stopPropagation(); closePick(); } }, true);
  modal.addEventListener('mousedown', (e) => { if (e.target === modal) closePick(); });

  root.addEventListener('input', (e) => {
    if (e.target.id === 'tl-vq') { vq = e.target.value; $('tl-vlist').innerHTML = videoRows(); const mo = root.querySelector('[data-more]'); if (mo) mo.parentElement.hidden = !!vq.trim(); return; }
    const r = e.target.closest('.vc-rng'); if (!r) return;
    const v = parseFloat(r.value); r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    const lab = root.querySelector('[data-val="max_videos"]'); if (lab) lab.textContent = String(Math.round(v));
    clearTimeout(timer); timer = setTimeout(() => act({ op: 'max_videos', n: v }), 400);
  });
  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !e.target.matches('input')) return; e.preventDefault();
    const id = e.target.id; const b = id === 'tl-keep' ? '[data-kadd]' : id === 'tl-app' ? '[data-ladd]' : id === 'tl-ph' || id === 'tl-url' || id === 'tl-nm' ? '[data-madd],[data-msave]' : id === 'tl-tok' || id === 'tl-chat' ? '[data-rsave]' : '';
    if (b) root.querySelector(b).click();
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b || busy) return; const d = b.dataset;
    if (b.closest('.tgl') || d.sw) { if (d.sw === 'auto_update') act({ op: 'auto_update', on: !b.classList.contains('on') }); else if (d.sw === 'ip_lookup') act({ op: 'ip_lookup', on: !b.classList.contains('on') }); return; }
    if (d.wizard) { if (window.openWizard) window.openWizard(); return; }
    if (d.bexport) { const ui = {}; for (const k of UIKEYS) { const v = window.LOOK.raw(k); if (v !== null) ui[k] = v; } const r = await backupCall({ op: 'export', ui }); if (r.ok) say(`Сохранено: настроек ${r.settings}, событий календаря ${r.events}`); else if (r.error === 'write_failed') say('Не удалось записать файл'); return; }
    if (d.bpick) { const r = await backupCall({ op: 'preview' }); if (r.ok) { bk = r; render(); } else if (r.error === 'bad_file') say('Это не резервная копия Jarvis или файл повреждён'); return; }
    if (d.bcancel) { bk = null; render(); return; }
    if (d.bapply) { const r = await backupCall({ op: 'apply', token: bk.token }); bk = null; if (!r.ok) { say(r.error === 'expired' ? 'Выберите файл заново' : 'Не удалось применить'); render(); return; } say(`Восстановлено: настроек ${r.settings}${r.events_added ? `, событий календаря ${r.events_added}` : ''}. Часть настроек применится после перезапуска.`); const ks = Object.keys(r.ui || {}); if (ks.length) { for (const k of ks) window.LOOK.setRaw(k, r.ui[k]); setTimeout(() => window.LOOK.reload(), 1200); } else load(); return; }
    if (d.open) { if (m.connected) J.send('open_url', { url: d.open }); else say('Без ядра ссылку не открыть'); return; }
    if (d.more) { allVideos = !allVideos; render(); return; }
    if (d.vdel) { act({ op: 'video_del', ts: d.vdel, url: d.url }, 'Видео убрано из списка'); return; }
    if (d.sdel) { scEditing = null; act({ op: 'scenario_del', name: d.sdel }, 'Сценарий удалён'); return; }
    if (d.sedit) { const x = T.scenarios.find((q) => q.name === d.sedit); if (!x) return; scEditing = x.name; render(); $('tl-sn').value = x.name; $('tl-sp').value = x.phrase; $('tl-ss').value = x.steps.join('\n'); $('tl-sn').focus(); return; }
    if (d.scancel) { scEditing = null; render(); return; }
    if (d.ssave) { const r = await act({ op: 'scenario_save', old: scEditing || '', name: $('tl-sn').value, phrase: $('tl-sp').value, steps: $('tl-ss').value }, scEditing !== null ? 'Сценарий изменён' : 'Сценарий добавлен'); if (r.ok) { scEditing = null; render(); } return; }
    if (d.mdel) { editing = null; act({ op: 'meeting_del', phrase: d.mdel }, 'Ссылка удалена'); return; }
    if (d.medit) { const x = T.meetings.find((q) => q.phrase === d.medit); if (!x) return; editing = x.phrase; render(); $('tl-ph').value = x.phrase; $('tl-url').value = x.url; $('tl-nm').value = x.name && x.name !== x.phrase ? x.name : ''; $('tl-ph').focus(); return; }
    if (d.mcancel) { editing = null; render(); clearForm(); return; }
    if (d.msave) { const r = await act({ op: 'meeting_edit', old: editing, phrase: $('tl-ph').value, url: $('tl-url').value, name: $('tl-nm').value }, 'Ссылка изменена'); if (r.ok) { editing = null; render(); clearForm(); } return; }
    if (d.madd) { const r = await act({ op: 'meeting_add', phrase: $('tl-ph').value, url: $('tl-url').value, name: $('tl-nm').value }, 'Ссылка добавлена'); if (r.ok) for (const id of ['tl-ph', 'tl-url', 'tl-nm']) $(id).value = ''; return; }
    if (d.kadd) { const r = await act({ op: 'keep_add', title: $('tl-keep').value }, 'Добавлено'); if (r.ok) $('tl-keep').value = ''; return; }
    if (d.kdel) { act({ op: 'keep_del', title: d.kdel }); return; }
    if (d.pick) { openPicker(d.pick); return; }
    if (d.ladd) { const r = await act({ op: 'launch_set', app: $('tl-app').value, mode: 'switch' }, 'Добавлено'); if (r.ok) $('tl-app').value = ''; return; }
    if (d.lset) { const sg = b.closest('.seg2'); sg.style.setProperty('--i', d.mode === 'new' ? 1 : 0); for (const x of sg.children) { x.classList.toggle('on', x === b); x.setAttribute('aria-checked', x === b); } const sub = b.closest('.tl-row').querySelector('small'); if (sub) sub.textContent = d.mode === 'new' ? 'всегда новое окно' : 'переключаться на открытое'; const r = await call({ op: 'launch_set', app: d.lset, mode: d.mode }); if (r.ok) T = r; else { say(ERR[r.error] || 'Не получилось сохранить'); render(); } return; }
    if (d.ldel) { act({ op: 'launch_del', app: d.ldel }); return; }
    if (d.redit) { editRemote = d.redit === '1'; render(); return; }
    if (d.rsave) { const r = await act({ op: 'remote_save', token: $('tl-tok').value, chat_id: $('tl-chat').value }, 'Сохранено, удалённое управление включено'); if (r.ok) editRemote = false, render(); return; }
    if (d.roff) { act({ op: 'remote_off' }, 'Удалённое управление выключено'); return; }
    if (d.ucheck) { const r = await call({ op: 'update_check' }); if (r.ok) { say('Проверяю обновления…'); setTimeout(load, 4000); } return; }
    if (d.uinst) { busy = true; const r = await call({ op: 'update_install' }); busy = false; if (r.ok) say('Устанавливаю обновление, Jarvis перезапустится'); else say(ERR[r.error] || 'Не получилось установить'); }
  });

  window.renderTools = () => { allVideos = false; editRemote = false; editing = null; vq = ''; load(); };
})();
