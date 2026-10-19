// Timers and reminders screen. Data: the `timers` topic from the core; commands `timer` and `reminder` (ui_next/bridge).
// Without a core it shows a local demo so the layout can be reviewed. Relies on globals of app.html: $, J, m, ic, C, esc, VIEW, setBadge.
(() => {
  const TIMER_PRESETS = [60, 300, 600, 900, 1800, 3600];
  const REM_PRESETS = [300, 900, 1800, 3600, 7200];
  const demo = { timer: { label: 'Чай', total: 600, end: Date.now() + 372000 }, rems: [{ id: 1, text: 'Позвонить маме', at: Date.now() + 25 * 60000 }, { id: 2, text: 'Выпить воды', at: Date.now() + 80 * 60000 }], seq: 3 };
  let tm = null, rems = [], remSec = 900, tick = 0, toastTimer = 0;
  const tbox = $('rm-timer'), list = $('rm-list'), toast = $('rm-toast'), rtext = $('rm-text'), rerr = $('rm-err'), rchips = $('rm-chips'), rcustom = $('rm-custom');

  const pad = (n) => String(n).padStart(2, '0');
  const clock = (s) => { s = Math.max(0, Math.round(s)); const h = Math.floor(s / 3600), mi = Math.floor(s % 3600 / 60); return (h ? h + ':' + pad(mi) : pad(mi)) + ':' + pad(s % 60); };
  const dur = (s) => { const h = Math.floor(s / 3600), mi = Math.round(s % 3600 / 60); return h && mi ? `${h} ч ${mi} мин` : h ? `${h} ч` : `${Math.max(1, mi)} мин`; };
  const at = (ts) => { const d = new Date(ts); return pad(d.getHours()) + ':' + pad(d.getMinutes()); };
  const left = (ts) => { const s = (ts - Date.now()) / 1000; return s < 60 ? 'меньше минуты' : 'через ' + dur(s); };

  function read() {
    if (m.connected) {
      const t = m.timers || {};
      return { timer: t.timer ? { label: t.timer.label, total: t.timer.total, end: (m.timersAt || Date.now()) + t.timer.remaining * 1000 } : null, rems: t.reminders || [] };
    }
    return { timer: demo.timer && demo.timer.end > Date.now() ? demo.timer : null, rems: demo.rems.filter((r) => r.at > Date.now()) };
  }

  function say(text) { toast.textContent = text; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3000); }

  async function act(cmd, data, okText) {
    if (!m.connected) {   // demo without a core
      if (cmd === 'timer') {
        if (data.op === 'cancel') demo.timer = null;
        else if (data.op === 'sub' && demo.timer) { demo.timer.end -= data.seconds * 1000; demo.timer.total -= data.seconds; }
        else if (data.op === 'add' && demo.timer) { demo.timer.end += data.seconds * 1000; demo.timer.total += data.seconds; }
        else demo.timer = { label: data.label || '', total: data.seconds, end: Date.now() + data.seconds * 1000 };
      } else if (data.op === 'cancel') demo.rems = demo.rems.filter((r) => r.id !== data.id);
      else demo.rems.push({ id: demo.seq++, text: data.text, at: Date.now() + data.seconds * 1000 });
      say(okText); render(); return true;
    }
    const r = await J.send(cmd, data);
    if (r && r.ok) { say(okText); return true; }
    say(r ? 'Не получилось: действие отклонено' : 'Jarvis не ответил — проверьте, что он запущен'); return false;
  }

  const X = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M5 5l14 14M19 5L5 19"/></svg>';

  function renderTimer() {
    if (!tm) {
      tbox.innerHTML = `<h3>${ic('timer', C.amber, 18)}Таймер</h3><div class="rm-lbl">Нажмите на время, и таймер запустится сразу</div>
        <div class="rm-chips">${TIMER_PRESETS.map((s) => `<button class="rm-chip" data-ts="${s}">${dur(s)}</button>`).join('')}</div>
        <div class="rm-row"><input class="rm-in num" id="rm-tmin" type="number" min="1" max="1440" inputmode="numeric" placeholder="мин" aria-label="Минуты"><input class="rm-in grow" id="rm-tlbl" type="text" maxlength="60" placeholder="Название таймера" aria-label="Название таймера"><button class="cm-try primary" id="rm-tgo">Запустить</button></div>`;
      window.fzStepper && window.fzStepper.enhance(tbox);
      return;
    }
    tbox.innerHTML = `<h3>${ic('timer', C.amber, 18)}Таймер</h3><div class="rm-clock" id="rm-tclock"></div><div class="rm-bar"><i id="rm-tbar"></i></div><div class="rm-sub" id="rm-tsub"></div>
      <div class="rm-row"><button class="rm-chip" data-add="-300">−5 мин</button><button class="rm-chip" data-add="-60">−1 мин</button><button class="rm-chip" data-add="60">+1 мин</button><button class="rm-chip" data-add="300">+5 мин</button><button class="cm-try danger" id="rm-tcancel" style="margin-left:auto">Отменить</button></div>`;
    paintClock();
  }

  function paintClock() {
    const c = $('rm-tclock'); if (!c || !tm) return;
    const s = Math.max(0, (tm.end - Date.now()) / 1000);
    c.textContent = clock(s); c.classList.toggle('low', s <= 60);
    $('rm-tbar').style.width = (tm.total ? Math.min(100, Math.max(0, (1 - s / tm.total) * 100)) : 0) + '%';
    $('rm-tsub').innerHTML = `${tm.label ? `<b>${esc(tm.label)}</b> · ` : ''}всего ${dur(tm.total)}, сработает в <b>${at(tm.end)}</b>`;
  }

  function renderList() {
    $('rm-count').textContent = rems.length ? 'в очереди: ' + rems.length : '';
    list.innerHTML = rems.length ? rems.map((r) => `<div class="rm-item"><div><b>${esc(r.text)}</b><small>в ${at(r.at)} · <span data-left="${esc(r.at)}">${left(r.at)}</span></small></div><button class="rm-x" data-cancel="${esc(r.id)}" aria-label="Отменить напоминание" title="Отменить">${X}</button></div>`).join('')
      : '<div class="rm-empty"><b>Напоминаний нет</b>Добавьте слева или скажите: «напомни через десять минут позвонить».</div>';
  }

  function render() {
    const s = read(); tm = s.timer; rems = s.rems;
    if (m.connected) setBadge('Напоминания', rems.length);
    if (VIEW !== 'rems') return;
    renderTimer(); renderList();
    clearInterval(tick);
    tick = setInterval(() => {
      if (VIEW !== 'rems') { clearInterval(tick); return; }
      if (!m.connected) { const d = read(); if (!!d.timer !== !!tm || d.rems.length !== rems.length) { render(); return; } }
      paintClock(); list.querySelectorAll('[data-left]').forEach((e) => { e.textContent = left(+e.dataset.left); });
    }, 1000);
  }

  // ---- reminder form ----
  const remChips = () => { rchips.innerHTML = REM_PRESETS.map((s) => `<button class="rm-chip${s === remSec && !rcustom.value ? ' on' : ''}" data-rs="${s}">${dur(s)}</button>`).join(''); };
  rchips.addEventListener('click', (e) => { const b = e.target.closest('[data-rs]'); if (!b) return; remSec = +b.dataset.rs; rcustom.value = ''; remChips(); });
  rcustom.addEventListener('input', remChips);
  async function addReminder() {
    const text = rtext.value.trim();
    const seconds = rcustom.value ? parseInt(rcustom.value, 10) * 60 : remSec;
    rtext.classList.remove('bad'); rerr.textContent = '';
    if (!text) { rtext.classList.add('bad'); rerr.textContent = 'Напишите, о чём напомнить'; rtext.focus(); return; }
    if (!(seconds >= 60 && seconds <= 86400)) { rerr.textContent = 'Время: от 1 минуты до 24 часов'; rcustom.focus(); return; }
    if (await act('reminder', { op: 'add', text, seconds }, 'Напоминание поставлено: ' + left(Date.now() + seconds * 1000))) { rtext.value = ''; rcustom.value = ''; remChips(); }
  }
  $('rm-radd').onclick = addReminder;
  rtext.addEventListener('keydown', (e) => { if (e.key === 'Enter') addReminder(); });
  rtext.addEventListener('input', () => { rtext.classList.remove('bad'); rerr.textContent = ''; });

  // ---- timer and list clicks ----
  function startCustom() {
    const mi = parseInt($('rm-tmin').value, 10);
    if (!(mi >= 1 && mi <= 1440)) { $('rm-tmin').classList.add('bad'); $('rm-tmin').focus(); return; }
    act('timer', { op: 'start', seconds: mi * 60, label: $('rm-tlbl').value.trim() }, 'Таймер на ' + dur(mi * 60) + ' запущен');
  }
  tbox.addEventListener('click', (e) => {
    const p = e.target.closest('[data-ts]'); if (p) { act('timer', { op: 'start', seconds: +p.dataset.ts }, 'Таймер на ' + dur(+p.dataset.ts) + ' запущен'); return; }
    const a = e.target.closest('[data-add]'); if (a) { const d = +a.dataset.add; if (d < 0 && tm && (tm.end - Date.now()) / 1000 <= -d) { say('На таймере осталось меньше. Отмените его, если он не нужен'); return; } act('timer', { op: d < 0 ? 'sub' : 'add', seconds: Math.abs(d) }, (d < 0 ? 'Убавлено ' : 'Добавлено ') + dur(Math.abs(d))); return; }
    if (e.target.closest('#rm-tcancel')) { act('timer', { op: 'cancel' }, 'Таймер отменён'); return; }
    if (e.target.closest('#rm-tgo')) startCustom();
  });
  tbox.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.closest('.rm-in')) startCustom(); });
  tbox.addEventListener('input', (e) => e.target.classList.remove('bad'));
  list.addEventListener('click', (e) => { const x = e.target.closest('[data-cancel]'); if (x) act('reminder', { op: 'cancel', id: +x.dataset.cancel }, 'Напоминание отменено'); });

  J.on('timers', () => { m.timersAt = Date.now(); render(); });
  J.on('live', render);
  document.querySelectorAll('#rems [data-ic]').forEach((e) => { e.outerHTML = ic(e.dataset.ic, C.amber, 18); });
  remChips();
  window.renderRems = render;
})();
