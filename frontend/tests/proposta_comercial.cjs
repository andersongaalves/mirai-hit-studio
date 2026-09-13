// All API responses are local fixtures. No email provider or real database is used.
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
        const proposal = JSON.parse(await fs.readFile(path.join(__dirname, 'fixtures/proposta.json')));
        const budget = { id: proposal.orcamento_id, nome_cliente: 'Cliente Teste', email: 'teste@example.com', servico: 'Mixagem', status: 'em_analise', valor_total: 100 };
        const productions = [], calls = [], errors = [];
        let failure = null;
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) errors.push(message.text());
        });
        await context.route('**/*', async route => {
            const request = route.request(), url = new URL(request.url());
            if (url.origin === 'http://localhost:8000') {
                calls.push(`${request.method()} ${url.pathname}`);
                if (url.pathname === '/orcamentos') return route.fulfill({ json: [budget] });
                if (url.pathname === '/usuarios') return route.fulfill({ json: [] });
                if (url.pathname === '/producoes') return route.fulfill({ json: productions });
                if (url.pathname.endsWith('/preview')) return route.fulfill({ contentType: 'text/html', body: '<p>Documento salvo</p>' });
                const action = url.pathname.split('/').pop();
                if (['enviar', 'aprovar'].includes(action)) {
                    await new Promise(resolve => setTimeout(resolve, 150));
                    if (failure === action) return route.fulfill({ status: 503, json: { detail: 'Falha sintetica comercial' } });
                    if (action === 'enviar') {
                        proposal.status = 'enviada';
                        proposal.enviada_em = '2026-09-12T12:00:00Z';
                        budget.status = 'proposta_enviada';
                    } else {
                        proposal.status = 'aceita';
                        proposal.aprovada_em = '2026-09-12T12:01:00Z';
                        budget.status = 'aprovado';
                        if (!productions.length) productions.push({ id: 1, titulo: 'Producao Teste', cliente: 'Cliente Teste', servico: 'Mixagem', status: 'aguardando_inicio', orcamento_id: budget.id, etapas: '[]', prazo_entrega: null });
                    }
                } else if (request.method() === 'PATCH') Object.assign(proposal, request.postDataJSON());
                else assert.ok(url.pathname.startsWith('/propostas/'), url.pathname);
                return route.fulfill({ json: proposal });
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
        await page.evaluate(async id => (await import('/js/admin/propostas/propostas.js')).abrirEditorProposta({ id }), budget.id);
        const state = () => page.evaluate(async () => (await import('/js/admin/propostas/proposta_state.js')).propostaState);
        const action = name => page.evaluate(async name => (await import('/js/admin/propostas/propostas.js'))[name](), name);
        const sendButton = page.locator('#btn-enviar-proposta'), approveButton = page.locator('#btn-aprovar-proposta');
        assert.equal(await sendButton.isDisabled(), false);
        assert.equal(await approveButton.isDisabled(), true);
        await page.locator('#proposta-tabs').getByRole('button', { name: 'Proposta', exact: true }).click();
        await page.locator('#proposta_descricao').fill('Escopo editado');
        assert.equal(await sendButton.isDisabled(), true);
        await action('enviarProposta');
        assert.equal(calls.filter(call => call.endsWith('/enviar')).length, 0);
        await action('salvarProposta');
        page.once('dialog', dialog => dialog.dismiss());
        await sendButton.click();
        assert.equal(calls.filter(call => call.endsWith('/enviar')).length, 0);
        failure = 'enviar';
        page.once('dialog', dialog => dialog.accept());
        await action('enviarProposta');
        assert.equal((await state()).proposta.status, 'rascunho');
        assert.equal((await state()).processando, false);
        assert.equal((await state()).dirty, false);
        assert.equal((await state()).proposta.descricao, 'Escopo editado');
        failure = null;
        page.once('dialog', dialog => dialog.accept());
        await page.evaluate(async () => {
            const c = await import('/js/admin/propostas/propostas.js');
            window.sending = Promise.all([c.enviarProposta(), c.enviarProposta()]);
        });
        assert.equal((await state()).processando, true);
        assert.equal(await sendButton.isDisabled(), true);
        assert.equal(await page.evaluate(() => window.fecharEditorProposta()), false);
        await page.evaluate(() => window.sending);
        assert.equal(calls.filter(call => call.endsWith('/enviar')).length, 2); // one failed, one successful
        assert.equal((await state()).proposta.status, 'enviada');
        assert.equal(await sendButton.isDisabled(), true);
        assert.equal(await approveButton.isDisabled(), false);
        await page.waitForFunction(async () => (await import('/js/admin/orcamentos/orcamentos_state.js')).orcamentosState.lista[0]?.status === 'proposta_enviada');
        assert.equal(calls.filter(call => call === 'GET /producoes').length, 0);
        failure = 'aprovar';
        page.once('dialog', dialog => dialog.accept());
        await action('aprovarProposta');
        assert.equal((await state()).proposta.status, 'enviada');
        assert.equal(await approveButton.isDisabled(), false);
        page.once('dialog', dialog => dialog.dismiss());
        await approveButton.click();
        assert.equal(calls.filter(call => call.endsWith('/aprovar')).length, 1);
        failure = null;
        page.once('dialog', dialog => dialog.accept());
        await action('aprovarProposta');
        assert.equal((await state()).proposta.status, 'aceita');
        assert.equal(await approveButton.isDisabled(), true);
        await page.waitForFunction(async () => (await import('/js/admin/orcamentos/orcamentos_state.js')).orcamentosState.lista[0]?.status === 'aprovado');
        await page.waitForFunction(async () => (await import('/js/admin/producoes/producoes_state.js')).producoesState.lista.length === 1);
        await page.evaluate(() => window.fecharEditorProposta());
        assert.equal(calls.filter(call => call === 'GET /orcamentos').length, 2);
        assert.equal(calls.filter(call => call === 'GET /producoes').length, 1);
        assert.ok(!calls.some(call => /\/status$|enviar-proposta/.test(call)));
        assert.deepEqual(errors, []);
        console.log('PASS: send/approve guards, dirty, confirmations, failures, double-submit, state, CRM reload and production availability.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
