const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const now = Date.now();
let loginRole = 'produtor';
let failList = false;
let uploads = 0;
let productions = [
    {
        id: 1,
        titulo: '<img src=x onerror=alert(1)>',
        cliente: '<script>Cliente A</script>',
        servico: 'Mixagem',
        status: 'aguardando_inicio',
        etapas: JSON.stringify([{ nome: 'Briefing', feito: true }, { nome: 'Produção', feito: false }]),
        prazo_entrega: new Date(now + 86400000).toISOString(),
        created_at: new Date(now - 86400000).toISOString(),
        updated_at: new Date(now).toISOString(),
    },
    {
        id: 2,
        titulo: 'Trilha de abertura',
        cliente: 'Cliente B',
        servico: 'Trilha',
        status: 'revisao',
        etapas: '[]',
        prazo_entrega: new Date(now - 86400000).toISOString(),
        created_at: new Date(now - 172800000).toISOString(),
        updated_at: new Date(now - 3600000).toISOString(),
    },
];
let files = [{
    id: 9, producao_id: 1, remetente_usuario_id: 1, tipo: 'material',
    nome_exibicao: '<img src=x>.pdf', mime_type: 'application/pdf', tamanho_bytes: 1024,
    sha256: 'a'.repeat(64), grupo_versao: 'synthetic-group', versao: 1,
    substitui_arquivo_id: null, visivel_produtor: true, visivel_cliente: false,
    created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
}];
let payouts = [{
    id: 4, producao_id: 1, producao_titulo: '<b>Faixa</b>', produtor_id: 2,
    produtor_nome: 'Producer A', valor_combinado: '350.00', moeda: 'BRL', status: 'pago',
    liberado_em: new Date(now - 3600000).toISOString(), pago_em: new Date(now).toISOString(),
    referencia_pagamento: 'PIX-TEST', comprovante_arquivo_id: 9,
    created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
}];

async function staticResponse(route) {
    const url = new URL(route.request().url());
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/produtor' || pathname.startsWith('/produtor/')) pathname = '/produtor.html';
    const file = path.resolve(root, '.' + pathname);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html',
                '.png': 'image/png', '.webp': 'image/webp', '.ttf': 'font/ttf',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1024, height: 800 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));

    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });

        const user = { id: 2, username: 'producer-a', role: loginRole, is_admin: loginRole === 'admin', ativo: true };
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'synthetic-producer-token', user } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: user });
        if (url.pathname === '/portal/produtor/producoes' && request.method() === 'GET') {
            return route.fulfill(failList ? { status: 500, json: { detail: 'Falha controlada da API.' } } : { json: productions });
        }
        if (url.pathname === '/portal/produtor/repasses' && request.method() === 'GET') {
            return route.fulfill({ json: payouts });
        }
        if (/^\/portal\/produtor\/repasses\/\d+\/comprovante$/.test(url.pathname)) {
            return route.fulfill({ body: 'receipt', headers: { 'content-disposition': "attachment; filename*=UTF-8''comprovante.pdf" } });
        }
        if (/^\/portal\/produtor\/arquivos\/\d+\/conteudo$/.test(url.pathname)) {
            return route.fulfill({ body: 'file', headers: { 'content-disposition': "attachment; filename*=UTF-8''arquivo.pdf" } });
        }
        const fileList = url.pathname.match(/^\/portal\/produtor\/producoes\/(\d+)\/arquivos$/);
        if (fileList && request.method() === 'GET') {
            return route.fulfill({ json: files.filter(file => file.producao_id === Number(fileList[1])) });
        }
        if (fileList && request.method() === 'POST') {
            uploads++;
            files.push({ ...files[0], id: 10, tipo: 'previa', nome_exibicao: 'preview.mp3', versao: 1 });
            return route.fulfill({ status: 201, json: files.at(-1) });
        }
        const detail = url.pathname.match(/^\/portal\/produtor\/producoes\/(\d+)$/);
        if (detail && request.method() === 'GET') {
            const item = productions.find(entry => entry.id === Number(detail[1]));
            return route.fulfill(item ? { json: item } : { status: 404, json: { detail: 'Producao nao encontrada.' } });
        }
        const status = url.pathname.match(/^\/portal\/produtor\/producoes\/(\d+)\/status$/);
        if (status && request.method() === 'PATCH') {
            const body = request.postDataJSON();
            const item = productions.find(entry => entry.id === Number(status[1]));
            Object.assign(item, { status: body.status, updated_at: new Date().toISOString() });
            return route.fulfill({ json: item });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await page.goto('http://localhost:4173/produtor');
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForSelector('.producer-metric');
        assert.equal(await page.locator('.producer-metric').count(), 5);
        assert.match(await page.locator('#producer-metrics').textContent(), /Produções ativas2/);
        assert.match(await page.locator('#producer-metrics').textContent(), /Em revisão1/);

        await page.getByRole('link', { name: 'Minhas produções' }).click();
        await page.waitForURL('**/produtor/producoes');
        const productionCards = page.locator('#producer-list .producer-card');
        assert.equal(await productionCards.count(), 2);
        assert.equal(await page.locator('#producer-list .producer-card img, #producer-list .producer-card script').count(), 0);
        const unsafeCard = productionCards.filter({ hasText: '<img src=x' });
        assert.equal(await unsafeCard.count(), 1);

        await unsafeCard.getByRole('button', { name: 'Abrir detalhes' }).click();
        await page.waitForURL('**/produtor/producoes/1');
        assert.equal(await page.getByRole('heading', { name: '<img src=x onerror=alert(1)>' }).count(), 1);
        assert.equal(await page.locator('.producer-file img, .producer-file script').count(), 0);
        assert.match(await page.locator('.producer-file').first().textContent(), /<img src=x>/);
        await page.getByLabel('Arquivo para enviar').setInputFiles({ name: 'preview.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('preview') });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('nova versão'));
        assert.equal(uploads, 1);
        await page.getByRole('button', { name: 'Confirmar início' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Andamento atualizado'));
        assert.equal(productions[0].status, 'em_producao');

        await page.getByRole('link', { name: 'Recebimentos' }).click();
        await page.waitForURL('**/produtor/financeiro');
        assert.match(await page.locator('#producer-payouts').textContent(), /R\$\s*350,00/);
        assert.equal(await page.locator('#producer-payouts img, #producer-payouts script').count(), 0);
        assert.match(await page.locator('#producer-payouts').textContent(), /<b>Faixa<\/b>/);
        assert.equal(await page.getByRole('button', { name: 'Baixar comprovante' }).count(), 1);

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `producer-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
        }

        await page.getByRole('button', { name: 'Sair' }).click();
        assert.equal(await page.locator('#login-panel').isVisible(), true);

        productions = [];
        payouts = [];
        await page.goto('http://localhost:4173/produtor');
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForSelector('.producer-metric');
        assert.match(await page.locator('#producer-metrics').textContent(), /Produções ativas0/);
        await page.getByRole('link', { name: 'Minhas produções' }).click();
        assert.match(await page.locator('#producer-list').textContent(), /ainda não possui produções/);
        await page.getByRole('button', { name: 'Sair' }).click();

        loginRole = 'admin';
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('login-error').textContent.includes('exclusiva'));
        assert.equal(await page.locator('#admin-area').isVisible(), false);

        loginRole = 'produtor';
        failList = true;
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Falha controlada'));
        assert.equal(await page.locator('#producer-loading').isVisible(), false);

        assert.deepEqual(errors, []);
        console.log('PASS: producer login/logout, dashboard, list, detail, progress, safe text, errors and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
