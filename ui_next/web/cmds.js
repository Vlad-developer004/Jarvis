// Commands screen: searchable catalog of everything Jarvis understands, with "try it" buttons.
// Data: the `catalog` topic from the core (ui_next/bridge/catalog.py); a short demo list when no core is connected.
// Relies on globals of app.html: $, J, m, ic, P, C, esc, setNotice, showView.
(() => {
  Object.assign(P, { vol: 'M4 9h4l5-4v14l-5-4H4zM16 9l3 3-3 3', doc: 'M6 3h9l4 4v14H6zM15 3v4h4', pc: 'M3 4h18v12H3zM8 20h8M12 16v4', grid: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z' });
  const CAT_ICON = { all: 'grid', assistant: 'mic', timers: 'timer', media: 'music', sound: 'vol', apps: 'ext', files: 'doc', pc: 'pc', games: 'pad', ui: 'theme' };
  const CAT_COL = { assistant: C.cyan, timers: C.amber, media: C.mag, sound: C.green, apps: C.purple, files: C.yel, pc: C.cyan, games: C.green, ui: C.purple };
  const GAME_COL = C.green;
  const SUGGEST = ['громкость', 'таймер', 'открой', 'выключи', 'скриншот', 'погода'];
  const DEMO = {
    categories: [{ key: 'assistant', title: 'Помощник', hint: 'Время, погода, вопросы' }, { key: 'timers', title: 'Таймеры и заметки', hint: 'Напоминания, диктовка' }, { key: 'sound', title: 'Звук и экран', hint: 'Громкость, яркость' }, { key: 'pc', title: 'Компьютер', hint: 'Питание, сеть' }],
    games: [{ key: 'game:ets2', title: 'Euro Truck Simulator 2', count: 1, installed: true }], ext: {},
    starters: ['timer_set', 'weather', 'vol_set'],
    items: [
      { id: 'weather', name: 'Погода', desc: 'Запрос актуального прогноза погоды для вашего региона.', cat: 'assistant', phrases: ['какая погода', 'температура на улице'], mode: 'run', try: 'какая погода' },
      { id: 'time_now', name: 'Время', desc: 'Голосовое оповещение о текущем времени.', cat: 'assistant', phrases: ['время', 'который час'], mode: 'run', try: 'время' },
      { id: 'timer_set', name: 'Таймер: Установить', desc: 'Запуск таймера обратного отсчёта с предупреждениями.', cat: 'timers', phrases: ['поставь таймер на [число] минут', 'таймер на час'], mode: 'run', try: 'поставь таймер на 10 минут' },
      { id: 'reminder', name: 'Напоминание', desc: 'Установка голосового напоминания через заданный интервал.', cat: 'timers', phrases: ['напомни через [время]'], mode: 'voice', try: null },
      { id: 'vol_set', name: 'Громкость: Уровень', desc: 'Установка громкости на точное значение (0-100%).', cat: 'sound', phrases: ['громкость на [число]'], mode: 'run', try: 'громкость на 50' },
      { id: 'shutdown', name: 'Выключить компьютер', desc: 'Безопасное завершение работы ПК.', cat: 'pc', phrases: ['выключи компьютер', 'выключи пк'], mode: 'confirm', try: 'выключи компьютер' },
      { id: 'game:ets2:0', name: 'Запуск двигателя', desc: '', cat: 'game:ets2', phrases: ['заведи двигатель', 'запусти мотор'], more: 3, mode: 'game', try: null },
    ],
  };
  const view = { cat: 'all', q: '', onlyRun: false, abc: false };
  // exchange-rate command settings, kept by the core (`currency` command): home currency, and the currencies the user follows ("мои курсы")
  const cur = { base: 'UAH', list: null, watch: [], rates: {} };
  const DEMO_CUR = [{ code: 'UAH', name: 'Украинская гривна' }, { code: 'USD', name: 'Доллар США' }, { code: 'EUR', name: 'Евро' }, { code: 'TRY', name: 'Турецкая лира' }, { code: 'CNY', name: 'Китайский юань' }, { code: 'BTC', name: 'Биткоин' }];
  const fmtRate = (v) => (v == null ? '…' : v >= 100 ? v.toFixed(0) : v >= 1 ? v.toFixed(2) : v.toPrecision(2));
  async function loadRates() {
    if (!m.connected) { cur.rates = { USD: 41.5, EUR: 45.1, TRY: 1.2, CNY: 5.8, BTC: 3600000 }; return; }
    const r = await J.send('currency', { op: 'rates' });
    if (r && r.ok) { cur.rates = Object.fromEntries(r.rates.map((x) => [x.code, x.rate])); render(); }
  }
  async function loadCur() {
    if (!m.connected) { cur.list = DEMO_CUR; cur.watch = cur.watch.length ? cur.watch : ['USD', 'EUR']; loadRates(); return; }
    const r = await J.send('currency', { op: 'get' });
    if (r && r.ok) { cur.base = r.base; cur.list = r.list; cur.watch = r.watch; render(); loadRates(); }
  }
  const curName = (code) => (cur.list.find((c) => c.code === code) || {}).name || code;
  function curCfg() {
    const homes = cur.list.filter((c) => c.code !== 'BTC'), free = cur.list.filter((c) => !cur.watch.includes(c.code) && c.code !== cur.base);
    const chips = cur.watch.length ? cur.watch.map((c) => `<span class="cw-chip" title="${esc(curName(c))}"><b>${esc(c)}</b><i>${c === cur.base ? '—' : fmtRate(cur.rates[c])}</i><button type="button" data-cw-rm="${esc(c)}" aria-label="Не следить: ${esc(curName(c))}">×</button></span>`).join('') : '<span class="cw-none">Пока пусто</span>';
    return `<div class="cm-cfg"><span>Моя валюта</span><select id="cm-cur" aria-label="Моя валюта">${homes.map((c) => `<option value="${esc(c.code)}"${c.code === cur.base ? ' selected' : ''}>${esc(c.name)}</option>`).join('')}</select><small>«курс юаня» назовёт цену в ней</small></div>`
      + `<div class="cm-cfg cm-watch"><span>Слежу за курсами</span><div class="cw-chips">${chips}</div>${cur.watch.length < 12 ? `<select id="cm-add" aria-label="Добавить валюту"><option value="">+ Добавить валюту</option>${free.map((c) => `<option value="${esc(c.code)}">${esc(c.name)} · ${esc(c.code)}</option>`).join('')}</select>` : ''}<small>Скажите «мои курсы», и Jarvis назовёт их все</small></div>`;
  }

  const body = $('cm-body'), input = $('cm-q'), rail = $('cm-rail'), sug = $('cm-sug'), note = $('cm-note'), toast = $('cm-toast'), onlySw = $('cm-only'), abcSw = $('cm-abc');
  const data = () => m.catalog || (m.connected ? null : DEMO);
  const pl = (n, f) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]}`;
  const isGame = (it) => it.mode === 'game';

  // ---- search: lowercase tokens, crude Russian stemming so "таймера" finds "таймер" ----
  const norm = (s) => String(s || '').toLowerCase().replace(/ё/g, 'е');
  const stem = (w) => (w.length >= 6 ? w.slice(0, -2) : w.length === 5 ? w.slice(0, -1) : w);
  const tokens = (s) => norm(s).split(/[^a-zа-я0-9]+/).filter((t) => t.length >= 2).map(stem);
  function score(it, toks) {
    const name = norm(it.name), desc = norm(it.desc), ph = it.phrases.map(norm);
    let total = 0;
    for (const t of toks) {
      let s = 0;
      if (ph.some((p) => p.startsWith(t))) s = 6; else if (ph.some((p) => p.includes(t))) s = 4;
      if (name.includes(t)) s = Math.max(s, 5); else if (desc.includes(t)) s = Math.max(s, 1);
      if (!s) return 0; total += s;
    }
    return total;
  }
  function hl(text) {
    const t = esc(text); if (!view.q) return t;
    const toks = tokens(view.q).filter(Boolean); if (!toks.length) return t;
    return t.replace(new RegExp('(' + toks.map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi'), '<mark>$1</mark>');
  }

  // ---- model helpers ----
  const catTitle = (d, key) => { const c = d.categories.find((x) => x.key === key); if (c) return c.title; const g = (d.games || []).find((x) => x.key === key); return g ? g.title : key; };
  const gameInfo = (d, key) => (d.games || []).find((g) => g.key === key);
  const extOff = (d, it) => it.needs && d.ext && d.ext[it.needs] && !d.ext[it.needs].installed ? d.ext[it.needs].name : null;
  const byName = (a, b) => a.name.localeCompare(b.name, 'ru');
  const visible = (d, it) => !view.onlyRun || (it.mode === 'run' || it.mode === 'confirm');

  // ---- rendering ----
  function card(d, it, tag) {
    const game = isGame(it), col = game ? GAME_COL : (CAT_COL[it.cat] || C.cyan), off = extOff(d, it), g = game ? gameInfo(d, it.cat) : null, can = m.connected && !off && (it.mode === 'run' || it.mode === 'confirm');
    let act;
    if (game) act = '';   // the one-line explanation sits in the section header, not on every card
    else if (off) act = `<span class="cm-voice warn">${ic('warn', C.amber, 14)}Нужно расширение «${esc(off)}»</span>`;
    else if (it.mode === 'voice') act = `<span class="cm-voice">${ic('mic', 'var(--ic)', 14)}Только голосом</span><span class="cm-hint" title="Команда принимает слово или число, либо действует на активное окно, поэтому из этого окна её не запустить.">нужен аргумент или окно</span>`;
    else act = `<button class="cm-try${it.mode === 'confirm' ? ' danger' : ''}" data-act="${it.mode === 'confirm' ? 'ask' : 'run'}" data-id="${esc(it.id)}"${can ? '' : ' disabled'} title="${can ? `Jarvis выполнит: «${window.I18N.keep(esc(it.try))}»` : 'Запустите Jarvis, чтобы пробовать команды'}">${it.mode === 'confirm' ? 'Выполнить…' : 'Попробовать'}</button><span class="cm-hint" title="Фраза, которую выполнит кнопка">«${esc(it.try)}»</span>`;
    const more = it.more ? `<span class="cm-more">ещё ${it.more}</span>` : '';
    const cfg = it.id === 'currency_rate' && cur.list ? curCfg() : '';
    return `<div class="cm-card${off ? ' off' : ''}" style="--cc:${col}" data-card="${esc(it.id)}"><div class="cm-top"><span class="ico" style="--c:${col}">${ic(game ? 'pad' : (CAT_ICON[it.cat] || 'list'), col, 19)}</span><div><div class="cm-name" translate="no">${hl(it.name)}</div>${it.desc ? `<div class="cm-desc" translate="no">${hl(it.desc)}</div>` : ''}</div>${tag ? `<span class="cm-tag">${esc(tag)}</span>` : ''}</div>`
      + `<div class="cm-say" translate="no">${it.phrases.map((p) => `<button class="cm-ph" data-act="copy" data-t="${esc(p)}" title="Нажмите, чтобы скопировать фразу">«${hl(p)}»</button>`).join('')}${more}</div>${cfg}${act ? `<div class="cm-act">${act}</div>` : ''}</div>`;
  }
  const section = (d, title, hint, items, tagged) => `<section class="cm-sec"><h3>${esc(title)}${hint ? `<small>${esc(hint)}</small>` : ''}</h3><div class="cm-grid">${items.map((it) => card(d, it, tagged ? catTitle(d, it.cat) : '')).join('')}</div></section>`;
  const railBtn = (key, title, count, icon, col, extra = '') => `<button class="cm-cat${view.cat === key ? ' on' : ''}${count === 0 ? ' zero' : ''}" data-cat="${esc(key)}" style="--cc:${col}"><span class="ci">${ic(icon, 'currentColor', 17)}</span><span class="cn">${esc(title)}${extra}</span><b>${count}</b></button>`;

  function render() {
    const d = data();
    note.style.display = m.connected ? 'none' : 'block';
    note.textContent = 'Jarvis не запущен: показан короткий пример списка, кнопки запуска неактивны. Полный список появится при подключении.';
    if (!d) { body.innerHTML = '<div class="cm-empty"><b>Загружаю список команд…</b>Это занимает пару секунд после запуска.</div>'; rail.innerHTML = ''; return; }
    const general = d.items.filter((i) => !isGame(i)), gameItems = d.items.filter(isGame), q = view.q.trim();
    $('cm-count').innerHTML = `${pl(general.length, ['общая команда', 'общие команды', 'общих команд'])}${gameItems.length ? ` · ${pl(gameItems.length, ['команда', 'команды', 'команд'])} в играх` : ''}`;
    const toks = tokens(q), scored = q ? d.items.filter((i) => visible(d, i)).map((i) => [score(i, toks), i]).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]).map((x) => x[1]) : null;
    const countOf = (key) => (scored ? scored.filter((i) => i.cat === key).length : d.items.filter((i) => i.cat === key && visible(d, i)).length);
    const total = scored ? scored.length : general.filter((i) => visible(d, i)).length;
    rail.innerHTML = railBtn('all', 'Все команды', total, 'grid', C.cyan)
      + '<div class="cm-rh">Общие</div>' + d.categories.map((c) => railBtn(c.key, c.title, countOf(c.key), CAT_ICON[c.key] || 'list', CAT_COL[c.key] || C.cyan)).join('')
      + ((d.games || []).length ? '<div class="cm-rh">В играх</div>' + d.games.map((g) => railBtn(g.key, g.title, countOf(g.key), 'pad', GAME_COL, g.installed === false ? '<small>не установлена</small>' : '')).join('') : '');
    sug.innerHTML = q ? `<span>${scored.length ? `Найдено: ${pl(scored.length, ['команда', 'команды', 'команд'])}` : 'Ничего не найдено'}</span><button data-q="">Сбросить поиск</button>` : `<span>Попробуйте найти:</span>${SUGGEST.map((s) => `<button data-q="${s}">${s}</button>`).join('')}`;
    onlySw.classList.toggle('on', view.onlyRun); onlySw.setAttribute('aria-pressed', view.onlyRun); abcSw.classList.toggle('on', view.abc); abcSw.setAttribute('aria-pressed', view.abc);
    if (scored) {
      const list = view.cat === 'all' ? scored : scored.filter((i) => i.cat === view.cat);
      body.innerHTML = list.length ? section(d, view.cat === 'all' ? 'Результаты поиска' : catTitle(d, view.cat), '', list, view.cat === 'all') : `<div class="cm-empty"><b>Ничего не нашлось по «${esc(q)}»</b>Попробуйте одно слово: «громкость», «таймер», «открой». Или выберите другую категорию слева${view.cat !== 'all' ? ' (сейчас выбрана одна)' : ''}.</div>`;
    } else if (view.cat === 'all' && view.abc) {
      const list = general.filter((i) => visible(d, i)).sort(byName);
      body.innerHTML = list.length ? section(d, 'Все команды по алфавиту', `${list.length}`, list, true) : '<div class="cm-empty"><b>Нечего показать</b>Выключите «Только с кнопкой запуска».</div>';
    } else if (view.cat === 'all') {
      const st = (d.starters || []).map((id) => d.items.find((i) => i.id === id)).filter((i) => i && visible(d, i));
      body.innerHTML = (st.length ? section(d, 'Для начала', 'Скажите «Джарвис», а затем любую из этих фраз', st) : '') + d.categories.map((c) => { const it = general.filter((i) => i.cat === c.key && visible(d, i)); return it.length ? section(d, c.title, c.hint, it) : ''; }).join('')
        + (gameItems.length ? `<div class="cm-more-games">В играх есть ещё ${pl(gameItems.length, ['команда', 'команды', 'команд'])}: выберите игру слева.</div>` : '');
    } else {
      const it = d.items.filter((i) => i.cat === view.cat && visible(d, i)).sort(view.abc ? byName : () => 0), c = d.categories.find((x) => x.key === view.cat), g = gameInfo(d, view.cat);
      body.innerHTML = it.length ? (g && g.installed === false ? '<div class="cm-note inline">Профиль этой игры не установлен: команды не сработают. Установить можно в Настройки → Расширения.</div>' : '') + section(d, c ? c.title : g ? g.title : view.cat, c ? c.hint : 'Работает в игровом режиме, когда игра запущена', it) : '<div class="cm-empty"><b>В этой категории пусто</b>Выключите переключатель «Только с кнопкой запуска».</div>';
    }
    body.scrollTop = 0;
  }

  // ---- actions ----
  let toastTimer = 0;
  function say(text, withLink) { toast.innerHTML = `<span>${esc(text)}</span>${withLink ? '<button data-go="dash">К обзору</button>' : ''}`; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 4000); }
  async function run(id, confirm, btn) {
    const label = btn && btn.classList.contains('danger') ? 'Выполнить…' : 'Попробовать';
    if (btn) { btn.classList.add('busy'); btn.textContent = 'Выполняю…'; }
    const r = await J.send('run', { id, confirm: !!confirm });
    if (btn) btn.classList.remove('busy');
    if (r && r.ok) { if (btn) { btn.classList.add('done'); btn.textContent = 'Готово'; setTimeout(() => { btn.classList.remove('done'); btn.textContent = label; }, 2200); } say(`Выполняю: «${r.phrase}»`, true); }
    else { if (btn) btn.textContent = label; say(!r ? 'Нет связи с Jarvis' : r.error === 'confirm_required' ? 'Нужно подтверждение' : 'Не удалось запустить команду'); }
  }
  const byId = (id) => data().items.find((x) => x.id === id);
  body.addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]'); if (!b) return;
    const act = b.dataset.act, cardEl = b.closest('.cm-card'), d = data();
    if (act === 'copy') { const t = b.dataset.t; (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(() => { b.classList.add('ok'); setTimeout(() => b.classList.remove('ok'), 900); say(`Скопировано: «${t}»`); }).catch(() => say('Не удалось скопировать')); }
    else if (act === 'run') run(b.dataset.id, false, b);
    else if (act === 'ask') { const it = byId(b.dataset.id); cardEl.querySelector('.cm-act').innerHTML = `<div class="cm-confirm">Точно выполнить «${esc(it.try)}»?<button class="cm-try danger" data-act="yes" data-id="${esc(it.id)}">Да</button><button class="cm-try" data-act="no">Нет</button></div>`; }
    else if (act === 'yes') { const it = byId(b.dataset.id); cardEl.outerHTML = card(d, it); run(it.id, true, body.querySelector(`[data-card="${CSS.escape(it.id)}"] .cm-try`)); }
    else if (act === 'no') cardEl.outerHTML = card(d, byId(cardEl.dataset.card));
  });
  async function saveWatch(codes, text) {
    cur.watch = codes;
    if (m.connected) { const r = await J.send('currency', { op: 'watch', codes }); if (r && r.ok) cur.watch = r.watch; else { say('Не удалось сохранить список'); return; } }
    say(text); render(); loadRates();
  }
  body.addEventListener('change', async (e) => {
    if (e.target.id === 'cm-add') { const code = e.target.value; if (code && !cur.watch.includes(code)) saveWatch([...cur.watch, code], `Слежу за валютой «${curName(code)}»`); return; }
    if (e.target.id !== 'cm-cur') return;
    const code = e.target.value, name = curName(code);
    if (!m.connected) { cur.base = code; say(`Демо: курсы будут считаться в валюте «${name}»`); render(); return; }
    const r = await J.send('currency', { op: 'set', base: code });
    if (r && r.ok) { cur.base = r.base; say(`Курсы теперь считаются в валюте «${name}»`); render(); loadRates(); } else say('Не удалось сохранить валюту');
  });
  body.addEventListener('click', (e) => { const b = e.target.closest('[data-cw-rm]'); if (b) saveWatch(cur.watch.filter((c) => c !== b.dataset.cwRm), `Больше не слежу за «${curName(b.dataset.cwRm)}»`); });
  if (window.fzDropdown) window.fzDropdown.watch(body);
  loadCur();
  rail.addEventListener('click', (e) => { const b = e.target.closest('.cm-cat'); if (!b) return; view.cat = b.dataset.cat; render(); });
  sug.addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; input.value = b.dataset.q; view.q = b.dataset.q; sync(); render(); if (b.dataset.q) input.focus(); });
  toast.addEventListener('click', (e) => { if (e.target.dataset.go) showView('dash'); });
  onlySw.onclick = () => { view.onlyRun = !view.onlyRun; render(); };
  abcSw.onclick = () => { view.abc = !view.abc; render(); };
  const sync = () => input.parentElement.classList.toggle('has', !!input.value);
  input.addEventListener('input', () => { view.q = input.value; sync(); render(); });
  $('cm-clear').onclick = () => { input.value = ''; view.q = ''; sync(); render(); input.focus(); };
  document.addEventListener('keydown', (e) => {
    if ($('app').dataset.view !== 'commands') return;
    if (e.key === '/' && document.activeElement !== input) { e.preventDefault(); input.focus(); input.select(); }
    else if (e.key === 'Escape' && (input.value || document.activeElement === input)) { input.value = ''; view.q = ''; sync(); render(); input.blur(); }
  });
  J.on('catalog', render); J.on('conn', () => { loadCur(); render(); }); J.on('live', render);
  window.renderCommands = render; window.cmdsCategory = (key) => { view.cat = key; render(); }; render();
})();
