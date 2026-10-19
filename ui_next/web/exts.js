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
  let confirmId = '', toastTimer = 0, demo = DEMO.map((e) => ({ ...e }));
  const body = $('ex-body'), toast = $('ex-toast');
  const list = () => (m.connected ? m.extensions : demo);
  function say(t) { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); }
  const pl = (n, f) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]}`;

  function card(e) {
    const act = e.simple
      ? (confirmId === e.id
        ? `<span class="confirm">Снять расширение?<button class="cm-try danger" data-yes="${e.id}">Да</button><button class="cm-try" data-no="1">Нет</button></span>`
        : e.installed ? `<button class="cm-try danger" data-off="${esc(e.id)}">Удалить</button>` : `<button class="cm-try" data-on="${esc(e.id)}">Установить</button>`)
      : `<button class="cm-try" data-setup="${e.id}">${e.installed ? 'Настроить' : 'Установить'}</button>${e.commands ? `<small>${pl(e.commands, ['команда', 'команды', 'команд'])}</small>` : ''}`;
    return `<div class="cm-card rm-card ex-card" style="--cc:${e.installed ? 'var(--green)' : 'var(--cyan)'}"><div class="ex-top"><div><div class="ex-name">${esc(e.name)}</div><div class="ex-desc">${esc(e.desc)}</div></div><span class="ex-badge${e.installed ? ' on' : ''}">${e.installed ? 'Установлено' : 'Не установлено'}</span></div>
      <div class="ex-act">${act}${e.commands && e.simple ? `<small>${pl(e.commands, ['команда', 'команды', 'команд'])}</small>` : ''}</div></div>`;
  }

  function render() {
    const l = list();
    $('ex-count').textContent = l ? `установлено ${l.filter((e) => e.installed).length} из ${l.length}` : '';
    if (!l) { body.innerHTML = '<div class="rm-empty"><b>Загружаю список…</b>Список придёт от Jarvis через секунду.</div>'; return; }
    const cats = [...new Set(l.map((e) => e.category))];
    body.innerHTML = cats.map((c) => `<section class="ex-sec"><h3>${esc(c)}</h3><div class="ex-grid">${l.filter((e) => e.category === c).map(card).join('')}</div></section>`).join('');
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
