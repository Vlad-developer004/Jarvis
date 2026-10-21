// Answer card: what Jarvis answers to a question (streaming text, a picture of the subject), the picture of the day, a recognised song.
// Data: the `answer` topic from the core (ui_next/bridge/answer.py). The core closes the card by itself after the speech and a reading pause; the cross dismisses it at once.
// It is the new window's version of the old HUD's small answer window and replaces it while this window is connected. Relies on globals of app.html: $, J, m, esc, ic.
(() => {
  let el = null, shownId = -1, dismissed = -1, stick = true;
  // The model delivers text in uneven pieces; the card reveals it at an even pace (CPS characters a second, faster while a backlog builds up so it never lags more than CATCH seconds).
  const CPS = 55, CATCH = 1.2;
  let target = '', shown = 0, acc = 0, last = 0, raf = 0;
  const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

  function build() {
    el = document.createElement('aside'); el.className = 'an'; el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite'); el.hidden = true;
    el.innerHTML = '<button type="button" class="an-x" aria-label="Закрыть ответ">×</button><div class="an-pic" hidden></div><div class="an-b"><h4 class="an-t"></h4><div class="an-txt"></div><div class="an-links" hidden></div><small class="an-vid" hidden>К ответу прилагается видео, оно показывается в старом окне.</small></div>';
    document.body.appendChild(el);
    el.querySelector('.an-x').addEventListener('click', () => { dismissed = shownId; paint(); if (m.connected) J.send('answer', { op: 'close' }); });
    el.querySelector('.an-links').addEventListener('click', (e) => { const b = e.target.closest('[data-url]'); if (b && m.connected) J.send('open_url', { url: b.dataset.url }); });
    const t = el.querySelector('.an-txt'); t.addEventListener('scroll', () => { stick = t.scrollTop + t.clientHeight >= t.scrollHeight - 12; });
  }

  function reveal(t, text) {
    if (text === target) return;
    const grows = text.startsWith(target.slice(0, shown));
    target = text;
    if (!grows || still()) shown = target.length;
    if (shown >= target.length) { cancelAnimationFrame(raf); raf = 0; t.textContent = target; if (stick) t.scrollTop = t.scrollHeight; return; }
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(function frame(now) {
      const dt = Math.min(0.25, (now - last) / 1000); last = now;
      acc += Math.max(CPS * dt, (target.length - shown) * dt / CATCH); const n = Math.floor(acc); acc -= n; shown = Math.min(target.length, shown + n);
      t.textContent = target.slice(0, shown); if (stick) t.scrollTop = t.scrollHeight;
      raf = shown < target.length ? requestAnimationFrame(frame) : 0;
    }); }
  }

  function paint() {
    const a = m.answer; if (!el) build();
    const on = !!(a && a.visible && a.id !== dismissed && m.connected) && (!window.__TAURI__ || !!window.__POPUP__);   // in the shell the pop-up window shows it, over any program
    if (!on) { if (!el.hidden) { el.classList.remove('in'); el.hidden = true; } return; }
    if (a.id !== shownId) { shownId = a.id; stick = true; target = ''; shown = 0; acc = 0; el.querySelector('.an-txt').scrollTop = 0; }
    el.querySelector('.an-t').textContent = a.subject || 'J.A.R.V.I.S.';
    const pic = el.querySelector('.an-pic');
    if (a.image) { if (pic.dataset.src !== a.image) { pic.dataset.src = a.image; pic.style.setProperty('--src', `url("${a.image}")`); } pic.hidden = false; } else { pic.hidden = true; pic.dataset.src = ''; pic.style.removeProperty('--src'); }
    el.querySelector('.an-vid').hidden = !a.video;
    const ln = el.querySelector('.an-links'), links = a.links || [], key = JSON.stringify(links);
    if (ln.dataset.k !== key) { ln.dataset.k = key; ln.innerHTML = links.map((x) => `<button type="button" data-url="${esc(x.url)}">${esc(x.label)}</button>`).join(''); }
    ln.hidden = !links.length;
    const t = el.querySelector('.an-txt'); reveal(t, a.text || '');
    t.hidden = !a.text;
    if (el.hidden) { el.hidden = false; requestAnimationFrame(() => el.classList.add('in')); }
  }

  window.AN = { paint };   // repaint from the current model.answer (used by the topic handler below)
  J.on('answer', paint);
  J.on('conn', () => { if (el && !m.connected) paint(); });
})();
