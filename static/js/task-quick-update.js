(() => {
    const panels = document.querySelectorAll('[data-quick-update]');
    if (!panels.length) return;

    const labelFor = (select, value) => {
        const option = [...select.options].find(item => item.value === value);
        return option ? option.textContent.trim() : value;
    };

    panels.forEach(panel => {
        const status = panel.querySelector('[data-quick-status]');
        const progress = panel.querySelector('[data-quick-progress]');
        const save = panel.querySelector('[data-quick-save]');
        const errorBox = panel.querySelector('[data-quick-error]');
        const statusText = panel.querySelector('[data-quick-status-text]');
        const taskId = panel.dataset.taskId;
        const card = taskId
            ? document.querySelector(`.kanban-task[data-task-id="${CSS.escape(taskId)}"]`)
            : null;
        const row = panel.closest('[data-task-row]') || card || panel;
        const controls = [status, progress, save].filter(Boolean);
        const locked = controls.filter(control => control.dataset.locked === 'true');
        let busy = false;

        const setBusy = value => {
            busy = value;
            controls.forEach(control => {
                control.disabled = value || locked.includes(control);
            });
        };

        const announce = (message, error = '') => {
            if (statusText) statusText.textContent = message;
            if (!errorBox) return;
            errorBox.textContent = error;
            errorBox.hidden = !error;
        };

        const showProgress = value => {
            if (!Number.isFinite(value)) return;
            const rounded = Math.round(value);
            row.querySelectorAll('[data-task-progress-label]').forEach(node => {
                node.textContent = `${rounded}%`;
            });
            row.querySelectorAll('progress').forEach(bar => {
                bar.value = rounded;
            });
        };

        const syncProgress = async () => {
            if (busy || !progress || progress.disabled) return;
            const value = progress.value.trim();
            if (value === '') {
                announce('', 'Progress harus antara 0 dan 100%.');
                progress.focus();
                return;
            }
            setBusy(true);
            announce('Menyimpan progress...');
            try {
                const result = await PCC.update(progress.dataset.url, { progress: value });
                progress.value = Math.round(result.progress);
                showProgress(result.progress);
                announce('Progress tersimpan.');
            } catch (error) {
                announce('', error.message);
            } finally {
                setBusy(false);
            }
        };

        save?.addEventListener('click', syncProgress);
        progress?.addEventListener('keydown', event => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            syncProgress();
        });

        status?.addEventListener('change', async () => {
            if (busy) return;
            const previous = status.dataset.current;
            setBusy(true);
            announce('Menyimpan status...');
            try {
                const result = await PCC.update(status.dataset.url, { status: status.value });
                status.dataset.current = result.status;
                row.querySelectorAll('[data-task-status-label]').forEach(node => {
                    node.textContent = labelFor(status, result.status);
                });
                announce('Status tersimpan.');
            } catch (error) {
                status.value = previous;
                announce('', error.message);
            } finally {
                setBusy(false);
            }
        });
    });
})();
