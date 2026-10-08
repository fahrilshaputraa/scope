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
    }
    function apply() {
        root.dataset.theme = preference === 'system' ? (system.matches ? 'dark' : 'light') : preference;
        root.dataset.themeMode = preference;
        root.style.colorScheme = root.dataset.theme;
        paintControls();
        if (window.Chart) {
            const styles = getComputedStyle(root);
            const ink = styles.getPropertyValue('--color-ink').trim();
            const ash = styles.getPropertyValue('--color-ash').trim();
            const border = styles.getPropertyValue('--color-hairline').trim();
            Chart.defaults.color = ash;
            Object.values(Chart.instances).forEach(chart => {
                chart.options.color = ash;
                Object.values(chart.options.scales || {}).forEach(scale => {
                    if (scale.ticks) scale.ticks.color = ash;
                    if (scale.grid) scale.grid.color = border;
                });
                chart.data.datasets.forEach(dataset => {
                    dataset.borderColor = /planned|rencana/i.test(dataset.label) ? ash : ink;
                    if (typeof dataset.backgroundColor === 'string') dataset.backgroundColor = /planned|rencana/i.test(dataset.label) ? ash : ink;
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
    document.addEventListener('DOMContentLoaded', () => {
        document.querySelectorAll('[data-theme-toggle]').forEach(button => {
            button.addEventListener('click', () => set(modes[(modes.indexOf(preference) + 1) % modes.length]));
        });
        paintControls();
    });
})();