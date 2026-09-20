const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const now = '2026-09-13T12:00:00Z';
const users = [
    { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true, created_at: now, updated_at: now },
    { id: 2, username: '<img src=x onerror=alert(1)>', role: 'produtor', is_admin: false, ativo: true, created_at: now, updated_at: now },
    { id: 3, username: 'inativo', role: 'produtor', is_admin: false, ativo: false, created_at: now, updated_at: now },
];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1024, height: 800 } });
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    const errors = [];
    const calls = [];
    let duplicate = false;
    let listFailure = false;
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });
        calls.push(`${request.method()} ${url.pathname}`);
        if (url.pathname === '/auth/login') return route.fulfill({ json: {
            access_token: 'users-token',
            user: users[0],
        } });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 },
            recent_activity: [],
        } });
        if (url.pathname === '/usuarios/produtores') return route.fulfill({ json: users.filter(user => user.ativo) });
        if (url.pathname === '/newsletter/subscribers' || url.pathname === '/newsletter/campaigns') return route.fulfill({ json: [] });
        if (url.pathname === '/usuarios' && request.method() === 'GET') {
            return route.fulfill(listFailure ? { status: 500, json: { detail: 'Falha' } } : { json: users });
        }
        if (url.pathname === '/usuarios' && request.method() === 'POST') {
            if (duplicate) return route.fulfill({ status: 409, json: { detail: 'Nome de usuario ja cadastrado.' } });
            const payload = request.postDataJSON();
            assert.deepEqual(Object.keys(payload).sort(), ['password', 'role', 'username']);
            const created = { id: 4, username: payload.username, role: payload.role, is_admin: payload.role === 'admin', ativo: true, created_at: now, updated_at: now };
            users.push(created);
            return route.fulfill({ status: 201, json: created });
        }
        const reset = url.pathname.match(/^\/usuarios\/(\d+)\/senha$/);
        if (reset) {
            assert.deepEqual(Object.keys(request.postDataJSON()), ['nova_senha']);
            return route.fulfill({ json: users.find(user => user.id === Number(reset[1])) });
        }
        const match = url.pathname.match(/^\/usuarios\/(\d+)$/);
        if (match) {
            const user = users.find(item => item.id === Number(match[1]));
            if (!user) return route.fulfill({ status: 404, json: { detail: 'Usuario nao encontrado.' } });
            if (request.method() === 'GET') return route.fulfill({ json: user });
            Object.assign(user, request.postDataJSON(), { is_admin: request.postDataJSON().role === 'admin', updated_at: now });
            return route.fulfill({ json: user });
        }
        if (['/config', '/servicos', '/projetos/admin', '/orcamentos', '/producoes', '/clientes'].includes(url.pathname)) {
            return route.fulfill({ json: url.pathname === '/config' ? {} : [] });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await page.goto('http://localhost:4173/admin.html');
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('admin-pass');
        await page.getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.waitForSelector('.usuarios-table tbody tr', { state: 'attached' });
        assert.equal(await page.locator('[data-admin-target="section-usuarios"]').isVisible(), true);
        await page.locator('[data-admin-target="section-usuarios"]').click();
        await page.waitForSelector('.usuarios-table tbody tr', { state: 'visible' });
        assert.equal(await page.locator('.usuarios-table tbody tr').count(), 3);
        assert.equal(await page.locator('#usuarios-list img, #usuarios-list script').count(), 0);
        assert.match(await page.locator('#usuarios-list').textContent(), /<img src=x/);

        await page.locator('#usuarios-status-filter').selectOption('inativo');
        assert.equal(await page.locator('.usuarios-table tbody tr').count(), 1);
        await page.locator('#usuarios-role-filter').selectOption('admin');
        assert.equal(await page.locator('#usuarios-list .admin-empty').textContent(), 'Nenhum usuario corresponde aos filtros.');
        await page.locator('#usuarios-clear-filters').click();
        await page.locator('#usuarios-search').fill('img src');
        assert.equal(await page.locator('.usuarios-table tbody tr').count(), 1);
        await page.locator('#usuarios-clear-filters').click();

        const newButton = page.getByRole('button', { name: 'Novo usuário' });
        await newButton.click();
        assert.equal(await page.evaluate(() => document.activeElement?.id), 'usuario-username');
        await page.locator('#usuario-username').fill('novo');
        await page.locator('#usuario-password').fill('secure-password');
        await page.locator('#usuario-save').click();
        await page.waitForFunction(() => document.getElementById('modal-usuario').classList.contains('hidden'));
        assert.equal(users.length, 4);

        const edit = page.locator('.usuarios-table tbody tr').filter({ hasText: 'novo' }).getByRole('button');
        await edit.click();
        await page.locator('#usuario-ativo').uncheck();
        await page.locator('#usuario-save').click();
        await page.waitForFunction(() => document.getElementById('modal-usuario').classList.contains('hidden'));
        assert.equal(users[3].ativo, false);

        await page.getByRole('button', { name: 'Abrir usuario inativo', exact: true }).click();
        await page.locator('#usuario-new-password').fill('another-password');
        await page.locator('#usuario-password-reset').click();
        await page.waitForFunction(() => document.getElementById('usuario-new-password')?.value === '');
        assert.equal(await page.locator('#usuario-new-password').inputValue(), '');
        await page.keyboard.press('Escape');

        duplicate = true;
        await newButton.click();
        await page.locator('#usuario-username').fill('admin');
        await page.locator('#usuario-password').fill('secure-password');
        await page.locator('#usuario-save').click();
        await page.waitForSelector('.notification.error');
        assert.equal(await page.locator('#modal-usuario').isVisible(), true);
        assert.equal(await page.locator('#usuario-username').inputValue(), 'admin');
        await page.keyboard.press('Escape');
        assert.equal(await newButton.evaluate(element => element === document.activeElement), true);

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.locator('.usuarios-mobile-view').isVisible(), width <= 768);
            assert.equal(await page.locator('.usuarios-table-view').isVisible(), width > 768);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }

        listFailure = true;
        await page.evaluate(async () => (await import('/js/admin/usuarios/usuarios.js')).carregarUsuarios());
        await page.waitForSelector('#usuarios-list .admin-error');
        await page.evaluate(() => window.fazerLogout());
        assert.equal(await page.locator('[data-admin-target="section-usuarios"]').isVisible(), false);
        assert.equal(await page.locator('#usuarios-list').textContent(), '');
        assert.ok(calls.includes('PATCH /usuarios/3/senha'));
        assert.deepEqual(errors, []);
        console.log('PASS: users CRUD, filters, roles, status, password reset, modal, responsive UI, logout and XSS safety.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
