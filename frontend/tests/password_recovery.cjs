const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const generic = 'Se existir uma conta elegível para este e-mail, enviaremos instruções para redefinir a senha.';
const token = 'synthetic-recovery-token-with-enough-entropy-1234567890';

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const aliases = {
        '/acesso': '/acesso.html',
        '/recuperar-senha': '/recuperar-senha.html',
        '/redefinir-senha': '/redefinir-senha.html',
    };
    const pathname = aliases[url.pathname] || url.pathname;
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
                '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const launchOptions = { headless: true };
    if (process.env.BROWSER_CHANNEL) launchOptions.channel = process.env.BROWSER_CHANNEL;
    else if (process.platform === 'win32') launchOptions.channel = 'msedge';
    const browser = await chromium.launch(launchOptions);
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404, body: '' });
        if (url.pathname === '/auth/password-recovery') {
            return route.fulfill({ status: 202, json: { accepted: true, message: generic } });
        }
        if (url.pathname === '/auth/password-recovery/reset') {
            return route.fulfill({ json: { reset: true, login_url: '/acesso' } });
        }
        return route.fulfill({ status: 404, json: { detail: 'not found' } });
    });

    try {
        await page.goto('http://localhost:4173/recuperar-senha');
        await page.getByLabel('E-mail').fill('client@example.com');
        await page.getByRole('button', { name: 'Enviar instruções' }).click();
        await assert.doesNotReject(() => page.getByText(generic).waitFor());

        await page.evaluate(() => {
            localStorage.setItem('mirai.auth.admin.access_token', 'admin-token');
            localStorage.setItem('mirai.auth.produtor.access_token', 'producer-token');
            localStorage.setItem('mirai.auth.cliente.access_token', 'client-token');
        });
        await page.goto(`http://localhost:4173/redefinir-senha?token=${token}`);
        await page.getByLabel('Nova senha', { exact: true }).fill('new-secure-password');
        await page.getByLabel('Confirmar nova senha').fill('new-secure-password');
        await page.getByRole('button', { name: 'Redefinir senha' }).click();
        await assert.doesNotReject(() => page.getByText('Senha redefinida com sucesso').waitFor());
        assert.equal(await page.getByRole('link', { name: 'Entrar na sua conta' }).getAttribute('href'), '/acesso');
        const storage = await page.evaluate(() => ({
            admin: localStorage.getItem('mirai.auth.admin.access_token'),
            producer: localStorage.getItem('mirai.auth.produtor.access_token'),
            client: localStorage.getItem('mirai.auth.cliente.access_token'),
        }));
        assert.deepEqual(storage, { admin: 'admin-token', producer: 'producer-token', client: null });

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            for (const route of ['/acesso', '/recuperar-senha', `/redefinir-senha?token=${token}`]) {
                await page.goto(`http://localhost:4173${route}`);
                const dimensions = await page.evaluate(() => ({
                    viewport: document.documentElement.clientWidth,
                    content: document.documentElement.scrollWidth,
                }));
                assert.ok(dimensions.content <= dimensions.viewport, `${route} overflows at ${width}px`);
            }
        }
        assert.deepEqual(errors, []);
        console.log('PASSWORD_RECOVERY_UI_PASS');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
