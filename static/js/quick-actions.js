(() => {
    const dialog = document.getElementById('quick-actions');
    if (!dialog) return;
    const query = dialog.querySelector('[data-quick-query]');
    const items = [...dialog.querySelectorAll('[data-quick-item]')];
    const groups = [...dialog.querySelectorAll('[data-quick-group]')];
    const empty = dialog.querySelector('[data-quick-empty]');
    const search = dialog.querySelector('[data-quick-search]');
    let cursor = 0;
    const visible = () => items.filter(item => !item.hidden);
    function paint() {
        const list = visible();
        cursor = Math.min(cursor, Math.max(list.length - 1, 0));
        items.forEach(item => item.classList.toggle('is-selected', item === list[cursor]));
        list[cursor]?.scrollIntoView({ block: 'nearest' });
    }
    function filter() {
        const term = query.value.trim().toLowerCase();
        items.forEach(item => { item.hidden = term !== '' && !item.dataset.label.includes(term); });
        groups.forEach(group => {
            let next = group.nextElementSibling, shown = false;
            while (next && !next.hasAttribute('data-quick-group')) { if (!next.hidden) shown = true; next = next.nextElementSibling; }
            group.hidden = !shown;
        });
        empty.hidden = visible().length > 0;
        cursor = 0;
        paint();
    }
    function open() {
        if (dialog.open) return;
        query.value = '';
        filter();
        dialog.showModal();
        query.focus();
    }
    document.addEventListener('click', event => {
        if (event.target.closest('[data-quick-open]')) { event.preventDefault(); open(); return; }
        if (event.target === dialog) dialog.close();
    });
    document.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            dialog.open ? dialog.close() : open();
        }
    });
    query.addEventListener('input', filter);
    query.addEventListener('keydown', event => {
        const list = visible();
        if (event.key === 'ArrowDown') { event.preventDefault(); cursor = (cursor + 1) % Math.max(list.length, 1); paint(); }
        else if (event.key === 'ArrowUp') { event.preventDefault(); cursor = (cursor - 1 + list.length) % Math.max(list.length, 1); paint(); }
        else if (event.key === 'Enter') {
            event.preventDefault();
            if (list[cursor]) { list[cursor].querySelector('a').click(); return; }
            const term = query.value.trim();
            if (term) { search.elements.q.value = term; search.submit(); }
        }
    });
})();
