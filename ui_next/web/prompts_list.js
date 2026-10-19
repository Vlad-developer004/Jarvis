// Prompt kinds with a list: the files and options of a git commit, and what the deep cleanup found (see prompts.js for the shell and the protocol).
// The core checks the answer against what it offered: only listed files are staged and only listed paths are deleted.
(() => {
  const { kinds: K, esc, btn } = window.PR;
  const ST = { M: ['изменён', 'var(--amber)'], A: ['добавлен', 'var(--green)'], D: ['удалён', 'var(--red)'], R: ['переименован', 'var(--cyan)'], '?': ['новый', 'var(--green)'], U: ['конфликт', 'var(--red)'] };
  const stat = (s) => ST[(s || '?').replace(/\s/g, '')[0]] || [s || '', 'var(--dim)'];
  const size = (b) => (b >= 1073741824 ? `${(b / 1073741824).toFixed(1)} ГБ` : b >= 1048576 ? `${(b / 1048576).toFixed(1)} МБ` : `${Math.max(1, Math.round(b / 1024))} КБ`);

  // ---- git commit ----
  K.git = {
    rows: (d, q) => d.files.map((f, i) => [f, i]).filter(([f]) => !q || f.file.toLowerCase().includes(q)).map(([f, i]) => { const [t, c] = stat(f.status);
      return `<label class="pr-f"><input type="checkbox" data-i="${i}" checked><span class="pr-fs" style="color:${c}">${t}</span><span class="pr-fn" title="${esc(f.file)}">${esc(f.file)}</span></label>`; }).join('') || '<div class="vc-note">Ничего не найдено</div>',
    render(d) {
      const opts = d.branches.map((b) => `<option value="${esc(b)}"${b === d.current ? ' selected' : ''}>${esc(b)}</option>`).join('') + '<option value="__new">＋ новая ветка…</option>';
      return { title: 'Коммит: что отправить', wide: true, focus: '#pr-msg', actions: [{ id: 'cancel', label: 'Отмена' }, { id: 'ok', label: 'Закоммитить', primary: true }],
        hint: 'Голосом: «коммит» / «отмена»  ·  Enter / Esc',
        body: `<small class="vc-note">Репозиторий: ${esc(d.repo)}</small><label class="pr-l">Сообщение коммита<input id="pr-msg" maxlength="2000" placeholder="Коротко, что изменилось (можно оставить пустым)" autocomplete="off"></label>`
          + `<div class="pr-row2"><label class="pr-l">Ветка<select id="pr-br">${opts}</select></label><label class="pr-l" id="pr-nbw" hidden>Имя новой ветки<input id="pr-nb" maxlength="100" placeholder="feature/name" autocomplete="off"></label></div>`
          + `<label class="pr-chk"><input type="checkbox" id="pr-push"> Сразу отправить (push)</label><div id="pr-pushopts" hidden><label class="pr-chk"><input type="checkbox" id="pr-force"> С перезаписью истории (force)</label><label class="pr-chk"><input type="checkbox" id="pr-up"> Привязать ветку (upstream)</label>`
          + `<label class="pr-l">Заголовок pull request, если нужен<input id="pr-prt" maxlength="200" placeholder="пусто: без pull request" autocomplete="off"></label></div>`
          + `<div class="pr-lh"><label class="pr-chk"><input type="checkbox" id="pr-all" checked> Выбрать все (${d.files.length})</label><input id="pr-q" class="pr-q" placeholder="Поиск по файлам" autocomplete="off"></div><div class="pr-fl" id="pr-fl">${this.rows(d, '')}</div>` };
    },
    click(e, r, d) {
      if (e.target.id === 'pr-all') r.querySelectorAll('#pr-fl input[type=checkbox]').forEach((c) => { c.checked = e.target.checked; });
      if (e.target.id === 'pr-push') r.querySelector('#pr-pushopts').hidden = !e.target.checked;
    },
    collect(r, d) {
      const sel = [...r.querySelectorAll('#pr-fl input[type=checkbox]:checked')].map((c) => d.files[+c.dataset.i].file);
      const br = r.querySelector('#pr-br').value === '__new' ? r.querySelector('#pr-nb').value.trim() : r.querySelector('#pr-br').value;
      if (!br) { window.PR.toast('Введите имя новой ветки'); return undefined; }
      return { files: sel, message: r.querySelector('#pr-msg').value, branch: br, push: r.querySelector('#pr-push').checked, force: r.querySelector('#pr-force').checked, upstream: r.querySelector('#pr-up').checked, pr_title: r.querySelector('#pr-prt').value };
    },
  };
  document.addEventListener('change', (e) => { const r = document.querySelector('.pr-git'); if (!r) return; if (e.target.id === 'pr-br') r.querySelector('#pr-nbw').hidden = e.target.value !== '__new'; });
  document.addEventListener('input', (e) => { if (e.target.id !== 'pr-q') return; const r = document.querySelector('.pr-git'), d = m.prompt && m.prompt.data; if (!r || !d) return;
    const keep = new Set([...r.querySelectorAll('#pr-fl input:checked')].map((c) => c.dataset.i)); const fl = r.querySelector('#pr-fl'); fl.innerHTML = K.git.rows(d, e.target.value.trim().toLowerCase()); fl.querySelectorAll('input').forEach((c) => { c.checked = keep.has(c.dataset.i); }); });

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
