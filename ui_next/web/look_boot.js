// Appearance preferences, applied before the first paint so the window never flashes the wrong theme.
// Kept in localStorage next to the older keys: jarvisTheme (theme id), uiScale, jarvisSfx; new ones are jarvisCustom, jarvisAuto, jarvisHide, jarvisFx, jarvisSfxVol.
// The settings screen (look.js) reads and writes the same keys through window.LOOK.
(() => {
  const root = document.documentElement;
  const raw = (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const setRaw = (k, v) => { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} };
  const json = (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
  const put = (k, v) => setRaw(k, JSON.stringify(v));

  const AUTO = { on: false, day: 'command', night: 'space', from: '20:00', to: '07:00' };
  const CUSTOM = { h: 197, sk: 0.9 };
  const mins = (t) => { const m = /^(\d{1,2}):(\d{2})$/.exec(t || ''); return m ? +m[1] * 60 + +m[2] : 0; };
  const isNight = (a, now = new Date()) => { const n = now.getHours() * 60 + now.getMinutes(), f = mins(a.from), t = mins(a.to); return f === t ? false : f < t ? n >= f && n < t : n >= f || n < t; };

  const auto = () => ({ ...AUTO, ...json('jarvisAuto', {}) });
  const custom = () => ({ ...CUSTOM, ...json('jarvisCustom', {}) });
  /* the id of the theme in force right now: the schedule wins while it is on */
  const themeId = () => { const a = auto(); return a.on ? (isNight(a) ? a.night : a.day) : (raw('jarvisTheme') || 'command'); };
  const pick = (themes) => {
    const id = themeId();
    if (id === 'custom') { const c = custom(); return { id: 'custom', name: 'Свой цвет', h: c.h, sk: c.sk }; }
    return themes.find((t) => t.id === id) || themes[0];
  };

  const HIDE = ['next', 'wxp', 'cam', 'sys', 'hist', 'sugg'];
  const hidden = () => { const v = json('jarvisHide', []); return Array.isArray(v) ? v.filter((k) => HIDE.includes(k)) : []; };
  const applyHide = () => { const h = hidden(); if (h.length) root.dataset.hide = h.join(' '); else delete root.dataset.hide; };
  applyHide();

  /* a theme change needs a full reload (canvas colours are read once); keep the open screen across it */
  const reload = () => { try { sessionStorage.setItem('jarvisView', (typeof VIEW !== 'undefined' && VIEW !== 'dash') ? VIEW : ''); } catch (e) {} location.reload(); };

  window.LOOK = {
    raw, setRaw, json, put, auto, custom, themeId, pick, hidden, applyHide, reload, isNight, HIDE, AUTO, CUSTOM,
    setTheme(id) { const a = auto(); if (a.on) put('jarvisAuto', { ...a, on: false }); setRaw('jarvisTheme', id); reload(); },
  };
})();
