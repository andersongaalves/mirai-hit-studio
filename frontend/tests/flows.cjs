// Run with Playwright available through NODE_PATH. All browser requests are mocked.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        await context.addInitScript(() => {
            window.testRegistrations = { listeners: 0, intervals: 0 };
            const add = EventTarget.prototype.addEventListener;
            EventTarget.prototype.addEventListener = function (...args) {
                if (this === document || this === window || this === document.body) {
                    window.testRegistrations.listeners++;
                }
                return add.apply(this, args);
            };
            const interval = window.setInterval;
            window.setInterval = (...args) => {
                window.testRegistrations.intervals++;
                return interval(...args);
            };
        });
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => {
            if (message.type() === 'error') errors.push(message.text());
        });
        let config = Object.fromEntries([
            'desconto', 'val_extra_duracao', 'val_extra_pessoa', 'val_extra_canal_voz',
            'val_extra_canal_inst', 'val_extra_melodia', 'val_extra_revisao',
            'val_inst_hibrido', 'val_inst_gravado', 'val_prazo_urgente',
            'val_prazo_express', 'val_lease_desconto',
        ].map(key => [key, 10]));
        const calls = [];
        const payloads = [];
        const services = [{ id: 1, nome: 'Servico teste', categoria: 'avulso',
            valor_base: 200, aplica_desconto: false,
            parametros: 'descricao, duracao,inst_aberto,prazo,guia' }];
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:8000') {
                const key = `${request.method()} ${url.pathname}`;
                calls.push(key);
                let data = [];
                if (url.pathname === '/auth/login') data = { access_token: 'synthetic-session', user: { id: 1, username: 'teste', role: 'admin', is_admin: true, ativo: true } };
                if (url.pathname === '/auth/me') data = { id: 1, username: 'teste', is_admin: true, role: 'admin' };
                if (url.pathname === '/dashboard') data = {
                    metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
                    pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
                    attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 },
                    recent_activity: [],
                };
                if (url.pathname === '/audit-logs') data = { items: [], total: 0, page: 1, page_size: 25, pages: 0 };
                if (url.pathname === '/financeiro/resumo') data = { valor_a_receber: '0.00', valor_recebido: '0.00', cobrancas_parciais: 0, pagamentos_em_atencao: 0, total_cobrancas: 0 };
                if (url.pathname === '/financeiro/cobrancas') data = { items: [], total: 0, page: 1, page_size: 25, pages: 0 };
                if (url.pathname === '/servicos') data = services;
                if (url.pathname === '/usuarios/produtores') data = [];
                if (url.pathname === '/config') {
                    if (request.method() === 'PUT') {
                        config = request.postDataJSON();
                        assert.ok('desconto' in config);
                        assert.ok(!('cfg_desconto' in config));
                    }
                    data = config;
                }
                if (key === 'POST /orcamentos') {
                    payloads.push(request.postDataJSON());
                    data = { id: payloads.length };
                }
                return route.fulfill({ json: data });
            }
            if (url.origin === 'http://localhost:4173') {
                const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
                assert.ok(file.startsWith(root + path.sep));
                try {
                    const body = await fs.readFile(file);
                    const types = { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css' };
                    return route.fulfill({ body, contentType: types[path.extname(file)] || 'application/octet-stream' });
                } catch {
                    return route.fulfill({ status: 200, body: '' });
                }
            }
            return route.fulfill({ status: 200, body: '' });
        });

        await page.goto('http://localhost:4173/calculadora.html');
        await page.waitForSelector('#srv_1', { state: 'attached' });
        await page.evaluate(() => document.getElementById('srv_1').click());
        await page.waitForSelector('#descricao', { state: 'attached' });
        for (const [description, options] of [['Texto do cliente', false], ['', true], ['Texto combinado', true], ['', false]]) {
            const requestCompleted = page.waitForResponse(response =>
                response.url() === 'http://localhost:8000/orcamentos'
                && response.request().method() === 'POST',
            );
            await page.evaluate(async ({ description, options }) => {
                const { state } = await import('/js/state.js');
                const { renderizarFormularioParametros } = await import('/js/ui.js');
                state.servicoSelecionadoOBJ.parametros = options ? 'descricao, duracao,inst_aberto,prazo,guia' : 'descricao,guia';
                renderizarFormularioParametros(state.servicoSelecionadoOBJ.parametros);
                document.getElementById('descricao').value = description;
                if (options) {
                    document.getElementById('duracao').value = '240';
                    document.getElementById('inst_aberto').value = 'sim';
                    document.getElementById('canais_inst').value = '8';
                    document.getElementById('prazo').value = 'urgente';
                }
                document.getElementById('nome_cliente').value = 'Cliente Teste';
                document.getElementById('email').value = 'teste@example.com';
                document.getElementById('whatsapp').value = '00000000000';
                const { calcular } = await import('/js/modules/calculator.js');
                calcular();
                document.getElementById('btn-solicitar').click();
            }, { description, options });
            await requestCompleted;
            const payload = payloads.at(-1);
            assert.equal(payload.servico, 'Servico teste');
            assert.equal(payload.valor_total, options ? 890 : 200);
            if (description) assert.ok(payload.detalhes.includes(description));
            if (options) {
                assert.ok(payload.detalhes.includes('Duração: 240s'));
                assert.ok(payload.detalhes.includes('8 canais'));
                assert.ok(payload.detalhes.includes('urgente'));
            }
            if (!description && !options) assert.equal(payload.detalhes, '');
        }
        assert.equal(payloads.length, 4);
        await page.evaluate(async () => {
            const { renderizarFormularioParametros } = await import('/js/ui.js');
            renderizarFormularioParametros('');
            if (document.getElementById('render-parametros').children.length) throw new Error('stale parameters');
        });
        assert.ok(await page.getByText('Solicitação de orçamento enviada.', { exact: true }).count());
        assert.deepEqual(errors, []);

        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fazerLogin === 'function');
        await page.locator('#username').fill('teste');
        await page.locator('#password').fill('synthetic-password');
        calls.length = 0;
        await page.evaluate(() => Promise.all([window.fazerLogin(), window.fazerLogin()]));
        assert.equal(await page.locator('#admin-area').evaluate(el => el.classList.contains('hidden')), false);
        assert.match(await page.locator('#lista-servicos').textContent(), /Servico teste/);
        const expected = ['GET /audit-logs', 'GET /clientes', 'GET /config', 'GET /dashboard', 'GET /financeiro/cobrancas', 'GET /financeiro/resumo', 'GET /newsletter/campaigns', 'GET /newsletter/subscribers', 'GET /orcamentos', 'GET /producoes', 'GET /projetos/admin', 'GET /servicos', 'GET /usuarios', 'GET /usuarios/produtores'];
        assert.deepEqual(calls.filter(call => call.startsWith('GET')).sort(), expected);
        assert.equal(calls.filter(call => call === 'POST /auth/login').length, 1);
        await page.evaluate(() => document.dispatchEvent(new Event('DOMContentLoaded')));
        assert.equal(calls.filter(call => call.startsWith('GET')).length, expected.length);
        assert.equal(await page.locator('#cfg_desconto').inputValue(), '10');
        for (const value of ['0', '15', '-1', '101']) {
            await page.locator('#cfg_desconto').evaluate((el, value) => { el.value = value; }, value);
            await page.evaluate(() => window.salvarConfiguracoesExtras());
            await page.evaluate(async () => (await import('/js/admin/configuracoes.js')).carregarConfiguracoes());
            assert.equal(await page.locator('#cfg_desconto').inputValue(), value);
        }
        const puts = calls.filter(call => call === 'PUT /config').length;
        await page.locator('#cfg_desconto').evaluate(el => { el.value = ''; });
        await page.evaluate(() => window.salvarConfiguracoesExtras());
        assert.equal(calls.filter(call => call === 'PUT /config').length, puts);
        assert.match(errors.pop(), /^Error: Informe um número válido para desconto\./);
        calls.length = 0;
        await page.reload();
        await page.waitForFunction(() => document.getElementById('lista-servicos').textContent.includes('Servico teste'));
        await page.waitForTimeout(100);
        assert.deepEqual(calls.sort(), ['GET /auth/me', ...expected].sort());
        const registrations = await page.evaluate(() => ({ ...window.testRegistrations }));
        await page.evaluate(() => window.fazerLogout());
        assert.equal(await page.locator('#admin-area').evaluate(el => el.classList.contains('hidden')), true);
        calls.length = 0;
        await page.evaluate(() => window.fazerLogin());
        assert.deepEqual(calls.filter(call => call.startsWith('GET')).sort(), expected);
        assert.deepEqual(await page.evaluate(() => window.testRegistrations), registrations);
        assert.deepEqual(errors, []);
        if (process.env.PAYLOAD_OUTPUT) await fs.writeFile(process.env.PAYLOAD_OUTPUT, JSON.stringify(payloads));
        console.log('PASS: four public payloads; config roundtrip/validation; login/reload/logout; no duplicate requests or unexpected console errors.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
