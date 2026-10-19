/* Panduan tetap dapat dinavigasi dan dicari tanpa JavaScript. */
(() => {
    const page = document.querySelector('[data-docs-page]');
    if (!page) return;

    const menu = page.querySelector('.docs-menu');
    const mobile = window.matchMedia('(max-width: 767px)');
    const setMenu = () => { if (menu) menu.open = !mobile.matches; };
    setMenu();
    mobile.addEventListener('change', setMenu);

    const printButton = page.querySelector('[data-docs-print]');
    if (printButton) {
        printButton.hidden = false;
        printButton.addEventListener('click', () => window.print());
    }

    const links = [...page.querySelectorAll('[data-docs-anchor]')];
    if ('IntersectionObserver' in window && links.length) {
        const observer = new IntersectionObserver(entries => {
            const entry = entries.find(item => item.isIntersecting);
            if (!entry) return;
            links.forEach(link => {
                if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
                else link.removeAttribute('aria-current');
            });
        }, { rootMargin: '-10% 0px -65% 0px' });
        page.querySelectorAll('.docs-section').forEach(section => observer.observe(section));
    }

    const calculator = page.querySelector('[data-docs-calculator]');
    if (!calculator) return;
    const inputs = [...calculator.querySelectorAll('[data-demo-task]')];
    const reset = calculator.querySelector('[data-demo-reset]');
    const format = new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 });
    const update = () => {
        const totalWeight = inputs.reduce((sum, input) => sum + Number(input.dataset.weight), 0);
        const actual = inputs.reduce((sum, input) => sum + Number(input.value) * Number(input.dataset.weight), 0) / totalWeight;
        const variance = actual - 60;
        inputs.forEach(input => {
            calculator.querySelector(`[data-demo-value="${input.dataset.demoTask}"]`).value = `${format.format(input.value)}%`;
        });
        calculator.querySelector('[data-demo-actual]').textContent = format.format(actual);
        calculator.querySelector('[data-demo-variance]').textContent = `${variance < 0 ? '−' : variance > 0 ? '+' : ''}${format.format(Math.abs(variance))}`;
        calculator.querySelector('[data-demo-formula]').textContent = `(${inputs[0].value} × 1 + ${inputs[1].value} × 3) ÷ 4 = ${format.format(actual)}%`;
        const y = 128 - actual * 1.08;
        calculator.querySelector('[data-demo-path]').setAttribute('d', `M28 128L104 122L180 112L256 99L330 ${y}`);
        calculator.querySelector('[data-demo-dot]').setAttribute('cy', y);
        calculator.querySelector('#demo-chart-title').textContent = `Rencana hari ini 60 persen; aktual ${format.format(actual)} persen.`;
    };
    inputs.forEach(input => {
        input.disabled = false;
        input.addEventListener('input', update);
    });
    reset.hidden = false;
    reset.addEventListener('click', () => {
        inputs.forEach(input => { input.value = input.defaultValue; });
        update();
    });
    calculator.querySelector('.demo-noscript').hidden = true;
})();
