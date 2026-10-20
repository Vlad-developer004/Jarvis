// Appearance screen: colour theme (ready-made, own colour, by time of day), interface size, effects and sounds, and which panels the overview shows.
// Everything is kept in this window's localStorage through window.LOOK (look_boot.js) and applies at once; a theme change reloads the page and returns to this screen.
// Relies on globals of app.html: $, J, m, ic, esc, THEMES, THEME, showView, layout, userScale.
(() => {
  const body = $('lk-body'), toast = $('lk-toast'), L = window.LOOK, root = document.documentElement;
  let toastTimer = 0, customOpen = false, draft = null, tab = 'look';
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 2600); };

  const PANELS = [['next', 'Что дальше', 'Таймеры, напоминания и ближайшие события'], ['wxp', 'Погода', 'Небо, температура, восход и закат'], ['cam', 'Камера и охрана', 'Превью камеры и режим охраны'],
    ['sys', 'Система', 'Процессор, память, диск, батарея, сеть'], ['hist', 'История', 'Что вы говорили Jarvis'], ['sugg', 'Подсказки под ядром', 'Примеры команд в виде кнопок']];
  const THEME_LIST = () => [...THEMES, { id: 'custom', name: 'Свой цвет', ...L.custom() }];
  const tileColors = (t) => ({ bg: `linear-gradient(160deg, hsl(${t.h} ${Math.round(70 * t.sk)}% 20%), hsl(${t.h + 10} ${Math.round(75 * t.sk)}% 6%))`, ac: `hsl(${t.h - 8} ${Math.min(100, Math.round(100 * t.sk))}% 59%)` });

  const card = (cc, icon, title, inner) => `<section class="cm-card rm-card vc-card" style="--cc:${cc}"><h3><span class="vc-ic">${ic(icon, cc, 18)}</span>${esc(title)}</h3>${inner}</section>`;
  const slider = (key, label, min, max, step, val, shown, hint, cls = '') => `<div class="vc-row"><div class="vc-lab"><span>${esc(label)}</span><b data-val="${key}">${esc(shown)}</b></div><input type="range" class="vc-rng ${cls}" data-key="${key}" min="${min}" max="${max}" step="${step}" value="${val}" style="--p:${((val - min) / (max - min)) * 100}%">${hint ? `<small>${esc(hint)}</small>` : ''}</div>`;
  const sw = (key, label, hint, on) => `<div class="vc-row vc-sw"><div><span>${esc(label)}</span>${hint ? `<small>${esc(hint)}</small>` : ''}</div><button type="button" class="tgl${on ? ' on' : ''}" data-sw="${key}" aria-pressed="${!!on}"><span class="sw"></span></button></div>`;
  const choice = (key, cur, items) => `<div class="vc-choice" role="radiogroup">${items.map(([v, t, d]) => `<button type="button" class="vc-opt${cur === v ? ' on' : ''}" data-ch="${key}" data-v="${v}" role="radio" aria-checked="${cur === v}"><b>${esc(t)}</b><small>${esc(d)}</small></button>`).join('')}</div>`;

  function themeCard() {
    const cur = THEME.id, tiles = THEME_LIST().map((t, k) => { const c = tileColors(t); return `<button type="button" class="lk-t${t.id === cur ? ' on' : ''}" data-theme="${t.id}" style="--k:${k};--bg:${c.bg};--ac:${c.ac};--h:${t.h}" title="${esc(t.name)}"><div class="lk-mock"><i></i><i></i><i></i><i></i><i></i><b></b>${t.id === cur ? '<em class="lk-ck"><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></em>' : ''}</div><span>${esc(t.name)}${t.id === cur ? '<small>сейчас</small>' : ''}</span></button>`; }).join('');
    let editor = '';
    if (customOpen) {
      const d = draft, chip = `hsl(${d.h} ${Math.round(100 * Math.min(1, d.sk))}% 58%)`;
      editor = `<div class="lk-custom"><div class="vc-lab"><span><i class="lk-chip" style="--chip:${chip}" id="lk-chip"></i>Свой цвет</span></div>`
        + slider('c_h', 'Оттенок', 0, 359, 1, d.h, String(Math.round(d.h)), '', 'lk-hue')
        + `<div style="--ph:${d.h}">${slider('c_sk', 'Насыщенность', 0.1, 1.1, 0.05, d.sk, `${Math.round(d.sk * 100)}%`, 'Меньше: спокойнее и серее, больше: ярче.', 'lk-sat')}</div>`
        + `<div class="vc-actions"><button type="button" class="cm-try primary" id="lk-c-ok">Применить</button><button type="button" class="cm-try" id="lk-c-no">Отмена</button><small>Окно перезагрузится, настройки останутся.</small></div></div>`;
    }
    return card('var(--cyan)', 'palette', 'Цветовая тема', `<div class="lk-themes">${tiles}</div>${editor}`);
  }
  function autoCard() {
    const a = L.auto(), opts = (sel) => THEME_LIST().map((t) => `<option value="${t.id}"${t.id === sel ? ' selected' : ''}>${esc(t.name)}</option>`).join('');
    const now = L.isNight(a) ? 'сейчас ночь' : 'сейчас день';
    return card('var(--amber)', 'cal', 'Тема по времени суток',
      sw('auto_on', 'Менять тему сама', a.on ? `Днём и ночью свои темы; ${now}.` : 'Днём одна тема, ночью другая.', a.on)
      + `<div class="lk-when${a.on ? '' : ' vc-dim'}"><label>Днём<select id="lk-day">${opts(a.day)}</select></label><label>Ночью<select id="lk-night">${opts(a.night)}</select></label>`
      + `<label>Ночь начинается<input type="time" id="lk-from" value="${esc(a.from)}"></label><label>Ночь заканчивается<input type="time" id="lk-to" value="${esc(a.to)}"></label></div>`);
  }
  function sizeCard() {
    const pct = Math.round(userScale * 100);
    return card('var(--green)', 'search', 'Размер интерфейса',
      slider('scale', 'Масштаб', 80, 160, 5, pct, `${pct}%`, 'То же, что Ctrl и + или −. Ctrl и 0 возвращает 100%.')
      + `<div class="vc-actions"><button type="button" class="cm-try" data-scale="-10">Меньше</button><button type="button" class="cm-try" data-scale="0">100%</button><button type="button" class="cm-try" data-scale="10">Больше</button></div>`);
  }
  function fxCard() {
    const fx = L.raw('jarvisFx') || 'auto', on = window.sfxOn ? window.sfxOn() : false, vol = window.sfxVolume ? window.sfxVolume() : 0.2;
    return card('var(--mag, #cc44ff)', 'pad', 'Эффекты и звук',
      choice('fx', fx, [['auto', 'Сама', 'Экономные, если так настроена система'], ['full', 'Полные', 'Фон, свет за курсором, плавные появления'], ['lite', 'Экономные', 'Меньше анимации, легче для слабого компьютера']])
      + `<div class="vc-sep"></div>` + sw('sfx', 'Звуки интерфейса', 'Тихие щелчки, переключатели и сигналы.', on)
      + `<div class="${on ? '' : 'vc-dim'}">${slider('sfx_vol', 'Громкость звуков', 5, 60, 5, Math.round(vol * 100), `${Math.round(vol * 100)}%`)}</div>`);
  }
  function panelsCard() {
    const hid = new Set(L.hidden());
    return card('var(--cyan)', 'home', 'Панели на обзоре', PANELS.map(([k, t, d]) => sw('p_' + k, t, d, !hid.has(k))).join('')
      + `<small class="vc-note">На узком окне часть панелей прячется сама, независимо от этих настроек.</small>`);
  }
  function render() {
    if (tab !== 'look') return;
    body.innerHTML = `${themeCard()}<div class="vc-grid" style="margin-top:.8rem"><div class="vc-col">${sizeCard()}${fxCard()}</div><div class="vc-col">${autoCard()}${panelsCard()}</div></div>`
      + `<div class="lk-foot"><button type="button" class="cm-try" id="lk-reset">Сбросить внешний вид</button><small>Настройки хранятся в этом окне.</small></div>`;
    if (window.fzDropdown) window.fzDropdown.watch(body);
    if (window.fzTime) window.fzTime.watch(body);
  }

  function setScale(pct) {
    userScale = Math.min(1.6, Math.max(0.8, Math.round(pct) / 100)); L.setRaw('uiScale', String(userScale)); layout();
    const r = body.querySelector('[data-key="scale"]'), v = body.querySelector('[data-val="scale"]');
    if (r) { r.value = Math.round(userScale * 100); r.style.setProperty('--p', `${((r.value - r.min) / (r.max - r.min)) * 100}%`); } if (v) v.textContent = `${Math.round(userScale * 100)}%`;
  }
  const preview = () => { root.style.setProperty('--h', draft.h); root.style.setProperty('--sk', draft.sk); root.style.setProperty('--navy-h', draft.h); root.style.setProperty('--ns', draft.sk); const c = $('lk-chip'); if (c) c.style.setProperty('--chip', `hsl(${draft.h} ${Math.round(100 * Math.min(1, draft.sk))}% 58%)`); const s = body.querySelector('.lk-sat'); if (s && s.parentElement) s.parentElement.style.setProperty('--ph', draft.h); };
  const stopPreview = () => { root.style.setProperty('--h', THEME.h); root.style.setProperty('--sk', THEME.sk); root.style.setProperty('--navy-h', THEME.skin === 'command' ? 219 : THEME.h); root.style.setProperty('--ns', THEME.skin === 'command' ? 1 : THEME.sk); };
  const saveAuto = (patch) => { const a = { ...L.auto(), ...patch }; L.put('jarvisAuto', a); if (L.themeId() !== THEME.id) { L.reload(); return; } render(); };
  const fxApply = (v) => { if (v === 'auto') L.setRaw('jarvisFx', null); else L.setRaw('jarvisFx', v); root.dataset.fx = v === 'lite' || (v === 'auto' && matchMedia('(prefers-reduced-motion: reduce)').matches) ? 'lite' : 'full'; };
  let sfxTimer = 0;

  body.addEventListener('input', (e) => {
    const r = e.target.closest('.vc-rng'); if (!r) return;
    const key = r.dataset.key, v = parseFloat(r.value), lab = body.querySelector(`[data-val="${key}"]`);
    r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    if (key === 'scale') { if (lab) lab.textContent = `${Math.round(v)}%`; setScale(v); }
    else if (key === 'c_h') { draft.h = v; if (lab) lab.textContent = String(Math.round(v)); preview(); }
    else if (key === 'c_sk') { draft.sk = v; if (lab) lab.textContent = `${Math.round(v * 100)}%`; preview(); }
    else if (key === 'sfx_vol') { if (lab) lab.textContent = `${Math.round(v)}%`; if (window.sfxVolume) window.sfxVolume(v / 100); clearTimeout(sfxTimer); sfxTimer = setTimeout(() => { if (window.sfx) window.sfx('ok'); }, 160); }
  });
  body.addEventListener('change', (e) => {
    const t = e.target;
    if (t.id === 'lk-day') saveAuto({ day: t.value }); else if (t.id === 'lk-night') saveAuto({ night: t.value });
    else if (t.id === 'lk-from' && t.value) saveAuto({ from: t.value }); else if (t.id === 'lk-to' && t.value) saveAuto({ to: t.value });
  });
  body.addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.theme) {
      if (b.dataset.theme === 'custom') { customOpen = !customOpen; if (customOpen) { const c = THEME.id === 'custom' ? L.custom() : { h: THEME.h, sk: Math.min(1.1, THEME.sk) }; draft = { h: c.h, sk: c.sk }; preview(); } else stopPreview(); render(); return; }
      if (b.dataset.theme !== THEME.id || L.auto().on) L.setTheme(b.dataset.theme); return;
    }
    if (b.id === 'lk-c-ok') { L.put('jarvisCustom', { h: Math.round(draft.h), sk: +draft.sk.toFixed(2) }); L.setTheme('custom'); return; }
    if (b.id === 'lk-c-no') { customOpen = false; stopPreview(); render(); return; }
    if (b.dataset.scale !== undefined) { setScale(b.dataset.scale === '0' ? 100 : userScale * 100 + (+b.dataset.scale)); return; }
    if (b.dataset.ch === 'fx') { fxApply(b.dataset.v); render(); return; }
    if (b.dataset.sw) {
      const k = b.dataset.sw, on = !b.classList.contains('on');
      if (k === 'auto_on') saveAuto({ on }); else if (k === 'sfx') { window.sfxOn && window.sfxOn(on); if (on && window.sfx) window.sfx('ok'); render(); }
      else if (k.startsWith('p_')) { const id = k.slice(2), h = new Set(L.hidden()); if (on) h.delete(id); else h.add(id); L.put('jarvisHide', [...h]); L.applyHide(); render(); }
      return;
    }
    if (b.id === 'lk-reset') {
      ['jarvisTheme', 'jarvisCustom', 'jarvisAuto', 'jarvisHide', 'jarvisFx', 'jarvisSfxVol', 'uiScale', 'jarvisSfx'].forEach((k) => L.setRaw(k, null)); say('Внешний вид сброшен'); setTimeout(() => L.reload(), 350);
    }
  });

  L.ui = { card, slider, sw, choice, say };
  function showTab(t) {
    tab = t; customOpen = false; stopPreview();
    [...$('lk-tabs').children].forEach((b, i) => { const on = b.dataset.tab === t; b.classList.toggle('on', on); b.setAttribute('aria-selected', on); if (on) $('lk-tabs').style.setProperty('--i', i); });
    body.hidden = t !== 'look'; $('lk-tools').hidden = t !== 'tools'; $('lk-mods').hidden = t !== 'modules'; $('lk-dev').hidden = t !== 'dev'; $('lk-ai').hidden = t !== 'ai';
    if (t === 'tools') window.renderTools(); else if (t === 'modules') window.renderModules(); else if (t === 'dev') window.renderDev(); else if (t === 'ai') window.renderAi(); else render();
  }
  $('lk-tabs').addEventListener('click', (e) => { const b = e.target.closest('button[data-tab]'); if (b && b.dataset.tab !== tab) showTab(b.dataset.tab); });
  window.renderLook = () => showTab(tab);
  setInterval(() => { if (!document.hidden && L.auto().on && L.themeId() !== THEME.id) L.reload(); }, 30000);   // the schedule crossed day or night
  addEventListener('load', () => { let v = ''; try { v = sessionStorage.getItem('jarvisView') || ''; sessionStorage.removeItem('jarvisView'); } catch (e) {} if (v) setTimeout(() => showView(v), 0); });
})();
