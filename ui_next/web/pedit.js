// Game profile editor: key bindings, macros (sequences of game actions, keys and pauses) and Hogwarts spell slots.
// Opens over the Games screen. Talks to the core with the `profile` command (see ui_next/bridge/profiles.py); every change is saved at once,
// like in the old editor. Needs a running Jarvis: the profiles are files the core owns. Relies on globals of app.html: $, J, m, esc.
(() => {
  const modal = $('pe-modal'), box = $('pe-box');
  let games = [], game = '', data = null, tab = 'keys', q = '', macro = null, capture = null, confirmDel = false, busy = false;

  /* KeyboardEvent.code -> the key names the core's input layer understands (layout independent, so it works with a Russian layout too) */
  const CODE = { Space: 'space', Enter: 'enter', NumpadEnter: 'numpadenter', Backspace: 'backspace', Delete: 'delete', Tab: 'tab', ShiftLeft: 'shift', ShiftRight: 'shift', ControlLeft: 'ctrl', ControlRight: 'ctrl', AltLeft: 'alt', AltRight: 'alt',
    ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', PageUp: 'pageup', PageDown: 'pagedown', Home: 'home', End: 'end', Insert: 'insert',
    NumpadAdd: 'add', NumpadSubtract: 'subtract', NumpadDivide: 'divide', NumpadMultiply: 'multiply', NumpadDecimal: 'decimal', BracketLeft: '[', BracketRight: ']', Semicolon: ';', Quote: "'", Backquote: '`', Minus: '-', Equal: '=', Backslash: '\\', Comma: ',', Period: '.', Slash: '/',
    PrintScreen: 'printscreen', Pause: 'pause', CapsLock: 'capslock', NumLock: 'numlock', ScrollLock: 'scrolllock' };
  function keyName(e) {
    if (CODE[e.code]) return CODE[e.code];
    let r;
    if ((r = /^Key([A-Z])$/.exec(e.code))) return r[1].toLowerCase();
    if ((r = /^Digit(\d)$/.exec(e.code))) return r[1];
    if ((r = /^Numpad(\d)$/.exec(e.code))) return 'numpad' + r[1];
    if (/^F([1-9]|1[0-2])$/.test(e.code)) return e.code.toLowerCase();
    return '';
  }
  const say = (t) => { const x = $('gm-toast'); x.textContent = t; x.classList.add('on'); clearTimeout(say.t); say.t = setTimeout(() => x.classList.remove('on'), 3000); };
  const call = async (body) => { const r = await J.send('profile', body); return r || { ok: false }; };
  const disp = (k) => (k ? (k.length <= 2 ? k.toUpperCase() : k) : '—');
  const ERR = { bad_key: 'Эту клавишу нельзя назначить.', bad_sequence: 'Не удалось сохранить: проверьте шаги макроса.', no_name: 'Введите название макроса.' };

  async function load(g) {
    game = g; busy = true; render();
    const r = await call({ op: 'get', game: g });
    busy = false;
    data = r.ok ? r : null; if (data && tab === 'grid' && data.kind !== 'hogwarts') tab = 'keys';
    render();
  }
  async function open(hint) {
    modal.hidden = false; macro = null; capture = null; q = ''; tab = 'keys'; confirmDel = false;
    if (!m.connected) { box.innerHTML = head('Клавиши и макросы') + '<div class="pe-note"><b>Нужен запущенный Jarvis</b>Профили игр — файлы, которыми владеет ядро. Запустите Jarvis с мостом интерфейса, и здесь можно будет менять клавиши, макросы и заклинания.</div>'; wireClose(); return; }
    box.innerHTML = head('Клавиши и макросы') + '<div class="pe-note">Загружаю профили…</div>'; wireClose();
    const r = await call({ op: 'games' });
    games = r.ok ? r.games : [];
    if (!games.length) { box.innerHTML = head('Клавиши и макросы') + '<div class="pe-note"><b>Профилей игр нет</b>Установите расширение игры на экране «Расширения».</div>'; wireClose(); return; }
    const h = (hint || '').toLowerCase().replace(/[^a-zа-я0-9 ]/gi, '');
    const pick = games.find((x) => h && (x.game.toLowerCase().includes(h) || h.includes(x.game.toLowerCase()))) || games.find((x) => x.active) || games[0];
    load(pick.game);
  }
  function close() { stopCapture(); modal.hidden = true; macro = null; }
  const head = (t) => `<div class="pe-head"><h3>${esc(t)}</h3><button type="button" class="pe-x" id="pe-close" aria-label="Закрыть">×</button></div>`;
  const wireClose = () => { const c = $('pe-close'); if (c) c.onclick = close; };

  /* ---- key capture ---- */
  function stopCapture() { if (capture) { document.removeEventListener('keydown', capture.fn, true); capture = null; } }
  function startCapture(btn, done) {
    stopCapture(); btn.textContent = 'Нажмите клавишу…'; btn.classList.add('listen');
    const fn = (e) => {
      e.preventDefault(); e.stopPropagation();
      if (e.code === 'Escape') { stopCapture(); render(); return; }
      const k = keyName(e); if (!k) return;
      stopCapture(); done(k);
    };
    capture = { fn }; document.addEventListener('keydown', fn, true);
  }

  /* ---- keys & macros lists ---- */
  const match = (s) => !q || s.toLowerCase().includes(q);
  function rowsHtml() {
    const rows = data.rows.filter((r) => match(r.label) || match(r.key));
    if (!rows.length) return `<div class="pe-empty">${q ? 'Ничего не найдено' : 'Здесь пока нет клавиш'}</div>`;
    return rows.map((r) => `<div class="pe-row" data-row="${esc(r.id)}"><span class="pe-name">${esc(r.label)}</span>
      <button type="button" class="pe-key${r.key ? ' set' : ''}" data-act="key">${esc(disp(r.key))}</button>
      <span class="pe-tools"><button type="button" class="pe-ib ok" data-act="test" title="Нажать эту клавишу сейчас" ${r.key || r.macro ? '' : 'disabled'}>▶</button>${r.kind === 'entry' ? `<button type="button" class="pe-ib amb" data-act="edit" title="Редактировать как макрос">⚙</button>` : ''}<button type="button" class="pe-ib red" data-act="clear" title="Убрать клавишу" ${r.key ? '' : 'disabled'}>✕</button></span></div>`).join('');
  }
  function macrosHtml() {
    const ms = data.macros.filter((x) => match(x.name) || x.variants.some(match));
    return `<div class="pe-new"><button type="button" class="cm-try pe-go" id="pe-newbtn">+ Новый макрос</button></div>${ms.length ? ms.map((x) => `<div class="pe-row mac" data-idx="${x.idx}" data-row="s:${x.idx}"><span class="pe-name">${esc(x.name)}<small>${x.telemetry ? esc(x.telemetry) : x.variants.map(esc).join(' · ')}</small></span><span class="pe-steps">${x.steps} шаг${x.steps % 10 === 1 && x.steps % 100 !== 11 ? '' : x.steps % 10 >= 2 && x.steps % 10 <= 4 && (x.steps % 100 < 10 || x.steps % 100 >= 20) ? 'а' : 'ов'}</span>
      <span class="pe-tools"><button type="button" class="pe-ib ok" data-act="test" title="Выполнить сейчас">▶</button><button type="button" class="pe-ib amb" data-act="edit" title="Редактировать">⚙</button></span></div>`).join('') : `<div class="pe-empty">${q ? 'Ничего не найдено' : 'Макросов пока нет. Макрос — это цепочка действий игры, клавиш и пауз под одну голосовую команду.'}</div>`}`;
  }
  function gridHtml() {
    const opts = (cur) => `<option value="—">—</option>` + data.slottable.map((n) => `<option${n === cur ? ' selected' : ''}>${esc(n)}</option>`).join('');
    return [1, 2, 3, 4].map((s) => `<div class="pe-set"><b>F${s}</b>${[1, 2, 3, 4].map((sl) => `<label><small>слот ${sl}</small><select data-set="${s}" data-slot="${sl}">${opts((data.grid[s] || {})[sl] || '')}</select></label>`).join('')}</div>`).join('');
  }

  function render() {
    if (macro) { renderMacro(); return; }
    const tabs = `<button type="button" class="pe-tab${tab === 'keys' ? ' on' : ''}" data-tab="keys">Клавиши</button><button type="button" class="pe-tab${tab === 'macros' ? ' on' : ''}" data-tab="macros">Макросы${data ? ` <i>${data.macros.length}</i>` : ''}</button>${data && data.kind === 'hogwarts' ? `<button type="button" class="pe-tab${tab === 'grid' ? ' on' : ''}" data-tab="grid">Заклинания F1–F4</button>` : ''}`;
    box.innerHTML = head('Клавиши и макросы') + `<div class="pe-games">${games.map((g) => `<button type="button" class="pe-g${g.game === game ? ' on' : ''}" data-game="${esc(g.game)}">${esc(g.short)}</button>`).join('')}</div>
      <div class="pe-bar"><div class="pe-tabs">${tabs}</div>${tab === 'grid' ? '' : `<input class="pe-search" id="pe-q" placeholder="Поиск" value="${esc(q)}" autocomplete="off">`}</div>
      <div class="pe-list" id="pe-list">${busy || !data ? '<div class="pe-empty">Загружаю…</div>' : tab === 'keys' ? rowsHtml() : tab === 'macros' ? macrosHtml() : gridHtml()}</div>
      <div class="pe-foot"><small>${tab === 'grid' ? 'Выберите заклинание для каждого слота: изменения сохраняются сразу.' : 'Нажмите на клавишу в строке, затем нужную кнопку на клавиатуре. Esc отменяет. Изменения сохраняются сразу.'}</small></div>`;
    wireClose();
  }

  box.addEventListener('click', async (e) => {
    const t = e.target.closest('button'); if (!t) return;
    if (t.dataset.game) { macro = null; q = ''; return load(t.dataset.game); }
    if (t.dataset.tab) { stopCapture(); tab = t.dataset.tab; q = ''; return render(); }
    if (t.id === 'pe-newbtn') return newMacroForm();
    const row = t.closest('[data-row]'); if (!row) return;
    const id = row.dataset.row;
    if (t.dataset.act === 'key') {
      startCapture(t, async (k) => { const r = await call({ op: 'set_key', game, row: id, key: k }); if (!r.ok) say(ERR[r.error] || 'Не удалось сохранить'); load(game); });
    } else if (t.dataset.act === 'clear') {
      const r = await call({ op: 'set_key', game, row: id, key: '' }); if (!r.ok) say('Не удалось сохранить'); load(game);
    } else if (t.dataset.act === 'test') {
      const r = await call({ op: 'test', game, row: id }); say(r.ok ? 'Выполняю: переключитесь в игру' : 'Не получилось выполнить');
    } else if (t.dataset.act === 'edit') {
      const idx = row.dataset.idx || id.slice(2); openMacro(+idx);
    }
  });
  box.addEventListener('input', (e) => { if (e.target.id === 'pe-q') { q = e.target.value.trim().toLowerCase(); const l = $('pe-list'); l.innerHTML = tab === 'keys' ? rowsHtml() : macrosHtml(); } });
  box.addEventListener('change', async (e) => {
    const s = e.target.closest('select[data-set]'); if (!s) return;
    const r = await call({ op: 'grid_set', game, set: +s.dataset.set, slot: +s.dataset.slot, name: s.value });
    if (!r.ok) say('Не удалось сохранить'); load(game);
  });

  /* ---- new macro ---- */
  function newMacroForm() {
    const binds = data.binds.map((b) => `<option value="${esc(b.id)}">${esc(b.label)}</option>`).join('');
    $('pe-list').innerHTML = `<div class="pe-form"><label>Название команды<input id="nm-name" placeholder="Например: подготовь тягач" autocomplete="off"></label>
      <label>Фразы, на которые она срабатывает (через запятую)<input id="nm-vars" placeholder="заведи, включи свет, поехал" autocomplete="off"></label>
      <label>Первое действие<select id="nm-first"><option value="">— пауза —</option>${binds}</select></label>
      <div class="pe-err" id="nm-err"></div><div class="pe-actions"><button type="button" class="cm-try" id="nm-cancel">Отмена</button><button type="button" class="cm-try pe-go" id="nm-ok">Создать и открыть</button></div></div>`;
    $('nm-name').focus();
    $('nm-cancel').onclick = () => render();
    $('nm-ok').onclick = async () => {
      const name = $('nm-name').value.trim(); if (!name) { $('nm-err').textContent = ERR.no_name; return; }
      const r = await call({ op: 'macro_create', game, name, variants: $('nm-vars').value.split(',').map((x) => x.trim()).filter(Boolean), first: $('nm-first').value });
      if (!r.ok) { $('nm-err').textContent = ERR[r.error] || 'Не удалось создать'; return; }
      await load(game); openMacro(r.idx);
    };
  }

  /* ---- macro editor ---- */
  async function openMacro(idx) {
    const r = await call({ op: 'macro_get', game, idx });
    if (!r.ok) { say('Не удалось открыть макрос'); return; }
    macro = { idx, name: r.name, variants: r.variants.join(', '), seq: r.sequence.map((s) => ({ ...s })), telemetry: r.telemetry }; confirmDel = false; render();
  }
  const bindOpts = (cur) => data.binds.map((b) => `<option value="${esc(b.id)}"${b.id === cur ? ' selected' : ''}>${esc(b.label)}</option>`).join('');
  function renderMacro() {
    const steps = macro.seq.map((s, i) => {
      const kind = 'wait' in s ? 'wait' : 'binding' in s ? 'binding' : 'key';
      const icon = { wait: '⏱', binding: '★', key: '⌨' }[kind];
      const field = kind === 'wait' ? `<label class="pe-mini">пауза, с<input data-f="wait" value="${esc(s.wait)}" inputmode="decimal"></label>`
        : kind === 'binding' ? `<label class="pe-mini grow">действие игры<select data-f="binding">${bindOpts(s.binding)}</select></label>`
          : `<span class="pe-mini">клавиша<button type="button" class="pe-key set" data-f="keybtn">${esc(disp(s.key))}</button></span><label class="pe-mini">удержание, с<input data-f="hold" value="${esc(s.hold ?? 0.1)}" inputmode="decimal"></label>`;
      return `<div class="pe-step ${kind}${s._disabled ? ' off' : ''}" data-i="${i}"><label class="pe-chk" title="Шаг включён"><input type="checkbox" data-f="on" ${s._disabled ? '' : 'checked'}><i></i></label><span class="pe-ico">${icon}</span>${field}<button type="button" class="pe-ib red" data-f="del" title="Удалить шаг">×</button></div>`;
    }).join('');
    box.innerHTML = head(macro.name || 'Макрос') + `<div class="pe-mbody"><button type="button" class="cm-try" id="mc-back">← К списку</button>
      ${macro.telemetry ? `<p class="pe-hint">Системное действие: ${esc(macro.telemetry)}</p>` : ''}
      <label class="pe-fl">Фразы (через запятую)<input id="mc-vars" value="${esc(macro.variants)}" autocomplete="off"></label>
      <div class="pe-steps-list" id="mc-steps">${steps || '<div class="pe-empty">Шагов нет</div>'}</div>
      <div class="pe-add"><button type="button" class="cm-try" id="mc-ab">+ Действие игры</button><button type="button" class="cm-try" id="mc-ak">+ Клавиша</button><button type="button" class="cm-try" id="mc-aw">+ Пауза</button></div></div>
      <div class="pe-foot"><button type="button" class="cm-try danger" id="mc-del">${confirmDel ? 'Точно удалить?' : 'Удалить макрос'}</button><span class="pe-sp"></span><div class="pe-err" id="mc-err"></div><button type="button" class="cm-try pe-go" id="mc-save">Сохранить</button></div>`;
    wireClose(); wireMacro();
  }
  function syncFields() {
    macro.variants = $('mc-vars').value;
    document.querySelectorAll('#mc-steps .pe-step').forEach((el) => {
      const s = macro.seq[+el.dataset.i];
      const w = el.querySelector('[data-f=wait]'), h = el.querySelector('[data-f=hold]'), b = el.querySelector('select[data-f=binding]'), on = el.querySelector('[data-f=on]');
      if (w) s.wait = w.value; if (h) s.hold = h.value; if (b) s.binding = b.value;
      if (on) { if (on.checked) delete s._disabled; else s._disabled = true; }
    });
  }
  function wireMacro() {
    $('mc-back').onclick = () => { macro = null; load(game); };
    $('mc-ab').onclick = () => { syncFields(); macro.seq.push({ binding: data.binds[0] ? data.binds[0].id : '' }); renderMacro(); };
    $('mc-ak').onclick = () => { syncFields(); macro.seq.push({ key: '', hold: 0.1 }); renderMacro(); };
    $('mc-aw').onclick = () => { syncFields(); macro.seq.push({ wait: 0.5 }); renderMacro(); };
    $('mc-steps').onclick = (e) => {
      const b = e.target.closest('button'); if (!b) return;
      const i = +b.closest('.pe-step').dataset.i;
      if (b.dataset.f === 'del') { syncFields(); macro.seq.splice(i, 1); renderMacro(); }
      else if (b.dataset.f === 'keybtn') startCapture(b, (k) => { syncFields(); macro.seq[i].key = k; renderMacro(); });
    };
    $('mc-steps').onchange = (e) => { if (e.target.dataset.f === 'on') { e.target.closest('.pe-step').classList.toggle('off', !e.target.checked); } };
    $('mc-del').onclick = async () => {
      if (!confirmDel) { confirmDel = true; $('mc-del').textContent = 'Точно удалить?'; setTimeout(() => { confirmDel = false; const d = $('mc-del'); if (d) d.textContent = 'Удалить макрос'; }, 3000); return; }
      const r = await call({ op: 'macro_delete', game, idx: macro.idx }); macro = null; say(r.ok ? 'Макрос удалён' : 'Не удалось удалить'); load(game);
    };
    $('mc-save').onclick = async () => {
      syncFields();
      const seq = macro.seq.map((s) => { const o = { ...s }; if ('wait' in o) o.wait = parseFloat(String(o.wait).replace(',', '.')) || 0; if ('hold' in o) o.hold = parseFloat(String(o.hold).replace(',', '.')) || 0.1; return o; });
      if (seq.some((s) => 'key' in s && !s.key)) { $('mc-err').textContent = 'У одного из шагов не выбрана клавиша.'; return; }
      const r = await call({ op: 'macro_save', game, idx: macro.idx, sequence: seq, variants: macro.variants.split(',').map((x) => x.trim()).filter(Boolean) });
      if (!r.ok) { $('mc-err').textContent = ERR[r.error] || 'Не удалось сохранить'; return; }
      macro = null; say('Макрос сохранён'); load(game);
    };
  }

  modal.addEventListener('mousedown', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !modal.hidden && !capture) close(); });
  if (window.fzDropdown) window.fzDropdown.watch(box);
  window.openProfileEditor = open;
})();
