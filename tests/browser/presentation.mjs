// Run only against an isolated seeded demo project. Saves presentation config.
// Requires Node 22+, a Chrome debugging session and a feedback column.
// PCC_TEST_URL=http://127.0.0.1:8002 PCC_CDP_URL=http://127.0.0.1:9223
// node tests/browser/visualizations.mjs
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

const screenshot = async name => {const {data} = await call('Page.captureScreenshot',{format:'png'});fs.mkdirSync('/tmp/pcc-presentation',{recursive:true});fs.writeFileSync(`/tmp/pcc-presentation/${name}.png`,Buffer.from(data,'base64'));};
try {
 await call('Page.enable'); await call('Runtime.enable');
 await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1000,deviceScaleFactor:1,mobile:false});
 await navigate(`/projects/${project}/`);
 await evaluate(`document.querySelector('a[data-project-action][href$="/presentation/"]').click()`);await settle();
 if (await evaluate(`!!document.querySelector('[name=username]')`)) {
  await evaluate(`document.querySelector('[name=username]').value='fahril';document.querySelector('[name=password]').value='preview-only-password';document.querySelector('form').requestSubmit()`);await settle();
  await navigate(`/projects/${project}/`);
 await evaluate(`document.querySelector('a[data-project-action][href$="/presentation/"]').click()`);await settle();
 }
 assert.ok(await evaluate(`!!document.getElementById('slide-order')`));
 assert.ok(await evaluate(`document.querySelector('#project-action-panel').open`));
 assert.equal(await evaluate(`location.pathname`), `/projects/${project}/`);
 const periodEnd = await evaluate(`document.querySelector('[name=period_end]').value`);
 await evaluate(`document.querySelector('[name=period_end]').value='2000-01-01';document.querySelector('#presentation-config').requestSubmit(document.querySelector('#presentation-config button[type=submit]:not([name=action])'))`);await settle();
 assert.ok(await evaluate(`document.querySelector('#project-action-panel').open && document.querySelector('#project-action-panel .errorlist')`));
 await evaluate(`document.querySelector('[name=period_end]').value='${periodEnd}';document.querySelector('#presentation-config').requestSubmit(document.querySelector('#presentation-config button[type=submit]:not([name=action])'))`);await settle();
 assert.equal(await evaluate(`location.pathname`), `/projects/${project}/`);
 assert.equal(await evaluate(`document.querySelector('#project-action-panel').open`),false);
 await evaluate(`document.querySelector('a[data-project-action][href$="/presentation/"]').click()`);await settle();
 await evaluate(`window.ScopeTheme.set('light')`);
 await screenshot('setup-light');
 const original = await evaluate(`document.querySelector('#slide-order li').dataset.slideKey`);
 await evaluate(`document.querySelector('#slide-order li [data-move="1"]').click()`);
 assert.notEqual(await evaluate(`document.querySelector('#slide-order li').dataset.slideKey`), original);
 await evaluate(`document.querySelectorAll('#slide-order li')[1].querySelector('[data-move="-1"]').click()`);
 assert.equal(await evaluate(`document.querySelector('#slide-order li').dataset.slideKey`), original);
 await evaluate(`(()=>{const list=document.getElementById('slide-order'), source=list.children[1], target=list.children[0], transfer=new DataTransfer();source.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:transfer}));target.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer,clientY:target.getBoundingClientRect().top}));source.dispatchEvent(new DragEvent('dragend',{bubbles:true,dataTransfer:transfer}));})()`);
 assert.notEqual(await evaluate(`document.querySelector('#slide-order li').dataset.slideKey`), original);
 await evaluate(`document.querySelector('#slide-order li [data-move="1"]').click()`);
 assert.equal(await evaluate(`document.querySelector('#slide-order li').dataset.slideKey`), original);
 await evaluate(`document.querySelector('[name=action][value=play]').click()`);await settle();
 assert.ok(await evaluate(`!!document.querySelector('[data-presentation-player]')`));
 await screenshot('overview-light');
 const count = await evaluate(`document.querySelectorAll('[data-slide]').length`);
 assert.ok(count >= 5);
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});
 assert.equal(await evaluate(`document.querySelector('[data-slide-jump]').value`),'1');
 await screenshot('ongoing-light');
 await evaluate(`document.querySelector('[data-slide-next]').click()`); await screenshot('next-light');
 const issueIndex = await evaluate(`[...document.querySelectorAll('[data-slide]')].findIndex(s=>s.querySelector('h1').textContent==='Daftar masalah')`);
 await evaluate(`document.querySelector('[data-slide-jump]').value='${issueIndex}';document.querySelector('[data-slide-jump]').dispatchEvent(new Event('change'))`);
 await screenshot('issues-light');
 const feedback = await evaluate(`[...document.querySelectorAll('[data-slide]')].findIndex(s=>s.querySelector('h1').textContent==='Feedback Preview Fixing')`);
 assert.ok(feedback >= 0);
 await evaluate(`document.querySelector('[data-slide-jump]').value='${feedback}';document.querySelector('[data-slide-jump]').dispatchEvent(new Event('change'))`);
 await screenshot('feedback-light');
 await evaluate(`window.ScopeTheme.set('dark')`);
 assert.equal(await evaluate(`document.documentElement.dataset.theme`),'dark');await screenshot('feedback-dark');
 await evaluate(`document.querySelector('[data-slide-jump]').value='0';document.querySelector('[data-slide-jump]').dispatchEvent(new Event('change'))`);
 await screenshot('overview-dark');
 await evaluate(`document.querySelector('[data-presentation-fullscreen]').click()`);await settle();
 assert.ok(await evaluate(`!!document.fullscreenElement || document.querySelector('.presentation-fallback-fullscreen')`));
 await evaluate(`document.querySelector('[data-presentation-fullscreen]').click()`);await settle();
 assert.equal(await evaluate(`!!document.fullscreenElement`),false);
 await evaluate(`document.querySelector('[data-presentation-player]').requestFullscreen=()=>Promise.reject(new Error('Fallback check'));document.querySelector('[data-presentation-fullscreen]').click()`);await settle();
 assert.ok(await evaluate(`document.querySelector('.presentation-fallback-fullscreen')`));
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});
 assert.equal(await evaluate(`!!document.querySelector('.presentation-fallback-fullscreen')`),false);
 await evaluate(`document.getElementById('presentation-stage').focus()`);
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'End',code:'End',windowsVirtualKeyCode:35});
 assert.equal(await evaluate(`document.querySelector('[data-slide-jump]').value`),String(count-1));
 assert.ok(await evaluate(`document.querySelector('[data-slide-next]').disabled`));await screenshot('closing-dark');
 await evaluate(`document.getElementById('presentation-stage').focus()`);
 await call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape',windowsVirtualKeyCode:27});await settle();
 assert.equal(await evaluate(`location.pathname`), `/projects/${project}/`);
 await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
 await navigate(`/projects/${project}/`);
 await evaluate(`document.querySelector('a[data-project-action][href$="/presentation/"]').click()`);await settle();assert.ok(await evaluate(`document.querySelector('#project-action-panel').open && document.querySelector('#project-action-panel').scrollWidth<=innerWidth`));await screenshot('setup-mobile');
 await navigate(`/projects/${project}/presentation/play/`);assert.ok(await evaluate(`document.body.scrollWidth<=innerWidth`));await screenshot('overview-mobile');
 await evaluate(`document.querySelector('[data-slide-next]').click()`);assert.ok(await evaluate(`document.body.scrollWidth<=innerWidth`));await screenshot('ongoing-mobile');
 await navigate(`/projects/${project}/tasks/`);assert.ok(await evaluate(`document.body.scrollWidth<=innerWidth`));
 assert.ok(await evaluate(`!!document.querySelector('[data-custom-column]')`));
 await evaluate(`document.querySelector('[data-custom-column]').scrollIntoView({block:'center',inline:'center'})`);await screenshot('kanban-mobile');
 await evaluate(`window.originalUpdate=PCC.update;PCC.update=async(url,data)=>{window.testMove={url,data};throw new Error('Read-only move check')}`);
 const taskId = await evaluate(`document.querySelector('[data-task-id][data-draggable="true"]').dataset.taskId`);
 await evaluate(`(()=>{const transfer=new DataTransfer();transfer.setData('text/plain','${taskId}');document.querySelector('[data-status="todo"]').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));})()`);
 await settle();assert.equal((await evaluate(`window.testMove`)).url, `/tasks/${taskId}/status/`);
 await evaluate(`(()=>{const transfer=new DataTransfer();transfer.setData('text/plain','${taskId}');document.querySelector('[data-custom-column]').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));})()`);
 await settle();assert.equal((await evaluate(`window.testMove`)).url, `/projects/${project}/board/tasks/${taskId}/`);
 const feedbackId = await evaluate(`document.querySelector('[data-feedback-id]').dataset.feedbackId`);
 await evaluate(`(()=>{const transfer=new DataTransfer();transfer.setData('text/plain','feedback:${feedbackId}');document.querySelector('[data-custom-column]').dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));})()`);
 await settle();assert.equal((await evaluate(`window.testMove`)).url, `/projects/${project}/board/feedback/${feedbackId}/`);
 await evaluate(`PCC.update=window.originalUpdate`);
 assert.deepEqual(errors,[]);console.log('PASS: saved slide setup, keyboard navigation, pagination, fullscreen, light/dark theme and mobile containment.');
} finally {socket.close();await fetch(`${endpoint}/json/close/${tab.id}`);}
