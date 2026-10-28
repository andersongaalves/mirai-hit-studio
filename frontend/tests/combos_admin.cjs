// Roadmap 3.0, 5.08: catalog combos in the Admin (list, create, edit, validation, layout).
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const services = [
    { id: 1, nome: 'Plano Start', subtitulo: '', valor_base: 1000, categoria: 'Mix', aplica_desconto: false, parametros: '', estrutura_servico: '{"intro":"","sections":[],"benefits":[]}' },
    { id: 2, nome: 'Master <i>pro</i>', subtitulo: '', valor_base: 350.5, categoria: 'Master', aplica_desconto: false, parametros: '', estrutura_servico: '{"intro":"","sections":[],"benefits":[]}' },
    { id: 3, nome: 'Vocal', subtitulo: '', valor_base: 200, categoria: 'Vocal', aplica_desconto: false, parametros: '', estrutura_servico: '{"intro":"","sections":[],"benefits":[]}' },
];
const serviceView = id => {
    const service = services.find(item => item.id === id);
    return { servico_id: id, nome: service.nome, valor_base: service.valor_base.toFixed(2), etapas: id === 3 ? 0 : 2 };
};
let combos = [{
    id: 9, nome: 'Combo <b>antigo</b>', descricao: 'Primeiro combo', preco_base: '1200.00', ativo: true,
    soma_servicos: '1350.50', servicos: [serviceView(1), serviceView(2)], created_at: null, updated_at: null,
}];
const writes = [];
let rejectNext = false;

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

function store(id, body) {
    const ids = body.servicos;
    const combo = {
        id, nome: body.nome, descricao: body.descricao, preco_base: body.preco_base, ativo: body.ativo,
        soma_servicos: ids.reduce((sum, item) => sum + services.find(service => service.id === item).valor_base, 0).toFixed(2),
        servicos: ids.map(serviceView), created_at: null, updated_at: null,
    };
    combos = combos.filter(item => item.id !== id).concat(combo);
    return combo;
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
        if (url.pathname === '/auth/me') return route.fulfill({ json: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } });
        if (url.pathname === '/servicos') return route.fulfill({ json: services });
        if (url.pathname === '/combos' && request.method() === 'GET') return route.fulfill({ json: combos });
        const write = url.pathname.match(/^\/combos(?:\/(\d+))?$/);
        if (write && ['POST', 'PUT'].includes(request.method())) {
            const body = request.postDataJSON();
            writes.push({ method: request.method(), id: write[1] ? Number(write[1]) : null, body });
            if (rejectNext) {
                rejectNext = false;
                return route.fulfill({ status: 422, json: { detail: 'Um dos servicos do combo nao existe no catalogo.' } });
            }
            const combo = store(write[1] ? Number(write[1]) : 10 + writes.length, body);
            return route.fulfill({ status: write[1] ? 200 : 201, json: combo });
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
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));
        await openAdminSection(page, 'section-servicos');
        const panel = page.locator('#combos-panel');
        await panel.locator('.combo-card').first().waitFor();

        // List renders as text with reference price, sum of services and stage counts.
        const card = panel.locator('.combo-card').first();
        assert.match(await card.textContent(), /Combo <b>antigo<\/b>.*Ativo.*Preço R\$\s1\.200,00 · soma dos serviços R\$\s1\.350,50/s);
        assert.match(await card.textContent(), /Master <i>pro<\/i> — R\$\s350,50 · 2 etapas/);
        assert.equal(await panel.locator('b, i').count(), 0);

        // Create: client-side validation, "use sum" helper and payload in catalog order.
        await panel.getByRole('button', { name: 'Criar combo' }).click();
        const form = panel.locator('.combo-form');
        await form.getByLabel('Nome').fill('Trio');
        await form.getByRole('button', { name: 'Salvar combo' }).click();
        assert.match(await form.locator('.combo-form__feedback').textContent(), /preço do combo/);
        await form.getByLabel('Vocal — R$').check();
        await form.getByLabel('Plano Start — R$').check();
        assert.match(await form.locator('.combo-form__sum').textContent(), /R\$\s1\.200,00 \(2 serviços\)/);
        await form.getByRole('button', { name: 'Usar soma dos serviços' }).click();
        assert.equal(await form.getByLabel('Preço (R$)').inputValue(), '1200.00');
        await form.getByLabel('Vocal — R$').uncheck();
        await form.getByRole('button', { name: 'Salvar combo' }).click();
        assert.match(await form.locator('.combo-form__feedback').textContent(), /pelo menos dois serviços/);
        assert.equal(writes.length, 0);
        await form.getByLabel('Vocal — R$').check();
        await form.getByLabel('Descrição').fill('Mix e voz');
        // Catalog rework: sold like a service (subtitle, discount choice and highlights).
        await form.getByLabel('Subtítulo do botão').fill('Para quem já gravou');
        await form.getByLabel('Aplicar desconto?').selectOption('true');
        await form.getByLabel('Promoção ativa').check();
        await form.getByLabel('Desconto especial (%)').fill('20');
        await form.getByLabel('Destaques do combo (um por linha, até 20)').fill('Desconto de combo\n\n  1 revisão extra ');
        rejectNext = true;
        await form.getByRole('button', { name: 'Salvar combo' }).click();
        await page.waitForFunction(() => document.querySelector('.combo-form__feedback')?.textContent.includes('nao existe'));
        await form.getByRole('button', { name: 'Salvar combo' }).click();
        await page.waitForFunction(() => document.querySelectorAll('#combos-list .combo-card').length === 2);
        assert.equal(await page.locator('#combo-editor').isVisible(), false);
        assert.deepEqual(writes.at(-1), { method: 'POST', id: null, body: {
            nome: 'Trio', descricao: 'Mix e voz', subtitulo: 'Para quem já gravou', preco_base: '1200.00', aplica_desconto: true,
            promocao: { ativa: true, percentual: '20', inicio: null, fim: null },
            destaques: ['Desconto de combo', '1 revisão extra'], ativo: true, servicos: [1, 3] } });

        // Edit: deactivate and change services; the card shows "Inativo".
        await panel.getByRole('button', { name: 'Editar combo Combo <b>antigo</b>' }).click();
        assert.equal(await form.getByLabel('Nome').inputValue(), 'Combo <b>antigo</b>');
        assert.equal(await form.getByLabel('Master <i>pro</i> — R$').isChecked(), true);
        await form.getByLabel('Ativo (aparece no site e em novas propostas)').uncheck();
        await form.getByLabel('Vocal — R$').check();
        // Order of the services: new ones go last and can be moved.
        assert.deepEqual(await form.locator('.combo-form__ordem-item > span').allTextContents(),
            ['1. Plano Start', '2. Master <i>pro</i>', '3. Vocal']);
        assert.equal(await form.getByRole('button', { name: 'Mover para cima: Plano Start' }).isDisabled(), true);
        await form.getByRole('button', { name: 'Mover para cima: Vocal' }).click();
        await form.getByRole('button', { name: 'Mover para cima: Vocal' }).click();
        assert.deepEqual(await form.locator('.combo-form__ordem-item > span').allTextContents(),
            ['1. Vocal', '2. Plano Start', '3. Master <i>pro</i>']);
        assert.equal(await form.locator('.combo-form__ordem b, .combo-form__ordem i').count(), 0);
        await form.getByRole('button', { name: 'Salvar combo' }).click();
        await page.waitForFunction(() => document.querySelector('.combo-card--inativo'));
        assert.deepEqual(writes.at(-1), { method: 'PUT', id: 9, body: {
            nome: 'Combo <b>antigo</b>', descricao: 'Primeiro combo', subtitulo: '', preco_base: '1200.00', aplica_desconto: false,
            promocao: null,
            destaques: [], ativo: false, servicos: [3, 1, 2] } });
        assert.match(await panel.locator('.combo-card--inativo').textContent(), /Inativo/);

        // Narrow screens: the panel and the form stay inside the viewport.
        await panel.getByRole('button', { name: 'Criar combo' }).click();
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), true);
        assert.equal(await panel.evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);
        await panel.getByRole('button', { name: 'Cancelar' }).click();
        assert.equal(await page.locator('#combo-editor').isVisible(), false);

        assert.deepEqual(errors, []);
        console.log('PASS: combos list as text, create with validation, sum helper, subtitle/discount/highlights, server error feedback, edit/deactivate, service order and narrow layout.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
