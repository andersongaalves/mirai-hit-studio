const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.js': 'text/javascript',
                '.css': 'text/css',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

const pageHtml = `<!doctype html><html><head><link rel="stylesheet" href="/css/main.css"></head><body>
<input id="producoes-search"><select id="producoes-status-filter"><option value="todos">Todos</option><option value="aguardando_inicio">Aguardando</option><option value="em_producao">Produção</option><option value="revisao">Revisão</option><option value="finalizado">Finalizado</option><option value="entregue">Entregue</option></select><select id="producoes-prazo-filter"><option value="todos">Todos</option><option value="atrasado">Atrasado</option><option value="proximo">Próximo</option><option value="sem_prazo">Sem prazo</option></select><button id="producoes-clear-filters" class="hidden">Limpar filtros</button>
<p id="producoes-summary"></p>
<div id="producoes-list"></div>
<div id="modal-producao" class="hidden" aria-labelledby="prod_titulo"><div class="modal-content producao-modal-content"><div class="producao-modal-header"><div><span id="prod_id"></span><h2 id="prod_titulo"></h2></div><button aria-label="Fechar detalhes">Fechar</button></div><span id="prod_cliente"></span><span id="prod_email"></span><span id="prod_servico"></span><span id="prod_data"></span><select id="prod_status"></select><span id="prod_produtor"></span><input id="prod_prazo" type="datetime-local"><span id="prod_prazo_status"></span><span id="prod_orcamento"></span><span id="prod_proposta"></span><div id="prod_etapas"></div><div class="producao-add-etapa"><input id="prod_nova_etapa"><button id="btn-add-etapa">Adicionar etapa</button></div><textarea id="prod_observacoes"></textarea><button id="btn-save-observacoes">Salvar observações</button><button id="btn-save-prazo">Salvar prazo</button></div></div>
<script type="module">localStorage.setItem('access_token','test-token'); const module = await import('/js/admin/producoes/producoes.js'); window.productionModule = module; await module.initProducoes();</script>
</body></html>`;

(async () => {
    const browser = await chromium.launch({
        headless: true,
        channel: process.env.BROWSER_CHANNEL || 'msedge',
    });
    const errors = [];
    const calls = [];
    let failList = false;
    let failStatus = false;
    const now = Date.now();
    const productions = [
        { id: 1, titulo: '<img src=x onerror=alert(1)>', cliente: '<script>cliente</script>', cliente_email: 'cliente@example.com', servico: 'Mixagem', status: 'aguardando_inicio', produtor_id: 1, produtor_nome: 'Ana', orcamento_id: 10, proposta_id: 20, proposta_numero: 'PROP-20', observacoes: '<b>nota</b>', etapas: '[]', prazo_entrega: new Date(now - 2 * 86400000).toISOString(), created_at: new Date(now - 10 * 86400000).toISOString(), updated_at: new Date().toISOString() },
        { id: 2, titulo: 'Trilha', cliente: 'Creator', cliente_email: null, servico: 'Tema', status: 'em_producao', produtor_id: null, produtor_nome: null, orcamento_id: 11, proposta_id: null, proposta_numero: null, observacoes: '', etapas: JSON.stringify([{ nome: 'Briefing', feito: true }, { nome: 'Produção', feito: false }]), prazo_entrega: new Date(now + 2 * 86400000).toISOString(), created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
        { id: 3, titulo: 'Finalizada', cliente: 'Artista', cliente_email: null, servico: 'Master', status: 'finalizado', produtor_id: 1, produtor_nome: 'Ana', orcamento_id: 12, proposta_id: null, proposta_numero: null, observacoes: '', etapas: '[]', prazo_entrega: new Date(now - 20 * 86400000).toISOString(), created_at: new Date().toISOString(), updated_at: new Date().toISOString() },
    ];

    const context = await browser.newContext();
    const page = await context.newPage();
    page.on('pageerror', (error) => errors.push(error.message));
    await context.route('**/*', async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === '/production-test.html') {
            return route.fulfill({ contentType: 'text/html', body: pageHtml });
        }
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });

        calls.push(`${route.request().method()} ${url.pathname}`);
        if (url.pathname === '/producoes' && route.request().method() === 'GET') {
            return route.fulfill(failList
                ? { status: 500, json: { detail: 'Falha sintética' } }
                : { json: productions });
        }
        const match = url.pathname.match(/^\/producoes\/(\d+)(?:\/(status|etapas|prazo|observacoes))?$/);
        if (!match) return route.fulfill({ status: 404, json: { detail: 'Não encontrado' } });
        const item = productions.find((entry) => entry.id === Number(match[1]));
        if (!item) return route.fulfill({ status: 404, json: { detail: 'Produção não encontrada' } });
        if (route.request().method() === 'GET') return route.fulfill({ json: item });
        const payload = route.request().postDataJSON();
        if (match[2] === 'status' && failStatus) {
            failStatus = false;
            return route.fulfill({ status: 422, json: { detail: 'Status inválido' } });
        }
        if (match[2] === 'status') item.status = payload.status;
        if (match[2] === 'etapas') item.etapas = payload.etapas;
        if (match[2] === 'prazo') item.prazo_entrega = payload.prazo_entrega;
        if (match[2] === 'observacoes') item.observacoes = payload.observacoes;
        return route.fulfill({ json: item });
    });

    try {
        await page.goto('http://localhost:4173/production-test.html');
        await page.waitForSelector('.producoes-table tbody tr');
        assert.equal(await page.locator('#producoes-list img').count(), 0);
        assert.equal(await page.locator('.producoes-table tbody tr').count(), 3);
        assert.equal(await page.locator('.producao-card').count(), 3);
        assert.equal(await page.locator('#producoes-summary').textContent(), '3 produções');
        assert.match(await page.locator('.producoes-table tbody tr').first().textContent(), /<script>cliente/);
        assert.match(await page.locator('.producao-card').first().textContent(), /<script>cliente/);
        assert.equal(await page.locator('.producao-card').first().getAttribute('data-prazo'), 'atrasado');
        assert.match(await page.locator('.producao-card').nth(1).textContent(), /1\/2 etapas \(50%\)/);
        assert.ok((await page.locator('.producoes-table tbody tr').first().locator('.badge-danger').textContent()).includes('Atrasada'));
        assert.ok((await page.locator('.producoes-table tbody tr').nth(2).locator('.badge-success').allTextContents()).some((text) => text.includes('Finalizado')));

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 900 });
            const mobile = width <= 768;
            assert.equal(await page.locator('.producoes-mobile-view').isVisible(), mobile, `cards em ${width}px`);
            assert.equal(await page.locator('.producoes-table-view').isVisible(), !mobile, `tabela em ${width}px`);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `overflow em ${width}px`);
        }
        await page.setViewportSize({ width: 1024, height: 900 });

        await page.locator('#producoes-prazo-filter').selectOption('atrasado');
        assert.equal(await page.locator('.producao-card').count(), 1);
        assert.equal(await page.locator('#producoes-summary').textContent(), '1 de 3 produções');
        assert.equal(await page.locator('#producoes-clear-filters').isVisible(), true);
        const listCallsBeforeClear = calls.filter((call) => call === 'GET /producoes').length;
        await page.locator('#producoes-clear-filters').click();
        assert.equal(await page.locator('#producoes-prazo-filter').inputValue(), 'todos');
        assert.equal(await page.locator('#producoes-summary').textContent(), '3 produções');
        assert.equal(calls.filter((call) => call === 'GET /producoes').length, listCallsBeforeClear);
        await page.locator('#producoes-search').fill('PROP-20');
        assert.equal(await page.locator('.producao-card').count(), 1);
        await page.locator('#producoes-search').fill('sem resultado');
        assert.equal(await page.locator('.admin-empty').textContent(), 'Nenhuma produção corresponde aos filtros.');
        await page.locator('#producoes-clear-filters').click();

        const desktopOpener = page.locator('.producoes-table tbody tr').first().getByRole('button', { name: 'Ver detalhes' });
        await desktopOpener.click();
        await page.waitForFunction(() => !document.getElementById('modal-producao').classList.contains('hidden'));
        assert.equal(await page.locator('#modal-producao').evaluate((element) => getComputedStyle(element).position), 'fixed');
        assert.equal(await page.locator('#modal-producao').getAttribute('role'), 'dialog');
        assert.equal(await page.evaluate(() => document.activeElement?.getAttribute('aria-label')), 'Fechar detalhes');
        assert.equal(await page.locator('#modal-producao img').count(), 0);
        assert.equal(await page.locator('#prod_cliente').textContent(), '<script>cliente</script>');
        assert.equal(await page.locator('#prod_proposta').textContent(), 'PROP-20 (#20)');
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => document.getElementById('modal-producao').classList.contains('hidden'));
        assert.equal(await desktopOpener.evaluate((element) => element === document.activeElement), true);

        await page.setViewportSize({ width: 320, height: 700 });
        const mobileOpener = page.locator('.producao-card').first().getByRole('button', { name: 'Ver detalhes' });
        await mobileOpener.click();
        await page.waitForFunction(() => !document.getElementById('modal-producao').classList.contains('hidden'));
        const modalBounds = await page.locator('.producao-modal-content').boundingBox();
        assert.ok(modalBounds.x >= 0 && modalBounds.x + modalBounds.width <= 320);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);

        await page.locator('#prod_nova_etapa').fill('<b>Briefing</b>');
        await page.locator('#btn-add-etapa').click();
        await page.waitForFunction(() => document.querySelector('#prod_etapas')?.textContent.includes('<b>Briefing</b>'));
        assert.equal(await page.locator('#prod_etapas b').count(), 0);
        await page.locator('#prod_etapas input[type="checkbox"]').check();
        await page.waitForFunction(() => {
            const checkbox = document.querySelector('#prod_etapas input[type="checkbox"]');
            return checkbox?.checked && !checkbox.disabled;
        });
        assert.equal(JSON.parse(productions[0].etapas)[0].feito, true);
        await page.getByRole('button', { name: 'Remover etapa <b>Briefing</b>' }).click();
        await page.waitForFunction(() => document.querySelector('#prod_etapas')?.textContent.includes('Nenhuma etapa definida.'));
        assert.deepEqual(JSON.parse(productions[0].etapas), []);

        await page.locator('#prod_observacoes').fill('<img src=x onerror=alert(1)>');
        await page.locator('#btn-save-observacoes').click();
        await page.waitForFunction(() => document.getElementById('prod_observacoes').value.includes('onerror'));
        assert.equal(productions[0].observacoes, '<img src=x onerror=alert(1)>');

        failStatus = true;
        await page.locator('#prod_status').selectOption('revisao');
        await page.waitForFunction(() => document.getElementById('prod_status').value === 'aguardando_inicio');
        assert.equal(await page.locator('#prod_status').inputValue(), 'aguardando_inicio');
        assert.equal(productions[0].status, 'aguardando_inicio');

        const deadline = await page.evaluate(async () => {
            const utils = await import('/js/admin/producoes/producoes_utils.js');
            const base = new Date('2030-01-10T12:00:00Z');
            return {
                late: utils.classificarPrazo('2030-01-09T12:00:00Z', 'em_producao', base).tipo,
                lateHour: utils.classificarPrazo('2030-01-10T11:00:00Z', 'em_producao', base).tipo,
                near: utils.classificarPrazo('2030-01-12T12:00:00Z', 'em_producao', base).tipo,
                done: utils.classificarPrazo('2030-01-01T12:00:00Z', 'entregue', base).tipo,
            };
        });
        assert.deepEqual(deadline, { late: 'atrasado', lateHour: 'atrasado', near: 'proximo', done: 'finalizado' });

        failList = true;
        await page.evaluate(() => window.productionModule.carregarProducoes());
        await page.waitForSelector('.admin-error');
        assert.equal(await page.locator('.admin-error').textContent(), 'Não foi possível carregar as produções.');
        assert.equal(errors.length, 0, errors.join('\n'));
        assert.ok(calls.includes('GET /producoes/1'));
        assert.ok(calls.includes('PATCH /producoes/1/etapas'));
        assert.ok(calls.includes('PATCH /producoes/1/observacoes'));
        console.log('PASS: production rendering, urgency, filters, detail, updates, errors and XSS safety.');
    } finally {
        await browser.close();
    }
})().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});
