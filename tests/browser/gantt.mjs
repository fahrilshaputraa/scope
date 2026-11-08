// Interactive Gantt regression (roadmap G1-G9). WRITES DATA: run only against an
// isolated seeded demo database (seed_demo), never against real projects.
// Requires Node 22+ and a Chrome debugging session. Logs in when PCC_USER/PCC_PASSWORD are set.
// PCC_TEST_URL=http://127.0.0.1:8002 PCC_CDP_URL=http://127.0.0.1:9223 PCC_USER=fahril PCC_PASSWORD=...
// node tests/browser/gantt.mjs   (PCC_SCREENSHOT=/tmp/gantt.png saves a desktop screenshot)
import assert from 'node:assert/strict';
import fs from 'node:fs';
const origin = process.env.PCC_TEST_URL || 'http://127.0.0.1:8002';
const endpoint = process.env.PCC_CDP_URL || 'http://127.0.0.1:9223';
const project = process.env.PCC_TEST_PROJECT || '1';
const tab = await (await fetch(`${endpoint}/json/new?about:blank`, { method: 'PUT' })).json();
const socket = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
let sequence = 0;
const pending = new Map(), errors = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
        const request = pending.get(message.id); pending.delete(message.id);
        if (message.error) request.reject(message.error); else request.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text);
});
const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence; pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
});
const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
    return result.result.value;
};
const settle = (ms = 700) => new Promise(resolve => setTimeout(resolve, ms));
const navigate = async path => { await call('Page.navigate', { url: origin + path }); await settle(900); };
const mouse = (type, x, y) => call('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: type === 'mouseReleased' ? 0 : 1, clickCount: 1, pointerType: 'mouse' });
const key = (k, code, vk, modifiers = 0) => call('Input.dispatchKeyEvent', { type: 'keyDown', key: k, code, windowsVirtualKeyCode: vk, modifiers }).then(() => call('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code, windowsVirtualKeyCode: vk, modifiers }));
const type = text => call('Input.insertText', { text });
const drag = async (x0, y0, x1, y1) => {
    await call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x0, y: y0 });
    await mouse('mousePressed', x0, y0);
    for (let i = 1; i <= 8; i++) await call('Input.dispatchMouseEvent', { type: 'mouseMoved', x: x0 + (x1 - x0) * i / 8, y: y0 + (y1 - y0) * i / 8, buttons: 1 });
    await mouse('mouseReleased', x1, y1);
    await settle(900);
};
const R = Date.now().toString(36).slice(-4);
const G = 'document.querySelector("[data-gantt]").gantt';
const row = title => `${G}.data.rows.find(r => r.title === ${JSON.stringify(title)})`;
const barBox = title => evaluate(`(()=>{const g=${G};const r=${row(title)};g.revealRow(r.id);g.paint();const b=document.querySelector('.gantt-bar[data-key="'+r.id+'"]');b.scrollIntoView({block:'center',inline:'center'});g.paint();const x=document.querySelector('.gantt-bar[data-key="'+r.id+'"]').getBoundingClientRect();return {x:x.x,y:x.y,w:x.width,h:x.height,px:g.px}})()`);
try {
    await call('Page.enable'); await call('Runtime.enable');
    await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
    await navigate(`/projects/${project}/timeline/`);
    if (await evaluate(`!!document.querySelector('[name=username]')`)) {
        assert.ok(process.env.PCC_USER, 'Log in first or set PCC_USER/PCC_PASSWORD.');
        await evaluate(`document.querySelector('[name=username]').value=${JSON.stringify(process.env.PCC_USER)};document.querySelector('[name=password]').value=${JSON.stringify(process.env.PCC_PASSWORD || '')};document.querySelector('[name=username]').form.submit()`);
        await settle(3000);
        await navigate(`/projects/${project}/timeline/`);
    }
    await evaluate(`sessionStorage.clear()`); await navigate(`/projects/${project}/timeline/`);
    assert.ok(await evaluate(`${G}.canEdit`), 'Use the project PM account so the Gantt is editable.');
    await evaluate(`window.ScopeTheme?.set('light')`);
    // G1/G2: two synced panes, scales, zoom keeps the centre date.
    assert.ok(await evaluate(`document.querySelectorAll('.gantt-row').length > 3 && document.querySelectorAll('.gantt-bar').length > 3`));
    await evaluate(`document.querySelector('[data-gantt-chart]').scrollTop = 80`); await settle(200);
    assert.equal(await evaluate(`document.querySelector('[data-gantt-tree]').scrollTop`), 80, 'Vertical scroll is synced.');
    await evaluate(`document.querySelector('[data-gantt-chart]').scrollTop = 0`);
    const centre = await evaluate(`${G}.centerDay()`);
    await evaluate(`document.querySelector('[data-scale="day"]').click()`); await settle(300);
    assert.equal(await evaluate(`document.querySelector('[data-scale="day"]').getAttribute('aria-pressed')`), 'true');
    assert.ok(Math.abs(await evaluate(`${G}.centerDay()`) - centre) < 2, 'Zoom keeps the centre date.');
    for (const s of ['month', 'quarter', 'week']) { await evaluate(`document.querySelector('[data-scale="${s}"]').click()`); await settle(200); }
    assert.ok(await evaluate(`document.querySelectorAll('.gantt-scale-bottom .gantt-tick').length > 3`));
    // G3: baseline, milestone, summary rows, status tones.
    assert.ok(await evaluate(`document.querySelectorAll('.gantt-bar.is-summary').length > 0`));
    // G4/G8: keyboard nudge saves through task_dates; undo restores.
    await evaluate(`document.querySelector('[data-scale="day"]').click()`); await settle(300);
    const target = await evaluate(`${G}.data.rows.find(r => r.kind==='task' && r.editable && !r.hasChildren && !r.subtask && !${G}.data.links.some(l=>l.to===r.task || l.from===r.task)).title`);
    const before = await evaluate(`${row(target)}.start`);
    await barBox(target);
    await evaluate(`(()=>{const g=${G};const r=${row(target)};g.setCursor(r.id,false);g.paint();document.querySelector('.gantt-bar[data-key="'+r.id+'"]').focus()})()`);
    await key('ArrowRight', 'ArrowRight', 39); await key('ArrowRight', 'ArrowRight', 39);
    await key('Enter', 'Enter', 13); await settle(1200);
    const after = await evaluate(`${row(target)}.start`);
    assert.equal((new Date(after) - new Date(before)) / 864e5, 2, 'Arrow keys move the bar by days.');
    assert.match(await evaluate(`document.querySelector('[data-gantt-live]').textContent + document.querySelector('[data-gantt-toast]').textContent`), /Tersimpan|Jadwal/);
    await evaluate(`document.querySelector('.gantt-toast-action').click()`); await settle(1200);
    assert.equal(await evaluate(`${row(target)}.start`), before, 'Undo restores the previous dates.');
    // G4: pointer drag moves by whole days.
    let box = await barBox(target);
    await drag(box.x + box.w / 2, box.y + box.h / 2, box.x + box.w / 2 + box.px * 3, box.y + box.h / 2);
    assert.equal((new Date(await evaluate(`${row(target)}.start`)) - new Date(before)) / 864e5, 3, 'Drag snaps to days.');
    await evaluate(`document.querySelector('.gantt-toast-action').click()`); await settle(1200);
    // Quick create: inline add row keeps the input open for the next title.
    await evaluate(`document.querySelector('.gantt-edit-tools .gantt-btn-primary').click()`); await settle(500);
    assert.ok(await evaluate(`document.activeElement.classList.contains('gantt-add-input')`));
    await type(`Task cepat satu ${R}`); await key('Enter', 'Enter', 13); await settle(1300);
    assert.ok(await evaluate(`document.activeElement.classList.contains('gantt-add-input')`), 'Input stays open for rapid entry.');
    await type(`Task cepat dua ${R}`); await key('Enter', 'Enter', 13); await settle(1300);
    assert.ok(await evaluate(`!!${row(`Task cepat satu ${R}`)} && !!${row(`Task cepat dua ${R}`)}`));
    await key('Escape', 'Escape', 27);
    // Paste list dialog creates many tasks at once.
    await evaluate(`[...document.querySelectorAll('.gantt-btn')].find(b=>b.textContent.includes('Tempel daftar')).click()`); await settle(300);
    await evaluate(`(()=>{const t=document.querySelector('#gantt-paste-text');t.value='Tempel A ${R}\\nTempel B ${R} | 2026-12-01 | 2026-12-03\\nTempel C ${R}';t.dispatchEvent(new Event('input'))})()`);
    await evaluate(`document.querySelector('.gantt-dialog form').requestSubmit()`); await settle(1500);
    assert.ok(await evaluate(`['Tempel A ${R}','Tempel B ${R}','Tempel C ${R}'].every(t => ${G}.data.rows.some(r => r.title === t))`), 'Paste list creates tasks.');
    assert.equal(await evaluate(`${row(`Tempel B ${R}`)}.start`), '2026-12-01');
    // Sequence + duplicate on a selection.
    await evaluate(`(()=>{const g=${G};for (const t of ['Tempel A ${R}','Tempel B ${R}','Tempel C ${R}']) g.selection.add(${G}.data.rows.find(r=>r.title===t).task);g.render(true)})()`); await settle(200);
    await evaluate(`[...document.querySelectorAll('.gantt-selection .gantt-btn')].find(b=>b.textContent.includes('Susun')).click()`); await settle(900);
    assert.ok(await evaluate(`document.querySelectorAll('.gantt-dialog .gantt-impact li').length >= 1`), 'Sequence shows a preview.');
    await evaluate(`document.querySelector('.gantt-dialog form').requestSubmit()`); await settle(1500);
    const seq = await evaluate(`['Tempel A ${R}','Tempel B ${R}','Tempel C ${R}'].map(t => [${G}.data.rows.find(r=>r.title===t).start, ${G}.data.rows.find(r=>r.title===t).end])`);
    assert.ok(seq[0][1] < seq[1][0] && seq[1][1] < seq[2][0], 'Selected tasks are chained.');
    await evaluate(`(()=>{const g=${G};g.duplicate([${row(`Tempel C ${R}`)}.task])})()`); await settle(1500);
    assert.ok(await evaluate(`!!${row(`Tempel C ${R} (salinan)`)}`));
    await evaluate(`document.querySelector('.gantt-toast-action').click()`); await settle(1300);
    assert.equal(await evaluate(`!!${row(`Tempel C ${R} (salinan)`)}`), false, 'Undo removes the duplicate.');
    // Inline title edit from the tree.
    await evaluate(`(()=>{const g=${G};const r=${row(`Tempel A ${R}`)};g.revealRow(r.id);g.paint();g.edit(r.id,'title')})()`); await settle(200);
    await evaluate(`document.querySelector('.gantt-editor').value='Tempel A ${R} diubah'`); await key('Enter', 'Enter', 13); await settle(1300);
    assert.ok(await evaluate(`!!${row(`Tempel A ${R} diubah`)}`));
    // G5/G6: create a dependency by dragging the end handle, then an invalid drop is rejected and reverted.
    const [first, second] = [`Tempel B ${R}`, `Tempel C ${R}`];
    const linkBefore = await evaluate(`${G}.data.links.length`);
    const a = await barBox(first);
    const dot = await evaluate(`(()=>{const r=${row(first)};const b=document.querySelector('.gantt-bar[data-key="'+r.id+'"] .gantt-dot[data-side="r"]').getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}})()`);
    const b = await evaluate(`(()=>{const g=${G};const r=${row(second)};const x=document.querySelector('.gantt-bar[data-key="'+r.id+'"]')?.getBoundingClientRect();return x?{x:x.x+x.width/2,y:x.y+x.height/2}:null})()`);
    assert.ok(a && b, 'Both bars visible for linking.');
    await drag(dot.x, dot.y, b.x, b.y); await settle(600);
    const linked = await evaluate(`${G}.data.links.length`);
    if (linked > linkBefore) {
        // Dragging the successor to start before the predecessor ends must be refused.
        const shift = await evaluate(`(new Date(${row(second)}.start) - new Date(${row(first)}.start)) / 864e5`);
        const s = await barBox(second);
        const startBefore = await evaluate(`${row(second)}.start`);
        await drag(s.x + s.w / 2, s.y + s.h / 2, s.x + s.w / 2 - (shift + 1) * s.px, s.y + s.h / 2);
        assert.equal(await evaluate(`${row(second)}.start`), startBefore, 'Rejected drop reverts the bar.');
        assert.ok(await evaluate(`document.querySelector('[data-gantt-toast]').classList.contains('is-error')`), 'Invalid drop shows an error.');
        assert.equal(await evaluate(`${row(second)}.start`) !== null, true);
        assert.match(await evaluate(`document.querySelector('[data-gantt-toast]').textContent`), /baru bisa dimulai|Ditolak|penerus/);
    } else {
        assert.match(await evaluate(`document.querySelector('[data-gantt-toast]').textContent`), /siklus|sudah ada|berjalan/, 'Link refusal explains why.');
    }
    if (process.env.PCC_SCREENSHOT) {
        await evaluate(`(()=>{const g=${G};g.selection.clear();document.querySelector('[data-scale="week"]').click();document.querySelector('[data-gantt-chart]').scrollTop=0;g.chart.scrollLeft=Math.max(0,g.x(g.workLo)-24)})()`); await settle(800);
        await evaluate(`document.querySelector('[data-gantt]').scrollIntoView({block:'start'});window.scrollBy(0,-90)`); await settle(400);
        const { data } = await call('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(process.env.PCC_SCREENSHOT, Buffer.from(data, 'base64'));
        await evaluate(`window.ScopeTheme?.set('dark')`); await settle(300);
        const dark = await call('Page.captureScreenshot', { format: 'png' });
        fs.writeFileSync(process.env.PCC_SCREENSHOT.replace(/\.png$/, '-dark.png'), Buffer.from(dark.data, 'base64'));
        await evaluate(`window.ScopeTheme?.set('light')`);
    }
    // G9: same component on the portfolio page; G8: mobile is read-only and contained at 390px.
    await navigate('/timeline/');
    assert.ok(await evaluate(`!!${G} && !${G}.canEdit && ${G}.data.mode === 'portfolio'`));
    await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
    for (const path of [`/projects/${project}/timeline/`, '/timeline/', '/reports/']) {
        await navigate(path);
        assert.ok(await evaluate(`document.body.scrollWidth <= innerWidth`), `Mobile containment: ${path}`);
        assert.equal(await evaluate(`${G}.canEdit`), false, `Mobile is read-only: ${path}`);
        assert.equal(await evaluate(`document.querySelectorAll('.gantt-handle').length`), 0);
    }
    assert.deepEqual(errors, []);
    console.log('PASS: synced panes, scales/zoom, keyboard + drag with undo, dependency + rejection, quick add, paste list, sequence, duplicate + undo, inline edit, portfolio reuse, mobile read-only.');
} finally { socket.close(); await fetch(`${endpoint}/json/close/${tab.id}`); }
