// AUD6-S09-006: Admin global search — grouped results, safe text, opens the section filtered.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
const now = new Date().toISOString();
const results = {
    termo: 'ana',
    grupos: [
        { tipo: 'clientes', rotulo: 'Clientes', secao: 'section-clientes', itens: [
            { id: 1, titulo: 'Ana Souza', detalhe: 'ana@example.test', filtro: 'Ana Souza' },
        ] },
        { tipo: 'orcamentos', rotulo: 'Orçamentos', secao: 'section-orcamentos', itens: [
            { id: 7, titulo: 'Orçamento #7 · <img src=x onerror=alert(1)>', detalhe: 'Mixagem', filtro: 'Ana Souza' },
        ] },
    ],
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        const searches = [];
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
            if (url.pathname === '/admin/busca') {
                searches.push(url.searchParams.get('q'));
                if (url.searchParams.get('q') === 'falha') return route.fulfill({ status: 503, json: { detail: 'down' } });
                if (url.searchParams.get('q') === 'zzz') return route.fulfill({ json: { termo: 'zzz', grupos: [] } });
                return route.fulfill({ json: results });
            }
            if (url.pathname === '/clientes') return route.fulfill({ json: [
                { id: 1, nome: 'Ana Souza', email: 'ana@example.test', telefone: null, ativo: true, is_test: false, created_at: now, updated_at: now },
                { id: 2, nome: 'Bruno Lima', email: 'bruno@example.test', telefone: null, ativo: true, is_test: false, created_at: now, updated_at: now },
            ] });
            if (url.pathname.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            if (url.pathname === '/dashboard') return route.fulfill({ json: {
                metrics: { clientes_ativos: 0 }, pipeline: {}, attention: {}, recent_activity: [],
            } });
            return route.fulfill({ json: [] });
        });
        await signIn(page, { next: '/admin.html', username: 'admin' });
        const box = page.getByRole('searchbox', { name: 'Buscar no painel' });
        await box.waitFor();
        await box.fill('a');
        await page.waitForTimeout(450);
        assert.deepEqual(searches, [], 'one letter does not search');
        await box.fill('an');
        await box.fill('ana');
        const panel = page.getByRole('region', { name: 'Resultados da busca' });
        await panel.getByRole('button', { name: /Ana Souza/ }).waitFor();
        assert.deepEqual(searches, ['ana'], 'typing is debounced into one request');
        assert.equal(await box.getAttribute('aria-expanded'), 'true');
        assert.deepEqual(await panel.locator('h2').allTextContents(), ['Clientes', 'Orçamentos']);
        assert.equal(await panel.locator('img').count(), 0);
        assert.match(await panel.textContent(), /<img src=x onerror=alert\(1\)>/);
        if (process.env.VISUAL_OUTPUT) await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, 'admin-search-1280.png') });
        await page.keyboard.press('Escape');
        assert.equal(await panel.isVisible(), false);
        await box.press('Enter');
        await panel.getByRole('button', { name: /Ana Souza/ }).click();
        await page.locator('#section-clientes').waitFor({ state: 'visible' });
        await page.waitForFunction(() => document.getElementById('clientes-search')?.value === 'Ana Souza');
        await box.fill('zzz');
        await page.waitForFunction(() => /Nada encontrado para “zzz”/.test(document.getElementById('admin-search-results')?.textContent || ''));
        await box.fill('falha');
        await page.waitForFunction(() => /Não foi possível buscar agora/.test(document.getElementById('admin-search-results')?.textContent || ''));
        await page.mouse.click(1200, 850);
        assert.equal(await panel.isVisible(), false);
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        assert.deepEqual(errors, []);
        await context.close();
        console.log('PASS: admin search debounces, groups results safely, opens the section filtered and handles empty and failed searches.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
