(() => {
    const root = document.documentElement;
    const key = 'scope-rail';
    const states = ['collapsed', 'expanded'];
    let state = 'collapsed';
    try { state = localStorage.getItem(key) || 'collapsed'; } catch { /* Private storage can be unavailable. */ }
    if (!states.includes(state)) state = 'collapsed';
    function paint() {
        root.dataset.rail = state;
        document.querySelectorAll('[data-rail-toggle]').forEach(button => {
            const expanded = state === 'expanded';
            button.setAttribute('aria-pressed', String(expanded));
            button.setAttribute('aria-label', expanded ? 'Perkecil sidebar' : 'Perluas sidebar');
            button.setAttribute('title', expanded ? 'Perkecil sidebar' : 'Perluas sidebar');
            const label = button.querySelector('.nav-label');
            if (label) label.textContent = expanded ? 'Perkecil' : 'Perluas';
        });
    }
    window.ScopeRail = {
        toggle() { state = state === 'expanded' ? 'collapsed' : 'expanded'; try { localStorage.setItem(key, state); } catch { /* still applies in memory. */ } paint(); },
        current: () => state,
    };
    paint();
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-rail-toggle]').forEach(button => {
            button.addEventListener('click', () => window.ScopeRail.toggle());
        });
        paint();
    });
})();