const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const access = {
    proposta_id: 8,
    cliente_id: 4,
    cliente_nome: 'Cliente Sintético',
    email: 'cliente@example.invalid',
    proposta_status: 'aceita',
    estado: 'sem_acesso',
    usuario_id: null,
    last_sent_at: null,
    expires_at: null,
    send_count: 0,
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/cliente-acessos/validar') {
                    return route.fulfill({ json: { estado: 'valido' } });
                }
                if (url.pathname === '/cliente-acessos/ativar') {
                    return route.fulfill({ json: { activated: true, login_url: '/acesso' } });
                }
                if (url.pathname.endsWith('/acesso-cliente/convidar')) {
                    Object.assign(access, {
                        estado: 'convite_pendente',
                        last_sent_at: '2026-10-05T12:00:00Z',
                        expires_at: '2026-10-07T12:00:00Z',
                        send_count: 1,
                    });
                    return route.fulfill({ json: access });
                }
                if (url.pathname.endsWith('/acesso-cliente')) return route.fulfill({ json: access });
                if (url.pathname === '/auth/me') return route.fulfill({ json: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true, cliente_id: null } });
                return route.fulfill({ json: [] });
            }
            if (url.origin === 'http://localhost:4173') {
                const aliases = { '/ativar': '/ativar.html' };
                const file = path.resolve(root, `.${aliases[url.pathname] || url.pathname}`);
                assert.ok(file.startsWith(root + path.sep));
                try {
                    return route.fulfill({
                        body: await fs.readFile(file),
                        contentType: { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png' }[path.extname(file)] || 'application/octet-stream',
                    });
                } catch { return route.fulfill({ status: 404, body: '' }); }
            }
            return route.fulfill({ status: 200, body: '' });
        });

        await page.goto('http://localhost:4173/ativar?token=synthetic-token-with-sufficient-length-1234');
        await page.waitForSelector('#activation-form:not(.hidden)');
        await page.locator('#activation-username').fill('cliente_portal');
        await page.locator('#activation-password').fill('secure-password');
        await page.locator('#activation-confirm').fill('secure-password');
        await page.locator('#activation-form').getByRole('button', { name: 'Ativar acesso' }).click();
        await page.waitForSelector('#activation-login:not(.hidden)');
        assert.equal(await page.locator('#activation-login').getAttribute('href'), '/acesso');

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            await page.goto('http://localhost:4173/ativar?token=synthetic-token-with-sufficient-length-1234');
            await page.waitForSelector('#activation-form:not(.hidden)');
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
            assert.ok(overflow <= 1, `activation overflow at ${width}px: ${overflow}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: client activation states, credentials form and responsive layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
