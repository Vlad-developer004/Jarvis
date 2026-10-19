// Settings > Modules: the feature profile (full / assistant / minimal), a switch for every module with a load estimate, the morning briefing and calendar reminders.
// Data comes from the `modules` bridge command (ui_next/bridge/modules.py); each change is saved at once and the core answers with the fresh state.
// Without a core the tab shows sample data and refuses changes. Relies on globals of app.html: $, J, m, ic, esc, and window.LOOK.ui from look.js.
(() => {
  const root = $('lk-mods'), U = window.LOOK.ui;
  const META = {
    qa: ['search', 'Ответы ИИ на вопросы', 'Вопросы к облачному ИИ. Нужен ключ провайдера.', 3],
    llm_chat_fallback: ['doc', 'Локальный ИИ как запасной', 'Если команда не распознана, отвечает офлайн, без интернета.', 2],
    games: ['pad', 'Игры', 'Игровой режим и профили игр. Пока он включён, работают только игровые команды, вопросы к ИИ и короткий список общих (громкость, яркость, медиа, таймеры, скриншот).', 4],
    cinema: ['cam', 'Кино', 'Что играет, перемотка, ваша библиотека, поиск в сервисах, даты серий и режим кино.', 1],
    system_monitoring: ['pc', 'Мониторинг системы', 'Процессор, память, диск и сеть на обзоре.', 3],
    battery_monitor: ['bell', 'Батарея', 'Заряд и предупреждения о низком уровне.', 1],
    lag_hunter: ['timer', 'Охотник за лагами', 'Ищет причины задержек и просадок производительности.', 2],
    morning_briefing: ['home', 'Утренняя сводка', 'Время, погода и дела на сегодня одной фразой.', 1],
    updater: ['ext', 'Обновления', 'Проверка и установка новых версий Jarvis.', 1],
    network_profiles: ['shield', 'Сетевые профили', 'Профили сети и VPN.', 1],
    system_health: ['grid', 'Состояние дисков', 'Отчёт о здоровье дисков.', 1],
    calendar_ics: ['cal', 'Календарь', 'События, напоминания вслух и создание событий голосом.', 1],
    inbox_digest: ['mail', 'Проверка почты', 'Сводка новых писем.', 1],
    git_integration: ['list', 'Git', 'Голосовые команды git: коммит и другие.', 1],
    translator: ['user', 'Переводчик', 'Голосовой перевод речи.', 1],
    song_id: ['music', 'Распознавание музыки', 'Что за песня: по микрофону или по звуку с компьютера.', 1],
  };
  const PROFILES = { full: ['Полный', 'Все функции', 'Максимум возможностей: ИИ-поиск, игры (ETS2, Planetbase и другие), медиа-автоматизация, глубокий мониторинг. Больше всего нагрузка на память и процессор.'],
    assistant: ['Ассистент', 'Без ИИ, игр и кино', 'Сбалансированный для повседневных дел: тяжёлые игровые и медиа-модули выключены, умный ассистент остаётся.'],
    minimal: ['Минимальный', 'Самый лёгкий', 'Только ядро распознавания речи и управление окнами. Самый быстрый отклик и минимум памяти.'] };
  const BRIEF = [['include_greeting', 'Приветствие'], ['include_time', 'Время'], ['include_weather', 'Погода'], ['include_battery', 'Батарея'], ['include_system_load', 'Нагрузка системы'], ['include_calendar', 'Календарь'], ['include_mail_unread', 'Непрочитанная почта']];
  const DEMO = { ok: true, profile: 'minimal', profiles: ['full', 'assistant', 'minimal'], modules: Object.keys(META).map((k) => ({ key: k, on: ['system_monitoring', 'battery_monitor'].includes(k), preset: ['system_monitoring', 'battery_monitor'].includes(k), manual: false })),
    briefing: { include_greeting: true, include_time: true, include_weather: true, include_battery: true, include_system_load: true, include_calendar: true, include_mail_unread: true, calendar_reminder_minutes: 15, calendar_reminders_enabled: true } };
  const ERR = { bad_value: 'Значение не подошло', write_failed: 'Не удалось сохранить', failed: 'Не получилось', no_handler: 'Jarvis ещё запускается' };
  let S = null, restartNote = false, askRestart = false, timer = 0;

  async function call(body) { if (!m.connected) { U.say('Без ядра изменить нельзя'); return { ok: false, error: 'offline' }; } return (await J.send('modules', body)) || { ok: false }; }
  async function act(body) {
    const r = await call(body);
    if (r.ok) { S = r; render(); } else if (r.error !== 'offline') { U.say(ERR[r.error] || 'Не получилось сохранить'); load(); }
    return r;
  }
  async function load() { if (!m.connected) { S = DEMO; render(); return; } const r = await call({ op: 'state' }); if (r.ok) { S = r; render(); } }

  const score = () => S.modules.reduce((n, x) => n + (x.on ? META[x.key][3] : 0), 0);
  const level = (n) => (n <= 4 ? ['Низкая', 'var(--green)'] : n <= 9 ? ['Средняя', 'var(--amber)'] : ['Высокая', 'var(--red)']);
  const MAXSCORE = Object.values(META).reduce((n, x) => n + x[3], 0);

  function profileCard() {
    const note = restartNote ? `<div class="md-note"><span>Профиль сохранён. Чтобы он применился полностью, перезапустите Jarvis.</span><button type="button" class="cm-try${askRestart ? ' tl-del' : ''}" data-restart="1">${askRestart ? 'Точно перезапустить?' : 'Перезапустить'}</button></div>` : '';
    return U.card('var(--green)', 'ext', 'Профиль',
      `<small class="vc-note">Профиль задаёт, какие модули включены по умолчанию. Отдельные модули ниже можно переключить вручную.</small>`
      + `<div class="vc-choice" role="radiogroup">${S.profiles.map((p) => `<button type="button" class="vc-opt${S.profile === p ? ' on' : ''}" data-profile="${p}" role="radio" aria-checked="${S.profile === p}"><b>${PROFILES[p][0]}</b><small>${PROFILES[p][1]}</small></button>`).join('')}</div>`
      + `<div class="vc-prev">${esc(PROFILES[S.profile][2])}</div>${note}`);
  }
  function modulesCard() {
    const sc = score(), [lv, col] = level(sc), manual = S.modules.some((x) => x.manual);
    const tiles = S.modules.map((x) => { const [icon, title, desc] = META[x.key]; return `<div class="md-t${x.on ? ' on' : ''}"><span class="md-ic">${ic(icon, x.on ? 'var(--green)' : 'var(--dim)', 18)}</span><div class="md-b"><b>${esc(title)}${x.manual ? `<em title="Отличается от профиля «${esc(PROFILES[S.profile][0])}»">вручную</em>` : ''}</b><small>${esc(desc)}</small></div><button type="button" class="tgl${x.on ? ' on' : ''}" data-mod="${x.key}" aria-pressed="${x.on}" aria-label="${esc(title)}"><span class="sw"></span></button></div>`; }).join('');
    return U.card('var(--cyan)', 'grid', 'Модули',
      `<div class="md-load"><div class="md-lh"><span>Нагрузка на компьютер</span><b style="color:${col}">${lv}</b></div><div class="md-bar"><i style="width:${Math.max(4, Math.round(sc / MAXSCORE * 100))}%;background:${col}"></i></div>`
      + `<small>Оценка по включённым модулям. Чем больше включено, тем больше занято памяти и процессора.</small></div>`
      + `<div class="md-grid">${tiles}</div>` + (manual ? `<div class="vc-actions"><button type="button" class="cm-try" data-reset="1">Вернуть как в профиле</button><small>Сбросит переключатели, которые вы меняли вручную.</small></div>` : ''));
  }
  function briefCard() {
    const b = S.briefing;
    return U.card('var(--amber)', 'home', 'Утренняя сводка', `<small class="vc-note">Что Jarvis говорит в сводке «что сегодня».</small>` + BRIEF.map(([k, t]) => U.sw('b_' + k, t, '', b[k])).join(''));
  }
  function remindCard() {
    const b = S.briefing, on = b.calendar_reminders_enabled;
    return U.card('var(--mag, #cc44ff)', 'cal', 'Напоминания о событиях',
      U.sw('b_calendar_reminders_enabled', 'Напоминать вслух', 'Jarvis скажет о ближайшем событии календаря заранее. Для события можно задать своё время в самом календаре.', on)
      + `<div class="${on ? '' : 'vc-dim'}">${U.slider('lead', 'За сколько минут напомнить', 1, 120, 1, b.calendar_reminder_minutes, `${b.calendar_reminder_minutes} мин`)}</div>`);
  }
  function render() {
    if (!S) { root.innerHTML = '<div class="vc-note" style="padding:1rem">Загружаю…</div>'; return; }
    root.innerHTML = `<div class="vc-grid"><div class="vc-col">${profileCard()}${briefCard()}${remindCard()}</div><div class="vc-col md-wide">${modulesCard()}</div></div>`;
  }

  root.addEventListener('input', (e) => {
    const r = e.target.closest('.vc-rng'); if (!r || r.dataset.key !== 'lead') return;
    const v = parseFloat(r.value); r.style.setProperty('--p', `${((v - r.min) / (r.max - r.min)) * 100}%`);
    const lab = root.querySelector('[data-val="lead"]'); if (lab) lab.textContent = `${Math.round(v)} мин`;
    clearTimeout(timer); timer = setTimeout(() => act({ op: 'briefing', key: 'calendar_reminder_minutes', value: Math.round(v) }), 400);
  });
  root.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return; const d = b.dataset;
    if (d.profile) { if (d.profile !== S.profile) { const r = await act({ op: 'profile', profile: d.profile }); if (r.ok) { restartNote = true; askRestart = false; render(); } } return; }
    if (d.mod) { act({ op: 'module', key: d.mod, on: !b.classList.contains('on') }); return; }
    if (d.reset) { act({ op: 'reset' }); return; }
    if (d.sw && d.sw.startsWith('b_')) { act({ op: 'briefing', key: d.sw.slice(2), value: !b.classList.contains('on') }); return; }
    if (d.restart) {
      if (!askRestart) { askRestart = true; render(); setTimeout(() => { if (askRestart) { askRestart = false; render(); } }, 5000); return; }
      const r = await call({ op: 'restart' }); if (r.ok) U.say('Jarvis перезапускается…'); else if (r.error !== 'offline') U.say('Не удалось перезапустить'); askRestart = false;
    }
  });

  window.renderModules = () => { restartNote = false; askRestart = false; load(); };
})();
