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
            contentType: { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

const pageHtml = `<!doctype html><html><head><link rel="stylesheet" href="/css/main.css"></head><body>
<input id="clientes-search"><select id="clientes-status-filter"><option value="todos">Todos</option><option value="ativo">Ativos</option><option value="inativo">Inativos</option></select><button id="clientes-clear-filters" class="hidden">Limpar filtros</button>
<p id="clientes-summary"></p><div id="clientes-list"></div>
<div id="modal-cliente" class="hidden" aria-labelledby="cliente-modal-title"><div class="modal-content cliente-modal-content"><div class="cliente-modal-header"><h2 id="cliente-modal-title"></h2><button aria-label="Fechar cliente">Fechar</button></div><input id="cliente-nome"><input id="cliente-email"><input id="cliente-telefone"><textarea id="cliente-observacoes"></textarea><input id="cliente-ativo" type="checkbox"><div id="cliente-history-block"><div id="cliente-historico"></div></div><button id="cliente-save">Salvar cliente</button></div></div>
<script type="module">localStorage.setItem('access_token','test-token'); const module = await import('/js/admin/clientes/clientes.js'); window.crmModule = module; await module.initClientes();</script>
</body></html>`;

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1024, height: 800 } });
    const page = await context.newPage();
    const errors = [];
    const calls = [];
    let failList = false;
    let duplicate = false;
    const clientes = [
        { id: 1, nome: '<img src=x onerror=alert(1)>', email: 'cliente@example.com', telefone: '5511999990000', observacoes: '<script>nota</script>', ativo: true, total_orcamentos: 2, ultima_interacao: '2026-09-10T12:00:00Z', created_at: '2026-01-01T12:00:00Z', updated_at: '2026-09-10T12:00:00Z' },
        { id: 2, nome: 'Cliente inativo', email: null, telefone: '11988887777', observacoes: '', ativo: false, total_orcamentos: 0, ultima_interacao: null, created_at: '2026-01-01T12:00:00Z', updated_at: '2026-01-01T12:00:00Z' },
    ];

    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.pathname === '/clientes-test.html') return route.fulfill({ contentType: 'text/html', body: pageHtml });
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });
        calls.push(`${request.method()} ${url.pathname}`);
        if (url.pathname === '/clientes' && request.method() === 'GET') {
            return route.fulfill(failList ? { status: 500, json: { detail: 'Falha' } } : { json: clientes });
        }
        if (url.pathname === '/clientes' && request.method() === 'POST') {
            if (duplicate) return route.fulfill({ status: 409, json: { detail: 'Cliente existente' } });
            const payload = request.postDataJSON();
            const created = { id: 3, ...payload, total_orcamentos: 0, ultima_interacao: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
            clientes.push(created);
            return route.fulfill({ status: 201, json: created });
        }
        const match = url.pathname.match(/^\/clientes\/(\d+)$/);
        if (!match) return route.fulfill({ status: 404, json: { detail: 'Not found' } });
        const cliente = clientes.find(item => item.id === Number(match[1]));
        if (!cliente) return route.fulfill({ status: 404, json: { detail: 'Not found' } });
        if (request.method() === 'GET') return route.fulfill({ json: { ...cliente, historico: [{ evento: 'orcamento_criado', titulo: '<b>Orçamento seguro</b>', data: '2026-09-10T12:00:00Z', orcamento_id: 1 }] } });
        Object.assign(cliente, request.postDataJSON(), { updated_at: new Date().toISOString() });
        return route.fulfill({ json: cliente });
    });

    try {
        await page.goto('http://localhost:4173/clientes-test.html');
        await page.waitForSelector('.clientes-table tbody tr');
        assert.equal(await page.locator('.clientes-table tbody tr').count(), 2);
        assert.equal(await page.locator('.cliente-card').count(), 2);
        assert.equal(await page.locator('#clientes-list img, #clientes-list script').count(), 0);
        assert.match(await page.locator('.clientes-table tbody tr').first().textContent(), /<img src=x/);
        assert.equal(await page.locator('#clientes-summary').textContent(), '2 clientes');

        await page.locator('#clientes-status-filter').selectOption('inativo');
        assert.equal(await page.locator('.cliente-card').count(), 1);
        assert.equal(await page.locator('#clientes-clear-filters').isVisible(), true);
        await page.locator('#clientes-clear-filters').click();
        await page.locator('#clientes-search').fill('example.com');
        assert.equal(await page.locator('.clientes-table tbody tr').count(), 1);
        await page.locator('#clientes-search').fill('(11) 99999-0000');
        assert.equal(await page.locator('.clientes-table tbody tr').count(), 1);
        await page.locator('#clientes-search').fill('ausente');
        assert.equal(await page.locator('.admin-empty').textContent(), 'Nenhum cliente corresponde aos filtros.');
        await page.locator('#clientes-clear-filters').click();

        const opener = page.locator('.clientes-table tbody tr').first().getByRole('button', { name: /Abrir cliente/ });
        await opener.click();
        await page.waitForFunction(() => !document.getElementById('modal-cliente').classList.contains('hidden'));
        assert.equal(await page.evaluate(() => document.activeElement?.id), 'cliente-nome');
        assert.equal(await page.locator('#cliente-historico b').count(), 0);
        assert.match(await page.locator('#cliente-historico').textContent(), /<b>Orçamento seguro<\/b>/);
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => document.getElementById('modal-cliente').classList.contains('hidden'));
        assert.equal(await opener.evaluate(element => element === document.activeElement), true);

        await page.evaluate(() => window.crmModule.novoCliente());
        await page.locator('#cliente-nome').fill('Novo cliente');
        await page.locator('#cliente-email').fill('novo@example.com');
        await page.locator('#cliente-save').click();
        await page.waitForFunction(() => document.getElementById('modal-cliente').classList.contains('hidden'));
        assert.equal(clientes.length, 3);

        const edit = page.locator('.clientes-table tbody tr').filter({ hasText: 'Novo cliente' }).getByRole('button');
        await edit.click();
        await page.locator('#cliente-nome').fill('Cliente editado');
        await page.locator('#cliente-ativo').uncheck();
        await page.locator('#cliente-save').click();
        await page.waitForFunction(() => document.getElementById('modal-cliente').classList.contains('hidden'));
        assert.equal(clientes[2].nome, 'Cliente editado');
        assert.equal(clientes[2].ativo, false);

        duplicate = true;
        await page.evaluate(() => window.crmModule.novoCliente());
        await page.locator('#cliente-nome').fill('Duplicado');
        await page.locator('#cliente-email').fill('cliente@example.com');
        await page.locator('#cliente-save').click();
        await page.waitForSelector('.notification.error');
        assert.equal(await page.locator('#modal-cliente').isVisible(), true);
        assert.equal(await page.locator('#cliente-nome').inputValue(), 'Duplicado');

        await page.keyboard.press('Escape');
        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.locator('.clientes-mobile-view').isVisible(), width <= 768);
            assert.equal(await page.locator('.clientes-table-view').isVisible(), width > 768);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }

        failList = true;
        await page.evaluate(() => window.crmModule.carregarClientes());
        await page.waitForSelector('.admin-error');
        assert.equal(await page.locator('.admin-error').textContent(), 'Não foi possível carregar os clientes.');
        assert.ok(calls.includes('POST /clientes'));
        assert.ok(calls.includes('PATCH /clientes/3'));
        assert.deepEqual(errors, []);
        console.log('PASS: CRM list, filters, responsive views, modal, CRUD, conflict, history and XSS safety.');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
