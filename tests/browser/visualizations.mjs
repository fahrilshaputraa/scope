// Read-only browser regression check. Requires Node 22+, a logged-in Chrome
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
    await call('Emulation.setDeviceMetricsOverride', { width:1440, height:1000, deviceScaleFactor:1, mobile:false });
    await navigate(`/projects/${project}/timeline/`);
    assert.ok(await evaluate(`!!document.querySelector('[data-timeline-scroll]')`), 'A logged-in browser and project tasks are required.');
    await evaluate(`document.querySelector('[data-timeline-scale="2"]').click();document.querySelector('[data-timeline-scroll]').scrollIntoView({block:'center'})`);
    const stats = () => evaluate(`(()=>{const s=document.querySelector('[data-timeline-scroll]');return {left:s.scrollLeft,width:s.scrollWidth,viewport:s.clientWidth}})()`);
    const coords = await evaluate(`(()=>{const r=document.querySelector('[data-timeline-scroll]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()`);
    const before=await stats();
    for (const deltaX of [300,-300,300,-300]) {
        const previous=await stats();
        await call('Input.dispatchMouseEvent', { type:'mouseWheel',...coords,deltaX,deltaY:0 }); await settle();
        const after=await stats();
        assert.equal(after.width,before.width);
        assert.ok(Math.abs(after.left-Math.max(0,Math.min(previous.left+deltaX,after.width-after.viewport)))<2, 'Timeline must keep the wheel position.');
    }
    await evaluate(`document.querySelector('[data-fullscreen-toggle]').click()`);await settle();
    assert.ok(await evaluate(`!!document.fullscreenElement`));
    await evaluate(`document.querySelector('[data-timeline-scroll]').scrollLeft=200;document.querySelector('.task-time-bar[data-project-action]').click()`);await settle();
    assert.ok(await evaluate(`document.querySelector('dialog').open && document.fullscreenElement.contains(document.querySelector('dialog'))`), 'Update drawer must work inside native fullscreen.');
    assert.deepEqual(await evaluate(`[...document.querySelector('dialog form').elements].filter(x=>x.name && x.name!=='csrfmiddlewaretoken').map(x=>x.name)`), ['status','progress','blocked_reason','blocked_dependency']);
    await evaluate(`document.querySelector('[data-panel-close]').click()`);
    const left=await stats();
    await evaluate(`document.querySelector('[data-fullscreen-toggle]').click()`);await settle();
    assert.equal((await stats()).left,left.left,'Fullscreen exit keeps the latest scroll position.');
    await navigate(`/projects/${project}/timeline/`);
    assert.equal((await stats()).left,left.left,'Daily-update reload preserves the timeline position.');
    assert.equal(await evaluate(`document.querySelector('[data-timeline-scale="2"]').getAttribute('aria-pressed')`),'true');
    await evaluate(`Object.defineProperty(document,'fullscreenEnabled',{value:false,configurable:true});document.querySelector('[data-fullscreen-toggle]').click()`);
    assert.ok(await evaluate(`document.querySelector('aside').inert`));
    await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
    assert.equal(await evaluate(`document.querySelectorAll('.visualization-fullscreen').length`),0);
    assert.equal(await evaluate(`document.querySelector('aside').inert`),false);
    await navigate(`/projects/${project}/progress/`);
    assert.equal(await evaluate(`document.querySelectorAll('[data-fullscreen-toggle]').length`),3);
    const height=await evaluate(`document.querySelector('canvas').clientHeight`);
    await evaluate(`document.querySelector('[data-fullscreen-panel="Plan vs Actual Progress"] [data-fullscreen-toggle]').click()`);await settle();
    assert.ok(await evaluate(`document.querySelector('canvas').clientHeight`)>height);
    await evaluate(`document.querySelector('[data-fullscreen-panel="Plan vs Actual Progress"] [data-fullscreen-toggle]').click()`);await settle();
    for (const theme of ['light','dark']) {
        await evaluate(`window.ScopeTheme.set('${theme}')`);
        assert.equal(await evaluate(`document.documentElement.dataset.theme`),theme);
        await navigate(`/projects/${project}/`);
        assert.equal(await evaluate(`document.documentElement.dataset.theme`),theme,'Theme persists between pages.');
        assert.equal(await evaluate(`Object.values(Chart.instances)[0].data.datasets[1].borderColor`),await evaluate(`getComputedStyle(document.documentElement).getPropertyValue('--color-ink').trim()`));
    }
    await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
    for (const path of [`/projects/${project}/`,`/projects/${project}/timeline/`,`/projects/${project}/issues/`,`/projects/${project}/notes/`,'/reports/']) {
        await navigate(path);assert.ok(await evaluate(`document.body.scrollWidth<=innerWidth`), `Mobile containment: ${path}`);
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: stable timeline panning, native/fallback fullscreen, update drawer inside fullscreen, chart resize, theme persistence and mobile containment.');
} finally { socket.close();await fetch(`${endpoint}/json/close/${tab.id}`); }
