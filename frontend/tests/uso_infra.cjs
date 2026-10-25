// Admin "Uso da infraestrutura": bars, limits, unavailable providers and manual refresh.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
const usage = {
    atualizado_em: '2026-10-25T15:00:00Z',
    blocos: [
        { nome: 'Servidor (Render)', status: 'ok', itens: [{ rotulo: 'Memória em uso agora', usado: 471859200, limite: 536870912, unidade: 'bytes' }] },
        { nome: 'Supabase', status: 'ok', itens: [{ rotulo: 'Banco de dados', usado: 52428800, limite: 524288000, unidade: 'bytes' }] },
        { nome: 'Cloudinary', status: 'indisponivel', mensagem: 'O Cloudinary não respondeu agora.' },
        { nome: '<img src=x onerror=alert(1)>', status: 'ok', itens: [{ rotulo: 'Requisições do site (30 dias)', usado: 12345, unidade: 'quantidade', detalhe: '10 ameaças bloqueadas' }], avisos: [] },
    ],
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const calls = [];
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173') {
                const file = url.pathname === '/acesso' ? '/acesso.html' : url.pathname;
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: '' }); }
            }
            if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
            if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'admin-token', user: admin } });
            if (url.pathname === '/auth/me') return route.fulfill({ json: admin });
            if (url.pathname === '/admin/uso') { calls.push(url.search); return route.fulfill({ json: usage }); }
            if (url.pathname.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            if (url.pathname === '/dashboard') return route.fulfill({ json: {
                metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
                pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
                attention: {}, recent_activity: [],
            } });
            return route.fulfill({ json: [] });
        });
        await signIn(page, { next: '/admin.html', username: 'admin' });
        assert.equal(calls.length, 0, 'usage loads only when the section opens');
        await page.locator('.admin-nav__item[data-admin-target="section-uso"]').click();
        const content = page.locator('#uso-content');
        await content.locator('.uso-card').first().waitFor();
        assert.equal(await content.locator('.uso-card').count(), 4);
        const memory = content.locator('.uso-card').first();
        assert.match(await memory.textContent(), /450 MB de 512 MB/);
        assert.equal(await memory.getByRole('meter').getAttribute('aria-valuenow'), '88');
        assert.match(await memory.locator('.uso-bar').getAttribute('class'), /uso-bar--warning/);
        assert.match(await content.textContent(), /O Cloudinary não respondeu agora/);
        assert.equal(await content.locator('img').count(), 0);
        assert.match(await content.textContent(), /<img src=x onerror=alert\(1\)>/);
        assert.match(await content.textContent(), /12\.345/);
        assert.match(await page.locator('#uso-updated').textContent(), /Atualizado em/);
        await page.getByRole('button', { name: 'Atualizar agora' }).click();
        await page.waitForFunction(() => true);
        await page.waitForTimeout(200);
        assert.deepEqual(calls, ['', '?atualizar=true']);
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        assert.deepEqual(errors, []);
        await context.close();
        console.log('PASS: infrastructure usage loads on demand, shows limits, isolates unavailable providers, refreshes and stays safe and responsive.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
