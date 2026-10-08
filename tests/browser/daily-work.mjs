// UX browser regression check (does not submit changes). Requires Node 22+, a logged-in Chrome
// debugging session and a project with enough scheduled work to scroll.
// PCC_TEST_URL=http://127.0.0.1:8002 PCC_CDP_URL=http://127.0.0.1:9223
// node tests/browser/visualizations.mjs
import assert from 'node:assert/strict';
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
    } else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
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
const settle = () => new Promise(resolve => setTimeout(resolve, 600));
const navigate = async path => { await call('Page.navigate', { url: origin + path }); await settle(); };
try {
    await call('Page.enable'); await call('Runtime.enable');
    await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
    await navigate(`/projects/${project}/`);
    assert.ok(await evaluate(`!!document.querySelector('.project-compact-summary') && document.querySelector('[data-fullscreen-panel]').dataset.fullscreenPanel==='Plan vs actual'`));
    await evaluate(`document.querySelector('[data-fullscreen-panel="Plan vs actual"] [data-fullscreen-toggle]').click()`); await settle();
    assert.ok(await evaluate(`!!document.fullscreenElement`));
    await evaluate(`document.querySelector('[data-fullscreen-panel="Plan vs actual"] [data-fullscreen-toggle]').click()`); await settle();
    await navigate('/my-tasks/');
    await evaluate(`document.querySelector('a[href*="mode=update"]').click()`); await settle();
    assert.deepEqual(await evaluate(`[...document.querySelector('dialog form').elements].filter(x=>x.name && x.name!=='csrfmiddlewaretoken').map(x=>x.name)`), ['status','progress','blocked_reason','blocked_dependency']);
    await evaluate(`document.querySelector('dialog [name=status]').value='blocked';document.querySelector('dialog [name=status]').dispatchEvent(new Event('change',{bubbles:true}))`);
    assert.equal(await evaluate(`document.querySelector('dialog [data-form-field=blocked_reason]').hidden`), false);
    await evaluate(`document.querySelector('[data-panel-close]').click()`);
    for (const path of [`/projects/${project}/`, '/my-tasks/']) {
        await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
        await navigate(path);
        assert.ok(await evaluate(`document.body.scrollWidth <= innerWidth`));
    }
    assert.deepEqual(errors, []);
    console.log('PASS: chart presentation, focused update drawer, blocker fields and mobile containment.');
} finally {
    socket.close();
    await fetch(`${endpoint}/json/close/${tab.id}`);
}
