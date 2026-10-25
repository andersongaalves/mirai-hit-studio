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
    if (/^\/(admin|produtor|cliente)(\/|$)/.test(pathname)) {
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
        if (url.origin === 'http://localhost:8000' && url.pathname === '/auth/me') {
            const token = (route.request().headers().authorization || '').replace('Bearer ', '');
            const user = users[token.replace(/-token$/, '')];
            return route.fulfill(user ? { json: { ...user, nome_exibicao: user.username === 'admin' ? 'Equipe Mirai' : null } } : { status: 401, json: {} });
        }
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
        await page.goto('http://localhost:4173/acesso');
        assert.equal(await page.getByLabel('Usuário').getAttribute('placeholder'), 'Seu usuário');
        const passwordToggle = page.locator('[data-password-toggle="password"]');
        assert.equal(await passwordToggle.textContent(), 'Mostrar senha');
        await passwordToggle.click();
        assert.equal(await page.locator('#password').getAttribute('type'), 'text');
        assert.equal(await passwordToggle.getAttribute('aria-pressed'), 'true');
        await passwordToggle.click();
        assert.equal(await page.locator('#password').getAttribute('type'), 'password');
        assert.equal(await passwordToggle.getAttribute('aria-pressed'), 'false');

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

        // AUD6-S02-003: each role returns to its own requested panel; other targets fall back home.
        for (const [role, next, expected] of [
            ['produtor', '/produtor/producoes/3', '/produtor/producoes/3'],
            ['admin', '/admin?secao=financeiro', '/admin'],
            ['admin', '/produtor', '/admin'],
            ['cliente', '//evil.example/cliente', '/cliente'],
            ['cliente', '/cliente/../admin', '/cliente'],
        ]) {
            await page.goto('http://localhost:4173/acesso');
            await page.evaluate(() => localStorage.clear());
            await page.goto(`http://localhost:4173/acesso?next=${encodeURIComponent(next)}`);
            await page.locator('#username').fill(role);
            await page.locator('#password').fill('synthetic-password');
            await Promise.all([
                page.waitForURL(url => url.pathname === expected, { waitUntil: 'commit' }),
                page.locator('#access-login-form').evaluate(form => form.requestSubmit()),
            ]);
            if (expected === '/admin' && next.startsWith('/admin?')) assert.equal(new URL(page.url()).search, '?secao=financeiro');
        }

        // AUD6-S02-013: an existing session offers "Continuar"; the form stays available.
        await page.goto('http://localhost:4173/acesso');
        await page.evaluate(() => { localStorage.clear(); localStorage.setItem('mirai.auth.admin.access_token', 'admin-token'); });
        await page.goto(`http://localhost:4173/acesso?next=${encodeURIComponent('/admin')}`);
        await page.locator('#access-session:not(.hidden)').waitFor();
        assert.equal(await page.locator('#access-session-name').textContent(), 'Equipe Mirai');
        assert.equal(await page.locator('#access-login-form').isVisible(), true);
        await Promise.all([page.waitForURL('http://localhost:4173/admin'), page.locator('#access-continue').click()]);
        await page.goto('http://localhost:4173/acesso');
        await page.evaluate(() => { localStorage.clear(); localStorage.setItem('mirai.auth.produtor.access_token', 'revoked-token'); });
        await page.goto('http://localhost:4173/acesso');
        await page.waitForTimeout(150);
        assert.equal(await page.locator('#access-session').isVisible(), false);

        // An expired session explains why the visitor is back here.
        await page.goto('http://localhost:4173/acesso?next=%2Fcliente&motivo=sessao_expirada');
        assert.match(await page.locator('#access-notice').textContent(), /Sua sessão terminou/);
        await page.goto('http://localhost:4173/acesso?motivo=%3Cimg%3E');
        assert.equal(await page.locator('#access-notice').isVisible(), false);

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
