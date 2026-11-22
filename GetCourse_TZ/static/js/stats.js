/* GetCourse — анимации и подсказки на странице статистики */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 1. Полосы и столбики «вырастают», когда блок появляется на экране.
  function grow(root) {
    root.querySelectorAll('[data-w]').forEach(function (el) { el.style.width = el.dataset.w + '%'; });
    root.querySelectorAll('[data-h]').forEach(function (el) { el.style.height = Math.max(el.dataset.h, 1) + '%'; });
    root.querySelectorAll('[data-attempts]').forEach(function (el) {
      var v = parseFloat(el.dataset.attempts), max = parseFloat(el.dataset.max) || v;
      el.style.width = 'calc(' + (v / max * 100) + '% - 8px)';
    });
  }
  var blocks = document.querySelectorAll('.st-card, .st-tile');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { setTimeout(function () { grow(e.target); }, 150); io.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    blocks.forEach(function (b) { io.observe(b); });
  } else {
    blocks.forEach(grow);
  }

  // 2. Главные числа «досчитывают» до значения.
  document.querySelectorAll('.st-num[data-count]').forEach(function (el) {
    var target = parseInt(el.dataset.count, 10) || 0, suffix = el.dataset.suffix || '';
    if (reduce || target === 0) return;
    var start = null, dur = 900;
    el.textContent = '0' + suffix;
    function step(t) {
      if (!start) start = t;
      var p = Math.min((t - start) / dur, 1), eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });

  // 3. Подсказка при наведении (и при фокусе с клавиатуры).
  var tip = document.querySelector('.st-tip');
  if (!tip) return;
  function show(el, x, y) {
    tip.textContent = el.dataset.tip; tip.hidden = false;
    var r = tip.getBoundingClientRect();
    var left = Math.min(x + 14, window.innerWidth - r.width - 10);
    var top = y - r.height - 12; if (top < 8) top = y + 18;
    tip.style.left = left + 'px'; tip.style.top = top + 'px';
    tip.classList.add('is-on');
  }
  function hide() { tip.classList.remove('is-on'); }
  document.querySelectorAll('[data-tip]').forEach(function (el) {
    el.addEventListener('pointermove', function (e) { show(el, e.clientX, e.clientY); });
    el.addEventListener('pointerleave', hide);
    el.addEventListener('focus', function () { var r = el.getBoundingClientRect(); show(el, r.left + r.width / 2, r.top); });
    el.addEventListener('blur', hide);
  });
})();
