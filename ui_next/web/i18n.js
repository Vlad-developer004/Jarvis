// Interface language. The source is written in Russian; with the Ukrainian language chosen (Voice settings, or the first-run wizard) the texts are replaced
// at the moment they are drawn, so no screen needs to know about languages. The catalog is i18n_uk.js: Russian fragment -> Ukrainian (I18N_UK) and the short
// words that are replaced only as whole words (I18N_WORDS: months, weekdays, units, the plural forms).
// Pieces of text are matched, not whole sentences, so a line built from parts ("Найдено: 5 команд") is translated too. What the user or a service wrote (mail,
// calendar titles, answers) is marked translate="no" and left alone. Changing the language reloads the page: the Russian text is never restored in place.
// Must come after the markup and after shared.js (it wraps J.send to notice the language being changed).
(() => {
  const KEY = 'uiLang', CY = 'А-Яа-яЁёІіЇїЄєҐґ', CYR = new RegExp(`[${CY}]`);
  const get = () => { try { return localStorage.getItem(KEY) || ''; } catch (x) { return ''; } };
  const put = (v) => { try { localStorage.setItem(KEY, v); } catch (x) {} };
  let test = ''; try { test = sessionStorage.getItem('uiLangTest') || ''; } catch (x) {}   // a test run forces a language for this window only, without touching what is stored
  const lang = (test || get()) === 'uk' ? 'uk' : 'ru';
  const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  function change(next) {
    next = next === 'uk' ? 'uk' : 'ru';
    if (next === lang) return;
    put(next); location.reload();
  }
  // keep(): text the user or the core wrote (a voice phrase, a title) placed inside a sentence of the screen; the Ukrainian layer leaves what is between the marks as it is
  window.I18N = { lang, change, tr: (s) => s, keep: (s) => s, missing: () => [] };

  // the language is the core's setting: this window follows it when it was changed elsewhere (the old window, a voice command)
  if (typeof J !== 'undefined') {
    const send = J.send.bind(J);
    J.send = async (cmd, body) => {
      const r = await send(cmd, body);
      if (cmd === 'voice' && body && body.op === 'set' && body.key === 'language' && r && r.ok) change(body.value);
      return r;
    };
    J.on('lang', () => {      // the core publishes its language when it connects and whenever it changes
      const l = m.lang;
      if (!l || test) return;
      if (l === lang) { try { sessionStorage.removeItem('uiLangTried'); } catch (x) {} return; }
      let tried = ''; try { tried = sessionStorage.getItem('uiLangTried') || ''; } catch (x) {}
      if (tried === l) return;                                  // storage that does not keep the choice must not turn into a reload loop
      try { sessionStorage.setItem('uiLangTried', l); } catch (x) {}
      change(l);
    });
  }
  if (lang !== 'uk') return;

  document.documentElement.lang = 'uk';
  const UK = window.I18N_UK || {}, WORDS = window.I18N_WORDS || {}, ALL = { ...UK, ...WORDS };
  const exact = new Map(Object.entries(ALL));
  // pieces found inside longer text: only whole words or phrases (a letter on either side forbids the match), longest first
  const keys = Object.keys(ALL).filter((k) => k.length >= 4 || k in WORDS).sort((a, b) => b.length - a.length);
  const rx = keys.length ? new RegExp(`(?<![${CY}])(?:${keys.map(esc).join('|')})(?![${CY}])`, 'g') : null;
  const TAIL = /^(\s*)([\s\S]*?)([\s.,:;]*)$/;

  const MARK = '\u2063';
  function tr(s) {
    if (!CYR.test(s)) return s;
    if (s.includes(MARK)) return s.split(MARK).map((part, i) => (i % 2 ? part : tr(part))).join('');
    const m = TAIL.exec(s); if (!m || !m[2]) return s;
    let out = exact.get(m[2]);
    if (out === undefined) out = rx ? m[2].replace(rx, (x) => ALL[x]) : m[2];
    return out === m[2] ? s : m[1] + out + m[3];
  }
  window.I18N.tr = tr; window.I18N.keep = (s) => MARK + s + MARK;

  // what people and services wrote (mail, the answer, the history of phrases, event titles, what plays) stays as it is; screens may also mark their own content translate="no"
  const SKIP = 'script,style,textarea,noscript,iframe,[translate=no],.ml-l1 b,.ml-l2,.ml-bd,.ml-rh h3,.ml-nm,.an-t,.an-txt,#hist .t1,.cl-ev,#np-title,#np-sub,.sg-txt b,.sg-art,.cm-hint';
  const doneT = new WeakMap(), doneA = new WeakMap(), ATTRS = ['title', 'placeholder', 'aria-label', 'alt'];
  const skipped = (el) => !el || !!el.closest(SKIP);
  function text(n) {
    if (doneT.get(n) === n.data) return;
    if (!skipped(n.parentElement)) { const t = tr(n.data); if (t !== n.data) n.data = t; }
    doneT.set(n, n.data);
  }
  function attr(el, name) {
    const v = el.getAttribute(name); if (v === null) return;
    const last = doneA.get(el) || (doneA.set(el, {}), doneA.get(el));
    if (last[name] === v) return;
    if (!skipped(el)) { const t = tr(v); if (t !== v) el.setAttribute(name, t); }
    last[name] = el.getAttribute(name);
  }
  function tree(root) {
    if (root.nodeType === 3) { text(root); return; }
    if (root.nodeType !== 1) return;
    if (skipped(root)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
    for (let n = root; n; n = w.nextNode()) {
      if (n.nodeType === 3) text(n);
      else if (n.nodeType === 1) for (const a of ATTRS) attr(n, a);
    }
  }

  new MutationObserver((recs) => {
    for (const r of recs) {
      if (r.type === 'childList') r.addedNodes.forEach(tree);
      else if (r.type === 'characterData') text(r.target);
      else if (r.type === 'attributes') attr(r.target, r.attributeName);
    }
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  tree(document.body); document.title = tr(document.title);

  // coverage check for tests and for finding what the catalog lacks: drawn text that still holds letters Russian has and Ukrainian does not
  // letters and words Russian has and Ukrainian does not
  const RUSSIAN = /[ыэъЫЭЪёЁ]|[А-Яа-я]*(ие|ые|ая|ое|ую|ческ|ский|ский|ений|ание|ение|ость)(?![А-Яа-яЁёІіЇїЄєҐґ])|(^|[^А-Яа-яЁёІіЇїЄєҐґ])(и|что|как|это|или|если|когда|чтобы|есть|нет|будет|можно|нужно|только|ещё|ваш\w*|свой|свои|добавить|удалить|сохранить|закрыть|открыть|выберите|нажмите)(?![А-Яа-яЁёІіЇїЄєҐґ])/i;
  window.I18N.missing = () => {
    const out = new Set(), w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) if (RUSSIAN.test(n.data) && !skipped(n.parentElement)) out.add(n.data.trim());
    document.querySelectorAll('[title],[placeholder],[aria-label]').forEach((el) => { if (skipped(el)) return; for (const a of ATTRS) { const v = el.getAttribute(a); if (v && RUSSIAN.test(v)) out.add(v); } });
    return [...out];
  };
})();
