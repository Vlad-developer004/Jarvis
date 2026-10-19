// System screen: CPU, memory, disk, network, video card and connection delay, each with a two-minute chart and the details the old performance monitor showed.
// Data: topic `perf` (one sample a second, see ui_next/bridge/perf.py; the core samples only while this screen sends `watch`). Without a core it shows a local demo.
// Relies on globals of app.html: $, J, m, ic, C, esc, VIEW.
(() => {
  const body = $('pf-body');
  let sel = 'cpu', beat = 0, demo = null;
  const KB = 1024, MB = KB * KB, GB = MB * KB;
  const p1 = (n) => (Math.round(n * 10) / 10).toString().replace('.', ',');
  const bytes = (n) => (n == null ? '—' : n >= GB ? `${p1(n / GB)} ГБ` : n >= MB ? `${Math.round(n / MB)} МБ` : `${Math.round(n / KB)} КБ`);
  const rate = (n) => (n == null ? '—' : n >= MB ? `${p1(n / MB)} МБ/с` : `${Math.round(n / KB)} КБ/с`);
  const pct = (n) => (n == null ? '—' : `${p1(n)}%`);
  const ghz = (mhz) => (mhz ? `${p1(mhz / 1000)} ГГц` : '—');
  const dur = (s) => { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), mi = Math.floor(s % 3600 / 60); return d ? `${d} д ${h} ч` : h ? `${h} ч ${mi} мин` : `${mi} мин`; };
  const or = (v, f = '—') => (v == null || v === '' ? f : v);

  // One entry per tile: the series drawn, the headline value, the chart title and the detail rows.
  const METRICS = {
    cpu: { name: 'Процессор', col: C.cyan, ic: 'chip', series: ['cpu'], max: 100, head: (s) => pct(s.cpu.pct), title: (s) => s.cpu.name || 'Загрузка процессора',
      rows: (s) => [['Загрузка', pct(s.cpu.pct)], ['Частота', `${ghz(s.cpu.mhz)}${s.cpu.max_mhz ? ` из ${ghz(s.cpu.max_mhz)}` : ''}`], ['Ядра и потоки', s.cpu.cores ? `${s.cpu.cores} / ${s.cpu.threads}` : '—'], ['Процессов', or(s.cpu.procs)],
        ['Кэш L2 / L3', s.cpu.l2_kb ? `${p1(s.cpu.l2_kb / 1024)} / ${p1(s.cpu.l3_kb / 1024)} МБ` : '—'], ['Виртуализация', s.cpu.virt == null ? '—' : s.cpu.virt ? 'включена' : 'выключена'], ['Температура', s.cpu.temp == null ? 'датчик недоступен' : `${Math.round(s.cpu.temp)}°C`]] },
    ram: { name: 'Память', col: C.mag, ic: 'list', series: ['ram'], max: 100, head: (s) => pct(s.ram.pct), title: () => 'Оперативная память',
      rows: (s) => [['Занято', `${bytes(s.ram.used)} из ${bytes(s.ram.total)}`], ['Доступно', bytes(s.ram.avail)], ['Кэш', bytes(s.ram.cached)], ['Выделено системой', s.ram.committed ? `${bytes(s.ram.committed)} из ${bytes(s.ram.commit_limit)}` : '—'],
        ['Тип', [s.ram.kind, s.ram.speed ? `${s.ram.speed} МГц` : '', s.ram.form].filter(Boolean).join(', ') || '—'], ['Слоты', s.ram.slots ? `занято ${s.ram.sticks} из ${s.ram.slots}` : s.ram.sticks ? `планок: ${s.ram.sticks}` : '—'], ['Пул ядра', s.ram.paged != null ? `${bytes(s.ram.paged + s.ram.nonpaged)}` : '—']] },
    disk: { name: 'Диск', col: C.green, ic: 'timer', series: ['disk'], max: 100, head: (s) => (s.disk.active == null ? rate(s.disk.read + s.disk.write) : pct(s.disk.active)), title: () => 'Диск',
      rows: (s) => [['Активность', pct(s.disk.active)], ['Отклик', s.disk.latency_ms == null ? '—' : `${p1(s.disk.latency_ms)} мс`], ['Чтение', rate(s.disk.read)], ['Запись', rate(s.disk.write)], ['Тип', or(s.disk.kind)],
        ['Диск C:', s.disk.total ? `${bytes(s.disk.used)} из ${bytes(s.disk.total)} (${pct(s.disk.pct)})` : '—']] },
    net: { name: 'Сеть', col: C.purple, ic: 'search', series: ['dn', 'up'], max: 0, head: (s) => rate(s.net.dn), title: (s) => s.net.adapter || 'Сеть',
      rows: (s) => [['Приём', rate(s.net.dn)], ['Отдача', rate(s.net.up)], ['Адаптер', or(s.net.adapter || s.net.name)], ['Подключение', or(s.net.profile)], ['Скорость линка', or(s.net.link)], ['IPv4', or(s.net.ipv4)], ['IPv6', or(s.net.ipv6)]] },
    gpu: { name: 'Видеокарта', col: C.amber, ic: 'theme', series: ['gpu'], max: 100, head: (s) => pct(s.gpu.util), title: (s) => s.gpu.name || 'Видеокарта',
      rows: (s) => [['Нагрузка', pct(s.gpu.util)], ['Видеопамять', s.gpu.mem_used != null ? `${bytes(s.gpu.mem_used)}${s.gpu.mem_total || s.gpu.vram ? ` из ${bytes(s.gpu.mem_total || s.gpu.vram)}` : ''}` : '—'], ['Температура', s.gpu.temp == null ? 'датчик недоступен' : `${Math.round(s.gpu.temp)}°C`],
        ['Частота', s.gpu.clock ? `${Math.round(s.gpu.clock)} МГц` : '—'], ['Питание', s.gpu.power ? `${Math.round(s.gpu.power)} Вт` : '—'], ['Драйвер', or(s.gpu.driver)], ['Тип', s.gpu.name ? (s.gpu.discrete ? 'дискретная' : 'встроенная') : '—']] },
    ping: { name: 'Связь', col: C.cyan, ic: 'warn', series: ['ping'], max: 0, floor: 100, head: (s) => (s.ping == null ? 'нет связи' : `${s.ping} мс`), title: () => 'Задержка до интернета',
      rows: (s) => { const h = (s.hist.ping || []).filter((x) => x > 0); return [['Сейчас', s.ping == null ? 'нет ответа' : `${s.ping} мс`], ['Лучшая за 2 минуты', h.length ? `${Math.min(...h)} мс` : '—'], ['Средняя', h.length ? `${Math.round(h.reduce((a, b) => a + b, 0) / h.length)} мс` : '—'], ['Худшая', h.length ? `${Math.max(...h)} мс` : '—'], ['Узел', '1.1.1.1 (проверка соединения)']]; } },
  };
  const ORDER = ['cpu', 'ram', 'disk', 'net', 'gpu', 'ping'];

  function demoSample() {
    if (!demo) { demo = { hist: { cpu: [], ram: [], disk: [], dio: [], dn: [], up: [], gpu: [], ping: [] }, v: { cpu: 22, ram: 61, disk: 6, dn: 300000, up: 90000, gpu: 12, ping: 38 } }; for (let i = 0; i < 120; i++) step(); }
    step();
    const v = demo.v, h = demo.hist;
    return { ts: Date.now(), uptime: 93000, ping: Math.round(v.ping), hist: h,
      cpu: { name: 'Пример: 4 ядра, 8 потоков', pct: v.cpu, mhz: 3100, max_mhz: 4200, cores: 4, threads: 8, procs: 231, l2_kb: 5120, l3_kb: 8192, virt: true, temp: 54 },
      ram: { pct: v.ram, used: 9.8 * GB, total: 16 * GB, avail: 6.2 * GB, cached: 3.1 * GB, committed: 14 * GB, commit_limit: 24 * GB, paged: 0.4 * GB, nonpaged: 0.3 * GB, kind: 'DDR4', speed: 3200, form: 'SODIMM', sticks: 2, slots: 2 },
      disk: { active: v.disk, latency_ms: 1.2, read: v.disk * 90000, write: v.disk * 40000, kind: 'SSD', used: 380 * GB, total: 476 * GB, pct: 80 },
      net: { dn: v.dn, up: v.up, adapter: 'Wi-Fi', profile: 'Домашняя сеть', link: '866 Mbps', ipv4: '192.168.0.10', ipv6: '' },
      gpu: { name: 'Пример: встроенная графика', util: v.gpu, mem_used: 1.1 * GB, vram: 2 * GB, discrete: false, driver: '32.0.1', temp: null } };
  }
  function step() {
    const v = demo.v, r = (x, lo, hi, d) => Math.min(hi, Math.max(lo, x + (Math.random() - .5) * d));
    v.cpu = r(v.cpu, 3, 95, 14); v.ram = r(v.ram, 40, 90, 1.4); v.disk = r(v.disk, 0, 80, 12); v.dn = r(v.dn, 0, 4e6, 5e5); v.up = r(v.up, 0, 9e5, 1.6e5); v.gpu = r(v.gpu, 0, 70, 10); v.ping = r(v.ping, 15, 120, 14);
    const h = demo.hist; for (const k of ['cpu', 'ram', 'disk', 'dn', 'up', 'gpu', 'ping']) { h[k].push(Math.round(v[k] * 10) / 10); if (h[k].length > 120) h[k].shift(); }
    h.dio.push(v.disk * 130000); if (h.dio.length > 120) h.dio.shift();
  }
  const sample = () => (m.connected ? m.perf : demoSample());

  /* ---- drawing ---- */
  function chart(met, s) {
    const W = 640, H = 230, L = 8, R = 58, T = 12, B = 22, w = W - L - R, h = H - T - B;
    const ser = met.series.map((k) => (k === 'disk' && s.disk.active == null ? s.hist.dio : s.hist[k]) || []);
    const pctScale = met.max && !(met === METRICS.disk && s.disk.active == null);
    const top = pctScale ? 100 : Math.max(met.floor || 0, ...ser.flat(), 1) * 1.2;
    const unit = (v) => (pctScale ? `${Math.round(v)}%` : met === METRICS.ping ? `${Math.round(v)} мс` : rate(v).replace(' МБ/с', ' МБ/с'));
    const X = (i, n) => L + w * (i + 120 - n) / 119, Y = (v) => T + h * (1 - Math.min(Math.max(v, 0), top) / top);
    let g = '';
    for (let i = 0; i <= 4; i++) { const y = T + h * i / 4; g += `<line x1="${L}" x2="${L + w}" y1="${y}" y2="${y}" class="pf-g"/><text x="${L + w + 6}" y="${y + 3.5}" class="pf-t">${unit(top * (1 - i / 4))}</text>`; }
    g += `<text x="${L}" y="${H - 5}" class="pf-t">2 мин назад</text><text x="${L + w}" y="${H - 5}" class="pf-t" text-anchor="end">сейчас</text>`;
    const paths = ser.map((pts, si) => {
      if (pts.length < 2) return '';
      const c = si ? 'var(--cyan)' : met.col, line = pts.map((v, i) => `${i ? 'L' : 'M'}${X(i, pts.length).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
      return (si ? '' : `<path d="${line}L${X(pts.length - 1, pts.length).toFixed(1)} ${T + h}L${X(0, pts.length).toFixed(1)} ${T + h}Z" fill="${met.col}" opacity=".16"/>`) + `<path d="${line}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round"/>`;
    }).join('');
    const legend = met.series.length > 1 ? `<div class="pf-lg"><span style="--c:${met.col}">приём</span><span style="--c:var(--cyan)">отдача</span></div>` : '';
    return `<svg viewBox="0 0 ${W} ${H}" class="pf-svg" role="img" aria-label="${esc(met.name)}: график за две минуты">${g}${paths}</svg>${legend}`;
  }
  function spark(key, s) {
    const met = METRICS[key], pts = ((key === 'net' ? s.hist.dn : key === 'disk' && s.disk.active == null ? s.hist.dio : s.hist[met.series[0]]) || []).slice(-40);
    if (pts.length < 2) return '';
    const top = met.max && !(key === 'disk' && s.disk.active == null) ? 100 : Math.max(met.floor || 0, ...pts, 1) * 1.15;
    const d = pts.map((v, i) => `${i ? 'L' : 'M'}${((i + 40 - pts.length) * 80 / 39).toFixed(1)} ${(26 - 24 * Math.min(v, top) / top).toFixed(1)}`).join('');
    return `<svg viewBox="0 0 80 28" class="pf-sp"><path d="${d}" fill="none" stroke="${met.col}" stroke-width="1.6"/></svg>`;
  }
  function paint() {
    const s = sample();
    if (!s) { body.innerHTML = '<div class="rm-empty"><b>Собираю данные…</b>Первые цифры появятся через секунду.</div>'; return; }
    const met = METRICS[sel];
    $('pf-sub').textContent = `${m.connected ? '' : 'пример, ядро не подключено · '}работает ${dur(s.uptime)}`;
    body.innerHTML = `<div class="pf-tiles" role="tablist" aria-label="Что показать">${ORDER.map((k) => `<button type="button" role="tab" aria-selected="${k === sel}" class="pf-tile${k === sel ? ' on' : ''}" style="--c:${METRICS[k].col}" data-k="${k}"><span class="pf-n">${ic(METRICS[k].ic, METRICS[k].col, 16)}${METRICS[k].name}</span><b>${esc(METRICS[k].head(s))}</b>${spark(k, s)}</button>`).join('')}</div>`
      + `<div class="pf-main"><div class="pf-card"><h3 style="--c:${met.col}">${esc(met.title(s))}</h3>${chart(met, s)}</div>`
      + `<div class="pf-card"><dl class="pf-rows">${met.rows(s).map(([a, b]) => `<div><dt>${a}</dt><dd>${esc(String(b))}</dd></div>`).join('')}</dl></div></div>`;
  }

  const T = window.__TAURI__; if (T && T.core) { $('pf-mini').hidden = false; $('pf-mini').onclick = () => T.core.invoke('open_perf_mini').catch(() => {}); }   // the pinned monitor is a second window of the Tauri shell
  body.addEventListener('click', (e) => { const b = e.target.closest('[data-k]'); if (b) { sel = b.dataset.k; paint(); } });
  function watch() { if (VIEW !== 'perf') { clearInterval(beat); beat = 0; return; } if (m.connected) J.send('perf', { op: 'watch' }).then((r) => { if (r && r.snapshot && !m.perf) { m.perf = r.snapshot; paint(); } }); else paint(); }
  window.renderPerf = () => { clearInterval(beat); watch(); beat = setInterval(() => (m.connected && VIEW === 'perf' ? watch() : (VIEW === 'perf' ? paint() : (clearInterval(beat), beat = 0))), m.connected ? 5000 : 1000); paint(); };
  J.on('perf', () => { if (VIEW === 'perf') paint(); });
  J.on('conn', () => { if (VIEW === 'perf') window.renderPerf(); });
})();
