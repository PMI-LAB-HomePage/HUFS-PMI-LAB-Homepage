
(function () {
  // 이메일 조립
  document.querySelectorAll('a.email[data-u][data-d]').forEach(function (a) {
    var addr = a.dataset.u + '@' + a.dataset.d;
    a.href = 'mailto:' + addr;
    a.textContent = addr;
  });

  // 모바일 메뉴
  document.querySelectorAll('.site-nav__toggle').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var nav = btn.closest('.site-nav');
      var open = nav.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open);
      btn.textContent = open ? 'CLOSE' : 'MENU';
    });
  });

  // 연도 선택: 고르면 닫는다
  document.querySelectorAll('.year-pick').forEach(function (d) {
    d.addEventListener('click', function (e) { if (e.target.closest('a')) d.open = false; });
  });

  // 라이트박스
  var lb = document.querySelector('.lightbox');
  if (!lb) return;
  var stage = lb.querySelector('.lightbox__stage');
  var counter = lb.querySelector('.lightbox__count');
  var items = [], idx = 0;
  function show(i) {
    idx = (i + items.length) % items.length;
    var src = items[idx];
    var img = src.querySelector('img');
    stage.innerHTML = '';
    if (img) { var n = new Image(); n.src = img.currentSrc || img.src; n.alt = img.alt || ''; stage.appendChild(n); }
    else { stage.appendChild(src.firstElementChild.cloneNode(true)); }
    counter.textContent = (idx + 1) + ' / ' + items.length;
  }
  function close() { lb.classList.remove('is-open'); document.body.style.overflow = ''; }
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-lightbox]');
    if (a) {
      e.preventDefault();
      items = Array.prototype.slice.call(document.querySelectorAll('[data-lightbox="' + a.dataset.lightbox + '"]'));
      lb.classList.add('is-open'); document.body.style.overflow = 'hidden';
      show(items.indexOf(a)); return;
    }
    var b = e.target.closest('[data-lb]');
    if (b) { if (b.dataset.lb === 'close') close(); if (b.dataset.lb === 'prev') show(idx - 1); if (b.dataset.lb === 'next') show(idx + 1); return; }
    if (e.target === lb) close();
  });
  document.addEventListener('keydown', function (e) {
    if (!lb.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') show(idx - 1);
    if (e.key === 'ArrowRight') show(idx + 1);
  });
})();
