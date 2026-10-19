/* Number stepper: wraps `input.rm-in.num[type=number]` into [−] value [+] and replaces the native spinner.
   window.fzStepper.enhance(root) is idempotent; call it after rendering markup that contains such inputs. */
(function () {
  const MINUS = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M5 12h14"/></svg>';
  const PLUS = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';

  function bump(inp, dir) {
    const min = inp.min === '' ? 0 : +inp.min, max = inp.max === '' ? Infinity : +inp.max;
    const cur = parseInt(inp.value, 10);
    const next = Number.isNaN(cur) ? (dir > 0 ? min || 1 : min) : Math.min(max, Math.max(min, cur + dir));
    inp.value = String(next);
    inp.classList.remove('bad');
    inp.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function hold(btn, inp, dir) {
    let t1, t2;
    const stop = () => { clearTimeout(t1); clearInterval(t2); };
    btn.addEventListener('pointerdown', (e) => {
      if (e.button) return;
      e.preventDefault(); bump(inp, dir);
      t1 = setTimeout(() => { t2 = setInterval(() => bump(inp, dir), 70); }, 420);
    });
    ['pointerup', 'pointerleave', 'pointercancel', 'blur'].forEach((n) => btn.addEventListener(n, stop));
    btn.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); bump(inp, dir); } });
  }

  function enhance(root) {
    (root || document).querySelectorAll('input.rm-in.num[type=number]').forEach((inp) => {
      if (inp.parentNode.classList.contains('stp')) return;
      const wrap = document.createElement('span'); wrap.className = 'stp';
      const mk = (cls, html, label, dir) => {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'st-b ' + cls; b.innerHTML = html; b.setAttribute('aria-label', label); b.tabIndex = -1;
        hold(b, inp, dir); return b;
      };
      inp.parentNode.insertBefore(wrap, inp);
      wrap.append(mk('st-m', MINUS, 'Меньше', -1), inp, mk('st-p', PLUS, 'Больше', 1));
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowUp') { e.preventDefault(); bump(inp, 1); } else if (e.key === 'ArrowDown') { e.preventDefault(); bump(inp, -1); }
      });
    });
  }

  window.fzStepper = { enhance };
  enhance(document);
})();
