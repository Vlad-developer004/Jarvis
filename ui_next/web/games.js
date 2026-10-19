// Games screen: game mode, voice-command profiles, and the installed library with a launch button.
// Data: topics `game` ({on, profile}), `library` ({games:[{id, name, launcher, last}], scanning}) and the `catalog` games list;
// commands `game_launch` and `library`. Without a core it shows a local demo. Relies on globals of app.html: $, J, m, ic, C, esc, VIEW, showView.
(() => {
  const DEMO_LIB = [
    { id: 'd1', name: 'Euro Truck Simulator 2', launcher: 'Steam', last: Date.now() / 1000 - 3600 * 5 }, { id: 'd2', name: 'Hogwarts Legacy', launcher: 'Epic Games', last: Date.now() / 1000 - 86400 * 9 },
    { id: 'd3', name: 'Planetbase', launcher: 'Steam', last: Date.now() / 1000 - 86400 * 40 }, { id: 'd4', name: 'Forza Horizon 5', launcher: 'Xbox', last: 0 }, { id: 'd5', name: 'Counter-Strike 2', launcher: 'Steam', last: Date.now() / 1000 - 86400 * 2 },
  ];
  const DEMO_PROF = [{ key: 'game:euro_truck_simulator_2', title: 'Euro Truck Simulator 2', count: 85, installed: true }, { key: 'game:hogwarts_legacy', title: 'Hogwarts Legacy', count: 40, installed: true }, { key: 'game:planetbase', title: 'Planetbase', count: 30, installed: false }];
  const LIB_SHOWN = 60;
  let q = '', all = false, scanning = false, toastTimer = 0, demoGame = false;
  const body = $('gm-body'), toast = $('gm-toast'), search = $('gm-q');
  const lib = () => (m.connected ? (m.library && m.library.games) || null : DEMO_LIB);
  const profiles = () => (m.catalog && m.catalog.games) || (m.connected ? [] : DEMO_PROF);
  const isOn = () => (m.connected ? !!m.game : demoGame);
  const pl = (n, f) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]}`;

  function ago(ts) {
    if (!ts) return 'ещё не запускалась';
    const d = Math.floor((Date.now() / 1000 - ts) / 86400);
    if (d < 1) return 'играли сегодня'; if (d === 1) return 'играли вчера'; if (d < 31) return `играли ${pl(d, ['день', 'дня', 'дней'])} назад`;
    const mo = Math.floor(d / 30); return mo < 12 ? `играли ${pl(mo, ['месяц', 'месяца', 'месяцев'])} назад` : 'играли больше года назад';
  }
  const hue = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };
  const ini = (n) => { const w = n.replace(/[^\p{L}\p{N} ]/gu, '').trim().split(/\s+/); return ((w[0] || '?')[0] + (w[1] ? w[1][0] : '')).toUpperCase(); };
  function say(t) { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); }

  function paintMode() {
    const on = isOn(), prof = m.connected ? m.gameProfile : (demoGame ? 'Euro Truck Simulator 2' : '');
    $('gm-st').className = on ? 'on' : ''; $('gm-st').textContent = on ? 'Включён' : 'Выключен';
    $('gm-sw').classList.toggle('on', on); $('gm-sw').setAttribute('aria-pressed', on);
    $('gm-prof').innerHTML = on ? (prof ? `Профиль игры: <b>${esc(prof)}</b>` : 'Профиль игры не выбран') : '';
  }

  function paintProfiles() {
    const ps = profiles();
    $('gm-pl').innerHTML = ps.length ? ps.map((p) => `<div class="gm-pr${p.installed === false ? ' off' : ''}"><div><b>${esc(p.title)}</b><small>${pl(p.count, ['команда', 'команды', 'команд'])}${p.installed === false ? ' · расширение не установлено' : ''}</small></div><span class="gm-pb"><button class="cm-try" data-cmds="${esc(p.key)}">Команды</button>${p.installed === false ? '' : `<button class="cm-try" data-keys="${esc(p.title)}" title="Клавиши, макросы и заклинания этой игры">Клавиши</button>`}</span></div>`).join('')
      : '<div class="rm-empty"><b>Профилей пока нет</b>Профили игр ставятся как расширения.</div>';
  }

  function paintLib() {
    const g = lib(), list = $('gm-lib');
    $('gm-count').textContent = g ? pl(g.length, ['игра', 'игры', 'игр']) : ''; if (g && !m.connected) $('gm-count').textContent += ' · пример, ядро не подключено';
    $('gm-scan').disabled = scanning; $('gm-scan').textContent = scanning ? 'Ищу…' : 'Обновить';
    if (!g) { list.innerHTML = '<div class="rm-empty"><b>Ищу установленные игры…</b>Steam, Epic Games и Xbox. Это занимает несколько секунд.</div>'; return; }
    const ql = q.trim().toLowerCase(), rows = ql ? g.filter((x) => x.name.toLowerCase().includes(ql)) : g;
    if (!rows.length) { list.innerHTML = `<div class="rm-empty"><b>${ql ? 'Ничего не найдено' : 'Игры не найдены'}</b>${ql ? 'Попробуйте другое название.' : 'Jarvis ищет в Steam, Epic Games и Xbox. Если игра установлена в другом месте, запустите её сами: профиль подключится по окну игры.'}</div>`; return; }
    const shown = all || ql ? rows : rows.slice(0, LIB_SHOWN);
    list.innerHTML = shown.map((x) => `<div class="gm-g"><span class="gm-ini${/^data:image\/png;base64,[A-Za-z0-9+\/=]+$/.test(x.icon || '') ? ' has' : ''}" style="--gh:${hue(x.name)}">${/^data:image\/png;base64,[A-Za-z0-9+\/=]+$/.test(x.icon || '') ? `<img alt="" src="${x.icon}">` : esc(ini(x.name))}</span><div><b title="${esc(x.name)}">${esc(x.name)}</b><small>${esc(x.launcher)} · ${ago(x.last)}</small></div><button class="cm-try" data-launch="${esc(x.id)}">Запустить</button></div>`).join('')
      + (shown.length < rows.length ? `<button class="rm-chip gm-more" id="gm-all">Показать все (${rows.length})</button>` : '');
  }

  function render() { paintMode(); paintProfiles(); paintLib(); }

  $('gm-sw').onclick = () => { if (m.connected) $('gmode').click(); else { demoGame = !demoGame; paintMode(); } };
  search.addEventListener('input', () => { q = search.value; paintLib(); });
  $('gm-scan').onclick = async () => {
    if (!m.connected) { say('Список обновлён'); return; }
    scanning = true; paintLib(); const r = await J.send('library', {});
    if (!r) { scanning = false; paintLib(); say('Jarvis не ответил — проверьте, что он запущен'); }
  };
  $('gm-pl').addEventListener('click', (e) => { const k = e.target.closest('[data-keys]'); if (k) { window.openProfileEditor(k.dataset.keys); return; } const b = e.target.closest('[data-cmds]'); if (b) { showView('commands'); window.cmdsCategory(b.dataset.cmds); } });
  $('gm-lib').addEventListener('click', async (e) => {
    if (e.target.id === 'gm-all') { all = true; paintLib(); return; }
    const b = e.target.closest('[data-launch]'); if (!b) return;
    const name = (lib() || []).find((x) => x.id === b.dataset.launch)?.name || 'игру';
    if (!m.connected) { say(`Демо: «${name}» запустилась бы здесь`); return; }
    b.disabled = true; setTimeout(() => { b.disabled = false; }, 4000);
    const r = await J.send('game_launch', { id: b.dataset.launch });
    say(r && r.ok ? `Запускаю «${r.name}». Игровой режим включится сам` : r ? 'Не получилось запустить: обновите список' : 'Jarvis не ответил — проверьте, что он запущен');
  });

  J.on('game', () => { if (VIEW === 'games') paintMode(); });
  J.on('library', () => { scanning = false; if (VIEW === 'games') paintLib(); });
  J.on('catalog', () => { if (VIEW === 'games') paintProfiles(); });
  J.on('live', () => { if (VIEW === 'games') render(); });
  document.querySelectorAll('#games [data-ic]').forEach((e) => { e.outerHTML = ic(e.dataset.ic, C.amber, 18); });
  window.renderGames = render;
})();
