// Calendar screen: connecting a CalDAV calendar (Yandex, iCloud, Fastmail, Nextcloud or any server) so events can be created, changed and
// deleted from here. Login and an app password go to the core once; the password is kept in the secrets file and never comes back to the screen.
(() => {
  const C = window.Cal; if (!C) return;
  const { S, call, say, esc, modal, mbox } = C;
  const SERVERS = [['yandex', 'Яндекс', 'https://id.yandex.ru/security/app-passwords'], ['icloud', 'iCloud', 'https://appleid.apple.com/account/manage'], ['fastmail', 'Fastmail', ''], ['other', 'Другой сервер (Nextcloud и другие)', '']];
  const ERR = { auth: 'Сервер не принял логин или пароль приложения', network: 'Нет связи с сервером', bad_url: 'Неверный адрес сервера', no_home: 'На сервере не нашлись календари', no_calendars: 'На сервере нет календарей с событиями', exists: 'Эти календари уже подключены' };
  let found = null;

  const val = (id) => $(id).value.trim();
  function render() {
    const kind = $('dv-srv') ? val('dv-srv') : 'yandex', help = (SERVERS.find((x) => x[0] === kind) || [])[2];
    const keep = { user: $('dv-user') ? val('dv-user') : '', pass: $('dv-pass') ? $('dv-pass').value : '', url: $('dv-url') ? val('dv-url') : '' };
    mbox.innerHTML = `<div class="xs-head"><h3>Подключить по CalDAV</h3><button type="button" class="xs-x" id="dv-close" aria-label="Закрыть">×</button></div>
      <div class="xs-body"><p class="dv-note">Так события можно не только смотреть, но и создавать, переносить и удалять. Нужен пароль приложения, а не основной пароль от аккаунта.${help ? ` <a href="#" data-url="${esc(help)}">Создать пароль приложения</a>` : ''}</p>
        ${found ? `<div class="dv-list">${found.map((c, i) => `<label class="dv-row"><input type="checkbox" data-i="${i}" checked><i style="background:${esc(c.color || '#4c8dff')}"></i><b>${esc(c.name)}</b></label>`).join('')}</div>`
    : `<label class="xs-f"><span>Сервер</span><select id="dv-srv">${SERVERS.map(([k, n]) => `<option value="${k}"${k === kind ? ' selected' : ''}>${n}</option>`).join('')}</select></label>
        ${kind === 'other' ? `<label class="xs-f"><span>Адрес сервера</span><input id="dv-url" data-fld="1" placeholder="https://cloud.example.com/remote.php/dav" value="${esc(keep.url)}" autocomplete="off"></label>` : ''}
        <label class="xs-f"><span>Логин</span><input id="dv-user" data-fld="1" placeholder="name@yandex.ru" value="${esc(keep.user)}" autocomplete="off"></label>
        <label class="xs-f"><span>Пароль приложения</span><input id="dv-pass" data-fld="1" type="password" value="${esc(keep.pass)}" autocomplete="new-password"></label>`}</div>
      <div class="xs-err" id="dv-err" role="alert"></div>
      <div class="xs-foot"><span class="xs-sp"></span><button type="button" class="cm-try" id="dv-cancel">Отмена</button><button type="button" class="cm-try primary" id="dv-go">${found ? 'Подключить' : 'Найти календари'}</button></div>`;
    if (window.fzDropdown) window.fzDropdown.watch(mbox);
  }
  function open() { found = null; modal.hidden = false; render(); setTimeout(() => { const f = $('dv-user'); if (f) f.focus(); }, 40); }
  const close = () => { modal.hidden = true; mbox.innerHTML = ''; found = null; };

  async function go() {
    const err = $('dv-err'), b = $('dv-go'); err.textContent = '';
    if (!m.connected) { err.textContent = 'Демо: без ядра подключиться нельзя'; return; }
    const kind = val('dv-srv') || 'yandex';
    if (found) {
      const picks = [...mbox.querySelectorAll('.dv-row input:checked')].map((x) => found[+x.dataset.i]);
      if (!picks.length) { err.textContent = 'Отметьте хотя бы один календарь'; return; }
      b.disabled = true; const r = await call({ op: 'caldav_add', server: found.server, user: found.user, password: found.password, calendars: picks }); b.disabled = false;
      if (!r.ok) { err.textContent = r.message || ERR[r.error] || 'Не удалось подключить'; return; }
      S.state = { ...S.state, ...r.state }; found = null; close(); C.invalidate(); say('Календари подключены'); C.load(true); return;
    }
    const server = kind === 'other' ? val('dv-url') : kind, user = val('dv-user'), password = $('dv-pass').value;
    if (!user || !password || (kind === 'other' && !server)) { err.textContent = 'Заполните все поля'; return; }
    b.disabled = true; b.textContent = 'Ищу…'; const r = await call({ op: 'caldav_find', server, user, password }); b.disabled = false; b.textContent = 'Найти календари';
    if (!r.ok) { err.textContent = r.message || ERR[r.error] || 'Не удалось подключиться'; return; }
    found = r.calendars; found.server = server; found.user = user; found.password = password; render();
  }
  mbox.addEventListener('click', (e) => {
    const a = e.target.closest('[data-url]'); if (a && $('dv-go')) { e.preventDefault(); if (m.connected) J.send('open_url', { url: a.dataset.url }); return; }
    const b = e.target.closest('button'); if (!b || !$('dv-go')) return;
    if (b.id === 'dv-close' || b.id === 'dv-cancel') close(); else if (b.id === 'dv-go') go();
  });
  mbox.addEventListener('change', (e) => { if (e.target.id === 'dv-srv') render(); });
  mbox.addEventListener('keydown', (e) => { if (e.key === 'Enter' && $('dv-go') && e.target.matches('input')) { e.preventDefault(); go(); } });
  window.CalDav = { open };
})();
