(() => {
    const root = document.documentElement;
    const system = window.matchMedia('(prefers-color-scheme: dark)');
    const modes = ['light', 'dark', 'system'];
    const labels = {light: 'Terang', dark: 'Gelap', system: 'Sistem'};
    let preference = 'system';
    try { preference = localStorage.getItem('scope-theme') || 'system'; } catch { /* Private storage can be unavailable. */ }
    if (!modes.includes(preference)) preference = 'system';
    function paintControls() {
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            const label = labels[preference];
            button.setAttribute('aria-label', `Tema ${label}. Klik untuk ganti tema.`);
            button.setAttribute('title', `Tema: ${label}`);
        });
        document.querySelectorAll('[data-theme-choice]').forEach(button => {
            const on = button.dataset.themeChoice === preference;
            button.setAttribute('aria-pressed', String(on));
            button.classList.toggle('is-active', on);
        });
    }
    function apply() {
        root.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
        root.dataset.themeMode = preference;
        root.style.colorScheme = root.dataset.theme;
        paintControls();
        if (window.Chart) {
            const styles = getComputedStyle(root);
            const ash = styles.getPropertyValue('--color-ash').trim();
            const border = styles.getPropertyValue('--color-hairline').trim();
            const actualColor = styles.getPropertyValue('--timeline-actual').trim();
            const planColor = styles.getPropertyValue('--timeline-plan').trim();
            const surface = styles.getPropertyValue('--color-paper').trim();
            Chart.defaults.color = ash;
            Object.values(Chart.instances).forEach(chart => {
                chart.options.color = ash;
                Object.values(chart.options.scales || {}).forEach(scale => {
                    if (scale.ticks) scale.ticks.color = ash;
                    if (scale.grid) scale.grid.color = border;
                });
                chart.data.datasets.forEach(dataset => {
                    const planned = /planned|rencana/i.test(dataset.label);
                    const color = planned ? planColor : actualColor;
                    dataset.borderColor = color;
                    if ('pointBorderColor' in dataset) dataset.pointBorderColor = color;
                    dataset.pointBackgroundColor = planned ? surface : actualColor;
                    if (typeof dataset.backgroundColor === 'string') dataset.backgroundColor = color;
                });
                if (chart.options.plugins?.legend?.labels) chart.options.plugins.legend.labels.color = ash;
                chart.update('none');
            });
        }
    }
    const set = next => {
        preference = modes.includes(next) ? next : 'system';
        try { localStorage.setItem('scope-theme', preference); } catch { /* Theme still applies in memory. */ }
        apply();
    };
    window.ScopeTheme = { set, current: () => preference };
    apply();
    system.addEventListener('change', () => { if (preference === 'system') apply(); });
    document.addEventListener('click', event => {
        const choice = event.target.closest('[data-theme-choice]');
        if (choice) { set(choice.dataset.themeChoice); return; }
        const toggle = event.target.closest('[data-theme-toggle]');
        if (toggle) set(modes[(modes.indexOf(preference) + 1) % modes.length]);
    });
    document.addEventListener('DOMContentLoaded', paintControls);
})();
