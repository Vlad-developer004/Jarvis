// Dialogs the core waits for: a name for a new folder or file, a commit message, what to clean up, which video to play, the camera alert.
// Data: the sticky `prompt` topic from the core (ui_next/bridge/prompts.py, dialogs.py); the answer goes back through the `prompt` command and is checked by the core against what it offered.
// Spoken words ("создай", "отмена", "первое") arrive as `prompt_cmd` and press the same buttons. This file is the shell plus the text, video and notice kinds; the commit and cleanup kinds are in prompts_list.js.
// Relies on globals of app.html: $, J, m, esc, ic.
(() => {
  const KINDS = {};
  let root = null, shownId = 0, shownKind = '';

  const btn = (t, a, cls = '') => `<button type="button" class="cm-try ${cls}" ${a}>${t}</button>`;
  window.PR = { kinds: KINDS, esc, btn, toast: (t) => { const e = root && root.querySelector('.pr-toast'); if (!e) return; e.textContent = t; e.classList.add('on'); clearTimeout(window.PR.tt); window.PR.tt = setTimeout(() => e.classList.remove('on'), 2600); } };

  async function answer(status, value) {
    const id = shownId; close(); if (!m.connected) return;
    await J.send('prompt', { op: 'answer', id, status, value });
  }
  function close() { if (root) { root.remove(); root = null; } document.removeEventListener('keydown', onKey, true); shownId = 0; shownKind = ''; }

  function shell(msg, spec) {
    close();
    root = document.createElement('div'); root.className = 'pr'; root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); root.setAttribute('aria-label', spec.title);
    const acts = spec.actions.map((a) => btn(a.label, `data-pr="${a.id}"`, `${a.primary ? 'primary' : ''} ${a.danger ? 'tl-del' : ''}`)).join('');
    root.innerHTML = `<div class="pr-box pr-${msg.kind}${spec.wide ? ' wide' : ''}"><header><h3>${esc(spec.title)}</h3>${spec.close === false ? '' : '<button type="button" class="pr-x" data-pr="cancel" aria-label="Закрыть">×</button>'}</header>`
      + `<div class="pr-body">${spec.body}</div>${spec.hint ? `<div class="pr-hint">${esc(spec.hint)}</div>` : ''}<footer>${acts}</footer>${msg.timeout ? `<div class="pr-tbar"><i style="animation-duration:${msg.timeout}s"></i></div>` : ''}<div class="pr-toast" role="status"></div></div>`;
    document.body.appendChild(root);
    if (window.fzFields) window.fzFields.watch(root);
    if (window.fzDropdown) window.fzDropdown.watch(root);
    root.addEventListener('click', onClick); document.addEventListener('keydown', onKey, true);
    shownId = msg.id; shownKind = msg.kind;
    const f = root.querySelector(spec.focus || 'input'); if (f) setTimeout(() => f.focus(), 40);
  }
  function confirm() {
    const k = KINDS[shownKind]; if (!k) return;
    const v = k.collect(root, m.prompt && m.prompt.data); if (v === undefined) return;
    answer('ok', v);
  }
  function onClick(e) {
    const b = e.target.closest('[data-pr]'); if (b) { if (b.dataset.pr === 'ok') confirm(); else if (b.dataset.pr === 'cancel') answer('cancel'); else { const k0 = KINDS[shownKind]; if (k0 && k0.click) k0.click(e, root, m.prompt && m.prompt.data, answer); } return; }
    const k = KINDS[shownKind]; if (k && k.click) k.click(e, root, m.prompt && m.prompt.data, answer);
  }
  function onKey(e) {
    if (!root) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); answer('cancel'); }
    else if (e.key === 'Enter' && !e.shiftKey && e.target.matches('input') && e.target.id !== 'pr-q' && !(KINDS[shownKind] && KINDS[shownKind].noEnter)) { e.preventDefault(); confirm(); }
  }

  function paint() {
    const msg = m.prompt;
    if (!msg || !msg.open || !m.connected) { if (root && (!msg || msg.id === shownId || !msg.open)) close(); return; }
    const k = KINDS[msg.kind]; if (!k) return;
    if (root && msg.id === shownId && k.update) { k.update(root, msg.data); return; }
    if (root && msg.id === shownId) return;
    shell(msg, k.render(msg.data));
  }

  // ---- a line of text, optionally with a folder and a file type ----
  KINDS.text = {
    render: (d) => {
      const path = d.path !== null ? `<label class="pr-l">Папка<div class="pr-row"><input id="pr-path" maxlength="600" value="${esc(d.path)}" autocomplete="off"><button type="button" class="cm-try" data-act="browse">Выбрать…</button></div></label>`
        + (d.quick.length ? `<div class="tl-chips pr-quick">${d.quick.map((q) => `<button type="button" class="ci-pre" data-act="quick" data-path="${esc(q.path)}">${esc(q.label)}</button>`).join('')}</div>` : '') : '';
      const ext = d.with_ext ? `<label class="pr-l">Тип файла<select id="pr-ext">${d.exts.map((x) => `<option value="${esc(x.ext)}"${x.ext === d.ext ? ' selected' : ''}>${esc(x.label)}</option>`).join('')}</select></label>` : '';
      return { title: d.header || d.title, body: `${path}<label class="pr-l">${d.with_ext ? 'Имя без расширения' : (d.path !== null ? 'Имя' : 'Текст')}<input id="pr-text" maxlength="300" placeholder="${esc(d.placeholder)}" value="${esc(d.value)}" autocomplete="off"></label>${ext}`,
        hint: d.hint, actions: [{ id: 'cancel', label: d.cancel || 'Отмена' }, { id: 'ok', label: d.ok || 'ОК', primary: true }], focus: '#pr-text' };
    },
    collect: (r, d) => {
      const text = r.querySelector('#pr-text').value.trim();
      if (!text && (d.require || d.with_ext)) { window.PR.toast('Введите значение'); return undefined; }
      return { text, path: r.querySelector('#pr-path') ? r.querySelector('#pr-path').value : '', ext: r.querySelector('#pr-ext') ? r.querySelector('#pr-ext').value : '' };
    },
    click: async (e, r) => {
      const b = e.target.closest('[data-act]'); if (!b) return;
      if (b.dataset.act === 'quick') r.querySelector('#pr-path').value = b.dataset.path;
      else if (b.dataset.act === 'browse') { const x = await J.send('dev', { op: 'pick_folder' }); if (x && x.ok && root) r.querySelector('#pr-path').value = x.path; }
    },
  };

  // ---- which video to play ----
  KINDS.yt = {
    noEnter: true,
    list: (d) => d.items.map((c, i) => `<button type="button" class="pr-yt" data-pick="${i}"><span class="pr-yn">${i + 1}</span><span class="pr-yp"${c.thumb ? ` style="background-image:url('${c.thumb}')"` : ''}></span><b>${esc(c.title)}</b></button>`).join(''),
    render(d) { return { title: 'Какое видео включить?', body: `<div class="pr-yl">${this.list(d)}</div>`, hint: 'Нажмите на видео или скажите: первое, второе… Без ответа включится первое.', actions: [{ id: 'cancel', label: 'Отмена' }], wide: true, focus: '.pr-yt' }; },
    update(r, d) { const l = r.querySelector('.pr-yl'); if (l) l.innerHTML = this.list(d); },
    click: (e, r, d, answer) => { const b = e.target.closest('[data-pick]'); if (b) answer('ok', +b.dataset.pick); },
    collect: () => undefined,
  };

  // ---- a notice (the camera guard's alert) ----
  KINDS.notice = {
    render: (d) => ({ title: d.title, body: `${d.image ? `<img class="pr-img" alt="Снимок с камеры" src="${d.image}">` : ''}<p class="pr-p">${esc(d.text)}</p>`,
      actions: d.actions && d.actions.length ? d.actions.map((a) => ({ id: esc(a.id), label: esc(a.label), primary: !!a.primary })) : [{ id: 'ok', label: 'Понятно', primary: true, danger: d.tone === 'alert' }], close: false, focus: '[data-pr=ok]' }),
    collect: () => null,
    click: (e, root, d, answer) => { const b = e.target.closest('[data-pr]'); if (b && b.dataset.pr !== 'ok' && b.dataset.pr !== 'cancel') answer('ok', b.dataset.pr); },   // extra buttons (snooze) answer with their id
  };

  window.PR.paint = paint;   // repaint from the current model.prompt
  J.on('prompt', paint); J.on('conn', () => { if (!m.connected) close(); });
  J.on('prompt_cmd', () => { const c = m.promptCmd; if (!root || !c || c.id !== shownId) return; if (c.action === 'confirm') confirm(); else answer('cancel'); });
})();
