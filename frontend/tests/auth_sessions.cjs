const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const keys = {
    admin: 'mirai.auth.admin.access_token',
    produtor: 'mirai.auth.produtor.access_token',
    cliente: 'mirai.auth.cliente.access_token',
};
const users = {
    admin: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true, cliente_id: null },
    produtor: { id: 2, username: 'producer', role: 'produtor', is_admin: false, ativo: true, cliente_id: null },
    cliente: { id: 3, username: 'client', role: 'cliente', is_admin: false, ativo: true, cliente_id: 8 },
};
const tokens = new Map([
    ['admin-token', users.admin],
    ['producer-token', users.produtor],
    ['client-token', users.cliente],
    ['legacy-producer-token', users.produtor],
]);

const harness = `<!doctype html><html><body>
<section id="login-panel"></section>
<main id="admin-area" class="hidden"><div data-admin-only></div></main>
<script type="module">
window.Auth = await import('/js/admin/auth.js');
window.restoreResult = await window.Auth.restaurarSessao();
window.authReady = true;
</script></body></html>`;

const accessStub = '<!doctype html><html><body><h1>Acesso</h1></body></html>';

async function staticResponse(route) {
    const url = new URL(route.request().url());
    if (url.pathname === '/acesso') return route.fulfill({ body: accessStub, contentType: 'text/html' });
    if (/^\/(admin|produtor|cliente)(\/|$)/.test(url.pathname)) {
        return route.fulfill({ body: harness, contentType: 'text/html' });
    }
    const file = path.resolve(root, `.${decodeURIComponent(url.pathname)}`);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

async function open(page, route) {
    await page.goto(`http://localhost:4173${route}`);
    await page.waitForFunction(() => window.authReady === true);
}

const sessions = {
    admin: { key: keys.admin, token: 'admin-token', route: '/admin' },
    producer: { key: keys.produtor, token: 'producer-token', route: '/produtor' },
    client: { key: keys.cliente, token: 'client-token', route: '/cliente' },
};

// AUD6-S02-003: panels have no login form. /acesso stores the token (covered by
// acesso.cjs); here the stored token is restored when the panel opens.
async function login(page, username) {
    const session = sessions[username];
    await page.evaluate(({ key, token }) => localStorage.setItem(key, token), session);
    await open(page, session.route);
    return page.evaluate(() => window.restoreResult);
}

async function expectAccess(page, next, reason = null) {
    await page.waitForURL(url => url.pathname === '/acesso');
    const params = new URL(page.url()).searchParams;
    assert.equal(params.get('next'), next);
    assert.equal(params.get('motivo'), reason);
}

(async () => {
    const launchOptions = { headless: true };
    if (process.env.BROWSER_CHANNEL) launchOptions.channel = process.env.BROWSER_CHANNEL;
    else if (process.platform === 'win32') launchOptions.channel = 'msedge';
    const browser = await chromium.launch(launchOptions);
    const context = await browser.newContext();
    const admin = await context.newPage();
    const producer = await context.newPage();
    const client = await context.newPage();
    const errors = [];
    for (const page of [admin, producer, client]) page.on('pageerror', error => errors.push(error.message));

    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404, body: '' });
        if (url.pathname === '/auth/login') {
            const username = request.postDataJSON().username;
            const user = Object.values(users).find(item => item.username === username);
            const token = username === 'admin' ? 'admin-token' : username === 'producer' ? 'producer-token' : 'client-token';
            return route.fulfill(user ? { json: { access_token: token, token_type: 'bearer', user } } : { status: 401, json: { detail: 'Inválido' } });
        }
        if (url.pathname === '/auth/me') {
            const token = (request.headers().authorization || '').replace('Bearer ', '');
            const user = tokens.get(token);
            return route.fulfill(user?.ativo ? { json: user } : { status: 401, json: { detail: 'Sessão inválida.' } });
        }
        if (url.pathname === '/forbidden') return route.fulfill({ status: 403, json: { detail: 'Negado' } });
        if (url.pathname === '/expired') return route.fulfill({ status: 401, json: { detail: 'Expirado' } });
        return route.fulfill({ json: [] });
    });

    try {
        await open(admin, '/admin');
        await open(producer, '/produtor');
        await open(client, '/cliente');
        assert.equal(await login(admin, 'admin'), true);
        assert.equal(await login(producer, 'producer'), true);
        assert.equal(await login(client, 'client'), true);

        const simultaneous = await admin.evaluate(keys => Object.fromEntries(
            Object.entries(keys).map(([name, key]) => [name, localStorage.getItem(key)]),
        ), keys);
        assert.deepEqual(simultaneous, { admin: 'admin-token', produtor: 'producer-token', cliente: 'client-token' });

        await producer.evaluate(() => window.Auth.logout());
        await expectAccess(producer, '/produtor');
        assert.equal(await admin.evaluate(key => localStorage.getItem(key), keys.admin), 'admin-token');
        assert.equal(await client.evaluate(key => localStorage.getItem(key), keys.cliente), 'client-token');

        assert.equal(await login(producer, 'producer'), true);
        const producerTab = await context.newPage();
        await open(producerTab, '/produtor/producoes/42');
        assert.equal(await producerTab.evaluate(() => window.restoreResult), true);
        await producer.evaluate(() => window.Auth.logout());
        await expectAccess(producerTab, '/produtor/producoes/42');
        // The cross-tab scenario is complete; do not let this tab restore later legacy fixtures.
        await producerTab.close();

        assert.equal(await login(producer, 'producer'), true);
        const forbiddenStatus = await producer.evaluate(async () => (
            await window.Auth.authFetch('/forbidden')
        ).status);
        assert.equal(forbiddenStatus, 403);
        assert.equal(await producer.evaluate(() => window.Auth.isAuthenticated()), true);
        await producer.evaluate(() => window.Auth.authFetch('/expired').catch(() => null)).catch(() => null);
        await expectAccess(producer, '/produtor', 'sessao_expirada');
        assert.equal(await producer.evaluate(key => localStorage.getItem(key), keys.produtor), null);
        assert.equal(await admin.evaluate(() => window.Auth.isAuthenticated()), true);
        assert.equal(await client.evaluate(() => window.Auth.isAuthenticated()), true);

        await admin.evaluate(() => window.Auth.logout());
        await expectAccess(admin, '/admin');
        await admin.evaluate(token => localStorage.setItem('access_token', token), 'legacy-producer-token');
        await open(admin, '/admin');
        assert.equal(await admin.evaluate(() => window.restoreResult), false);
        assert.equal(await admin.evaluate(key => localStorage.getItem(key), keys.admin), null);
        assert.equal(await admin.evaluate(() => localStorage.getItem('access_token')), 'legacy-producer-token');
        await open(producer, '/produtor/producoes/7');
        assert.equal(await producer.evaluate(() => window.restoreResult), true);
        assert.equal(await producer.evaluate(key => localStorage.getItem(key), keys.produtor), 'legacy-producer-token');
        assert.equal(await producer.evaluate(() => localStorage.getItem('access_token')), null);

        users.produtor.role = 'cliente';
        users.produtor.cliente_id = 9;
        await producer.goto('http://localhost:4173/produtor');
        await expectAccess(producer, '/produtor');
        assert.equal(await producer.evaluate(key => localStorage.getItem(key), keys.produtor), null);

        assert.deepEqual(errors, []);
        console.log('PASS: isolated admin, producer and client sessions; refresh, tabs, logout and 401 return to /acesso, 403 and legacy migration.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
