const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const now = Date.now();
let loginRole = 'cliente';
let failList = false;
let uploads = 0;
let productions = [
    {
        id: 1, titulo: '<img src=x onerror=alert(1)>', servico: 'Mixagem', status: 'revisao',
        etapas: JSON.stringify([{ nome: 'Briefing', feito: true }, { nome: 'Avaliação', feito: false }]),
        prazo_entrega: new Date(now + 86400000).toISOString(), created_at: new Date(now - 86400000).toISOString(),
        updated_at: new Date(now).toISOString(),
    },
    {
        id: 2, titulo: 'Trilha final', servico: 'Trilha', status: 'entregue', etapas: '[]',
        prazo_entrega: null, created_at: new Date(now - 172800000).toISOString(),
        updated_at: new Date(now - 3600000).toISOString(),
    },
];
let files = [{
    id: 7, producao_id: 1, tipo: 'previa', nome_exibicao: '<script>preview</script>.mp3',
    mime_type: 'audio/mpeg', tamanho_bytes: 2048, sha256: 'a'.repeat(64),
    grupo_versao: 'preview-group', versao: 1, substitui_arquivo_id: null,
    enviado_por_mim: false, created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
}, {
    id: 8, producao_id: 1, tipo: 'material', nome_exibicao: 'voz.wav', mime_type: 'audio/wav',
    tamanho_bytes: 1024, sha256: 'b'.repeat(64), grupo_versao: 'material-group', versao: 1,
    substitui_arquivo_id: null, enviado_por_mim: true,
    created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
}, {
    id: 9, producao_id: 2, tipo: 'entrega', nome_exibicao: 'final.wav', mime_type: 'audio/wav',
    tamanho_bytes: 4096, sha256: 'c'.repeat(64), grupo_versao: 'delivery-group', versao: 1,
    substitui_arquivo_id: null, enviado_por_mim: false,
    created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
}];

const finances = new Map([
    [1, {
        producao_id: 1, proposta_numero: 'PROP-001', proposta_status: 'aceita',
        checkout_url: 'https://miraihitstudio.com.br/checkout/11111111-1111-1111-1111-111111111111',
        cobranca: { status: 'parcialmente_paga', valor_total: '1000.00', valor_pago: '500.00', saldo_pendente: '500.00', moeda: 'BRL', vencimento: null, pagamentos: [] },
    }],
    [2, { producao_id: 2, proposta_numero: null, proposta_status: null, checkout_url: null, cobranca: null }],
]);

async function staticResponse(route) {
    const url = new URL(route.request().url());
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/cliente' || pathname.startsWith('/cliente/')) pathname = '/portal-cliente.html';
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
    const redirects = await fs.readFile(path.join(root, '_redirects'), 'utf8');
    assert.match(redirects, /^\/cliente \/portal-cliente 200$/m);
    assert.match(redirects, /^\/cliente\/\* \/portal-cliente 200$/m);

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

        const user = { id: 4, username: 'client-a', role: loginRole, is_admin: loginRole === 'admin', ativo: true, cliente_id: loginRole === 'cliente' ? 1 : null };
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'synthetic-client-token', user } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: user });
        if (url.pathname === '/portal/cliente/producoes' && request.method() === 'GET') {
            return route.fulfill(failList ? { status: 500, json: { detail: 'Falha controlada da API.' } } : { json: productions });
        }
        const financial = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/financeiro$/);
        if (financial) return route.fulfill({ json: finances.get(Number(financial[1])) });
        const fileList = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/arquivos$/);
        if (fileList && request.method() === 'GET') {
            return route.fulfill({ json: files.filter(file => file.producao_id === Number(fileList[1])) });
        }
        if (fileList && request.method() === 'POST') {
            uploads++;
            const uploaded = { ...files[1], id: 10, nome_exibicao: 'nova-voz.wav', versao: 2, substitui_arquivo_id: 8 };
            files.push(uploaded);
            return route.fulfill({ status: 201, json: uploaded });
        }
        if (/^\/portal\/cliente\/arquivos\/\d+\/conteudo$/.test(url.pathname)) {
            return route.fulfill({ body: 'synthetic-audio', contentType: 'audio/mpeg', headers: { 'content-disposition': "attachment; filename*=UTF-8''preview.mp3" } });
        }
        const detail = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)$/);
        if (detail) {
            const item = productions.find(entry => entry.id === Number(detail[1]));
            return route.fulfill(item ? { json: item } : { status: 404, json: { detail: 'Producao nao encontrada.' } });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await page.goto('http://localhost:4173/cliente');
        await page.locator('#username').fill('client-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForSelector('.producer-metric');
        assert.equal(await page.locator('.producer-metric').count(), 4);
        const metrics = await page.locator('#client-metrics').textContent();
        assert.match(metrics, /Projetos em andamento1/);
        assert.match(metrics, /Projetos concluídos1/);
        assert.match(metrics, /Pagamentos pendentes1/);
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `client-dashboard-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
        }

        await page.getByRole('link', { name: 'Meus projetos' }).click();
        await page.waitForURL('**/cliente/projetos');
        assert.equal(await page.locator('#client-list .producer-card').count(), 2);
        assert.equal(await page.locator('#client-list img, #client-list script').count(), 0);
        const unsafeCard = page.locator('#client-list .producer-card').filter({ hasText: '<img src=x' });
        await unsafeCard.getByRole('button', { name: 'Abrir projeto' }).click();
        await page.waitForURL('**/cliente/projetos/1');
        assert.equal(await page.getByRole('heading', { name: '<img src=x onerror=alert(1)>' }).count(), 1);
        assert.equal(await page.locator('.producer-file img, .producer-file script').count(), 0);
        assert.match(await page.locator('.producer-file').first().textContent(), /<script>preview<\/script>/);
        assert.match(await page.locator('.client-finance-grid').textContent(), /R\$\s*1\.000,00/);
        assert.equal(await page.getByRole('link', { name: 'Ir para pagamento' }).count(), 1);

        await page.getByRole('button', { name: 'Reproduzir' }).click();
        await page.waitForSelector('audio.client-player', { state: 'attached' });
        assert.equal(await page.locator('audio.client-player').count(), 1);

        await page.getByLabel('Arquivo para enviar').setInputFiles({ name: 'nova-voz.wav', mimeType: 'audio/wav', buffer: Buffer.from('RIFF-client') });
        await page.getByLabel('Versão substituída').selectOption('8');
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Nova versão'));
        assert.equal(uploads, 1);
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `client-detail-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
        }

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }

        await page.getByRole('button', { name: 'Sair' }).click();
        assert.equal(await page.locator('#login-panel').isVisible(), true);

        productions = [];
        await page.goto('http://localhost:4173/cliente');
        await page.locator('#username').fill('client-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForSelector('.producer-metric');
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        assert.match(await page.locator('#client-list').textContent(), /ainda não possui projetos/);
        await page.getByRole('button', { name: 'Sair' }).click();

        loginRole = 'produtor';
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('login-error').textContent.includes('exclusiva'));
        assert.equal(await page.locator('#admin-area').isVisible(), false);

        loginRole = 'cliente';
        failList = true;
        await page.locator('#username').fill('client-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Falha controlada'));
        assert.equal(await page.locator('#client-loading').isVisible(), false);

        assert.deepEqual(errors, []);
        console.log('PASS: client login, dashboard, projects, files, preview, finance, safe text, errors and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
