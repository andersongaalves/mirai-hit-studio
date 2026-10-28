// AUD6-S09-002: producer page and contextual links between producer, production, client and budget.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
const now = new Date().toISOString();
const producer = { id: 2, username: 'ana.produtora', nome_exibicao: 'Ana <b>Beats</b>', role: 'produtor', is_admin: false, ativo: true, is_test: false, painel_beats: true, cliente_id: null, created_at: now, updated_at: now };
const production = {
    id: 41, titulo: 'Single Aurora', cliente: 'Cliente Nove', servico: 'Mixagem', status: 'em_producao', produtor_id: 2,
    produtor_nome: 'ana.produtora', orcamento_id: 7, proposta_id: null, proposta_numero: null, is_test: false,
    cliente_email: 'nove@example.test', cliente_id: 9, observacoes: '', etapas: '[]', prazo_entrega: null, created_at: now, updated_at: now,
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
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
            const p = url.pathname;
            if (p === '/auth/login') return route.fulfill({ json: { access_token: 'admin-token', user: admin } });
            if (p === '/auth/me') return route.fulfill({ json: admin });
            if (p === '/usuarios') return route.fulfill({ json: [producer] });
            if (p === '/admin/produtores/2/resumo') return route.fulfill({ json: {
                produtor: { id: 2, username: 'ana.produtora', nome_exibicao: 'Ana <b>Beats</b>', ativo: true, painel_beats: true },
                contagens: { producoes_ativas: 1, producoes_atrasadas: 1, producoes_finalizadas: 0, beats_em_revisao: 2, beats_aprovados: 3, beats_vendidos: 1, beats_rejeitados: 0 },
                producoes: [{ id: 41, titulo: 'Single Aurora', cliente: 'Cliente Nove', status: 'em_producao', prazo_entrega: null, atrasada: true }],
            } });
            if (p === '/producoes/41') return route.fulfill({ json: production });
            if (p === '/producoes') return route.fulfill({ json: [production] });
            if (p === '/clientes/9') return route.fulfill({ json: {
                id: 9, nome: 'Cliente Nove', email: 'nove@example.test', telefone: null, ativo: true, observacoes: '', is_test: false,
                created_at: now, updated_at: now, total_orcamentos: 1,
                historico: [{ evento: 'orcamento_criado', titulo: 'Orcamento criado: Mixagem', data: now, orcamento_id: 7 }],
            } });
            if (p === '/orcamentos') return route.fulfill({ json: [{
                id: 7, nome_cliente: 'Cliente Nove', email: 'nove@example.test', whatsapp: null, servico: 'Mixagem', valor_total: 0,
                detalhes: '', status: 'novo', observacoes: '', data_solicitacao: now, cliente_id: 9, is_test: false, produtor: null,
            }] });
            if (p.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            if (p === '/dashboard') return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            return route.fulfill({ json: [] });
        });
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await openAdminSection(page, 'section-usuarios');
        await page.getByRole('button', { name: 'Visão geral de Ana <b>Beats</b>' }).first().click();
        const dialog = page.getByRole('dialog', { name: 'Ana <b>Beats</b>' });
        await dialog.getByText('Produções ativas').waitFor();
        assert.equal(await dialog.locator('b').count(), 0);
        assert.match(await dialog.textContent(), /Beats no catálogo3/);
        assert.match(await dialog.textContent(), /Cliente Nove · Em produção · atrasada/);
        await dialog.getByRole('button', { name: '#41 Single Aurora' }).click();
        await page.locator('#section-producoes').waitFor({ state: 'visible' });
        await page.locator('#modal-producao').waitFor({ state: 'visible' });
        assert.equal(await dialog.isVisible(), false);
        const toClient = page.locator('#prod_cliente_abrir');
        assert.equal(await toClient.isVisible(), true);
        assert.equal(await page.locator('#prod_produtor_abrir').isVisible(), true);
        await toClient.click();
        await page.locator('#section-clientes').waitFor({ state: 'visible' });
        await page.locator('#modal-cliente').waitFor({ state: 'visible' });
        assert.equal(await page.locator('#modal-producao').isVisible(), false);
        await page.locator('#modal-cliente').getByRole('button', { name: 'Abrir orçamento' }).click();
        await page.locator('#section-orcamentos').waitFor({ state: 'visible' });
        await page.locator('#modal-orcamento').waitFor({ state: 'visible' });
        assert.equal(await page.locator('#orc_cliente_abrir').isVisible(), true);
        assert.deepEqual(errors, []);
        await context.close();
        console.log('PASS: producer page and contextual links open the producer, production, client and budget safely.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
