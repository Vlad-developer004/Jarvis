// Shared mock model + Tauri/demo adapter for the design variants (a.html, b.html, c.html).
// Real: cpu/ram/disk/net from Rust events and the state cycle. Mock: transcript, reminders, models.
const J = (() => {
  const STATE_RU = { IDLE: 'Ожидание', LISTENING: 'Слушаю', SPEAKING: 'Говорю' };
  const hm = (d) => d.toTimeString().slice(0, 5), ago = (min) => hm(new Date(Date.now() - min * 60000)), inn = (min) => hm(new Date(Date.now() + min * 60000));
  const model = {
    state: 'IDLE', heard: '', reply: '', level: 0,
    sensors: { cpu: 0, ram: 0, disk: 0, down: 0, up: 0 },
    log: [
      { t: ago(95), said: 'какой сегодня день', did: 'Пятница, 16 октября', kind: 'info' },
      { t: ago(70), said: 'включи музыку', did: 'Играет плейлист «Фокус»', kind: 'app' },
      { t: ago(36), said: 'поставь таймер на десять минут', did: 'Таймер на 10 минут запущен', kind: 'timer' },
      { t: ago(33), said: 'какая погода в Киеве', did: '+18°, облачно', kind: 'info' },
      { t: ago(30), said: 'открой календарь', did: 'Календарь открыт', kind: 'app' },
    ],
    upcoming: [
      { t: inn(8), label: 'Таймер', note: 'осталось 07:42', kind: 'timer' },
      { t: inn(65), label: 'Созвон', note: 'напоминание', kind: 'reminder' },
      { t: inn(190), label: 'Игровая сессия', note: 'профиль ETS2', kind: 'game' },
    ],
    modes: [{ k: 'mic', ru: 'Микрофон', on: true }, { k: 'game', ru: 'Игровой режим', on: false }, { k: 'night', ru: 'Ночной режим', on: false }, { k: 'quiet', ru: 'Тихий режим', on: false }],
    models: [{ ru: 'Распознавание', v: 'Vosk', ok: true }, { ru: 'Голос', v: 'Silero', ok: true }, { ru: 'Локальная LLM', v: 'подключена', ok: true }, { ru: 'Groq', v: 'отключён', ok: false }],
  };
  const SCRIPT = { heard: 'включи игровой режим', reply: 'Игровой режим включён' };
  const subs = new Proxy({}, { get: (t, k) => (t[k] ||= []) });
  const live = { checked: false, on: false };
  let typeTimer = null;
  const emit = (k) => subs[k].forEach((f) => f(model));

  function setState(s) {
    model.state = s; clearInterval(typeTimer);
    if (s === 'LISTENING') { model.heard = ''; model.reply = ''; let i = 0; typeTimer = setInterval(() => { model.heard = SCRIPT.heard.slice(0, ++i); emit('heard'); if (i >= SCRIPT.heard.length) clearInterval(typeTimer); }, 130); }
    if (s === 'SPEAKING') { model.heard = SCRIPT.heard; model.reply = SCRIPT.reply; }
    if (s === 'IDLE') { model.heard = ''; model.reply = ''; }
    emit('state'); emit('heard');
  }
  // synthetic voice level (0..1) for the visualisations
  function level(t) {
    if (live.on && model.connected) return model.level;
    const base = { IDLE: 0.04, LISTENING: 0.45, SPEAKING: 0.8 }[model.state] || 0.04;
    return Math.max(0, Math.min(1, base * (0.55 + 0.45 * Math.abs(Math.sin(t * 5.1) * Math.sin(t * 1.7 + 1)))));
  }

  // ---- live feed from the Python core: Server-Sent Events from ui_next/bridge (address and token come from a discovery file read by the shell) ----
  function applyLive(topic, d) {
    if (topic === 'state') {
      model.loading = d.mode === 'LOADING'; model.state = model.loading ? 'IDLE' : d.mode;
      if (model.state === 'LISTENING') { model.heard = ''; model.reply = ''; }   // a new utterance starts; the previous phrase stays until then (IDLE shows the hint anyway)
      emit('state'); emit('heard');
    } else if (topic === 'heard') { model.heard = d.text; emit('heard');
    } else if (topic === 'reply') { model.reply = d.text; emit('heard');
    } else if (topic === 'level') { model.level = d.v;    } else if (topic === 'extensions') { model.extensions = d; emit('extensions');
    } else if (topic === 'voice_llm') { model.voiceLlm = d; emit('voice_llm');
    } else if (topic === 'voice_cal') { model.voiceCal = d; emit('voice_cal');
    } else if (topic === 'perf') { model.perf = d; emit('perf');
    } else if (topic === 'lang') { model.lang = d.language; emit('lang');
    } else if (topic === 'songs') { model.songs = d; emit('songs');
    } else if (topic === 'library') { model.library = d; emit('library');
    } else if (topic === 'game') { model.game = d.on; model.gameProfile = d.profile || ''; emit('game');
    } else if (topic === 'uicmd') { model.uicmd = d; emit('uicmd');
    } else if (topic === 'guard') { model.guard = !!d.on; emit('guard');
    } else if (topic === 'notices') { model.notices = d; emit('notices');
    } else if (topic === 'history') { model.history = d; emit('history');
    } else if (topic === 'catalog') { model.catalog = d; emit('catalog');
    } else if (topic === 'muted') { model.muted = d.on; emit('muted');
    } else if (topic === 'mic') { model.mic = d; emit('mic');
    } else if (topic === 'speech') { model.speechTs = d.ts; emit('speech');
    } else if (topic === 'autostart') { model.autostart = d.on; emit('autostart');
    } else if (topic === 'timers') { model.timers = d; emit('timers');
    } else if (topic === 'weather') { model.weather = d; emit('weather');
    } else if (topic === 'nowplaying') { model.np = d; emit('nowplaying'); } else if (topic === 'answer') { model.answer = d; emit('answer'); } else if (topic === 'prompt') { model.prompt = d; emit('prompt'); } else if (topic === 'prompt_cmd') { model.promptCmd = d; emit('prompt_cmd'); }
  }
  // UI -> core command (whitelisted on the Python side); resolves to the JSON reply or null when there is no core
  async function send(cmd, data = {}) {
    if (!live.on || !live.info || !model.connected) return null;
    try {
      const r = await fetch(`http://127.0.0.1:${live.info.port}/cmd?token=${encodeURIComponent(live.info.token)}`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ cmd, ...data }) });
      return r.ok ? await r.json() : null;
    } catch (e) { return null; }
  }
  async function connectLive(core) {
    for (;;) {
      let info = null; try { const txt = await core.invoke('bridge_info'); info = txt ? JSON.parse(txt) : null; } catch (e) {}
      live.checked = true;
      if (!info) { if (live.on) { live.on = false; model.connected = false; emit('conn'); } await new Promise((r) => setTimeout(r, 3000)); continue; }
      live.info = info;
      if (!live.on) { live.on = true; emit('live'); }
      await new Promise((resolve) => {
        const es = new EventSource(`http://127.0.0.1:${info.port}/events?token=${encodeURIComponent(info.token)}`);
        for (const t of ['uicmd', 'guard', 'lang', 'perf', 'prompt', 'prompt_cmd', 'answer', 'state', 'heard', 'reply', 'level', 'game', 'library', 'songs', 'voice_cal', 'voice_llm', 'extensions', 'notices', 'history', 'weather', 'timers', 'mic', 'speech', 'autostart', 'catalog', 'muted', 'nowplaying']) es.addEventListener(t, (e) => { try { applyLive(t, JSON.parse(e.data)); } catch (x) {} });
        es.onopen = () => { model.connected = true; emit('conn'); };
        es.onerror = () => { model.connected = false; emit('conn'); es.close(); setTimeout(resolve, 2000); };   // core restarted: re-read the discovery file
      });
    }
  }
  const clock = () => new Date().toLocaleTimeString('ru-RU');

  if (window.__TAURI__) {
    const { event, core } = window.__TAURI__;
    event.listen('sensors', (e) => { model.sensors = e.payload; emit('sensors'); });
    event.listen('state', (e) => { if (live.checked && !live.on && !(window.NX && (window.NX.has('idle') || window.NX.has('speak')))) setState(e.payload); });   // the Rust shell's demo state cycle; ignored while a core is connected
    connectLive(core);
  } else {
    live.checked = true;
    setInterval(() => { const want = window.NX && window.NX.has('idle') ? 'IDLE' : ['IDLE', 'LISTENING', 'SPEAKING'][Math.floor(Date.now() / 4000) % 3]; if (want !== model.state) setState(want); }, 500);
    setInterval(() => { model.sensors = { cpu: 8 + Math.random() * 10, ram: 63, disk: 79, down: 12, up: 3 }; emit('sensors'); }, 1000);
  }
  return { model, send, STATE_RU, on: (k, f) => subs[k].push(f), level, clock, setState };
})();
