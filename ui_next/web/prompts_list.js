// Prompt kinds with a list: the files and options of a git commit, and what the deep cleanup found (see prompts.js for the shell and the protocol).
// The core checks the answer against what it offered: only listed files are staged and only listed paths are deleted.
(() => {
  const { kinds: K, esc, btn } = window.PR;
  const ST = { M: ['изменён', 'var(--amber)'], A: ['добавлен', 'var(--green)'], D: ['удалён', 'var(--red)'], R: ['переименован', 'var(--cyan)'], '?': ['новый', 'var(--green)'], U: ['конфликт', 'var(--red)'] };
  const stat = (s) => ST[(s || '?').replace(/\s/g, '')[0]] || [s || '', 'var(--dim)'];
  const size = (b) => (b >= 1073741824 ? `${(b / 1073741824).toFixed(1)} ГБ` : b >= 1048576 ? `${(b / 1048576).toFixed(1)} МБ` : `${Math.max(1, Math.round(b / 1024))} КБ`);

  // ---- git commit ----
  // Files are grouped by their top folder; a file the core flagged (secret name, build output, big file) starts unchecked, and checking it anyway asks once more.
  const WARN = { secret_name: ['секрет', 'Имя файла похоже на ключ или пароль'], build: ['сборка', 'Результат сборки или кэш: обычно не нужен в репозитории'], large: ['большой', 'Файл больше 2 МБ'], secret_text: ['ключ?', 'В тексте похоже на ключ или пароль: проверьте перед отправкой'] };
  const HARD = ['secret_name', 'build', 'large'];
  const grp = (f) => (f.file.includes('/') ? f.file.split('/')[0] + '/' : '(корень)');
  K.git = {
    rows(d, q, on) {
      const groups = new Map();
      d.files.forEach((f, i) => { if (!q || f.file.toLowerCase().includes(q)) { const g = grp(f); if (!groups.has(g)) groups.set(g, []); groups.get(g).push([f, i]); } });
      return [...groups].sort(([a], [b]) => a.localeCompare(b)).map(([g, list]) => `<div class="pr-g"><label><input type="checkbox" data-g="${esc(g)}"${list.every(([, i]) => on.has(i)) ? ' checked' : ''}><b>${esc(g)}</b><small>${list.length}</small></label></div>`
        + list.map(([f, i]) => { const [t, c] = stat(f.status), w = WARN[f.warn], rest = g === '(корень)' ? f.file : f.file.slice(g.length), cut = rest.lastIndexOf('/') + 1;
          return `<label class="pr-f"><input type="checkbox" data-i="${i}" data-g="${esc(g)}"${on.has(i) ? ' checked' : ''}><span class="pr-fs" style="color:${c}">${t}</span><span class="pr-fn" title="${esc(f.file)}"><em>${esc(rest.slice(0, cut))}</em>${esc(rest.slice(cut))}</span>`
            + (w ? `<span class="pr-w" title="${w[1]}">${w[0]}</span>` : '') + (f.add || f.del ? `<span class="pr-n"><b>+${f.add}</b>${f.del ? `<i>−${f.del}</i>` : ''}</span>` : '') + '</label>'; }).join('')).join('') || '<div class="vc-note">Ничего не найдено</div>';
    },
    render(d) {
      this.on = new Set(d.files.map((f, i) => [f, i]).filter(([f]) => !HARD.includes(f.warn)).map(([, i]) => i));
      const opts = d.branches.map((b) => `<option value="${esc(b)}"${b === d.current ? ' selected' : ''}>${esc(b)}</option>`).join('') + '<option value="__new">＋ новая ветка…</option>';
      const held = d.files.filter((f) => HARD.includes(f.warn)).length;
      return { title: 'Коммит: что отправить', wide: true, focus: '#pr-msg', actions: [{ id: 'cancel', label: 'Отмена' }, { id: 'ok', label: 'Закоммитить', primary: true }],
        hint: 'Голосом: «коммит» / «отмена»  ·  Enter / Esc',
        body: `<small class="vc-note">Репозиторий: ${esc(d.repo)}</small><div class="pr-l">Сообщение коммита<div class="pr-mr"><input id="pr-msg" maxlength="2000" placeholder="Коротко, что изменилось (можно оставить пустым)" autocomplete="off">`
          + (d.suggest ? `<button type="button" class="cm-try" data-suggest="1" title="${esc(d.suggest)}">Предложить</button>` : '') + '</div></div>'
          + `<div class="pr-row2"><label class="pr-l">Ветка<select id="pr-br">${opts}</select></label><label class="pr-l" id="pr-nbw" hidden>Имя новой ветки<input id="pr-nb" maxlength="100" placeholder="feature/name" autocomplete="off"></label></div>`
          + `<label class="pr-chk"><input type="checkbox" id="pr-push"> Сразу отправить (push)</label><div id="pr-pushopts" hidden><label class="pr-chk"><input type="checkbox" id="pr-force"> С перезаписью истории (force, с проверкой, что на сервере нет чужих изменений)</label><label class="pr-chk"><input type="checkbox" id="pr-up"> Привязать ветку (upstream)</label>`
          + `<label class="pr-l">Заголовок pull request, если нужен<input id="pr-prt" maxlength="200" placeholder="пусто: без pull request" autocomplete="off"></label></div>`
          + (held ? `<div class="vc-note pr-hold">Не отмечено заранее: ${held} (секреты, результат сборки, большие файлы). Отметьте вручную, если они действительно нужны.</div>` : '')
          + `<div class="pr-lh"><label class="pr-chk"><input type="checkbox" id="pr-all"${this.on.size === d.files.length ? ' checked' : ''}> <span id="pr-cnt">Выбрано: ${this.on.size} из ${d.files.length}</span></label>`
          + `<span class="pr-pk"><button type="button" class="cm-try" data-pick="new">Новые</button><button type="button" class="cm-try" data-pick="mod">Изменённые</button></span><input id="pr-q" class="pr-q" placeholder="Поиск по файлам" autocomplete="off"></div><div class="pr-fl" id="pr-fl">${this.rows(d, '', this.on)}</div>` };
    },
    count(r, d) { r.querySelector('#pr-cnt').textContent = `Выбрано: ${this.on.size} из ${d.files.length}`; },
    redraw(r, d) { const q = r.querySelector('#pr-q').value.trim().toLowerCase(); r.querySelector('#pr-fl').innerHTML = this.rows(d, q, this.on); r.querySelector('#pr-all').checked = this.on.size === d.files.length; this.count(r, d); },
    click(e, r, d) {
      const t = e.target;
      if (!this.on) this.on = new Set();
      if (t.id === 'pr-all') { this.on = new Set(t.checked ? d.files.map((_, i) => i) : []); this.redraw(r, d); }
      else if (t.id === 'pr-push') r.querySelector('#pr-pushopts').hidden = !t.checked;
      else if (t.matches('#pr-fl input[data-i]')) { if (t.checked) this.on.add(+t.dataset.i); else this.on.delete(+t.dataset.i); this.redraw(r, d); }
      else if (t.matches('#pr-fl input[data-g]:not([data-i])')) { d.files.forEach((f, i) => { if (grp(f) === t.dataset.g) { if (t.checked) this.on.add(i); else this.on.delete(i); } }); this.redraw(r, d); }
      const b = t.closest('button');
      if (b && b.dataset.suggest) { const m = r.querySelector('#pr-msg'); m.value = d.suggest; m.focus(); }
      if (b && b.dataset.pick) { this.on = new Set(d.files.map((f, i) => [f, i]).filter(([f]) => !HARD.includes(f.warn) && (b.dataset.pick === 'new' ? ['?', 'A'].includes((f.status || '?')[0]) : (f.status || '')[0] === 'M')).map(([, i]) => i)); this.redraw(r, d); }
    },
    collect(r, d) {
      const sel = [...this.on].sort((a, b) => a - b).map((i) => d.files[i]);
      const bad = sel.filter((f) => HARD.includes(f.warn));
      if (bad.length && r.dataset.warned !== '1') { r.dataset.warned = '1'; window.PR.toast(`Выбраны файлы с предупреждением (${bad.slice(0, 3).map((f) => f.file).join(', ')}). Нажмите «Закоммитить» ещё раз, если это нужно.`); return undefined; }
      const br = r.querySelector('#pr-br').value === '__new' ? r.querySelector('#pr-nb').value.trim() : r.querySelector('#pr-br').value;
      if (!br) { window.PR.toast('Введите имя новой ветки'); return undefined; }
      return { files: sel.map((f) => f.file), message: r.querySelector('#pr-msg').value, branch: br, push: r.querySelector('#pr-push').checked, force: r.querySelector('#pr-force').checked, upstream: r.querySelector('#pr-up').checked, pr_title: r.querySelector('#pr-prt').value };
    },
  };
  document.addEventListener('change', (e) => { const r = document.querySelector('.pr-git'); if (!r) return; if (e.target.id === 'pr-br') r.querySelector('#pr-nbw').hidden = e.target.value !== '__new'; });
  document.addEventListener('input', (e) => { if (e.target.id !== 'pr-q') return; const r = document.querySelector('.pr-git'), d = m.prompt && m.prompt.data; if (!r || !d) return; K.git.redraw(r, d); });

  // ---- cleanup review ----
  K.cleanup = {
    noEnter: true,
    render(d) {
      const total = d.items.reduce((s, x) => s + x.size, 0);
      const rows = d.items.map((x, i) => `<label class="pr-f pr-c"><input type="checkbox" data-i="${i}"><span class="pr-cn"><b>${esc(x.name)}</b><small title="${esc(x.path)}">${esc(x.path)}</small><small class="pr-cm">${size(x.size)}, не открывали ${x.age} дн.</small></span></label>`).join('');
      return { title: 'Что можно удалить', wide: true, actions: [{ id: 'cancel', label: 'Отмена' }, { id: 'ok', label: 'Удалить выбранное', primary: true, danger: true }], focus: '#pr-fl',
        body: `<small class="vc-note">Найдено папок: ${d.items.length}, всего ${size(total)}. Ничего не отмечено заранее: выберите то, что действительно не нужно. Папки удаляются насовсем, без корзины, поэтому проверьте путь каждой.</small>`
          + (d.items.length ? `<div class="vc-actions"><button type="button" class="cm-try" data-act="all">Выбрать все</button><button type="button" class="cm-try" data-act="none">Снять выбор</button><span class="pr-sel" id="pr-sel">Выбрано: 0</span></div>` : '<div class="vc-note">Ничего не найдено.</div>')
          + `<div class="pr-fl" id="pr-fl">${rows}</div>` };
    },
    sum(r, d) { const on = [...r.querySelectorAll('#pr-fl input:checked')]; r.querySelector('#pr-sel').textContent = `Выбрано: ${on.length}, ${size(on.reduce((s, c) => s + d.items[+c.dataset.i].size, 0))}`; },
    click(e, r, d) {
      const a = e.target.closest('[data-act]'); if (a) { r.querySelectorAll('#pr-fl input').forEach((c) => { c.checked = a.dataset.act === 'all'; }); }
      if (a || e.target.matches('#pr-fl input')) this.sum(r, d);
    },
    collect(r, d) { const p = [...r.querySelectorAll('#pr-fl input:checked')].map((c) => d.items[+c.dataset.i].path); if (!p.length) { window.PR.toast('Ничего не выбрано'); return undefined; } return p; },
  };
})();
