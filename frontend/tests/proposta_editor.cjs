// Browser-only integration. Every request is fulfilled locally; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const fixture = JSON.parse(await fs.readFile(path.join(__dirname, 'fixtures/proposta.json')));
        const saved = new Map();
        const calls = [];
        const errors = [];
        let failSave = false;
        let failLoad = false;
        let delayLoad = 0;
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) errors.push(message.text());
        });
        await context.route('**/*', async route => {
            const req = route.request();
            const url = new URL(req.url());
            if (url.origin === 'http://localhost:8000') {
                calls.push({ method: req.method(), path: url.pathname, body: req.postDataJSON() });
                if (/^\/propostas\/\d+\/preview$/.test(url.pathname)) {
                    return route.fulfill({ contentType: 'text/html', body: '<!doctype html><p>Preview backend</p>' });
                }
                const budget = url.pathname.match(/^\/propostas\/orcamento\/(\d+)$/);
                if (budget) {
                    if (delayLoad) await new Promise(resolve => setTimeout(resolve, delayLoad));
                    if (failLoad) return route.fulfill({ status: 500, json: { detail: 'Falha sintetica ao carregar' } });
                    const value = saved.get(Number(budget[1]));
                    return route.fulfill({ status: value ? 200 : 404, json: value || { detail: 'Nao encontrada' } });
                }
                const create = url.pathname.match(/^\/orcamentos\/(\d+)\/proposta$/);
                if (create && req.method() === 'POST') {
                    assert.deepEqual(req.postDataJSON(), {});
                    const id = Number(create[1]);
                    if (!saved.has(id)) {
                        const response = structuredClone(fixture);
                        response.id = id + 100;
                        response.orcamento_id = id;
                        response.cliente_snapshot.orcamento.id = id;
                        saved.set(id, response);
                    }
                    return route.fulfill({ json: saved.get(id) });
                }
                const item = url.pathname.match(/^\/propostas\/(\d+)$/);
                if (item) {
                    const response = [...saved.values()].find(value => value.id === Number(item[1]));
                    if (req.method() === 'GET') return route.fulfill({ json: response });
                    assert.equal(req.method(), 'PATCH');
                    await new Promise(resolve => setTimeout(resolve, 150));
                    if (failSave) return route.fulfill({ status: 422, json: { detail: 'Falha sintetica ao salvar' } });
                    const payload = req.postDataJSON();
                    assert.deepEqual(Object.keys(payload).sort(), ['condicoes', 'descricao', 'itens', 'objeto', 'pagamentos', 'produtor_id']);
                    assert.ok(payload.itens.every(value => !('subtotal' in value) && !('id' in value)));
                    Object.assign(response, payload, { versao: response.versao + 1 });
                    // Deliberately distinct from the estimate: saved totals must come from the response.
                    response.totais = { subtotal: '222.22', desconto: '0.00', total: '222.22' };
                    return route.fulfill({ json: response });
                }
                throw new Error(`Unexpected API call: ${req.method()} ${url.pathname}`);
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
        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fecharEditorProposta === 'function');
        await page.evaluate(() => localStorage.setItem('access_token', 'synthetic-only'));
        const state = () => page.evaluate(async () => (await import('/js/admin/propostas/proposta_state.js')).propostaState);
        const open = id => page.evaluate(async id => {
            const controller = await import('/js/admin/propostas/propostas.js');
            return controller.abrirEditorProposta({ id, nome_cliente: 'MUST NOT DISPLAY', detalhes: 'MUST NOT DISPLAY', status: 'em_analise' });
        }, id);
        const tab = name => page.locator('#proposta-tabs').getByRole('button', { name, exact: true }).click();
        const save = () => Promise.all([
            page.waitForResponse(response => response.request().method() === 'PATCH'),
            page.locator('#btn-save-proposta').click()
        ]);
        const waitSaved = () => page.waitForFunction(async () => !(await import('/js/admin/propostas/proposta_state.js')).propostaState.salvando);

        delayLoad = 150;
        await page.evaluate(async () => {
            const controller = await import('/js/admin/propostas/propostas.js');
            window.opening = Promise.all([controller.abrirEditorProposta({ id: 42 }), controller.abrirEditorProposta({ id: 42 })]);
        });
        assert.equal((await state()).carregando, true);
        await page.evaluate(() => window.opening);
        delayLoad = 0;
        assert.deepEqual(calls.map(call => `${call.method} ${call.path}`), ['GET /propostas/orcamento/42', 'POST /orcamentos/42/proposta']);
        assert.equal((await state()).dirty, false);
        assert.equal(await page.locator('#btn-save-proposta').isDisabled(), true);
        assert.match(await page.locator('#proposta-content').textContent(), /Cliente Teste/);
        assert.ok(!(await page.locator('#proposta-content').textContent()).includes('MUST NOT DISPLAY'));
        assert.equal(await page.locator('#proposta-content textarea').getAttribute('readonly'), '');
        await tab('Proposta');
        assert.equal(await page.locator('#proposta_numero').inputValue(), fixture.numero);
        assert.equal(await page.locator('#proposta_numero').getAttribute('readonly'), '');
        assert.match(await page.locator('#proposta-status').textContent(), /rascunho.*Versão 1/);
        assert.equal((await state()).dirty, false);
        await page.locator('#proposta_descricao').fill('Descricao persistida');
        assert.equal((await state()).dirty, true);
        await tab('Condições');
        await page.locator('#proposta_condicoes').fill('Condicoes persistidas');
        await tab('Itens');
        await page.locator('#btn-add-proposta-item').click();
        const rows = page.locator('.proposta-item-row');
        const description = rows.nth(1).locator('[data-campo="descricao"]');
        await description.pressSequentially('Masterizacao');
        assert.equal(await description.inputValue(), 'Masterizacao');
        assert.equal(await description.evaluate(el => el === document.activeElement), true);
        const amount = rows.nth(1).locator('[data-campo="valor_unitario"]');
        await amount.fill('');
        await amount.pressSequentially('123.45');
        assert.equal(await amount.inputValue(), '123.45');
        assert.equal(await amount.evaluate(el => el === document.activeElement), true);
        assert.ok(await page.locator('#proposta-itens-total').textContent());
        await rows.nth(0).getByRole('button', { name: 'Remover' }).click();
        assert.equal(await rows.count(), 1);
        await tab('Pagamento');
        const link = page.locator('#proposta_pagamento_pagamento_completo_url');
        await link.fill('https://example.com/completo');
        assert.equal(await link.evaluate(el => el === document.activeElement), true);
        await page.locator('#proposta_pagamento_pagamento_parcial_1_url').fill('https://example.com/entrada');
        await page.locator('#proposta_pagamento_pagamento_parcial_2_url').fill('https://example.com/final');
        await page.locator('#proposta_pagamento_parcial_2_disponivel').check();
        assert.equal(await page.locator('#proposta_pagamento_entrada').getAttribute('readonly'), '');
        await page.evaluate(async () => {
            const controller = await import('/js/admin/propostas/propostas.js');
            window.saving = Promise.all([controller.salvarProposta(), controller.salvarProposta()]);
        });
        assert.equal((await state()).salvando, true);
        assert.equal(await page.evaluate(() => window.fecharEditorProposta()), false);
        assert.equal(await page.locator('#btn-save-proposta').isDisabled(), true);
        await page.evaluate(() => window.saving);
        assert.equal(calls.filter(call => call.method === 'PATCH').length, 1);
        assert.equal((await state()).dirty, false);
        assert.equal((await state()).proposta.versao, 2);
        assert.equal(await page.locator('#proposta_pagamento_valor_total').inputValue(), '222.22');
        const persisted = saved.get(42);
        assert.equal(persisted.itens[0].descricao, 'Masterizacao');
        assert.equal(persisted.itens[0].valor_unitario, '123.45');
        assert.equal(persisted.pagamentos[2].habilitado, true);
        assert.deepEqual(persisted.cliente_snapshot, fixture.cliente_snapshot);

        await page.locator('#proposta_pagamento_parcial_2_disponivel').uncheck();
        failSave = true;
        await save();
        await waitSaved();
        assert.equal((await state()).dirty, true);
        assert.equal((await state()).proposta.pagamentos[2].habilitado, false);
        assert.equal(saved.get(42).pagamentos[2].habilitado, true);
        await page.waitForFunction(() => !document.getElementById('btn-save-proposta').disabled);
        assert.match(await page.locator('.notification.error').last().textContent(), /Falha sintetica ao salvar/);
        page.once('dialog', dialog => dialog.dismiss());
        await page.evaluate(() => window.fecharEditorProposta());
        assert.equal(await page.locator('#modal-proposta').isVisible(), true);
        page.once('dialog', dialog => dialog.accept());
        await page.evaluate(() => window.fecharEditorProposta());
        assert.equal(await page.locator('#modal-proposta').isVisible(), false);
        failSave = false;
        const posts = calls.filter(call => call.method === 'POST').length;
        await page.evaluate(async () => {
            const { orcamentosState } = await import('/js/admin/orcamentos/orcamentos_state.js');
            const budget = { id: 42, status: 'em_analise', nome_cliente: 'Current budget name' };
            orcamentosState.lista = [budget];
            const controller = await import('/js/admin/orcamentos/orcamentos.js');
            await controller.gerarProposta(42);
            if (budget.status !== 'em_analise') throw new Error('budget status changed');
        });
        assert.equal(calls.filter(call => call.method === 'POST').length, posts);
        assert.equal((await state()).proposta.pagamentos[2].habilitado, true);
        assert.equal((await state()).proposta.itens[0].descricao, 'Masterizacao');
        await tab('Pagamento');
        await page.locator('#proposta_pagamento_parcial_2_disponivel').uncheck();
        await save();
        await waitSaved();
        assert.equal(saved.get(42).pagamentos[2].habilitado, false);
        await tab('Preview');
        assert.ok(!(await page.locator('#proposta-content').textContent()).includes('https://example.com/final'));
        assert.equal(await page.locator('#btn-gerar-pdf-proposta').isDisabled(), false);
        const byId = await page.evaluate(async id => (await import('/js/admin/propostas/proposta_api.js')).buscarPorId(id), persisted.id);
        assert.equal(byId.id, persisted.id);
        await page.evaluate(() => window.fecharEditorProposta());

        failLoad = true;
        await open(43);
        assert.equal((await state()).carregando, false);
        assert.equal((await state()).proposta, null);
        assert.equal(calls.filter(call => call.path === '/orcamentos/43/proposta').length, 0);
        failLoad = false;
        await page.evaluate(() => window.fecharEditorProposta());
        delayLoad = 150;
        await page.evaluate(async () => {
            const controller = await import('/js/admin/propostas/propostas.js');
            window.pending = controller.abrirEditorProposta({ id: 44 });
            controller.fecharEditorProposta();
        });
        await page.evaluate(() => window.pending);
        delayLoad = 0;
        assert.equal((await state()).proposta, null);
        assert.equal(await page.locator('#modal-proposta').isVisible(), false);
        assert.equal(calls.filter(call => call.path === '/orcamentos/44/proposta').length, 0);
        saved.get(42).status = 'enviada';
        await open(42);
        await tab('Proposta');
        assert.equal(await page.locator('#proposta_descricao').isDisabled(), true);
        assert.equal(await page.locator('#btn-save-proposta').isDisabled(), true);
        assert.ok(calls.every(call => call.method !== 'DELETE'));
        assert.ok(calls.every(call => !call.path.endsWith('/status')));
        assert.deepEqual(errors, []);
        console.log('PASS: create/load/save/reopen, snapshot, dirty, failure preservation, double-submit, items, payments, focus, stale responses and readonly status.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
