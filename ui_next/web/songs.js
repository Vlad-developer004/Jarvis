// Songs screen: the history of recognized songs (Shazam / AudD) with cover, links to streaming services and a "listen now" button.
// Data: topic `songs` ({songs:[{id, title, artist, album, at, source, cover, links}], total}); commands `song_open`, `song_clear`, `run` (song_id).
// Without a core it shows a local demo. Relies on globals of app.html: $, J, m, ic, C, esc, VIEW.
(() => {
  const NOW = Date.now() / 1000;
  const DEMO = [
    { id: 'd1', title: 'Птичка', artist: 'HammAli & Navai', album: '', at: NOW - 3600, source: 'shazam', cover: '', links: ['spotify', 'apple', 'youtube'] },
    { id: 'd2', title: 'Ночь', artist: 'Андрей Губин', album: '', at: NOW - 86400 * 2, source: 'shazam', cover: '', links: ['apple', 'youtube'] },
    { id: 'd3', title: 'Panda E', artist: 'Desiigner', album: '', at: NOW - 86400 * 12, source: 'audd', cover: '', links: ['spotify', 'youtube'] },
  ];
  const SERVICE = { spotify: 'Spotify', apple: 'Apple Music', youtube: 'YouTube' };
  const MONTHS = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
  const body = $('sg-body'), toast = $('sg-toast');
  let confirmClear = false, toastTimer = 0, listening = false, demo = DEMO.map((s) => ({ ...s }));
  const data = () => (m.connected ? (m.songs ? m.songs.songs : null) : demo);
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); };
  const pl = (n, f) => `${n} ${n % 10 === 1 && n % 100 !== 11 ? f[0] : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? f[1] : f[2]}`;
  const p2 = (n) => String(n).padStart(2, '0');
  // the history is grouped by day: a heading ("Сегодня", "Вчера", "18 октября") and only the time on the card
  const hm = (ts) => { const d = new Date(ts * 1000); return `${p2(d.getHours())}:${p2(d.getMinutes())}`; };
  function day(ts) {
    const d = new Date(ts * 1000), t = new Date();
    const days = Math.round((new Date(t.getFullYear(), t.getMonth(), t.getDate()) - new Date(d.getFullYear(), d.getMonth(), d.getDate())) / 86400000);
    if (days <= 0) return 'Сегодня';
    if (days === 1) return 'Вчера';
    return `${d.getDate()} ${MONTHS[d.getMonth()]}${d.getFullYear() !== t.getFullYear() ? ' ' + d.getFullYear() : ''}`;
  }
  const okCover = (c) => /^data:image\/jpeg;base64,[A-Za-z0-9+/=]+$/.test(c || '');
  const hue = (s) => { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 360; return h; };

  function card(s) {
    const cover = okCover(s.cover) ? `<img alt="" src="${s.cover}">` : ic('music', 'currentColor', 26);
    const links = s.links.filter((k) => SERVICE[k]).map((k) => `<button type="button" class="sg-link" data-open="${esc(s.id)}" data-svc="${k}">${SERVICE[k]}</button>`).join('');
    const bg = okCover(s.cover) ? `<i class="sg-bg" style="--bg:url('${s.cover}')"></i>` : '';
    return `<div class="cm-card sg-card" style="--gh:${hue(s.title + s.artist)}">${bg}<span class="sg-cover${okCover(s.cover) ? ' has' : ''}">${cover}</span>
      <div class="sg-txt"><b title="${esc(s.title)}">${esc(s.title || 'Без названия')}</b><span class="sg-art">${esc(s.artist)}</span>
      <small class="sg-meta"><span>${hm(s.at)}</span>${s.source ? `<span class="sg-src">${s.source === 'audd' ? 'AudD' : 'Shazam'}</span>` : ''}</small>
      <div class="sg-links">${links}</div></div></div>`;
  }

  function render() {
    const l = data(), total = m.connected && m.songs ? m.songs.total : l ? l.length : 0;
    $('sg-count').textContent = l ? (l.length ? pl(total, ['песня', 'песни', 'песен']) : '') + (m.connected ? '' : (l.length ? ' · ' : '') + 'пример, ядро не подключено') : '';
    $('sg-clear').style.display = l && l.length ? '' : 'none';
    $('sg-clear').textContent = confirmClear ? 'Точно очистить?' : 'Очистить историю';
    $('sg-clear').classList.toggle('danger', confirmClear);
    $('sg-now').disabled = listening; $('sg-now').textContent = listening ? 'Слушаю…' : 'Узнать песню';
    if (!l) { body.innerHTML = '<div class="rm-empty"><b>Загружаю историю…</b>Список придёт от Jarvis через секунду.</div>'; return; }
    if (!l.length) { body.innerHTML = '<div class="rm-empty"><b>Песен пока нет</b>Включите музыку и скажите «Джарвис, что за песня играет», либо нажмите «Узнать песню». Найденные песни сохранятся здесь со ссылками на Spotify, Apple Music и YouTube.</div>'; return; }
    let last = '', html = '';
    for (const s of l) { const d = day(s.at); if (d !== last) { html += `${last ? '</div>' : ''}<h3 class="sg-day">${d}</h3><div class="sg-grid">`; last = d; } html += card(s); }
    body.innerHTML = `${html}</div>` + (m.connected && total > l.length ? `<p class="sg-more">Показаны последние ${l.length} из ${total}</p>` : '');
  }

  body.addEventListener('click', async (e) => {
    const t = e.target.closest('button[data-open]'); if (!t) return;
    if (!m.connected) { say('Демо: здесь откроется ' + SERVICE[t.dataset.svc]); return; }
    const r = await J.send('song_open', { id: t.dataset.open, service: t.dataset.svc });
    say(r && r.ok ? 'Открываю в браузере' : 'Не удалось открыть ссылку');
  });
  $('sg-clear').onclick = async () => {
    if (!confirmClear) { confirmClear = true; render(); setTimeout(() => { if (confirmClear) { confirmClear = false; render(); } }, 3500); return; }
    confirmClear = false;
    if (m.connected) await J.send('song_clear', {}); else demo = [];
    say('История очищена'); render();
  };
  $('sg-now').onclick = async () => {
    if (!m.connected) { say('Демо: Jarvis послушает музыку несколько секунд и покажет результат'); return; }
    listening = true; render();
    const r = await J.send('run', { id: 'song_id' });
    setTimeout(() => { listening = false; if (VIEW === 'songs') render(); }, 20000);
    say(r && r.ok ? 'Слушаю музыку, результат появится здесь и прозвучит голосом' : 'Не получилось запустить: Jarvis ещё запускается');
  };
  J.on('songs', () => { if (VIEW === 'songs') { listening = false; render(); } });
  J.on('live', () => { if (VIEW === 'songs') render(); });
  window.renderSongs = render;
})();
