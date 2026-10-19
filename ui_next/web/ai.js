// Settings > AI: provider and model, the API key (write-only: the core never sends it back), the local server address, answer style, a test request.
// Data comes from the `ai` bridge command (ui_next/bridge/ai.py); every change is saved at once and the core answers with the fresh state.
// Without a core the tab shows sample data and refuses changes. Relies on globals of app.html: $, J, m, esc, and window.LOOK.ui from look.js.
(() => {
  const root = $('lk-ai'), U = window.LOOK.ui;
  const DEMO = { ok: true, provider: 'groq', model: 'llama-3.3-70b-versatile', temperature: 0.3, max_tokens: 250, top_k: 40, web_search: false, mini_window: true, models_all: false, fallback: { enabled: true, order: ['google'] }, budget: { enabled: false, limit: 0, limit_in: 0, limit_out: 0, primary: 'groq', usage: [{ id: 'groq', name: 'Groq', count: 12, tin: 3000, tout: 900, limit: 1000 }], days: Array.from({ length: 14 }, (_, i) => ({ date: new Date(Date.now() - (13 - i) * 864e5).toISOString().slice(0, 10), req: i, in: i * 200, out: i * 60, by: { groq: { req: i, in: i * 200, out: i * 60 } } })) }, last_switch: {}, local_url: 'http://localhost:11434/v1',
    models: [{ id: 'llama-3.3-70b-versatile', ctx: '128k', rpm: '30', rpd: '1000', alias: '' }, { id: 'llama-3.1-8b-instant', ctx: '128k', rpm: '30', rpd: '14400', alias: '' }],
    providers: [{ id: 'groq', name: 'Groq', site: '', has_key: true, needs_key: true }, { id: 'openai', name: 'OpenAI', site: '', has_key: false, needs_key: true }, { id: 'local', name: 'Локальный сервер', site: '', has_key: false, needs_key: false }] };
  const ERR = { bad_value: 'Значение не подошло', not_found: 'Не найдено', no_key: 'Сначала сохраните ключ', fetch_failed: 'Не удалось получить список: проверьте ключ и интернет', unreachable: 'Сервер не отвечает по этому адресу',
    failed: 'Запрос не удался', empty: 'Ответ пришёл пустой', write_failed: 'Не удалось сохранить', no_handler: 'Jarvis ещё запускается' };
  const STYLES = [['Кратко', 0.2, 150], ['Обычно', 0.3, 250], ['Подробно', 0.5, 600]];
  let chartM = 'req', chartP = 'all', S = null, status = '', testing = false, busy = false, timer = 0, askClear = false;
  const say = (t) => { if (t) U.say(t); };

  async function call(body) { if (!m.connected) { say('Без ядра изменить нельзя'); return { ok: false, error: 'offline' }; } return (await J.send('ai', body)) || { ok: false }; }
  async function act(body, okText) {
    const r = await call(body);
    if (r.ok) { if (r.providers) S = r; say(okText); render(); } else if (r.error !== 'offline') say(ERR[r.error] || 'Не получилось сохранить');
    return r;
  }
  async function load() { if (!m.connected) { S = DEMO; render(); return; } const r = await call({ op: 'state' }); if (r.ok) { S = r; render(); } }
  async function refresh(quiet) {
    if (!m.connected || busy) return; busy = true; status = 'Обновляю список моделей…'; render();
    const r = await call({ op: 'refresh' }); busy = false;
    if (r.ok) { S = r; status = `Моделей в списке: ${r.count ?? r.models.length}`; } else { status = quiet && r.error === 'no_key' ? '' : (ERR[r.error] || 'Не удалось обновить список'); }
    render();
  }
  const btn = (t, a, cls = '') => `<button type="button" class="cm-try ${cls}" ${a}>${t}</button>`;
  const cur = () => S.providers.find((p) => p.id === S.provider) || S.providers[0];

  function providerCard() {
    const p = cur(), mo = S.models.find((x) => x.id === S.model);
    const grid = `<div class="ai-prov" role="radiogroup">${S.providers.map((x) => `<button type="button" class="ai-p${x.id === S.provider ? ' on' : ''}" data-prov="${x.id}" role="radio" aria-checked="${x.id === S.provider}"><b>${esc(x.name)}</b><small>${x.needs_key ? (x.has_key ? 'ключ есть' : 'нет ключа') : 'ключ не нужен'}</small></button>`).join('')}</div>`;
    const opts = (S.model ? '' : '<option value="" selected>Модель по умолчанию у сервиса</option>') + S.models.map((x) => `<option value="${esc(x.id)}"${x.id === S.model ? ' selected' : ''}>${esc(x.id)}</option>`).join('') + (S.model && !mo ? `<option value="${esc(S.model)}" selected>${esc(S.model)} (своя)</option>` : '');
    const stats = mo ? `<div class="ai-stats"><span><small>Контекст</small><b>${esc(mo.ctx)}</b></span><span><small>Запросов в минуту</small><b>${esc(mo.rpm)}</b></span><span><small>В день</small><b>${esc(mo.rpd)}</b></span></div>${mo.alias ? `<small class="vc-note">${esc(mo.alias)}</small>` : ''}` : '';
    return U.card('var(--cyan)', 'user', 'Провайдер и модель',
      `<small class="vc-note">Облачный ИИ отвечает на вопросы, которые Jarvis сам не знает. Выберите, чьим сервисом пользоваться.</small>${grid}`
      + `<label class="ai-l">Модель<select id="ai-model">${opts || '<option value="">Список пуст: нажмите «Обновить»</option>'}</select></label>${stats}`
      + `<div class="vc-add ai-custom"><input id="ai-cm" maxlength="120" placeholder="Своя модель, если её нет в списке" autocomplete="off">${btn('Использовать', 'data-cmodel="1"')}</div>`
      + U.sw('models_all', 'Показывать все модели сервиса', 'Как на странице сервиса: вместе с речевыми, служебными и платными. Для ответов подходят только текстовые модели.', S.models_all)
      + `<div class="vc-actions">${btn('Обновить список', 'data-refresh="1"')}${p.site ? btn('Где взять ключ', `data-site="${esc(p.site)}"`) : ''}</div>${status ? `<div class="tl-status">${esc(status)}</div>` : ''}`);
  }
  function keyCard() {
    const p = cur();
    if (p.id === 'local') {
      return U.card('var(--green)', 'pc', 'Локальный сервер',
        `<small class="vc-note">Ollama, llama.cpp или TabbyAPI на этом или другом компьютере. Подойдёт любой сервер с интерфейсом OpenAI. Ключ обычно не нужен.</small>`
        + `<div class="tl-form"><label>Адрес сервера<input id="ai-url" maxlength="300" value="${esc(S.local_url)}" autocomplete="off"></label><label>Ключ, если сервер его требует<input id="ai-key" type="password" maxlength="400" placeholder="${p.has_key ? 'Уже сохранён: оставьте пустым' : 'обычно не нужен'}" autocomplete="off"></label>`
        + `<div class="vc-actions">${btn('Сохранить', 'data-lsave="1"', 'primary')}${p.has_key ? btn('Удалить ключ', 'data-kclear="1"', 'tl-del') : ''}</div></div>`);
    }
    return U.card('var(--green)', 'shield', `Ключ ${esc(p.name)}`,
      `<div class="tl-status ${p.has_key ? 'tl-ok' : 'tl-warn'}">${p.has_key ? 'Ключ сохранён на этом компьютере' : 'Ключ не задан: ответы ИИ этого сервиса недоступны'}</div>`
      + `<small class="vc-note">Ключ хранится в файле секретов и никогда не показывается в окне. Вставьте новый, чтобы заменить.</small>`
      + `<div class="tl-form"><label>${p.has_key ? 'Новый ключ' : 'Ключ'}<input id="ai-key" type="password" maxlength="400" placeholder="Вставьте ключ" autocomplete="off"></label>`
      + `<div class="vc-actions">${btn('Сохранить ключ', 'data-ksave="1"', 'primary')}${p.has_key ? btn(askClear ? 'Точно удалить?' : 'Удалить ключ', 'data-kclear="1"', 'tl-del') : ''}</div></div>`);
  }
  function testCard() {
    return U.card('var(--amber)', 'check', 'Проверка связи',
      `<small class="vc-note">Отправит один короткий запрос через выбранный сервис и модель. Покажет, работает ли ключ, и за сколько приходит ответ. Расходует доли цента, если сервис платный.</small>`
      + `<div class="vc-actions">${btn(testing ? 'Проверяю…' : 'Проверить', `data-test="1"${testing ? ' disabled' : ''}`, 'primary')}</div><div id="ai-testres" class="tl-status"></div>`);
  }
  function styleCard() {
    const t = S.temperature, mt = S.max_tokens, local = S.provider === 'local';
    const seg = `<div class="seg2 ai-style" role="radiogroup" style="--n:3;--i:${Math.max(0, STYLES.findIndex((x) => Math.abs(x[1] - t) < 0.01 && x[2] === mt))}">${STYLES.map((x, i) => `<button type="button" class="${Math.abs(x[1] - t) < 0.01 && x[2] === mt ? 'on' : ''}" data-style="${i}" role="radio">${x[0]}</button>`).join('')}</div>`;
    return U.card('var(--mag, #cc44ff)', 'palette', 'Как отвечает ИИ',
      `<small class="vc-note">Готовые наборы или ручная настройка ниже.</small>${seg}`
      + U.slider('temp', 'Креативность', 0, 1, 0.05, t, t.toFixed(2), 'Меньше: точнее и суше. Больше: свободнее и разнообразнее.')
      + U.slider('maxtok', 'Длина ответа, токенов', 50, 2000, 10, mt, String(mt), 'Верхняя граница длины ответа. Голосом короткие ответы удобнее.')
      + (local ? U.slider('topk', 'Top-K (локальный сервер)', 1, 100, 1, S.top_k, String(S.top_k), 'Сколько вариантов слова рассматривать. Работает только у локальных серверов.') : ''));
  }
  const fmtN = (n) => Number(n).toLocaleString('ru-RU');
  const dayLab = (iso) => `${+iso.slice(8, 10)}.${iso.slice(5, 7)}`;
  const val = (d, prov, k) => (prov === 'all' ? d[k] : ((d.by[prov] || {})[k] || 0));
  function fallbackCard() {
    const f = S.fallback, nm = (id) => (S.providers.find((p) => p.id === id) || { name: id }).name, why = { limit: 'исчерпан лимит', error: 'не ответил' };
    const chain = [S.provider, ...f.order].slice(0, 4), flow = f.enabled ? `<div class="ai-flow">${chain.map((id, i) => `<span class="ai-fs${i === 0 ? ' main' : ''}"><i>${i + 1}</i>${esc(nm(id))}${i === 0 ? '<small>выбранный</small>' : ''}</span>`).join('<b class="ai-ar">→</b>')}</div>` : '';
    const ls = S.last_switch && S.last_switch.to ? `<div class="tl-status">Последний раз вместо ${esc(nm(S.last_switch.from))} ответил ${esc(nm(S.last_switch.to))} (${why[S.last_switch.reason] || 'не ответил'}), ${new Date(S.last_switch.at * 1000).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}.</div>` : '';
    return U.card('var(--amber)', 'warn', 'Если сервис не отвечает',
      '<small class="vc-note">Облачный ИИ иногда не отвечает: сбой сети, закончился лимит. Тогда Jarvis спросит другой сервис, у которого сохранён ключ, и скажет об этом вслух. Без запасного вопрос просто останется без ответа.</small>'
      + U.sw('fallback', 'Пробовать другой сервис', 'Порядок попыток показан ниже. Локальный сервер участвует, если задан его адрес.', f.enabled)
      + (f.enabled ? (f.order.length ? flow : '<div class="vc-note">Других сервисов с ключом пока нет: сохраните ключ ещё у одного сервиса или задайте адрес локального сервера.</div>') : '') + ls);
  }
  function usageCard() {
    const b = S.budget, nm = (id) => (S.providers.find((p) => p.id === id) || { name: id }).name, prim = b.primary, cur = b.usage.find((u) => u.id === prim) || { count: 0, tin: 0, tout: 0, limit: 0 };
    const M = { req: ['Запросы', 'запросов', b.limit || cur.limit, 'var(--cyan)'], in: ['Вход', 'токенов на вход', b.limit_in, 'var(--amber)'], out: ['Выход', 'токенов на выход', b.limit_out, 'var(--mag, #cc44ff)'] };
    const gauge = (k, v) => { const lim = M[k][2], pct = lim ? Math.min(100, Math.round(v / lim * 100)) : 0, col = pct >= 100 ? 'var(--red)' : pct >= 80 ? 'var(--amber)' : M[k][3];
      return `<div class="ai-g"><div class="md-lh"><span>${M[k][1][0].toUpperCase() + M[k][1].slice(1)}</span><b>${fmtN(v)}${lim ? ` из ${fmtN(lim)}` : ' · без лимита'}</b></div><div class="md-bar"><i style="width:${lim ? Math.max(2, pct) : 0}%;background:${col}"></i></div></div>`; };
    const provs = ['all', ...new Set([prim, ...b.days.flatMap((d) => Object.keys(d.by))])], cp = provs.includes(chartP) ? chartP : 'all', cm = chartM;
    const vals = b.days.map((d) => val(d, cp, cm)), lim = cp === 'all' || cp === prim ? M[cm][2] : 0, mx = Math.max(lim || 0, ...vals, 1), W = 560, H = 150, bw = W / 14, total = vals.reduce((x, y) => x + y, 0);
    const bars = b.days.map((d, i) => { const v = vals[i], h = v ? Math.max(2, v / mx * (H - 22)) : 0, over = lim && v >= lim, x = i * bw + 5;
      return `<g><title>${dayLab(d.date)}: ${fmtN(v)} ${M[cm][1]}</title><rect x="${x}" y="${H - 18 - h}" width="${bw - 10}" height="${h}" rx="3" fill="${over ? 'var(--red)' : M[cm][3]}" opacity="${i === 13 ? 1 : 0.62}"/><text x="${x + (bw - 10) / 2}" y="${H - 4}" text-anchor="middle" class="ai-tx">${dayLab(d.date).split('.')[0]}</text></g>`; }).join('');
    const limLine = lim ? `<line x1="0" x2="${W}" y1="${H - 18 - lim / mx * (H - 22)}" y2="${H - 18 - lim / mx * (H - 22)}" class="ai-lim"/><text x="${W - 2}" y="${H - 21 - lim / mx * (H - 22)}" text-anchor="end" class="ai-tx lim">лимит ${fmtN(lim)}</text>` : '';
    const chart = `<div class="ai-chart"><div class="ai-ctl"><div class="seg2 ai-cm" role="radiogroup" style="--n:3;--i:${['req', 'in', 'out'].indexOf(cm)}">${['req', 'in', 'out'].map((k) => `<button type="button" class="${cm === k ? 'on' : ''}" data-cm="${k}" role="radio" aria-checked="${cm === k}">${M[k][0]}</button>`).join('')}</div>`
      + `<select id="ai-cp" aria-label="Сервис">${provs.map((p) => `<option value="${p}"${p === cp ? ' selected' : ''}>${p === 'all' ? 'Все сервисы' : esc(nm(p))}</option>`).join('')}</select></div>`
      + `<svg viewBox="0 0 ${W} ${H}" class="ai-svg" role="img" aria-label="Расход за 14 дней">${limLine}${bars}</svg><div class="ai-ct"><span>За 14 дней: ${fmtN(total)} ${M[cm][1]}</span><span>Пик за день: ${fmtN(Math.max(0, ...vals))}</span></div></div>`;
    const inp = (id, lab, v, ph) => `<label class="ai-lf">${lab}<input id="${id}" type="number" min="0" value="${v}" placeholder="${ph}" aria-label="${lab}"></label>`;
    return U.card('var(--cyan)', 'timer', 'Расход и лимиты',
      '<small class="vc-note">Сколько ИИ расходует в день. Токен: кусочек текста, примерно 3–4 буквы. «Вход» — то, что Jarvis отправляет сервису (вопрос и история разговора), «выход» — ответ. Токены считаются по тексту, поэтому цифры приблизительные.</small>'
      + `<div class="ci-sub">Сегодня, ${esc(nm(prim))}</div>${gauge('req', cur.count)}${gauge('in', cur.tin)}${gauge('out', cur.tout)}`
      + chart
      + '<div class="ci-sub">Лимиты</div>'
      + U.sw('budget', 'Следить за лимитами', 'Когда израсходовано 80% лимита, Jarvis предупредит вслух. Когда лимит выбран, он ответит через запасной сервис (или локальный). Лимиты считаются для выбранного сервиса и сбрасываются в полночь.', b.enabled)
      + `<div class="ai-lims ${b.enabled ? '' : 'vc-dim'}">${inp('ai-lim', 'Запросов в день', b.limit, 'как у модели')}${inp('ai-lin', 'Токенов на вход', b.limit_in, 'без лимита')}${inp('ai-lout', 'Токенов на выход', b.limit_out, 'без лимита')}</div>`
      + `<small class="vc-note">0 — без лимита. Для запросов 0 значит «как указано у модели в списке», если там есть число.</small>`
      + `<div class="vc-actions">${btn('Сохранить лимиты', 'data-lims="1"', 'primary')}${btn('Сбросить счётчик за сегодня', 'data-ureset="1"')}</div>`);
  }
  function miscCard() {
    return U.card('var(--cyan)', 'grid', 'Дополнительно',
      U.sw('web_search', 'Поиск в интернете у OpenAI', 'Для OpenAI ответ строится с живым поиском по сети (используются модели search-preview). У остальных сервисов переключатель ничего не меняет.', S.web_search)
      + U.sw('mini_window', 'Окно с ответом ИИ', 'Показывать ответ в небольшом окне рядом с голосовым ответом.', S.mini_window));
  }
  function render() {
    if (!S) { root.innerHTML = '<div class="vc-note" style="padding:1rem">Загружаю…</div>'; return; }
    const keep = {}; for (const id of ['ai-cm', 'ai-url']) { const e = $(id); if (e && e.value) keep[id] = e.value; }
    root.innerHTML = `<div class="vc-grid"><div class="vc-col">${providerCard()}${keyCard()}${testCard()}</div><div class="vc-col">${styleCard()}${fallbackCard()}${usageCard()}${miscCard()}</div></div>`;
    for (const id in keep) if ($(id)) $(id).value = keep[id];
    if (window.fzDropdown) window.fzDropdown.watch(root);
  }

  root.addEventListener('input', (e) => {
    const r = e.target.closest('.vc-rng'); if (!r) return;
    const v = parseFloat(r.value); r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    const k = r.dataset.key, lab = root.querySelector(`[data-val="${k}"]`); if (lab) lab.textContent = k === 'temp' ? v.toFixed(2) : String(Math.round(v));
    const body = k === 'temp' ? { temperature: v } : k === 'maxtok' ? { max_tokens: Math.round(v / 10) * 10 } : { top_k: Math.round(v) };
    clearTimeout(timer); timer = setTimeout(() => act({ op: 'params', ...body }), 400);
  });
  root.addEventListener('change', (e) => { if (e.target.id === 'ai-model' && e.target.value) act({ op: 'model', id: e.target.value }); if (e.target.id === 'ai-cp') { chartP = e.target.value; render(); } });
  root.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' || !e.target.matches('input')) return; e.preventDefault();
    const b = { 'ai-cm': '[data-cmodel]', 'ai-key': '[data-ksave],[data-lsave]', 'ai-url': '[data-lsave]', 'ai-lim': '[data-lims]', 'ai-lin': '[data-lims]', 'ai-lout': '[data-lims]' }[e.target.id]; if (b) root.querySelector(b).click();
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return; const d = b.dataset;
    if (b.closest('.tgl') || d.sw) { if (d.sw === 'models_all') { const r = await act({ op: 'models_all', on: !b.classList.contains('on') }); if (r.ok) refresh(false); } else if (d.sw === 'fallback' || d.sw === 'budget') act(d.sw === 'budget' ? { op: 'budget', on: !b.classList.contains('on') } : { op: 'fallback', on: !b.classList.contains('on') }); else if (d.sw === 'web_search' || d.sw === 'mini_window') act({ op: d.sw, on: !b.classList.contains('on') }); return; }
    if (d.prov) { if (d.prov !== S.provider) { askClear = false; const r = await act({ op: 'provider', id: d.prov }); if (r.ok) refresh(true); } return; }
    if (d.cmodel) { const v = $('ai-cm').value.trim(); if (!v) { say('Введите название модели'); return; } const r = await act({ op: 'model', id: v }, 'Модель выбрана'); if (r.ok) $('ai-cm').value = ''; return; }
    if (d.lims) { act({ op: 'budget', limit: $('ai-lim').value || 0, limit_in: $('ai-lin').value || 0, limit_out: $('ai-lout').value || 0 }, 'Лимиты сохранены'); return; }
    if (d.cm) { chartM = d.cm; render(); return; }
    if (d.ureset) { act({ op: 'usage_reset' }, 'Счётчик сброшен'); return; }
    if (d.refresh) { refresh(false); return; }
    if (d.site) { if (m.connected) J.send('open_url', { url: d.site }); else say('Без ядра ссылку не открыть'); return; }
    if (d.style) { const x = STYLES[+d.style]; act({ op: 'params', temperature: x[1], max_tokens: x[2] }); return; }
    if (d.ksave) { const k = $('ai-key').value.trim(); if (!k) { say('Вставьте ключ'); return; } const r = await act({ op: 'key_save', provider: S.provider, key: k }, 'Ключ сохранён'); if (r.ok) refresh(false); return; }
    if (d.lsave) {
      const k = $('ai-key').value.trim(); let ok = true;
      const r = await act({ op: 'local_url', url: $('ai-url').value }, 'Адрес сохранён'); ok = r.ok;
      if (ok && k) ok = (await act({ op: 'key_save', provider: 'local', key: k }, 'Ключ сохранён')).ok;
      if (ok) refresh(false); return;
    }
    if (d.kclear) {
      if (!askClear) { askClear = true; render(); setTimeout(() => { if (askClear) { askClear = false; render(); } }, 5000); return; }
      askClear = false; act({ op: 'key_clear', provider: S.provider }, 'Ключ удалён'); return;
    }
    if (d.test) {
      testing = true; render(); const res = () => $('ai-testres'); if (res()) res().textContent = 'Жду ответ…';
      const r = await call({ op: 'test' }); testing = false; render();
      if (res()) { res().className = 'tl-status ' + (r.ok ? 'tl-ok' : 'tl-warn'); res().textContent = r.ok ? `Работает: ответ за ${(r.ms / 1000).toFixed(1)} с. Модель ответила: «${r.reply}»` : (r.error === 'offline' ? 'Без ядра проверить нельзя' : `${ERR[r.error] || 'Не получилось'}${r.ms ? ` (${(r.ms / 1000).toFixed(1)} с)` : ''}`); }
    }
  });

  window.renderAi = () => { askClear = false; status = ''; load().then(() => { if (m.connected && S) refresh(true); }); };   // the list is asked from the provider every time the tab opens
})();
