// Pengujian Docs tanpa menulis data proyek. Node 22+ dan sesi Chrome yang sudah masuk.
// PCC_TEST_URL=http://127.0.0.1:8013 PCC_CDP_URL=http://127.0.0.1:9223
// PCC_TEST_SCREENSHOTS=/tmp/scope-docs-qa node tests/browser/documentation.mjs
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const origin = process.env.PCC_TEST_URL || 'http://127.0.0.1:8013';
const endpoint = process.env.PCC_CDP_URL || 'http://127.0.0.1:9223';
const screenshots = process.env.PCC_TEST_SCREENSHOTS;
const tab = await (await fetch(`${endpoint}/json/new?about:blank`, { method: 'PUT' })).json();
const socket = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise(resolve => socket.addEventListener('open', resolve, { once: true }));
let sequence = 0;
const pending = new Map(), errors = [], failures = [];
socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    if (message.id) {
        const request = pending.get(message.id); pending.delete(message.id);
        if (message.error) request.reject(message.error); else request.resolve(message.result);
    } else if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    else if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) failures.push(message.params.response.url);
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
const settle = () => new Promise(resolve => setTimeout(resolve, 350));
const navigate = async path => {
    await call('Page.navigate', { url: origin + path });
    for (let attempt = 0; attempt < 40; attempt++) {
        await settle();
        if (await evaluate(`document.readyState === 'complete' && location.pathname === ${JSON.stringify(path.split('?')[0])}`)) break;
    }
    assert.ok(await evaluate(`document.readyState === 'complete' && location.pathname === ${JSON.stringify(path.split('?')[0])}`), `Navigation failed: ${path}`);
    await evaluate('document.fonts.ready');
};
const viewport = (width, height) => call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 768 });
const shot = async name => {
    if (!screenshots) return;
    await mkdir(screenshots, { recursive: true });
    const result = await call('Page.captureScreenshot', { format: 'png' });
    await writeFile(join(screenshots, name + '.png'), Buffer.from(result.data, 'base64'));
};
const contained = async () => assert.ok(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Page overflows viewport');
try {
    await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable');
    await viewport(1440, 1000);
    await navigate('/auth/settings/');
    assert.ok(await evaluate(`!!document.querySelector('.settings-sidebar .project-nav-item[aria-current="page"][href="/auth/settings/"]')`));
    await evaluate(`document.querySelector('.settings-sidebar a[href="/auth/settings/docs/"]').click()`);
    await settle();
    assert.equal(await evaluate('location.pathname'), '/auth/settings/docs/');
    assert.equal(await evaluate('document.documentElement.lang'), 'id');
    assert.equal(await evaluate(`document.querySelectorAll('.docs-nav-group a').length`), 18);
    assert.ok(await evaluate(`document.querySelector('.settings-sidebar').getBoundingClientRect().left > 0 && getComputedStyle(document.querySelector('.settings-sidebar')).position === 'fixed'`));
    await contained(); await shot('docs-desktop');
    await navigate('/auth/settings/docs/progress-proyek/');
    assert.equal(await evaluate(`document.querySelector('[data-demo-actual]').textContent`), '35');
    await evaluate(`document.querySelector('#demo-build').focus()`);
    await call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 });
    await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39 });
    assert.equal(await evaluate(`document.querySelector('[data-demo-actual]').textContent`), '38,75');
    assert.equal(await evaluate(`document.querySelector('[data-demo-variance]').textContent`), '−21,25');
    await evaluate(`document.querySelector('#demo-build').value='100'; document.querySelector('#demo-build').dispatchEvent(new Event('input', {bubbles:true}))`);
    assert.equal(await evaluate(`document.querySelector('[data-demo-actual]').textContent`), '95');
    assert.equal(await evaluate(`document.querySelector('[data-demo-variance]').textContent`), '+35');
    await evaluate(`document.querySelector('[data-demo-reset]').click()`);
    assert.equal(await evaluate(`document.querySelector('[data-demo-actual]').textContent`), '35');
    await evaluate(`document.querySelector('[data-docs-calculator]').scrollIntoView({block:'center'})`);
    await shot('docs-progress');
    await evaluate(`ScopeTheme.set('dark')`); await shot('docs-dark');
    await call('Emulation.setEmulatedMedia', { media: 'print' });
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.settings-sidebar')).display`), 'none');
    assert.equal(await evaluate(`getComputedStyle(document.querySelector('.workspace-body')).marginLeft`), '0px');
    assert.ok(await evaluate(`getComputedStyle(document.documentElement).getPropertyValue('--ink').trim() === '#16150f'`));
    await shot('docs-print');
    await call('Emulation.setEmulatedMedia', { media: '' });
    await evaluate(`ScopeTheme.set('light')`);
    await navigate('/auth/settings/docs/');
    await evaluate(`document.querySelector('#docs-query').value='10 MB';document.querySelector('.docs-search').requestSubmit()`); await settle();
    assert.ok(await evaluate(`!!document.querySelector('.docs-result[href="/auth/settings/docs/komentar-lampiran/"]')`));
    await shot('docs-search');
    await navigate('/auth/settings/docs/?q=qzxmissing');
    assert.ok(await evaluate(`!!document.querySelector('.docs-empty')`));
    await navigate('/auth/settings/docs/');
    const paths = await evaluate(`[...document.querySelectorAll('.docs-nav-group a')].map(a=>new URL(a.href).pathname)`);
    await viewport(390, 844);
    await navigate('/auth/settings/docs/');
    assert.equal(await evaluate(`document.querySelector('.docs-menu').open`), false);
    await evaluate(`document.querySelector('.docs-menu summary').click()`);
    assert.equal(await evaluate(`document.querySelector('.docs-menu').open`), true);
    await evaluate(`document.querySelector('.docs-menu summary').click()`);
    await shot('docs-mobile');
    for (const path of paths) { await navigate(path); await contained(); }
    await navigate('/auth/settings/docs/progress-proyek/');
    await evaluate(`document.querySelector('[data-docs-calculator]').scrollIntoView({block:'center'})`);
    await shot('docs-progress-mobile');
    await navigate('/auth/settings/'); await contained();
    await call('Emulation.setScriptExecutionDisabled', { value: true });
    await navigate('/auth/settings/docs/?q=baseline');
    const noScript = await (await fetch(`${origin}/auth/settings/docs/?q=baseline`, { headers: { Cookie: (await call('Network.getCookies', { urls: [origin] })).cookies.map(c => `${c.name}=${c.value}`).join('; ') } })).text();
    assert.ok(noScript.includes('class="docs-result"'));
    await call('Emulation.setScriptExecutionDisabled', { value: false });
    assert.deepEqual(errors, []); assert.deepEqual(failures, []);
    // Cetak PDF dilakukan terakhir: Chrome dapat menahan lapisan fixed yang tersembunyi
    // setelah printToPDF sehingga tangkapan layar berikutnya kehilangan sidebar.
    if (screenshots) {
        await viewport(1440, 1000);
        await navigate('/auth/settings/docs/progress-proyek/');
        const pdf = await call('Page.printToPDF', { printBackground: true, preferCSSPageSize: true, paperWidth: 8.27, paperHeight: 11.69 });
        await writeFile(join(screenshots, 'panduan-progres.pdf'), Buffer.from(pdf.data, 'base64'));
    }
    console.log('PASS: Settings submenu, 18 mobile guides, search, keyboard calculator, reset, dark theme, print and server-rendered search.');
} finally {
    await call('Emulation.setScriptExecutionDisabled', { value: false }).catch(() => {});
    socket.close();
    await fetch(`${endpoint}/json/close/${tab.id}`);
}
