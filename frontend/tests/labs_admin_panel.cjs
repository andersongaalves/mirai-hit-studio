// Mirai Hit Labs admin panel (labs/admin/): sign-in, overview, plugins and releases,
// orders and refund, customers, licenses, coupons and store, with a simulated API.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..', '..', 'labs');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const shots = process.env.SHOT_DIR;

const plugin = {
    id: 1, slug: 'mirai-saturator', nome: 'Mirai Saturator', tagline: 'Saturação analógica', descricao: 'Calor.', categoria: 'Saturação',
    versao: '1.1.0', formatos: ['VST3', 'AU'], recursos: ['Três modos'], requisitos: 'Windows 10+',
    en: { tagline: 'Analog saturation', descricao: null, categoria: null, recursos: [], requisitos: null },
    preco: '149.90', preco_vigente: '149.90', preco_promocional: null, em_promocao: false, gratuito: false,
    capa_url: null, video_url: null, destaque: true, sistemas: [], publicado_em: '2026-11-01T12:00:00Z',
    status: 'publicado', ordem: 0,
    instaladores: [{ sistema: 'windows', nome: 'Windows', versao: '1.1.0', tamanho_bytes: 52428800, tipo: 'arquivo', nome_arquivo: 'Mirai-Saturator-1.1.0-Windows.zip', link: null, atualizado_em: '2026-11-10T12:00:00Z' }],
    licencas: { ativas: 3, reservadas: 1, revogadas: 0 },
};
const tuner = { ...plugin, id: 2, slug: 'mirai-tuner', nome: 'Mirai Tuner', destaque: false, status: 'rascunho', instaladores: [], licencas: { ativas: 0, reservadas: 0, revogadas: 0 } };
const days = Array.from({ length: 30 }, (_, index) => ({ dia: new Date(Date.UTC(2026, 9, 17 + index)).toISOString().slice(0, 10), vendas: index % 4, gratis: index % 7 === 0 ? 1 : 0 }));
const overview = {
    dias: 30, receita: { periodo: { brl: '299.80', usd: '129.90' }, total: { brl: '899.40', usd: '129.90' } },
    vendas_periodo: 3, gratis_periodo: 1, downloads_periodo: 12, licencas: { ativas: 3, aguardando_pagamento: 1, revogadas: 0 },
    contas_labs: { total: 8, novas_periodo: 2 }, serie: days,
    plugins: [{ id: 1, nome: 'Mirai Saturator', slug: 'mirai-saturator', status: 'publicado', versao: '1.1.0', capa_url: null, licencas_ativas: 3, receita_brl: '299.80', receita_usd: '129.90', downloads_periodo: 12 }],
    ultimas_licencas: [{ id: 9, plugin: 'Mirai Saturator', cliente: 'Cliente A', origem: 'stripe', valor: '129.90', moeda: 'usd', ativada_em: '2026-11-14T15:00:00Z' }],
};
const orders = [
    { id: 'usd-4', tipo: 'stripe', moeda: 'usd', status: 'pago', plugin: 'Mirai Saturator', plugin_id: 1, cliente: { id: 1, nome: 'Cliente A', email: 'a@example.test', teste: false },
      valor: '129.90', licenca_id: 9, pedido_id: 4, cupom: { codigo: 'USD20', desconto: '20.00' }, criado_em: '2026-11-14T14:58:00Z', pago_em: '2026-11-14T15:00:00Z', pode_reembolsar: true },
    { id: 'brl-7', tipo: 'checkout', moeda: 'brl', status: 'aguardando', plugin: 'Mirai Saturator', plugin_id: 1, cliente: { id: 2, nome: 'Cliente B', email: 'b@example.test', teste: false },
      valor: '149.90', licenca_id: 7, proposta_id: 31, cobranca_id: 5, cupom: null, criado_em: '2026-11-13T10:00:00Z', pago_em: null, pode_reembolsar: false },
];
const licenses = [
    { id: 9, plugin_id: 1, plugin: 'Mirai Saturator', slug: 'mirai-saturator', cliente_id: 1, cliente: 'Cliente A', email: 'a@example.test', teste: false, origem: 'stripe', status: 'ativa', motivo: null, chave: 'MHL-ABCD-EFGH-JKLM-NPQR', valor: '129.90', moeda: 'usd', criada_em: '2026-11-14T14:58:00Z', ativada_em: '2026-11-14T15:00:00Z', encerrada_em: null },
    { id: 3, plugin_id: 1, plugin: 'Mirai Saturator', slug: 'mirai-saturator', cliente_id: 2, cliente: 'Cliente B', email: 'b@example.test', teste: false, origem: 'cortesia', status: 'revogada', motivo: 'teste', chave: 'MHL-ZZZZ-YYYY-XXXX-WWWW', valor: '0.00', moeda: 'brl', criada_em: '2026-11-01T10:00:00Z', ativada_em: '2026-11-01T10:00:00Z', encerrada_em: '2026-11-02T10:00:00Z' },
];
const customers = [
    { id: 2, nome: 'Cliente B', email: 'b@example.test', teste: false, conta: { tipo: 'labs', usuario: 'clienteb', ativo: true, criada_em: '2026-11-01T10:00:00Z' }, licencas_ativas: 0, total_brl: '0.00', total_usd: '0.00', criado_em: '2026-11-01T10:00:00Z' },
    { id: 1, nome: 'Cliente A', email: 'a@example.test', teste: false, conta: { tipo: 'estudio', usuario: 'client-a', ativo: true, criada_em: '2026-10-01T10:00:00Z' }, licencas_ativas: 1, total_brl: '0.00', total_usd: '129.90', criado_em: '2026-10-01T10:00:00Z' },
];
const releases = [
    { id: 2, plugin_id: 1, versao: '1.1.0', canal: 'estavel', notas: '- Novo modo válvula', notas_en: '- New tube mode', obrigatoria: false, publicada: true, publicada_em: '2026-11-10T12:00:00Z', criada_em: '2026-11-10T12:00:00Z' },
    { id: 1, plugin_id: 1, versao: '1.0.0', canal: 'estavel', notas: null, notas_en: null, obrigatoria: false, publicada: true, publicada_em: '2026-11-01T12:00:00Z', criada_em: '2026-11-01T12:00:00Z' },
];

(async () => {
    // PW_CHANNEL=msedge (or chrome) runs on an installed browser instead of Playwright's Chromium.
    const browser = await chromium.launch(process.env.PW_CHANNEL ? { channel: process.env.PW_CHANNEL } : {});
    try {
        const calls = [];
        let coupons = [];
        let signedIn = false;
        const errors = [];
        const context = await browser.newContext({ viewport: { width: 1360, height: 900 } });
        const page = await context.newPage();
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', message => { if (message.type() === 'error' && !/Failed to load resource/.test(message.text())) errors.push(message.text()); });
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4174') {
                const file = url.pathname.endsWith('/') ? `${url.pathname}index.html` : url.pathname;
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: 'not found' }); }
            }
            if (url.origin === 'http://localhost:8000') {
                const p = url.pathname;
                const method = request.method();
                const body = request.postData() ? JSON.parse(request.postData()) : null;
                calls.push({ method, path: p, search: url.search, body, auth: request.headers().authorization || null });
                if (p === '/auth/login') {
                    if (body.password !== 'certa') return route.fulfill({ status: 401, json: { detail: 'Usuario ou senha incorretos.' } });
                    if (body.username === 'cliente') return route.fulfill({ json: { access_token: 'client-token', user: { id: 4, username: 'cliente', role: 'cliente', is_admin: false } } });
                    signedIn = true;
                    return route.fulfill({ json: { access_token: 'admin-token', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
                }
                if (request.headers().authorization !== 'Bearer admin-token' || !signedIn) return route.fulfill({ status: 401, json: { detail: 'x' } });
                if (p === '/auth/me') return route.fulfill({ json: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } });
                if (p === '/admin/labs/resumo') return route.fulfill({ json: overview });
                if (p === '/admin/labs/plugins') return route.fulfill({ json: [plugin, tuner] });
                if (p === '/admin/labs/plugins/1') return route.fulfill({ json: plugin });
                if (p === '/admin/labs/plugins/1/versoes' && method === 'GET') return route.fulfill({ json: releases });
                if (p === '/admin/labs/plugins/1/versoes' && method === 'POST') return route.fulfill({ status: 201, json: { ...releases[0], id: 3, versao: body.versao } });
                if (p === '/admin/labs/pedidos') return route.fulfill({ json: orders });
                if (p === '/admin/labs/pedidos/stripe/4/reembolsar') return route.fulfill({ json: { id: 4, status: 'reembolsado' } });
                if (p === '/admin/labs/clientes') return route.fulfill({ json: customers });
                if (p === '/admin/labs/clientes/1') return route.fulfill({ json: { ...customers[1], telefone: null, ativo: true, licencas: [licenses[0]], pedidos: [orders[0]] } });
                if (p === '/admin/labs/licencas') return route.fulfill({ json: licenses });
                if (p === '/admin/labs/licencas/3/reativar') return route.fulfill({ json: { id: 3, status: 'ativa' } });
                if (p === '/admin/labs/cupons' && method === 'GET') return route.fulfill({ json: coupons });
                if (p === '/admin/labs/cupons' && method === 'POST') {
                    const row = { id: 1, ...body, situacao: 'ativo', usos: 0, usos_registrados: 0, plugin: body.plugin_id ? 'Mirai Saturator' : null, criado_em: '2026-11-15T10:00:00Z' };
                    coupons = [row];
                    return route.fulfill({ status: 201, json: row });
                }
                if (p === '/admin/labs/conteudo') return route.fulfill({ json: { banner: { ativo: false, texto: null, texto_en: null, link: null } } });
                if (p === '/admin/labs/conteudo/banner') return route.fulfill({ json: { banner: body } });
                if (p === '/admin/labs/ordem') return route.fulfill({ json: [tuner, plugin] });
                return route.fulfill({ status: 404, json: { detail: 'nao simulado' } });
            }
            if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') return route.fulfill({ status: 200, body: '', contentType: 'text/css' });
            return route.fulfill({ status: 204, body: '' });
        });
        const last = (p, method = null) => [...calls].reverse().find(call => call.path === p && (!method || call.method === method));

        // Sign-in: wrong password, a customer account, then the admin.
        await page.goto('http://localhost:4174/admin/');
        await page.getByLabel('Usuário').fill('admin');
        await page.getByLabel('Senha').fill('errada');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.getByText('Usuário ou senha incorretos.').waitFor();
        await page.getByLabel('Usuário').fill('cliente');
        await page.getByLabel('Senha').fill('certa');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.getByText('Esta conta não é de administrador.').waitFor();
        await page.getByLabel('Usuário').fill('admin');
        await page.getByLabel('Senha').fill('certa');
        await page.getByRole('button', { name: 'Entrar' }).click();

        // Overview.
        await page.getByRole('heading', { name: 'Visão geral' }).waitFor();
        await page.locator('.tile__value', { hasText: 'R$ 299,80' }).waitFor();
        assert.equal(await page.locator('.chart .hit').count(), 30);
        await page.locator('.chart .hit').nth(3).hover();
        assert.match(await page.locator('.chart__tip').textContent(), /3 vendas/);
        if (shots) await page.screenshot({ path: path.join(shots, 'admin-overview.png'), fullPage: true });

        // Plugins: list, editor tabs, new release.
        await page.getByRole('navigation').getByRole('link', { name: 'Plugins' }).click();
        await page.getByRole('heading', { name: 'Plugins' }).waitFor();
        await page.getByText('Falta Windows e macOS').waitFor();
        await page.getByRole('link', { name: /Mirai Saturator/ }).click();
        await page.getByRole('heading', { name: 'Mirai Saturator' }).waitFor();
        assert.equal(await page.getByLabel('Nome', { exact: true }).inputValue(), 'Mirai Saturator');
        await page.getByRole('tab', { name: 'Capa e instaladores' }).click();
        await page.getByText('Mirai-Saturator-1.1.0-Windows.zip', { exact: false }).waitFor();
        await page.getByRole('tab', { name: 'Versões' }).click();
        await page.getByText('- Novo modo válvula').waitFor();
        await page.getByLabel('Versão', { exact: true }).fill('1.2.0');
        await page.getByLabel('Novidades (PT)').fill('- Preset novo');
        await page.getByRole('button', { name: 'Adicionar versão' }).click();
        await page.getByText('Versão 1.2.0 adicionada.').waitFor();
        assert.deepEqual(last('/admin/labs/plugins/1/versoes', 'POST').body,
            { versao: '1.2.0', canal: 'estavel', notas: '- Preset novo', notas_en: null, obrigatoria: false, publicar: true });
        if (shots) await page.screenshot({ path: path.join(shots, 'admin-releases.png'), fullPage: true });

        // Orders: refund needs a reason and goes to the API.
        await page.getByRole('navigation').getByRole('link', { name: 'Pedidos' }).click();
        await page.getByText('cupom USD20').waitFor();
        await page.getByRole('button', { name: 'Reembolsar' }).click();
        const dialog = page.getByRole('dialog');
        await dialog.getByLabel('Motivo (fica no histórico)').fill('pedido do cliente');
        await dialog.getByRole('button', { name: 'Reembolsar' }).click();
        await page.getByText('Reembolso feito.').waitFor();
        assert.deepEqual(last('/admin/labs/pedidos/stripe/4/reembolsar').body, { motivo: 'pedido do cliente' });
        await page.getByLabel('Moeda').selectOption('usd');
        await page.waitForFunction(() => window.location.hash.includes('moeda=usd'));
        await page.waitForFunction(() => document.querySelector('.page-title')?.textContent === 'Pedidos');
        await page.waitForTimeout(200);
        assert.equal(last('/admin/labs/pedidos').search, '?moeda=usd');

        // Customers and detail.
        await page.getByRole('navigation').getByRole('link', { name: 'Clientes' }).click();
        await page.getByText('Conta da Labs').waitFor();
        await page.getByRole('link', { name: 'Cliente A' }).click();
        await page.getByRole('heading', { name: 'Cliente A' }).waitFor();
        await page.getByText('MHL-ABCD-EFGH-JKLM-NPQR').waitFor();

        // Licenses: reactivate a revoked one.
        await page.getByRole('navigation').getByRole('link', { name: 'Licenças' }).click();
        await page.getByRole('button', { name: 'Reativar' }).click();
        await page.getByRole('dialog').getByRole('button', { name: 'Reativar' }).click();
        await page.getByText('Licença reativada.').waitFor();
        assert.ok(last('/admin/labs/licencas/3/reativar', 'POST'));

        // Coupons: create one.
        await page.getByRole('navigation').getByRole('link', { name: 'Cupons' }).click();
        await page.getByText('Nenhum cupom ainda.').waitFor();
        await page.getByRole('button', { name: 'Novo cupom' }).click();
        const form = page.getByRole('dialog');
        await form.getByLabel('Código').fill('bf 30');
        await form.getByLabel('Desconto').fill('30');
        await form.getByLabel('Limite de usos').fill('100');
        await form.getByRole('button', { name: 'Criar cupom' }).click();
        await page.getByText('Cupom BF30 criado.').waitFor();
        const created = last('/admin/labs/cupons', 'POST').body;
        assert.equal(created.codigo, 'BF30');
        assert.equal(created.tipo, 'percentual');
        assert.equal(created.max_usos, 100);
        await page.locator('td', { hasText: 'BF30' }).waitFor();

        // Store: reorder and banner.
        await page.getByRole('navigation').getByRole('link', { name: 'Loja' }).click();
        await page.getByRole('button', { name: 'Descer: Mirai Saturator' }).click();
        await page.getByRole('button', { name: 'Salvar ordem' }).click();
        await page.getByText('Ordem da loja salva.').waitFor();
        assert.deepEqual(last('/admin/labs/ordem').body, { ids: [2, 1], destaques: [1] });
        await page.getByLabel('Texto (PT)').fill('Black Friday: 30% off');
        await page.getByLabel('Mostrar na loja').check();
        await page.getByRole('button', { name: 'Salvar aviso' }).click();
        await page.getByText(/Aviso publicado/).waitFor();
        assert.equal(last('/admin/labs/conteudo/banner').body.ativo, true);
        if (shots) await page.screenshot({ path: path.join(shots, 'admin-store.png'), fullPage: true });

        // Mobile: no horizontal scroll on the overview.
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto('http://localhost:4174/admin/#/visao-geral');
        await page.getByRole('heading', { name: 'Visão geral' }).waitFor();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        assert.ok(overflow <= 1, `horizontal overflow ${overflow}px`);
        if (shots) await page.screenshot({ path: path.join(shots, 'admin-mobile.png'), fullPage: true });

        // Sign out.
        await page.getByRole('button', { name: 'Sair' }).click();
        await page.getByText('Você saiu do painel.').waitFor();

        assert.deepEqual(errors, []);
        console.log('PASS: Labs admin panel: sign-in, overview, plugins and releases, orders and refund, customers, licenses, coupons, store and mobile layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
