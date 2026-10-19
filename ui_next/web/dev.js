// Settings > Developer: IDE context apps and folder search, extensions for new files, editors, and the "get to work" projects.
// Data comes from the `dev` bridge command (ui_next/bridge/dev.py); every change is saved at once and the core answers with the fresh state.
// Without a core the tab shows sample data and refuses changes. Relies on globals of app.html: $, J, m, esc, and window.LOOK.ui (look.js), window.toolsPickApp (tools.js).
(() => {
  const root = $('lk-dev'), U = window.LOOK.ui;
  const DEMO = { ok: true, context_apps: ['code.exe', 'pycharm64.exe'], allow_parent: false, depth: 4, extensions: ['py', 'ts'], default_editor: 'code',
    projects: [{ name: 'Jarvis', path: 'C:\\projects\\Jarvis', editor: '', exists: true }] };
  const DEMO_ED = { editors: [{ key: 'code', name: 'VS Code', custom: false }, { key: 'pycharm', name: 'PyCharm', custom: false }], default: 'code' };
  const ERR = { required: 'Заполните название и путь', bad_value: 'Значение не подошло', exists: 'Такая запись уже есть', too_many: 'Записей уже слишком много', not_found: 'Записи уже нет', path_missing: 'Такой папки нет на диске',
    no_editor: 'Редактор не найден: выберите другой', failed: 'Не получилось', write_failed: 'Не удалось сохранить', cancelled: '', no_handler: 'Jarvis ещё запускается' };
  let S = null, ED = null, form = { name: '', path: '', editor: '', old: '' }, found = null, finding = false, timer = 0;
  const say = (t) => { if (t) U.say(t); };

  async function call(body) { if (!m.connected) { say('Без ядра изменить нельзя'); return { ok: false, error: 'offline' }; } return (await J.send('dev', body)) || { ok: false }; }
  async function act(body, okText) {
    const r = await call(body);
    if (r.ok) { if (r.projects !== undefined) S = r; if (r.editors) ED = { editors: r.editors, default: r.default_editor }; say(okText); render(); } else if (r.error !== 'offline') say(ERR[r.error] ?? 'Не получилось сохранить');
    return r;
  }
  async function load() {
    if (!m.connected) { S = DEMO; ED = DEMO_ED; render(); return; }
    const r = await call({ op: 'state' }); if (r.ok) { S = r; render(); }
    const e = await call({ op: 'editors' }); if (e.ok) { ED = e; render(); }
  }
  const btn = (t, a, cls = '') => `<button type="button" class="cm-try ${cls}" ${a}>${t}</button>`;
  const chip = (label, attr, val) => `<span class="tl-chip">${esc(label)}<button type="button" ${attr}="${esc(val)}" aria-label="Убрать ${esc(label)}">×</button></span>`;
  const edName = (key) => { const e = ED && ED.editors.find((x) => x.key === key); return e ? e.name : key; };

  function ctxCard() {
    return U.card('var(--cyan)', 'pc', 'Рабочее окружение',
      '<small class="vc-note">Когда одно из этих приложений в фокусе, Jarvis понимает, в каком вы проекте: папка берётся из активного файла или корня проекта (.git, package.json). Это нужно командам «создай файл», «открой», «запусти».</small>'
      + (S.context_apps.length ? `<div class="tl-chips">${S.context_apps.map((a) => chip(a, 'data-cdel', a)).join('')}</div>` : '<div class="vc-note">Список пуст: определение проекта не работает.</div>')
      + `<div class="vc-add"><input id="dv-app" maxlength="60" placeholder="например: rider64.exe" autocomplete="off">${btn('Добавить', 'data-cadd="1"')}${btn('Из списка', 'data-cpick="1"')}</div>`
      + U.sw('dv_parent', 'Искать в родительских папках', 'Если на «зайди в папку» нужная папка не нашлась внутри, Jarvis поищет выше.', S.allow_parent)
      + U.slider('depth', 'Глубина поиска папок', 1, 10, 1, S.depth, String(S.depth), 'Сколько уровней вложенности просматривать. Больше уровней: дольше поиск.'));
  }
  function extCard() {
    return U.card('var(--amber)', 'doc', 'Новый файл: расширения',
      '<small class="vc-note">Эти расширения предлагаются, когда вы просите создать файл голосом.</small>'
      + (S.extensions.length ? `<div class="tl-chips">${S.extensions.map((e) => chip('.' + e, 'data-xdel', e)).join('')}</div>` : '<div class="vc-note">Пока пусто.</div>')
      + `<div class="vc-add"><input id="dv-ext" maxlength="16" placeholder="py, tsx…" autocomplete="off">${btn('Добавить', 'data-xadd="1"')}</div>`);
  }
  function editorsCard() {
    const body = ED && !ED.editors.length ? '<div class="vc-note">Установленные редакторы не найдены. Добавьте свой кнопкой ниже: например, exe вашей среды разработки.</div>' : ED ? `<div class="dv-eds">${ED.editors.map((e) => `<span class="dv-ed${e.key === ED.default ? ' on' : ''}"><button type="button" data-ed="${esc(e.key)}" aria-pressed="${e.key === ED.default}">${esc(e.name)}</button>${e.custom ? `<button type="button" class="dv-x" data-edrm="${esc(e.key)}" aria-label="Убрать ${esc(e.name)}">×</button>` : ''}</span>`).join('')}</div>`
      : '<div class="vc-note">Определяю установленные редакторы…</div>';
    return U.card('var(--green)', 'pad', 'Редактор по умолчанию',
      `<small class="vc-note">В нём открываются проекты по команде «за работу». Для отдельного проекта можно выбрать другой.</small>${body}<div class="vc-actions">${btn('Добавить свой…', 'data-edadd="1"')}${btn('Обновить список', 'data-edref="1"')}</div>`);
  }
  function projCard() {
    const rows = S.projects.map((p) => `<div class="tl-row"><div class="tl-t"><b>${esc(p.name)}</b><small title="${esc(p.path)}">${esc(p.path)} · ${p.editor ? esc(edName(p.editor)) : 'редактор по умолчанию'}</small>${p.exists ? '' : '<small class="tl-warn">Папки нет на диске</small>'}</div>`
      + `<div class="tl-b">${btn('Открыть', `data-popen="${esc(p.name)}"`)}${btn('Изменить', `data-pedit="${esc(p.name)}"`)}${btn('Удалить', `data-pdel="${esc(p.name)}"`, 'tl-del')}</div></div>`).join('');
    const opts = `<option value="">По умолчанию${ED ? ` (${esc(edName(ED.default))})` : ''}</option>` + (ED ? ED.editors.map((e) => `<option value="${esc(e.key)}"${form.editor === e.key ? ' selected' : ''}>${esc(e.name)}</option>`).join('') : '');
    const res = finding ? '<div class="vc-note">Ищу на диске…</div>' : found ? (found.length ? `<div class="tl-sub">Найдено: ${found.length}. Нажмите на папку, чтобы выбрать.</div><div class="tl-list">${found.map((f) => `<div class="tl-row"><div class="tl-t"><b title="${esc(f)}">${esc(f)}</b></div><div class="tl-b">${btn('Выбрать', `data-fpick="${esc(f)}"`)}</div></div>`).join('')}</div>` : '<div class="vc-note">Ничего не нашлось. Проверьте название или выберите папку вручную.</div>') : '';
    return U.card('var(--mag, #cc44ff)', 'list', 'Проекты: за работу',
      '<small class="vc-note">«Джарвис, за работу»: открою проект в редакторе. Если проектов несколько, спрошу, какой.</small>'
      + (rows ? `<div class="tl-list">${rows}</div>` : '<div class="vc-note">Проекты не добавлены.</div>')
      + `<div class="tl-form"><label>Название<input id="dv-pn" maxlength="60" placeholder="Мой проект" value="${esc(form.name)}" autocomplete="off"></label>`
      + `<label>Путь<input id="dv-pp" maxlength="500" placeholder="C:\\projects\\…" value="${esc(form.path)}" autocomplete="off"></label>`
      + `<div class="vc-actions">${btn('Выбрать папку…', 'data-pbrowse="1"')}${btn('Найти по названию', 'data-pfind="1"')}</div>${res}`
      + `<label>Редактор<select id="dv-pe">${opts}</select></label>`
      + `<div class="vc-actions">${btn(form.old ? 'Сохранить' : 'Добавить проект', 'data-psave="1"', 'primary')}${form.old ? btn('Отмена', 'data-pcancel="1"') : ''}</div></div>`);
  }
  function readForm() { const n = $('dv-pn'), p = $('dv-pp'), e = $('dv-pe'); if (n) form.name = n.value; if (p) form.path = p.value; if (e) form.editor = e.value; }
  function render() {
    if (!S) { root.innerHTML = '<div class="vc-note" style="padding:1rem">Загружаю…</div>'; return; }
    readForm(); const keep = {}; for (const id of ['dv-app', 'dv-ext']) { const e = $(id); if (e && e.value) keep[id] = e.value; }
    root.innerHTML = `<div class="vc-grid"><div class="vc-col">${ctxCard()}${extCard()}</div><div class="vc-col">${editorsCard()}${projCard()}</div></div>`;
    for (const id in keep) $(id).value = keep[id];
    if (window.fzDropdown) window.fzDropdown.watch(root);
  }

  function pickContextApp() {
    if (!window.toolsPickApp) return;
    window.toolsPickApp('Приложение для определения проекта', 'Выберите редактор или среду разработки: когда оно в фокусе, Jarvis узнает проект.', (a) => S.context_apps.includes(((a.exe || '').split(/[\\/]/).pop() || '').toLowerCase()),
      (a) => { const exe = ((a.exe || '').split(/[\\/]/).pop() || '').toLowerCase(); if (exe) act({ op: 'ctx_add', app: exe }, `Добавлено: ${exe}`); else say('У этой программы нет имени процесса'); });
  }

  root.addEventListener('input', (e) => {
    const r = e.target.closest('.vc-rng'); if (!r || r.dataset.key !== 'depth') return;
    const v = parseFloat(r.value); r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    const lab = root.querySelector('[data-val="depth"]'); if (lab) lab.textContent = String(Math.round(v));
    clearTimeout(timer); timer = setTimeout(() => act({ op: 'depth', value: Math.round(v) }), 400);
  });
  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !e.target.matches('input')) return; e.preventDefault();
    const b = { 'dv-app': '[data-cadd]', 'dv-ext': '[data-xadd]', 'dv-pn': '[data-psave]', 'dv-pp': '[data-psave]' }[e.target.id]; if (b) root.querySelector(b).click();
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return; const d = b.dataset;
    if (b.closest('.tgl') || d.sw) { if (d.sw === 'dv_parent') act({ op: 'parent_search', on: !b.classList.contains('on') }); return; }
    if (d.cdel) { act({ op: 'ctx_remove', app: d.cdel }); return; }
    if (d.cadd) { const r = await act({ op: 'ctx_add', app: $('dv-app').value }, 'Добавлено'); if (r.ok) $('dv-app').value = ''; return; }
    if (d.cpick) { pickContextApp(); return; }
    if (d.xdel) { act({ op: 'ext_remove', ext: d.xdel }); return; }
    if (d.xadd) { const r = await act({ op: 'ext_add', ext: $('dv-ext').value }, 'Добавлено'); if (r.ok) $('dv-ext').value = ''; return; }
    if (d.ed) { act({ op: 'editor_default', key: d.ed }, `Редактор по умолчанию: ${edName(d.ed)}`); return; }
    if (d.edrm) { act({ op: 'editor_remove', key: d.edrm }, 'Редактор убран из списка'); return; }
    if (d.edadd) { act({ op: 'editor_add' }, 'Редактор добавлен и выбран'); return; }
    if (d.edref) { say('Ищу редакторы…'); const r = await call({ op: 'editors', refresh: true }); if (r.ok) { ED = r; render(); say('Список обновлён'); } return; }
    if (d.pbrowse) { readForm(); const r = await call({ op: 'pick_folder' }); if (r.ok) { form.path = r.path; if (!form.name.trim()) form.name = r.path.split(/[\\/]/).filter(Boolean).pop() || ''; found = null; render(); } else say(ERR[r.error] ?? ''); return; }
    if (d.pfind) { readForm(); const q = form.name.trim(); if (q.length < 2) { say('Введите название для поиска'); return; } finding = true; found = null; render(); const r = await call({ op: 'find', query: q }); finding = false; found = r.ok ? r.results : null; if (!r.ok && r.error !== 'offline') say(ERR[r.error] ?? 'Поиск не удался'); render(); return; }
    if (d.fpick) { readForm(); form.path = d.fpick; if (!form.name.trim()) form.name = d.fpick.split(/[\\/]/).filter(Boolean).pop() || ''; found = null; render(); return; }
    if (d.psave) { readForm(); const r = await act({ op: 'project_save', name: form.name, path: form.path, editor: form.editor, old_name: form.old }, form.old ? 'Проект сохранён' : 'Проект добавлен'); if (r.ok) { form = { name: '', path: '', editor: '', old: '' }; found = null; render(); } return; }
    if (d.pcancel) { form = { name: '', path: '', editor: '', old: '' }; found = null; render(); return; }
    if (d.pedit) { const p = S.projects.find((x) => x.name === d.pedit); if (p) { form = { name: p.name, path: p.path, editor: p.editor, old: p.name }; found = null; render(); $('dv-pn').focus(); } return; }
    if (d.pdel) { const r = await act({ op: 'project_remove', name: d.pdel }, 'Проект удалён'); if (r.ok && form.old === d.pdel) { form = { name: '', path: '', editor: '', old: '' }; render(); } return; }
    if (d.popen) { const r = await call({ op: 'project_open', name: d.popen }); if (r.ok) say(`Открываю: ${d.popen}`); else if (r.error !== 'offline') say(ERR[r.error] ?? 'Не получилось открыть'); }
  });

  window.renderDev = () => { found = null; finding = false; load(); };
})();
