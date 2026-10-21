// Videos screen: the videos saved by voice ("save the video") with thumbnail, title, author and length; open or remove them here.
// Data comes from the `tools` bridge command (op `state`, `video_meta`, `video_del`, `open_url`); the storage limit stays in Settings > Tools.
// Without a core it shows two sample entries. Relies on globals of app.html: $, J, m, esc, VIEW.
(() => {
  const DEMO = [{ ts: '2026-10-18 21:40', url: 'https://youtu.be/dQw4w9WgXcQ' }, { ts: '2026-10-17 09:12', url: 'https://www.youtube.com/watch?v=aqz-KE-bpKQ' }];
  const body = $('vd-body'), toast = $('vd-toast'), count = $('vd-count'), search = $('vd-q');
  const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
  let videos = [], vm = {}, q = '', toastTimer = 0, metaTry = 0;
  const say = (t) => { toast.textContent = t; toast.classList.add('on'); clearTimeout(toastTimer); toastTimer = setTimeout(() => toast.classList.remove('on'), 3200); };
  const vdate = (ts) => { const r = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)/.exec(ts); return r ? `${+r[3]} ${MON[+r[2] - 1]} ${r[1]}, ${r[4]}` : ts; };
  const thumbOk = (t) => /^data:image\/jpeg;base64,[A-Za-z0-9+\/=]+$/.test(t || '');
  // the picture needs no help from the core: YouTube serves it to the page directly, so it shows while the title is still on its way
  const vidOf = (u) => (/^https?:\/\/(?:www\.|m\.|music\.)?(?:youtube\.com\/(?:watch\?(?:[^#\s]*&)?v=|shorts\/|live\/)|youtu\.be\/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])/.exec(u) || [])[1];
  const thumbOf = (x, u) => (thumbOk(x.thumb) ? x.thumb : vidOf(u) ? `https://i.ytimg.com/vi/${vidOf(u)}/mqdefault.jpg` : '');
  const short = (u) => (u.length > 46 ? u.slice(0, 44) + '…' : u);
  const pl = (n) => `${n} видео`;

  function render() {
    count.textContent = videos.length ? pl(videos.length) : '';
    search.hidden = videos.length < 6;
    const f = q.trim().toLowerCase();
    const list = f ? videos.filter((v) => { const x = vm[v.url] || {}; return `${x.title || ''} ${x.author || ''} ${v.url}`.toLowerCase().includes(f); }) : videos;
    if (!list.length) { body.innerHTML = `<div class="vd-empty">${f ? 'Ничего не найдено.' : 'Пока ничего не сохранено. Скажите «сохрани видео», когда оно играет.'}</div>`; return; }
    body.innerHTML = `<div class="vd-grid">${list.map((v) => { const x = vm[v.url] || {};
      return `<div class="vd-card"><span class="vd-th"${thumbOf(x, v.url) ? ` style="background-image:url('${thumbOf(x, v.url)}')"` : ''}>${x.duration ? `<em>${esc(x.duration)}</em>` : ''}</span>`
        + `<div class="vd-t"><b>${esc(x.title || short(v.url))}</b><small>${x.author ? esc(x.author) + ' · ' : ''}${esc(vdate(v.ts))}</small>`
        + `<div class="vd-b"><button type="button" class="cm-try" data-open="${esc(v.url)}">Открыть</button><button type="button" class="cm-try tl-del" data-del="${esc(v.ts)}" data-url="${esc(v.url)}">Удалить</button></div></div></div>`; }).join('')}</div>`;
  }
  async function fetchMeta() {
    if (!m.connected || !videos.length) return;
    const r = await J.send('tools', { op: 'video_meta', urls: videos.map((v) => v.url) }); if (!r || !r.ok) return;
    Object.assign(vm, r.items); if (VIEW === 'videos') render();
    if (r.pending > 0 && metaTry++ < 20) setTimeout(fetchMeta, 600);
  }
  async function load() {
    if (!m.connected) { videos = DEMO.map((v) => ({ ...v })); render(); return; }
    const r = await J.send('tools', { op: 'state' });
    if (r && r.ok) { videos = r.videos || []; render(); metaTry = 0; fetchMeta(); }
  }
  search.addEventListener('input', () => { q = search.value; render(); });
  body.addEventListener('click', async (e) => {
    const b = e.target.closest('button'); if (!b) return;
    if (b.dataset.open) { if (m.connected) J.send('open_url', { url: b.dataset.open }); else say('Без ядра ссылку не открыть'); return; }
    if (b.dataset.del) {
      if (!m.connected) { say('Без ядра изменить нельзя'); return; }
      const r = await J.send('tools', { op: 'video_del', ts: b.dataset.del, url: b.dataset.url });
      if (r && r.ok) { say('Видео убрано из списка'); load(); } else say('Не получилось удалить');
    }
  });
  J.on('live', () => { if (VIEW === 'videos') load(); });
  window.renderVideos = load;
})();
