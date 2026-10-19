// Setup forms of the extensions that need more than "install": Telegram chat id, mail account, calendar sources, ETS2 plugin, Planetbase mod.
// Opens as a panel over the Extensions screen; talks to the core with the `ext_setup` command (op get / save / act). Passwords go to the core
// and are never sent back (the form only learns "a password is saved"). Relies on globals of app.html: $, J, m, esc, VIEW.
(() => {
  const modal = $('ex-modal'), box = $('ex-mbox');
  let cur = null;       // { id, name, state }
  const DEMO_STATE = {
    telegram: { kind: 'telegram', installed: false, chat_id_set: false },
    mail: { kind: 'mail', installed: false, email: '', imap: '', smtp: '', has_password: false },
    calendar: { kind: 'calendar', installed: false, sources: [] },
    ets2: { kind: 'ets2', installed: false, dll: false, path: true, ai_key: false, ai_on: false },
    planetbase: { kind: 'planetbase', installed: false, found: true, mod: false },
  };
  const ERR = { bad_chat_id: 'Chat ID состоит из цифр (может начинаться с «-»).', bad_email: 'Укажите корректный адрес почты.', no_password: 'Укажите пароль приложения.', bad_sources: 'Не удалось прочитать список источников.', no_form: 'Для этого расширения форма не нужна.' };
  const say = (t) => { const x = $('ex-toast'); x.textContent = t; x.classList.add('on'); clearTimeout(say.t); say.t = setTimeout(() => x.classList.remove('on'), 3200); };

  const field = (id, label, val, ph, extra = '') => `<label class="xs-f"><span>${label}</span><input id="${id}" value="${esc(val || '')}" placeholder="${esc(ph || '')}" autocomplete="off" spellcheck="false" ${extra}></label>`;
  const status = (ok, onText, offText) => `<span class="xs-st ${ok ? 'ok' : 'warn'}">${ok ? onText : offText}</span>`;

  const FORMS = {
    telegram: (s) => ({
      title: 'Охранная камера', body: `<p>Чтобы фото при обнаружении движения приходили на телефон, укажите ваш личный Telegram Chat ID.</p>
        <ol class="xs-steps"><li>Найдите в Telegram бота <b>@userinfobot</b>.</li><li>Нажмите /start: бот пришлёт ваш ID.</li></ol>
        ${field('xs-chat', 'Chat ID', '', s.chat_id_set ? 'уже задан: оставьте пустым, чтобы не менять' : 'например 123456789', 'inputmode="numeric"')}`,
      save: () => ({ chat_id: $('xs-chat').value.trim() }),
    }),
    mail: (s) => ({
      title: 'Подключение почты', body: `<p>Данные хранятся только на вашем компьютере. Пароль не показывается и не возвращается в интерфейс.</p>
        ${field('xs-email', 'Адрес почты', s.email, 'name@gmail.com', 'type="email"')}
        <label class="xs-f"><span>Пароль приложения ${s.has_password ? '<em class="xs-ok">уже сохранён</em>' : ''}</span><span class="xs-pw"><input id="xs-pass" type="password" placeholder="${s.has_password ? 'оставьте пустым, чтобы сохранить текущий' : 'пароль приложения'}" autocomplete="new-password" spellcheck="false"><button type="button" class="cm-try" id="xs-eye">Показать</button></span></label>
        <p class="xs-hint">Если в Google включена двухфакторная защита, обычный пароль не подойдёт: создайте отдельный «пароль приложения» (16 символов) в настройках аккаунта. <button type="button" class="xs-link" id="xs-apppwd">Открыть страницу создания</button></p>
        <div class="xs-two">${field('xs-imap', 'IMAP-сервер', s.imap, 'imap.yandex.ru')}${field('xs-smtp', 'SMTP-сервер', s.smtp, 'smtp.yandex.ru')}</div><p class="xs-hint">Серверы нужны, если почта не Gmail.</p>`,
      save: () => ({ email: $('xs-email').value.trim(), password: $('xs-pass').value, imap: $('xs-imap').value.trim(), smtp: $('xs-smtp').value.trim() }),
      wire: () => {
        $('xs-eye').onclick = () => { const i = $('xs-pass'); const show = i.type === 'password'; i.type = show ? 'text' : 'password'; $('xs-eye').textContent = show ? 'Скрыть' : 'Показать'; };
        $('xs-apppwd').onclick = async () => { if (!m.connected) { say('Демо: откроется страница создания пароля приложения'); return; } await J.send('ext_setup', { id: cur.id, op: 'act', action: 'app_password_page', email: $('xs-email').value.trim() }); };
      },
    }),
    calendar: (s) => {
      cur.sources = cur.sources || (s.sources || []).slice();
      return {
        title: 'Календарь', body: `<p>Добавьте ссылки на календари или пути к файлам .ics. Jarvis читает их и напоминает о ближайших событиях.</p>
          <div class="xs-list" id="xs-list"></div>
          <div class="xs-add">${field('xs-src', 'Ссылка или путь к .ics', '', 'https://.../.ics  или  C:\\путь\\calendar.ics')}<button type="button" class="cm-try" id="xs-addbtn">Добавить</button></div>`,
        save: () => { const v = $('xs-src').value.trim(); if (v) { cur.sources.push(v); } return { sources: cur.sources }; },
        wire: () => {
          const paint = () => { $('xs-list').innerHTML = cur.sources.length ? cur.sources.map((x, i) => `<div class="xs-row"><span title="${esc(x)}">${esc(x)}</span><button type="button" class="cm-try danger" data-rm="${i}">Убрать</button></div>`).join('') : '<div class="xs-empty">Источников пока нет</div>'; };
          const add = () => { const i = $('xs-src'), v = i.value.trim(); if (v) { cur.sources.push(v); i.value = ''; paint(); } };
          $('xs-addbtn').onclick = add; $('xs-src').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); add(); } });
          $('xs-list').onclick = (e) => { const b = e.target.closest('[data-rm]'); if (b) { cur.sources.splice(+b.dataset.rm, 1); paint(); } };
          paint();
        },
      };
    },
    ets2: (s) => ({
      title: 'Euro Truck Simulator 2', body: `<p>Голосовое управление грузовиком работает через плагин телеметрии в папке игры.</p>
        <div class="xs-line"><b>Плагин телеметрии</b>${status(s.dll, 'установлен', 'не установлен')}${s.dll ? '' : `<button type="button" class="cm-try" id="xs-act-dll">${s.path ? 'Установить плагин' : 'Папка игры не найдена'}</button>`}</div>
        ${s.path ? '' : '<p class="xs-hint">Игра не найдена автоматически: при установке Jarvis попросит выбрать её папку.</p>'}
        <div class="xs-line"><b>AI-комментарии к рейсам</b>${s.ai_key ? `<button type="button" class="tgl${s.ai_on ? ' on' : ''}" id="xs-ai" aria-pressed="${!!s.ai_on}"><span class="sw"></span></button>` : '<span class="xs-st warn">нужен ключ</span>'}</div>
        ${s.ai_key ? '' : '<p class="xs-hint">Подключите AI-модель в настройках, и Jarvis будет давать брифинги перед рейсом и отчёты после доставки.</p>'}`,
      wire: () => {
        const dll = $('xs-act-dll'); if (dll) dll.onclick = () => act('install', 'Установка плагина запущена', dll);
        const ai = $('xs-ai'); if (ai) ai.onclick = async () => { const on = !ai.classList.contains('on'); ai.classList.toggle('on', on); ai.setAttribute('aria-pressed', on); if (m.connected) await J.send('ext_setup', { id: cur.id, op: 'act', action: 'ai', on }); };
      },
    }),
    planetbase: (s) => ({
      title: 'Planetbase', body: `<p>Для телеметрии и голосового управления колонией в игру ставится небольшой мод. Он патчит файлы игры, копия оригинала сохраняется.</p>
        <div class="xs-line"><b>Игра</b>${status(s.found, 'найдена', 'не найдена')}</div>
        <div class="xs-line"><b>Мод телеметрии</b>${status(s.mod, 'активен', 'не установлен')}${s.mod || !s.found ? '' : '<button type="button" class="cm-try" id="xs-act-mod">Установить мод</button>'}</div>`,
      wire: () => { const b = $('xs-act-mod'); if (b) b.onclick = () => act('install', 'Установка мода запущена', b); },
    }),
  };

  async function act(action, okText, btn) {
    if (!m.connected) { say('Демо: ' + okText.toLowerCase()); return; }
    btn.disabled = true;
    const r = await J.send('ext_setup', { id: cur.id, op: 'act', action });
    if (r && r.ok) { cur.state = r.state || cur.state; say(r.needs_path ? 'Папка игры не найдена: выберите её в открывшемся окне' : r.not_found ? 'Игра не найдена на этом компьютере' : okText); setTimeout(refreshState, 4000); render(); }
    else { btn.disabled = false; say('Не получилось: Jarvis ещё запускается'); }
  }
  async function refreshState() {
    if (!cur || !m.connected || modal.hidden) return;
    const r = await J.send('ext_setup', { id: cur.id, op: 'get' });
    if (r && r.ok && !modal.hidden) { cur.state = r.state; render(); }
  }

  function render() {
    const s = cur.state, f = FORMS[s.kind](s), hasSave = !!f.save;
    box.innerHTML = `<div class="xs-head"><h3>${esc(f.title)}</h3><button type="button" class="xs-x" id="xs-close" aria-label="Закрыть">×</button></div><div class="xs-body">${f.body}</div>
      <div class="xs-err" id="xs-err" role="alert"></div>
      <div class="xs-foot">${s.installed ? '<button type="button" class="cm-try danger" id="xs-uninst">Удалить расширение</button>' : ''}<span class="xs-sp"></span><button type="button" class="cm-try" id="xs-cancel">${hasSave ? 'Отмена' : 'Закрыть'}</button>${hasSave ? `<button type="button" class="cm-try xs-go" id="xs-save">${s.installed ? 'Сохранить' : 'Установить'}</button>` : ''}</div>`;
    if (f.wire) f.wire();
    $('xs-close').onclick = $('xs-cancel').onclick = close;
    const un = $('xs-uninst');
    if (un) un.onclick = async () => {
      if (!un.dataset.sure) { un.dataset.sure = '1'; un.textContent = 'Точно удалить?'; setTimeout(() => { if (un.isConnected) { delete un.dataset.sure; un.textContent = 'Удалить расширение'; } }, 3000); return; }
      if (m.connected) await J.send('ext_setup', { id: cur.id, op: 'act', action: 'uninstall' }); say('Расширение удалено'); close();
    };
    const sv = $('xs-save');
    if (sv) sv.onclick = async () => {
      const data = f.save(); $('xs-err').textContent = '';
      if (!m.connected) { say('Демо: настройки сохранены бы здесь'); close(); return; }
      sv.disabled = true;
      const r = await J.send('ext_setup', { id: cur.id, op: 'save', ...data });
      sv.disabled = false;
      if (r && r.ok) { say(s.installed ? 'Настройки сохранены' : 'Расширение установлено'); close(); } else $('xs-err').textContent = (r && ERR[r.error]) || 'Не получилось сохранить: Jarvis ещё запускается';
    };
    const first = box.querySelector('input'); if (first && !first.value) first.focus();
  }

  function close() { modal.hidden = true; cur = null; }
  async function open(e) {
    const id = e.id;
    cur = { id, name: e.name };
    modal.hidden = false; box.innerHTML = '<div class="xs-body"><p>Загружаю…</p></div>';
    let st = null;
    if (m.connected) { const r = await J.send('ext_setup', { id, op: 'get' }); st = r && r.ok ? r.state : null; }
    else if (DEMO_STATE[e.setup]) st = { ...DEMO_STATE[e.setup], installed: !!e.installed };
    if (!st) { box.innerHTML = '<div class="xs-body"><p>Не удалось загрузить настройки: Jarvis ещё запускается.</p></div>'; return; }
    cur.state = st; render();
  }
  modal.addEventListener('mousedown', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden) close(); });
  window.openExtSetup = open;
})();
