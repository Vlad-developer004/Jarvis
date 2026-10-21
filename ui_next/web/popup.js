// The pop-up window (popup.html): a small always-on-top window in the corner of the screen, so the assistant can tell the user something over any
// program and while the main window is in the tray. It shows (1) the answer card (answer.js, same code as before) and (2) the notices the core waits for:
// a reminder or a timer that is due, the camera guard. The shell (src-tauri/src/main.rs) shows and sizes the window from the height reported here
// and never gives it the keyboard focus. Relies on globals set in popup.html: J, $, m, esc.
(() => {
  const T = window.__TAURI__;
  if (!T) return;
  const core = T.core, root = document.documentElement;

  // ---- the colour theme of the main window (app.html stores {h, sk}; a change arrives as a storage event) ----
  const theme = () => { try { const t = JSON.parse(localStorage.getItem('jarvisHue') || 'null'); if (t && isFinite(t.h)) { root.style.setProperty('--h', t.h); root.style.setProperty('--sk', t.sk); } } catch (e) { /* the default look */ } };
  theme(); addEventListener('storage', (e) => { if (e.key === 'jarvisHue') theme(); });

  // ---- size the window to the cards: the body is as tall as the visible cards, none means the window is hidden ----
  let last = -1;
  const fit = () => {
    const h = Math.ceil(document.body.getBoundingClientRect().height);
    if (h === last) return;
    last = h;
    (h > 0 ? core.invoke('popup_fit', { height: h }) : core.invoke('popup_hide')).catch(() => {});
  };
  new ResizeObserver(fit).observe(document.body);

  // ---- a notice: the core opens it, the buttons answer it; a spoken "ок" / "отмена" arrives as prompt_cmd ----
  let card = null, shownId = 0;
  const build = () => { card = document.createElement('aside'); card.className = 'an pn'; card.setAttribute('role', 'alertdialog'); card.hidden = true; document.body.insertBefore(card, document.body.firstChild); card.addEventListener('click', onClick); };
  const answer = (status, value) => { const id = shownId; hide(); if (m.connected && id) J.send('prompt', { op: 'answer', id, status, value }); };
  function hide() { if (!card) return; card.classList.remove('in'); card.hidden = true; shownId = 0; }
  function onClick(e) {
    const b = e.target.closest('[data-pr]'); if (!b) return;
    if (b.dataset.pr === 'ok') answer('ok', null); else answer('ok', b.dataset.pr);   // an extra button (snooze) answers with its own id
  }
  function paint() {
    const p = m.prompt;
    if (!p || p.kind !== 'notice' || !p.open || !m.connected) { if (card && !card.hidden) hide(); return; }
    if (!card) build();
    if (p.id === shownId) return;
    shownId = p.id;
    const d = p.data || {}, acts = d.actions && d.actions.length ? d.actions : [{ id: 'ok', label: 'Понятно', primary: true }];
    card.classList.toggle('alert', d.tone === 'alert');
    card.innerHTML = `${d.image ? `<div class="an-pic" style="--src:url('${esc(d.image)}')"></div>` : ''}<div class="an-b"><h4 class="an-t">${esc(d.title || '')}</h4><div class="an-txt">${esc(d.text || '')}</div>`
      + `<div class="an-links">${acts.map((a) => `<button type="button" class="${a.primary ? 'primary' : ''}" data-pr="${esc(a.id)}">${esc(a.label)}</button>`).join('')}</div></div>`;
    card.hidden = false; requestAnimationFrame(() => card.classList.add('in'));
  }
  J.on('prompt', paint);
  J.on('conn', () => { if (!m.connected) hide(); });
  J.on('prompt_cmd', () => { const c = m.promptCmd; if (!card || card.hidden || !c || c.id !== shownId) return; if (c.action === 'confirm') answer('ok', null); else answer('cancel'); });
})();
