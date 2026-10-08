// Keep the mounted timeline and its viewing position across daily-update saves.
document.querySelectorAll('[data-timeline-controls]').forEach(controls => {
    const panel = controls.closest('[data-fullscreen-panel]');
    const scroller = panel.querySelector('[data-timeline-scroll]');
    const grid = panel.querySelector('[data-timeline-grid]');
    const storageKey = 'scope-timeline:' + location.pathname;
    let scale = 1;
    const labelWidth = () => parseFloat(getComputedStyle(grid).getPropertyValue('--task-label-width')) || 250;
    function setScale(value) {
        scale = value;
        grid.style.width = Math.max(scroller.clientWidth, 1000) * scale + 'px';
        controls.querySelectorAll('[data-timeline-scale]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.timelineScale) === scale)));
    }
    function remember() {
        try { sessionStorage.setItem(storageKey, JSON.stringify({ scale, left:scroller.scrollLeft })); } catch { /* View still works without storage. */ }
    }
    try {
        const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null');
        if (saved && [1,2].includes(saved.scale)) { setScale(saved.scale); scroller.scrollLeft = Number(saved.left) || 0; }
    } catch { /* Invalid or unavailable storage falls back to the full project. */ }
    scroller.addEventListener('scroll', remember, { passive:true });
    controls.querySelectorAll('[data-timeline-scale]').forEach(button => button.addEventListener('click', () => {
        const ratio = (scroller.scrollLeft + scroller.clientWidth / 2 - labelWidth()) / (grid.offsetWidth - labelWidth());
        setScale(Number(button.dataset.timelineScale));
        scroller.scrollLeft = Math.max(0, labelWidth() + ratio * (grid.offsetWidth - labelWidth()) - scroller.clientWidth / 2);
        remember();
    }));
    controls.querySelector('[data-timeline-today]').addEventListener('click', () => {
        if (!grid.dataset.today) { PCC.notify('Hari ini berada di luar rentang project.'); return; }
        scroller.scrollLeft = Math.max(0, labelWidth() + Number(grid.dataset.today) / 100 * (grid.offsetWidth - labelWidth()) - scroller.clientWidth / 2);
        remember();
    });
});
