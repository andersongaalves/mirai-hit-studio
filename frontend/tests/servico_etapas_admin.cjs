// Roadmap 3.0, 5.04: service stages editor (order, weights summing to 100%); 5.09: file quotas.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const service = { id: 3, nome: 'Plano Start', subtitulo: '', valor_base: 1000, categoria: 'Mixagem', aplica_desconto: false, parametros: '', estrutura_servico: '{"intro":"","sections":[],"benefits":[]}' };
let stored = [{ id: 1, ordem: 1, nome: 'Briefing', descricao: '', peso_percentual: '0.00', prazo_dias: null, unidade: '', revisoes_incluidas: null, depende_da_anterior: false, administrativa: true }];
const puts = [];
let rejectNext = false;
const quotaPuts = [];
const policyPuts = [];

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
    const context = await browser.newContext({ viewport: { width: 1400, height: 900 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });
        if (url.pathname === '/auth/login') {
            return route.fulfill({ json: { access_token: 'synthetic-admin', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
        }
        if (url.pathname === '/servicos') return route.fulfill({ json: [service] });
        if (url.pathname === '/servicos/3/etapas' && request.method() === 'GET') return route.fulfill({ json: stored });
        if (url.pathname === '/servicos/3/etapas' && request.method() === 'PUT') {
            const body = request.postDataJSON();
            puts.push(body);
            if (rejectNext) {
                rejectNext = false;
                return route.fulfill({ status: 422, json: { detail: 'Etapas com nomes repetidos.' } });
            }
            stored = body.etapas.map((stage, index) => ({ id: index + 10, ordem: index + 1, ...stage, peso_percentual: Number(stage.peso_percentual).toFixed(2) }));
            return route.fulfill({ json: stored });
        }
        if (url.pathname === '/servicos/3/politicas') {
            const herdadas = { publicacao_previa: 'automatica', revisoes_excedentes: 'permitir', cliente_ve_etapas: true, cliente_ve_prazos_etapas: true, financeiro_cliente: 'completo' };
            const politicas = request.method() === 'PUT' ? request.postDataJSON() : { financeiro_cliente: 'resumido' };
            if (request.method() === 'PUT') policyPuts.push(politicas);
            return route.fulfill({ json: { servico_id: 3, politicas, herdadas } });
        }
        if (url.pathname === '/servicos/3/cotas-arquivos' && request.method() === 'GET') {
            return route.fulfill({ json: [{ tipo: 'previa', max_arquivos: 2, max_versoes: null, max_tamanho_mb: null, max_total_mb: null, formatos: null }] });
        }
        if (url.pathname === '/servicos/3/cotas-arquivos' && request.method() === 'PUT') {
            const body = request.postDataJSON();
            quotaPuts.push(body);
            return route.fulfill({ json: body.cotas });
        }
        if (url.pathname === '/config') return route.fulfill({ json: {} });
        if (url.pathname === '/config/portfolio-segments') return route.fulfill({ json: { segments: [], revision: '0'.repeat(64) } });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 },
            recent_activity: [],
        } });
        if (['/projetos/admin', '/orcamentos', '/producoes', '/clientes', '/usuarios', '/usuarios/produtores', '/newsletter/subscribers', '/newsletter/campaigns'].includes(url.pathname)) {
            return route.fulfill({ json: [] });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fazerLogin === 'function');
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('synthetic-password');
        await page.locator('#login-panel').getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));
        await page.locator('[data-admin-target="section-servicos"]').click();
        await page.locator('#section-servicos').getByRole('button', { name: 'Editar' }).click();
        await page.waitForSelector('.servico-etapa');
        assert.equal(await page.locator('.servico-etapa').count(), 1);
        assert.match(await page.locator('#servico-etapas-total').textContent(), /0,00%.*precisa somar 100%/);
        assert.equal(await page.locator('#servico-etapas-unsaved').isVisible(), false);

        for (const [name, weight] of [['Rough Mix', '20'], ['Mixagem', '50'], ['Masterização', '29,5']]) {
            await page.getByRole('button', { name: 'Adicionar etapa' }).click();
            const index = await page.locator('.servico-etapa').count();
            await page.getByLabel(`Nome da etapa ${index}`).fill(name);
            await page.getByLabel(`Peso da etapa ${index} em %`).fill(weight);
        }
        assert.match(await page.locator('#servico-etapas-total').textContent(), /99,50%.*precisa somar 100%/);
        await page.getByRole('button', { name: 'Salvar etapas' }).click();
        assert.equal(puts.length, 0);

        await page.getByLabel('Peso da etapa 4 em %').fill('30');
        assert.equal(await page.locator('#servico-etapas-total').textContent(), 'Total: 100,00%');
        await page.getByLabel('Prazo em dias da etapa 3').fill('5');
        await page.locator('.servico-etapa').nth(2).getByLabel('Depende da anterior').check();
        assert.equal(await page.locator('.servico-etapa').first().getByLabel('Depende da anterior').isDisabled(), true);
        await page.getByRole('button', { name: 'Mover para baixo: etapa 1' }).click();
        assert.equal(await page.getByLabel('Nome da etapa 1').inputValue(), 'Rough Mix');

        rejectNext = true;
        await page.getByRole('button', { name: 'Salvar etapas' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Etapas com nomes repetidos.'));
        await page.getByRole('button', { name: 'Salvar etapas' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Etapas salvas.'));
        const sent = puts.at(-1).etapas;
        assert.deepEqual(sent.map(stage => [stage.nome, stage.peso_percentual, stage.depende_da_anterior, stage.administrativa]), [
            ['Rough Mix', '20', false, false],
            ['Briefing', '0.00', false, true],
            ['Mixagem', '50', true, false],
            ['Masterização', '30', false, false],
        ]);
        assert.equal(sent[2].prazo_dias, 5);
        assert.equal(sent.every(stage => !('id' in stage) && !('ordem' in stage)), true);
        assert.equal(await page.getByLabel('Peso da etapa 3 em %').inputValue(), '50.00');

        await page.getByRole('button', { name: 'Remover etapa 1' }).click();
        assert.equal(await page.locator('.servico-etapa').first().getByLabel('Depende da anterior').isChecked(), false);

        // 5.09: quotas of the service, saved as a typed list.
        await page.waitForSelector('#servico-cotas .file-quota');
        assert.equal(await page.locator('#servico-cotas-unsaved').isVisible(), false);
        assert.equal(await page.getByLabel('Arquivos — Prévias').inputValue(), '2');
        await page.getByLabel('Limitar entregas').check();
        await page.getByLabel('MB por arquivo — Entregas').fill('50');
        await page.getByRole('button', { name: 'Salvar cotas' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Cotas salvas.'));
        assert.deepEqual(quotaPuts.at(-1).cotas.map(cota => [cota.tipo, cota.max_arquivos, cota.max_tamanho_mb]), [
            ['previa', 2, null], ['entrega', null, 50],
        ]);

        // 5.10: service policies override only what is chosen; the rest inherits the global default.
        await page.waitForSelector('#servico-politicas select');
        assert.equal(await page.locator('#servico-politicas-unsaved').isVisible(), false);
        assert.equal(await page.locator('#servico-politicas').getByLabel('Financeiro no portal do cliente').inputValue(), 'resumido');
        await page.locator('#servico-politicas').getByLabel('Prévias do produtor').selectOption('aprovacao_admin');
        await page.getByRole('button', { name: 'Salvar políticas' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Políticas do serviço salvas.'));
        assert.deepEqual(policyPuts.at(-1), { publicacao_previa: 'aprovacao_admin', financeiro_cliente: 'resumido' });

        // The legacy builder layout already overflows on phones; the stages section itself must not.
        for (const width of [390, 1024, 1400]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => [...document.querySelectorAll('#servico-etapas, #servico-etapas *, #servico-cotas, #servico-cotas *, #servico-politicas, #servico-politicas *')]
                .some(element => element.getBoundingClientRect().right > Math.max(window.innerWidth, document.getElementById('servico-etapas').parentElement.getBoundingClientRect().right) + 1));
            assert.equal(overflow, false, `stages overflow at ${width}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: service stages editor validates 100% total, ordering, dependencies and saves the typed list; file quotas and policies save.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
