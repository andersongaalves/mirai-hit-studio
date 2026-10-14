// Roadmap 3.0, 5.05/5.08: catalog services and combos in the proposal editor and the frozen snapshot view.
// Browser-only integration. Every request is fulfilled locally; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const SERVICES = [
    { id: 1, nome: 'Plano Start', subtitulo: '', valor_base: 1000, categoria: 'Mix', aplica_desconto: false,
      parametros: '', estrutura_servico: '{}' },
    { id: 2, nome: '<b>Master</b>', subtitulo: '', valor_base: 300, categoria: 'Master', aplica_desconto: false,
      parametros: '', estrutura_servico: '{}' },
];

// 5.08: one active combo and one inactive combo (never offered for new lines).
const COMBOS = [
    { id: 5, nome: 'Combo <i>Mix</i>+Master', descricao: '', preco_base: '1200.00', ativo: true, soma_servicos: '1300.50',
      servicos: [{ servico_id: 1, nome: 'Plano Start', valor_base: '1000.00', etapas: 4 }, { servico_id: 2, nome: '<b>Master</b>', valor_base: '300.50', etapas: 1 }] },
    { id: 6, nome: 'Combo antigo', descricao: '', preco_base: '900.00', ativo: false, soma_servicos: '1000.00', servicos: [] },
];

const COMBO_SNAPSHOT_ITEM = {
    indice: 3, descricao: 'Combo Mix+Master', servico_id: null, servico_nome: null, preco_catalogo: '1200.00',
    catalogo_disponivel: true, quantidade: '1', valor_unitario: '1000.00', bruto: '1000.00', desconto: '0.00',
    valor_contratado: '1000.00', combo_id: 5, combo_nome: 'Combo Mix+Master',
    componentes: [
        { indice: 1, servico_id: 1, servico_nome: 'Plano Start', preco_catalogo: '1000.00', valor_alocado: '769.05' },
        { indice: 2, servico_id: 2, servico_nome: 'Master', preco_catalogo: '300.50', valor_alocado: '230.95' },
    ],
    etapas: [
        { ordem: 1, nome: 'Mixagem', peso_percentual: '100.00', valor: '769.05', prazo_dias: 3, unidade: 'faixa',
          revisoes_incluidas: null, depende_da_anterior: false, administrativa: false, servico_id: 1, servico_nome: 'Plano Start', componente_indice: 1 },
        { ordem: 2, nome: 'Master final', peso_percentual: '100.00', valor: '230.95', prazo_dias: 2, unidade: 'faixa',
          revisoes_incluidas: null, depende_da_anterior: false, administrativa: false, servico_id: 2, servico_nome: 'Master', componente_indice: 2 },
    ],
};

const SNAPSHOT = {
    versao_snapshot: 1, proposta_versao: 3, moeda: 'BRL', origem: 'envio',
    congelado_em: '2026-10-14T12:00:00+00:00', subtotal: '1050.00', desconto: '200.00', total: '850.00',
    itens: [
        { indice: 1, descricao: 'Plano Start', servico_id: 1, servico_nome: 'Plano Start', preco_catalogo: '1000.00',
          catalogo_disponivel: true, quantidade: '1', valor_unitario: '1000.00', bruto: '1000.00', desconto: '200.00',
          valor_contratado: '800.00', etapas: [
            { ordem: 1, nome: 'Briefing', peso_percentual: '0.00', valor: '0.00', prazo_dias: null, unidade: '',
              revisoes_incluidas: null, depende_da_anterior: false, administrativa: true },
            { ordem: 2, nome: 'Rough Mix', peso_percentual: '20.00', valor: '160.00', prazo_dias: 3, unidade: 'faixa',
              revisoes_incluidas: null, depende_da_anterior: false, administrativa: false },
            { ordem: 3, nome: 'Mixagem', peso_percentual: '50.00', valor: '400.00', prazo_dias: 3, unidade: 'faixa',
              revisoes_incluidas: 2, depende_da_anterior: true, administrativa: false },
            { ordem: 4, nome: 'Masterizacao', peso_percentual: '30.00', valor: '240.00', prazo_dias: 3, unidade: 'faixa',
              revisoes_incluidas: null, depende_da_anterior: true, administrativa: false },
          ] },
        { indice: 2, descricao: 'Taxa avulsa', servico_id: null, servico_nome: null, preco_catalogo: null,
          catalogo_disponivel: false, quantidade: '1', valor_unitario: '50.00', bruto: '50.00', desconto: '0.00',
          valor_contratado: '50.00', etapas: [] },
    ],
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const fixture = JSON.parse(await fs.readFile(path.join(__dirname, 'fixtures/proposta.json')));
        const proposal = structuredClone(fixture);
        const patches = [];
        const errors = [];
        const unexpected = [];
        let catalogRequests = 0;
        let failCatalog = false;
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) errors.push(message.text());
        });
        await context.route('**/*', async route => {
            const req = route.request();
            const url = new URL(req.url());
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/combos' && req.method() === 'GET') {
                    if (failCatalog) return route.fulfill({ status: 503, json: { detail: 'indisponivel' } });
                    return route.fulfill({ json: COMBOS });
                }
                if (url.pathname === '/servicos' && req.method() === 'GET') {
                    catalogRequests += 1;
                    if (failCatalog) return route.fulfill({ status: 503, json: { detail: 'indisponivel' } });
                    return route.fulfill({ json: SERVICES });
                }
                if (url.pathname === '/propostas/orcamento/42') return route.fulfill({ json: proposal });
                if (/^\/propostas\/\d+\/acesso-cliente$/.test(url.pathname)) {
                    return route.fulfill({ json: { estado: 'conta_ativa', cliente_id: 42, convite_disponivel: true,
                        last_sent_at: null, expires_at: null } });
                }
                if (/^\/propostas\/\d+\/classificacao$/.test(url.pathname)) {
                    return route.fulfill({ json: { id: proposal.id, orcamento_id: 42, is_test: false, protegida: false,
                        historico_financeiro: false, reversao_permitida: true } });
                }
                if (/^\/propostas\/\d+\/preview$/.test(url.pathname)) {
                    return route.fulfill({ contentType: 'text/html', body: '<!doctype html><p>Preview</p>' });
                }
                if (url.pathname === `/propostas/${proposal.id}` && req.method() === 'PATCH') {
                    const payload = req.postDataJSON();
                    patches.push(payload);
                    Object.assign(proposal, payload, { versao: proposal.versao + 1 });
                    proposal.itens = payload.itens.map(item => ({ servico_id: null, ...item }));
                    return route.fulfill({ json: proposal });
                }
                // Admin shell bootstrap calls (session, dashboards) are not part of this suite.
                unexpected.push(`${req.method()} ${url.pathname}`);
                return route.fulfill({ status: 404, json: { detail: 'not mocked' } });
            }
            if (url.origin === 'http://localhost:4173') {
                const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
                assert.ok(file.startsWith(root + path.sep));
                try {
                    return route.fulfill({ body: await fs.readFile(file), contentType:
                        { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
                } catch { return route.fulfill({ body: '' }); }
            }
            return route.fulfill({ body: '' });
        });

        const boot = async () => {
            await page.goto('http://localhost:4173/admin.html');
            await page.waitForFunction(() => typeof window.fecharEditorProposta === 'function');
            await page.evaluate(() => localStorage.setItem('mirai.auth.admin.access_token', 'synthetic-only'));
        };
        const open = () => page.evaluate(async () => {
            const controller = await import('/js/admin/propostas/propostas.js');
            await controller.abrirEditorProposta({ id: 42, status: 'em_analise' });
        });
        const tab = name => page.locator('#proposta-tabs').getByRole('button', { name, exact: true }).click();
        const rows = page.locator('.proposta-item-row');
        const select = page.locator('#proposta-catalogo-servico');
        const save = () => Promise.all([
            page.waitForResponse(response => response.request().method() === 'PATCH'),
            page.locator('#btn-save-proposta').click(),
        ]);

        await boot();
        await open();
        await tab('Itens');
        // Placeholder + 2 services + 1 active combo (the inactive one is never offered).
        await page.waitForFunction(() => document.querySelectorAll('#proposta-catalogo-servico option').length === 4);
        assert.deepEqual(await select.locator('optgroup').evaluateAll(groups => groups.map(group => group.label)), ['Serviços', 'Combos']);
        assert.deepEqual(await select.locator('optgroup[label="Combos"] option').allTextContents(), ['Combo <i>Mix</i>+Master — R$\u00a01.200,00']);
        assert.equal(await page.locator('#proposta-catalogo-servico i').count(), 0);
        assert.equal(await select.isDisabled(), false);
        assert.equal(await page.locator('#btn-add-proposta-catalogo').isDisabled(), true);
        // Service names are text, never markup.
        assert.match(await select.locator('option').nth(2).textContent(), /<b>Master<\/b>/);
        assert.equal(await page.locator('#proposta-catalogo-servico b').count(), 0);

        await select.selectOption('s:1');
        await page.locator('#btn-add-proposta-catalogo').click();
        assert.equal(await rows.count(), 2);
        const catalogRow = rows.nth(1);
        assert.equal(await catalogRow.locator('[data-campo="descricao"]').inputValue(), 'Plano Start');
        assert.equal(await catalogRow.locator('[data-campo="valor_unitario"]').inputValue(), '1000');
        assert.match(await catalogRow.locator('[data-origem]').textContent(), /Catálogo: Plano Start · preço base R\$\s1\.000,00/);
        assert.equal(await catalogRow.locator('.proposta-item-origem__tag').count(), 0);
        assert.equal(await rows.nth(0).locator('[data-origem]').count(), 0);

        // Negotiated price: the line keeps its catalog origin and is flagged.
        const price = catalogRow.locator('[data-campo="valor_unitario"]');
        await price.fill('800');
        assert.equal(await catalogRow.locator('.proposta-item-origem__tag').textContent(), 'Preço negociado');
        assert.equal(await price.evaluate(el => el === document.activeElement), true);
        await price.fill('1000');
        assert.equal(await catalogRow.locator('.proposta-item-origem__tag').count(), 0);
        await price.fill('800');

        await save();
        const first = patches.at(-1);
        assert.equal(first.itens.length, 2);
        assert.equal(Object.hasOwn(first.itens[0], 'servico_id'), false);
        assert.deepEqual(first.itens[1], { descricao: 'Plano Start', quantidade: 1, valor_unitario: '800', desconto: 0, servico_id: 1 });

        // 5.08: a combo line starts at the reference price and carries combo_id (never servico_id).
        await tab('Itens');
        await page.waitForFunction(() => document.querySelectorAll('#proposta-catalogo-servico option').length === 4);
        await select.selectOption('c:5');
        await page.locator('#btn-add-proposta-catalogo').click();
        const comboRow = rows.nth(2);
        assert.equal(await comboRow.locator('[data-campo="valor_unitario"]').inputValue(), '1200');
        assert.match(await comboRow.locator('[data-origem]').textContent(), /Combo: Combo <i>Mix<\/i>\+Master · preço de referência R\$\s1\.200,00 · Plano Start \+ <b>Master<\/b>/);
        assert.equal(await comboRow.locator('i, b').count(), 0);
        await comboRow.locator('[data-campo="valor_unitario"]').fill('1000');
        assert.equal(await comboRow.locator('.proposta-item-origem__tag').textContent(), 'Preço negociado');
        await save();
        assert.deepEqual(patches.at(-1).itens[2], { descricao: 'Combo <i>Mix</i>+Master', quantidade: 1, valor_unitario: '1000', desconto: 0, combo_id: 5 });
        await tab('Itens');
        await page.waitForFunction(() => document.querySelectorAll('.proposta-item-row [data-desvincular]').length === 2);
        await rows.nth(2).getByRole('button', { name: 'Desvincular' }).click();
        await save();
        assert.equal(Object.hasOwn(patches.at(-1).itens[2], 'combo_id'), false);

        // Unlinking keeps the line as a free item.
        await tab('Itens');
        await page.waitForFunction(() => document.querySelectorAll('.proposta-item-row [data-desvincular]').length === 1);
        await rows.nth(1).getByRole('button', { name: 'Desvincular' }).click();
        assert.equal(await rows.nth(1).locator('[data-origem]').count(), 0);
        await save();
        assert.equal(Object.hasOwn(patches.at(-1).itens[1], 'servico_id'), false);
        assert.equal(catalogRequests, 1, 'catalog is loaded once per page');

        // Sent proposal: frozen snapshot is shown read-only and the catalog picker is locked.
        proposal.status = 'enviada';
        proposal.snapshot_economico = { ...SNAPSHOT, total: '1850.00', itens: [...SNAPSHOT.itens, COMBO_SNAPSHOT_ITEM] };
        proposal.itens = [{ descricao: 'Plano Start', quantidade: '1', valor_unitario: '1000.00', desconto: '200.00', servico_id: 1 },
            { descricao: 'Taxa avulsa', quantidade: '1', valor_unitario: '50.00', desconto: '0.00', servico_id: null }];
        await page.evaluate(() => window.fecharEditorProposta());
        await open();
        await tab('Itens');
        const snapshot = page.locator('#proposta-snapshot');
        await snapshot.waitFor();
        const text = await snapshot.textContent();
        assert.match(text, /Valores congelados no envio/);
        assert.match(text, /Plano Start.*contratado R\$\s800,00/s);
        assert.match(text, /Rough Mix\s*20,00%\s*R\$\s160,00/);
        assert.match(text, /Masterizacao\s*30,00%\s*R\$\s240,00/);
        assert.match(text, /Briefing \(administrativa\)/);
        assert.match(text, /Item avulso, sem etapas de catálogo/);
        assert.match(text, /não mudam estes valores/);
        // 5.08: combo shows each service share and its stages.
        assert.match(text, /Combo Mix\+Master.*contratado R\$\s1\.000,00.*Combo: Combo Mix\+Master · preço de referência R\$\s1\.200,00/s);
        assert.match(text, /Plano Start — R\$\s769,05.*catálogo R\$\s1\.000,00.*Mixagem\s*100,00%\s*R\$\s769,05/s);
        assert.match(text, /Master — R\$\s230,95.*Master final\s*100,00%\s*R\$\s230,95/s);
        await page.waitForFunction(() => !document.querySelector('#proposta-catalogo-servico option')?.textContent.includes('Carregando'));
        assert.equal(await select.isDisabled(), true);
        assert.equal(await page.locator('[data-desvincular]').isDisabled(), true);

        // Narrow screens: the snapshot must not overflow horizontally.
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await snapshot.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);
        await page.setViewportSize({ width: 1280, height: 800 });

        // Catalog failure: a clear notice, manual items keep working.
        failCatalog = true;
        proposal.status = 'rascunho';
        proposal.snapshot_economico = null;
        await boot();
        await open();
        await tab('Itens');
        await page.waitForFunction(() => document.getElementById('proposta-catalogo-aviso')?.textContent.includes('indisponível'));
        assert.equal(await select.isDisabled(), true);
        const before = await rows.count();
        await page.locator('#btn-add-proposta-item').click();
        assert.equal(await rows.count(), before + 1);
        assert.equal(await page.locator('#proposta-snapshot').count(), 0);

        console.log('unmocked:', [...new Set(unexpected)].join(', ') || 'none');
        assert.ok(unexpected.every(call => !call.includes('/propostas') && !call.includes('/servicos') && !call.includes('/combos')), unexpected.join(', '));
        assert.deepEqual(errors, []);
        console.log('PASS: catalog picker, base price, negotiated flag, payload origin, unlink, single catalog load, frozen snapshot view, narrow layout and catalog failure.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
