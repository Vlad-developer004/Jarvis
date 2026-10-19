// Mail screen, writing: the rich-text editor (bold, italic, underline, strike, size, colour, lists, quote, link, emoji, clear) used by the inline reply
// and by the new-message window, and that window itself: recipient chips with suggestions from the people in your mail, Cc/Bcc, subject, attachments,
// a draft saved when the window is closed (like Gmail), expand, discard. Loaded after mail.js; uses window.MailApp and window.MailX.
(() => {
  const A = window.MailApp; if (!A) return;
  const { S, call, say, esc, I, modal, mbox } = A;
  const SVG = (d, w = 1.9) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const IC = {
    bold: SVG('<path d="M7 5h6a3.5 3.5 0 0 1 0 7H7zM7 12h7a3.5 3.5 0 0 1 0 7H7z"/>', 2.3), italic: SVG('<path d="M10 5h8M6 19h8M14 5l-4 14"/>'), underline: SVG('<path d="M7 4v7a5 5 0 0 0 10 0V4M5 20h14"/>'),
    strike: SVG('<path d="M5 12h14M16 7a4 4 0 0 0-4-2c-2.5 0-4 1.2-4 3 0 4 8 2 8 6 0 1.800-1.700 3-4.200 3a5 5 0 0 1-4-2"/>'), ul: SVG('<path d="M9 6h11M9 12h11M9 18h11M4.500 6h.01M4.500 12h.01M4.500 18h.01" />', 2.2),
    ol: SVG('<path d="M10 6h10M10 12h10M10 18h10M4 5l1.500-1v4M4 13c0-1.500 2.500-1.500 2.500 0S4 15 4 16h2.500M4 18.500h2l-1 1.500c1 0 1.500.5 1.500 1.200S5.500 22 4 21.500"/>', 1.600),
    quote: SVG('<path d="M5 7h5v5H7a2 2 0 0 0 2 3M14 7h5v5h-3a2 2 0 0 0 2 3"/>'), link: SVG('<path d="M10 14a4 4 0 0 0 5.700 0l3-3a4 4 0 0 0-5.700-5.700l-1 1M14 10a4 4 0 0 0-5.700 0l-3 3a4 4 0 0 0 5.700 5.700l1-1"/>'),
    emoji: SVG('<circle cx="12" cy="12" r="8.500"/><path d="M8.500 14a4 4 0 0 0 7 0M9 9.500h.01M15 9.500h.01" />', 1.800), clear: SVG('<path d="M6 5h12M12 5l-3 14M5 19l14-14" />', 1.800),
    size: '<span class="rte-aa">Aa</span>', color: '<span class="rte-aa rte-col">A</span>', send: SVG('<path d="M4 12l16-8-6 16-3-7zM11 13l9-9"/>', 1.900),
    expand: SVG('<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7"/>', 1.800), close: SVG('<path d="M6 6l12 12M18 6L6 18"/>', 2.200), trash: I.trash, clip: I.clip,
  };
  const EMOJI = '😀 😁 😂 🤣 😊 😍 😘 😉 😎 🤔 😅 😢 😭 😡 👍 👎 👏 🙏 💪 🔥 ✨ 🎉 ❤️ 💔 ✅ ❌ ⭐ 📎 📅 ⏰ 📌 💡 👋 🙂 🙃 😴 🤝 👀 💬 📞 ✉️ 🚀 ☕ 🍀 🎯 📈 💼'.split(' ');
  const COLORS = ['#e8edf2', '#ff6b6b', '#ffa94d', '#ffd43b', '#51cf66', '#22d3ee', '#4c8dff', '#b197fc', '#f783ac', '#9aa7b5'];
  const SIZES = [['Мелкий', 2], ['Обычный', 3], ['Крупный', 5], ['Огромный', 6]];
  const MAIL_RE = /^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/;
  const plainToHtml = (t) => esc(t || '').replace(/\r?\n/g, '<br>');

  // ---- editor ----
  function mount(host, o = {}) {
    const btn = (cmd, icon, title, extra = '') => `<button type="button" class="rte-b${extra}" data-c="${cmd}" title="${title}" aria-label="${title}">${icon}</button>`;
    host.innerHTML = `<div class="rte${o.compact ? ' sm' : ''}"><div class="rte-ed" contenteditable="true" role="textbox" aria-multiline="true" aria-label="${esc(o.label || 'Текст письма')}" data-ph="${esc(o.placeholder || '')}"></div>
      <div class="rte-bar">${btn('size', IC.size, 'Размер текста')}${btn('bold', IC.bold, 'Жирный (Ctrl+B)')}${btn('italic', IC.italic, 'Курсив (Ctrl+I)')}${btn('underline', IC.underline, 'Подчёркнутый (Ctrl+U)')}${btn('strikeThrough', IC.strike, 'Зачёркнутый')}${btn('color', IC.color, 'Цвет текста')}<i class="rte-sep"></i>
        ${btn('insertUnorderedList', IC.ul, 'Маркированный список')}${btn('insertOrderedList', IC.ol, 'Нумерованный список')}${btn('quote', IC.quote, 'Цитата')}<i class="rte-sep"></i>${btn('link', IC.link, 'Ссылка')}${btn('emoji', IC.emoji, 'Эмодзи')}${btn('removeFormat', IC.clear, 'Убрать форматирование')}</div></div>`;
    const root = host.querySelector('.rte'), ed = host.querySelector('.rte-ed'), bar = host.querySelector('.rte-bar');
    let range = null, pop = null;
    try { document.execCommand('styleWithCSS', false, false); } catch (e) { /* older engines */ }
    if (o.html) ed.innerHTML = o.html;
    const saveRange = () => { const s = getSelection(); if (s.rangeCount && ed.contains(s.anchorNode)) range = s.getRangeAt(0).cloneRange(); };
    const restore = () => { ed.focus(); if (range) { const s = getSelection(); s.removeAllRanges(); s.addRange(range); } };
    const closePop = () => { if (pop) { pop.remove(); pop = null; } };
    const exec = (cmd, val) => { restore(); document.execCommand(cmd, false, val); saveRange(); mark(); };
    const mark = () => { for (const b of bar.querySelectorAll('[data-c]')) { const c = b.dataset.c; if (['bold', 'italic', 'underline', 'strikeThrough', 'insertUnorderedList', 'insertOrderedList'].includes(c)) { let on = false; try { on = document.queryCommandState(c); } catch (e) { /* no state */ } b.classList.toggle('on', on); } } };
    const popup = (anchor, html) => {
      closePop(); pop = document.createElement('div'); pop.className = 'rte-pop'; pop.innerHTML = html; root.appendChild(pop);
      const r = anchor.getBoundingClientRect(), b = root.getBoundingClientRect(); pop.style.left = `${Math.max(0, Math.min(r.left - b.left, b.width - pop.offsetWidth))}px`; pop.style.bottom = `${b.bottom - r.top + 6}px`;
      return pop;
    };
    ed.addEventListener('input', () => { if (ed.innerHTML === '<br>') ed.innerHTML = ''; });
    ed.addEventListener('keyup', () => { saveRange(); mark(); }); ed.addEventListener('mouseup', () => { saveRange(); mark(); }); ed.addEventListener('blur', saveRange);
    ed.addEventListener('paste', (e) => { e.preventDefault(); const t = (e.clipboardData || window.clipboardData).getData('text/plain'); document.execCommand('insertText', false, t); });
    ed.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && o.onSubmit) { e.preventDefault(); o.onSubmit(); } });
    bar.addEventListener('mousedown', (e) => { if (!e.target.closest('input')) e.preventDefault(); });
    root.addEventListener('mousedown', (e) => { if (pop && !e.target.closest('.rte-pop') && !e.target.closest('.rte-b')) closePop(); });
    root.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pop) { e.stopPropagation(); closePop(); ed.focus(); } });
    bar.addEventListener('click', (e) => {
      const b = e.target.closest('[data-c]'); if (!b) return; const c = b.dataset.c; saveRange();
      if (c === 'size') popup(b, `<div class="rte-list">${SIZES.map(([t, v]) => `<button type="button" class="rte-li" data-size="${v}">${t}</button>`).join('')}</div>`);
      else if (c === 'color') popup(b, `<div class="rte-sw">${COLORS.map((x) => `<button type="button" class="rte-s" data-color="${x}" style="--c:${x}" aria-label="${x}"></button>`).join('')}</div>`);
      else if (c === 'emoji') popup(b, `<div class="rte-em">${EMOJI.map((x) => `<button type="button" data-emoji="${x}">${x}</button>`).join('')}</div>`);
      else if (c === 'link') {
        const p = popup(b, '<div class="rte-ln"><input type="text" data-fld="1" placeholder="https://…" aria-label="Адрес ссылки"><button type="button" class="cm-try primary" data-go>Вставить</button></div>');
        const inp = p.querySelector('input'); inp.focus();
        const go = () => {
          let u = inp.value.trim(); if (!u) return; if (!/^(https?:|mailto:)/i.test(u)) u = MAIL_RE.test(u) ? `mailto:${u}` : `https://${u}`;
          closePop(); restore();
          if (getSelection().isCollapsed) document.execCommand('insertHTML', false, `<a href="${esc(u)}">${esc(u.replace(/^mailto:/, ''))}</a>`); else document.execCommand('createLink', false, u);
          saveRange();
        };
        p.querySelector('[data-go]').onclick = go; inp.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); go(); } });
      } else if (c === 'quote') { restore(); let v = ''; try { v = String(document.queryCommandValue('formatBlock')).toLowerCase(); } catch (er) { /* none */ } document.execCommand('formatBlock', false, v === 'blockquote' ? 'div' : 'blockquote'); saveRange(); }
      else exec(c);
    });
    root.addEventListener('click', (e) => {
      const z = e.target.closest('[data-size]'), k = e.target.closest('[data-color]'), em = e.target.closest('[data-emoji]');
      if (z) { closePop(); exec('fontSize', z.dataset.size); } else if (k) { closePop(); exec('foreColor', k.dataset.color); } else if (em) { closePop(); exec('insertText', em.dataset.emoji); }
    });
    return {
      el: ed, focus: () => ed.focus(), html: () => ed.innerHTML.replace(/(<br>)+$/, '').trim(), text: () => ed.innerText.replace(/ /g, ' '),
      isEmpty: () => !ed.innerText.trim(), setText: (t) => { ed.innerHTML = plainToHtml(t); },
    };
  }

  // ---- new-message window ----
  let comp = null, ed = null, sugIdx = -1;
  const KEYS = ['to', 'cc', 'bcc'], NAMES = { to: 'Кому', cc: 'Копия', bcc: 'Скрытая' };
  const parse = (s) => String(s || '').split(/[\s,;]+/).filter((x) => MAIL_RE.test(x));
  const contacts = () => { const m2 = new Map(); for (const r of S.rows) if (r.addr && !m2.has(r.addr.toLowerCase())) m2.set(r.addr.toLowerCase(), r.name || r.addr); return [...m2].map(([addr, name]) => ({ addr, name })); };
  const chip = (a, i, k) => `<span class="mc-chip"><i style="--gh:${[...a].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 0)}">${esc(a[0].toUpperCase())}</i>${esc(a)}<button type="button" data-rm="${k}:${i}" aria-label="Убрать ${esc(a)}">×</button></span>`;
  const dirty = () => comp && (KEYS.some((k) => comp[k].length) || $('mc-subj').value.trim() || !ed.isEmpty() || comp.attach.length);

  function open(init = {}) {
    comp = { to: parse(init.to), cc: parse(init.cc), bcc: [], attach: [], sending: false, replace: init.replace || '', quote: init.quote || null, max: false, showCc: !!init.cc, showBcc: false, title: init.title || 'Новое сообщение' };
    modal.hidden = false; render(init);
    setTimeout(() => { if (!comp.to.length) $('mc-ti-to').focus(); else if (!$('mc-subj').value) $('mc-subj').focus(); else ed.focus(); }, 40);
  }
  function render(init) {
    const row = (k) => `<div class="mc-row" id="mc-r-${k}"${k !== 'to' && !comp[k === 'cc' ? 'showCc' : 'showBcc'] ? ' hidden' : ''}><label for="mc-ti-${k}">${NAMES[k]}</label><div class="mc-box" id="mc-${k}"><span class="mc-cs"></span><input data-fld="1" id="mc-ti-${k}" data-k="${k}" type="text" autocomplete="off" spellcheck="false" aria-label="${NAMES[k]}"></div>
      ${k === 'to' ? '<span class="mc-more"><button type="button" data-show="cc">Копия</button><button type="button" data-show="bcc">Скрытая</button></span>' : ''}</div>`;
    mbox.className = ''; mbox.id = 'ml-mbox';
    mbox.innerHTML = `<div class="mc-head"><b>${esc(/^fwd:/i.test(init.subject || '') ? 'Пересылка' : comp.title)}</b><span class="ml-sp"></span><button type="button" class="mc-ib" data-mc="max" title="Развернуть" aria-label="Развернуть">${IC.expand}</button><button type="button" class="mc-ib" data-mc="close" title="Закрыть (письмо сохранится в черновики)" aria-label="Закрыть">${IC.close}</button></div>
      <div class="mc-rows">${row('to')}${row('cc')}${row('bcc')}<div class="mc-row"><label for="mc-subj">Тема</label><div class="mc-box"><input data-fld="1" id="mc-subj" type="text" autocomplete="off" aria-label="Тема" value="${esc(init.subject || '')}"></div></div><div class="mc-sug" id="mc-sug" hidden></div></div>
      <div class="mc-ed" id="mc-ed"></div>${comp.quote ? '<div class="ml-qc mc-qn"><span>Исходное письмо будет вставлено ниже, с оформлением</span></div>' : ''}<div id="mc-att"></div><div class="xs-err" id="mc-err" role="alert"></div>
      <div class="mc-foot"><button type="button" class="cm-try primary mc-send" id="mc-send">${IC.send}<span>Отправить</span></button><button type="button" class="mc-ib lg" data-mc="attach" title="Прикрепить файлы" aria-label="Прикрепить файлы">${IC.clip}</button><span class="mc-hint">Ctrl+Enter</span><span class="ml-sp"></span><button type="button" class="mc-ib lg" data-mc="discard" title="Удалить письмо" aria-label="Удалить письмо">${IC.trash}</button></div>`;
    ed = mount($('mc-ed'), { html: init.body ? plainToHtml(init.body) : '', placeholder: 'Текст письма', onSubmit: send });
    for (const k of KEYS) paintChips(k);
  }
  function paintChips(k) { const box = $(`mc-${k}`); if (box) box.querySelector('.mc-cs').innerHTML = comp[k].map((a, i) => chip(a, i, k)).join(''); }
  const paintAttach = () => { $('mc-att').innerHTML = A.attachHtml(comp.attach); };

  function commit(k, text) {
    const bad = [];
    for (const t of String(text || '').split(/[\s,;]+/).filter(Boolean)) { const a = (t.match(/<([^<>]+)>/) || [, t])[1]; if (MAIL_RE.test(a)) { if (!comp[k].some((x) => x.toLowerCase() === a.toLowerCase())) comp[k].push(a); } else bad.push(t); }
    paintChips(k); return bad.join(' ');
  }
  function suggest(k, q) {
    const sug = $('mc-sug'); q = q.trim().toLowerCase(); sugIdx = -1;
    const list = q ? contacts().filter((c) => !comp[k].some((x) => x.toLowerCase() === c.addr) && (c.addr.includes(q) || c.name.toLowerCase().includes(q))).slice(0, 5) : [];
    sug.hidden = !list.length; sug.dataset.k = k;
    sug.innerHTML = list.map((c, i) => `<button type="button" class="mc-sg" data-i="${i}" data-addr="${esc(c.addr)}"><i style="--gh:${[...c.addr].reduce((h, ch) => (h * 31 + ch.charCodeAt(0)) % 360, 0)}">${esc((c.name || c.addr)[0].toUpperCase())}</i><b>${esc(c.name)}</b><small>${esc(c.addr)}</small></button>`).join('');
    const box = $(`mc-r-${k}`); if (box && list.length) sug.style.top = `${box.offsetTop + box.offsetHeight}px`;
  }
  const pickSug = (k, addr) => { const i = $(`mc-ti-${k}`); commit(k, addr); i.value = ''; $('mc-sug').hidden = true; i.focus(); };

  mbox.addEventListener('input', (e) => { const i = e.target.closest('[data-k]'); if (i) suggest(i.dataset.k, i.value); });
  mbox.addEventListener('keydown', (e) => {
    const i = e.target.closest('[data-k]'); if (!i) return; const k = i.dataset.k, sug = $('mc-sug'), items = [...sug.querySelectorAll('.mc-sg')];
    if (!sug.hidden && items.length && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) { e.preventDefault(); sugIdx = (sugIdx + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; items.forEach((x, n) => x.classList.toggle('on', n === sugIdx)); return; }
    if ((e.key === 'Enter' || e.key === 'Tab') && sugIdx >= 0 && !sug.hidden) { e.preventDefault(); pickSug(k, items[sugIdx].dataset.addr); return; }
    if (['Enter', ',', ';', ' '].includes(e.key) || (e.key === 'Tab' && i.value.trim())) { if (i.value.trim()) { e.preventDefault(); const bad = commit(k, i.value); i.value = bad; i.classList.toggle('bad', !!bad); sug.hidden = true; } else if (e.key === 'Enter') e.preventDefault(); }
    else if (e.key === 'Backspace' && !i.value && comp[k].length) { comp[k].pop(); paintChips(k); }
  });
  mbox.addEventListener('focusout', (e) => { const i = e.target.closest && e.target.closest('[data-k]'); if (i && i.value.trim()) { const bad = commit(i.dataset.k, i.value); i.value = bad; i.classList.toggle('bad', !!bad); } });
  mbox.addEventListener('paste', (e) => { const i = e.target.closest && e.target.closest('[data-k]'); if (!i) return; e.preventDefault(); const bad = commit(i.dataset.k, (e.clipboardData || window.clipboardData).getData('text/plain')); i.value = bad; });

  mbox.addEventListener('click', async (e) => {
    const t = e.target, sg = t.closest('.mc-sg'); if (sg) { pickSug($('mc-sug').dataset.k, sg.dataset.addr); return; }
    const rm = t.closest('[data-rm]'); if (rm) { const [k, n] = rm.dataset.rm.split(':'); comp[k].splice(+n, 1); paintChips(k); return; }
    const sh = t.closest('[data-show]'); if (sh) { const k = sh.dataset.show; comp[k === 'cc' ? 'showCc' : 'showBcc'] = true; $(`mc-r-${k}`).hidden = false; $(`mc-ti-${k}`).focus(); return; }
    const dr = t.closest('[data-drop]'); if (dr) { e.stopPropagation(); await A.dropAttach(dr.dataset.drop, comp.attach); paintAttach(); return; }
    const b = t.closest('[data-mc]'); if (b) {
      const a = b.dataset.mc;
      if (a === 'max') { comp.max = !comp.max; mbox.classList.toggle('max', comp.max); }
      else if (a === 'close') close(true);
      else if (a === 'attach') { await A.pick(comp.attach); paintAttach(); }
      else if (a === 'discard') discard();
      return;
    }
    if (t.closest('#mc-send')) send();
  });
  modal.addEventListener('mousedown', (e) => { if (e.target === modal && comp) close(true); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && comp && !modal.hidden && !document.querySelector('.dd-pop, .ml-dlg, .rte-pop')) close(true); });

  function values() {
    for (const k of KEYS) { const i = $(`mc-ti-${k}`); if (i && i.value.trim()) { const bad = commit(k, i.value); i.value = bad; } }
    return { to: comp.to.join(', '), cc: comp.cc.join(', '), bcc: comp.bcc.join(', '), subject: $('mc-subj').value, body: ed.text().replace(/\n{3,}/g, '\n\n').trim(), html: ed.html() };
  }
  async function send() {
    if (!comp || comp.sending) return;
    const v = values(), err = $('mc-err');
    if (!comp.to.length) { err.textContent = 'Укажите получателя: адрес вида name@example.com'; $('mc-ti-to').focus(); return; }
    if (!v.body && !comp.attach.length && !comp.quote) { err.textContent = 'Введите текст письма или добавьте вложение'; ed.focus(); return; }
    err.textContent = ''; comp.sending = true; const sb = $('mc-send'); sb.disabled = true; sb.querySelector('span').textContent = 'Отправляю…';
    await A.sendMail({ ...v, quote: comp.quote, replace: comp.replace, attach: comp.attach.map((x) => x.id) }, (ok) => {
      if (ok) { comp.attach = []; close(false); } else { comp.sending = false; if ($('mc-send')) { sb.disabled = false; sb.querySelector('span').textContent = 'Отправить'; } }
    });
  }
  async function close(save) {
    if (!comp) return;
    const c = comp, v = values(), has = dirty();
    if (save && has && S.folders.includes('drafts')) {
      if (!m.connected) say('Демо: черновик не сохраняется');
      else {
        const r = await call({ op: 'draft', to: v.to, cc: v.cc, bcc: v.bcc, subject: v.subject, body: v.body, html: v.html, replace: c.replace, attach: c.attach.map((x) => x.id) });
        if (r.ok) { say('Сохранено в черновики'); c.attach = []; if (S.folder === 'drafts') A.loadList({ silent: true, refresh: true }); } else { say(r.message || 'Не удалось сохранить черновик'); return; }
      }
    }
    for (const x of c.attach) if (m.connected) call({ op: 'drop', id: x.id });
    comp = null; ed = null; modal.hidden = true; mbox.classList.remove('max');
  }
  function discard() {
    const gone = () => { for (const x of comp.attach) if (m.connected) call({ op: 'drop', id: x.id }); const old = comp.replace; comp = null; ed = null; modal.hidden = true; mbox.classList.remove('max'); if (old && m.connected) call({ op: 'remove', folder: 'drafts', uids: [old], to: '' }); };
    if (!dirty()) { gone(); return; }
    window.MailX.dlg({ title: 'Удалить письмо?', body: 'Написанное не сохранится.', ok: 'Удалить', danger: true, onOk: gone });
  }

  window.MailC = { mount, open };
})();
