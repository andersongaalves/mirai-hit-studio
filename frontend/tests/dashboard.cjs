const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const dashboard = {
    metrics: { clientes_ativos: 4, orcamentos_abertos: 3, propostas_aguardando_decisao: 2, producoes_ativas: 5, producoes_atrasadas: 1 },
    pipeline: { orcamentos_abertos: 3, propostas_enviadas: 2, propostas_aprovadas: 1, producoes_ativas: 5 },
    attention: {
        producoes_atrasadas: 1,
        propostas_aguardando_decisao: 2,
        solicitacoes_producao: 3,
        beats_em_revisao: 4,
        portfolio_em_revisao: 5,
        falhas_processamento_tag: 6,
        pagamentos_em_conciliacao: 7,
        entregas_aguardando_aprovacao: 8,
        propostas_expiradas: 2,
    },
    recent_activity: [{ tipo: 'proposta_enviada', titulo: '<img src=x onerror=alert(1)>', data: '2026-09-13T12:00:00Z', secao: 'section-orcamentos' }],
};

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream',
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
    let tagRetries = 0;
    const financeQueries = [];
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'dashboard-token', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } });
        if (url.pathname === '/dashboard') return route.fulfill(dashboardFailure
            ? { status: 500, json: { detail: 'Falha controlada' } }
            : { json: dashboard });
        if (url.pathname === '/admin/beats') return route.fulfill({ json: [] });
        if (url.pathname === '/admin/beats/configuracao') return route.fulfill({ json: {
            capa_mb: 10, mp3_mb: 50, wav_mb: 100, multitrack_mb: 100,
            total_mb: 260, multitrack_mode: 'arquivo',
        } });
        if (['/config', '/servicos', '/projetos/admin', '/orcamentos', '/producoes', '/clientes', '/usuarios'].includes(url.pathname)) {
            return route.fulfill({ json: url.pathname === '/config' ? {} : [] });
        }
        if (url.pathname === '/usuarios/produtores') return route.fulfill({ json: [] });
        if (url.pathname === '/admin/audio-tag/previas/falhas') return route.fulfill({ json: [
            { arquivo_id: 41, arquivo_nome: '<b>mix.wav</b>', producao_id: 3, producao_titulo: 'Single Aurora', created_at: '2026-10-20T12:00:00Z' },
        ] });
        if (url.pathname === '/admin/audio-tag/previas/41/reprocessar' && request.method() === 'POST') {
            tagRetries++;
            return route.fulfill({ json: { estado: 'pendente' } });
        }
        if (url.pathname === '/financeiro/resumo') return route.fulfill({ json: { valor_a_receber: '0.00', valor_recebido: '0.00', cobrancas_parciais: 0, pagamentos_em_atencao: 7, total_cobrancas: 0 } });
        if (url.pathname === '/financeiro/cobrancas') {
            financeQueries.push(url.searchParams.get('reconciliation_status') || '');
            return route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20, pages: 1 } });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });
    try {
        await signIn(page, { next: '/admin.html', username: 'admin', password: 'synthetic-password' });
        await page.waitForSelector('#dashboard-metrics .dashboard-kpi');
        assert.equal(await page.locator('#dashboard-metrics .dashboard-kpi').count(), 5);
        assert.match(await page.locator('#dashboard-metrics').textContent(), /4/);
        // AUD6-S09-003: one indicator row (pipeline) and one pending list, no repeats.
        assert.equal(await page.locator('#dashboard-pipeline').count(), 0);
        const kpiText = await page.locator('#dashboard-metrics').textContent();
        assert.match(kpiText, /Propostas enviadas/);
        assert.doesNotMatch(kpiText, /atrasad|aguardando decisão/);
        assert.equal(await page.locator('#dashboard-attention .dashboard-attention-item').count(), 9);
        assert.match(await page.locator('#dashboard-attention').textContent(), /2 propostas vencidas sem resposta/);
        assert.match(await page.locator('#dashboard-attention').textContent(), /1 produção atrasada/);
        assert.match(await page.locator('#dashboard-attention').textContent(), /3 solicitações de produção para análise/);
        const failures = page.locator('#dashboard-attention .dashboard-tag-failures');
        await failures.waitFor();
        assert.match(await failures.textContent(), /Single Aurora · <b>mix\.wav<\/b>/);
        assert.equal(await failures.locator('b').count(), 0);
        await failures.getByRole('button', { name: 'Reprocessar a tag de <b>mix.wav</b>' }).click();
        await page.waitForFunction(() => document.querySelector('.dashboard-tag-failures')?.textContent.includes('na fila para reprocessar'));
        assert.equal(tagRetries, 1);
        const attentionBeforeActivity = await page.evaluate(() =>
            Boolean(document.getElementById('dashboard-attention').compareDocumentPosition(document.getElementById('dashboard-activity')) & Node.DOCUMENT_POSITION_FOLLOWING));
        assert.equal(attentionBeforeActivity, true);
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.evaluate(() => window.scrollTo(0, 0));
                await page.screenshot({ path: path.join(process.env.VISUAL_OUTPUT, `mirai-j-admin-${width}.png`), animations: 'disabled' });
            }
        }
        assert.equal(await page.locator('#dashboard-activity img, #dashboard-activity script').count(), 0);
        assert.match(await page.locator('#dashboard-activity').textContent(), /<img src=x/);
        await page.locator('#dashboard-attention').getByRole('button', { name: 'Ver produções' }).click();
        assert.equal(await page.locator('#section-producoes').isVisible(), true);
        await page.evaluate(() => window.mostrarDashboard());
        await page.locator('#dashboard-attention').getByRole('button', { name: 'Revisar beats' }).click();
        assert.equal(await page.locator('#section-beats').isVisible(), true);
        await page.evaluate(() => window.mostrarDashboard());
        await page.locator('#dashboard-attention').getByRole('button', { name: 'Conciliar pagamentos' }).click();
        assert.equal(await page.locator('#section-financeiro').isVisible(), true);
        await page.waitForFunction(() => document.getElementById('financeiro-reconciliation-filter')?.value === 'pending');
        assert.equal(financeQueries.at(-1), 'pending');

        dashboard.metrics = { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 };
        dashboard.pipeline = { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 };
        dashboard.attention = {
            producoes_atrasadas: 0, propostas_aguardando_decisao: 0,
            solicitacoes_producao: 0, beats_em_revisao: 0,
            portfolio_em_revisao: 0, falhas_processamento_tag: 0,
            pagamentos_em_conciliacao: 0, entregas_aguardando_aprovacao: 0,
            propostas_expiradas: 0,
        };
        dashboard.recent_activity = [];
        await page.evaluate(() => window.mostrarDashboard());
        await page.waitForFunction(() => document.querySelector('#dashboard-metrics')?.textContent.includes('0'));
        assert.equal(await page.locator('.admin-success').textContent(), 'Nenhuma ação pendente no momento.');
        assert.equal(await page.locator('#dashboard-activity .admin-empty').textContent(), 'Ainda não há atividade recente.');

        dashboardFailure = true;
        await page.evaluate(() => window.mostrarDashboard());
        await page.waitForSelector('#dashboard-content .admin-error');
        assert.equal(await page.locator('#dashboard-content .admin-error').textContent(), 'Não foi possível carregar o dashboard.Tentar novamente');
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
