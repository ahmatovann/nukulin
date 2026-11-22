/* GetCourse — анимации и поведение интерфейса */
(function () {
  'use strict';
  var root = document.documentElement;

  // Включаем переходы только после первой отрисовки, чтобы панель не «прыгала».
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { root.classList.remove('no-anim'); });
  });

  // 1. Сворачивание стеклянной панели (состояние запоминается).
  document.querySelectorAll('[data-side-toggle]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var collapsed = root.classList.toggle('side-collapsed');
      btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      btn.setAttribute('aria-label', collapsed ? 'Развернуть меню' : 'Свернуть меню');
      try { localStorage.setItem('gc-side', collapsed ? 'collapsed' : 'open'); } catch (e) {}
    });
  });

  // 2. Полноэкранное стеклянное меню на телефоне.
  var openBtn = document.querySelector('[data-menu-open]');
  var overlay = document.querySelector('.gm-overlay');
  function setMenu(open) {
    root.classList.toggle('menu-open', open);
    if (openBtn) openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (overlay) overlay.setAttribute('aria-hidden', open ? 'false' : 'true');
    if (open && overlay) {
      var first = overlay.querySelector('.gm-item');
      if (first) setTimeout(function () { first.focus(); }, 120);
    } else if (openBtn) {
      openBtn.focus();
    }
  }
  if (openBtn) openBtn.addEventListener('click', function () { setMenu(true); });
  document.querySelectorAll('[data-menu-close]').forEach(function (b) {
    b.addEventListener('click', function () { setMenu(false); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && root.classList.contains('menu-open')) setMenu(false);
  });

  // 3. Блоки появляются по очереди при прокрутке.
  var revealItems = document.querySelectorAll('[data-reveal]');
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });
    revealItems.forEach(function (el) { io.observe(el); });
  } else {
    revealItems.forEach(function (el) { el.classList.add('is-visible'); });
  }

  // 4. «Блик» на стеклянных карточках следует за курсором.
  document.querySelectorAll('[data-shine]').forEach(function (card) {
    card.addEventListener('pointermove', function (e) {
      var r = card.getBoundingClientRect();
      card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      card.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });

  // 5. Всплывающие сообщения исчезают сами через 5 секунд.
  document.querySelectorAll('.gc-toast').forEach(function (t, i) {
    setTimeout(function () {
      t.classList.add('is-hiding');
      t.addEventListener('animationend', function () { t.remove(); });
    }, 5000 + i * 400);
  });
})();

/* 6. Профиль: предпросмотр фото и проверка размера ещё до отправки. */
(function () {
  var input = document.querySelector('input[type=file][name=avatar]');
  if (!input) return;
  var preview = document.getElementById('avatar-preview');
  var label = document.querySelector('.gc-drop strong');
  var nameEl = document.getElementById('file-name');
  input.addEventListener('change', function () {
    var file = input.files && input.files[0];
    if (!file) return;
    var okType = /^image\/(jpeg|png)$/.test(file.type);
    var okSize = file.size <= 2 * 1024 * 1024;
    if (nameEl) {
      nameEl.textContent = okType && okSize ? file.name : 'Нужен JPG или PNG до 2 МБ';
      nameEl.style.color = okType && okSize ? '' : 'var(--error-text)';
    }
    if (!okType || !okSize || !preview) return;
    var reader = new FileReader();
    reader.onload = function (e) {
      preview.innerHTML = '';
      var img = document.createElement('img');
      img.src = e.target.result; img.alt = 'Новое фото профиля';
      preview.appendChild(img);
      if (label) label.textContent = 'Фото выбрано — нажмите «Сохранить»';
      preview.classList.remove('is-changed'); void preview.offsetWidth; preview.classList.add('is-changed');
    };
    reader.readAsDataURL(file);
  });
})();

/* 7. Восстановление пароля: клетки для кода, загрузка с точками, таймер повторной отправки. */
(function () {
  // Загрузка «Отправляем код…» — экран размывается, появляются прыгающие точки.
  document.querySelectorAll('form[data-loading]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var flow = form.closest('[data-flow]');
      if (!flow) return;
      var text = flow.querySelector('.gc-flow-loader-text');
      if (text) text.textContent = form.dataset.loading + '…';
      flow.classList.add('is-loading');
    });
  });
  window.addEventListener('pageshow', function () {
    document.querySelectorAll('[data-flow].is-loading').forEach(function (f) { f.classList.remove('is-loading'); });
  });

  // Шесть клеток: переход к следующей, Backspace назад, вставка всего кода, автоотправка.
  var form = document.querySelector('[data-otp-form]');
  if (form) {
    var cells = Array.prototype.slice.call(form.querySelectorAll('.gc-otp-cell'));
    var hidden = form.querySelector('input[name=code]');
    var group = form.querySelector('.gc-otp');
    var code = function () { return cells.map(function (c) { return c.value; }).join(''); };
    var submitIfFull = function () {
      if (code().length === cells.length) {
        hidden.value = code();
        setTimeout(function () { form.requestSubmit ? form.requestSubmit() : form.submit(); }, 250);
      }
    };
    var fill = function (from, digits) {
      digits.split('').forEach(function (d, k) {
        var cell = cells[from + k];
        if (cell) { cell.value = d; cell.classList.add('is-filled'); }
      });
      var next = cells[Math.min(from + digits.length, cells.length - 1)];
      if (next) next.focus();
      submitIfFull();
    };
    cells.forEach(function (cell, i) {
      cell.addEventListener('input', function () {
        var digits = cell.value.replace(/\D/g, '');
        cell.value = '';
        cell.classList.remove('is-filled');
        if (group) group.classList.remove('is-error');
        if (digits) fill(i, digits.slice(0, cells.length - i));
      });
      cell.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && !cell.value && i > 0) {
          cells[i - 1].value = ''; cells[i - 1].classList.remove('is-filled'); cells[i - 1].focus(); e.preventDefault();
        } else if (e.key === 'ArrowLeft' && i > 0) { cells[i - 1].focus(); }
        else if (e.key === 'ArrowRight' && i < cells.length - 1) { cells[i + 1].focus(); }
      });
      cell.addEventListener('paste', function (e) {
        var text = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
        if (!text) return;
        e.preventDefault();
        fill(0, text.slice(0, cells.length));
      });
    });
    form.addEventListener('submit', function () { hidden.value = code(); });
  }

  // «Отправить код ещё раз» — доступно через 60 секунд.
  var resend = document.querySelector('[data-resend]');
  if (resend) {
    var left = parseInt(resend.dataset.wait, 10) || 0;
    var label = resend.textContent;
    var tick = function () {
      if (left > 0) {
        resend.disabled = true;
        resend.textContent = label + ' через ' + left + ' с';
        left -= 1;
        setTimeout(tick, 1000);
      } else {
        resend.disabled = false;
        resend.textContent = label;
      }
    };
    tick();
  }
})();
