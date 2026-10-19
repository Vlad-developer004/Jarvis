// First-run wizard: language, microphone, how Jarvis addresses you, the feature profile and an AI key, in five steps and a finish.
// It opens by itself until it is finished or skipped once (the `wizard` bridge command keeps the flag), and again from Settings > Tools or window.openWizard().
// Every choice goes through the same bridge commands as the settings screens (voice, modules, ai) and is applied at once; the current values are preselected, so walking through changes nothing.
// Relies on globals of app.html: $, J, m, esc, ic.
(() => {
  const STEPS = [['Начало', 'home'], ['Микрофон', 'mic'], ['Обращение', 'user'], ['Профиль', 'grid'], ['ИИ', 'search'], ['Готово', 'check']];
  const PROFILES = { full: ['Полный', 'Все функции: ИИ-ответы, игры, кино, мониторинг. Больше всего нагрузки на память и процессор.'], assistant: ['Ассистент', 'Без ИИ, игр и кино: сбалансированный набор для повседневных дел.'], minimal: ['Минимальный', 'Только распознавание речи и управление окнами. Самый быстрый отклик.'] };
  const PROV = [['groq', 'Groq', 'Есть бесплатный план, быстрый отклик'], ['openai', 'OpenAI', 'Платный'], ['google', 'Google', 'Есть бесплатный план'], ['local', 'Свой сервер', 'Без ключа, на этом или другом компьютере']];
  let root = null, step = 0, busy = false, shown = false;
  const S = { v: null, dev: null, prof: null, ai: null, cal: '', calState: '', keyNote: '', pickedProv: '' };

  const call = async (cmd, body) => (m.connected ? (await J.send(cmd, body)) || { ok: false } : { ok: false, error: 'offline' });
  const toast = (t) => { const e = root && root.querySelector('.wz-toast'); if (!e) return; e.textContent = t; e.classList.add('on'); clearTimeout(toast.t); toast.t = setTimeout(() => e.classList.remove('on'), 3000); };
  const btn = (t, a, cls = '') => `<button type="button" class="cm-try ${cls}" ${a}>${t}</button>`;
  const tiles = (items, cur, attr) => `<div class="vc-choice wz-tiles" role="radiogroup">${items.map(([v, t, d]) => `<button type="button" class="vc-opt${cur === v ? ' on' : ''}" ${attr}="${esc(v)}" role="radio" aria-checked="${cur === v}"><b>${esc(t)}</b><small>${esc(d)}</small></button>`).join('')}</div>`;

  async function loadAll() {
    const [v, d, p, a] = await Promise.all([call('voice', { op: 'get' }), call('voice', { op: 'devices' }), call('modules', { op: 'state' }), call('ai', { op: 'state' })]);
    if (v.ok) S.v = v.values; if (d.ok) S.dev = d; if (p.ok) S.prof = p; if (a.ok) S.ai = a;
    S.pickedProv = S.ai ? S.ai.provider : 'groq'; paint();
  }
  const setVoice = async (key, value) => { const r = await call('voice', { op: 'set', key, value }); if (r.ok) S.v = r.values; else toast('Не получилось сохранить'); return r; };

  function body() {
    const v = S.v || {}, uk = v.speech_language === 'uk';
    if (step === 0) {
      return `<h2>Добро пожаловать в Jarvis</h2><p>Пять коротких шагов, и ассистент готов: язык, микрофон, обращение, набор функций и ИИ. Всё это можно изменить потом в Настройках, ничего не потеряется.</p>`
        + `<h4>Язык интерфейса и голоса</h4>${tiles([['ru', 'Русский', 'Jarvis говорит и слушает по-русски'], ['uk', 'Українська', 'Jarvis говорить і слухає українською']], v.language || 'ru', 'data-lang')}`;
    }
    if (step === 1) {
      const d = S.dev, ins = d ? d.inputs : [], cur = d && d.input !== null && d.input !== undefined ? String(d.input) : '';
      const sel = d ? `<label class="wz-l">Микрофон<select id="wz-in"><option value=""${cur === '' ? ' selected' : ''}>По умолчанию в Windows</option>${ins.map((x) => `<option value="${x.index}"${String(x.index) === cur ? ' selected' : ''}>${esc(x.name)}</option>`).join('')}</select></label>` : '<div class="vc-note">Ищу микрофоны…</div>';
      return `<h2>Микрофон</h2><p>Выберите, через какой микрофон вас слушать. Затем замерьте фон: Jarvis сам подберёт порог и усиление, чтобы он слышал вас, а не шум.</p>${sel}`
        + `<div class="vc-actions">${btn(S.calState === 'running' ? 'Замеряю…' : 'Замерить фон', `data-cal="1"${S.calState === 'running' ? ' disabled' : ''}`, 'primary')}${btn('Послушать голос', 'data-say="1"')}</div>`
        + (S.cal ? `<div class="tl-status ${S.calState === 'done' ? 'tl-ok' : S.calState === 'error' ? 'tl-warn' : ''}">${esc(S.cal)}</div>` : '<small class="vc-note">Во время замера помолчите несколько секунд.</small>');
    }
    if (step === 2) {
      const pv = v.address_mode === 'custom' ? (v.custom_address || '…') : v.address_mode === 'female' ? (uk ? 'пані' : 'леди') : (uk ? 'сер' : 'сэр');
      return `<h2>Как к вам обращаться</h2><p>Jarvis будет вставлять это в ответы: «Слушаю, ${esc(pv)}».</p>`
        + tiles([['male', uk ? 'Сер' : 'Сэр', 'Мужское обращение'], ['female', uk ? 'Пані' : 'Леди', 'Женское обращение'], ['custom', 'Своё слово', 'Например: шеф']], v.address_mode || 'male', 'data-addr')
        + (v.address_mode === 'custom' ? `<div class="vc-add"><input id="wz-addr" maxlength="30" placeholder="например: шеф" value="${esc(v.custom_address || '')}" autocomplete="off">${btn('Сохранить', 'data-addrok="1"')}</div>` : '')
        + `<div class="vc-actions">${btn('Послушать голос', 'data-say="1"')}</div>`;
    }
    if (step === 3) {
      const p = S.prof;
      return `<h2>Набор функций</h2><p>Профиль решает, какие модули включены. Отдельные модули можно переключить позже в Настройках. Тяжёлые профили занимают больше памяти.</p>`
        + (p ? tiles(p.profiles.map((k) => [k, PROFILES[k][0], PROFILES[k][1]]), p.profile, 'data-prof') + '<small class="vc-note">Профиль применится полностью после перезапуска Jarvis.</small>' : '<div class="vc-note">Загружаю…</div>');
    }
    if (step === 4) {
      const a = S.ai, cur = S.pickedProv, has = a && a.providers.find((x) => x.id === cur) && a.providers.find((x) => x.id === cur).has_key, local = cur === 'local', site = a && (a.providers.find((x) => x.id === cur) || {}).site;
      return `<h2>ИИ для ответов на вопросы</h2><p>Нужен для вопросов, на которые Jarvis сам не знает ответ. Без ключа ассистент работает как голосовой пульт, но на такие вопросы не ответит. Этот шаг можно пропустить.</p>`
        + tiles(PROV.map(([id, n, d]) => [id, n, d]), cur, 'data-prov')
        + (local ? '<small class="vc-note">Адрес локального сервера задаётся потом в Настройках, на вкладке «ИИ».</small>'
          : `<div class="tl-status ${has ? 'tl-ok' : ''}">${has ? 'Ключ уже сохранён на этом компьютере' : 'Ключ ещё не задан'}</div><label class="wz-l">Ключ доступа<input id="wz-key" type="password" maxlength="400" placeholder="${has ? 'Вставьте новый, чтобы заменить' : 'Вставьте ключ'}" autocomplete="off"></label>`
            + `<div class="vc-actions">${btn('Сохранить ключ', 'data-key="1"', 'primary')}${site ? btn('Где взять ключ', `data-site="${esc(site)}"`) : ''}</div>`)
        + (S.keyNote ? `<div class="tl-status">${esc(S.keyNote)}</div>` : '');
    }
    const prof = S.prof ? PROFILES[S.prof.profile][0] : '', prov = S.ai ? (S.ai.providers.find((x) => x.id === S.ai.provider) || {}).name : '', hasKey = S.ai && S.ai.providers.some((x) => x.needs_key && x.has_key);
    return `<h2>Всё готово</h2><p>Jarvis настроен. Вот что выбрано:</p><ul class="wz-sum"><li><b>Язык</b>${v.language === 'uk' ? 'Українська' : 'Русский'}</li><li><b>Профиль</b>${esc(prof)}</li><li><b>ИИ</b>${hasKey ? esc(prov || 'ключ задан') : 'ключ не задан'}</li></ul>`
      + `<p>Попробуйте сказать: «что сейчас играет», «перемотай на 5 минут назад» или «добавь в календарь завтра в 15:00 встреча».</p><small class="vc-note">Мастер можно пройти снова в Настройках, на вкладке «Инструменты».</small>`;
  }

  function paint() {
    if (!root) return;
    const keep = {}; for (const id of ['wz-addr', 'wz-key']) { const e = root.querySelector('#' + id); if (e && e.value) keep[id] = e.value; }
    const rail = STEPS.map(([t, i], n) => `<li class="${n === step ? 'on' : n < step ? 'done' : ''}"><i>${n < step ? '✓' : n + 1}</i><span>${t}</span></li>`).join('');
    root.querySelector('.wz-rail').innerHTML = `<div class="wz-brand">${ic('home', 'var(--cyan)', 20)}<b>Jarvis</b></div><ol>${rail}</ol>`;
    root.querySelector('.wz-main').innerHTML = body();
    root.querySelector('.wz-back').hidden = step === 0; root.querySelector('.wz-next').textContent = step === STEPS.length - 1 ? 'Начать работу' : step === 4 ? 'Далее' : 'Далее';
    for (const id in keep) { const e = root.querySelector('#' + id); if (e) e.value = keep[id]; }
    if (window.fzDropdown) window.fzDropdown.watch(root.querySelector('.wz-main'));
  }

  async function finish(skipped) {
    if (busy) return; busy = true; const r = await call('wizard', { op: 'done' }); busy = false;
    if (!r.ok && r.error !== 'offline') toast('Не удалось запомнить, мастер может открыться снова');
    close();
  }
  function close() { if (!root) return; root.remove(); root = null; shown = false; document.removeEventListener('keydown', onKey, true); }
  function onKey(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }

  function open() {
    if (shown) return; if (!m.connected) { const t = document.querySelector('.cm-toast'); if (t) { t.textContent = 'Мастеру нужен запущенный Jarvis'; t.classList.add('on'); setTimeout(() => t.classList.remove('on'), 2500); } return; }
    shown = true; step = 0; Object.assign(S, { v: null, dev: null, prof: null, ai: null, cal: '', calState: '', keyNote: '' });
    root = document.createElement('div'); root.className = 'wz'; root.setAttribute('role', 'dialog'); root.setAttribute('aria-modal', 'true'); root.setAttribute('aria-label', 'Мастер первой настройки');
    root.innerHTML = `<div class="wz-box"><aside class="wz-rail"></aside><section class="wz-pane"><div class="wz-main"></div><div class="wz-foot"><button type="button" class="wz-skip">Пропустить мастер</button><span class="wz-sp"></span><button type="button" class="cm-try wz-back">Назад</button><button type="button" class="cm-try primary wz-next">Далее</button></div><div class="wz-toast" role="status"></div></section></div>`;
    document.body.appendChild(root); if (window.fzFields) window.fzFields.watch(root);
    document.addEventListener('keydown', onKey, true); paint(); loadAll();
    root.addEventListener('click', onClick); root.addEventListener('change', onChange);
    root.addEventListener('keydown', (e) => { if (e.key === 'Enter' && e.target.matches('input')) { e.preventDefault(); const b = root.querySelector(e.target.id === 'wz-key' ? '[data-key]' : '[data-addrok]'); if (b) b.click(); } });
  }

  async function onChange(e) {
    if (e.target.id === 'wz-in') { const r = await call('voice', { op: 'set_devices', input: e.target.value === '' ? null : +e.target.value, output: (S.dev && S.dev.output) || '' }); toast(r.ok ? 'Микрофон применён' : 'Не получилось переключить микрофон'); if (r.ok && S.dev) S.dev.input = e.target.value === '' ? null : +e.target.value; }
  }
  async function onClick(e) {
    const b = e.target.closest('button'); if (!b) return; const d = b.dataset;
    if (b.classList.contains('wz-skip')) { finish(true); return; }
    if (b.classList.contains('wz-back')) { step = Math.max(0, step - 1); paint(); return; }
    if (b.classList.contains('wz-next')) { if (step === STEPS.length - 1) { finish(false); return; } step += 1; paint(); return; }
    if (d.lang) { await setVoice('language', d.lang); paint(); return; }
    if (d.cal) { const r = await call('voice', { op: 'calibrate' }); if (r.ok) { S.calState = 'running'; S.cal = 'Подбираю частоту и уровень шума: помолчите несколько секунд'; paint(); } else toast(r.error === 'busy' ? 'Замер уже идёт' : 'Не получилось запустить замер'); return; }
    if (d.say) { const r = await call('voice', { op: 'say' }); toast(r.ok ? 'Говорю тестовую фразу' : 'Jarvis ещё запускается'); return; }
    if (d.addr) { await setVoice('address_mode', d.addr); paint(); return; }
    if (d.addrok) { const t = root.querySelector('#wz-addr').value.trim(); if (!t) { toast('Введите слово для обращения'); return; } await setVoice('custom_address', t); paint(); toast('Обращение сохранено'); return; }
    if (d.prof) { const r = await call('modules', { op: 'profile', profile: d.prof }); if (r.ok) { S.prof = r; paint(); } else toast('Не получилось сохранить профиль'); return; }
    if (d.prov) { S.pickedProv = d.prov; S.keyNote = ''; const r = await call('ai', { op: 'provider', id: d.prov }); if (r.ok) S.ai = r; paint(); return; }
    if (d.site) { J.send('open_url', { url: d.site }); return; }
    if (d.key) { const k = root.querySelector('#wz-key').value.trim(); if (!k) { toast('Вставьте ключ'); return; } const r = await call('ai', { op: 'key_save', provider: S.pickedProv, key: k }); if (r.ok) { S.ai = r; S.keyNote = 'Ключ сохранён'; } else S.keyNote = r.error === 'bad_value' ? 'Ключ не подошёл: проверьте, что скопировали его целиком' : 'Не получилось сохранить ключ'; paint(); }
  }
  J.on('voice_cal', () => { const c = m.voiceCal; if (!c || !root) return; S.calState = c.state; S.cal = c.text; if (step === 1) paint(); });

  window.openWizard = open;
  addEventListener('load', async () => { setTimeout(async () => { if (!m.connected) return; const r = await call('wizard', { op: 'state' }); if (r.ok && !r.done) open(); }, 2500); });
})();
