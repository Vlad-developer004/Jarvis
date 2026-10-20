// Extensions screen: what is installed, install/uninstall of the simple ones, and a way into the old dialog for setup.
// Data: topic `extensions` ([{id, name, desc, category, installed, commands, simple}]); commands `extension` and `dialog`.
// Relies on globals of app.html: $, J, m, ic, C, esc, VIEW.
(() => {
  const DEMO = [
    { id: 'game_ets2', name: 'Euro Truck Simulator 2', desc: 'Голосовое управление грузовиком: двигатель, свет, круиз, прицеп.', category: 'Игровые профили', installed: true, commands: 0, simple: false, setup: 'ets2' },
    { id: 'game_hogwarts', name: 'Hogwarts Legacy', desc: 'Голосовое управление заклинаниями и действиями в игре.', category: 'Игровые профили', installed: false, commands: 0, simple: true },
    { id: 'feature_mail_client', name: 'Почта', desc: 'Входящие, чтение и ответы на письма голосом.', category: 'Интеграции', installed: false, commands: 11, simple: false, setup: 'mail' },
    { id: 'feature_system_health', name: 'Система: диски', desc: 'Состояние дисков и свободное место.', category: 'Система', installed: true, commands: 5, simple: true },
  ];
  const SV = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const EI = {
    pad: '<path d="M7 8h10a4 4 0 0 1 4 4v2.5a2.5 2.5 0 0 1-4.3 1.7L15 14.5H9l-1.7 1.7A2.5 2.5 0 0 1 3 14.5V12a4 4 0 0 1 4-4zM8 10.5v3M6.5 12h3M16 11h.01M18 13h.01"/>',
    mail: '<path d="M4 6h16v12H4zM4 7l8 6 8-6"/>', shield: '<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6zM9 12l2.2 2.2L15.5 10"/>', cam: '<path d="M3 8h4l1.5-2.5h7L17 8h4v11H3zM12 11a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3M10 10h4v4h-4z"/>', note: '<path d="M9 18V6l10-2v12M9 18a3 3 0 1 1-3-3 3 3 0 0 1 3 3zM19 16a3 3 0 1 1-3-3 3 3 0 0 1 3 3z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>', cal: '<path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4"/>', puzzle: '<path d="M10 4a2 2 0 1 1 4 0v2h4v4h-2a2 2 0 1 0 0 4h2v4h-4v-2a2 2 0 1 0-4 0v2H6v-4h2a2 2 0 1 0 0-4H6V6h4z"/>',
    dl: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>', trash: '<path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6"/>', gear: '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M18.7 5.3l-2.1 2.1M7.4 16.6l-2.1 2.1"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/>', cmd: '<path d="M5 7l5 5-5 5M12 18h7"/>',
  };
  const iconOf = (e) => { const k = `${e.id} ${e.name} ${e.category}`.toLowerCase();
    return /game_|игров|simulator|legacy|planetbase/.test(k) ? 'pad' : /mail|почт/.test(k) ? 'mail' : /камер|cam|охран|guard|безопас/.test(k) ? 'shield' : /disk|диск|health|систем|cpu/.test(k) ? 'cpu' : /music|song|музык|spotify|плеер/.test(k) ? 'note' : /weather|погод|nasa/.test(k) ? 'sun' : /calendar|календар|напомин/.test(k) ? 'cal' : 'puzzle'; };
  const TINTS = ['var(--cyan)', '#a98bff', 'var(--amber)', '#ff7fd6', '#4da3ff', '#3df5ac'];
  const tintOf = (cat) => { let h = 0; for (const c of cat || '') h = (h * 31 + c.charCodeAt(0)) % TINTS.length; return TINTS[h]; };
  let flt = 'all', query = '';
  let confirmId = '', toastTimer = 0, demo = DEMO.map((e) => ({ ...e }));
  const body = $('ex-body'), toast = $('ex-toast');
  const list = () => (m.connected ? m.extensions : demo);
  function say(t) { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); }
  const pl = (n, f) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]}`;

  function card(e) {
    const n = e.commands ? `<span class="ex-cmds" title="Голосовых команд">${SV(EI.cmd)}${pl(e.commands, ['команда', 'команды', 'команд'])}</span>` : '';
    const act = e.simple
      ? (confirmId === e.id
        ? `<span class="confirm">Снять расширение?<button class="cm-try danger" data-yes="${e.id}">Да</button><button class="cm-try" data-no="1">Нет</button></span>`
        : e.installed ? `<button class="cm-try danger" data-off="${esc(e.id)}">${SV(EI.trash)}Удалить</button>` : `<button class="cm-try primary" data-on="${esc(e.id)}">${SV(EI.dl)}Установить</button>`)
      : `<button class="cm-try${e.installed ? '' : ' primary'}" data-setup="${e.id}">${SV(e.installed ? EI.gear : EI.dl)}${e.installed ? 'Настроить' : 'Установить'}</button>`;
    return `<div class="cm-card rm-card ex-card${e.installed ? ' on' : ''}" style="--cc:${e.installed ? 'var(--green)' : 'var(--cyan)'};--tint:${tintOf(e.category)}"><div class="ex-top"><span class="ex-ico">${SV(EI[iconOf(e)])}</span><div><div class="ex-name">${esc(e.name)}</div><span class="ex-badge${e.installed ? ' on' : ''}">${e.installed ? 'Установлено' : 'Не установлено'}</span></div></div>
      <div class="ex-desc">${esc(e.desc)}</div><div class="ex-act">${act}${n}</div></div>`;
  }

  const FLT = [['all', 'Все'], ['on', 'Установленные'], ['off', 'Не установленные']];
  const head = document.querySelector('.ex-head');
  head.insertAdjacentHTML('beforeend', `<div class="ex-tools"><div class="ex-seg" id="ex-seg" role="tablist"></div><label class="ex-q">${SV(EI.search)}<input id="ex-q" placeholder="Найти расширение" autocomplete="off" aria-label="Найти расширение"></label></div>`);
  const seg = $('ex-seg'), qin = $('ex-q');
  const paintSeg = (l) => { seg.innerHTML = FLT.map(([k, t]) => `<button type="button" role="tab" class="${k === flt ? 'on' : ''}" data-flt="${k}" aria-selected="${k === flt}">${t}${l ? `<i>${k === 'all' ? l.length : l.filter((e) => e.installed === (k === 'on')).length}</i>` : ''}</button>`).join(''); };
  seg.addEventListener('click', (e) => { const b = e.target.closest('[data-flt]'); if (b) { flt = b.dataset.flt; render(); } });
  qin.addEventListener('input', () => { query = qin.value.trim().toLowerCase(); render(); });
  function render() {
    const l = list();
    $('ex-count').textContent = l ? `установлено ${l.filter((e) => e.installed).length} из ${l.length}` : ''; paintSeg(l);
    if (!l) { body.innerHTML = '<div class="rm-empty"><b>Загружаю список…</b>Список придёт от Jarvis через секунду.</div>'; return; }
    const shown = l.filter((e) => (flt === 'all' || e.installed === (flt === 'on')) && (!query || `${e.name} ${e.desc} ${e.category}`.toLowerCase().includes(query)));
    if (!shown.length) { body.innerHTML = `<div class="rm-empty"><b>${query ? 'Ничего не найдено' : 'Здесь пусто'}</b>${query ? 'Попробуйте другое слово или сбросьте фильтр.' : 'В этом разделе расширений нет.'}</div>`; return; }
    const cats = [...new Set(shown.map((e) => e.category))];
    body.innerHTML = cats.map((c) => { const items = shown.filter((e) => e.category === c); return `<section class="ex-sec"><h3 style="--tint:${tintOf(c)}"><span class="ex-hi">${SV(EI[iconOf(items[0])])}</span>${esc(c)}<em>${items.length}</em></h3><div class="ex-grid">${items.map(card).join('')}</div></section>`; }).join('');
  }

  async function setOn(id, on) {
    confirmId = '';
    if (!m.connected) { const e = demo.find((x) => x.id === id); if (e) e.installed = on; say(on ? 'Расширение установлено' : 'Расширение удалено'); render(); return; }
    const r = await J.send('extension', { id, on });
    say(r && r.ok ? (on ? 'Расширение установлено' : 'Расширение удалено') : r && r.error === 'needs_setup' ? 'Этому расширению нужна настройка: откройте окно' : 'Не получилось: Jarvis не ответил'); render();
  }
  body.addEventListener('click', (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.on) setOn(t.dataset.on, true);
    else if (t.dataset.off) { confirmId = t.dataset.off; render(); }
    else if (t.dataset.yes) setOn(t.dataset.yes, false);
    else if (t.dataset.no) { confirmId = ''; render(); }
    else if (t.dataset.setup) { const x = list().find((y) => y.id === t.dataset.setup); if (x) window.openExtSetup(x); }
  });
  J.on('extensions', () => { if (VIEW === 'exts') render(); });
  J.on('live', () => { if (VIEW === 'exts') render(); });
  window.renderExts = render;
})();
