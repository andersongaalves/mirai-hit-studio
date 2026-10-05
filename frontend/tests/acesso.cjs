const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '..');
const keys = {
    admin: 'mirai.auth.admin.access_token',
    produtor: 'mirai.auth.produtor.access_token',
    cliente: 'mirai.auth.cliente.access_token',
};
const users = {
    admin: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true, cliente_id: null },
    produtor: { id: 2, username: 'produtor', role: 'produtor', is_admin: false, ativo: true, cliente_id: null },
    cliente: { id: 3, username: 'cliente', role: 'cliente', is_admin: false, ativo: true, cliente_id: 8 },
    desconhecido: { id: 4, username: 'desconhecido', role: 'owner', is_admin: false, ativo: true, cliente_id: null },
};

async function staticResponse(route) {
    const url = new URL(route.request().url());
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/acesso') pathname = '/acesso.html';
    if (['/admin', '/produtor', '/cliente'].includes(pathname)) {
        return route.fulfill({ body: '<!doctype html><title>Destino</title>', contentType: 'text/html' });
    }
    const file = path.resolve(root, `.${pathname}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.html': 'text/html',
                '.js': 'text/javascript',
                '.css': 'text/css',
                '.png': 'image/png',
                '.ttf': 'font/ttf',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

async function login(page, username) {
    await page.goto('http://localhost:4173/acesso');
    await page.locator('#username').fill(username);
    await page.locator('#password').fill('synthetic-password');
    await page.locator('#access-login-form').evaluate(form => form.requestSubmit());
}

(async () => {
    const redirects = await fs.readFile(path.join(root, '_redirects'), 'utf8');
    assert.doesNotMatch(redirects, /^\/acesso \/acesso\.html 200$/m);

    const browser = await chromium.launch({
        headless: true,
        channel: process.env.BROWSER_CHANNEL || (process.platform === 'win32' ? 'msedge' : undefined),
    });
    const context = await browser.newContext();
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000' || url.pathname !== '/auth/login') {
            return route.fulfill({ status: 404, body: '' });
        }
        const username = route.request().postDataJSON().username;
        const user = users[username];
        return route.fulfill(user ? {
            json: { access_token: `${username}-token`, token_type: 'bearer', user },
        } : {
            status: 401,
            json: { detail: 'Usuário ou senha incorretos' },
        });
    });

    try {
        for (const [role, destination] of Object.entries({
            admin: '/admin',
            produtor: '/produtor',
            cliente: '/cliente',
        })) {
            await context.clearCookies();
            await page.goto('http://localhost:4173/acesso');
            await page.evaluate(() => localStorage.clear());
            await login(page, role);
            await page.waitForURL(`http://localhost:4173${destination}`);
            const stored = await page.evaluate(keys => Object.fromEntries(
                Object.entries(keys).map(([name, key]) => [name, localStorage.getItem(key)]),
            ), keys);
            assert.equal(stored[role], `${role}-token`);
            assert.equal(Object.values(stored).filter(Boolean).length, 1);
        }

        await page.goto('http://localhost:4173/acesso');
        await page.evaluate(() => localStorage.clear());
        await login(page, 'inexistente');
        await assert.rejects(page.waitForURL(/\/(admin|produtor|cliente)$/, { timeout: 300 }));
        await page.locator('#login-error').waitFor({ state: 'visible' });
        assert.equal(await page.locator('#login-error').textContent(), 'Usuário ou senha incorretos');

        await login(page, 'desconhecido');
        await assert.rejects(page.waitForURL(/\/(admin|produtor|cliente)$/, { timeout: 300 }));
        assert.equal(
            await page.locator('#login-error').textContent(),
            'Esta conta não possui uma área de acesso válida.',
        );
        assert.deepEqual(
            await page.evaluate(keys => Object.values(keys).map(key => localStorage.getItem(key)), keys),
            [null, null, null],
        );

        for (const width of [320, 768, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            await page.goto('http://localhost:4173/acesso');
            assert.equal(await page.locator('#access-login-form').isVisible(), true);
            assert.equal(
                await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
                true,
            );
        }

        assert.deepEqual(errors, []);
        console.log('PASS: centralized login routes each role and fails closed.');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
