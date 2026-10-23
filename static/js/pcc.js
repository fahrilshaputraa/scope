window.PCC = {
    trapSidebar(event) {
        const links = [...document.querySelectorAll('#main-sidebar a, #main-sidebar button')];
        if (!links.length) return;
        if (event.shiftKey && document.activeElement === links[0]) {
            event.preventDefault(); links.at(-1).focus();
        } else if (!event.shiftKey && document.activeElement === links.at(-1)) {
            event.preventDefault(); links[0].focus();
        }
    },
    notify(message, error = false) {
        const target = document.getElementById('interaction-status');
        if (!target) return;
        target.textContent = message;
        target.classList.remove('hidden');
        target.classList.toggle('is-error', error);
        target.setAttribute('role', error ? 'alert' : 'status');
        target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    },
    async update(url, data) {
        const response = await fetch(url, {
            method: 'PATCH', credentials: 'same-origin',
            headers: { 'X-CSRFToken': document.querySelector('meta[name=csrf-token]').content,
                       'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams(data),
        });
        let result;
        try { result = await response.json(); } catch { throw new Error('Sesi berakhir atau respons tidak valid. Muat ulang halaman dan coba lagi.'); }
        if (!response.ok || !result.ok) throw new Error(result.error || 'Perubahan belum tersimpan. Coba lagi.');
        return result;
    }
};

PCC.initMentions = function(root = document) {
    const forms = root.matches?.('[data-mention-form]')
        ? [root]
        : [...root.querySelectorAll('[data-mention-form]')];
    forms.forEach(form => {
        const editor = form.querySelector('.wysiwyg-editor');
        const textarea = form.querySelector('textarea[name=content]');
        const surface = editor || (textarea && !textarea.hasAttribute('data-wysiwyg') ? textarea : null);
        if (!surface || surface.dataset.mentionReady) return;
        surface.dataset.mentionReady = 'true';

        const url = form.dataset.mentionUrl;
        const project = form.dataset.mentionProject;
        if (!url || !project) return;

        const listbox = document.createElement('div');
        listbox.className = 'mention-suggest';
        listbox.id = `mention-suggest-${Math.random().toString(36).slice(2, 8)}`;
        listbox.setAttribute('role', 'listbox');
        listbox.setAttribute('aria-label', 'Saran anggota project');
        listbox.hidden = true;
        document.body.append(listbox);
        surface.setAttribute('aria-autocomplete', 'list');
        surface.setAttribute('aria-controls', listbox.id);
        surface.setAttribute('aria-expanded', 'false');

        let items = [], active = -1, context = null, timer = null, controller = null;
        const pattern = /(?:^|[\s([{"'])@([A-Za-z0-9_.@+\-]*)$/;

        const close = () => {
            listbox.hidden = true;
            listbox.replaceChildren();
            items = []; active = -1; context = null;
            surface.setAttribute('aria-expanded', 'false');
            surface.removeAttribute('aria-activedescendant');
        };

        const locate = () => {
            if (surface instanceof HTMLTextAreaElement) {
                const caret = surface.selectionStart ?? surface.value.length;
                const match = surface.value.slice(0, caret).match(pattern);
                return match ? { query: match[1], caret } : null;
            }
            const selection = window.getSelection();
            if (!selection || !selection.rangeCount || !surface.contains(selection.anchorNode)) return null;
            const range = selection.getRangeAt(0);
            if (!range.collapsed) return null;
            const before = range.cloneRange();
            before.selectNodeContents(surface);
            before.setEnd(range.startContainer, range.startOffset);
            const match = before.toString().match(pattern);
            return match ? { query: match[1], caretRange: range } : null;
        };

        const render = () => {
            listbox.replaceChildren();
            items.forEach((item, index) => {
                const option = document.createElement('div');
                option.id = `${listbox.id}-${index}`;
                option.className = 'mention-suggest-item';
                option.setAttribute('role', 'option');
                option.setAttribute('aria-selected', String(index === active));
                const name = document.createElement('strong');
                name.textContent = item.name || item.username;
                const handle = document.createElement('small');
                handle.textContent = `@${item.username}`;
                option.append(name, handle);
                option.addEventListener('pointerdown', event => {
                    event.preventDefault();
                    choose(item);
                });
                listbox.append(option);
            });
            if (active >= 0) surface.setAttribute('aria-activedescendant', `${listbox.id}-${active}`);
        };

        const position = found => {
            const rect = surface.getBoundingClientRect();
            let left = rect.left, top = rect.bottom + 6;
            if (found && found.caretRange) {
                const caret = found.caretRange.getBoundingClientRect();
                if (caret && (caret.top || caret.left)) { left = caret.left; top = caret.bottom + 6; }
            }
            listbox.hidden = false;
            listbox.style.left = `${Math.max(8, Math.min(left, window.innerWidth - listbox.offsetWidth - 8))}px`;
            if (top + listbox.offsetHeight > window.innerHeight - 8) {
                top = Math.max(8, window.innerHeight - listbox.offsetHeight - 8);
            }
            listbox.style.top = `${top}px`;
        };

        const choose = item => {
            const found = context || locate();
            if (!found) { close(); return; }
            const text = `@${item.username} `;
            if (surface instanceof HTMLTextAreaElement) {
                surface.setRangeText(text, found.caret - found.query.length - 1, found.caret, 'end');
                surface.dispatchEvent(new Event('input', { bubbles: true }));
            } else {
                const range = found.caretRange;
                const node = range.startContainer;
                if (node.nodeType === Node.TEXT_NODE && range.startOffset >= found.query.length + 1) {
                    const replace = document.createRange();
                    replace.setStart(node, range.startOffset - found.query.length - 1);
                    replace.setEnd(node, range.startOffset);
                    replace.deleteContents();
                    const textNode = document.createTextNode(text);
                    replace.insertNode(textNode);
                    const after = document.createRange();
                    after.setStartAfter(textNode);
                    after.collapse(true);
                    const selection = window.getSelection();
                    selection.removeAllRanges();
                    selection.addRange(after);
                } else {
                    document.execCommand('insertText', false, text);
                }
                surface.dispatchEvent(new Event('input', { bubbles: true }));
            }
            close();
        };

        const request = query => {
            if (timer) clearTimeout(timer);
            timer = setTimeout(async () => {
                const found = locate();
                if (!found || found.query !== query) return;
                context = found;
                controller?.abort();
                controller = new AbortController();
                try {
                    const params = new URLSearchParams({ project, q: query });
                    const response = await fetch(`${url}?${params}`, {
                        credentials: 'same-origin',
                        signal: controller.signal,
                        headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    });
                    if (!response.ok) { close(); return; }
                    const data = await response.json();
                    const latest = locate();
                    if (!Array.isArray(data) || !latest || latest.query !== query) return;
                    context = latest;
                    items = data;
                    active = data.length ? 0 : -1;
                    if (!data.length) { close(); return; }
                    render();
                    position(latest);
                    surface.setAttribute('aria-expanded', 'true');
                } catch (error) {
                    if (error.name !== 'AbortError') close();
                }
            }, 120);
        };

        surface.addEventListener('input', () => {
            const found = locate();
            if (!found) { close(); return; }
            context = found;
            request(found.query);
        });
        surface.addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (listbox.hidden) return;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                const delta = event.key === 'ArrowDown' ? 1 : -1;
                active = (active + delta + items.length) % items.length;
                render();
            } else if (event.key === 'Enter' || event.key === 'Tab') {
                if (items[active]) { event.preventDefault(); choose(items[active]); }
            } else if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                close();
            }
        });
        document.addEventListener('pointerdown', event => {
            if (!listbox.hidden && !listbox.contains(event.target) && event.target !== surface) close();
        });
        window.addEventListener('resize', close);
        document.addEventListener('scroll', event => {
            if (!listbox.hidden && !listbox.contains(event.target)) close();
        }, true);
    });
};

PCC.initForms = function(root = document) {
    root.querySelectorAll('[data-choice-picker]').forEach(picker => {
        if (picker.dataset.ready) return;
        picker.dataset.ready = 'true';
        const rows = [...picker.querySelectorAll('[data-choice-row]')];
        const search = picker.querySelector('[data-choice-search]');
        const refresh = () => {
            const selected = rows.filter(row => row.querySelector('input').checked);
            picker.querySelector('[data-choice-count]').textContent = `${selected.length} dipilih`;
            picker.querySelector('[data-choice-summary]').textContent = selected.slice(0, 3)
                .map(row => row.querySelector('.choice-name').textContent.trim()).join(', ')
                + (selected.length > 3 ? ` +${selected.length - 3} lainnya` : '');
            picker.querySelector('[data-choice-clear]').disabled = !selected.length;
        };
        search.addEventListener('input', () => {
            const query = search.value.trim().toLocaleLowerCase('id');
            rows.forEach(row => { row.hidden = !row.textContent.toLocaleLowerCase('id').includes(query); });
            picker.querySelector('[data-choice-empty]').hidden = !rows.length || rows.some(row => !row.hidden);
        });
        picker.addEventListener('change', refresh);
        picker.querySelector('[data-choice-clear]').addEventListener('click', () => {
            rows.forEach(row => { row.querySelector('input').checked = false; }); refresh();
        });
        refresh();
    });
    root.querySelectorAll('[data-simple-form]').forEach(form => {
        if (form.dataset.ready) return;
        form.dataset.ready = 'true';
        const status = form.querySelector('[name=status]');
        const sync = () => {
            form.querySelectorAll('[data-form-field=blocked_reason], [data-form-field=blocked_dependency]').forEach(row => {
                row.hidden = status && status.value !== 'blocked' && !row.querySelector('input,select,textarea').value;
                if (status?.value === 'blocked' && row.closest('details')) row.closest('details').open = true;
            });
        };
        status?.addEventListener('change', sync); sync();
    });
};

(function() {
    const drawer = document.getElementById('project-action-panel');
    const content = drawer?.querySelector('[data-panel-content]');
    const panelStatus = drawer?.querySelector('[data-panel-status]');
    const announce = message => { if (panelStatus) panelStatus.textContent = message; };
    let actionURL, busy = false, controller, opener;
    function showForm(html) {
        const page = new DOMParser().parseFromString(html, 'text/html');
        const form = page.querySelector('.pcc-form-surface');
        if (!form) { location.href = actionURL; return; }
        content.replaceChildren(form);
        drawer.dataset.panelKind = form.dataset.panelKind || '';
        content.dispatchEvent(new CustomEvent('pcc:panel-loaded', {bubbles:true}));
        const heading = form.querySelector('h1');
        if (heading) { heading.id = 'drawer-title'; drawer.setAttribute('aria-labelledby', heading.id); }
        drawer.scrollTop = 0;
        PCC.initForms(content);
        const invalid = form.querySelector('[aria-invalid=true]');
        if (invalid) announce('Form berisi kesalahan. Periksa field yang ditandai.');
        const focusTarget = invalid?.matches('input,textarea,select') ? invalid
            : invalid?.querySelector('input,textarea,select')
                || form.querySelector('input:not([type=hidden]):not([type=checkbox]), textarea, select');
        focusTarget?.focus();
    }
    document.addEventListener('click', async event => {
        const cancel = event.target.closest('[data-panel-cancel], [data-panel-close]');
        if (cancel && cancel.closest('dialog')) { event.preventDefault(); if (!busy) drawer.close(); return; }
        const link = event.target.closest('a[data-project-action]');
        if (!link || !drawer || event.ctrlKey || event.metaKey || event.shiftKey || event.button) return;
        event.preventDefault(); opener = link.closest('details')?.querySelector('summary') || link;
        link.closest('details')?.removeAttribute('open');
        actionURL = link.href;
        drawer.removeAttribute('aria-labelledby');
        content.textContent = 'Memuat form…';
        announce('Memuat form.');
        if (document.fullscreenElement) document.fullscreenElement.append(drawer);
        drawer.showModal();
        controller = new AbortController();
        try {
            const response = await fetch(actionURL, { credentials:'same-origin', signal:controller.signal });
            if (!response.ok) throw new Error('Aksi ini belum bisa dibuka. Coba muat ulang project.');
            showForm(await response.text());
        } catch (error) {
            if (error.name === 'AbortError') return;
            content.replaceChildren(); const message = document.createElement('p');
            message.textContent = error.message; message.setAttribute('role','alert'); content.append(message);
            const fallback = document.createElement('a'); fallback.href = actionURL;
            fallback.textContent = 'Buka halaman form'; fallback.className = 'pcc-button mt-4'; content.append(fallback);
        }
    });
    drawer?.addEventListener('cancel', event => { if (busy) event.preventDefault(); });
    drawer?.addEventListener('close', () => { controller?.abort(); document.body.append(drawer); opener?.focus(); });
    drawer?.addEventListener('click', event => {
        if (event.target === drawer && !busy) {
            const rect = drawer.getBoundingClientRect();
            if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) drawer.close();
        }
    });
    drawer?.addEventListener('submit', async event => {
        event.preventDefault(); if (busy) return;
        const form = event.target;
        const submit = event.submitter || form.querySelector('[type=submit], button:not([type])');
        const payload = new FormData(form, event.submitter || undefined);
        const navigateAfterSave = submit.hasAttribute('data-panel-navigate');
        const label = submit.textContent;
        busy = true; submit.disabled = true; drawer.querySelector('[data-panel-close]').disabled = true; submit.textContent = 'Menyimpan…';
        drawer.setAttribute('aria-busy','true'); announce('Menyimpan perubahan…');
        try {
            const response = await fetch(actionURL, { method:'POST', body:payload, credentials:'same-origin' });
            if (!response.ok) throw new Error('Perubahan belum tersimpan. Periksa koneksi dan coba lagi.');
            if (response.redirected) {
                if (new URL(response.url).pathname.startsWith('/auth/login')) { location.href = response.url; return; }
                const page = new DOMParser().parseFromString(await response.text(), 'text/html');
                const message = [...page.querySelectorAll('.workspace-message:not(#interaction-status)')].at(-1)?.textContent.trim().replace(/×$/, '').trim();
                sessionStorage.setItem('pcc-panel-saved', message || 'Perubahan berhasil disimpan.');
                if (navigateAfterSave || new URL(actionURL).pathname === '/projects/import/') location.href = response.url;
                else location.reload(); return;
            }
            showForm(await response.text());
        } catch (error) {
            let message = content.querySelector('[data-panel-error]');
            if (!message) { message = document.createElement('p'); message.dataset.panelError=''; message.className='workspace-message is-error mb-4'; message.setAttribute('role','alert'); content.prepend(message); }
            message.textContent = error.message;
            announce(error.message);
        } finally { busy = false; submit.disabled = false; drawer.querySelector('[data-panel-close]').disabled = false; submit.textContent = label; drawer.removeAttribute('aria-busy'); }
    });
    const confirmedForms = new WeakSet();
    document.addEventListener('submit', event => {
        const form = event.target.closest('form[data-confirm]');
        if (!form) return;
        if (confirmedForms.has(form)) { confirmedForms.delete(form); return; }
        event.preventDefault();
        if (!drawer || busy) return;
        opener = event.submitter;
        const submitter = event.submitter;
        const heading = document.createElement('h1');
        heading.id = 'drawer-title'; heading.className = 'text-2xl';
        heading.textContent = 'Konfirmasi perubahan';
        const message = document.createElement('p');
        message.className = 'mt-4 text-sm'; message.textContent = form.dataset.confirm;
        const actions = document.createElement('div'); actions.className = 'form-actions mt-6';
        const cancel = document.createElement('button'); cancel.type = 'button';
        cancel.className = 'pcc-button pcc-button-secondary'; cancel.textContent = 'Batal';
        cancel.addEventListener('click', () => drawer.close());
        const confirm = document.createElement('button'); confirm.type = 'button';
        confirm.className = 'pcc-button';
        confirm.textContent = submitter?.textContent.trim() || 'Lanjutkan';
        confirm.addEventListener('click', () => {
            confirmedForms.add(form); drawer.close(); form.requestSubmit(submitter || undefined);
        });
        actions.append(cancel, confirm); content.replaceChildren(heading, message, actions);
        drawer.setAttribute('aria-labelledby', heading.id); drawer.showModal(); drawer.scrollTop = 0;
        cancel.focus();
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') document.querySelectorAll('.project-add-menu[open]').forEach(menu => { menu.open = false; menu.querySelector('summary').focus(); });
    });
    document.addEventListener('click', event => {
        document.querySelectorAll('.project-add-menu[open]').forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
    });
    document.addEventListener('invalid', event => {
        let details = event.target.closest('details');
        while (details) { details.open = true; details = details.parentElement.closest('details'); }
    }, true);
    PCC.initForms();
    const saved = sessionStorage.getItem('pcc-panel-saved');
    if (saved) { sessionStorage.removeItem('pcc-panel-saved'); PCC.notify(saved); }
})();

// Expand existing visualization panels without cloning charts or rebuilding timelines.
PCC.initVisualizations = function(root = document) {
    const panels = [...root.querySelectorAll('[data-fullscreen-panel]')];
    let fallbackPanel, activePanel, opener, previousOverflow;
    const inertSiblings = [];
    const sync = () => {
        const expanded = document.fullscreenElement || fallbackPanel;
        panels.forEach(panel => {
            const on = panel === expanded;
            panel.classList.toggle('visualization-fullscreen', on);
            const button = panel.querySelector('[data-fullscreen-toggle]');
            if (!button) return;
            button.setAttribute('aria-pressed', String(on));
            button.setAttribute('aria-label', `${on ? 'Keluar dari' : 'Buka'} fullscreen: ${panel.dataset.fullscreenPanel}`);
            button.querySelector('span').textContent = on ? 'Kembali' : (panel.dataset.expandLabel || 'Perbesar');
        });
        if (!expanded && activePanel) { activePanel = null; opener?.focus({ preventScroll: true }); }
    };
    const exitFallback = () => {
        fallbackPanel = null;
        inertSiblings.forEach(([element, inert]) => { element.inert = inert; });
        inertSiblings.length = 0;
        document.body.style.overflow = previousOverflow;
        sync();
    };
    const enterFallback = panel => {
        fallbackPanel = panel;
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        for (let ancestor = panel; ancestor.parentElement; ancestor = ancestor.parentElement) {
            [...ancestor.parentElement.children].filter(element => element !== ancestor && !element.matches('dialog,script,style,link')).forEach(element => {
                inertSiblings.push([element, element.inert]); element.inert = true;
            });
        }
        sync();
        panel.querySelector('[data-fullscreen-toggle]').focus({ preventScroll: true });
    };
    panels.forEach((panel, index) => {
        const heading = panel.querySelector('h2,h3');
        const toolbar = panel.querySelector('[data-visualization-actions]') || heading?.closest('.panel-heading,.border-b');
        if (!toolbar) return;
        panel.id ||= `visualization-${index}`;
        const button = document.createElement('button');
        button.type = 'button'; button.dataset.fullscreenToggle = '';
        button.className = 'pcc-button pcc-button-secondary visualization-toggle';
        button.setAttribute('aria-controls', panel.id); button.setAttribute('aria-pressed', 'false');
        button.setAttribute('aria-label', `Buka fullscreen: ${panel.dataset.fullscreenPanel}`);
        button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/></svg><span>Perbesar</span>';
        if (!toolbar.hasAttribute('data-visualization-actions')) toolbar.classList.add('visualization-header');
        if (panel.dataset.expandLabel) button.querySelector('span').textContent = panel.dataset.expandLabel;
        toolbar.append(button);
        button.addEventListener('click', async () => {
            if (fallbackPanel) { exitFallback(); return; }
            if (document.fullscreenElement === panel) { await document.exitFullscreen(); return; }
            opener = button; activePanel = panel;
            if (panel.requestFullscreen && document.fullscreenEnabled) {
                try { await panel.requestFullscreen(); return; } catch { /* Browser denied native fullscreen; use the same panel in the viewport. */ }
            }
            enterFallback(panel);
        });
    });
    document.addEventListener('fullscreenchange', sync);
    document.addEventListener('keydown', event => {
        if (!fallbackPanel || document.querySelector('dialog[open]')) return;
        if (event.key === 'Escape') { event.preventDefault(); exitFallback(); return; }
        if (event.key !== 'Tab') return;
        const focusable = [...fallbackPanel.querySelectorAll('a,button,input,select,textarea,[tabindex="0"]')]
            .filter(element => !element.disabled && element.getBoundingClientRect().width);
        const first = focusable[0], last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    });
};
PCC.initVisualizations();


// Navbar search suggestions: htmx fetches, this keeps the dropdown tidy.
PCC.initNavSearch = function(root = document) {
    const form = root.querySelector('.header-search');
    if (!form || form.dataset.searchReady) return;
    form.dataset.searchReady = 'true';
    const results = form.querySelector('#nav-search-results');
    const input = form.querySelector('#workspace-search');
    if (!results || !input) return;
    const clear = () => results.replaceChildren();
    input.addEventListener('keydown', event => {
        if (event.key === 'Escape') { clear(); input.blur(); return; }
        const items = [...results.querySelectorAll('.search-suggest-item')];
        if (!items.length || (event.key !== 'ArrowDown' && event.key !== 'ArrowUp')) return;
        event.preventDefault();
        const current = items.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? current + 1 : current - 1;
        (items[next] || (event.key === 'ArrowDown' ? items[0] : items.at(-1))).focus();
    });
    form.addEventListener('submit', clear);
    document.addEventListener('click', event => { if (!form.contains(event.target)) clear(); });
};
PCC.initNavSearch();
PCC.initMentions();
