// Main script of the window page (app.html): shared helpers, layout, notices, weather, sensors and view switching.
// Loaded as a classic script at the place it used to be inline, so the globals it declares ($, J, m, ic, P, esc, ...) are the same for the later scripts.
const $ = (id) => document.getElementById(id), m = J.model, html = document.documentElement;
const C = { cyan: hsl2hex(THEME.h - 8, 100 * THEME.sk, 59), star: hsl2hex(THEME.h - 5, 100 * THEME.sk, 87), green: '#3df5ac', amber: '#ffb347', red: '#ff6b6b', purple: '#a98bff', mag: '#ff3fd0', yel: '#ffd21f' };
let micMuted = false, VIEW = 'dash'; const DIMCOL = '#6f8396'; let coreTint = ''; const curCol = () => (micMuted ? DIMCOL : (coreTint || SC[m.state] || SC.IDLE));
const SC = { IDLE: C.cyan, LISTENING: C.cyan, SPEAKING: C.star }, SRU = { IDLE: 'ОЖИДАНИЕ', LISTENING: 'СЛУШАЮ', SPEAKING: 'ГОВОРЮ' };
const P = { home: 'M3 11l9-8 9 8v10h-6v-6H9v6H3z', mic: 'M9 3h6v9l-2 2h-2l-2-2zM5 11v2l4 4h6l4-4v-2M12 17v4M8 21h8', list: 'M4 6h16M4 12h16M4 18h10',
  bell: 'M12 3l5 4v6l3 4H4l3-4V7zM9 20h6', cal: 'M4 5h16v16H4zM4 10h16M8 3v4M16 3v4', play: 'M8 5v14l11-7z', music: 'M9 18V5l10-2v13M9 18l-3 2-3-2 3-2zM19 16l-3 2-3-2 3-2z', mail: 'M3 5h18v14H3zM3 5l9 8 9-8', pad: 'M7 7h10l4 4v3l-2 4h-3l-2-3h-4l-2 3H5l-2-4v-3zM8.5 10v4M6.5 12h4M15.5 10.5h.6M17.5 12.5h.6',
  ext: 'M4 8h5V4h4v4h5v5h-4v4h4v3H4z', gear: 'M12 2l8 4.5v9L12 22l-8-6.5v-9zM12 9l3 1.7v3.6L12 16l-3-1.7v-3.6z', timer: 'M12 4l8 4v8l-8 4-8-4V8zM12 8v5l3 2M9 1h6', search: 'M10 3l5 2 2 5-2 5-5 2-5-2-2-5 2-5zM16 16l5 5', check: 'M4 12l5 5L20 6', warn: 'M12 3l10 18H2zM12 10v5M12 18v1', theme: 'M12 3l9 5v8l-9 5-9-5V8zM12 12l9-4M12 12v9M12 12L3 8', cam: 'M3 7h4l2-3h6l2 3h4v13H3zM9 13l3-3 3 3-3 3z', shield: 'M12 2l8 3v7l-8 10-8-10V5z', chip: 'M7 7h10v10H7zM10 2v3M14 2v3M10 19v3M14 19v3M2 10h3M2 14h3M19 10h3M19 14h3' };
const ic = (k, col = 'currentColor', s = 20) => `<svg viewBox="0 0 24 24" width="${s}" height="${s}" fill="none" stroke="${col}" stroke-width="1.8" stroke-linecap="square" stroke-linejoin="miter"><path d="${P[k]}"/></svg>`;
const hmDate = (t) => { const [h, mm] = t.split(':').map(Number), d = new Date(); d.setHours(h, mm, 0, 0); return d; };
/* times arrive as HH:MM, so a day boundary has to be inferred: a past time that is "ahead" of the clock was yesterday, a future time that is "behind" it is tomorrow */
const mins = (t) => { const d = hmDate(t); if (d < Date.now() - 30000) d.setDate(d.getDate() + 1); return Math.max(0, Math.round((d - Date.now()) / 60000)); },
  ago = (t) => { const d = hmDate(t); if (d > Date.now() + 30000) d.setDate(d.getDate() - 1); const x = Math.max(0, Math.round((Date.now() - d) / 60000)); return x < 60 ? x + ' мин назад' : x < 1440 ? Math.floor(x / 60) + ' ч назад' : 'вчера'; };
const rel = (x) => x < 60 ? `через ${x} мин` : `через ${Math.floor(x / 60)} ч ${x % 60 ? (x % 60) + ' мин' : ''}`;
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };

// ---- thresholds in rem (OS scaling and user zoom are accounted for automatically) ----
const TIERS = [{ name: 'mini', maxRemW: 52 }, { name: 'compact', maxRemW: 72 }, { name: 'standard', maxRemW: 100 }, { name: 'wide', maxRemW: Infinity }]; const SHORT_REM_H = 38, SCALE_EXP = 0.8, SCALE_MIN = 0.85, SCALE_MAX = 2.3, MIN_ROOT_PX = 13;   // MIN_ROOT_PX: the smallest text stays readable at any window size and zoom
let userScale = 1; try { userScale = Math.min(1.6, Math.max(.8, +localStorage.getItem('uiScale') || 1)); } catch (e) {}
function layout() { const W = innerWidth, H = innerHeight, k = Math.min(SCALE_MAX, Math.max(SCALE_MIN, Math.min(W / 1280, H / 720))); const px = Math.max(MIN_ROOT_PX, 16 * Math.pow(k, SCALE_EXP) * userScale); html.style.fontSize = px.toFixed(2) + 'px';
  const remW = W / px, remH = H / px, tier = TIERS.find((t) => remW < t.maxRemW).name; html.dataset.tier = tier; html.dataset.short = remH < SHORT_REM_H ? '1' : '0';
  $('dbg').textContent = `${tier} · ${W}×${H}px · ${remW.toFixed(0)}×${remH.toFixed(0)}rem · ${px.toFixed(1)}px · зум ${Math.round(userScale * 100)}%${demoT !== null ? ' · демо-время ' + fmtT(demoT) : ''}${WX.cond !== 'partly' ? ' · погода: ' + WX.cond : ''}`;
  requestAnimationFrame(() => { fitRows($('hist')); fitSide(); fitNav(); fitHero(); sizeCanvas(); sizeSky(); sizeCam(); }); }
/* the lower part of the hero (what you said, the reply, the player, the wave) may take at most 45% of its height; otherwise the least important parts go, one by one */
function fitHero() { const hero = $('hero'), foot = hero.querySelector('.foot'); if (!foot) return; hero.removeAttribute('data-fit'); const off = [];
  for (const s of ['np', 'wave', 'reply']) { if (foot.offsetHeight <= hero.clientHeight * 0.45) break; off.push(s); hero.dataset.fit = off.join(' '); } }
if (window.ResizeObserver) new ResizeObserver(() => fitHero()).observe(document.querySelector('#hero .foot'));
function fitRows(el) { const rows = [...el.children]; rows.forEach((r) => (r.style.display = '')); for (let i = rows.length - 1; i > 0 && el.scrollHeight > el.clientHeight + 1; i--) rows[i].style.display = 'none'; }
function fitNav() { const nav = $('nav'), card = nav.querySelector('.offl'), parts = ['mrow-off', 'lv', 'mrow-auto', 'kv'].map((id) => $(id)); const over = () => nav.scrollHeight > nav.clientHeight + 2;
  parts.forEach((e) => e && (e.style.display = '')); if (card) card.style.display = ''; nav.classList.remove('tight', 'scroll');
  if (html.dataset.tier === 'mini') return;
  if (html.dataset.tier === 'compact') { if (over()) nav.classList.add('tight', 'scroll'); return; }
  /* order: tighter menu rows, then drop the card's optional parts one by one, then the whole card */
  if (over()) nav.classList.add('tight');
  for (const e of parts) { if (!over()) break; if (e) e.style.display = 'none'; }
  if (over() && card) card.style.display = 'none';
  if (over()) nav.classList.add('scroll'); }      /* a very short window: the menu scrolls, nothing is lost */
function fitSide() { const side = $('side'), order = [document.querySelector('.cam'), document.querySelector('.wxp')]; order.forEach((p) => p && (p.style.display = '')); if (html.dataset.tier === 'mini') return;
  const clipped = () => [...side.children].some((p) => getComputedStyle(p).display !== 'none' && p.scrollHeight > p.clientHeight + 3);   // a panel whose content is cut off is worse than a hidden one
  for (const p of order) { if (side.scrollHeight <= side.clientHeight + 2 && !clipped()) break; if (getComputedStyle(p).display !== 'none') p.style.display = 'none'; } }
addEventListener('resize', layout);
const fmtT = (min) => String(Math.floor(min / 60)).padStart(2, '0') + ':' + String(Math.round(min % 60)).padStart(2, '0');
let demoT = null, problem = false; const DEMO_TIMES = [null, 6 * 60 + 10, 12 * 60, 18 * 60 + 40, 23 * 60 + 30], CONDS = ['partly', 'clear', 'cloudy', 'rain', 'snow'];
addEventListener('keydown', (e) => { const z = (d) => { userScale = Math.min(1.6, Math.max(.8, +(userScale + d).toFixed(2))); try { localStorage.setItem('uiScale', userScale); } catch (x) {} layout(); e.preventDefault(); };
  if (e.ctrlKey && (e.key === '+' || e.key === '=')) z(.1); else if (e.ctrlKey && e.key === '-') z(-.1); else if (e.ctrlKey && e.key === '0') { userScale = 1; try { localStorage.setItem('uiScale', 1); } catch (x) {} layout(); e.preventDefault(); }
  else if (e.key === 'x' || e.key === 'ч') { problem = !problem; setNotice('mic', problem ? { sev: 'err', text: 'Микрофон не отвечает — проверьте подключение' } : null); }
  else if (e.key === 'n' || e.key === 'т') { setNotice('mail', { sev: 'info', text: 'Почта: 3 новых письма' }); setNotice('bat', { sev: 'warn', text: 'Низкий заряд батареи — 14%' }); setNotice('timer', { sev: 'info', text: 'Таймер на 10 минут запущен' }); }
  else if (e.key === 't' || e.key === 'е') { demoT = DEMO_TIMES[(DEMO_TIMES.indexOf(demoT) + 1) % DEMO_TIMES.length]; layout(); } else if (e.key === 'w' || e.key === 'ц') { WX.cond = CONDS[(CONDS.indexOf(WX.cond) + 1) % CONDS.length]; layout(); } });
addEventListener('wheel', (e) => { if (e.ctrlKey) e.preventDefault(); }, { passive: false });

// ---- static content ----
const NAVKEY = { 'Настройки': 'look', 'Обзор': 'dash', 'Команды': 'commands', 'Напоминания': 'rems', 'Игры': 'games', 'Расширения': 'exts', 'Песни': 'songs', 'Видео': 'videos', 'Голос': 'voice', 'Почта': 'mail', 'Календарь': 'calendar', 'Кино': 'cinema', 'Система': 'perf' };
$('nav').innerHTML = `<div class="logo"><i></i><div class="lb"><b>JARVIS</b><small>центр управления</small></div></div>` + [['home', 'Обзор', 0], ['mic', 'Голос', 0], ['list', 'Команды', 0], ['bell', 'Напоминания', 2], ['cal', 'Календарь', 0], ['music', 'Песни', 0], ['play', 'Видео', 0], ['cam', 'Кино', 0], ['mail', 'Почта', 3], ['pad', 'Игры', 0], ['chip', 'Система', 0], ['ext', 'Расширения', 0]]
  .map(([k, l, b], i) => `<button class="ni ${i ? '' : 'on'}" title="${l}" data-nav="${NAVKEY[l] || ''}" data-label="${l}">${ic(k, 'currentColor', 20)}<span class="lb">${l}</span>${b ? `<span class="bd">${b}</span>` : ''}</button>`).join('') + `<div class="spacer"></div><div class="offl"><div class="r1"><button class="mswb on" id="msw" aria-pressed="true" title="Выключить или включить микрофон для Jarvis">${ic('mic', C.cyan, 18)}</button><b>Микрофон</b></div><div class="hear" id="hear">пока тихо</div><div class="lv" id="lv">${'<i></i>'.repeat(16)}</div>
    <div class="kv"><span>Усиление<b id="mgain">—</b></span><span>Порог<b id="mthr">—</b></span></div>
    <div class="ar" id="mrow-auto"><span>Автозапуск</span><button class="tgl" id="asw" aria-pressed="false" title="Запускать Jarvis вместе с Windows"><span class="sw"></span></button></div>
    <div class="r2" id="mrow-off">${ic('shield', C.green, 15)}Работает офлайн, речь остаётся на этом компьютере</div></div><button class="ni" title="Настройки" data-nav="look" data-label="Настройки">${ic('gear', 'currentColor', 20)}<span class="lb">Настройки</span></button>`;
$('search').innerHTML = ic('search', 'var(--ic)', 16) + '<span>Поиск  Ctrl+K</span>'; $('ib1').innerHTML = ic('bell', 'var(--ic)', 19); $('mic').innerHTML = ic('mic', '#3df5ac', 28);
$('sys').innerHTML = [['cpu', 'ЦП', C.cyan], ['ram', 'Память', C.green], ['disk', 'Диск C:', C.amber], ['bat', 'Батарея', C.green]].map(([k, l, c]) => `<div class="m" style="--c:${c}"><div class="ring"><svg viewBox="0 0 80 80"><circle class="tr" cx="40" cy="40" r="34"/><circle class="pg" id="b_${k}" cx="40" cy="40" r="34" stroke-dasharray="213.6" stroke-dashoffset="213.6"/></svg><b id="v_${k}">–</b></div><span id="l_${k}">${l}</span></div>`).join('');
const setGame = (on) => { $('gmode').classList.toggle('on', on); $('gmode').setAttribute('aria-pressed', on); $('gs').textContent = on ? 'включён' : 'выключен'; $('gi').innerHTML = ic('pad', on ? C.amber : 'var(--ic)', 20); }; setGame(false); $('gmode').onclick = async () => { const want = !$('gmode').classList.contains('on'); if (m.connected) { const r = await J.send('run', { id: want ? 'game_mode_on' : 'game_mode_off' }); if (!(r && r.ok)) setGame(!!m.game); return; } setGame(want); };   // live: the state comes back through the `game` topic setGame(false);
const SUG = ['поставь таймер на 10 минут', 'что за песня играет', 'включи игровой режим']; $('sugg').innerHTML = SUG.map((s) => `<button>«${s}»</button>`).join('');
$('sugg').onclick = (e) => { const b = e.target.closest('button'); if (b) { J.model.heard = b.textContent.slice(1, -1); J.setState('SPEAKING'); } };

// ---- notices: calm greeting when fine, scrolling ticker when there is something to say ----
const notices = {}; const SEV = { info: [C.cyan, 'bell'], warn: [C.amber, 'warn'], err: [C.red, 'warn'] };
function setNotice(id, n) { if (n) notices[id] = n; else delete notices[id]; renderMsg(); }
function bellList(list) { $('drop').innerHTML = '<h4>Уведомления</h4>' + (list.length ? list.map((n) => { const [c, k] = SEV[n.sev]; return `<div class="it">${ic(k, c, 17)}<span>${esc(n.text)}</span></div>`; }).join('') : '<div class="em">Всё спокойно: новых уведомлений нет.</div>'); }
P.palette = 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM9 11h.01M15 11h.01M12 15h.01';
$('ib1').onclick = (e) => { e.stopPropagation(); $('drop').classList.toggle('open'); }; document.addEventListener('click', () => { $('drop').classList.remove('open'); });
function bellBadge(list) { bellList(list); const old = $('ib1').querySelector('.cnt'); if (old) old.remove(); if (list.length) $('ib1').insertAdjacentHTML('beforeend', `<span class="cnt${list.some((n) => n.sev === 'err') ? ' err' : ''}">${list.length}</span>`); }
const SUBS = { IDLE: 'ждёт команду', LISTENING: 'слушает вас', SPEAKING: 'отвечает' };
function renderMsg() { const list = Object.values(notices), bad = list.some((n) => n.sev === 'err'), warn = list.some((n) => n.sev === 'warn'); const col = bad ? C.red : warn || micMuted ? C.amber : C.green;
  bellBadge(list); const hr = new Date().getHours(), gr = hr < 6 ? 'Доброй ночи' : hr < 12 ? 'Доброе утро' : hr < 18 ? 'Добрый день' : 'Добрый вечер';
  const first = list.find((n) => n.sev === 'err') || list.find((n) => n.sev === 'warn');
  $('msg').innerHTML = `<div class="mod" style="--c:${col}"><span class="lamp"></span><div><b>${bad ? 'Нужно внимание' : micMuted ? 'Jarvis не слушает' : 'Jarvis работает'}</b><span id="sub">${first ? esc(first.text) : micMuted ? 'микрофон выключен' : SUBS[m.state]}</span></div></div>`;
  const items = list.map((n) => { const [c, k] = SEV[n.sev]; return `<span style="--c:${c}">${ic(k, c, 17)}${esc(n.text)}</span>`; }).join(''); const dur = Math.max(18, list.length * 9);
  document.querySelector('.stage').classList.toggle('hasmsg', list.length > 0); $('tbar').innerHTML = list.length ? `<div class="ticker"><div class="track" style="--dur:${dur}s">${items}</div></div>` : '';
  const tk = $('tbar').firstElementChild, tr = tk && tk.firstElementChild; if (tr && tr.getBoundingClientRect().width > tk.clientWidth) tr.innerHTML = items + items; else if (tk) { tk.style.maskImage = tk.style.webkitMaskImage = 'none'; tr.style.animation = 'none'; } }   // scroll only when the notices do not fit
renderMsg();

// ---- next / history ----
const KIND = { timer: ['timer', C.cyan], info: ['list', C.cyan], app: ['cal', C.green], reminder: ['bell', C.amber], game: ['pad', C.green] };
let left = 7 * 60 + 42; const clock = () => String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
const EMPTY = (t) => `<div class="empty">${t}</div>`;
let timerEnd = 0;   // epoch ms when the running timer ends (live mode); 0 = demo countdown
const fmtLeft = (sec) => { sec = Math.max(0, Math.round(sec)); const h = Math.floor(sec / 3600), mi = Math.floor(sec % 3600 / 60), se = sec % 60, p = (n) => String(n).padStart(2, '0'); return h ? `${h}:${p(mi)}:${p(se)}` : `${p(mi)}:${p(se)}`; };
function renderNext() {
  if (!m.upcoming.length) { $('next').innerHTML = EMPTY('Ближайших дел нет'); return; }
  $('next').innerHTML = m.upcoming.map((u) => {
    if (u.kind === 'timer') return `<div class="row"><span class="ico" style="--c:${C.cyan}">${ic('timer', C.cyan, 19)}</span><div><div class="t1">${esc(u.label || 'Таймер')}</div><div class="t2">сработает в ${u.t}</div></div><span class="big" id="cd">${timerEnd ? fmtLeft((timerEnd - Date.now()) / 1000) : clock()}</span></div>`;
    const [k, c] = KIND[u.kind] || KIND.info; return `<div class="row"><span class="ico" style="--c:${c}">${ic(k, c, 19)}</span><div><div class="t1">${esc(u.label)}</div><div class="t2">${u.t}${u.note ? ' · ' + esc(u.note) : ''}</div></div><span class="rt">${rel(mins(u.t))}</span></div>`;
  }).join('');
}
function renderHist() {
  $('hist').innerHTML = m.log.length ? m.log.slice().reverse().map((l) => { const [k, c] = KIND[l.kind] || KIND.info; return `<div class="row"><span class="ico s" style="--c:${c}">${ic(k, c, 15)}</span><div class="t1">${l.said ? `«${esc(l.said)}» <span>→ ${esc(l.did)}</span>` : esc(l.did)}</div><span class="rt">${ago(l.t)}</span></div>`; }).join('') : EMPTY('Пока пусто: скажите «Джарвис» и команду');
  requestAnimationFrame(() => fitRows($('hist')));
}
const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
renderNext(); renderHist();
setInterval(() => { const e = $('cd'); if (timerEnd) { if (e) e.textContent = fmtLeft((timerEnd - Date.now()) / 1000); return; } left = Math.max(0, left - 1); if (e) e.textContent = clock(); }, 1000);
const MON = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
function tick() { const d = new Date(), p2 = (n) => String(n).padStart(2, '0'), sec = d.getSeconds();
  $('clk').innerHTML = `${p2(d.getHours())}:${p2(d.getMinutes())}<span class="ss">${p2(sec)}</span>`;
  const bar = $('secp'); bar.style.transition = sec === 0 ? 'none' : ''; bar.style.setProperty('--p', (sec / 59 * 100).toFixed(1) + '%');
  { const dk = d.toDateString(); if ($('date').dataset.d !== dk) { $('date').dataset.d = dk; $('date').innerHTML = `<b>${d.toLocaleDateString('ru-RU', { weekday: 'long' })}</b><i></i><span>${d.getDate()} ${MON[d.getMonth()]}</span>`; } } } setInterval(tick, 1000); tick();
const FX_SPD = { IDLE: ['7s', '4.5s'], LISTENING: ['3.4s', '2.4s'], SPEAKING: ['2.4s', '1.6s'] };
let stateAt = Date.now(), seenSt = '';
/* "calm": nothing is happening, so the page may draw slowly and stop its endless animations. LISTENING counts as calm when it has lasted
   over 8 s with no speech (the core can sit in it for a long time after a stray noise). */
const calm = () => m.state === 'IDLE' || (m.state === 'LISTENING' && m.connected && Date.now() - Math.max(m.speechTs || 0, stateAt) > 8000);
const syncCalm = () => { const v = calm() ? 'IDLE' : m.state; if (html.dataset.st !== v) html.dataset.st = v; };
function paint() { if (m.state !== seenSt) { seenSt = m.state; stateAt = Date.now(); } syncCalm(); { const f = FX_SPD[m.state] || FX_SPD.IDLE; html.style.setProperty('--sweep', f[0]); html.style.setProperty('--breathe', f[1]); } const sb = $('sub'); if (sb && !Object.keys(notices).length) sb.textContent = micMuted ? 'микрофон выключен' : SUBS[m.state]; const col = curCol(); html.style.setProperty('--state', col); $('st').textContent = micMuted ? 'МИКРОФОН ВЫКЛЮЧЕН' : SRU[m.state]; const idle = m.state === 'IDLE';
  $('heard').textContent = micMuted ? 'Нажмите на микрофон, чтобы Jarvis снова слушал' : m.state === 'LISTENING' ? '«' + (m.heard || '…') + '»' : m.state === 'SPEAKING' ? '«' + m.heard + '»' : 'Скажите «Джарвис»'; $('heard').style.opacity = idle || micMuted ? .55 : 1; $('reply').textContent = m.state === 'SPEAKING' ? m.reply : ''; $('sugg').style.visibility = idle && !micMuted ? 'visible' : 'hidden'; if (decorKey !== curCol() + CW + CH) drawDecor(); }
J.on('state', paint); J.on('heard', paint);
const BAT = { v: 87, real: false, charging: false }; if (navigator.getBattery) navigator.getBattery().then((b) => { const upd = () => { BAT.v = Math.round(b.level * 100); BAT.charging = b.charging; BAT.real = true; }; upd(); b.addEventListener('levelchange', upd); b.addEventListener('chargingchange', upd); }).catch(() => {});
const NET_ARROW = (k) => `<svg viewBox="0 0 12 12" width="11" height="11" fill="${k === 'd' ? C.green : C.amber}"><path d="${k === 'd' ? 'M1 3h10L6 11z' : 'M1 9h10L6 1z'}"/></svg>`;
const fmtSpeed = (kb) => { kb = kb || 0; if (kb < 1) return '0 КБ/с'; if (kb < 1000) return Math.round(kb) + ' КБ/с'; const mb = kb / 1024; return (mb < 10 ? mb.toFixed(1) : Math.round(mb)).toString().replace('.', ',') + ' МБ/с'; };
J.on('sensors', () => { const s = m.sensors, set = (k, v) => { window.fzNum ? fzNum($('v_' + k), v, '<small>%</small>') : ($('v_' + k).innerHTML = Math.round(v) + '<small>%</small>'); $('b_' + k).style.strokeDashoffset = 213.6 * (1 - Math.min(100, v) / 100); }; set('cpu', s.cpu || 0); set('ram', s.ram || 0); set('disk', s.disk || 0); set('bat', BAT.v); { const rg = $('v_bat') && $('v_bat').parentElement; if (rg) { let bd = rg.querySelector('.chg'); if (BAT.charging && !bd) rg.insertAdjacentHTML('beforeend', `<span class="chg" title="Заряжается"><svg viewBox="0 0 24 24" width="10" height="10" fill="#04140e"><path d="M13 2L4 14h6l-1 8 9-12h-6z"/></svg></span>`); else if (!BAT.charging && bd) bd.remove(); } } $('net').innerHTML = `<span title="Скорость скачивания из интернета">${NET_ARROW('d')}<b>${fmtSpeed(s.down)}</b><em>скачивание</em></span><span title="Скорость отправки в интернет">${NET_ARROW('u')}<b>${fmtSpeed(s.up)}</b><em>отправка</em></span>`; });

// ================= weather: sky scene driven by real sunrise/sunset (day/night cycle) =================
const WX = { city: 'Киев', temp: 18, feels: 17, wind: 2.2, wdir: 315, gust: 6.1, hum: 54, pres: 764, uv: 3, pop: 20, vis: 10, tmax: 21, tmin: 11, sr: '07:34', ss: '18:09', cond: 'partly', yest: 3 };
const COND_RU = { partly: 'Переменная облачность', clear: 'Ясно', cloudy: 'Пасмурно', rain: 'Дождь', snow: 'Снег' }, TIP = { partly: 'Возьмите лёгкую куртку', clear: 'Хороший день для прогулки', cloudy: 'Может стать прохладнее', rain: 'Возьмите зонт', snow: 'Одевайтесь теплее, скользко' };
const toMin = (s) => +s.slice(0, 2) * 60 + +s.slice(3);
const nowMin = () => { if (demoT !== null) return demoT; const d = new Date(); return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60; };
function sunState() { const t = nowMin(), sr = toMin(WX.sr), ss = toMin(WX.ss);
  if (t >= sr && t <= ss) { const f = (t - sr) / (ss - sr); return { day: true, f, h: Math.sin(Math.PI * f), t, sr, ss }; }
  const nl = 1440 - (ss - sr), tt = t > ss ? t - ss : t + 1440 - ss, f = tt / nl, dist = Math.min(tt, nl - tt), x = Math.min(1, dist / 120), sm = x * x * (3 - 2 * x); return { day: false, f, h: -0.02 - 0.98 * sm, t, sr, ss }; }
const lerpC = (a, b, k) => a.map((v, i) => Math.round(v + (b[i] - v) * k)), mix = (stops, h) => { for (let i = 0; i < stops.length - 1; i++) { const [h0, c0] = stops[i], [h1, c1] = stops[i + 1]; if (h <= h1) return lerpC(c0, c1, Math.max(0, (h - h0) / (h1 - h0))); } return stops[stops.length - 1][1]; };
const SKY_TOP = [[-1, [4, 9, 28]], [-.12, [8, 16, 44]], [.02, [52, 44, 98]], [.2, [24, 98, 170]], [1, [20, 108, 190]]], SKY_BOT = [[-1, [10, 24, 52]], [-.12, [16, 34, 74]], [.02, [222, 112, 74]], [.2, [110, 190, 235]], [1, [126, 202, 244]]];
const sky = $('sky'), sg = sky.getContext('2d'); let SW = 300, SH = 150, SD = 1; const CLOUDS = Array.from({ length: 7 }, (_, i) => ({ x: (i * 0.173) % 1, y: .12 + ((i * 0.37) % 0.5), s: .6 + (i % 3) * .3, v: .006 + (i % 4) * .003 })), DROPS = Array.from({ length: 60 }, (_, i) => ({ x: (i * .6180339) % 1, y: (i * .377) % 1, v: .5 + (i % 5) * .12 })), STARS2 = Array.from({ length: 70 }, (_, i) => ({ x: (i * .6180339 * 1.7) % 1, y: ((i * .377 * 2.3) % 1) * .8, p: i }));
function sizeSky() { const r = sky.getBoundingClientRect(); if (!r.width) return; SD = Math.min(devicePixelRatio || 1, 1.5); SW = r.width; SH = r.height; sky.width = Math.round(SW * SD); sky.height = Math.round(SH * SD); }
function drawSky(now) { const S = sunState(), g = sg; g.setTransform(SD, 0, 0, SD, 0, 0); const top = mix(SKY_TOP, S.h), bot = mix(SKY_BOT, S.h), gr = g.createLinearGradient(0, 0, 0, SH); gr.addColorStop(0, `rgb(${top})`); gr.addColorStop(1, `rgb(${bot})`); g.fillStyle = gr; g.fillRect(0, 0, SW, SH);
  const night = Math.max(0, Math.min(1, (0.1 - S.h) / 0.25)); if (night > 0) { g.fillStyle = '#dff1ff'; for (const s of STARS2) { g.globalAlpha = night * (.25 + .6 * Math.abs(Math.sin(now / 900 + s.p))); g.fillRect(s.x * SW, s.y * SH, 1.3, 1.3); } g.globalAlpha = 1; }
  const baseY = SH * .78, arcH = SH * .52, x0 = SW * .1, x1 = SW * .9, px = x0 + (x1 - x0) * S.f, py = baseY - Math.sin(Math.PI * S.f) * arcH;
  g.strokeStyle = 'rgba(255,255,255,.22)'; g.setLineDash([2, 5]); g.lineWidth = 1; g.beginPath(); for (let i = 0; i <= 40; i++) { const f = i / 40, x = x0 + (x1 - x0) * f, y = baseY - Math.sin(Math.PI * f) * arcH; i ? g.lineTo(x, y) : g.moveTo(x, y); } g.stroke(); g.setLineDash([]);
  const cc = { clear: 0, partly: 3, cloudy: 7, rain: 7, snow: 7 }[WX.cond]; const dark = WX.cond === 'cloudy' || WX.cond === 'rain' ? .55 : 0;
  if (S.day) { const rg = g.createRadialGradient(px, py, 2, px, py, SH * .5); rg.addColorStop(0, 'rgba(255,236,170,.95)'); rg.addColorStop(.18, 'rgba(255,214,120,.55)'); rg.addColorStop(1, 'rgba(255,200,100,0)'); g.fillStyle = rg; g.fillRect(0, 0, SW, SH); g.fillStyle = '#fff3c4'; g.beginPath(); g.arc(px, py, SH * .055, 0, 6.283); g.fill(); }
  else { const rg = g.createRadialGradient(px, py, 2, px, py, SH * .4); rg.addColorStop(0, 'rgba(190,215,255,.5)'); rg.addColorStop(1, 'rgba(190,215,255,0)'); g.fillStyle = rg; g.fillRect(0, 0, SW, SH); g.fillStyle = '#e8f1ff'; g.beginPath(); g.arc(px, py, SH * .06, 0, 6.283); g.fill(); g.fillStyle = `rgb(${top})`; g.beginPath(); g.arc(px + SH * .03, py - SH * .01, SH * .055, 0, 6.283); g.fill(); }
  for (let i = 0; i < cc; i++) { const c = CLOUDS[i], x = ((c.x + now / 1000 * c.v) % 1.3 - .15) * SW, y = c.y * SH, w = SW * .26 * c.s; const lum = S.day ? 255 - dark * 120 : 120 - dark * 40, a = (S.day ? .7 : .35) * (WX.cond === 'partly' ? .8 : 1);
    g.fillStyle = `rgba(${lum},${lum},${Math.min(255, lum + 8)},${a})`; for (const [dx, dy, r] of [[0, 0, .32], [.28, -.1, .4], [.6, 0, .3], [.3, .08, .34]]) { g.beginPath(); g.ellipse(x + dx * w, y + dy * w * .5, r * w * .7, r * w * .42, 0, 0, 6.283); g.fill(); } }
  if (WX.cond === 'rain') { g.strokeStyle = 'rgba(190,220,255,.55)'; g.lineWidth = 1; g.beginPath(); for (const d of DROPS) { const y = ((d.y + now / 1000 * d.v) % 1) * SH, x = d.x * SW + y * .12; g.moveTo(x, y); g.lineTo(x - 2, y + 9); } g.stroke(); }
  if (WX.cond === 'snow') { g.fillStyle = 'rgba(255,255,255,.85)'; for (const d of DROPS) { const y = ((d.y + now / 1000 * d.v * .25) % 1) * SH, x = d.x * SW + Math.sin(now / 900 + d.y * 9) * 6; g.beginPath(); g.arc(x, y, 1.5, 0, 6.283); g.fill(); } }
  g.fillStyle = S.day ? 'rgba(8,24,44,.55)' : 'rgba(3,8,18,.82)'; g.beginPath(); g.moveTo(0, SH); g.lineTo(0, baseY + 6); for (let i = 0; i <= 24; i++) { const x = SW * i / 24, h = [0, 8, 4, 14, 6, 10, 3, 12, 8, 16, 5, 9, 4, 13, 7, 10, 3, 11, 6, 15, 5, 9, 4, 8, 6][i]; g.lineTo(x, baseY + 6 - h); } g.lineTo(SW, SH); g.closePath(); g.fill();
  if (S.h < .12) { g.fillStyle = '#ffd98a'; for (let i = 0; i < 16; i++) { g.globalAlpha = .35 + .5 * Math.abs(Math.sin(now / 1500 + i * 2)); g.fillRect(SW * (.05 + i * .059), baseY + 5 - ((i * 7) % 9), 1.6, 1.6); } g.globalAlpha = 1; }
  g.fillStyle = `rgba(0,0,0,${.12 + dark * .15})`; g.fillRect(0, 0, SW, SH); }
function paintWeather() { const S = sunState(), tip = TIP[WX.cond]; $('wdeg').textContent = (WX.temp > 0 ? '+' : '') + WX.temp + '°'; $('wdesc').textContent = COND_RU[WX.cond]; $('wfeels').textContent = `ощущается ${WX.feels > 0 ? '+' : ''}${WX.feels}°`;
  $('wcmp').textContent = tip; $('wsr').textContent = WX.sr; $('wss').textContent = WX.ss; $('wxr').innerHTML = esc(WX.city) + (demoT !== null ? `<span class="badge">демо ${fmtT(demoT)}</span>` : '');
  const rest = S.day ? Math.round((S.ss - S.t)) : Math.round(S.t < S.sr ? S.sr - S.t : 1440 - S.t + S.sr); $('wleft').textContent = S.day ? `до заката ${Math.floor(rest / 60)} ч ${rest % 60} мин` : `до рассвета ${Math.floor(rest / 60)} ч ${rest % 60} мин`;
  const wi = (d) => `<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const num = (v) => v !== null && v !== undefined && v !== '' && !Number.isNaN(+v), DIRS = ['С', 'СВ', 'В', 'ЮВ', 'Ю', 'ЮЗ', 'З', 'СЗ'];
  const aql = (a) => (a <= 20 ? 'хорошее' : a <= 40 ? 'приемлемое' : a <= 60 ? 'умеренное' : a <= 80 ? 'плохое' : a <= 100 ? 'очень плохое' : 'крайне плохое');
  const uvl = (u) => (u < 3 ? 'низкий' : u < 6 ? 'умеренный' : u < 8 ? 'высокий' : u < 11 ? 'очень высокий' : 'экстремальный');
  const chips = [
    num(WX.wind) && [wi('<path d="M3 8h11a3 3 0 1 0-3-3M3 12h15a3 3 0 1 1-3 3M3 16h7"/>'), `${(+WX.wind).toFixed(1)} м/с${num(WX.wdir) ? ' ' + DIRS[Math.round(WX.wdir / 45) % 8] : ''}`, `Ветер${num(WX.wdir) ? ', ' + Math.round(WX.wdir) + '°' : ''}${num(WX.gust) ? `, порывы до ${(+WX.gust).toFixed(0)} м/с` : ''}`],
    num(WX.hum) && [wi('<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>'), `${Math.round(WX.hum)}%`, 'Влажность воздуха'],
    num(WX.pres) && [wi('<path d="M4 17a8 8 0 1 1 16 0M12 17l4-5"/>'), `${Math.round(WX.pres)} мм`, 'Атмосферное давление, мм рт. ст.'],
    num(WX.uv) && [wi('<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>'), `УФ ${Math.round(WX.uv)}`, `УФ-индекс сегодня: ${uvl(WX.uv)}`],
    num(WX.pop) && [wi('<path d="M7 15a4 4 0 0 1 .5-8 5.5 5.5 0 0 1 10.5 1.5A3.3 3.3 0 0 1 17.5 15M9 18v3M13 18v3M17 18v3"/>'), `${Math.round(WX.pop)}%`, 'Вероятность осадков сегодня'],
    num(WX.aqi) && [wi('<path d="M4 9h10a3 3 0 1 0-3-3M3 14h14a3 3 0 1 1-3 3M3 19h6"/>'), `AQI ${Math.round(WX.aqi)}`, `Качество воздуха (европейский индекс): ${aql(WX.aqi)}`],
    num(WX.yest) && Math.abs(WX.yest) >= 2 && [wi('<path d="M12 19V5M5 12l7-7 7 7"' + (WX.yest < 0 ? ' transform="rotate(180 12 12)"' : '') + '/>'), `${WX.yest > 0 ? '+' : ''}${Math.round(WX.yest)}°`, `${WX.yest > 0 ? 'Теплее' : 'Холоднее'}, чем вчера`],
    num(WX.vis) && [wi('<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>'), `${+WX.vis >= 10 ? Math.round(WX.vis) : (+WX.vis).toFixed(1)} км`, 'Видимость'],
  ].filter(Boolean);
  $('wstats').innerHTML = chips.map(([ic, v, t]) => `<span class="wxs" title="${t}">${ic}<b>${v}</b></span>`).join('');
  if (num(WX.tmax) && num(WX.tmin)) { const sg = (n) => (n > 0 ? '+' : '') + Math.round(n); $('wfeels').textContent = `ощущается ${WX.feels > 0 ? '+' : ''}${WX.feels}° · ${sg(WX.tmin)}…${sg(WX.tmax)}°`; }
  const [br, bg, bb] = String(mix([[-1, [5, 18, 40]], [-.1, [8, 26, 54]], [.2, [10, 50, 92]], [1, [12, 62, 108]]], S.h)).split(',').map(Number), mxv = Math.max(br, bg, bb) / 255, mnv = Math.min(br, bg, bb) / 255, ll = (mxv + mnv) / 2, ss = mxv === mnv ? 0 : (mxv - mnv) / (1 - Math.abs(2 * ll - 1));
  html.style.setProperty('--bg1', `hsl(calc(var(--h) + 5) calc(${(ss * 100).toFixed(0)}% * var(--sk)) ${(ll * 100).toFixed(1)}%)`); }

// ================= camera and guard (from the old HUD: preview with face box, guard mode) =================
const cam = $('cam'), cg = cam.getContext('2d'); let CWd = 300, CHt = 150, camOn = false, guardOn = false;
function sizeCam() { const r = cam.getBoundingClientRect(); if (!r.width) return; cam.width = Math.round(r.width); cam.height = Math.round(r.height); CWd = r.width; CHt = r.height; }
function corners(g, w, h, col, s = 16, p = 10) { g.strokeStyle = col; g.lineWidth = 2; for (const [x, y, dx, dy] of [[p, p, 1, 1], [w - p, p, -1, 1], [p, h - p, 1, -1], [w - p, h - p, -1, -1]]) { g.beginPath(); g.moveTo(x + dx * s, y); g.lineTo(x, y); g.lineTo(x, y + dy * s); g.stroke(); } }
// real webcam through getUserMedia (the preview only; the guard keeps using the synthetic view in this prototype)
const vid = document.createElement('video'); vid.muted = true; vid.playsInline = true; let stream = null, camErr = '', camBusy = false;
async function camStart() { if (stream || camBusy) return; camBusy = true; camErr = '';
  try { stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false }); vid.srcObject = stream; await vid.play(); if (!camOn) camStop(); }
  catch (e) { camErr = e && e.name === 'NotAllowedError' ? 'Нет доступа к камере' : 'Камера не найдена или занята'; camOn = false; paintCam(); }
  camBusy = false; }
function camStop() { if (stream) { stream.getTracks().forEach((t) => t.stop()); stream = null; vid.srcObject = null; } }
function drawVideo(g, w, h, col) { const vw = vid.videoWidth, vh = vid.videoHeight; g.fillStyle = '#040b14'; g.fillRect(0, 0, w, h); if (!vw) { g.fillStyle = C.dim || '#8fb4cc'; g.font = '500 13px Onest'; g.textAlign = 'center'; g.fillText('запуск камеры…', w / 2, h / 2); g.textAlign = 'left'; return; }
  const k = Math.max(w / vw, h / vh), dw = vw * k, dh = vh * k; g.save(); g.translate(w, 0); g.scale(-1, 1); g.drawImage(vid, (w - dw) / 2, (h - dh) / 2, dw, dh); g.restore();   // mirrored like a mirror
  corners(g, w, h, col); hud(g, w, h, `${vw}×${vh}`); }
// live tag with a pulsing dot (top right), clock and resolution (bottom left)
function hud(g, w, h, res) { const t = performance.now() / 1000, on = .55 + .45 * Math.sin(t * 4); g.font = '700 11px Onest'; g.textAlign = 'right'; g.fillStyle = 'rgba(2,8,18,.55)'; g.fillRect(w - 62, 10, 52, 18);
  g.fillStyle = C.red; g.globalAlpha = on; g.beginPath(); g.arc(w - 51, 19, 3.5, 0, 6.283); g.fill(); g.globalAlpha = 1; g.fillStyle = '#fff'; g.fillText('LIVE', w - 15, 23);
  g.textAlign = 'left'; g.font = '600 11px Onest'; const d = new Date(), ts = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
  g.fillStyle = 'rgba(2,8,18,.55)'; g.fillRect(12, h - 30, 66 + (res ? g.measureText(res).width + 12 : 0), 18); g.fillStyle = '#dff1ff'; g.fillText(ts, 17, h - 17); if (res) { g.fillStyle = C.dim || '#8fb4cc'; g.fillText(res, 17 + 58, h - 17); } }
const pad2 = (n) => String(n).padStart(2, '0'), since = (t0) => { const s = Math.max(0, Math.floor((Date.now() - t0) / 1000)); return `${pad2(Math.floor(s / 3600))}:${pad2(Math.floor(s / 60) % 60)}:${pad2(s % 60)}`; };
let guardSince = 0;
// standby screen: grid and rings; the guard adds a radar sweep with blips, the idle view a camera glyph, a failure shows its reason
function drawIdle(g, w, h, col, t) { g.fillStyle = '#050c16'; g.fillRect(0, 0, w, h);
  g.strokeStyle = rgba(col, .07); g.lineWidth = 1; g.beginPath(); for (let x = (w % 24) / 2; x < w; x += 24) { g.moveTo(x, 0); g.lineTo(x, h); } for (let y = (h % 24) / 2; y < h; y += 24) { g.moveTo(0, y); g.lineTo(w, y); } g.stroke();
  const cx = w / 2, cy = h * .44, r = Math.min(w, h) * .3;
  g.strokeStyle = col; g.lineWidth = 1; g.globalAlpha = .45; for (const k of [1, .66, .33]) { g.beginPath(); g.arc(cx, cy, r * k, 0, 6.283); g.stroke(); } g.beginPath(); g.moveTo(cx - r, cy); g.lineTo(cx + r, cy); g.moveTo(cx, cy - r); g.lineTo(cx, cy + r); g.stroke(); g.globalAlpha = 1;
  if (guardOn) { const a = t * 1.5;
    for (let i = 0; i < 16; i++) { g.fillStyle = rgba(col, .3 * (1 - i / 16)); g.beginPath(); g.moveTo(cx, cy); g.arc(cx, cy, r, a - (i + 1) * .045, a - i * .045); g.fill(); }
    g.strokeStyle = col; g.lineWidth = 1.5; g.beginPath(); g.moveTo(cx, cy); g.lineTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r); g.stroke();
    for (const [ba, bd] of [[.9, .55], [2.8, .8], [4.4, .35], [5.5, .7]]) { const age = (((a - ba) % 6.283) + 6.283) % 6.283, al = Math.max(0, 1 - age / 3.2); if (al > .02) { g.fillStyle = rgba(C.red, al); g.beginPath(); g.arc(cx + Math.cos(ba) * r * bd, cy + Math.sin(ba) * r * bd, 3, 0, 6.283); g.fill(); } }
    g.fillStyle = col; g.font = '700 12px Onest'; g.textAlign = 'center'; g.fillText('НАБЛЮДАЮ', cx, h - 26); g.fillStyle = C.dim || '#8fb4cc'; g.font = '500 11px Onest'; g.fillText(`под охраной ${since(guardSince || Date.now())}`, cx, h - 11); g.textAlign = 'left'; }
  else if (camErr) { g.fillStyle = C.amber; g.font = '600 12px Onest'; g.textAlign = 'center'; g.fillText(camErr, cx, cy + 4); g.fillStyle = C.dim || '#8fb4cc'; g.font = '500 11px Onest'; g.fillText('проверьте доступ и нажмите «Камера» ещё раз', cx, h - 14); g.textAlign = 'left'; }
  else { const s = Math.min(w, h) * .13; g.strokeStyle = col; g.globalAlpha = .9; g.lineWidth = 1.8; g.lineJoin = 'round'; g.beginPath(); g.roundRect(cx - s, cy - s * .55, s * 2, s * 1.35, 5); g.moveTo(cx - s * .45, cy - s * .55); g.lineTo(cx - s * .3, cy - s * .85); g.lineTo(cx + s * .3, cy - s * .85); g.lineTo(cx + s * .45, cy - s * .55); g.stroke(); g.beginPath(); g.arc(cx, cy + s * .12, s * .45, 0, 6.283); g.stroke(); g.globalAlpha = 1;
    g.fillStyle = C.dim || '#8fb4cc'; g.font = '600 12px Onest'; g.textAlign = 'center'; g.fillText('камера выключена', cx, h - 26); g.font = '500 11px Onest'; g.fillStyle = rgba(col, .75); g.fillText('нажмите «Камера» для просмотра', cx, h - 11); g.textAlign = 'left'; }
  corners(g, w, h, col); }
function drawCam(now) { const g = cg, w = CWd, h = CHt; g.clearRect(0, 0, w, h); const col = guardOn ? C.amber : C.cyan, t = now / 1000;
  if (camOn && !guardOn) { drawVideo(g, w, h, col); return; }
  if (camOn) { const bg = g.createLinearGradient(0, 0, w, h); bg.addColorStop(0, '#16303a'); bg.addColorStop(1, '#0b1c26'); g.fillStyle = bg; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(255,255,255,.05)'; for (let i = 0; i < 90; i++) g.fillRect((i * 97.3 + t * 40) % w, (i * 53.7) % h, 2, 1);
    const fx = w * .5 + Math.sin(t * .8) * w * .06, fy = h * .5, fw = h * .5; g.fillStyle = '#244a58'; g.beginPath(); g.ellipse(fx, fy + fw * .15, fw * .42, fw * .58, 0, 0, 6.283); g.fill(); g.fillStyle = '#12303c'; g.beginPath(); g.ellipse(fx, fy + fw * .75, fw * .8, fw * .4, 0, 0, 6.283); g.fill();
    g.strokeStyle = '#ffff55'; g.lineWidth = 1.5; g.strokeRect(fx - fw * .5, fy - fw * .55, fw, fw * 1.3); g.fillStyle = '#ffff55'; g.font = '600 11px Onest'; g.fillText('владелец', fx - fw * .5, fy - fw * .6); corners(g, w, h, col); hud(g, w, h, ''); return; }
  drawIdle(g, w, h, col, t); }
const bsvg = (d) => `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const BI = { cam: bsvg('<path d="M3 8h4l1.5-2.5h7L17 8h4v11H3zM12 11a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/>'), stop: bsvg('<rect x="6" y="6" width="12" height="12" rx="2"/>'), shield: bsvg('<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6zM9 12l2.2 2.2L15.5 10"/>'), off: bsvg('<path d="M12 3l8 3v6c0 4.5-3.2 7.8-8 9-4.8-1.2-8-4.5-8-9V6zM9.5 9.5l5 5M14.5 9.5l-5 5"/>') };
function paintCam() { if (camOn && !guardOn) camStart(); else camStop(); $('bcam').classList.toggle('on', camOn); $('bguard').classList.toggle('on', guardOn); $('bcam').disabled = guardOn; $('bcam').title = guardOn ? 'Камеру сейчас использует охрана' : ''; $('bcam').innerHTML = camOn ? `${BI.stop}Стоп` : `${BI.cam}Камера`; $('bguard').innerHTML = guardOn ? `${BI.off}Снять охрану` : `${BI.shield}Охрана`;
  $('camst').textContent = guardOn ? 'охрана включена' : camOn ? 'идёт просмотр' : camErr || 'выключена'; $('camst').style.color = guardOn ? C.amber : camOn ? C.green : ''; $('camnote').textContent = guardOn ? 'Последнее: владелец распознан · ' + new Date(Date.now() - 6 * 60000).toTimeString().slice(0, 5) : 'Охрана узнаёт вас по лицу и сообщает о чужих'; }
$('bcam').onclick = () => { camOn = !camOn; paintCam(); }; const setGuard = (on) => { if (!!on && !guardOn) guardSince = Date.now(); guardOn = !!on; if (guardOn) camOn = false; paintCam(); setNotice('guard', guardOn ? { sev: 'info', text: 'Охрана включена' } : null); if (guardOn) setTimeout(() => setNotice('guard', null), 9000); };
$('bguard').onclick = () => { const want = !guardOn; if (!m.connected) { setGuard(want); return; } if (want) { camOn = false; paintCam(); } J.send('guard', { on: want }); };   // the core answers through the `guard` topic: it needs a few seconds to learn the owner's face
J.on('guard', () => { if (m.guard !== guardOn) setGuard(m.guard); }); paintCam();

// ================= core canvas (as in h.html) =================
const cv = $('core'), g = cv.getContext('2d'), decor = document.createElement('canvas'); let FH = 0, CW = 600, CH = 300, GX, GY, RG, DPR = 1;
function sizeCanvas() { FH = document.querySelector('.foot').offsetHeight; cv.style.height = `calc(100% + ${FH}px)`; const r = cv.getBoundingClientRect(); if (!r.width) return; DPR = Math.min(devicePixelRatio || 1, 1.25); /* soft line art: a higher density only costs fill rate */ CW = r.width; CH = r.height; cv.width = Math.round(CW * DPR); cv.height = Math.round(CH * DPR); decor.width = cv.width; decor.height = cv.height; GX = CW / 2; const CHs = CH - FH; GY = CHs * 0.47; RG = Math.min(CW * 0.22, CHs * 0.3); const sw = $('sweep'), gw = $('glow'); sw.style.cssText = `left:${GX - RG * 1.3}px;top:${GY - RG * 1.3}px;width:${RG * 2.6}px;height:${RG * 2.6}px`; gw.style.cssText = `left:${GX - RG * 2.1}px;top:${GY - RG * 2.1}px;width:${RG * 4.2}px;height:${RG * 4.2}px`; drawDecor(); }
let decorKey = '', barCol = '';
/* The core is drawn once per colour/size into `decor` (dense node mesh on a sphere, atmosphere, orbits with satellites, glowing floor,
   side arcs, dust). While idle only a few hub nodes and stars glint (see frame); nothing is re-computed per frame. */
const TWINK = []; let ORBG = [];
const MESH = (() => { const N = 270, pts = [], links = [];
  for (let i = 0; i < N; i++) { const y = 1 - 2 * (i + .5) / N, r = Math.sqrt(1 - y * y), a = i * 2.399963; pts.push([r * Math.cos(a), y, r * Math.sin(a)]); }
  for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) { const dx = pts[i][0] - pts[j][0], dy = pts[i][1] - pts[j][1], dz = pts[i][2] - pts[j][2]; if (dx * dx + dy * dy + dz * dz < .105) links.push([i, j]); }
  return { pts, links }; })();
function drawDecor() { if (!GX) return; decorKey = curCol() + CW + CH; const d = decor.getContext('2d'), col = curCol(); d.setTransform(DPR, 0, 0, DPR, 0, 0); d.clearRect(0, 0, CW, CH); TWINK.length = 0;
  const TAU = 6.283185, FY = GY + RG * 1.3;
  // aura
  { const gl = d.createRadialGradient(GX, GY, RG * .1, GX, GY, RG * 2.4); gl.addColorStop(0, rgba(col, .30)); gl.addColorStop(.5, rgba(col, .09)); gl.addColorStop(1, rgba(col, 0)); d.fillStyle = gl; d.fillRect(0, 0, CW, CH); }
  // floor: glow disc, concentric glowing ellipses, tick ring
  { d.save(); d.translate(0, FY); d.scale(1, .24); d.translate(0, -FY); const fl = d.createRadialGradient(GX, FY, 0, GX, FY, RG * 2.4); fl.addColorStop(0, rgba(col, .34)); fl.addColorStop(.45, rgba(col, .12)); fl.addColorStop(1, rgba(col, 0)); d.fillStyle = fl; d.beginPath(); d.arc(GX, FY, RG * 2.4, 0, TAU); d.fill(); d.restore();
    d.strokeStyle = col; d.shadowColor = col; d.shadowBlur = 10; for (let k = 0; k < 5; k++) { d.globalAlpha = .75 - k * .13; d.lineWidth = k ? 1 : 1.6; d.beginPath(); d.ellipse(GX, FY, RG * (1.1 + k * .42), RG * (.14 + k * .05), 0, 0, TAU); d.stroke(); }
    d.shadowBlur = 0; d.lineWidth = 1; d.globalAlpha = .45; d.beginPath(); for (let a = 0; a < 150; a++) { const an = a * TAU / 150, c = Math.cos(an), sn = Math.sin(an), l = a % 10 === 0 ? 11 : a % 5 === 0 ? 7 : 3.5, rx = RG * 2.05, ry = RG * .3; d.moveTo(GX + c * rx, FY + sn * ry); d.lineTo(GX + c * (rx + l), FY + sn * (ry + l * .22)); } d.stroke(); d.globalAlpha = 1; }
  // orbits, back halves
  const ORB = [[RG * 1.85, RG * .5, -.2, [.4, 1.3]], [RG * 2.12, RG * .66, .17, [.9, 1.75]]];
  const arc = (o, a0, a1) => { d.beginPath(); d.ellipse(GX, GY, o[0], o[1], o[2], a0 * Math.PI, a1 * Math.PI); d.stroke(); };
  d.strokeStyle = col; d.lineWidth = 1; d.globalAlpha = .32; for (const o of ORB) arc(o, 1, 2);
  // atmosphere
  { const at = d.createRadialGradient(GX, GY, RG * .9, GX, GY, RG * 1.3); at.addColorStop(0, rgba(col, 0)); at.addColorStop(.28, rgba(col, .4)); at.addColorStop(1, rgba(col, 0)); d.globalAlpha = 1; d.fillStyle = at; d.beginPath(); d.arc(GX, GY, RG * 1.3, 0, TAU); d.fill(); }
  // sphere body and mesh
  { d.save(); d.beginPath(); d.arc(GX, GY, RG, 0, TAU); d.clip();
    const bg = d.createRadialGradient(GX - RG * .32, GY - RG * .38, RG * .05, GX, GY, RG); bg.addColorStop(0, rgba(col, .34)); bg.addColorStop(.55, rgba(col, .11)); bg.addColorStop(1, rgba(col, .03)); d.fillStyle = bg; d.fillRect(GX - RG, GY - RG, RG * 2, RG * 2);
    const ROT = .9, TILT = .34, cr = Math.cos(ROT), sr = Math.sin(ROT), ct = Math.cos(TILT), st = Math.sin(TILT);
    const P = MESH.pts.map((p) => { const x = p[0] * cr + p[2] * sr, z = -p[0] * sr + p[2] * cr, y2 = p[1] * ct - z * st, z2 = p[1] * st + z * ct; return [GX + RG * x, GY - RG * y2, z2]; });
    d.lineWidth = .7; d.strokeStyle = col;
    for (const [lo, hi, al] of [[-2, 0, .14], [0, .3, .3], [.3, .65, .52], [.65, 2, .85]]) { d.globalAlpha = al; d.beginPath(); for (const [i, j] of MESH.links) { const zz = (P[i][2] + P[j][2]) / 2; if (zz >= lo && zz < hi) { d.moveTo(P[i][0], P[i][1]); d.lineTo(P[j][0], P[j][1]); } } d.stroke(); }
    for (let i = 0; i < P.length; i++) { const p = P[i]; if (p[2] < -.05) continue; const hub = i % 11 === 0, z = Math.max(0, p[2]);
      if (hub) { const hg = d.createRadialGradient(p[0], p[1], 0, p[0], p[1], 9); hg.addColorStop(0, rgba(col, .75)); hg.addColorStop(1, rgba(col, 0)); d.globalAlpha = .4 + .6 * z; d.fillStyle = hg; d.fillRect(p[0] - 9, p[1] - 9, 18, 18); if (z > .3) TWINK.push([p[0], p[1], i]); }
      d.globalAlpha = .35 + .65 * z; d.fillStyle = hub ? '#fff' : col; d.beginPath(); d.arc(p[0], p[1], hub ? 1.9 + z : .8 + z * .9, 0, TAU); d.fill(); }
    d.restore(); }
  // rim light
  d.globalAlpha = 1; d.strokeStyle = col; d.shadowColor = col; d.shadowBlur = 16; d.lineWidth = 1.6; d.beginPath(); d.arc(GX, GY, RG, 0, TAU); d.stroke(); d.shadowBlur = 0; d.lineWidth = 1; d.globalAlpha = .4; d.beginPath(); d.arc(GX, GY, RG * 1.06, 0, TAU); d.stroke();
  // orbits, front halves and satellites
  d.shadowColor = col; d.shadowBlur = 8; d.globalAlpha = .85; for (const o of ORB) arc(o, 0, 1); d.shadowBlur = 0;
  ORBG = ORB; d.globalAlpha = 1;
  // thin HUD ring with sparse ticks and bearing labels
  d.strokeStyle = col; d.lineWidth = 1; d.globalAlpha = .3; d.beginPath(); d.arc(GX, GY, RG * 1.2, 0, TAU); d.stroke(); d.beginPath(); for (let i = 0; i < 100; i++) { const a = i * TAU / 100, r1 = RG * 1.2, r2 = r1 + RG * (i % 5 ? .03 : .07); if (i % 5 === 0 || i % 2 === 0) { d.moveTo(GX + r1 * Math.cos(a), GY + r1 * Math.sin(a)); d.lineTo(GX + r2 * Math.cos(a), GY + r2 * Math.sin(a)); } } d.stroke();
  d.globalAlpha = .7; d.fillStyle = col; d.font = '600 10px Tektur'; d.textAlign = 'center'; d.textBaseline = 'middle'; for (const [t, an] of [['000', -1.5708], ['090', 0], ['270', 3.1416]]) d.fillText(t, GX + Math.cos(an) * RG * 1.42, GY + Math.sin(an) * RG * 1.42); d.textAlign = 'start'; d.textBaseline = 'alphabetic';
  // side arcs (wide stage) and dust
  if (CW > 640) { d.strokeStyle = col; d.lineWidth = 2; for (const sg of [-1, 1]) for (let r = 0; r < 2; r++) { const rad = RG * (1.9 + r * .22), a0 = (sg < 0 ? Math.PI : 0) - .55; d.globalAlpha = .5 - r * .2; d.beginPath(); d.arc(GX, GY, rad, a0, a0 + 1.1); d.stroke(); }
    d.lineWidth = 1; d.globalAlpha = .4; d.beginPath(); for (let i = -6; i <= 6; i++) for (const sg of [-1, 1]) { const an = (sg < 0 ? Math.PI : 0) + i * .075 * (sg < 0 ? -1 : 1), r1 = RG * 2.18, r2 = r1 + (i % 3 ? 4 : 9); d.moveTo(GX + Math.cos(an) * r1, GY + Math.sin(an) * r1); d.lineTo(GX + Math.cos(an) * r2, GY + Math.sin(an) * r2); } d.stroke(); }
  d.fillStyle = col; for (let i = 0; i < 70; i++) { d.globalAlpha = .12 + (i * .37 % 1) * .4; d.fillRect(GX + Math.sin(i * 12.9898) * CW * .44, GY + RG * 1.6 - ((i * .137) % 1) * CH * .95, 1.5, 1.5); }
  d.globalAlpha = 1; }
const NODES = Array.from({ length: 28 }, (_, i) => ({ lat: Math.asin(((i * 0.6180339 * 2) % 2) - 1), lon: i * 2.399963 })), STARS = Array.from({ length: 50 }, (_, i) => ({ x: ((i * 97.3) % 100) / 100, y: ((i * 53.7) % 100) / 100, p: i * 1.7 }));
function project(lat, lon, th, tilt) { const x = Math.cos(lat) * Math.sin(lon + th), y0 = Math.sin(lat), z0 = Math.cos(lat) * Math.cos(lon + th); const y = y0 * Math.cos(tilt) - z0 * Math.sin(tilt), z = y0 * Math.sin(tilt) + z0 * Math.cos(tilt); return [GX + RG * x, GY - RG * y, z]; }

// ---- "from the future" layer on the core: voice equalizer ring, radar sweep, comets on the orbits, pulse waves, mouse parallax ----
let mx = 0, my = 0, pmx = 0, pmy = 0; addEventListener('pointermove', (e) => { mx = e.clientX / innerWidth - .5; my = e.clientY / innerHeight - .5; });
const AMP = { IDLE: .1, LISTENING: .55, SPEAKING: .85 }; let amp = .1; const waves = []; let nextWave = 0;
function fx(g, t, dt, col) {
  const a = AMP[m.state] || .1; amp += (a - amp) * Math.min(1, dt * 5); const lv = J.level(t), R0 = RG * 1.06;
  // equalizer ring: 72 bars, height follows the voice level (state-based noise in the prototype)
  g.lineWidth = 2; g.strokeStyle = col; g.lineCap = 'round'; g.globalAlpha = .85; g.beginPath();
  for (let i = 0; i < 72; i++) { const an = i / 72 * 6.283 - 1.5708, n = Math.abs(Math.sin(t * 3.1 + i * .9) * Math.sin(t * 1.7 + i * .37)), h = 2 + (.25 + .75 * n) * lv * RG * .5; g.moveTo(GX + Math.cos(an) * R0, GY + Math.sin(an) * R0); g.lineTo(GX + Math.cos(an) * (R0 + h), GY + Math.sin(an) * (R0 + h)); } g.stroke();
  // pulse waves when listening or speaking
  if (m.state !== 'IDLE' && t > nextWave) { waves.push(t); nextWave = t + (m.state === 'SPEAKING' ? .55 : .9); } while (waves.length && t - waves[0] > 2.2) waves.shift();
  g.lineWidth = 1.5; for (const w0 of waves) { const k = (t - w0) / 2.2; g.globalAlpha = (1 - k) * .45; g.strokeStyle = col; g.beginPath(); g.arc(GX, GY, RG * (1.1 + k * 1.1), 0, 6.283); g.stroke(); }
  // comets on the orbit ellipses
  for (let k = 0; k < 3; k++) { const rr = RG * (1.3 + (k + 1) * .45), ry = RG * (.16 + (k + 1) * .05), sp = (.5 + k * .22) * (k % 2 ? -1 : 1);
    for (let tail = 0; tail < 14; tail++) { const an = t * sp - tail * .045 * Math.sign(sp); g.globalAlpha = (1 - tail / 14) * .9; g.fillStyle = tail ? col : '#fff'; g.beginPath(); g.arc(GX + Math.cos(an) * rr, GY + RG * 1.3 + Math.sin(an) * ry, (1 - tail / 14) * 2.6 + .3, 0, 6.283); g.fill(); } }
  g.globalAlpha = 1; g.lineCap = 'butt'; }
const SPD = { IDLE: .32, LISTENING: .8, SPEAKING: 1.3 }; let th = 0, last = performance.now(), lastSlow = 0, lastBars = 0;
const NO_NX = new Set();
/* cheap vector motion on top of the static art: a light band sweeping down the sphere, satellites on both orbits, a bright arc running along the floor rings */
function coreMotion(g, t, col) { const TAU = 6.283185, FY = GY + RG * 1.3;
  g.save(); g.beginPath(); g.arc(GX, GY, RG, 0, TAU); g.clip();
  const by = GY - RG + (((t * .17) % 1.5) - .25) * RG * 2, bh = RG * .42, bg = g.createLinearGradient(0, by - bh, 0, by + bh); bg.addColorStop(0, rgba(col, 0)); bg.addColorStop(.5, rgba(col, .26)); bg.addColorStop(1, rgba(col, 0)); g.fillStyle = bg; g.fillRect(GX - RG, by - bh, RG * 2, bh * 2); g.restore();
  g.lineCap = 'round'; g.strokeStyle = col; const fa = t * .9; for (const [w, al] of [[5, .12], [1.8, .9]]) { g.lineWidth = w; g.globalAlpha = al; g.beginPath(); g.ellipse(GX, FY, RG * 1.94, RG * .3, 0, fa, fa + .7); g.stroke(); }
  g.lineWidth = 1.4; g.globalAlpha = .55; g.beginPath(); g.ellipse(GX, FY, RG * 1.52, RG * .22, 0, -fa * 1.3, -fa * 1.3 + .45); g.stroke(); g.lineCap = 'butt';
  ORBG.forEach((o, i) => { for (let k = 0; k < 2; k++) { const a = t * (i ? -.32 : .42) + k * Math.PI + i, ex = o[0] * Math.cos(a), ey = o[1] * Math.sin(a), x = GX + ex * Math.cos(o[2]) - ey * Math.sin(o[2]), y = GY + ex * Math.sin(o[2]) + ey * Math.cos(o[2]), back = Math.sin(a) < 0;
    g.fillStyle = col; g.globalAlpha = back ? .12 : .3; g.beginPath(); g.arc(x, y, back ? 5 : 8, 0, TAU); g.fill(); g.fillStyle = '#fff'; g.globalAlpha = back ? .45 : 1; g.beginPath(); g.arc(x, y, back ? 1.6 : 2.5, 0, TAU); g.fill(); } });
  g.globalAlpha = 1; }
let rafOn = false; const wake = () => { if (!rafOn) { rafOn = true; requestAnimationFrame(frame); } };
/* the loop asks for a frame only while the dashboard is on screen; showView() and visibilitychange wake it. While calm it wakes on a timer (~11 fps),
   so the compositor is not asked for 60-75 frames a second just to skip them */
function frame(now) { rafOn = false; if (document.hidden || VIEW !== 'dash') return; draw(now); setTimeout(wake, calm() ? 85 : 30); }   // ~11 fps calm, ~27 fps active
document.addEventListener('visibilitychange', wake);
/* breathing halo and pulsing lamps, written on the core tick. As CSS animations they kept the compositor drawing at the display rate (75/s) while Jarvis
   listened or spoke, about twice the GPU of the same scene at 27 fps. Calm and lite: static (see fx.css) */
let beating = false;
function beat(t, quiet) {
  if (quiet || html.dataset.fx === 'lite') { if (beating) { beating = false; document.querySelectorAll('#glow, .pill i, .lamp').forEach((e) => { e.style.opacity = e.style.transform = ''; }); } return; }
  beating = true; const kb = .5 - .5 * Math.cos(t * 6.2832 / (parseFloat(html.style.getPropertyValue('--breathe')) || 4.5)), kp = .5 - .5 * Math.cos(t * 6.2832 / 2.2), gl = $('glow');
  if (gl) { gl.style.opacity = (1 - .45 * kb).toFixed(3); gl.style.transform = `scale(${(1 - .06 * kb).toFixed(3)})`; }
  document.querySelectorAll('.pill i, .lamp').forEach((e) => { e.style.opacity = (1 - .65 * kp).toFixed(3); e.style.transform = `scale(${(1 - .2 * kp).toFixed(3)})`; });
}
/* The status lamps keep breathing where beat() does not run: every screen except the overview, and the calm overview (4 writes a second, one tiny element; fx lite stays static). */
setInterval(() => {
  if (document.hidden || html.dataset.fx === 'lite' || (VIEW === 'dash' && !calm())) return;
  const kp = .5 - .5 * Math.cos(Date.now() / 1000 * 6.2832 / 2.6);
  document.querySelectorAll('.pill i, .lamp').forEach((e) => { e.style.opacity = (1 - .65 * kp).toFixed(2); e.style.transform = `scale(${(1 - .2 * kp).toFixed(2)})`; });
}, 250);
function draw(now) {
  const NXs = window.NX || NO_NX; if (now - lastSlow > 80) { lastSlow = now; if (sky.width && !NXs.has('sky')) drawSky(now); if (cam.width && !NXs.has('cam')) drawCam(now); }          // weather and camera at ~9 fps (clouds drift slowly)
  const quiet = calm();
  if (NXs.has('core') || !GX || now - last < (quiet ? 80 : 30)) return;   // quiet: 10 fps (motion overlay + glints); listening and speaking: 25 fps
  const dt = (now - last) / 1000; last = now; const col = curCol(), t = now / 1000;
  g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, cv.width, cv.height); g.drawImage(decor, 0, 0); g.setTransform(DPR, 0, 0, DPR, 0, 0);
  g.fillStyle = C.star; for (const s of STARS) { g.globalAlpha = .12 + .4 * Math.abs(Math.sin(t * .8 + s.p)); g.fillRect(s.x * CW, s.y * CH, 1.4, 1.4); }
  g.fillStyle = '#fff'; for (const h of TWINK) { g.globalAlpha = .15 + .75 * Math.max(0, Math.sin(t * 1.2 + h[2] * 1.7)) ** 3; g.beginPath(); g.arc(h[0], h[1], 2.6, 0, 6.283); g.fill(); } g.globalAlpha = 1;
  beat(t, quiet);
  if (!NXs.has('motion')) coreMotion(g, t, col);
  if (!quiet) fx(g, t, dt, col);
  const bars = document.querySelectorAll('#lv i'); if (now - lastBars > (calm() ? 220 : 90)) { lastBars = now; const lv = J.level(t); bars.forEach((b, i) => { b.style.transform = `scaleY(${((12 + lv * 88 * Math.abs(Math.sin(t * 4 + i * .8))) / 100).toFixed(2)})`; if (barCol !== col) b.style.background = col; }); barCol = col; }
  const wv = $('wave'), on = m.state !== 'IDLE'; wv.style.visibility = on ? 'visible' : 'hidden';
  if (on) { const w = wv.clientWidth, h = wv.clientHeight; if (wv.width !== w * 2) { wv.width = w * 2; wv.height = h * 2; } const c = wv.getContext('2d'), lv = J.level(t); c.setTransform(2, 0, 0, 2, 0, 0); c.clearRect(0, 0, w, h); c.lineWidth = 2; c.strokeStyle = col; 
    for (let k = 0; k < 2; k++) { c.globalAlpha = k ? .35 : 1; c.beginPath(); for (let x = 0; x <= w; x += 3) { const u = x / w, env = Math.sin(u * 3.1416) ** 1.5, y = h / 2 + Math.sin(u * 14 + t * (6 + k * 2) + k) * env * h * .42 * (.25 + lv); x ? c.lineTo(x, y) : c.moveTo(x, y); } c.stroke(); } } }
new ResizeObserver(() => { sizeCanvas(); sizeSky(); sizeCam(); }).observe(document.body);

// ================= live data from the Jarvis core (see ui_next/bridge); demo content stays only when no core is connected =================
const toT = (ts) => { const d = new Date(ts); return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
const WCODE = (c, desc) => { if (c == null) { const d = String(desc || '').toLowerCase(); return /снег|сніг/.test(d) ? 'snow' : /дожд|дощ|ливен|гроз/.test(d) ? 'rain' : /ясно|солнечно|сонячно/.test(d) ? 'clear' : /пасмур|хмар|туман/.test(d) ? 'cloudy' : 'partly'; }
  return c === 0 ? 'clear' : c <= 2 ? 'partly' : c === 3 || c === 45 || c === 48 ? 'cloudy' : (c >= 71 && c <= 77) || c === 85 || c === 86 ? 'snow' : 'rain'; };
J.on('live', () => { m.upcoming = []; m.log = []; document.querySelectorAll('.ni .bd').forEach((b) => b.remove()); renderNext(); renderHist(); });
J.on('conn', () => { setNotice('conn', m.connected ? null : { sev: 'warn', text: 'Нет связи с Jarvis: запущен ли он?' }); });
J.on('state', () => { setNotice('loading', m.loading ? { sev: 'info', text: 'Jarvis загружается…' } : null); });
J.on('game', () => { setGame(!!m.game); });
J.on('notices', () => { for (const k of Object.keys(notices)) if (k.startsWith('core:')) delete notices[k]; for (const n of m.notices) notices['core:' + n.id] = { sev: n.sev, text: n.text }; renderMsg(); });
const setBadge = (label, n) => { const b = [...document.querySelectorAll('.ni')].find((x) => x.title === label); if (!b) return; let bd = b.querySelector('.bd'); if (!n) { if (bd) bd.remove(); return; } if (!bd) { b.insertAdjacentHTML('beforeend', '<span class="bd"></span>'); bd = b.querySelector('.bd'); } bd.textContent = n; };
J.on('timers', () => { const t = m.timers || {}, up = []; timerEnd = 0;
  if (t.timer) { timerEnd = Date.now() + t.timer.remaining * 1000; up.push({ kind: 'timer', label: t.timer.label || 'Таймер', t: toT(timerEnd) }); }
  for (const r of t.reminders || []) up.push({ kind: 'reminder', label: r.text, t: toT(r.at), note: 'напоминание' });
  m.upcoming = up; renderNext(); setBadge('Напоминания', (t.reminders || []).length); });
J.on('history', () => { m.log = m.history.map((h) => ({ t: toT(h.ts), said: h.said, did: h.did, kind: 'info' })); renderHist(); });
J.on('weather', () => { const w = m.weather; if (!w || !w.ok) return; Object.assign(WX, { city: w.city, temp: w.temp, feels: w.feels, wind: w.wind, wdir: w.wind_dir, gust: w.gust, hum: w.humidity, pres: w.pressure, uv: w.uv, pop: w.pop, vis: w.vis_km, tmax: w.tmax, tmin: w.tmin, aqi: w.aqi, yest: w.vs_yesterday, sr: w.sunrise, ss: w.sunset, cond: WCODE(w.code, w.desc) }); paintWeather(); });


// ---- views: Overview (dashboard) and Commands; other sections announce that they are coming ----
function showView(v) { VIEW = v; $('app').dataset.view = v === 'dash' ? '' : v;
  document.querySelectorAll('.ni[data-nav]').forEach((b) => { if (b.dataset.nav) b.classList.toggle('on', b.dataset.nav === v); });
  if (v === 'dash') { requestAnimationFrame(() => layout()); wake(); } else if (v === 'rems') window.renderRems(); else if (v === 'games') window.renderGames(); else if (v === 'exts') window.renderExts(); else if (v === 'songs') window.renderSongs(); else if (v === 'videos') window.renderVideos(); else if (v === 'voice') window.renderVoice(); else if (v === 'mail') window.renderMail(); else if (v === 'calendar') window.renderCalendar(); else if (v === 'look') window.renderLook(); else if (v === 'cinema') window.renderCinema(); else if (v === 'perf') window.renderPerf(); else if (window.renderCommands) window.renderCommands(); }
let soonTimer = 0;
$('nav').addEventListener('click', (e) => { const b = e.target.closest('.ni'); if (!b) return;
  if (b.dataset.nav) { showView(b.dataset.nav); return; }
  setNotice('soon', { sev: 'info', text: `Раздел «${b.dataset.label || b.title}» появится в следующих версиях` }); clearTimeout(soonTimer); soonTimer = setTimeout(() => setNotice('soon', null), 3500); });

// ---- commands from the core ("open settings", "show the window", reactor effects by voice) ----
const CORE_TINT = { red: C.red, cyan: C.cyan, green: C.green, amber: C.amber, magenta: C.mag, white: '#ffffff' };
const coreBurst = () => { for (let i = 0; i < 3; i++) setTimeout(() => waves.push(performance.now() / 1000), i * 160); };
J.on('uicmd', () => { const c = m.uicmd || {};
  if (c.op === 'show') { const T = window.__TAURI__; if (T && T.core) T.core.invoke('show_window').catch(() => {}); }
  else if (c.op === 'view') showView(c.name || 'dash');
  else if (c.op === 'wizard') { showView('dash'); if (window.openWizard) window.openWizard(); }
  else if (c.op === 'compose') { showView('mail'); if (window.MailC) window.MailC.open(); }
  else if (c.op === 'mail') {   // the core's background check found new mail or a changed unread count (ui_next/bridge/mail_watch.py)
    setBadge('Почта', c.unread);
    const A = window.MailApp; if (A) { A.S.unreadInbox = c.unread; if (VIEW === 'mail') { if (c.new) A.loadList({ silent: true, refresh: true }); else A.refreshUnread(); } }
  }
  else if (c.op === 'reactor') { if (c.what === 'color') coreTint = CORE_TINT[c.color] || ''; else if (c.what === 'reset') coreTint = ''; else if (c.what === 'pulse') coreBurst(); else if (c.what === 'glitch') { const keep = coreTint; ['red', 'magenta', 'white', 'cyan'].forEach((k, i) => setTimeout(() => { coreTint = CORE_TINT[k]; }, i * 110)); setTimeout(() => { coreTint = keep; }, 520); coreBurst(); } }
});

J.on('conn', () => { if (m.connected) J.send('mail', { op: 'unread' }).then((r) => { if (r && r.ok && r.unread != null) setBadge('Почта', r.unread); }); });   // a window that opens later still shows the count

// ---- microphone card: configured gain/threshold (live from the core), "hearing" readout from the last voice onset, Windows autostart ----
let autoOn = false;
const setAuto = (on) => { autoOn = !!on; $('asw').classList.toggle('on', autoOn); $('asw').setAttribute('aria-pressed', autoOn); };
$('asw').onclick = async () => { const want = !autoOn; if (m.connected) { const r = await J.send('autostart', { on: want }); if (r && r.ok) setAuto(r.on); } else setAuto(want); };
J.on('mic', () => { const mp = m.mic || {}; $('mgain').textContent = mp.gain ? '×' + Number(mp.gain).toFixed(1) : '—'; $('mthr').textContent = mp.threshold != null ? mp.threshold : '—'; });
J.on('autostart', () => setAuto(m.autostart));
function paintHear() { const el = $('hear'); let txt = 'пока тихо', col = 'var(--dim)'; if (micMuted) { el.textContent = 'выключен'; el.style.color = 'var(--amber)'; return; }
  if (m.connected) { if (m.speechTs > 0) { const s = (Date.now() - m.speechTs) / 1000; if (s < 2) { txt = 'слышит'; col = 'var(--green)'; } else { txt = s < 60 ? `${Math.floor(s)} с назад` : `${Math.floor(s / 60)} мин назад`; col = s < 120 ? 'var(--amber)' : 'var(--red)'; } } }
  else if (m.state !== 'IDLE') { txt = 'слышит'; col = 'var(--green)'; }
  const dot = col === 'var(--dim)' ? '' : '● '; el.textContent = dot + txt; el.style.color = col; }
setInterval(() => { if (!document.hidden) { paintHear(); syncCalm(); } }, 500); paintHear();
// ---- microphone on/off (the old reactor click): while muted Jarvis ignores everything until switched back ----
function setMuted(on) { micMuted = !!on; html.classList.toggle('muted', micMuted); $('msw').classList.toggle('on', !micMuted); $('msw').setAttribute('aria-pressed', !micMuted); $('mic').setAttribute('aria-pressed', micMuted); $('mic').title = micMuted ? 'Микрофон выключен: нажмите, чтобы включить' : 'Выключить микрофон'; renderMsg(); paint(); paintHear(); }
async function toggleMic() { const r = await J.send('mic', { on: micMuted }); if (r && r.ok) setMuted(r.muted); else if (!m.connected) setMuted(!micMuted); }
$('mic').onclick = toggleMic; $('msw').onclick = toggleMic; J.on('muted', () => setMuted(m.muted));

if (!window.__TAURI__) { $('mgain').textContent = '×2.5'; $('mthr').textContent = '199'; }   // browser demo values
layout(); paint(); paintWeather(); setInterval(paintWeather, 15000); wake();
const _layout = layout; layout = function () { _layout(); paintWeather(); };
// demo presets from the shell (env JARVIS_Q), e.g. "t=12:00;w=rain;x;n;g;c" = time, weather, mic problem, notices, guard, camera
function applyDemo(q) { if (!q || q === 'full' || q === 'lite') return; for (const part of q.split(';')) { const [k, v] = part.split('='); if (k === 'cat') { window.cmdsCategory(v); continue; } if (k === 'z') { setMuted(true); continue; } if (k === 'v') { showView(v); continue; } if (k === 'q') { $('cm-q').value = v; $('cm-q').dispatchEvent(new Event('input')); continue; } if (k === 'th') { if (v !== THEME.id) { try { localStorage.setItem('jarvisTheme', v); } catch (e) {} location.reload(); return; } continue; }
  if (k === 't') demoT = toMin(v); else if (k === 'w') WX.cond = v; else if (k === 'x') { problem = true; setNotice('mic', { sev: 'err', text: 'Микрофон не отвечает — проверьте подключение' }); }
  else if (k === 'n') { setNotice('mail', { sev: 'info', text: 'Почта: 3 новых письма' }); setNotice('bat', { sev: 'warn', text: 'Низкий заряд батареи — 14%' }); setNotice('timer', { sev: 'info', text: 'Таймер на 10 минут запущен' }); }
  else if (k === 'g') { guardOn = true; camOn = false; paintCam(); } else if (k === 'c') { camOn = true; paintCam(); } else if (k === 'm') { setGame(true); } } layout(); }
if (window.__TAURI__) window.__TAURI__.core.invoke('get_quality').then(applyDemo);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(layout); setTimeout(layout, 600);
