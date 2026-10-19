document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-copy-url]');
    if (!button) return;
    const input = document.querySelector(button.dataset.copyUrl);
    if (!input) return;
    let copied = false;
    try {
        await navigator.clipboard.writeText(input.value);
        copied = true;
    } catch {
        input.select();
        copied = document.execCommand('copy');
    }
    if (!copied) return;
    const label = button.textContent;
    button.textContent = 'Tersalin';
    setTimeout(() => { button.textContent = label; }, 1500);
});
