// Voice screen: microphone (level, threshold, gain, devices, calibration), speech (volume, speed, night mode), wake mode, how Jarvis addresses you,
// speech recognition engine and the local fallback model. Every change is applied and saved at once (command `voice`, see ui_next/bridge/voice.py).
// Without a core the screen shows demo values and keeps changes local. Relies on globals of app.html: $, J, m, ic, esc, VIEW, showView.
(() => {
  Object.assign(P, { user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 20c1-4 4-5 8-5s7 1 8 5' });
  const body = $('vc-body'), toast = $('vc-toast');
  const DEMO = { stt_engine: 'gigaam', threshold: 200, gain: 2.5, volume: 1, headphone_mode: false, tts_speed: 1, tts_unload_timeout: 300, tts_night_enabled: true, tts_night_volume: 0.7,
    night_start: [22, 0], night_end: [7, 0], wake_word_mode: 'continuous', wake_active_timeout_sec: 30, address_mode: 'male', custom_address: '', llm_chat_fallback: true, llm_chat_unload_timeout: 600, language: 'ru', speech_language: 'ru',
    unload_steps: [60, 180, 300, 600, 900, 1800, 3600, 7200, 18000, 0] };
  let V = null, dev = null, calText = '', calState = '', toastTimer = 0, loaded = false, restartNote = false, LLM = { custom: '', default_present: true, busy: '', pct: 0, text: '' };
  const timers = {};
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); };
  const ERR = { bad_value: 'Значение не подошло', no_handler: 'Jarvis ещё запускается', failed: 'Не получилось применить' };
  const p2 = (n) => String(n).padStart(2, '0');
  const hm = (a) => `${p2(a[0])}:${p2(a[1])}`;
  const dur = (s) => (s === 0 ? 'всегда в памяти' : s < 3600 ? `${s / 60} мин` : `${s / 3600} ч`);

  async function call(body_) { return (await J.send('voice', body_)) || { ok: false }; }
  async function load() {
    if (m.connected) { const l = await call({ op: 'llm' }); if (l.ok) LLM = l.llm; }
    if (!m.connected) { V = { ...DEMO }; dev = { inputs: [{ index: 1, name: 'Микрофон (демо)' }], outputs: [{ name: 'Динамики (демо)' }], input: null, output: '' }; loaded = true; render(); return; }
    const r = await call({ op: 'get' }); if (r.ok) { V = r.values; loaded = true; render(); }
    const d = await call({ op: 'devices' }); if (d.ok) { dev = d; if (VIEW === 'voice') render(); }
  }
  function set(key, value, quiet) {
    V[key] = value;
    clearTimeout(timers[key]);
    timers[key] = setTimeout(async () => {
      if (!m.connected) return;
      const r = await call({ op: 'set', key, value });
      if (r.ok) { V = r.values; if (!quiet) render(); } else { say(ERR[r.error] || 'Не получилось сохранить'); load(); }
    }, 180);
  }

  // ---- building blocks ----
  const card = (cc, icon, title, inner, extra = '') => `<section class="cm-card rm-card vc-card" style="--cc:${cc}"><h3><span class="vc-ic">${ic(icon, cc, 18)}</span>${esc(title)}${extra}</h3>${inner}</section>`;
  const slider = (key, label, min, max, step, fmt, hint) => `<div class="vc-row"><div class="vc-lab"><span>${esc(label)}</span><b data-val="${key}">${esc(fmt(V[key]))}</b></div><input type="range" class="vc-rng" data-key="${key}" min="${min}" max="${max}" step="${step}" value="${V[key]}" style="--p:${((V[key] - min) / (max - min)) * 100}%">${hint ? `<small>${esc(hint)}</small>` : ''}</div>`;
  const sw = (key, label, hint) => `<div class="vc-row vc-sw"><div><span>${esc(label)}</span>${hint ? `<small>${esc(hint)}</small>` : ''}</div><button type="button" class="tgl${V[key] ? ' on' : ''}" data-sw="${key}" aria-pressed="${!!V[key]}"><span class="sw"></span></button></div>`;
  const choice = (key, items) => `<div class="vc-choice" role="radiogroup">${items.map(([v, t, d]) => `<button type="button" class="vc-opt${V[key] === v ? ' on' : ''}" data-ch="${key}" data-v="${v}" role="radio" aria-checked="${V[key] === v}"><b>${esc(t)}</b><small>${esc(d)}</small></button>`).join('')}</div>`;
  const FMT = { threshold: (v) => String(Math.round(v)), gain: (v) => `×${(+v).toFixed(1)}`, volume: (v) => `${Math.round(v * 100)}%`, tts_speed: (v) => `${(+v).toFixed(2)}×`, tts_night_volume: (v) => `${Math.round(v * 100)}%`, wake_active_timeout_sec: (v) => `${Math.round(v)} с` };

  function micCard() {
    const opt = (list, sel, valFn) => `<option value="">Как в системе</option>${list.map((d) => `<option value="${esc(valFn(d))}"${String(valFn(d)) === String(sel) ? ' selected' : ''}>${esc(d.name)}</option>`).join('')}`;
    const devs = dev ? `<div class="vc-dev"><label>Микрофон<select id="vc-in">${opt(dev.inputs, dev.input, (d) => d.index)}</select></label><label>Динамики<select id="vc-out">${opt(dev.outputs, dev.output, (d) => d.name)}</select></label></div>` : '<div class="vc-note">Ищу устройства…</div>';
    return card('var(--amber)', 'mic', 'Микрофон',
      `<div class="vc-meter" title="Уровень звука с микрофона и порог срабатывания"><i id="vc-lvl"></i><u id="vc-thr"></u></div>`
      + slider('threshold', 'Порог срабатывания', 30, 1200, 10, FMT.threshold, 'Ниже порога Jarvis считает тишиной. Поднимите, если он реагирует на шум.')
      + slider('gain', 'Усиление', 1, 6, 0.1, FMT.gain, 'Если голос тихий, увеличьте.')
      + `<div class="vc-actions"><button type="button" class="cm-try" id="vc-cal"${calState === 'running' ? ' disabled' : ''}>${calState === 'running' ? 'Калибрую…' : 'Откалибровать'}</button><span class="vc-status ${calState}" id="vc-calt">${esc(calText)}</span></div>`
      + devs + sw('headphone_mode', 'Режим наушников', 'Jarvis не слышит сам себя, когда звук идёт в наушники.'));
  }
  function speechCard() {
    const steps = V.unload_steps.map((s) => `<option value="${s}"${+V.tts_unload_timeout === s ? ' selected' : ''}>${dur(s)}</option>`).join('');
    return card('var(--cyan)', 'vol', 'Озвучка',
      slider('volume', 'Громкость голоса', 0, 1, 0.01, FMT.volume) + slider('tts_speed', 'Скорость речи', 0.6, 1.4, 0.05, FMT.tts_speed)
      + `<div class="vc-actions"><button type="button" class="cm-try" id="vc-say">Проверить голос</button></div>`
      + `<div class="vc-row"><div class="vc-lab"><span>Держать модель голоса в памяти</span></div><select id="vc-tts-keep">${steps}</select><small>Дольше в памяти: быстрее ответ, но занято больше оперативной памяти.</small></div>`
      + `<div class="vc-sep"></div>` + sw('tts_night_enabled', 'Ночной режим', 'Ночью Jarvis говорит тише.')
      + `<div class="vc-night${V.tts_night_enabled ? '' : ' off'}"><label>С<input type="time" id="vc-ns" value="${hm(V.night_start)}"></label><label>До<input type="time" id="vc-ne" value="${hm(V.night_end)}"></label></div>`
      + `<div class="${V.tts_night_enabled ? '' : 'vc-dim'}">${slider('tts_night_volume', 'Ночная громкость', 0.1, 1, 0.05, FMT.tts_night_volume)}</div>`);
  }
  function wakeCard() {
    return card('var(--green)', 'bell', 'Как Jarvis просыпается',
      choice('wake_word_mode', [['continuous', 'Диалог', 'После «Джарвис» слушает несколько команд подряд'], ['single', 'Одна команда', 'Каждая команда начинается со слова «Джарвис»']])
      + (V.wake_word_mode === 'continuous' ? slider('wake_active_timeout_sec', 'Сколько слушать после обращения', 10, 120, 5, FMT.wake_active_timeout_sec, 'Если молчать дольше, нужно снова сказать «Джарвис».') : ''));
  }
  function addrCard() {
    const uk = V.speech_language === 'uk', preview = V.address_mode === 'custom' ? (V.custom_address || '—') : V.address_mode === 'female' ? (uk ? 'пані' : 'леди') : (uk ? 'сер' : 'сэр');
    return card('var(--mag, #cc44ff)', 'user', 'Как Jarvis к вам обращается',
      choice('address_mode', [['male', V.speech_language === 'uk' ? 'Сер' : 'Сэр', 'Мужское обращение'], ['female', V.speech_language === 'uk' ? 'Пані' : 'Леди', 'Женское обращение'], ['custom', 'Своё', 'Любое слово: «шеф», «мастер»…']])
      + (V.address_mode === 'custom' ? `<div class="vc-add"><input id="vc-addr" maxlength="30" placeholder="например: шеф" value="${esc(V.custom_address)}" autocomplete="off"><button type="button" class="cm-try" id="vc-addr-ok">Применить</button></div>` : '')
      + `<div class="vc-prev">Jarvis скажет: <b>«Да, ${esc(preview)}»</b></div>`);
  }
  function sttCard() {
    return card('var(--purple, #a78bfa)', 'doc', 'Распознавание речи',
      choice('stt_engine', [['gigaam', 'GigaAM', 'Точнее и быстрее, рекомендуется'], ['vosk', 'Vosk', 'Легче и проще, но менее точный']])
      + (restartNote ? '<div class="vc-warn">Чтобы смена движка заработала, перезапустите Jarvis.</div>' : '') + (V.stt_engine === 'vosk' ? '<div class="vc-warn soft">Vosk понимает хуже: сложные фразы и числа он может перепутать.</div>' : ''));
  }
  function langCard() {
    return card('var(--amber)', 'doc', 'Язык',
      choice('language', [['ru', 'Русский', 'Окна, подсказки и профили игр на русском'], ['uk', 'Українська', 'Вікна, підказки та профілі ігор українською']])
      + `<div class="vc-prev">Jarvis слушает и говорит на <b>${V.speech_language === 'uk' ? 'украинском' : 'русском'}</b>: хорошей украинской модели речи пока нет, поэтому язык интерфейса речь не меняет.</div>`
      + '<div class="vc-note">Язык окон меняется сразу: страница перезагружается, настройки остаются.</div>');
  }
  function modelBlock() {
    const busy = LLM.busy, down = busy === 'downloading';
    const what = LLM.custom ? `Своя модель: ${LLM.custom}` : LLM.default_present ? 'Стандартная модель' : 'Стандартная модель ещё не скачана (около 870 МБ)';
    const bar = down ? `<div class="vc-prog"><i style="width:${LLM.pct || 0}%"></i></div>` : '';
    const dis = busy === 'validating' || busy === 'picking' || down ? ' disabled' : '';
    return `<div class="vc-model"><div class="vc-mt"><b>${esc(what)}</b>${LLM.text ? `<span class="vc-status ${/не подошла|Ошибка|Не удалось/.test(LLM.text) ? 'error' : /Готово|загружена/.test(LLM.text) ? 'done' : 'running'}">${esc(LLM.text)}</span>` : ''}</div>${bar}
      <div class="vc-actions"><button type="button" class="cm-try" id="vc-llm-pick"${dis}>Выбрать файл модели…</button>${LLM.custom ? `<button type="button" class="cm-try" id="vc-llm-reset"${dis}>Вернуть стандартную</button>` : ''}${!LLM.custom && !LLM.default_present && !down ? `<button type="button" class="cm-try pe-go" id="vc-llm-dl"${dis}>Скачать</button>` : ''}${down ? '<button type="button" class="cm-try danger" id="vc-llm-cancel">Отменить загрузку</button>' : ''}</div>
      <small>Подойдёт любая модель в формате GGUF. Перед сохранением Jarvis проверит, что она запускается.</small></div>`;
  }
  function llmCard() {
    const steps = V.unload_steps.map((s) => `<option value="${s}"${+V.llm_chat_unload_timeout === s ? ' selected' : ''}>${dur(s)}</option>`).join('');
    return card('var(--cyan)', 'ext', 'Локальная нейросеть',
      sw('llm_chat_fallback', 'Отвечать нейросетью, когда команда не распознана', 'Работает без интернета на вашем компьютере.')
      + `<div class="vc-row"><div class="vc-lab"><span>Выгружать из памяти через</span></div><select id="vc-llm-keep">${steps}</select></div>`
      + modelBlock());
  }

  function render() {
    if (!loaded || !V) { body.innerHTML = '<div class="rm-empty"><b>Загружаю настройки голоса…</b></div>'; return; }
    const keep = body.scrollTop;
    body.innerHTML = `<div class="vc-grid"><div class="vc-col">${micCard()}${wakeCard()}${sttCard()}${langCard()}</div><div class="vc-col">${speechCard()}${addrCard()}${llmCard()}</div></div>`
      + (m.connected ? '' : '<p class="vc-demo">Пример: ядро не подключено, изменения никуда не сохраняются.</p>');
    body.scrollTop = keep; paintMeter();
  }

  // ---- level meter: read the core's level a few times a second, only while this screen is open ----
  let meterTimer = 0;
  function paintMeter() {
    const bar = $('vc-lvl'), thr = $('vc-thr'); if (!bar || !V) return;
    /* the core publishes sqrt(rms / 4000): the threshold (raw rms) is placed on the same scale */
    const lv = Math.max(0, Math.min(1, (m.connected ? m.level : 0) || 0));
    bar.style.transform = `scaleX(${lv})`; thr.style.left = `${Math.min(100, Math.sqrt(V.threshold / 4000) * 100)}%`;
  }
  const startMeter = () => { clearInterval(meterTimer); meterTimer = setInterval(() => { if (VIEW !== 'voice' || document.hidden) return; paintMeter(); }, 120); };

  // ---- events ----
  body.addEventListener('input', (e) => {
    const r = e.target.closest('.vc-rng'); if (!r) return;
    const key = r.dataset.key, v = parseFloat(r.value);
    r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    const lab = body.querySelector(`[data-val="${key}"]`); if (lab) lab.textContent = FMT[key](v);
    set(key, v, true); if (key === 'threshold') paintMeter();
  });
  body.addEventListener('change', async (e) => {
    const t = e.target;
    if (t.id === 'vc-tts-keep') return set('tts_unload_timeout', +t.value);
    if (t.id === 'vc-llm-keep') return set('llm_chat_unload_timeout', +t.value);
    if (t.id === 'vc-ns' || t.id === 'vc-ne') { const [h, mm] = t.value.split(':').map(Number); if (!Number.isNaN(h)) set(t.id === 'vc-ns' ? 'night_start' : 'night_end', [h, mm]); return; }
    if (t.id === 'vc-in' || t.id === 'vc-out') {
      const inp = $('vc-in').value, out = $('vc-out').value;
      if (!m.connected) { say('Демо: устройства не переключаются'); return; }
      say('Переключаю устройства…');
      const r = await call({ op: 'set_devices', input: inp === '' ? null : +inp, output: out });
      say(r.ok ? (r.message || 'Устройства применены') : 'Не получилось переключить устройство');
    }
  });
  body.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.sw) { const key = b.dataset.sw; set(key, !V[key]); render(); return; }
    if (b.dataset.ch) { const key = b.dataset.ch; if (V[key] === b.dataset.v) return; if (key === 'stt_engine') restartNote = true; set(key, b.dataset.v); render(); return; }
    if (b.id === 'vc-cal') {
      if (!m.connected) { calState = 'done'; calText = 'Демо: в работе здесь запустится замер фона'; render(); return; }
      const r = await call({ op: 'calibrate' }); if (!r.ok) say(r.error === 'busy' ? 'Калибровка уже идёт' : 'Не получилось запустить калибровку');
    } else if (b.id === 'vc-say') {
      if (!m.connected) { say('Демо: здесь Jarvis произнесёт тестовую фразу'); return; }
      const r = await call({ op: 'say' }); say(r.ok ? 'Говорю тестовую фразу' : ERR[r.error] || 'Не получилось');
    } else if (b.id === 'vc-addr-ok') {
      const v = $('vc-addr').value.trim(); if (!v) { say('Введите слово для обращения'); return; }
      set('custom_address', v); render(); say('Обращение сохранено');
    } else if (b.id === 'vc-llm-pick') {
      if (!m.connected) { say('Демо: откроется выбор файла модели'); return; }
      const r = await call({ op: 'llm', do: 'pick' }); if (!r.ok) say(r.error === 'busy' ? 'Подождите, предыдущая операция ещё идёт' : 'Не получилось открыть выбор файла');
    } else if (b.id === 'vc-llm-reset') {
      const r = await (m.connected ? call({ op: 'llm', do: 'reset' }) : { ok: true }); if (r.ok) { if (!m.connected) LLM = { ...LLM, custom: '', text: 'Стандартная модель' }; say('Вернул стандартную модель'); load(); } else say('Сейчас нельзя: идёт проверка или загрузка');
    } else if (b.id === 'vc-llm-dl') {
      if (!m.connected) { say('Демо: начнётся загрузка модели'); return; }
      const r = await call({ op: 'llm', do: 'download' }); say(r.ok ? 'Скачиваю модель, это может занять несколько минут' : 'Загрузка уже идёт');
    } else if (b.id === 'vc-llm-cancel') {
      await call({ op: 'llm', do: 'cancel' }); say('Отменяю загрузку…');
    }
  });
  J.on('voice_llm', () => { if (m.voiceLlm) { LLM = m.voiceLlm; if (VIEW === 'voice') render(); } });
  J.on('voice_cal', () => {
    const c = m.voiceCal; if (!c) return;
    calState = c.state; calText = c.text; if (c.state === 'done') { load(); } else if (VIEW === 'voice') render();
  });
  J.on('conn', () => { if (VIEW === 'voice') load(); });
  window.renderVoice = () => { restartNote = false; load(); startMeter(); };
  if (window.fzDropdown) window.fzDropdown.watch(body);
})();
