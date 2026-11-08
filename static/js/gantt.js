/* Scope Gantt: dependency-free interactive schedule (roadmap G1-G9).
 *
 * One component for every schedule view. Markup: templates/projects/partials/_gantt.html.
 * Data: a JSON payload from apps/work/gantt.py (rows in tree order, links, columns).
 *
 * Layout of this file:
 *   1. utilities (dates, DOM, storage, api)
 *   2. Gantt store: data indexing, tree visibility, time range, undo
 *   3. render: toolbar, tree pane, time scale, chart (rows, bars, links, chips)
 *   4. interaction: pointer (move, resize, create, link, pan), keyboard, menus, dialogs
 *
 * Every write goes through a JSON endpoint; the UI reverts when the server refuses.
 */
(() => {
'use strict';

/* ------------------------------------------------------------ 1. utilities */
const DAY_MS = 864e5, ROW_H = 40, HEAD_H = 52, OVERSCAN = 8;
const PRESETS = { day: 36, week: 14, month: 4.5, quarter: 1.6 };
const SCALE_LABEL = { day: 'Hari', week: 'Minggu', month: 'Bulan', quarter: 'Kuartal' };
const STEP = { day: 7, week: 28, month: 91, quarter: 365 };
const MIN_PX = 0.8, MAX_PX = 80;
const MONTHS = 'Jan Feb Mar Apr Mei Jun Jul Agu Sep Okt Nov Des'.split(' ');
const MONTHS_LONG = 'Januari Februari Maret April Mei Juni Juli Agustus September Oktober November Desember'.split(' ');
const WEEKDAY = 'M S S R K J S'.split(' ');
const TONE = {
    backlog: 'neutral', todo: 'todo', in_progress: 'active', review: 'info', blocked: 'danger', done: 'ok',
    upcoming: 'todo', completed: 'ok', delayed: 'danger', draft: 'neutral', planning: 'todo',
    on_hold: 'warn', cancelled: 'neutral', not_started: 'neutral',
};

const D = {
    from(iso) { return iso ? Math.round(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / DAY_MS) : null; },
    iso(n) { return new Date(n * DAY_MS).toISOString().slice(0, 10); },
    parts(n) { const d = new Date(n * DAY_MS); return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate(), w: d.getUTCDay() }; },
    short(n) { const p = D.parts(n); return `${p.d} ${MONTHS[p.m]}`; },
    long(n) { const p = D.parts(n); return `${p.d} ${MONTHS[p.m]} ${p.y}`; },
    month(y, m) { return Math.round(Date.UTC(y, m, 1) / DAY_MS); },
    monday(n) { return n - ((D.parts(n).w + 6) % 7); },
};
const span = (a, b) => b - a + 1;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const scaleFor = px => px >= 24 ? 'day' : px >= 8 ? 'week' : px >= 2.5 ? 'month' : 'quarter';
const plural = (n, word) => `${n} ${word}`;
const deviation = d => (d > 0 ? '+' : '') + d + ' hari';

function h(tag, attrs = {}, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === 'class') node.className = v;
        else if (k === 'text') node.textContent = v;
        else if (k === 'style') Object.assign(node.style, v);
        else if (k === 'html') node.innerHTML = v; // only used with static icon markup
        else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
        else node.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) node.append(kid);
    return node;
}
const svgNS = 'http://www.w3.org/2000/svg';
const ICON = {
    today: '<rect x="3" y="4" width="18" height="17" rx="2"/><path d="M16 2v4M8 2v4M3 10h18M12 14v3"/>',
    prev: '<path d="m15 18-6-6 6-6"/>',
    next: '<path d="m9 18 6-6-6-6"/>',
    zoomIn: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11h6M11 8v6"/>',
    zoomOut: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4M8 11h6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    paste: '<rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2M8 12h8M8 16h5"/>',
    chain: '<path d="M4 6h7v4H4zM13 14h7v4h-7zM11 8h3v8h-1"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    close: '<path d="M18 6 6 18M6 6l12 12"/>',
    more: '<path d="M5 12h.01M12 12h.01M19 12h.01"/>',
    chevron: '<path d="m9 6 6 6-6 6"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
};
const icon = name => h('span', { class: 'gantt-icon', 'aria-hidden': 'true', html: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">${ICON[name]}</svg>` });

const store = {
    get(area, key) { try { return JSON.parse(window[area].getItem(key) || 'null'); } catch { return null; } },
    set(area, key, value) { try { window[area].setItem(key, JSON.stringify(value)); } catch { /* View works without storage. */ } },
};

const csrf = () => document.querySelector('meta[name=csrf-token]')?.content || '';
async function api(url, body, { form = false, method = 'POST' } = {}) {
    const headers = { 'X-CSRFToken': csrf(), Accept: 'application/json' };
    let payload;
    if (method !== 'GET') {
        headers['Content-Type'] = form ? 'application/x-www-form-urlencoded' : 'application/json';
        payload = form ? new URLSearchParams(body) : JSON.stringify(body);
    }
    try {
        const res = await fetch(url, { method, credentials: 'same-origin', headers, body: payload });
        let data;
        try { data = await res.json(); } catch { data = { ok: false, error: 'Sesi berakhir atau respons tidak valid. Muat ulang halaman lalu coba lagi.' }; }
        return { status: res.status, ...data };
    } catch {
        return { status: 0, ok: false, error: 'Koneksi terputus. Perubahan belum tersimpan.' };
    }
}

/* --------------------------------------------------------------- 2. store */
class Gantt {
    constructor(root) {
        this.root = root;
        this.data = JSON.parse(document.getElementById(root.dataset.ganttSource).textContent);
        this.forcedReadonly = root.hasAttribute('data-gantt-readonly');
        this.small = matchMedia('(max-width: 767px), (pointer: coarse)');
        this.key = `scope-gantt:${location.pathname}:${root.dataset.ganttSource}`;
        const saved = store.get('sessionStorage', this.key) || {};
        this.px = clamp(saved.px || PRESETS[root.dataset.ganttScale || 'week'], MIN_PX, MAX_PX);
        this.collapsed = new Set(saved.collapsed || this.data.collapsed || []);
        this.selection = new Set();
        this.undoStack = [];
        this.cursor = null;          // row id that owns the roving focus
        this.editing = null;         // inline editor in the tree
        this.draft = null;           // drag-created bar waiting for a title
        this.addRow = null;          // tree "add task" row with an open input
        this.subFor = null;          // task id that shows an "add detail" row
        this.pending = null;         // keyboard nudge waiting to be saved
        this.savedDay = saved.day;
        this.treeW = store.get('localStorage', 'scope-gantt-tree');
        this.build();
        this.index();
        this.layout();
        this.restoreScroll();
        this.bind();
    }

    get canEdit() { return !this.forcedReadonly && !!this.data.editable && !this.small.matches; }
    get urls() { return this.data.urls || {}; }
    url(name, id) { return this.urls[name].replace('/0/', `/${id}/`); }

    /* Index rows, compute what the tree shows, and the time range. */
    index() {
        const rows = this.data.rows || [];
        this.byId = new Map(rows.map(r => [r.id, r]));
        this.byTask = new Map(rows.filter(r => r.task).map(r => [r.task, r]));
        this.kids = new Map();
        for (const r of rows) if (r.parent) { if (!this.kids.has(r.parent)) this.kids.set(r.parent, []); this.kids.get(r.parent).push(r); }
        const hidden = new Set(), visible = [];
        let group = null;
        const closeGroup = () => {
            if (group && this.canEdit && group.kind === 'phase' && this.data.mode === 'project' && !this.collapsed.has(group.id)) {
                visible.push({ id: `add-${group.id}`, kind: 'add', phase: group.phase, parent: group.id, depth: 1 });
            }
        };
        for (const r of rows) {
            if (r.parent && (hidden.has(r.parent) || this.collapsed.has(r.parent))) { hidden.add(r.id); continue; }
            if (!r.parent) { closeGroup(); group = r; }
            visible.push(r);
        }
        closeGroup();
        if (this.subFor) {
            // "Add detail" row sits after the activity's last visible detail.
            const parent = this.byTask.get(this.subFor);
            const at = parent ? visible.indexOf(parent) : -1;
            if (at >= 0) {
                let end = at + 1;
                while (end < visible.length && visible[end].parent === parent.id) end++;
                visible.splice(end, 0, this.subRow(parent));
            }
        }
        this.visible = visible;
        this.rowIndex = new Map(visible.map((r, i) => [r.id, i]));
        let lo = Infinity, hi = -Infinity;
        const take = iso => { const n = D.from(iso); if (n != null) { lo = Math.min(lo, n); hi = Math.max(hi, n); } };
        for (const r of rows) { take(r.start); take(r.end); }
        this.workLo = lo; this.workHi = hi;
        for (const r of rows) { take(r.baseStart); take(r.baseEnd); }
        take(this.data.start); take(this.data.end); take(this.data.today);
        this.today = D.from(this.data.today);
        if (lo === Infinity) { lo = hi = this.today; }
        this.rangeLo = lo; this.rangeHi = hi;
    }

    subRow(parent) { return { id: `add-sub-${parent.task}`, kind: 'add', phase: parent.phase, parentTask: parent.task, parent: parent.id, depth: 2 }; }

    /* Time range: data range plus padding, wide enough to fill the viewport. */
    computeRange() {
        const pad = Math.ceil(240 / this.px) + 7;
        this.rs = D.monday(this.rangeLo - pad);
        let re = this.rangeHi + pad + 21;
        const need = Math.ceil((this.chart.clientWidth || 900) / this.px) + 2;
        if (span(this.rs, re) < need) re = this.rs + need;
        this.re = re;
        this.width = span(this.rs, this.re) * this.px;
    }

    x(day) { return (day - this.rs) * this.px; }
    dayAt(clientX) { return this.rs + Math.floor((clientX - this.canvas.getBoundingClientRect().left) / this.px); }
    centerDay() { return this.rs + (this.chart.scrollLeft + this.chart.clientWidth / 2) / this.px; }

    remember() {
        store.set('sessionStorage', this.key, {
            px: this.px, collapsed: [...this.collapsed],
            day: this.rs + this.chart.scrollLeft / this.px, top: this.chart.scrollTop,
        });
    }

    pushUndo(label, run) {
        this.undoStack.push({ label, run });
        if (this.undoStack.length > 20) this.undoStack.shift();
        this.toast(label, { action: 'Urungkan', onAction: () => this.undo() });
    }

    async undo() {
        const entry = this.undoStack.pop();
        if (!entry) { this.toast('Tidak ada perubahan untuk diurungkan.'); return; }
        const res = await entry.run();
        if (res && res.ok === false) { this.toast(res.error, { error: true }); return; }
        await this.reload();
        this.toast(`Diurungkan: ${entry.label.charAt(0).toLowerCase()}${entry.label.slice(1)}`);
    }

    async reload() {
        if (!this.urls.data) return;
        const res = await api(this.urls.data, null, { method: 'GET' });
        if (!res.ok) { this.toast(res.error || 'Gagal memuat ulang jadwal.', { error: true }); return; }
        const anchor = this.rs + this.chart.scrollLeft / this.px, top = this.chart.scrollTop;
        this.data = res.gantt;
        for (const id of [...this.selection]) if (!this.byTaskAfter(id)) this.selection.delete(id);
        this.index();
        this.layout();
        this.chart.scrollLeft = (anchor - this.rs) * this.px;
        this.chart.scrollTop = top;
        this.render(true);
    }
    byTaskAfter(id) { return (this.data.rows || []).some(r => r.task === id); }

    /* Client-side mirror of apps/work/gantt.Plan rules, for instant feedback. */
    problem(row, s, e, mode) {
        if (row.lock) return row.lock;
        if (e < s) return 'Tanggal selesai tidak boleh sebelum tanggal mulai.';
        if (row.subtask) {
            const parent = this.byId.get(row.parent);
            const ps = D.from(parent?.start), pe = D.from(parent?.end);
            if (ps != null && pe != null && (s < ps || e > pe)) return `Detail harus berada di dalam rentang activity "${parent.title}" (${D.short(ps)} – ${D.short(pe)}).`;
        }
        if (row.hasChildren && mode !== 'move') {
            for (const child of this.kids.get(row.id) || []) {
                const cs = D.from(child.start), ce = D.from(child.end);
                if (cs != null && (cs < s || ce > e)) return `Rentang activity harus mencakup detail "${child.title}" (${D.short(cs)} – ${D.short(ce)}).`;
            }
        }
        for (const link of this.data.links) {
            if (link.to !== row.task) continue;
            const before = this.byTask.get(link.from), be = D.from(before?.end);
            if (be != null && s <= be) return `"${row.title}" baru bisa dimulai setelah "${before.title}" selesai (${D.short(be)}).`;
        }
        return null;
    }

    successorsHit(row, e) {
        return this.data.links.filter(l => l.from === row.task).map(l => this.byTask.get(l.to))
            .filter(r => r && r.start && D.from(r.start) <= e);
    }

    /* ---------------------------------------------------------- 3. render */
    build() {
        const root = this.root;
        root.classList.add('gantt-ready');
        this.toolbar = root.querySelector('[data-gantt-toolbar]');
        this.body = root.querySelector('[data-gantt-body]');
        this.tree = root.querySelector('[data-gantt-tree]');
        this.splitter = root.querySelector('[data-gantt-splitter]');
        this.chart = root.querySelector('[data-gantt-chart]');
        this.live = root.querySelector('[data-gantt-live]');
        this.toastEl = root.querySelector('[data-gantt-toast]');
        root.querySelector('[data-gantt-fallback]')?.remove();
        if (this.treeW) this.body.style.setProperty('--gantt-tree-w', `${this.treeW}px`);
        this.buildToolbar();
        // Tree pane
        this.treeHead = h('div', { class: 'gantt-tree-head', role: 'row' });
        this.treeRows = h('div', { class: 'gantt-tree-rows', role: 'rowgroup' });
        this.tree.replaceChildren(h('div', { class: 'gantt-tree-inner' }, this.treeHead, this.treeRows));
        // Chart pane
        this.scale = h('div', { class: 'gantt-scale', 'aria-hidden': 'true' });
        this.cols = h('div', { class: 'gantt-cols', 'aria-hidden': 'true' });
        this.rowLayer = h('div', { class: 'gantt-row-layer' });
        this.links = document.createElementNS(svgNS, 'svg');
        this.links.setAttribute('class', 'gantt-links');
        this.links.setAttribute('aria-hidden', 'true');
        this.links.innerHTML = '<defs><marker id="gantt-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 8 4 0 8z" fill="context-stroke"/></marker></defs><g></g>';
        this.barLayer = h('div', { class: 'gantt-bar-layer' });
        this.todayLine = h('div', { class: 'gantt-today', 'aria-hidden': 'true' });
        this.chipLayer = h('div', { class: 'gantt-chip-layer' });
        this.tip = h('div', { class: 'gantt-tip', role: 'status', hidden: true });
        this.canvas = h('div', { class: 'gantt-canvas' }, this.cols, this.rowLayer, this.links, this.barLayer, this.todayLine, this.chipLayer, this.tip);
        this.chart.replaceChildren(this.scale, this.canvas);
        this.hint = h('p', { class: 'sr-only', id: `${this.root.id || this.root.dataset.ganttSource}-hint` },
            'Panah atas dan bawah pindah baris. Panah kiri dan kanan menggeser tanggal satu hari, Shift dengan panah mengubah durasi. Enter membuka detail, tombol menu konteks membuka aksi.');
        root.append(this.hint);
    }

    buildToolbar() {
        const btn = (label, iconName, onclick, extra = {}) => h('button', { type: 'button', class: 'gantt-btn', onclick, ...extra }, iconName && icon(iconName), h('span', { class: extra.iconOnly ? 'sr-only' : null, text: label }));
        this.periodEl = h('h3', { class: 'gantt-period', 'aria-live': 'polite' });
        const nav = h('div', { class: 'gantt-group' },
            btn('Hari ini', 'today', () => this.scrollToDay(this.today, true)),
            h('div', { class: 'gantt-seg' },
                btn('Sebelumnya', 'prev', () => this.step(-1), { iconOnly: true, title: 'Periode sebelumnya' }),
                btn('Berikutnya', 'next', () => this.step(1), { iconOnly: true, title: 'Periode berikutnya' })),
            this.periodEl);
        this.scaleButtons = Object.keys(PRESETS).map(name => h('button', {
            type: 'button', class: 'gantt-seg-btn', 'data-scale': name, 'aria-pressed': 'false',
            onclick: () => this.zoomTo(PRESETS[name]), text: SCALE_LABEL[name],
        }));
        const view = h('div', { class: 'gantt-group' },
            h('div', { class: 'gantt-seg', role: 'group', 'aria-label': 'Skala waktu' }, this.scaleButtons),
            h('div', { class: 'gantt-seg', role: 'group', 'aria-label': 'Zoom' },
                btn('Perkecil', 'zoomOut', () => this.zoomTo(this.px / 1.35), { iconOnly: true, title: 'Perkecil (Ctrl + scroll)' }),
                btn('Perbesar', 'zoomIn', () => this.zoomTo(this.px * 1.35), { iconOnly: true, title: 'Perbesar (Ctrl + scroll)' })));
        this.editTools = h('div', { class: 'gantt-group gantt-edit-tools' },
            btn('Task', 'plus', () => this.openFirstAddRow(), { class: 'gantt-btn gantt-btn-primary', title: 'Tambah task di phase pertama' }),
            btn('Tempel daftar', 'paste', () => this.pasteDialog()));
        this.selTools = h('div', { class: 'gantt-group gantt-selection', hidden: true },
            this.selCount = h('span', { class: 'gantt-sel-count' }),
            btn('Susun berurutan', 'chain', () => this.sequenceDialog()),
            btn('Duplikat', 'copy', () => this.duplicate([...this.selection])),
            btn('Batal pilih', 'close', () => { this.selection.clear(); this.render(true); }, { iconOnly: true, title: 'Batal pilih' }));
        this.mobileNote = h('p', { class: 'gantt-note', hidden: true, text: 'Mode baca di layar kecil. Ubah jadwal dari layar yang lebih lebar.' });
        this.toolbar.replaceChildren(nav, view, this.editTools, this.selTools, this.mobileNote);
        this.toolbar.setAttribute('role', 'toolbar');
        this.toolbar.setAttribute('aria-label', 'Navigasi jadwal');
    }

    layout() {
        this.computeRange();
        const n = this.visible.length;
        this.canvas.style.width = this.scale.style.width = `${this.width}px`;
        this.canvas.style.height = `${Math.max(n, 1) * ROW_H}px`;
        this.treeRows.style.height = `${Math.max(n, 1) * ROW_H + 16}px`;
        this.links.setAttribute('width', this.width);
        this.links.setAttribute('height', Math.max(n, 1) * ROW_H);
        this.body.style.setProperty('--gantt-content-h', `${HEAD_H + Math.max(n, 3) * ROW_H + 18}px`);
        this.body.style.setProperty('--gantt-px', `${this.px}px`);
        this.root.classList.toggle('is-editable', this.canEdit);
        this.root.classList.toggle('is-readonly', !this.canEdit);
        this.editTools.hidden = !this.canEdit || this.data.mode !== 'project';
        this.mobileNote.hidden = !(this.data.editable && !this.forcedReadonly && this.small.matches);
        this.buildTreeHead();
        this.lastWindow = null;
    }

    columns() { return this.data.columns || []; }
    gridTemplate() {
        const widths = { date: '72px', person: '116px', percent: '68px' };
        return [this.canEdit ? '32px' : null, 'minmax(200px, 1fr)', ...this.columns().map(c => widths[c.type] || '90px')].filter(Boolean).join(' ');
    }

    buildTreeHead() {
        const tmpl = this.gridTemplate();
        this.tree.style.setProperty('--gantt-cols', tmpl);
        const min = (this.canEdit ? 32 : 0) + 200 + this.columns().reduce((sum, c) => sum + ({ date: 72, person: 116, percent: 68 }[c.type] || 90), 0);
        this.tree.style.setProperty('--gantt-tree-min', `${min}px`);
        if (!this.treeW) this.body.style.setProperty('--gantt-tree-w', `${Math.round(Math.min(min, Math.max(320, this.body.clientWidth * 0.48)))}px`);
        const anyOpen = (this.data.rows || []).some(r => this.kids.has(r.id) && !this.collapsed.has(r.id));
        this.treeHead.replaceChildren(...[
            this.canEdit ? h('div', { class: 'gantt-hcell', role: 'columnheader' }, h('span', { class: 'sr-only', text: 'Pilih' })) : null,
            h('div', { class: 'gantt-hcell gantt-hcell-name', role: 'columnheader' },
                h('span', { text: this.data.mode === 'portfolio' ? 'Project' : 'Task' }),
                h('button', { type: 'button', class: 'gantt-link-btn', onclick: () => this.toggleAll(), text: anyOpen ? 'Lipat semua' : 'Buka semua' })),
            ...this.columns().map(c => h('div', { class: `gantt-hcell gantt-hcell-${c.type}`, role: 'columnheader', text: c.label }))].filter(Boolean));
        this.tree.setAttribute('aria-rowcount', String(this.visible.length));
    }

    toggleAll() {
        const parents = (this.data.rows || []).filter(r => this.kids.has(r.id)).map(r => r.id);
        const anyOpen = parents.some(id => !this.collapsed.has(id));
        this.collapsed = new Set(anyOpen ? parents : []);
        this.relayout();
    }

    relayout() { const top = this.chart.scrollTop; const anchor = this.rs + this.chart.scrollLeft / this.px; this.index(); this.layout(); this.chart.scrollLeft = (anchor - this.rs) * this.px; this.chart.scrollTop = top; this.render(true); this.remember(); }

    render(force = false) {
        if (force) this.lastWindow = null;
        cancelAnimationFrame(this.frame);
        this.frame = requestAnimationFrame(() => this.paint());
    }

    paint() {
        const top = this.chart.scrollTop, height = this.chart.clientHeight - HEAD_H;
        const n = this.visible.length;
        const i0 = Math.max(0, Math.floor(top / ROW_H) - OVERSCAN);
        const i1 = Math.min(n, Math.ceil((top + height) / ROW_H) + OVERSCAN);
        const x0 = Math.max(0, this.chart.scrollLeft - 160), x1 = this.chart.scrollLeft + this.chart.clientWidth + 160;
        const win = `${i0}:${i1}:${Math.floor(x0 / 200)}:${this.px}`;
        if (win !== this.lastWindow) {
            this.lastWindow = win;
            if (!this.editing) this.paintTree(i0, i1);
            this.paintScale(x0, x1);
            this.paintRows(i0, i1);
            this.paintLinks();
        }
        this.paintChips(i0, i1);
        this.paintPeriod();
        this.paintToolbar();
        const t = this.x(this.today) + this.px / 2;
        this.todayLine.style.left = `${t}px`;
        this.todayLine.hidden = this.today < this.rs || this.today > this.re;
    }

    paintToolbar() {
        const scale = scaleFor(this.px);
        for (const b of this.scaleButtons) b.setAttribute('aria-pressed', String(b.dataset.scale === scale));
        const count = this.selection.size;
        this.selTools.hidden = !this.canEdit || count === 0;
        this.selCount.textContent = `${count} dipilih`;
        const seq = this.selTools.querySelector('button:nth-of-type(1)');
        if (seq) seq.disabled = count < 2;
    }

    paintPeriod() {
        const a = Math.floor(this.rs + this.chart.scrollLeft / this.px);
        const b = Math.floor(this.rs + (this.chart.scrollLeft + this.chart.clientWidth) / this.px) - 1;
        const pa = D.parts(a), pb = D.parts(b);
        let text;
        if (pa.y === pb.y && pa.m === pb.m) text = `${MONTHS_LONG[pa.m]} ${pa.y}`;
        else if (pa.y === pb.y) text = `${MONTHS[pa.m]} – ${MONTHS[pb.m]} ${pa.y}`;
        else text = `${MONTHS[pa.m]} ${pa.y} – ${MONTHS[pb.m]} ${pb.y}`;
        if (this.periodEl.textContent !== text) this.periodEl.textContent = text;
    }

    /* Tree pane ---------------------------------------------------------- */
    paintTree(i0, i1) {
        const frag = document.createDocumentFragment();
        for (let i = i0; i < i1; i++) frag.append(this.treeRow(this.visible[i], i));
        const focused = document.activeElement && this.treeRows.contains(document.activeElement) ? document.activeElement.dataset.col : null;
        this.treeRows.replaceChildren(frag);
        if (focused && this.cursor) this.treeCell(this.cursor, focused)?.focus({ preventScroll: true });
        if (this.addRow) this.mountAddInput();
    }

    treeCell(id, col) { return this.treeRows.querySelector(`[data-key="${CSS.escape(id)}"] [data-col="${col}"]`); }

    treeRow(r, i) {
        const isTask = r.kind === 'task';
        const hasKids = this.kids.has(r.id);
        const row = h('div', {
            class: `gantt-row k-${r.kind}${this.selection.has(r.task) ? ' is-selected' : ''}${this.cursor === r.id ? ' is-cursor' : ''}`,
            role: 'row', 'aria-rowindex': i + 1, 'aria-level': (r.depth || 0) + 1,
            'aria-expanded': hasKids ? String(!this.collapsed.has(r.id)) : null,
            'aria-selected': isTask && this.canEdit ? String(this.selection.has(r.task)) : null,
            'data-key': r.id, style: { top: `${i * ROW_H}px` },
        });
        if (r.kind === 'add') return this.addTreeRow(r, row);
        if (this.canEdit) {
            row.append(h('div', { class: 'gantt-cell gantt-cell-check', role: 'gridcell' }, isTask ? h('input', {
                type: 'checkbox', checked: this.selection.has(r.task), 'aria-label': `Pilih ${r.title}`, tabindex: '-1',
                onclick: e => this.toggleSelect(r, e.shiftKey),
            }) : null));
        }
        const name = h('div', { class: 'gantt-cell gantt-cell-name', role: 'gridcell', 'data-col': 'title', tabindex: this.cursor === r.id || (!this.cursor && i === 0) ? '0' : '-1', style: { '--depth': r.depth || 0 } });
        if (hasKids) {
            name.append(h('button', {
                type: 'button', class: 'gantt-toggle', tabindex: '-1', 'aria-label': `${this.collapsed.has(r.id) ? 'Buka' : 'Lipat'} ${r.title}`,
                onclick: () => this.toggle(r.id),
            }, icon('chevron')));
        } else name.append(h('span', { class: 'gantt-toggle-space' }));
        if (r.kind !== 'group' && r.kind !== 'phase') name.append(h('span', { class: `gantt-dot-status tone-${TONE[r.status] || 'neutral'}`, title: r.statusLabel || '' }));
        const label = r.url && !this.canEdit
            ? h('a', { class: 'gantt-name', href: r.url, tabindex: '-1', text: r.title })
            : h('span', { class: 'gantt-name', text: r.title });
        name.append(label);
        if (r.code) name.append(h('span', { class: 'gantt-code', text: r.code }));
        if ((r.kind === 'phase' || r.kind === 'group' || r.kind === 'project') && r.count != null) name.append(h('span', { class: 'gantt-count', text: String(r.count) }));
        if (r.lock && this.canEdit) name.append(h('span', { class: 'gantt-lock', title: r.lock, role: 'img', 'aria-label': r.lock }, icon('lock')));
        if (isTask && (this.canEdit || r.url)) {
            name.append(h('button', { type: 'button', class: 'gantt-more', tabindex: '-1', 'aria-label': `Aksi untuk ${r.title}`, onclick: e => { e.stopPropagation(); this.openMenu(r, e.currentTarget); } }, icon('more')));
        }
        row.append(name);
        for (const c of this.columns()) row.append(this.valueCell(r, c));
        return row;
    }

    valueCell(r, c) {
        const cell = h('div', { class: `gantt-cell gantt-cell-${c.type}`, role: 'gridcell', 'data-col': c.key, tabindex: '-1' });
        const v = r[c.key];
        if (c.type === 'date') {
            if (r.kind === 'milestone' && c.key !== 'start') { cell.textContent = ''; return cell; }
            const n = D.from(v);
            cell.textContent = n != null ? D.short(n) : (r.kind === 'task' && this.canEdit && r.editable ? 'Atur' : '—');
            if (n != null) cell.title = D.long(n);
            if (n == null) cell.classList.add('is-empty');
        } else if (c.type === 'person') {
            cell.textContent = r.kind === 'task' ? (r.assigneeName || '—') : '';
            if (r.kind === 'task' && !r.assigneeName) cell.classList.add('is-empty');
        } else if (c.type === 'percent') {
            if (v == null || r.kind === 'milestone' || r.kind === 'group') { cell.textContent = r.kind === 'milestone' ? (r.statusLabel || '') : '—'; return cell; }
            cell.append(h('span', { class: 'gantt-pct', text: `${Math.round(v)}%` }), h('span', { class: 'gantt-meter', 'aria-hidden': 'true' }, h('i', { style: { width: `${clamp(v, 0, 100)}%` } })));
        }
        if (this.canEdit && r.kind === 'task' && ['title', 'start', 'end', 'assignee'].includes(c.key)) cell.classList.add('is-editable');
        return cell;
    }

    addTreeRow(r, row) {
        const label = r.parentTask ? 'Tambah detail activity' : 'Tambah task';
        if (this.canEdit) row.append(h('div', { class: 'gantt-cell gantt-cell-check', role: 'gridcell' }));
        const cell = h('div', { class: 'gantt-cell gantt-cell-add', role: 'gridcell', 'data-col': 'title', style: { '--depth': r.depth } },
            h('button', { type: 'button', class: 'gantt-add-btn', tabindex: '-1', onclick: () => this.openAddRow(r) }, icon('plus'), h('span', { text: label })),
            h('span', { class: 'gantt-add-hint', text: 'Enter untuk simpan, lanjut ketik berikutnya · tempel banyak baris sekaligus' }));
        row.append(cell);
        return row;
    }

    /* Time scale + grid -------------------------------------------------- */
    paintScale(x0, x1) {
        const scale = scaleFor(this.px), top = [], bottom = [], cols = [];
        const a = this.rs + Math.floor(x0 / this.px), b = Math.min(this.re, this.rs + Math.ceil(x1 / this.px));
        const cell = (list, from, to, text, cls = '') => {
            const l = this.x(from), w = span(from, to) * this.px;
            list.push(h('div', { class: `gantt-tick ${cls}`, style: { left: `${l}px`, width: `${w}px` } }, h('span', { text })));
        };
        const months = [];
        for (let p = D.parts(a), m = D.month(p.y, p.m); m <= b; ) {
            const q = D.parts(m), next = D.month(q.y, q.m + 1);
            months.push([m, next - 1, q]);
            m = next;
        }
        if (scale === 'day' || scale === 'week') {
            for (const [m, end, q] of months) cell(top, m, end, `${MONTHS_LONG[q.m]} ${q.y}`);
            if (scale === 'day') {
                for (let d = a; d <= b; d++) {
                    const p = D.parts(d), weekend = p.w === 0 || p.w === 6;
                    cell(bottom, d, d, `${WEEKDAY[p.w]} ${p.d}`, `${weekend ? 'is-weekend' : ''}${d === this.today ? ' is-today' : ''}`);
                    cols.push(h('div', { class: `gantt-col${weekend ? ' is-weekend' : ''}`, style: { left: `${this.x(d)}px`, width: `${this.px}px` } }));
                }
            } else {
                for (let d = D.monday(a); d <= b; d += 7) {
                    cell(bottom, d, d + 6, `${D.parts(d).d}–${D.parts(d + 6).d}`, d <= this.today && this.today <= d + 6 ? 'is-today' : '');
                    cols.push(h('div', { class: 'gantt-col', style: { left: `${this.x(d)}px`, width: `${7 * this.px}px` } }));
                    cols.push(h('div', { class: 'gantt-col is-weekend is-thin', style: { left: `${this.x(d + 5)}px`, width: `${2 * this.px}px` } }));
                }
            }
        } else if (scale === 'month') {
            const years = new Map();
            for (const [m, end, q] of months) {
                cell(bottom, m, end, MONTHS[q.m], m <= this.today && this.today <= end ? 'is-today' : '');
                cols.push(h('div', { class: 'gantt-col', style: { left: `${this.x(m)}px`, width: `${span(m, end) * this.px}px` } }));
                const y = years.get(q.y) || [m, end]; y[1] = end; years.set(q.y, y);
            }
            for (const [y, [m, end]] of years) cell(top, m, end, String(y));
        } else {
            const years = new Map(), quarters = new Map();
            for (const [m, end, q] of months) {
                const key = `${q.y}-${Math.floor(q.m / 3)}`;
                const k = quarters.get(key) || [m, end, `K${Math.floor(q.m / 3) + 1}`]; k[1] = end; quarters.set(key, k);
                const y = years.get(q.y) || [m, end]; y[1] = end; years.set(q.y, y);
            }
            for (const [, [m, end, label]] of quarters) {
                cell(bottom, m, end, label, m <= this.today && this.today <= end ? 'is-today' : '');
                cols.push(h('div', { class: 'gantt-col', style: { left: `${this.x(m)}px`, width: `${span(m, end) * this.px}px` } }));
            }
            for (const [y, [m, end]] of years) cell(top, m, end, String(y));
        }
        this.scale.replaceChildren(h('div', { class: 'gantt-scale-top' }, top), h('div', { class: 'gantt-scale-bottom' }, bottom));
        this.cols.replaceChildren(...cols);
    }

    /* Rows, bars, baselines, milestones ---------------------------------- */
    paintRows(i0, i1) {
        const bgs = [], bars = [];
        for (let i = i0; i < i1; i++) {
            const r = this.visible[i];
            const y = i * ROW_H;
            const creatable = this.canEdit && this.creatable(r);
            bgs.push(h('div', {
                class: `gantt-track k-${r.kind}${creatable ? ' can-create' : ''}${this.selection.has(r.task) ? ' is-selected' : ''}${this.cursor === r.id ? ' is-cursor' : ''}`,
                'data-key': r.id, style: { top: `${y}px` },
            }, creatable && !r.start ? h('span', { class: 'gantt-track-hint', style: { left: `${this.chart.scrollLeft + 12}px` }, text: r.kind === 'task' ? 'Tarik untuk menjadwalkan' : 'Tarik untuk membuat task' }) : null));
            const bar = this.bar(r, y);
            if (bar) bars.push(...bar);
        }
        if (this.draft && this.rowIndex.has(this.draft.rowKey)) bars.push(...this.draftBar());
        this.rowLayer.replaceChildren(...bgs);
        this.barLayer.replaceChildren(...bars);
    }

    creatable(r) {
        return r.kind === 'phase' || r.kind === 'add' || (r.kind === 'task' && r.editable && !r.start);
    }

    bar(r, y) {
        const s = D.from(r.start), e = D.from(r.end);
        const out = [];
        if (r.kind === 'milestone') {
            if (s == null) return out;
            out.push(h('div', {
                class: `gantt-milestone tone-${TONE[r.status] || 'neutral'}`, 'data-key': r.id, tabindex: '-1', role: 'img',
                'aria-label': `Milestone ${r.title}, ${D.long(s)}, ${r.statusLabel || ''}`,
                style: { left: `${this.x(s) + this.px / 2}px`, top: `${y + ROW_H / 2}px` },
            }), h('span', { class: 'gantt-ms-label', style: { left: `${this.x(s) + this.px / 2 + 12}px`, top: `${y}px` }, text: `${r.title} · ${D.short(s)}` }));
            return out;
        }
        const bs = D.from(r.baseStart), be = D.from(r.baseEnd);
        if (bs != null && be != null && r.kind === 'task') {
            out.push(h('div', { class: 'gantt-baseline', 'aria-hidden': 'true', title: `Baseline ${D.long(bs)} – ${D.long(be)}`, style: { left: `${this.x(bs)}px`, width: `${span(bs, be) * this.px}px`, top: `${y + 31}px` } }));
        }
        if (s == null || e == null) return out;
        const summary = r.kind !== 'task' || r.hasChildren;
        const tone = r.kind === 'phase' && !r.status ? 'summary' : (TONE[r.status] || 'neutral');
        const left = this.x(s), width = Math.max(span(s, e) * this.px, 6);
        const progress = r.progress == null ? null : clamp(r.progress, 0, 100);
        const dev = r.kind === 'task' && be != null ? e - be : 0;
        const meta = [progress != null ? `${Math.round(progress)}%` : null, dev ? deviation(dev) : null].filter(Boolean).join(' · ');
        const text = r.title;
        const inside = width > Math.min(220, text.length * 6.5 + 50);
        const draggable = this.canEdit && r.kind === 'task' && r.editable;
        const describe = [
            r.title, `${D.long(s)} sampai ${D.long(e)}`, plural(span(s, e), 'hari'),
            progress != null ? `progress ${Math.round(progress)}%` : null, r.planned != null ? `rencana ${Math.round(r.planned)}%` : null,
            r.statusLabel, bs != null ? `baseline ${D.long(bs)} sampai ${D.long(be)}${dev ? `, ${deviation(dev)}` : ''}` : null,
            r.overdue ? 'terlambat' : null, r.lock || null,
        ].filter(Boolean).join(', ');
        const node = h('div', {
            class: `gantt-bar tone-${tone}${summary ? ' is-summary' : ''}${r.kind === 'project' ? ' is-project' : ''}${draggable ? ' is-draggable' : ''}${r.overdue ? ' is-overdue' : ''}${this.selection.has(r.task) ? ' is-selected' : ''}${r.lock ? ' is-locked' : ''}`,
            'data-key': r.id, tabindex: this.cursor === r.id ? '0' : '-1', role: 'button', 'aria-label': describe,
            'aria-describedby': this.canEdit && r.kind === 'task' ? this.hint.id : null,
            style: { left: `${left}px`, width: `${width}px`, top: `${y + (summary ? 12 : 7)}px` },
        });
        if (progress != null) node.append(h('span', { class: 'gantt-bar-fill', style: { width: `${progress}%` } }));
        if (inside && !summary) node.append(h('span', { class: 'gantt-bar-label' }, h('span', { class: 'gantt-bar-title', text }), meta ? h('span', { class: 'gantt-bar-meta', text: meta }) : null));
        if (draggable) {
            node.append(h('span', { class: 'gantt-handle', 'data-side': 'l', 'aria-hidden': 'true' }), h('span', { class: 'gantt-handle', 'data-side': 'r', 'aria-hidden': 'true' }));
            node.append(h('span', { class: 'gantt-dot', 'data-side': 'l', title: 'Tarik ke task lain: jadikan prasyarat', 'aria-hidden': 'true' }), h('span', { class: 'gantt-dot', 'data-side': 'r', title: 'Tarik ke task lain: jadikan penerus', 'aria-hidden': 'true' }));
        }
        out.push(node);
        if (!inside || summary) {
            out.push(h('span', { class: `gantt-bar-outside${summary ? ' is-summary' : ''}`, style: { left: `${left + width + 8}px`, top: `${y}px` } },
                h('span', { class: 'gantt-bar-title', text: summary ? (meta || '') : text }), !summary && meta ? h('span', { class: 'gantt-bar-meta', text: meta }) : null));
        }
        return out;
    }

    draftBar() {
        const { start, end, rowKey } = this.draft;
        const y = this.rowIndex.get(rowKey) * ROW_H;
        const out = [h('div', { class: 'gantt-bar is-draft', style: { left: `${this.x(start)}px`, width: `${span(start, end) * this.px}px`, top: `${y + 7}px` } })];
        if (this.draft.input) {
            const input = this.draft.input;
            input.style.left = `${this.x(start)}px`;
            input.style.top = `${y + 4}px`;
            out.push(input);
        }
        return out;
    }

    paintLinks() {
        const g = this.links.querySelector('g');
        const paths = [];
        for (const link of this.data.links || []) {
            const a = this.byTask.get(link.from), b = this.byTask.get(link.to);
            if (!a || !b || !this.rowIndex.has(a.id) || !this.rowIndex.has(b.id)) continue;
            const ae = D.from(a.end), bs = D.from(b.start);
            if (ae == null || bs == null) continue;
            const x1 = this.x(ae + 1), y1 = this.rowIndex.get(a.id) * ROW_H + ROW_H / 2;
            const x2 = this.x(bs), y2 = this.rowIndex.get(b.id) * ROW_H + ROW_H / 2;
            const gap = 8;
            let d;
            if (x2 - gap >= x1 + gap) d = `M${x1} ${y1}H${x1 + gap}V${y2}H${x2 - 1}`;
            else {
                const mid = y1 + (y2 > y1 ? ROW_H / 2 : -ROW_H / 2);
                d = `M${x1} ${y1}H${x1 + gap}V${mid}H${x2 - gap}V${y2}H${x2 - 1}`;
            }
            const conflict = bs <= ae;
            const label = `Dependency ${a.title} ke ${b.title}${conflict ? ', bertabrakan' : ''}`;
            paths.push(`<path class="gantt-link${conflict ? ' is-conflict' : ''}" d="${d}" marker-end="url(#gantt-arrow)"/>`);
            if (this.canEdit) paths.push(`<path class="gantt-link-hit" d="${d}" data-from="${link.from}" data-to="${link.to}"><title>${label.replace(/[<&"]/g, c => ({ '<': '&lt;', '&': '&amp;', '"': '&quot;' })[c])}</title></path>`);
        }
        g.innerHTML = paths.join('');
    }

    paintChips(i0, i1) {
        const chips = [];
        const left = this.chart.scrollLeft, right = left + this.chart.clientWidth;
        for (let i = i0; i < i1; i++) {
            const r = this.visible[i];
            if (r.kind !== 'task' && r.kind !== 'milestone' && r.kind !== 'project') continue;
            const s = D.from(r.start), e = D.from(r.end);
            if (s == null || e == null) continue;
            const bl = this.x(s), br = this.x(e + 1);
            const side = br < left + 4 ? 'l' : bl > right - 4 ? 'r' : null;
            if (!side) continue;
            chips.push(h('button', {
                type: 'button', tabindex: '-1', class: `gantt-chip is-${side}`, 'data-key': r.id,
                style: { top: `${i * ROW_H + 10}px`, left: side === 'l' ? `${left + 6}px` : `${right - 6}px` },
                'aria-label': `${r.title} di luar layar, ${D.long(s)}. Geser ke bar.`,
                onclick: () => this.scrollToDay(s + (e - s) / 2, true),
            }, side === 'l' ? `‹ ${D.short(s)}` : `${D.short(s)} ›`));
        }
        this.chipLayer.replaceChildren(...chips);
    }

    /* Navigation ---------------------------------------------------------- */
    scrollToDay(day, smooth = false) {
        const left = this.x(day) - this.chart.clientWidth / 2;
        this.chart.scrollTo({ left: Math.max(0, left), behavior: smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'auto' });
    }

    step(dir) {
        const days = STEP[scaleFor(this.px)];
        this.chart.scrollBy({ left: dir * days * this.px, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }

    zoomTo(px, anchorClientX) {
        const next = clamp(px, MIN_PX, MAX_PX);
        if (Math.abs(next - this.px) < 0.001) return;
        const rect = this.chart.getBoundingClientRect();
        const offset = anchorClientX != null ? anchorClientX - rect.left : this.chart.clientWidth / 2;
        const day = this.rs + (this.chart.scrollLeft + offset) / this.px;
        this.px = next;
        this.layout();
        this.chart.scrollLeft = (day - this.rs) * this.px - offset;
        this.render(true);
        this.remember();
        this.say(`Skala ${SCALE_LABEL[scaleFor(this.px)].toLowerCase()}.`);
    }

    restoreScroll() {
        const saved = store.get('sessionStorage', this.key);
        requestAnimationFrame(() => {
            if (saved && saved.day != null) { this.chart.scrollLeft = (saved.day - this.rs) * this.px; this.chart.scrollTop = saved.top || 0; }
            else if (this.workLo === Infinity || (this.today >= this.workLo && this.today <= this.workHi + 14)) this.chart.scrollLeft = Math.max(0, this.x(this.today) - this.chart.clientWidth / 3);
            else this.chart.scrollLeft = Math.max(0, this.x(this.today < this.workLo ? this.workLo : Math.max(this.workLo, this.workHi - this.chart.clientWidth / this.px + 10)) - 24);
            this.tree.scrollTop = this.chart.scrollTop;
            this.render(true);
        });
    }

    toggle(id) {
        if (this.collapsed.has(id)) this.collapsed.delete(id); else this.collapsed.add(id);
        this.relayout();
        this.treeCell(id, 'title')?.focus({ preventScroll: true });
    }

    toggleSelect(r, range) {
        if (!r.task) return;
        if (range && this.anchorSel != null) {
            const tasks = this.visible.filter(v => v.kind === 'task');
            const a = tasks.findIndex(v => v.task === this.anchorSel), b = tasks.findIndex(v => v.task === r.task);
            if (a >= 0 && b >= 0) for (const v of tasks.slice(Math.min(a, b), Math.max(a, b) + 1)) this.selection.add(v.task);
        } else if (this.selection.has(r.task)) this.selection.delete(r.task);
        else this.selection.add(r.task);
        this.anchorSel = r.task;
        this.render(true);
        this.say(`${this.selection.size} task dipilih.`);
    }

    /* Feedback ------------------------------------------------------------ */
    say(message) { this.live.textContent = ''; requestAnimationFrame(() => { this.live.textContent = message; }); }

    toast(message, { error = false, action, onAction } = {}) {
        clearTimeout(this.toastTimer);
        const el = this.toastEl;
        el.hidden = false;
        el.classList.toggle('is-error', error);
        el.setAttribute('role', error ? 'alert' : 'status');
        el.replaceChildren(h('span', { text: message }),
            action ? h('button', { type: 'button', class: 'gantt-toast-action', onclick: () => { el.hidden = true; onAction(); }, text: action }) : null,
            h('button', { type: 'button', class: 'gantt-toast-close', 'aria-label': 'Tutup pesan', onclick: () => { el.hidden = true; } }, icon('close')));
        this.toastTimer = setTimeout(() => { el.hidden = true; }, action ? 10000 : error ? 8000 : 4000);
        if (!error) this.say(message);
    }

    /* ----------------------------------------------------- 4. interaction */
    bind() {
        let syncing = false;
        this.chart.addEventListener('scroll', () => {
            if (!syncing) { syncing = true; this.tree.scrollTop = this.chart.scrollTop; syncing = false; }
            this.render();
            clearTimeout(this.rememberTimer);
            this.rememberTimer = setTimeout(() => this.remember(), 200);
        }, { passive: true });
        this.tree.addEventListener('scroll', () => {
            if (syncing) return;
            if (Math.abs(this.chart.scrollTop - this.tree.scrollTop) > 1) { syncing = true; this.chart.scrollTop = this.tree.scrollTop; syncing = false; }
        }, { passive: true });
        this.tree.addEventListener('wheel', e => {
            if (e.deltaY && !e.shiftKey) { this.chart.scrollTop += e.deltaY; e.preventDefault(); }
        }, { passive: false });
        this.chart.addEventListener('wheel', e => {
            if (e.ctrlKey || e.metaKey) { e.preventDefault(); this.zoomTo(this.px * (e.deltaY < 0 ? 1.15 : 1 / 1.15), e.clientX); }
        }, { passive: false });
        this.canvas.addEventListener('pointerdown', e => this.onPointerDown(e));
        this.canvas.addEventListener('dblclick', e => {
            const key = e.target.closest('.gantt-bar')?.dataset.key;
            const r = key && this.byId.get(key);
            if (r && r.kind === 'task') this.open(r, true);
        });
        this.canvas.addEventListener('contextmenu', e => {
            const key = e.target.closest('.gantt-bar')?.dataset.key;
            const r = key && this.byId.get(key);
            if (r && r.kind === 'task') { e.preventDefault(); this.openMenu(r, null, e.clientX, e.clientY); }
        });
        this.canvas.addEventListener('click', e => {
            const hit = e.target.closest('.gantt-link-hit');
            if (hit) this.linkMenu(+hit.dataset.from, +hit.dataset.to, e.clientX, e.clientY);
        });
        this.chart.addEventListener('keydown', e => this.onChartKey(e));
        this.chart.addEventListener('focusin', e => {
            const key = e.target.closest?.('.gantt-bar')?.dataset.key;
            if (key) this.setCursor(key, false);
        });
        this.tree.addEventListener('keydown', e => this.onTreeKey(e));
        this.tree.addEventListener('dblclick', e => {
            const cell = e.target.closest('.gantt-cell.is-editable');
            if (cell) this.edit(cell.closest('[data-key]').dataset.key, cell.dataset.col);
        });
        this.tree.addEventListener('click', e => {
            const rowEl = e.target.closest('[data-key]');
            const cell = e.target.closest('.gantt-cell');
            if (!rowEl || !cell || e.target.closest('button, input, a, select')) return;
            const key = rowEl.dataset.key, r = this.byId.get(key);
            this.setCursor(key, false);
            cell.focus({ preventScroll: true });
            if (r && r.kind === 'task' && cell.classList.contains('is-editable') && cell.dataset.col !== 'title' && this.lastClick === `${key}:${cell.dataset.col}`) this.edit(key, cell.dataset.col);
            this.lastClick = `${key}:${cell.dataset.col}`;
            const bar = r && D.from(r.start);
            if (bar != null) {
                const l = this.x(bar), rr = this.x(D.from(r.end) + 1);
                if (rr < this.chart.scrollLeft || l > this.chart.scrollLeft + this.chart.clientWidth) this.scrollToDay((bar + D.from(r.end)) / 2, true);
            }
        });
        this.root.addEventListener('keydown', e => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.target.closest('input, textarea, select') && this.canEdit) { e.preventDefault(); this.undo(); }
        });
        this.bindSplitter();
        new ResizeObserver(() => { const before = this.width; this.computeRange(); if (before !== this.width) this.layout(); this.render(true); }).observe(this.chart);
        this.small.addEventListener('change', () => { this.selection.clear(); this.relayout(); });
        document.addEventListener('pointerdown', e => { if (this.menu && !this.menu.contains(e.target)) this.closeMenu(); }, true);
    }

    bindSplitter() {
        const sp = this.splitter;
        if (!sp) return;
        const set = w => {
            const max = Math.max(220, this.body.clientWidth * 0.7);
            this.treeW = Math.round(clamp(w, 160, max));
            this.body.style.setProperty('--gantt-tree-w', `${this.treeW}px`);
            sp.setAttribute('aria-valuenow', String(this.treeW));
            store.set('localStorage', 'scope-gantt-tree', this.treeW);
            this.render(true);
        };
        sp.addEventListener('pointerdown', e => {
            e.preventDefault();
            const x0 = e.clientX, w0 = this.tree.getBoundingClientRect().width;
            sp.setPointerCapture(e.pointerId);
            const move = ev => set(w0 + ev.clientX - x0);
            const up = () => { sp.removeEventListener('pointermove', move); sp.removeEventListener('pointerup', up); sp.removeEventListener('pointercancel', up); };
            sp.addEventListener('pointermove', move); sp.addEventListener('pointerup', up); sp.addEventListener('pointercancel', up);
        });
        sp.addEventListener('keydown', e => {
            const w = this.tree.getBoundingClientRect().width;
            if (e.key === 'ArrowLeft') { e.preventDefault(); set(w - 24); }
            if (e.key === 'ArrowRight') { e.preventDefault(); set(w + 24); }
        });
        sp.addEventListener('dblclick', () => { this.treeW = null; this.body.style.removeProperty('--gantt-tree-w'); try { localStorage.removeItem('scope-gantt-tree'); } catch { /* ignore */ } this.render(true); });
    }

    /* Generic pointer tracker with Esc-to-cancel and edge auto-scroll. */
    track(e, { move, end, cancel }) {
        const id = e.pointerId;
        this.canvas.setPointerCapture?.(id);
        let last = e;
        const edge = () => {
            const rect = this.chart.getBoundingClientRect();
            const dx = last.clientX < rect.left + 36 ? -12 : last.clientX > rect.right - 36 ? 12 : 0;
            if (dx) { this.chart.scrollLeft += dx; move(last); }
        };
        const timer = setInterval(edge, 40);
        const done = () => {
            clearInterval(timer);
            this.canvas.removeEventListener('pointermove', onMove);
            this.canvas.removeEventListener('pointerup', onUp);
            this.canvas.removeEventListener('pointercancel', onCancel);
            window.removeEventListener('keydown', onKey, true);
            this.dragging = false;
            this.root.classList.remove('is-dragging');
        };
        const onMove = ev => { last = ev; move(ev); };
        const onUp = ev => { done(); end(ev); };
        const onCancel = () => { done(); cancel(); };
        const onKey = ev => { if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); done(); cancel(); } };
        this.dragging = true;
        this.root.classList.add('is-dragging');
        this.canvas.addEventListener('pointermove', onMove);
        this.canvas.addEventListener('pointerup', onUp);
        this.canvas.addEventListener('pointercancel', onCancel);
        window.addEventListener('keydown', onKey, true);
    }

    onPointerDown(e) {
        if (e.button !== 0 || e.target.closest('.gantt-chip, .gantt-draft-input')) return;
        this.closeMenu();
        const barEl = e.target.closest('.gantt-bar:not(.is-draft)');
        const key = (barEl || e.target.closest('[data-key]'))?.dataset.key;
        const r = key && this.byId.get(key) || (key && this.visible[this.rowIndex.get(key)]);
        if (this.canEdit && r && e.target.closest('.gantt-dot')) { e.preventDefault(); return this.startLink(e, r, e.target.closest('.gantt-dot').dataset.side); }
        if (this.canEdit && r && e.target.closest('.gantt-handle')) { e.preventDefault(); return this.startDrag(e, r, e.target.closest('.gantt-handle').dataset.side === 'l' ? 'start' : 'end', barEl); }
        if (barEl && r) {
            if (this.canEdit && r.kind === 'task' && r.editable) { e.preventDefault(); return this.startDrag(e, r, 'move', barEl); }
            if (r.kind === 'task' && r.lock && this.canEdit) { this.tipAt(barEl, r.lock, true); setTimeout(() => this.hideTip(), 1800); }
            return this.clickThrough(e, r);
        }
        if (this.canEdit && r && this.creatable(r) && e.pointerType !== 'touch') { e.preventDefault(); return this.startCreate(e, r); }
        if (e.pointerType === 'mouse') this.startPan(e);
    }

    clickThrough(e, r) {
        const x0 = e.clientX, y0 = e.clientY;
        const up = ev => {
            this.canvas.removeEventListener('pointerup', up);
            if (Math.hypot(ev.clientX - x0, ev.clientY - y0) < 5) { this.setCursor(r.id, true); if (!this.canEdit) this.open(r); }
        };
        this.canvas.addEventListener('pointerup', up);
    }

    startPan(e) {
        const x0 = e.clientX, y0 = e.clientY, l0 = this.chart.scrollLeft, t0 = this.chart.scrollTop;
        this.root.classList.add('is-panning');
        this.canvas.setPointerCapture?.(e.pointerId);
        const move = ev => { this.chart.scrollLeft = l0 - (ev.clientX - x0); this.chart.scrollTop = t0 - (ev.clientY - y0); };
        const up = () => { this.root.classList.remove('is-panning'); this.canvas.removeEventListener('pointermove', move); this.canvas.removeEventListener('pointerup', up); this.canvas.removeEventListener('pointercancel', up); };
        this.canvas.addEventListener('pointermove', move); this.canvas.addEventListener('pointerup', up); this.canvas.addEventListener('pointercancel', up);
    }

    /* Move / resize with snap-to-day, ghost and live validation. */
    startDrag(e, r, mode, barEl) {
        const s0 = D.from(r.start), e0 = D.from(r.end), d0 = this.dayAt(e.clientX), x0 = e.clientX;
        let ns = s0, ne = e0, moved = false, problem = null, hits = [];
        const ghost = h('div', { class: 'gantt-ghost', style: { left: barEl.style.left, width: barEl.style.width, top: barEl.style.top, height: `${barEl.offsetHeight}px` } });
        this.setCursor(r.id, false);
        this.track(e, {
            move: ev => {
                if (!moved && Math.abs(ev.clientX - x0) < 4) return;
                if (!moved) { moved = true; this.barLayer.prepend(ghost); barEl.classList.add('is-moving'); }
                const d = this.dayAt(ev.clientX) - d0;
                if (mode === 'move') { ns = s0 + d; ne = e0 + d; }
                else if (mode === 'start') { ns = Math.min(s0 + d, e0); ne = e0; }
                else { ns = s0; ne = Math.max(e0 + d, s0); }
                problem = this.problem(r, ns, ne, mode);
                hits = problem ? [] : this.successorsHit(r, ne);
                barEl.style.left = `${this.x(ns)}px`;
                barEl.style.width = `${Math.max(span(ns, ne) * this.px, 6)}px`;
                barEl.classList.toggle('is-invalid', !!problem);
                ghost.classList.toggle('is-invalid', !!problem);
                const info = `${D.short(ns)} – ${D.short(ne)} · ${plural(span(ns, ne), 'hari')}`;
                this.tipAt(barEl, problem ? `Ditolak: ${problem}` : hits.length ? `${info} · ${hits.length} penerus terdampak` : info, !!problem);
            },
            end: () => {
                this.hideTip();
                ghost.remove();
                if (!moved) { this.setCursor(r.id, true); return; }
                if (problem) { this.render(true); this.toast(problem, { error: true }); this.say(`Ditolak: ${problem}`); return; }
                if (ns === s0 && ne === e0) { this.render(true); return; }
                this.saveDates(r, ns, ne);
            },
            cancel: () => { this.hideTip(); ghost.remove(); this.render(true); this.say('Perubahan dibatalkan.'); },
        });
    }

    tipAt(barEl, text, error = false) { this.tipXY(parseFloat(barEl.style.left), parseFloat(barEl.style.top) - 30, text, error); }
    tipXY(x, y, text, error = false) {
        this.tip.hidden = false;
        this.tip.textContent = text;
        this.tip.classList.toggle('is-error', error);
        this.tip.style.top = `${Math.max(2, y)}px`;
        this.tip.style.left = `${clamp(x, this.chart.scrollLeft + 4, Math.max(this.chart.scrollLeft + 4, this.chart.scrollLeft + this.chart.clientWidth - 280))}px`;
    }
    hideTip() { this.tip.hidden = true; }

    async saveDates(r, ns, ne, { shift = false, quiet = false } = {}) {
        const before = { start: r.start, end: r.end };
        r.start = D.iso(ns); r.end = D.iso(ne);
        this.render(true);
        const res = await api(this.url('dates', r.task), { start: D.iso(ns), end: D.iso(ne), shift_successors: shift ? 'true' : '' }, { form: true });
        if (res.status === 409 && res.code === 'successor_conflict') {
            Object.assign(r, before); this.render(true);
            const ok = await this.confirmImpact(res.error, res.impact);
            if (ok) return this.saveDates(r, ns, ne, { shift: true, quiet });
            this.say('Dibatalkan; jadwal tidak berubah.');
            return false;
        }
        if (!res.ok) {
            Object.assign(r, before); this.render(true);
            this.toast(res.error, { error: true }); this.say(`Ditolak: ${res.error}`);
            return false;
        }
        const changes = res.changes || [];
        if (changes.length) {
            const extra = changes.length - 1;
            this.pushUndo(`Jadwal "${r.title}" menjadi ${D.short(ns)} – ${D.short(ne)}${extra ? `; ${extra} task lain ikut digeser` : ''}.`, () => this.restoreDates(changes));
        }
        await this.reload();
        if (!quiet) this.say(`Tersimpan: ${r.title}, ${D.long(ns)} sampai ${D.long(ne)}.`);
        this.focusBar(r.id);
        return true;
    }

    restoreDates(changes) {
        return api(this.urls.bulkDates, { reason: 'undo', changes: changes.map(c => ({ id: c.id, start: c.old_start, end: c.old_end })) });
    }

    /* Drag on an empty track: schedule an undated task or draft a new one. */
    startCreate(e, r) {
        const d0 = this.dayAt(e.clientX), x0 = e.clientX;
        let ns = d0, ne = d0, moved = false;
        this.cancelDraft();
        this.draft = { rowKey: r.id, start: d0, end: d0 };
        this.render(true);
        this.track(e, {
            move: ev => {
                if (!moved && Math.abs(ev.clientX - x0) < 4) return;
                moved = true;
                const d = this.dayAt(ev.clientX);
                ns = Math.min(d0, d); ne = Math.max(d0, d);
                Object.assign(this.draft, { start: ns, end: ne });
                const bar = this.barLayer.querySelector('.is-draft');
                if (bar) { bar.style.left = `${this.x(ns)}px`; bar.style.width = `${span(ns, ne) * this.px}px`; this.tipAt(bar, `${D.short(ns)} – ${D.short(ne)} · ${plural(span(ns, ne), 'hari')}`); }
            },
            end: () => {
                this.hideTip();
                if (!moved) ne = ns + 2;
                if (r.kind === 'task') {
                    this.draft = null;
                    const problem = this.problem(r, ns, ne, 'move');
                    if (problem) { this.render(true); this.toast(problem, { error: true }); return; }
                    this.saveDates(r, ns, ne);
                    return;
                }
                this.openDraft(r, ns, ne);
            },
            cancel: () => { this.hideTip(); this.cancelDraft(); },
        });
    }

    openDraft(r, ns, ne) {
        const parentTask = r.parentTask || null;
        const input = h('input', {
            class: 'gantt-draft-input pcc-field', type: 'text', maxlength: '200', placeholder: 'Judul task, lalu Enter',
            'aria-label': `Judul task baru, ${D.long(ns)} sampai ${D.long(ne)}`,
        });
        this.draft = { rowKey: r.id, start: ns, end: ne, input, phase: r.phase ?? null, parentTask };
        input.addEventListener('keydown', async ev => {
            if (ev.key === 'Escape') { ev.preventDefault(); this.cancelDraft(); this.say('Task baru dibatalkan.'); }
            if (ev.key === 'Enter' && input.value.trim()) {
                ev.preventDefault();
                const d = this.draft;
                input.disabled = true;
                const ok = await this.create({ items: [{ title: input.value.trim(), start: D.iso(d.start), end: D.iso(d.end) }], phase: d.phase, parent: d.parentTask });
                if (ok) this.draft = null; else input.disabled = false;
                this.render(true);
            }
        });
        input.addEventListener('paste', ev => this.interceptPaste(ev, { phase: r.phase ?? null, parent: parentTask, start: ns }));
        input.addEventListener('blur', () => setTimeout(() => { if (this.draft?.input === input && !input.value.trim() && !input.disabled) this.cancelDraft(); }, 150));
        this.render(true);
        requestAnimationFrame(() => requestAnimationFrame(() => input.focus()));
    }

    cancelDraft() { if (this.draft) { this.draft = null; this.render(true); } }

    interceptPaste(ev, opts) {
        const text = ev.clipboardData?.getData('text') || '';
        if (!/\r?\n/.test(text.trim())) return;
        ev.preventDefault();
        this.cancelDraft();
        this.closeAddRow();
        this.pasteDialog({ ...opts, text });
    }

    async create(body) {
        const res = await api(this.urls.create, body);
        if (!res.ok) { this.toast(res.error, { error: true }); this.say(`Gagal: ${res.error}`); return false; }
        const ids = res.ids || [];
        this.pushUndo(ids.length === 1 ? 'Task dibuat.' : `${ids.length} task dibuat.`, () => api(this.urls.undoCreate, { ids }));
        await this.reload();
        const first = this.byTask.get(ids[0]);
        if (first && this.rowIndex.has(first.id)) this.revealRow(first.id);
        return ids;
    }

    /* Tree "add task" row: quick, repeated entry. */
    openFirstAddRow() {
        const add = this.visible.find(r => r.kind === 'add');
        if (!add) {
            const firstPhase = (this.data.rows || []).find(r => r.kind === 'phase');
            if (firstPhase && this.collapsed.has(firstPhase.id)) { this.collapsed.delete(firstPhase.id); this.relayout(); return this.openFirstAddRow(); }
            this.toast('Tambahkan phase terlebih dahulu.', { error: true }); return;
        }
        this.openAddRow(add);
    }

    openAddRow(r) {
        this.addRow = { key: r.id, row: r };
        this.revealRow(r.id);
        this.render(true);
    }

    closeAddRow() { if (this.addRow) { this.addRow = null; if (this.subFor) { this.subFor = null; this.relayout(); } else this.render(true); } }

    mountAddInput() {
        const r = this.addRow.row;
        const rowEl = this.treeRows.querySelector(`[data-key="${CSS.escape(this.addRow.key)}"] .gantt-cell-add`);
        if (!rowEl) return;
        const input = this.addRow.input || h('input', {
            class: 'gantt-add-input pcc-field', type: 'text', maxlength: '200', placeholder: r.parentTask ? 'Judul detail activity, Enter' : 'Judul task, Enter (tempel banyak baris sekaligus)',
            'aria-label': r.parentTask ? 'Judul detail activity baru' : 'Judul task baru',
        });
        if (!this.addRow.input) {
            this.addRow.input = input;
            input.addEventListener('keydown', async ev => {
                if (ev.key === 'Escape') { ev.preventDefault(); this.closeAddRow(); return; }
                if (ev.key !== 'Enter' || !input.value.trim()) return;
                ev.preventDefault();
                const title = input.value.trim();
                input.disabled = true;
                const start = this.nextStart(r);
                const ok = await this.create({ items: [{ title, start: D.iso(start), end: D.iso(start + 2) }], phase: r.phase ?? null, parent: r.parentTask || null });
                input.disabled = false;
                if (ok) { input.value = ''; this.say(`Task ${title} dibuat. Ketik judul berikutnya.`); }
                this.render(true);
                requestAnimationFrame(() => this.addRow?.input?.focus());
            });
            input.addEventListener('paste', ev => this.interceptPaste(ev, { phase: r.phase ?? null, parent: r.parentTask || null, start: this.nextStart(r) }));
            input.addEventListener('blur', () => setTimeout(() => { if (this.addRow?.input === input && !input.value.trim() && !input.disabled && document.activeElement !== input) this.closeAddRow(); }, 200));
        }
        rowEl.replaceChildren(input);
        if (document.activeElement !== input) input.focus({ preventScroll: true });
    }

    /* Day after the last scheduled task of the group, or today. */
    nextStart(r) {
        let last = null;
        const parent = r.parentTask ? this.byTask.get(r.parentTask) : null;
        for (const row of this.data.rows || []) {
            if (row.kind !== 'task') continue;
            const same = parent ? row.parent === parent.id : (row.phase ?? null) === (r.phase ?? null) && !row.subtask;
            if (same && row.end) last = Math.max(last ?? -Infinity, D.from(row.end));
        }
        if (parent && last == null) return D.from(parent.start) ?? this.today;
        return last != null ? last + 1 : this.today;
    }

    revealRow(id) {
        const i = this.rowIndex.get(id);
        if (i == null) return;
        const top = i * ROW_H, view = this.chart.clientHeight - HEAD_H;
        if (top < this.chart.scrollTop) this.chart.scrollTop = top;
        else if (top + ROW_H > this.chart.scrollTop + view) this.chart.scrollTop = top + ROW_H - view;
    }

    setCursor(id, focusBar) {
        if (this.cursor !== id) {
            this.cursor = id;
            this.render(true);
        }
        if (focusBar) this.focusBar(id);
    }

    focusBar(id) {
        requestAnimationFrame(() => requestAnimationFrame(() => this.barLayer.querySelector(`.gantt-bar[data-key="${CSS.escape(id)}"]`)?.focus({ preventScroll: true })));
    }

    open(r, edit = false) {
        if (!r || r.kind !== 'task' && r.kind !== 'project') return;
        if (edit && this.canEdit && this.urls.edit) {
            const a = h('a', { href: this.url('edit', r.task), 'data-project-action': '', hidden: true });
            this.root.append(a); a.click(); a.remove();
            return;
        }
        if (r.updateUrl && !this.canEdit && document.getElementById('project-action-panel')) {
            const a = h('a', { href: r.updateUrl, 'data-project-action': '', hidden: true });
            this.root.append(a); a.click(); a.remove();
            return;
        }
        if (r.url) location.href = r.url;
    }

    /* Keyboard: bars ------------------------------------------------------ */
    onChartKey(e) {
        const barEl = e.target.closest?.('.gantt-bar');
        if (!barEl) {
            if (e.target === this.chart && ['ArrowDown', 'ArrowUp'].includes(e.key)) {
                const first = this.cursor || this.visible.find(r => r.start)?.id;
                if (first) { e.preventDefault(); this.setCursor(first, true); this.revealRow(first); }
            }
            if (e.target === this.chart && e.key.toLowerCase() === 't') this.scrollToDay(this.today, true);
            return;
        }
        const r = this.byId.get(barEl.dataset.key);
        if (!r) return;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            this.flushNudge();
            const i = this.rowIndex.get(r.id), dir = e.key === 'ArrowDown' ? 1 : -1;
            for (let j = i + dir; j >= 0 && j < this.visible.length; j += dir) {
                const next = this.visible[j];
                if (next.start && next.kind !== 'add') { this.setCursor(next.id, true); this.revealRow(next.id); this.keepBarInView(next); break; }
            }
            return;
        }
        if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') && this.canEdit && r.kind === 'task') {
            e.preventDefault();
            if (!r.editable) { this.say(r.lock || 'Task ini tidak bisa dijadwalkan ulang.'); return; }
            const dir = e.key === 'ArrowRight' ? 1 : -1;
            const p = this.pending && this.pending.r === r ? this.pending : { r, s0: D.from(r.start), e0: D.from(r.end), ns: D.from(r.start), ne: D.from(r.end) };
            if (e.shiftKey) p.ne = Math.max(p.ns, p.ne + dir); else { p.ns += dir; p.ne += dir; }
            this.pending = p;
            const problem = this.problem(r, p.ns, p.ne, e.shiftKey ? 'end' : 'move');
            barEl.style.left = `${this.x(p.ns)}px`;
            barEl.style.width = `${Math.max(span(p.ns, p.ne) * this.px, 6)}px`;
            barEl.classList.toggle('is-invalid', !!problem);
            this.tipAt(barEl, problem ? `Ditolak: ${problem}` : `${D.short(p.ns)} – ${D.short(p.ne)} · ${plural(span(p.ns, p.ne), 'hari')} · Enter simpan, Esc batal`, !!problem);
            this.say(problem ? `Tidak valid: ${problem}` : `Mulai ${D.long(p.ns)}, selesai ${D.long(p.ne)}, ${plural(span(p.ns, p.ne), 'hari')}.`);
            clearTimeout(this.nudgeTimer);
            this.nudgeTimer = setTimeout(() => this.flushNudge(), 900);
            return;
        }
        if (e.key === 'Escape' && this.pending) { e.preventDefault(); clearTimeout(this.nudgeTimer); this.pending = null; this.hideTip(); this.render(true); this.say('Perubahan dibatalkan.'); return; }
        if (e.key === 'Enter') { e.preventDefault(); if (this.pending) this.flushNudge(); else this.open(r, this.canEdit); return; }
        if (e.key === ' ' && this.canEdit && r.task) { e.preventDefault(); this.toggleSelect(r, e.shiftKey); return; }
        if (e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) { e.preventDefault(); this.openMenu(r, barEl); }
    }

    keepBarInView(r) {
        const s = D.from(r.start), e = D.from(r.end);
        if (s == null) return;
        if (this.x(e + 1) < this.chart.scrollLeft || this.x(s) > this.chart.scrollLeft + this.chart.clientWidth - 40) this.scrollToDay(s + (e - s) / 2);
    }

    flushNudge() {
        clearTimeout(this.nudgeTimer);
        const p = this.pending;
        if (!p) return;
        this.pending = null;
        this.hideTip();
        if (p.ns === p.s0 && p.ne === p.e0) { this.render(true); return; }
        const problem = this.problem(p.r, p.ns, p.ne, 'move');
        if (problem) { this.render(true); this.toast(problem, { error: true }); this.focusBar(p.r.id); return; }
        this.saveDates(p.r, p.ns, p.ne);
    }

    /* Keyboard: tree (treegrid conventions) ------------------------------ */
    onTreeKey(e) {
        if (e.target.closest('.gantt-editor, .gantt-add-input')) return;
        const cell = e.target.closest('.gantt-cell');
        const rowEl = e.target.closest('[data-key]');
        if (!cell || !rowEl) return;
        const key = rowEl.dataset.key, r = this.byId.get(key), col = cell.dataset.col;
        const cols = ['title', ...this.columns().map(c => c.key)];
        const move = (id, c) => { this.setCursor(id, false); this.revealRow(id); requestAnimationFrame(() => requestAnimationFrame(() => this.treeCell(id, c)?.focus({ preventScroll: true }))); };
        const i = this.rowIndex.get(key);
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            const j = clamp(i + (e.key === 'ArrowDown' ? 1 : -1), 0, this.visible.length - 1);
            const next = this.visible[j];
            move(next.id, next.kind === 'add' ? 'title' : col);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            if (col === 'title' && this.kids.has(key) && this.collapsed.has(key)) this.toggle(key);
            else if (cols.indexOf(col) < cols.length - 1 && r) move(key, cols[cols.indexOf(col) + 1]);
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            if (col === 'title' && this.kids.has(key) && !this.collapsed.has(key)) this.toggle(key);
            else if (col !== 'title') move(key, cols[cols.indexOf(col) - 1]);
            else if (r?.parent && this.rowIndex.has(r.parent)) move(r.parent, 'title');
        } else if (e.key === 'Home') { e.preventDefault(); move(this.visible[0].id, col); }
        else if (e.key === 'End') { e.preventDefault(); move(this.visible.at(-1).id, col); }
        else if ((e.key === 'Enter' || e.key === 'F2') && r?.kind === 'task' && cell.classList.contains('is-editable')) { e.preventDefault(); this.edit(key, col); }
        else if (e.key === 'Enter' && !r) { e.preventDefault(); this.openAddRow(this.visible[i]); }
        else if (e.key === 'Enter' && r?.kind !== 'task') { e.preventDefault(); if (this.kids.has(key)) this.toggle(key); else if (r?.url) location.href = r.url; }
        else if (e.key === ' ' && r?.task && this.canEdit) { e.preventDefault(); this.toggleSelect(r, e.shiftKey); }
        else if ((e.key === 'ContextMenu' || (e.shiftKey && e.key === 'F10')) && r?.kind === 'task') { e.preventDefault(); this.openMenu(r, cell); }
    }

    /* Inline cell editor ------------------------------------------------- */
    edit(key, col) {
        const r = this.byId.get(key);
        if (!this.canEdit || !r || r.kind !== 'task') return;
        if ((col === 'start' || col === 'end') && !r.editable) { this.toast(r.lock || 'Jadwal task ini dikunci.', { error: true }); return; }
        const cell = this.treeCell(key, col);
        if (!cell) return;
        let input;
        if (col === 'title') input = h('input', { type: 'text', value: r.title, maxlength: '200', 'aria-label': 'Judul task' });
        else if (col === 'start' || col === 'end') input = h('input', { type: 'date', value: r[col] || '', 'aria-label': col === 'start' ? 'Tanggal mulai' : 'Tanggal selesai' });
        else if (col === 'assignee') {
            input = h('select', { 'aria-label': 'Pelaksana' }, h('option', { value: '', text: 'Belum ditugaskan' }),
                (this.data.assignees || []).map(p => h('option', { value: p.id, text: p.name, selected: p.id === r.assignee })));
        } else return;
        input.className = 'gantt-editor pcc-field';
        this.editing = { key, col };
        const original = cell.cloneNode(true);
        cell.replaceChildren(input);
        input.focus();
        if (input.select) input.select();
        let finished = false;
        const finish = async commit => {
            if (finished) return;
            finished = true;
            this.editing = null;
            if (!commit) { cell.replaceWith(original); this.render(true); this.treeCell(key, col)?.focus(); return; }
            await this.commitEdit(r, col, input.value);
            requestAnimationFrame(() => requestAnimationFrame(() => this.treeCell(key, col)?.focus({ preventScroll: true })));
        };
        input.addEventListener('keydown', ev => {
            if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); finish(false); }
            if (ev.key === 'Enter') { ev.preventDefault(); finish(true); }
            if (ev.key === 'Tab') finish(true);
        });
        input.addEventListener('blur', () => finish(true));
        if (col === 'assignee') input.addEventListener('change', () => finish(true));
    }

    async commitEdit(r, col, value) {
        if (col === 'title') {
            const title = value.trim();
            if (!title || title === r.title) { this.render(true); if (!title) this.toast('Judul task wajib diisi.', { error: true }); return; }
            const old = r.title;
            const res = await api(this.url('patch', r.task), { title });
            if (!res.ok) { this.toast(res.error, { error: true }); this.render(true); return; }
            this.pushUndo(`Judul diubah menjadi "${title}".`, () => api(this.url('patch', r.task), { title: old }));
            await this.reload();
            return;
        }
        if (col === 'assignee') {
            const id = value ? Number(value) : null;
            if (id === (r.assignee ?? null)) { this.render(true); return; }
            const old = r.assignee ?? null;
            const res = await api(this.url('patch', r.task), { assignee: id });
            if (!res.ok) { this.toast(res.error, { error: true }); this.render(true); return; }
            this.pushUndo(`Pelaksana "${r.title}" diperbarui.`, () => api(this.url('patch', r.task), { assignee: old }));
            await this.reload();
            return;
        }
        const n = D.from(value);
        if (n == null) { this.render(true); return; }
        let s = D.from(r.start), e = D.from(r.end);
        const length = s != null && e != null ? e - s : 2;
        if (col === 'start') { s = n; if (e == null || e < s) e = s + length; }
        else { e = n; if (s == null) s = e - length; }
        if (s === D.from(r.start) && e === D.from(r.end)) { this.render(true); return; }
        const problem = this.problem(r, s, e, col === 'start' ? 'start' : 'end');
        if (problem) { this.toast(problem, { error: true }); this.render(true); return; }
        await this.saveDates(r, s, e);
    }

    /* Dependencies -------------------------------------------------------- */
    startLink(e, r, side) {
        const barEl = e.target.closest('.gantt-bar');
        const sx = side === 'r' ? parseFloat(barEl.style.left) + parseFloat(barEl.style.width) : parseFloat(barEl.style.left);
        const sy = this.rowIndex.get(r.id) * ROW_H + ROW_H / 2;
        const line = document.createElementNS(svgNS, 'path');
        line.setAttribute('class', 'gantt-link is-drawing');
        this.links.append(line);
        let target = null;
        this.track(e, {
            move: ev => {
                const rect = this.canvas.getBoundingClientRect();
                const x = ev.clientX - rect.left, y = ev.clientY - rect.top;
                line.setAttribute('d', `M${sx} ${sy}L${x} ${y}`);
                const hit = document.elementFromPoint(ev.clientX, ev.clientY)?.closest('.gantt-bar');
                this.barLayer.querySelectorAll('.is-link-target').forEach(n => n.classList.remove('is-link-target'));
                target = hit && hit !== barEl ? this.byId.get(hit.dataset.key) : null;
                if (target && target.kind === 'task') hit.classList.add('is-link-target'); else target = null;
                this.tipXY(x + 12, y - 34, target ? (side === 'r' ? `${r.title} → ${target.title}` : `${target.title} → ${r.title}`) : 'Lepas di bar task lain');
            },
            end: () => {
                line.remove(); this.hideTip();
                this.barLayer.querySelectorAll('.is-link-target').forEach(n => n.classList.remove('is-link-target'));
                if (!target) return;
                const [from, to] = side === 'r' ? [r, target] : [target, r];
                this.addLink(from, to);
            },
            cancel: () => { line.remove(); this.hideTip(); },
        });
    }

    reaches(from, to) {
        const stack = [from], seen = new Set();
        while (stack.length) {
            const cur = stack.pop();
            if (cur === to) return true;
            if (seen.has(cur)) continue;
            seen.add(cur);
            for (const l of this.data.links) if (l.to === cur) stack.push(l.from);
        }
        return false;
    }

    async addLink(from, to) {
        if (from.task === to.task) return;
        if (this.data.links.some(l => l.from === from.task && l.to === to.task)) { this.toast('Dependency ini sudah ada.', { error: true }); return; }
        if (this.reaches(from.task, to.task)) { this.toast(`Dependency ditolak: "${to.title}" sudah menjadi prasyarat "${from.title}" sehingga akan membentuk siklus.`, { error: true }); return; }
        const res = await api(this.urls.dependency, { from: from.task, to: to.task, action: 'add' });
        if (!res.ok) { this.toast(res.error, { error: true }); return; }
        await this.reload();
        if (res.warning) {
            this.undoStack.push({ label: 'Dependency ditambahkan.', run: () => api(this.urls.dependency, { from: from.task, to: to.task, action: 'remove' }) });
            this.toast(res.warning, { action: 'Geser penerus', onAction: () => this.shiftAfter(this.byTask.get(from.task)) });
        } else {
            this.pushUndo(`Dependency "${from.title}" → "${to.title}" ditambahkan.`, () => api(this.urls.dependency, { from: from.task, to: to.task, action: 'remove' }));
        }
    }

    async removeLink(from, to) {
        const a = this.byTask.get(from), b = this.byTask.get(to);
        const res = await api(this.urls.dependency, { from, to, action: 'remove' });
        if (!res.ok) { this.toast(res.error, { error: true }); return; }
        this.pushUndo(`Dependency "${a?.title}" → "${b?.title}" dihapus.`, () => api(this.urls.dependency, { from, to, action: 'add' }));
        await this.reload();
    }

    /* G7: push successors after a task, with an impact preview first. */
    async shiftAfter(r) {
        if (!r) return;
        const res = await api(this.url('dates', r.task), { start: r.start, end: r.end, shift_successors: 'true', preview: 'true' }, { form: true });
        if (!res.ok) { this.toast(res.error, { error: true }); return; }
        if (!res.impact?.length) { this.toast('Jadwal penerus sudah sesuai.'); return; }
        if (await this.confirmImpact('Geser task penerus agar dimulai setelah prasyaratnya selesai?', res.impact)) {
            this.saveDates(r, D.from(r.start), D.from(r.end), { shift: true });
        }
    }

    /* Menus --------------------------------------------------------------- */
    openMenu(r, anchor, cx, cy) {
        this.closeMenu();
        const items = [];
        const add = (label, run, disabled = false) => items.push(h('button', { type: 'button', role: 'menuitem', class: 'gantt-menu-item', disabled, onclick: () => { this.closeMenu(); run(); } }, label));
        if (r.url) add('Buka detail', () => { location.href = r.url; });
        if (r.updateUrl && !this.canEdit) add('Update progress…', () => this.open(r));
        if (this.canEdit) {
            add('Edit task…', () => this.open(r, true));
            add('Duplikat', () => this.duplicate(this.selection.has(r.task) && this.selection.size > 1 ? [...this.selection] : [r.task]));
            if (!r.subtask) add('Tambah detail activity', () => this.openSubRow(r));
            add(this.selection.has(r.task) ? 'Batal pilih' : 'Pilih', () => this.toggleSelect(r, false));
            const hits = this.successorsHit(r, D.from(r.end) ?? -Infinity);
            if (hits.length) add(`Geser ${plural(hits.length, 'penerus')} agar sesuai`, () => this.shiftAfter(r));
            for (const l of this.data.links.filter(l => l.from === r.task || l.to === r.task)) {
                const other = this.byTask.get(l.from === r.task ? l.to : l.from);
                if (other) add(`Hapus dependency ${l.from === r.task ? '→' : '←'} ${other.title}`, () => this.removeLink(l.from, l.to));
            }
        }
        if (r.start) add('Geser layar ke bar', () => this.scrollToDay((D.from(r.start) + D.from(r.end)) / 2, true));
        if (!items.length) return;
        this.showMenu(items, anchor, cx, cy, `Aksi ${r.title}`);
    }

    linkMenu(from, to, cx, cy) {
        const a = this.byTask.get(from), b = this.byTask.get(to);
        if (!a || !b) return;
        const items = [h('button', { type: 'button', role: 'menuitem', class: 'gantt-menu-item is-danger', onclick: () => { this.closeMenu(); this.removeLink(from, to); } }, `Hapus dependency ${a.title} → ${b.title}`)];
        if (D.from(b.start) <= D.from(a.end)) items.push(h('button', { type: 'button', role: 'menuitem', class: 'gantt-menu-item', onclick: () => { this.closeMenu(); this.shiftAfter(a); } }, 'Geser penerus agar sesuai'));
        this.showMenu(items, null, cx, cy, 'Aksi dependency');
    }

    showMenu(items, anchor, cx, cy, label) {
        const menu = h('div', { class: 'gantt-menu', role: 'menu', 'aria-label': label }, items);
        this.root.append(menu);
        const rootRect = this.root.getBoundingClientRect();
        const ar = anchor?.getBoundingClientRect();
        const x = (ar ? ar.left : cx) - rootRect.left, y = (ar ? ar.bottom + 4 : cy) - rootRect.top;
        menu.style.left = `${clamp(x, 4, rootRect.width - menu.offsetWidth - 4)}px`;
        menu.style.top = `${y}px`;
        this.menu = menu;
        this.menuReturn = anchor || document.activeElement;
        const buttons = [...menu.querySelectorAll('button:not([disabled])')];
        buttons[0]?.focus();
        menu.addEventListener('keydown', ev => {
            const i = buttons.indexOf(document.activeElement);
            if (ev.key === 'ArrowDown') { ev.preventDefault(); buttons[(i + 1) % buttons.length].focus(); }
            if (ev.key === 'ArrowUp') { ev.preventDefault(); buttons[(i - 1 + buttons.length) % buttons.length].focus(); }
            if (ev.key === 'Escape' || ev.key === 'Tab') { ev.preventDefault(); this.closeMenu(true); }
        });
    }

    closeMenu(restore = false) {
        if (!this.menu) return;
        this.menu.remove(); this.menu = null;
        if (restore) this.menuReturn?.focus?.();
    }

    openSubRow(r) {
        this.subFor = r.task;
        this.collapsed.delete(r.id);
        this.index(); this.layout();
        const add = this.visible.find(v => v.kind === 'add' && v.parentTask === r.task);
        if (add) this.openAddRow(add);
    }

    /* Bulk actions ------------------------------------------------------- */
    async duplicate(ids) {
        if (!ids.length) return;
        const res = await api(this.urls.duplicate, { ids });
        if (!res.ok) { this.toast(res.error, { error: true }); return; }
        const created = res.ids || [];
        this.pushUndo(`${plural(created.length, 'task')} diduplikasi.`, () => api(this.urls.undoCreate, { ids: created }));
        this.selection = new Set(created.filter(id => !ids.includes(id)));
        await this.reload();
    }

    dialog(title, body, actions) {
        const dlg = h('dialog', { class: 'gantt-dialog', 'aria-label': title },
            h('form', { method: 'dialog', class: 'gantt-dialog-form' },
                h('header', {}, h('h2', { text: title }), h('button', { type: 'button', class: 'icon-button', 'aria-label': 'Tutup', onclick: () => dlg.close('cancel') }, icon('close'))),
                h('div', { class: 'gantt-dialog-body' }, body),
                h('footer', {}, actions)));
        this.root.append(dlg);
        dlg.addEventListener('close', () => setTimeout(() => dlg.remove(), 0));
        dlg.showModal();
        return dlg;
    }

    confirmImpact(message, impact) {
        return new Promise(resolve => {
            const list = h('ul', { class: 'gantt-impact' }, (impact || []).map(c => h('li', {},
                h('strong', { text: c.title }),
                h('span', { text: `${c.old_start ? D.short(D.from(c.old_start)) : '—'} – ${c.old_end ? D.short(D.from(c.old_end)) : '—'} → ${D.short(D.from(c.start))} – ${D.short(D.from(c.end))}` }))));
            const dlg = this.dialog('Pratinjau dampak', [h('p', { text: message }), h('p', { class: 'gantt-muted', text: `${plural(impact.length, 'task')} akan berubah. Baseline tidak ikut berubah.` }), list], [
                h('button', { type: 'button', class: 'pcc-button pcc-button-secondary', onclick: () => dlg.close('cancel'), text: 'Batal' }),
                h('button', { type: 'button', class: 'pcc-button', onclick: () => dlg.close('ok'), text: 'Geser penerus & simpan' }),
            ]);
            dlg.addEventListener('close', () => resolve(dlg.returnValue === 'ok'));
            dlg.querySelector('footer .pcc-button:not(.pcc-button-secondary)').focus();
        });
    }

    phaseOptions(selected) {
        return (this.data.rows || []).filter(r => r.kind === 'phase').map(r => h('option', { value: r.phase ?? '', text: r.title, selected: (r.phase ?? null) === (selected ?? null) }));
    }

    pasteDialog({ phase = undefined, parent = null, start = null, text = '' } = {}) {
        const firstPhase = (this.data.rows || []).find(r => r.kind === 'phase');
        const ph = phase === undefined ? (firstPhase?.phase ?? null) : phase;
        const area = h('textarea', { class: 'pcc-field', rows: '8', id: 'gantt-paste-text', placeholder: 'Analisis kebutuhan\nDesain UI | 2026-11-10 | 2026-11-14 | rina\nPengujian | 17/11/2026 | 21/11/2026' });
        area.value = text;
        const phaseSel = h('select', { class: 'pcc-field', id: 'gantt-paste-phase', disabled: !!parent }, this.phaseOptions(ph));
        const startIn = h('input', { class: 'pcc-field', type: 'date', id: 'gantt-paste-start', value: D.iso(start ?? this.nextStart({ phase: ph, parentTask: parent })) });
        const dur = h('input', { class: 'pcc-field', type: 'number', min: '1', max: '365', value: '3', id: 'gantt-paste-duration' });
        const seq = h('input', { type: 'checkbox', checked: true, id: 'gantt-paste-seq' });
        const count = h('p', { class: 'gantt-muted', 'aria-live': 'polite' });
        const error = h('p', { class: 'gantt-error', role: 'alert', hidden: true });
        const update = () => {
            const lines = area.value.split(/\r?\n/).filter(l => l.trim()).length;
            count.textContent = lines ? `${plural(lines, 'task')} akan dibuat${parent ? ' sebagai detail activity' : ''}.` : 'Satu judul per baris.';
            submit.disabled = !lines;
        };
        phaseSel.addEventListener('change', () => { startIn.value = D.iso(this.nextStart({ phase: phaseSel.value ? Number(phaseSel.value) : null })); });
        const submit = h('button', { type: 'submit', class: 'pcc-button', text: 'Buat task' });
        const dlg = this.dialog(parent ? 'Tempel detail activity' : 'Tempel daftar task', [
            h('label', { class: 'gantt-label', for: 'gantt-paste-text', text: 'Satu task per baris' }),
            area,
            h('p', { class: 'gantt-muted', text: 'Opsional per baris: judul | mulai | selesai | pelaksana. Tanggal 2026-11-08 atau 08/11/2026; pelaksana dengan username atau nama.' }),
            h('div', { class: 'gantt-fields' },
                h('div', {}, h('label', { class: 'gantt-label', for: 'gantt-paste-phase', text: 'Phase' }), phaseSel),
                h('div', {}, h('label', { class: 'gantt-label', for: 'gantt-paste-start', text: 'Mulai dari' }), startIn),
                h('div', {}, h('label', { class: 'gantt-label', for: 'gantt-paste-duration', text: 'Durasi (hari)' }), dur)),
            h('label', { class: 'gantt-check', for: 'gantt-paste-seq' }, seq, h('span', { text: 'Jadwalkan berurutan untuk baris tanpa tanggal' })),
            count, error,
        ], [h('button', { type: 'button', class: 'pcc-button pcc-button-secondary', onclick: () => dlg.close('cancel'), text: 'Batal' }), submit]);
        area.addEventListener('input', update);
        update();
        dlg.querySelector('form').addEventListener('submit', async ev => {
            ev.preventDefault();
            submit.disabled = true; submit.setAttribute('aria-busy', 'true');
            const body = { text: area.value, phase: phaseSel.value ? Number(phaseSel.value) : null, parent, start: startIn.value, duration: Number(dur.value) || 3, sequential: seq.checked };
            const res = await api(this.urls.create, body);
            submit.removeAttribute('aria-busy');
            if (!res.ok) { error.hidden = false; error.textContent = res.error; submit.disabled = false; area.focus(); return; }
            dlg.close('ok');
            const ids = res.ids || [];
            this.pushUndo(`${plural(ids.length, 'task')} dibuat dari daftar.`, () => api(this.urls.undoCreate, { ids }));
            await this.reload();
            const first = this.byTask.get(ids[0]);
            if (first) { this.revealRow(first.id); this.setCursor(first.id, false); }
        });
        area.focus();
    }

    sequenceDialog() {
        const ordered = (this.data.rows || []).filter(r => r.kind === 'task' && this.selection.has(r.task));
        if (ordered.length < 2) { this.toast('Pilih minimal dua task.', { error: true }); return; }
        const starts = ordered.map(r => D.from(r.start)).filter(n => n != null);
        const startIn = h('input', { class: 'pcc-field', type: 'date', id: 'gantt-seq-start', value: D.iso(starts.length ? Math.min(...starts) : this.today) });
        const dur = h('input', { class: 'pcc-field', type: 'number', min: '1', max: '365', value: '3', id: 'gantt-seq-duration' });
        const link = h('input', { type: 'checkbox', id: 'gantt-seq-link' });
        const list = h('ol', { class: 'gantt-impact' });
        const note = h('p', { class: 'gantt-muted', 'aria-live': 'polite' });
        const error = h('p', { class: 'gantt-error', role: 'alert', hidden: true });
        const submit = h('button', { type: 'submit', class: 'pcc-button', text: `Susun ${ordered.length} task` });
        let shift = false, timer;
        const body = extra => ({ ids: ordered.map(r => r.task), start: startIn.value, duration: Number(dur.value) || 1, link: link.checked, shift_successors: shift, ...extra });
        const preview = async () => {
            shift = false;
            let res = await api(this.urls.sequence, body({ preview: true }));
            if (res.status === 409 && res.code === 'successor_conflict') { shift = true; res = await api(this.urls.sequence, body({ preview: true })); if (res.ok) res.shifted = true; }
            error.hidden = res.ok;
            if (!res.ok) { error.textContent = res.error; submit.disabled = true; list.replaceChildren(); note.textContent = ''; return; }
            submit.disabled = false;
            const impact = res.impact || [];
            list.replaceChildren(...impact.map(c => h('li', { class: c.primary ? '' : 'is-extra' }, h('strong', { text: c.title }), h('span', { text: `${D.short(D.from(c.start))} – ${D.short(D.from(c.end))}${c.primary ? '' : ' · penerus ikut digeser'}` }))));
            note.textContent = impact.length ? `${plural(impact.length, 'task')} akan berubah${res.shifted ? ', termasuk task penerus' : ''}.` : 'Urutan sudah sesuai; tidak ada perubahan tanggal.';
        };
        const schedule = () => { clearTimeout(timer); timer = setTimeout(preview, 250); };
        const dlg = this.dialog('Susun berurutan', [
            h('p', { class: 'gantt-muted', text: 'Task dijadwalkan satu setelah yang lain sesuai urutan di daftar. Durasi tiap task dipertahankan.' }),
            h('div', { class: 'gantt-fields' },
                h('div', {}, h('label', { class: 'gantt-label', for: 'gantt-seq-start', text: 'Mulai' }), startIn),
                h('div', {}, h('label', { class: 'gantt-label', for: 'gantt-seq-duration', text: 'Durasi task tanpa tanggal (hari)' }), dur)),
            h('label', { class: 'gantt-check', for: 'gantt-seq-link' }, link, h('span', { text: 'Hubungkan sebagai dependency (selesai → mulai)' })),
            note, list, error,
        ], [h('button', { type: 'button', class: 'pcc-button pcc-button-secondary', onclick: () => dlg.close('cancel'), text: 'Batal' }), submit]);
        for (const input of [startIn, dur, link]) input.addEventListener('input', schedule);
        preview();
        dlg.querySelector('form').addEventListener('submit', async ev => {
            ev.preventDefault();
            submit.disabled = true;
            const res = await api(this.urls.sequence, body({}));
            if (!res.ok) { error.hidden = false; error.textContent = res.error; submit.disabled = false; return; }
            dlg.close('ok');
            const changes = res.changes || [], links = res.links || [];
            this.pushUndo(`${plural(ordered.length, 'task')} disusun berurutan.`, async () => {
                for (const l of links) await api(this.urls.dependency, { from: l.from, to: l.to, action: 'remove' });
                return changes.length ? this.restoreDates(changes) : { ok: true };
            });
            this.selection.clear();
            await this.reload();
        });
    }
}

function mount(root = document) {
    root.querySelectorAll('[data-gantt]:not(.gantt-ready)').forEach(node => {
        try { node.gantt = new Gantt(node); } catch (error) { console.error('Gantt gagal dimuat', error); }
    });
}
window.ScopeGantt = { mount, Gantt };
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount());
else mount();
})();
