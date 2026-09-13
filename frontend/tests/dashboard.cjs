const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const dashboard = {
    metrics: { clientes_ativos: 4, orcamentos_abertos: 3, propostas_aguardando_decisao: 2, producoes_ativas: 5, producoes_atrasadas: 1 },
    pipeline: { orcamentos_abertos: 3, propostas_enviadas: 2, propostas_aprovadas: 1, producoes_ativas: 5 },
    attention: { producoes_atrasadas: 1, propostas_aguardando_decisao: 2 },
    recent_activity: [{ tipo: 'proposta_enviada', titulo: '<img src=x onerror=alert(1)>', data: '2026-09-13T12:00:00Z', secao: 'section-orcamentos' }],
};

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
    const errors = [];
    let dashboardFailure = false;
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'dashboard-token' } });
        if (url.pathname === '/dashboard') return route.fulfill(dashboardFailure
            ? { status: 500, json: { detail: 'Falha controlada' } }
            : { json: dashboard });
        if (['/config', '/servicos', '/projetos', '/orcamentos', '/producoes', '/clientes', '/usuarios'].includes(url.pathname)) {
            return route.fulfill({ json: url.pathname === '/config' ? {} : [] });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });
    try {
        await page.goto('http://localhost:4173/admin.html');
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.waitForSelector('.dashboard-kpi');
        assert.equal(await page.locator('.dashboard-kpi').count(), 5);
        assert.match(await page.locator('#dashboard-metrics').textContent(), /4/);
        assert.equal(await page.locator('#dashboard-pipeline li').count(), 4);
        assert.equal(await page.locator('#dashboard-activity img, #dashboard-activity script').count(), 0);
        assert.match(await page.locator('#dashboard-activity').textContent(), /<img src=x/);
        await page.locator('#dashboard-attention').getByRole('button', { name: 'Ver producoes' }).click();
        assert.equal(await page.locator('#section-producoes').isVisible(), true);

        dashboard.metrics = { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 };
        dashboard.pipeline = { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 };
        dashboard.attention = { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 };
        dashboard.recent_activity = [];
        await page.evaluate(() => window.mostrarDashboard());
        await page.waitForFunction(() => document.querySelector('#dashboard-metrics')?.textContent.includes('0'));
        assert.equal(await page.locator('.admin-success').textContent(), 'Nenhuma acao pendente no momento.');
        assert.equal(await page.locator('#dashboard-activity .admin-empty').textContent(), 'Ainda nao ha atividade recente.');

        dashboardFailure = true;
        await page.evaluate(() => window.mostrarDashboard());
        await page.waitForSelector('#dashboard-content .admin-error');
        assert.equal(await page.locator('#dashboard-content .admin-error').textContent(), 'Nao foi possivel carregar o dashboard.Tentar novamente');
        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: dashboard real, zero/error states, safe text, navigation and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
