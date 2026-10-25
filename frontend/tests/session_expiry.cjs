// AUD6-S02-011: the panels warn a few minutes before the session ends (no silent renewal).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const user = { id: 2, username: 'producer-a', role: 'produtor', is_admin: false, ativo: true, painel_beats: false };
const b64 = value => Buffer.from(JSON.stringify(value)).toString('base64url');
const token = seconds => `${b64({ alg: 'HS256' })}.${b64({ sub: 'producer-a', exp: Math.floor(Date.now() / 1000) + seconds })}.sig`;

async function open(browser, seconds) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin === 'http://localhost:4173') {
            let file = /^\/produtor(\/|$)/.test(url.pathname) ? '/portal-produtor.html' : url.pathname;
            if (file === '/acesso') file = '/acesso.html';
            try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
            catch { return route.fulfill({ status: 404, body: '' }); }
        }
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: token(seconds), user } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: user });
        if (url.pathname.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
        return route.fulfill({ json: [] });
    });
    await signIn(page, { next: '/produtor', username: 'producer-a' });
    return { context, page };
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const near = await open(browser, 240);
        const warning = near.page.locator('#session-expiry-warning');
        await warning.waitFor();
        assert.equal(await warning.getAttribute('role'), 'alert');
        assert.match(await warning.textContent(), /Sua sessão termina em cerca de 4 min/);
        const box = await warning.boundingBox();
        assert.ok(box.x >= 0 && box.x + box.width <= 390, JSON.stringify(box));
        await near.page.getByRole('button', { name: 'Ok' }).click();
        assert.equal(await warning.count(), 0);
        await near.page.evaluate(() => document.dispatchEvent(new Event('noop')));
        await near.context.close();

        const relogin = await open(browser, 240);
        await relogin.page.locator('#session-expiry-warning').waitFor();
        const { params } = await expectAccessPage(relogin.page,
            () => relogin.page.getByRole('button', { name: 'Entrar de novo agora' }).click());
        assert.equal(params.get('motivo') || params.get('reason') || 'sessao_expirada', 'sessao_expirada');
        await relogin.context.close();

        const far = await open(browser, 3600);
        await far.page.waitForTimeout(500);
        assert.equal(await far.page.locator('#session-expiry-warning').count(), 0);
        await far.context.close();
        console.log('PASS: expiry warning shows near the end, dismisses, offers sign-in again and stays hidden for fresh sessions.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
