(() => {
  function initPresentationForm(root = document) {
    const form = root.querySelector('#presentation-config');
    if (!form || form.dataset.initialized) return;
    form.dataset.initialized = 'true';
    const list = form.querySelector('#slide-order');
    const field = form.querySelector('[name=sections]');
    const state = form.querySelector('#presentation-save-state');
    let dragged = null;
    const sync = () => {
      const rows = [...list.children];
      field.value = JSON.stringify(rows.map((row, index) => {
        row.querySelector('.slide-order-number').textContent = String(index + 1).padStart(2, '0');
        row.querySelector('[data-move="-1"]')?.toggleAttribute('disabled', index === 0);
        row.querySelector('[data-move="1"]')?.toggleAttribute('disabled', index === rows.length - 1);
        return {key: row.dataset.slideKey, title: row.querySelector('[data-slide-title]').value, enabled: row.querySelector('[data-enabled]').checked, show_details: row.querySelector('[data-show-details]')?.checked ?? true};
      }));
    };
    const changed = () => {sync(); if (state) state.textContent = 'Ada perubahan. Mulai presentasi juga akan menyimpan susunan ini.';};
    list.addEventListener('input', changed);
    list.addEventListener('click', event => {
      const button = event.target.closest('[data-move]'); if (!button) return;
      const row = button.closest('li');
      if (button.dataset.move === '-1' && row.previousElementSibling) list.insertBefore(row, row.previousElementSibling);
      else if (row.nextElementSibling) list.insertBefore(row.nextElementSibling, row);
      changed(); button.focus();
    });
    list.addEventListener('dragstart', event => {
      if (event.target.closest('input, button')) {event.preventDefault(); return;}
      dragged = event.target.closest('li');
      event.dataTransfer.setData('text/plain', dragged.dataset.slideKey);
      dragged.classList.add('is-dragging');
    });
    list.addEventListener('dragover', event => {if (dragged) event.preventDefault();});
    list.addEventListener('drop', event => {
      if (!dragged) return; event.preventDefault();
      const target = event.target.closest('li');
      if (target && target !== dragged) list.insertBefore(dragged, event.clientY > target.getBoundingClientRect().top + target.offsetHeight / 2 ? target.nextSibling : target);
      changed();
    });
    list.addEventListener('dragend', () => {dragged?.classList.remove('is-dragging'); dragged = null;});
    form.addEventListener('submit', sync);
    sync();
  }
  initPresentationForm();
  document.addEventListener('pcc:panel-loaded', event => initPresentationForm(event.target));
  const player = document.querySelector('[data-presentation-player]');
  if (!player) return;
  const slides = [...player.querySelectorAll('[data-slide]')];
  const previous = player.querySelector('[data-slide-prev]');
  const next = player.querySelector('[data-slide-next]');
  const jump = player.querySelector('[data-slide-jump]');
  const counter = player.querySelector('[data-slide-counter]');
  let index = 0;
  const show = value => {
    index = Math.max(0, Math.min(slides.length - 1, value));
    slides.forEach((slide, i) => {slide.hidden = i !== index;});
    previous.disabled = index === 0; next.disabled = index === slides.length - 1;
    jump.value = String(index); counter.textContent = `${index + 1} / ${slides.length}`;
    const canvas = slides[index]?.querySelector('canvas');
    if (canvas && window.Chart) requestAnimationFrame(() => Chart.getChart(canvas)?.resize());
  };
  previous.addEventListener('click', () => show(index - 1));
  next.addEventListener('click', () => show(index + 1));
  jump.addEventListener('change', () => show(Number(jump.value)));
  const fullscreen = player.querySelector('[data-presentation-fullscreen]');
  const setFullscreenLabel = () => {
    const active = Boolean(document.fullscreenElement) || player.classList.contains('presentation-fallback-fullscreen');
    fullscreen.setAttribute('aria-label', active ? 'Keluar layar penuh' : 'Layar penuh');
    fullscreen.querySelector('span').textContent = active ? 'Keluar layar penuh' : 'Layar penuh';
  };
  fullscreen.addEventListener('click', async () => {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (player.classList.contains('presentation-fallback-fullscreen')) player.classList.remove('presentation-fallback-fullscreen');
    else {try {await player.requestFullscreen();} catch {player.classList.add('presentation-fallback-fullscreen');}}
    setFullscreenLabel();
  });
  document.addEventListener('fullscreenchange', setFullscreenLabel);
  document.addEventListener('keydown', event => {
    if (event.target.closest('input, select, textarea') && event.key !== 'Escape') return;
    if (event.key === ' ' && event.target.closest('button, a')) return;
    if (event.key === 'ArrowRight' || event.key === 'PageDown' || event.key === ' ') {event.preventDefault(); show(index + 1);}
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') {event.preventDefault(); show(index - 1);}
    if (event.key === 'Home') {event.preventDefault(); show(0);}
    if (event.key === 'End') {event.preventDefault(); show(slides.length - 1);}
    if (event.key === 'Escape' && !document.fullscreenElement) {
      if (player.classList.contains('presentation-fallback-fullscreen')) {player.classList.remove('presentation-fallback-fullscreen'); setFullscreenLabel();}
      else location.href = player.querySelector('.presentation-exit').href;
    }
  });
  let touchStart = null;
  const stage = document.getElementById('presentation-stage');
  stage.addEventListener('touchstart', event => {touchStart = {x: event.changedTouches[0].clientX, y: event.changedTouches[0].clientY};}, {passive: true});
  stage.addEventListener('touchend', event => {
    if (!touchStart || event.target.closest('.slide-table-wrap')) return;
    const dx = event.changedTouches[0].clientX - touchStart.x, dy = event.changedTouches[0].clientY - touchStart.y;
    if (Math.abs(dx) > 70 && Math.abs(dy) < 50) show(index + (dx < 0 ? 1 : -1));
    touchStart = null;
  }, {passive: true});
  show(0);
})();
