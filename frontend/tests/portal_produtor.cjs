const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const now = Date.now();
let loginRole = 'produtor';
let failList = false;
let failPayouts = false;
let lastUploadBody = '';
let portalSettings = null;
const threadPosts = [];
let threadFails = true;
let beatUploads = 0;
// Roadmap 5.06: contract stages of production 1 (server-decided actions, no values).
const PRODUCER_ACTIONS = { pendente: ['em_andamento'], em_andamento: ['em_revisao'], em_revisao: ['em_andamento'], concluida: [] };
const stagePatches = [];
let stageConflict = true;
const stageData = {
    producao_id: 1,
    progresso_percentual: 20,
    etapas: [
        { id: 31, ordem: 1, item_indice: 1, item_descricao: 'Plano Start', ordem_no_item: 1, nome: 'Briefing', status: 'pendente',
          prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: false, administrativa: true, unidade: '',
          revisoes_incluidas: null, prazo_dias: null, acoes: ['em_andamento'] },
        { id: 32, ordem: 2, item_indice: 1, item_descricao: 'Plano Start', ordem_no_item: 2, nome: 'Rough <b>Mix</b>', status: 'em_andamento',
          prazo: new Date(now + 3 * 86400000).toISOString(), iniciada_em: new Date(now).toISOString(), concluida_em: null,
          depende_da_anterior: false, administrativa: false, unidade: 'faixa', revisoes_incluidas: 2, prazo_dias: 3, acoes: ['em_revisao'] },
        { id: 33, ordem: 3, item_indice: 1, item_descricao: 'Plano Start', ordem_no_item: 3, nome: 'Mixagem', status: 'pendente',
          prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: true, administrativa: false, unidade: 'faixa',
          revisoes_incluidas: null, prazo_dias: null, acoes: [] },
    ],
};
let uploads = 0;
let productions = [
    {
        id: 1,
        titulo: '<img src=x onerror=alert(1)>',
        cliente: '<script>Cliente A</script>',
        contato_cliente: { nome: '<img src=x onerror=alert(1)> Cliente',
            email: 'cliente.sintetico.com.endereco.longo.para.testar.quebras@example.test', whatsapp: '(11) 99999-0000' },
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
}, {
    id: 8, producao_id: 1, remetente_usuario_id: 2, tipo: 'previa',
    nome_exibicao: 'historical.mp3', mime_type: 'audio/mpeg', tamanho_bytes: 1024,
    sha256: 'b'.repeat(64), grupo_versao: 'historical-group', versao: 1,
    substitui_arquivo_id: null, visivel_produtor: true, visivel_cliente: false,
    observacao: 'Primeira ideia <i>sem master</i>',
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
    if (pathname === '/produtor' || pathname.startsWith('/produtor/')) pathname = '/portal-produtor.html';
    const file = path.resolve(root, '.' + pathname);
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html',
                '.png': 'image/png', '.webp': 'image/webp', '.svg': 'image/svg+xml', '.ttf': 'font/ttf',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const redirects = await fs.readFile(path.join(root, '_redirects'), 'utf8');
    assert.match(redirects, /^\/produtor \/portal-produtor 200$/m);
    assert.match(redirects, /^\/produtor\/\* \/portal-produtor 200$/m);

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

        const user = { id: 2, username: 'producer-a', role: loginRole, is_admin: loginRole === 'admin', ativo: true, painel_beats: true };
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'synthetic-producer-token', user } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: user });
        const stageList = url.pathname.match(/^\/portal\/produtor\/producoes\/(\d+)\/etapas$/);
        if (stageList && request.method() === 'GET') {
            return route.fulfill(Number(stageList[1]) === 1 ? { json: stageData } : { status: 404, json: { detail: 'Not found' } });
        }
        const stageUpdate = url.pathname.match(/^\/portal\/produtor\/producoes\/1\/etapas\/(\d+)$/);
        if (stageUpdate && request.method() === 'PATCH') {
            const body = request.postDataJSON();
            stagePatches.push({ id: Number(stageUpdate[1]), ...body });
            if (stageConflict) {
                stageConflict = false;
                return route.fulfill({ status: 409, json: { detail: 'A etapa foi atualizada por outra pessoa. Recarregue antes de continuar.' } });
            }
            const stage = stageData.etapas.find(item => item.id === Number(stageUpdate[1]));
            Object.assign(stage, { status: body.status, acoes: PRODUCER_ACTIONS[body.status] });
            return route.fulfill({ json: stageData });
        }
        const thread = url.pathname.match(/^\/portal\/produtor\/producoes\/(\d+)\/mensagens$/);
        if (thread && request.method() === 'GET') {
            if (threadFails) return route.fulfill({ status: 503, json: { detail: 'indisponível' } });
            return route.fulfill({ json: threadPosts.map((body, index) => ({ id: index + 1, producao_id: 1, autor_papel: 'produtor', enviado_por_mim: true, audiencia: body.audiencia, texto: body.texto, responde_a_id: null, arquivo: null, created_at: new Date().toISOString() })) });
        }
        if (thread && request.method() === 'POST') {
            threadPosts.push(request.postDataJSON());
            return route.fulfill({ status: 201, json: {} });
        }
        if (url.pathname === '/portal/produtor/configuracao') {
            return route.fulfill(portalSettings ? { json: { portal: 'produtor', versao: 2, config: portalSettings } } : { status: 503, json: { detail: 'indisponível' } });
        }
        if (url.pathname === '/portal/produtor/beats' && request.method() === 'GET') {
            return route.fulfill({ json: [{ id: 71, produtor_id: 2, produtor: 'Producer A', titulo: '<Beat seguro>', descricao: '', bpm: 140, tonalidade: 'Am', generos: 'Trap', preco_lease: '100.00', preco_exclusivo: '500.00', status: 'revisao', ativo: true, motivo_rejeicao: null, created_at: new Date().toISOString() }] });
        }
        if (url.pathname === '/portal/produtor/beats' && request.method() === 'POST') {
            const body = request.postDataBuffer().toString('latin1');
            for (const field of ['titulo', 'mp3', 'capa', 'preco_lease']) {
                assert.match(body, new RegExp(`name="${field}"`));
            }
            assert.doesNotMatch(body, /name="(?:wav|multitrack)"/);
            beatUploads++;
            return route.fulfill({ status: 201, json: { id: 72, status: 'revisao' } });
        }
        if (url.pathname === '/portal/produtor/producoes' && request.method() === 'GET') {
            return route.fulfill(failList ? { status: 500, json: { detail: 'Falha controlada da API.' } } : { json: productions });
        }
        if (url.pathname === '/portal/produtor/repasses-etapas' && request.method() === 'GET') {
            return route.fulfill({ json: [] });
        }
        if (url.pathname === '/portal/produtor/repasses' && request.method() === 'GET') {
            if (failPayouts) return route.fulfill({ status: 503, json: { detail: 'Repasses indisponíveis.' } });
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
            lastUploadBody = request.postData() || '';
            files.push({ ...files[0], id: 10, tipo: 'previa', nome_exibicao: 'preview.mp3', versao: 1, visivel_cliente: true });
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
        await page.getByRole('link', { name: 'Beats' }).click();
        await page.waitForURL('**/produtor/beats');
        await page.waitForSelector('#producer-beats-list .producer-card');
        assert.match(await page.locator('#producer-beats-list').textContent(), /<Beat seguro>/);
        assert.equal(await page.locator('#producer-beats-list script, #producer-beats-list img').count(), 0);
        await page.getByLabel('Título').fill('Novo beat');
        await page.locator('#producer-beat-form [name="preco_lease"]').fill('120');
        await page.locator('#producer-beat-form [name="mp3"]').setInputFiles({ name: 'beat.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('ID3synthetic') });
        await page.locator('#producer-beat-form [name="capa"]').setInputFiles({ name: 'capa.png', mimeType: 'image/png', buffer: Buffer.from('synthetic-cover') });
        await page.getByRole('button', { name: 'Enviar para revisão' }).click();
        await page.waitForFunction(() => !document.querySelector('#producer-beat-form button[type=submit]')?.disabled);
        assert.equal(beatUploads, 1);
        await page.getByRole('link', { name: 'Dashboard' }).click();
        await page.setViewportSize({ width: 390, height: 900 });
        const producerMenu = page.locator('.integrado-portal__menu-toggle');
        await producerMenu.click();
        assert.equal(await producerMenu.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#producer-navigation').isVisible(), true);
        await page.keyboard.press('Escape');
        assert.equal(await producerMenu.getAttribute('aria-expanded'), 'false');
        await page.setViewportSize({ width: 1440, height: 900 });
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `producer-dashboard-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
        }

        await page.getByRole('link', { name: 'Minhas produções' }).click();
        await page.waitForURL('**/produtor/producoes');
        const productionCards = page.locator('#producer-list .producer-card');
        assert.equal(await productionCards.count(), 2);
        assert.equal(await page.locator('#producer-list .producer-card img, #producer-list .producer-card script').count(), 0);
        const unsafeCard = productionCards.filter({ hasText: '<img src=x' });
        assert.equal(await unsafeCard.count(), 1);

        await unsafeCard.getByRole('button', { name: 'Abrir detalhes' }).click();
        await page.waitForURL('**/produtor/producoes/1');
        const contact = page.locator('.producer-client-contact');
        await contact.waitFor();
        assert.match(await contact.textContent(), /<img src=x onerror=alert\(1\)> Cliente/);
        assert.equal(await contact.locator('img, script').count(), 0);
        assert.equal(await contact.getByRole('link', { name: 'Abrir WhatsApp' }).getAttribute('href'), 'https://wa.me/5511999990000');
        assert.equal(await contact.locator('a').first().getAttribute('href'), `mailto:${encodeURIComponent(productions[0].contato_cliente.email)}`);
        assert.equal(await page.getByRole('heading', { name: '<img src=x onerror=alert(1)>' }).count(), 1);
        assert.equal(await page.locator('.producer-file img, .producer-file script').count(), 0);
        assert.match(await page.locator('.producer-file').first().textContent(), /<img src=x>/);
        assert.match(await page.locator('.producer-file').filter({ hasText: 'historical.mp3' }).textContent(), /Não compartilhada com o cliente/);
        assert.match(await page.locator('.producer-file').filter({ hasText: 'historical.mp3' }).textContent(), /Sua observação: Primeira ideia <i>sem master<\/i>/);
        assert.equal(await page.locator('.file-note i').count(), 0);
        // Roadmap 5.06: contract stages replace the legacy checklist; producers send to review, never conclude.
        await page.waitForSelector('#production-stages-panel .production-stages');
        const stagesPanel = page.locator('#production-stages-panel');
        assert.equal(await stagesPanel.locator('.producer-progress').count(), 0);
        assert.equal(await stagesPanel.locator('b').count(), 0);
        assert.match(await stagesPanel.textContent(), /Rough <b>Mix<\/b>/);
        assert.match(await stagesPanel.textContent(), /20% concluído/);
        assert.doesNotMatch(await stagesPanel.textContent(), /R\$/);
        assert.equal(await stagesPanel.getByRole('button', { name: 'Aprovar e concluir' }).count(), 0);
        assert.match(await stagesPanel.locator('.production-stage').nth(2).textContent(), /Depende da etapa anterior/);
        assert.equal(await stagesPanel.locator('.production-stage').nth(2).locator('button').count(), 0);
        const review = stagesPanel.locator('.production-stage').nth(1).getByRole('button', { name: 'Enviar para revisão' });
        await review.click();
        await page.waitForFunction(() => document.querySelector('.production-stages__feedback')?.textContent.includes('Recarregue'));
        assert.equal(await review.isDisabled(), false);
        await review.click();
        await page.waitForFunction(() => document.querySelectorAll('#production-stages-panel .production-stage')[1]?.textContent.includes('Em revisão'));
        assert.deepEqual(stagePatches.at(-1), { id: 32, status: 'em_revisao', status_atual: 'em_andamento' });
        assert.equal(await stagesPanel.locator('.production-stage').nth(1).getByRole('button', { name: 'Retomar' }).count(), 1);

        // Roadmap 5.03: a thread failure never blocks the production; producers can post internal notes.
        await page.waitForFunction(() => document.querySelector('.production-messages__error')?.textContent.includes('mensagens'));
        threadFails = false;
        await page.getByLabel('Quem pode ver').selectOption('equipe');
        await page.getByLabel('Anexar referência a um arquivo').selectOption('9');
        await page.getByLabel('Escreva uma mensagem').fill('Nota interna para a equipe');
        await page.getByRole('button', { name: 'Enviar mensagem' }).click();
        await page.waitForFunction(() => document.querySelector('.production-message--team'));
        assert.deepEqual(threadPosts[0], { texto: 'Nota interna para a equipe', audiencia: 'equipe', responde_a_id: null, arquivo_id: 9 });
        assert.match(await page.locator('.production-message--team').textContent(), /Interna/);

        await page.getByLabel('Observação para esta versão').fill('Mix com graves reduzidos');
        await page.getByLabel('Arquivo para enviar').setInputFiles({ name: 'preview.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('preview') });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Prévia enviada ao cliente com sucesso!'));
        assert.equal(uploads, 1);
        assert.match(lastUploadBody, /name="observacao"[\s\S]*Mix com graves reduzidos/);
        assert.match(await page.locator('.producer-file').filter({ hasText: 'preview.mp3' }).textContent(), /Compartilhada com o cliente/);
        // AUD-S08-001: replacement options follow the selected type.
        const replacementValues = () => page.getByLabel('Versão substituída').locator('option')
            .evaluateAll(options => options.map(option => option.value));
        assert.deepEqual(await replacementValues(), ['', '8', '10']);
        await page.getByLabel('Tipo de arquivo').selectOption('entrega');
        assert.deepEqual(await replacementValues(), ['']);
        await page.getByLabel('Tipo de arquivo').selectOption('previa');
        await page.getByRole('button', { name: 'Confirmar início' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Andamento atualizado'));
        assert.equal(productions[0].status, 'em_producao');
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `producer-detail-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
        }

        productions[0].contato_cliente = null;
        await page.reload();
        await page.waitForSelector('#detail-title');
        assert.equal(await page.locator('.producer-client-contact').count(), 0);

        await page.getByRole('link', { name: 'Financeiro' }).click();
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
                    path: path.join(process.env.VISUAL_OUTPUT, `producer-finance-${width}.png`),
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

        // AUD-S08-002: a payout failure must not block the production workspace.
        loginRole = 'produtor';
        failPayouts = true;
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('repasses'));
        assert.equal(await page.locator('.producer-metric').count(), 5);
        failPayouts = false;
        await page.getByRole('button', { name: 'Sair' }).click();

        failList = true;
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Falha controlada'));
        assert.equal(await page.locator('#producer-loading').isVisible(), false);

        // Roadmap 5.01: published settings drive notice, texts, indicators and filters.
        await page.getByRole('button', { name: 'Sair' }).click();
        failList = false;
        portalSettings = {
            aviso: { ativo: true, nivel: 'info', texto: 'Novo fluxo de entregas a partir de segunda.' },
            textos: { descricao_dashboard: 'Foco nos prazos da semana.', ajuda_financeiro: 'Repasses às sextas.' },
            indicadores: ['vencidos', 'ativas'],
            filtros: { status_padrao: 'revisao', ordenacao_padrao: 'recente' },
        };
        await page.locator('#username').fill('producer-a');
        await page.locator('#password').fill('synthetic-password');
        await page.getByRole('button', { name: 'Entrar' }).click();
        await page.waitForFunction(() => document.getElementById('producer-loading').classList.contains('hidden'));
        await page.getByRole('link', { name: 'Dashboard' }).click();
        await page.waitForSelector('#producer-metrics .producer-metric');
        assert.equal(await page.locator('#producer-notice').textContent(), 'Novo fluxo de entregas a partir de segunda.');
        assert.equal(await page.locator('#producer-dashboard-lead').textContent(), 'Foco nos prazos da semana.');
        assert.deepEqual(await page.locator('#producer-metrics dt').allTextContents(), ['Prazos vencidos', 'Produções ativas']);
        assert.equal(await page.locator('#producer-status-filter').inputValue(), 'revisao');
        assert.equal(await page.locator('#producer-order').inputValue(), 'recente');
        assert.equal(await page.locator('#producer-finance-help').textContent(), 'Repasses às sextas.');

        assert.deepEqual(errors, []);
        console.log('PASS: producer login/logout, dashboard, list, detail, progress, safe text, errors and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
