const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ reducedMotion: 'reduce' });
        let sessions = 0, mode = 'reply', sent = [], history = [], state = 'open', delay = 0;
        const errors = [];
        await context.addInitScript(() => localStorage.setItem('mirai.analytics_consent.v1', 'rejected'));
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname.endsWith('/session')) {
                    sessions++; history = []; state = 'open';
                    return route.fulfill({ json: { session_token: String(sessions).padStart(43, 'a'), expires_at: '2099-01-01T00:00:00Z' } });
                }
                if (url.pathname.endsWith('/history')) return route.fulfill({ json: { status: state, messages: history } });
                if (url.pathname.endsWith('/messages')) {
                    const data = route.request().postDataJSON();
                    sent.push(data);
                    if (delay) await new Promise(resolve => setTimeout(resolve, delay));
                    if (mode === 'error') return route.fulfill({ status: 503, json: { detail: 'INTERNAL PRIVATE ERROR' } });
                    state = mode === 'handoff' ? 'waiting_human' : 'open';
                    const text = '<img src=x onerror=alert(1)> javascript:alert(1) <script>bad()</script>';
                    if (!history.some(row => row.message_id === data.message_id)) {
                        history.push({ role: 'user', text: data.message, message_id: data.message_id });
                        if (mode !== 'handoff') history.push({ role: 'assistant', text, message_id: data.message_id });
                    }
                    if (mode === 'lost') return route.fulfill({ status: 503 });
                    return route.fulfill({ json: { action: mode, status: state, text: mode === 'reply' ? text : null } });
                }
                return route.fulfill({ json: [] });
            }
            if (url.origin === 'http://localhost:4173') {
                if (url.pathname === '/fixture') return route.fulfill({ contentType: 'text/html', body: `<!doctype html><html lang="pt-BR"><head><meta name="viewport" content="width=device-width"><meta name="mirai-ga-id" content="G-TEST123"><link rel="stylesheet" href="/css/main.css"></head><body><main><h1>Mirai</h1><button id="outside">Fora</button></main><script type="module">import { initSiteChat } from '/js/chat/chat.js'; initSiteChat(); initSiteChat();</script></body></html>` });
                const file = path.resolve(root, '.' + url.pathname);
                assert.ok(file.startsWith(root + path.sep));
                try { return route.fulfill({ body: await fs.readFile(file), contentType: ({ '.js': 'text/javascript', '.css': 'text/css' })[path.extname(file)] || 'text/html' }); }
                catch { return route.fulfill({ status: 404 }); }
            }
            return route.fulfill({ body: '' });
        });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        await page.goto('http://localhost:4173/fixture');
        const launcher = page.locator('#site-chat-launcher');
        assert.equal(await launcher.count(), 1);
        assert.equal(sessions, 0);
        await launcher.click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sessions, 1);
        assert.equal(await launcher.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'site-chat-title');
        for (let i = 0; i < 8; i++) {
            await page.keyboard.press(i % 2 ? 'Shift+Tab' : 'Tab');
            assert.ok(await page.evaluate(() => document.querySelector('#site-chat').contains(document.activeElement)));
        }
        await page.keyboard.press('Escape');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'site-chat-launcher');
        await launcher.click();
        const input = page.locator('#site-chat-message');
        await input.fill('Unicode: produção 音楽');
        await input.press('Shift+Enter');
        assert.ok((await input.inputValue()).includes('\n'));
        delay = 100;
        await input.press('Enter');
        await page.keyboard.press('Enter');
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sent.length, 1);
        assert.equal(await page.locator('.site-chat-message').count(), 2);
        assert.equal(await page.locator('.site-chat-messages img,.site-chat-messages script,.site-chat-messages a').count(), 0);
        assert.deepEqual(Object.keys(sent[0]).sort(), ['message', 'message_id']);
        assert.equal(await page.evaluate(() => window.dataLayer?.length || 0), 0);
        mode = 'error';
        await input.fill('Mensagem para retry');
        await input.press('Enter');
        await page.getByRole('button', { name: 'Tentar novamente' }).waitFor();
        assert.ok(!(await page.locator('#site-chat').innerText()).includes('PRIVATE'));
        const retryId = sent.at(-1).message_id;
        mode = 'reply';
        await page.getByRole('button', { name: 'Tentar novamente' }).click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sent.at(-1).message_id, retryId);
        await page.reload();
        await launcher.click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sessions, 1);
        assert.equal(await page.locator('.site-chat-message').count(), 4);
        mode = 'lost';
        await input.fill('Resposta perdida na conexao');
        await input.press('Enter');
        await page.getByRole('button', { name: 'Tentar novamente' }).waitFor();
        const beforeReload = sent.length;
        await page.reload();
        await launcher.click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sent.length, beforeReload);
        assert.equal(await page.locator('.site-chat-message').count(), 6);
        await page.evaluate(async () => {
            const analytics = await import('/js/analytics.js');
            localStorage.setItem('mirai.analytics_consent.v1', 'accepted');
            analytics.track('ai_chat_message', { email: 'private@example.invalid', token: 'secret', message: 'private' });
        });
        const event = await page.evaluate(() => window.dataLayer.find(entry => entry[0] === 'event' && entry[1] === 'ai_chat_message'));
        assert.deepEqual(event[2], {});
        mode = 'handoff';
        await input.fill('Quero falar com uma pessoa');
        await input.press('Enter');
        await page.waitForFunction(() => document.querySelector('.site-chat-status').textContent.includes('não é notificada'));
        assert.ok(await input.isDisabled());
        await page.getByRole('button', { name: 'Nova conversa' }).click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        assert.equal(sessions, 2);
        state = 'closed';
        await page.reload();
        await launcher.click();
        await page.waitForFunction(() => document.querySelector('.site-chat-status').textContent.includes('encerrada'));
        assert.ok(await input.isDisabled());
        await page.getByRole('button', { name: 'Nova conversa' }).click();
        await page.waitForFunction(() => !document.querySelector('#site-chat-message').disabled);
        for (const width of [320, 360, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 700 });
            const bounds = await page.locator('#site-chat').boundingBox();
            assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width + 1, JSON.stringify(bounds));
            assert.ok(bounds.y >= 0 && bounds.y + bounds.height <= 701);
            assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        }
        await page.setViewportSize({ width: 390, height: 400 });
        await page.screenshot({ path: path.join(process.env.TEMP || '.', 'mirai-chat-mobile.png') });
        assert.ok((await input.boundingBox()).y < 400, JSON.stringify(await page.locator('#site-chat').evaluate(node => [...node.children].map(child => ({tag: child.tagName, height: child.getBoundingClientRect().height, y: child.getBoundingClientRect().y})))));
        const sendBounds = await page.getByRole('button', { name: 'Enviar', exact: true }).boundingBox();
        assert.ok(sendBounds.y + sendBounds.height <= 400, JSON.stringify(sendBounds));
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.screenshot({ path: path.join(process.env.TEMP || '.', 'mirai-chat-desktop.png') });
        await page.getByRole('button', { name: 'Fechar', exact: true }).click();
        assert.equal(await launcher.getAttribute('aria-expanded'), 'false');
        await page.setViewportSize({ width: 320, height: 700 });
        await page.evaluate(async () => {
            localStorage.removeItem('mirai.analytics_consent.v1');
            (await import('/js/analytics.js')).initAnalytics();
        });
        await page.locator('#analytics-consent-dialog').waitFor();
        await page.screenshot({ path: path.join(process.env.TEMP || '.', 'mirai-chat-consent.png') });
        const launchBounds = await launcher.boundingBox();
        const consentBounds = await page.locator('#analytics-consent-dialog').boundingBox();
        assert.ok(launchBounds.y + launchBounds.height <= consentBounds.y);
        await launcher.click();
        assert.ok(await page.locator('#site-chat').isVisible());
        assert.deepEqual(errors, []);
        console.log('Site chat: session, retry, XSS, consent, handoff, keyboard and 8 widths passed.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
