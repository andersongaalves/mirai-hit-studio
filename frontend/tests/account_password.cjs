// AUD6-S02-004: own password change from the panels, synthetic API only.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const users = {
    produtor: { id: 2, username: 'producer-a', role: 'produtor', is_admin: false, ativo: true, painel_beats: false },
    admin: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true },
};

async function staticResponse(route, url) {
    let file = url.pathname;
    if (/^\/produtor(\/|$)/.test(file)) file = '/portal-produtor.html';
    if (file === '/acesso') file = '/acesso.html';
    const target = path.resolve(root, '.' + decodeURIComponent(file));
    assert.ok(target.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(target), contentType: types[path.extname(target)] || 'application/octet-stream' });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

async function scenario(browser, role, next) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const changes = [];
    const revokes = [];
    let token = `${role}-token-1`;
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route, url);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: token, user: users[role] } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: users[role] });
        if (url.pathname === '/auth/senha') {
            const body = request.postDataJSON();
            changes.push({ body, authorization: request.headers().authorization });
            if (body.senha_atual !== 'old-password') return route.fulfill({ status: 400, json: { detail: 'Senha atual incorreta.' } });
            token = `${role}-token-2`;
            return route.fulfill({ json: { access_token: token, token_type: 'bearer', user: users[role] } });
        }
        if (url.pathname === '/auth/sair-de-todos' && request.method() === 'POST') {
            revokes.push(request.headers().authorization);
            return route.fulfill({ status: 204, body: '' });
        }
        if (url.pathname.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: {}, recent_activity: [],
        } });
        return route.fulfill({ json: [] });
    });
    await signIn(page, { next, username: users[role].username });
    const button = page.getByRole('button', { name: 'Alterar senha' });
    await button.waitFor();
    await button.click();
    const dialog = page.getByRole('dialog', { name: 'Alterar senha' });
    await dialog.waitFor();
    await dialog.getByLabel('Senha atual').fill('old-password');
    await dialog.getByLabel('Nova senha (8 a 72 caracteres)').fill('new-password-1');
    await dialog.getByLabel('Repita a nova senha').fill('new-password-2');
    await dialog.getByRole('button', { name: 'Salvar nova senha' }).click();
    assert.match(await dialog.locator('form').getByRole('status').textContent(), /precisam ser iguais/);
    assert.equal(changes.length, 0);
    await dialog.getByLabel('Senha atual').fill('wrong-password');
    await dialog.getByLabel('Repita a nova senha').fill('new-password-1');
    await dialog.getByRole('button', { name: 'Salvar nova senha' }).click();
    await page.waitForFunction(() => /não confere/.test(document.querySelector('.account-password__status')?.textContent || ''));
    await dialog.getByLabel('Senha atual').fill('old-password');
    await dialog.getByLabel('Nova senha (8 a 72 caracteres)').fill('new-password-1');
    await dialog.getByLabel('Repita a nova senha').fill('new-password-1');
    await dialog.getByRole('button', { name: 'Salvar nova senha' }).click();
    await page.waitForFunction(() => /Senha alterada/.test(document.querySelector('.account-password__status')?.textContent || ''));
    assert.equal(changes.length, 2);
    assert.equal(changes[1].authorization, `Bearer ${role}-token-1`);
    assert.deepEqual(Object.keys(changes[1].body).sort(), ['nova_senha', 'senha_atual']);
    const stored = await page.evaluate(() => Object.values(localStorage).filter(value => /token-\d$/.test(value)));
    assert.ok(stored.includes(`${role}-token-2`), JSON.stringify(stored));
    assert.equal(await page.locator('.account-password__status').textContent(), 'Senha alterada. Os outros aparelhos foram desconectados.');
    // AUD6-S02-006: "Sair de todos os aparelhos" ends this session too.
    page.once('dialog', confirmation => confirmation.dismiss());
    await dialog.getByRole('button', { name: 'Sair de todos os aparelhos' }).click();
    assert.equal(revokes.length, 0);
    page.once('dialog', confirmation => confirmation.accept());
    await expectAccessPage(page, () => dialog.getByRole('button', { name: 'Sair de todos os aparelhos' }).click());
    assert.deepEqual(revokes, [`Bearer ${role}-token-2`]);
    assert.equal(await page.evaluate(() => Object.values(localStorage).filter(value => /token-\d$/.test(value)).length), 0);
    await context.close();
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        await scenario(browser, 'produtor', '/produtor');
        await scenario(browser, 'admin', '/admin.html');
        console.log('PASS: own password change validates, maps errors, renews the current session and never sends extra fields.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
