const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const now = Date.now();
let loginRole = 'cliente';
let failList = false;
let uploads = 0;
let failFileList = false;
let uploadFailure = null;
let slowUpload = false;
let failFinance = false;
let lastUploadBody = '';
let portalSettings = null;
const messages = [{ id: 1, producao_id: 1, autor_papel: 'produtor', enviado_por_mim: false, audiencia: 'todos', texto: 'Prévia nova <img src=x onerror=alert(3)>', responde_a_id: null, arquivo: { id: 7, nome_exibicao: 'mix.mp3', tipo: 'previa', versao: 1 }, created_at: new Date(now).toISOString() }];
const messagePosts = [];
let proposals = [{
    id: 11,
    numero: 'PROP-CLIENT-011',
    versao: 1,
    status: 'enviada',
    servico: 'Produção musical',
    objeto: '<img src=x onerror=alert(2)>',
    descricao: 'Proposta sintética segura.',
    itens: [{ descricao: 'Produção musical', quantidade: '1', valor_unitario: '1200.00', desconto: '0.00' }],
    totais: { subtotal: '1200.00', desconto: '0.00', total: '1200.00' },
    politica_pagamento: 'entrada_50_50',
    condicoes: 'Entrada de 50% para início.',
    documento_disponivel: true,
    situacao_comercial: 'aguardando_aceite',
    cobranca_status: null,
    enviada_em: new Date(now).toISOString(),
    aprovada_em: null,
    created_at: new Date(now).toISOString(),
    updated_at: new Date(now).toISOString(),
}];
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
    enviado_por_mim: false, observacao: 'Mix v1 <b>com voz guia</b>', created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString(),
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
}, {
    // Roadmap 5.14: final delivery held until the balance is paid.
    id: 20, producao_id: 1, tipo: 'entrega', nome_exibicao: 'master-final.wav', mime_type: 'audio/wav',
    tamanho_bytes: 4096, sha256: 'd'.repeat(64), grupo_versao: 'held-group', versao: 1,
    substitui_arquivo_id: null, enviado_por_mim: false, bloqueado_pagamento: true,
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
    if (pathname === '/checkout') pathname = '/checkout.html';
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
    assert.match(redirects, /^\/cliente \/portal-cliente 200$/m);
    assert.match(redirects, /^\/cliente\/\* \/portal-cliente 200$/m);

    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1024, height: 800 }, serviceWorkers: 'block' });
    await context.addInitScript(() => {
        const listeners = new Set();
        const emit = task => listeners.forEach(listener => listener({ data: { type: 'mirai-upload-task', task } }));
        const registration = { active: { postMessage: message => {
            if (message.type === 'mirai-upload-list') return;
            const task = { id: message.id, label: message.label, owner: message.owner, meta: message.meta,
                status: 'uploading', message: 'Aguardando envio.', createdAt: Date.now(), updatedAt: Date.now() };
            emit(task);
            setTimeout(async () => {
                const body = new FormData();
                message.entries.forEach(([name, value]) => body.append(name, value));
                const response = await fetch(message.url, {
                    method: message.method,
                    headers: { Authorization: `Bearer ${message.token}` },
                    body,
                });
                task.status = response.ok ? 'completed' : 'failed';
                task.message = response.ok ? 'Envio concluído.' : 'O envio foi recusado.';
                task.updatedAt = Date.now();
                emit(task);
            }, 0);
        } } };
        Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: {
            register: async () => registration,
            ready: Promise.resolve(registration),
            addEventListener: (type, listener) => { if (type === 'message') listeners.add(listener); },
        } });
    });
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
        if (url.pathname === '/servicos') return route.fulfill({ json: [{ id: 5, nome: 'Mixagem' }] });
        if (url.pathname === '/portal/cliente/solicitacoes' && request.method() === 'POST') {
            const payload = request.postDataJSON();
            assert.deepEqual(Object.keys(payload).sort(), ['descricao', 'request_id', 'servico_id', 'titulo']);
            assert.equal(payload.servico_id, 5);
            assert.equal(payload.titulo, 'Novo single');
            assert.match(payload.request_id, /^[0-9a-f-]{36}$/);
            return route.fulfill({ status: 201, json: { id: 82, status: 'novo' } });
        }
        if (url.pathname === '/portal/cliente/propostas' && request.method() === 'GET') {
            return route.fulfill({ json: proposals });
        }
        const proposalDocument = url.pathname.match(/^\/portal\/cliente\/propostas\/(\d+)\/documento$/);
        if (proposalDocument) {
            return route.fulfill({
                body: '%PDF-1.4 synthetic',
                contentType: 'application/pdf',
                headers: { 'content-disposition': "attachment; filename*=UTF-8''proposta-11-v1.pdf" },
            });
        }
        const proposalAction = url.pathname.match(/^\/portal\/cliente\/propostas\/(\d+)\/(aceitar|recusar)$/);
        if (proposalAction && request.method() === 'POST') {
            const proposal = proposals.find(item => item.id === Number(proposalAction[1]));
            proposal.status = proposalAction[2] === 'aceitar' ? 'aceita' : 'recusada';
            proposal.situacao_comercial = proposal.status === 'aceita' ? 'aguardando_pagamento' : 'recusada';
            return route.fulfill({ json: proposal });
        }
        const proposalDetail = url.pathname.match(/^\/portal\/cliente\/propostas\/(\d+)$/);
        if (proposalDetail) {
            const proposal = proposals.find(item => item.id === Number(proposalDetail[1]));
            return route.fulfill(proposal ? { json: proposal } : { status: 404, json: { detail: 'Proposta nao encontrada.' } });
        }
        // Roadmap 5.06: production 1 has contract stages; the client view has no values or actions.
        const clientStages = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/etapas$/);
        if (clientStages && request.method() === 'GET') {
            if (Number(clientStages[1]) !== 1) return route.fulfill({ status: 404, json: { detail: 'Not found' } });
            return route.fulfill({ json: { producao_id: 1, progresso_percentual: 50, etapas: [
                { id: 41, ordem: 1, item_indice: 1, item_descricao: 'Mixagem', ordem_no_item: 1, nome: 'Rough Mix', status: 'concluida',
                  prazo: null, iniciada_em: null, concluida_em: new Date().toISOString(), depende_da_anterior: false, administrativa: false },
                { id: 42, ordem: 2, item_indice: 1, item_descricao: 'Mixagem', ordem_no_item: 2, nome: 'Mix <i>final</i>', status: 'em_andamento',
                  prazo: new Date(Date.now() + 5 * 86400000).toISOString(), iniciada_em: null, concluida_em: null,
                  depende_da_anterior: true, administrativa: false },
            ] } });
        }
        const thread = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/mensagens$/);
        if (thread && request.method() === 'GET') return route.fulfill({ json: messages.filter(item => item.producao_id === Number(thread[1])) });
        if (thread && request.method() === 'POST') {
            const body = request.postDataJSON();
            messagePosts.push(body);
            const created = { id: messages.length + 1, producao_id: Number(thread[1]), autor_papel: 'cliente', enviado_por_mim: true, audiencia: 'todos', texto: body.texto, responde_a_id: body.responde_a_id, arquivo: null, created_at: new Date().toISOString() };
            messages.push(created);
            return route.fulfill({ status: 201, json: created });
        }
        if (url.pathname === '/portal/cliente/configuracao') {
            return route.fulfill(portalSettings ? { json: { portal: 'cliente', versao: 4, config: portalSettings } } : { status: 503, json: { detail: 'indisponível' } });
        }
        if (url.pathname === '/portal/cliente/beats') {
            return route.fulfill({ json: [{ id: 71, produtor_id: 2, produtor: '<Producer>', titulo: '<Horizonte>', descricao: '', bpm: 140, tonalidade: 'Am', generos: 'Trap', preco_lease: '100.00', preco_exclusivo: '500.00', status: 'aprovado', ativo: true, motivo_rejeicao: null, created_at: new Date().toISOString() }] });
        }
        if (url.pathname === '/portal/cliente/beats/adquiridos') {
            return route.fulfill({ json: [] });
        }
        if (url.pathname === '/beats/71/preview') {
            return route.fulfill({ body: 'ID3synthetic-preview', contentType: 'audio/mpeg' });
        }
        if (url.pathname === '/portal/cliente/beats/71/solicitar' && request.method() === 'POST') {
            assert.equal(request.postDataJSON().licenca, 'lease');
            assert.match(request.headers()['idempotency-key'], /^[0-9a-f-]{36}$/);
            return route.fulfill({ status: 201, json: { id: 91, status: 'aceita', checkout_path: '/checkout?proposta=91' } });
        }
        if (url.pathname === '/portal/cliente/producoes' && request.method() === 'GET') {
            return route.fulfill(failList ? { status: 500, json: { detail: 'Falha controlada da API.' } } : { json: productions });
        }
        const financial = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/financeiro$/);
        if (financial) {
            if (failFinance) return route.fulfill({ status: 503, json: { detail: 'Financeiro indisponível.' } });
            return route.fulfill({ json: finances.get(Number(financial[1])) });
        }
        const fileList = url.pathname.match(/^\/portal\/cliente\/producoes\/(\d+)\/arquivos$/);
        if (fileList && request.method() === 'GET') {
            if (failFileList) return route.fulfill({ status: 503, json: { detail: 'Lista indisponível.' } });
            return route.fulfill({ json: files.filter(file => file.producao_id === Number(fileList[1])) });
        }
        if (fileList && request.method() === 'POST') {
            uploads++;
            lastUploadBody = request.postData() || '';
            if (slowUpload) await new Promise(resolve => setTimeout(resolve, 200));
            if (uploadFailure === 'network') return route.abort();
            if (uploadFailure) return route.fulfill({ status: uploadFailure, json: { detail: 'Falha controlada.' } });
            const uploaded = { ...files[1], id: 9 + uploads, nome_exibicao: request.postData()?.includes('nome-longo') ? 'nome-longo.wav' : 'nova-voz.wav', versao: 1 + uploads, substitui_arquivo_id: 8 };
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
        await signIn(page, { next: '/cliente', username: 'client-a' });
        await page.waitForSelector('.producer-metric');
        if (process.env.VISUAL_OUTPUT) {
            for (const width of [390, 1440]) {
                await page.setViewportSize({ width, height: 900 });
                await page.screenshot({
                    path: path.join(process.env.VISUAL_OUTPUT, `client-overview-${width}.png`),
                    fullPage: true,
                    animations: 'disabled',
                });
            }
            await page.setViewportSize({ width: 1024, height: 800 });
        }
        assert.equal(await page.locator('.producer-metric').count(), 4);
        const metrics = await page.locator('#client-metrics').textContent();
        assert.match(metrics, /Projetos em andamento1/);
        assert.match(metrics, /Projetos concluídos1/);
        assert.match(metrics, /Pagamentos pendentes1/);
        await page.locator('#client-dashboard [data-new-production]').click();
        const requestDialog = page.getByRole('dialog', { name: 'Nova produção' });
        await requestDialog.getByLabel('Título').fill('Novo single');
        await requestDialog.getByLabel('Serviço').selectOption('5');
        await requestDialog.getByLabel('Conte sobre o projeto').fill('Preciso de uma mixagem.');
        await requestDialog.getByRole('button', { name: 'Enviar para análise' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert')?.textContent.includes('Solicitação #82 enviada'));
        assert.equal(await requestDialog.isVisible(), false);
        assert.equal(new URL(page.url()).pathname, '/cliente');
        await page.getByRole('link', { name: 'Explorar' }).click();
        await page.waitForURL('**/cliente/explorar');
        assert.equal(await page.getByRole('link', { name: 'Projetos', exact: true }).getAttribute('href'), '/portfolio');
        assert.match(await page.locator('#client-beats').textContent(), /Catálogo de beats/);
        await page.waitForSelector('#client-beats-list .producer-card');
        assert.match(await page.locator('#client-beats-list').textContent(), /<Horizonte>/);
        assert.equal(await page.locator('#client-acquired-beats-section').isVisible(), false);
        assert.equal(await page.locator('#client-beats-list script, #client-beats-list img').count(), 0);
        await page.waitForFunction(() => !document.querySelector('#client-beats-list .beat-preview__play').disabled);
        const beatBox = await page.locator('#client-beats-list .beat-card').boundingBox();
        assert.ok(Math.abs(beatBox.width - beatBox.height) < 2, 'client beat card must remain square');
        assert.equal(await page.locator('#client-beats-list .client-beat-card__content').evaluate(element => (
            element.scrollHeight <= element.clientHeight && element.scrollWidth <= element.clientWidth
        )), true, 'client beat content must fit inside the square');
        await page.getByRole('button', { name: /MP3 lease/ }).click();
        await page.waitForURL('**/checkout?proposta=91');
        await page.goBack();
        await page.waitForURL('**/cliente/explorar');
        await page.getByRole('link', { name: 'Dashboard' }).click();
        assert.equal(await page.locator('#client-proposal-summary').isVisible(), true);
        await page.getByRole('link', { name: 'Propostas', exact: true }).click();
        await page.waitForURL('**/cliente/propostas');
        await page.getByRole('button', { name: 'Abrir proposta' }).click();
        await page.waitForURL('**/cliente/propostas/11');
        await page.waitForFunction(() => (
            document.getElementById('client-proposal-detail-content')
                ?.textContent.includes('<img src=x onerror=alert(2)>')
        ));
        assert.equal(await page.locator('#client-proposal-detail-content img').count(), 0);
        assert.match(await page.locator('#client-proposal-detail-content').textContent(), /<img src=x onerror=alert\(2\)>/);
        assert.match(await page.locator('#client-proposal-detail-content').textContent(), /R\$\s*1\.200,00/);
        const proposalDownloadPromise = page.waitForEvent('download');
        await page.getByRole('button', { name: 'Baixar PDF' }).click();
        assert.match((await proposalDownloadPromise).suggestedFilename(), /^proposta-11(?:-v1)?\.pdf$/);
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', { name: 'Aceitar proposta' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Proposta aceita'));
        assert.equal(await page.getByRole('button', { name: 'Aceitar proposta' }).count(), 0);
        await page.setViewportSize({ width: 390, height: 900 });
        const clientMenu = page.locator('.integrado-portal__menu-toggle');
        await clientMenu.click();
        assert.equal(await clientMenu.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#client-navigation').isVisible(), true);
        await page.keyboard.press('Escape');
        assert.equal(await clientMenu.getAttribute('aria-expanded'), 'false');
        for (const width of [320, 375, 390, 768, 1024, 1366, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
            const geometry = await page.evaluate(() => {
                const sidebar = document.querySelector('.producer-sidebar').getBoundingClientRect();
                const navigation = document.querySelector('#client-navigation').getBoundingClientRect();
                const workspace = document.querySelector('.producer-workspace').getBoundingClientRect();
                return {
                    sidebarLeft: sidebar.left,
                    sidebarRight: sidebar.right,
                    sidebarBottom: sidebar.bottom,
                    navigationLeft: navigation.left,
                    navigationRight: navigation.right,
                    workspaceLeft: workspace.left,
                    workspaceTop: workspace.top,
                };
            });
            if (width >= 768) {
                assert.ok(geometry.navigationLeft >= geometry.sidebarLeft - 1, JSON.stringify({ width, geometry }));
                assert.ok(geometry.navigationRight <= geometry.sidebarRight + 1, JSON.stringify({ width, geometry }));
                assert.ok(geometry.sidebarRight <= geometry.workspaceLeft + 1, JSON.stringify({ width, geometry }));
            } else {
                assert.ok(geometry.sidebarBottom <= geometry.workspaceTop + 1, JSON.stringify({ width, geometry }));
            }
        }
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
        // AUD6-S07-001: section shortcuts, with the pending payment reachable from the top.
        const sections = page.getByRole('navigation', { name: 'Seções do projeto' });
        assert.deepEqual(await sections.getByRole('button').allTextContents(), ['Visão geral', 'Arquivos', 'Mensagens', 'Pagamento pendente']);
        await page.locator('#project-section-overview').getByRole('button', { name: 'Ver pagamento' }).click();
        await page.waitForFunction(() => document.activeElement?.closest('#project-section-payment'));
        await sections.getByRole('button', { name: 'Arquivos' }).click();
        await page.waitForFunction(() => document.activeElement?.closest('#project-section-files'));

        // Roadmap 5.14: the held delivery shows its state and the payment link, never a download.
        const heldFile = page.locator('.producer-file').filter({ hasText: 'master-final.wav' });
        assert.match(await heldFile.textContent(), /aguardando a quitação do saldo/);
        assert.equal(await heldFile.getByRole('button', { name: 'Baixar' }).count(), 0);
        assert.equal(await heldFile.getByRole('link', { name: 'Pagar saldo e liberar' }).getAttribute('href'),
            'https://miraihitstudio.com.br/checkout/11111111-1111-1111-1111-111111111111');
        assert.match(await page.locator('.client-file-group').filter({ hasText: 'Entregas finais' }).textContent(),
            /liberados após a quitação do saldo/);

        // Roadmap 5.06: contract stages replace the legacy list, read-only and without values.
        await page.waitForSelector('#production-stages-panel .production-stages');
        const clientStagePanel = page.locator('#production-stages-panel');
        assert.match(await clientStagePanel.textContent(), /50% concluído/);
        assert.match(await clientStagePanel.textContent(), /Mix <i>final<\/i>.*Em andamento.*Prazo:/s);
        assert.match(await clientStagePanel.locator('.production-stage').first().textContent(), /Concluída/);
        assert.equal(await clientStagePanel.locator('button, i').count(), 0);
        assert.doesNotMatch(await clientStagePanel.textContent(), /R\$|revisões/);
        assert.equal(await clientStagePanel.getByRole('progressbar').getAttribute('aria-valuenow'), '50');

        // Roadmap 5.03: thread renders as text, replies and sends without audience choice.
        await page.waitForSelector('.production-message');
        assert.equal(await page.locator('.production-messages img').count(), 0);
        assert.match(await page.locator('.production-message').first().textContent(), /Produção.*Prévia nova <img src=x onerror=alert\(3\)>.*Arquivo: mix\.mp3 \(v1\)/s);
        assert.equal(await page.getByLabel('Quem pode ver').count(), 0);
        await page.locator('.production-message').first().getByRole('button', { name: 'Responder' }).click();
        await page.getByLabel('Escreva uma mensagem').fill('Ficou ótimo, pode seguir.');
        await page.getByRole('button', { name: 'Enviar mensagem' }).click();
        await page.waitForFunction(() => document.querySelectorAll('.production-message').length === 2);
        assert.deepEqual(messagePosts[0], { texto: 'Ficou ótimo, pode seguir.', audiencia: 'todos', responde_a_id: 1, arquivo_id: null });
        assert.match(await page.locator('.production-message').nth(1).textContent(), /Você.*Em resposta a: Prévia nova/s);

        await page.getByRole('button', { name: 'Reproduzir' }).click();
        await page.waitForSelector('audio.client-player', { state: 'attached' });
        assert.equal(await page.locator('audio.client-player').count(), 1);

        const longName = `${'nome-longo-'.repeat(18)}.wav`;
        await page.getByLabel('Arquivo para enviar').setInputFiles({ name: longName, mimeType: 'audio/wav', buffer: Buffer.from('RIFF-client') });
        for (const width of [1440, 1024, 768, 390, 320]) {
            await page.setViewportSize({ width, height: 800 });
            const bounds = await page.evaluate(() => {
                const form = document.querySelector('.producer-upload').getBoundingClientRect();
                const controls = [...document.querySelector('.producer-upload').children]
                    .filter(element => !element.classList.contains('producer-upload__feedback') && element.getClientRects().length)
                    .map(element => ({ left: element.getBoundingClientRect().left, right: element.getBoundingClientRect().right }));
                return { left: form.left, right: form.right, controls, scrollWidth: document.documentElement.scrollWidth, viewport: innerWidth };
            });
            assert.ok(bounds.scrollWidth <= bounds.viewport, JSON.stringify({ width, bounds }));
            assert.ok(bounds.controls.every(item => item.left >= bounds.left - 1 && item.right <= bounds.right + 1), JSON.stringify({ width, bounds }));
            assert.equal(await page.locator('.producer-upload__filename').getAttribute('title'), longName);
        }
        // Roadmap 5.02: version notes are shown as text and sent with the upload.
        assert.match(await page.locator('.producer-file').first().textContent(), /Observação da equipe: Mix v1 <b>com voz guia<\/b>/);
        assert.equal(await page.locator('.file-note b').count(), 0);
        await page.getByLabel('Observação para esta versão').fill('Voz regravada no take 3');
        await page.getByLabel('Versão substituída').selectOption('8');
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.querySelector('.producer-upload__feedback')?.textContent.includes('Envio iniciado'));
        await page.getByRole('button', { name: /^Envios/ }).click();
        await page.waitForFunction(() => document.querySelector('.upload-tasks-dialog')?.textContent.includes('Concluído'));
        assert.equal(uploads, 1);
        assert.match(lastUploadBody, /name="observacao"[\s\S]*Voz regravada no take 3/);
        await page.getByRole('button', { name: 'Fechar' }).click();

        // AUD-S07-001: a finance failure keeps the project and its files available.
        await page.setViewportSize({ width: 1024, height: 800 });
        failFinance = true;
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        await page.waitForURL('**/cliente/projetos');
        await page.locator('#client-list .producer-card').filter({ hasText: '<img src=x' })
            .getByRole('button', { name: 'Abrir projeto' }).click();
        await page.waitForURL('**/cliente/projetos/1');
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('informações de pagamento'));
        assert.equal(await page.getByRole('heading', { name: '<img src=x onerror=alert(1)>' }).count(), 1);
        assert.ok(await page.locator('.producer-file').count() > 0);
        assert.match(await page.locator('.client-finance-grid').textContent(), /R\$\s*1\.000,00/);
        failFinance = false;
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

        // AUD6-S02-003: "Sair" sends the client to the single access page.
        const signedOut = await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());
        assert.match(signedOut.params.get('next'), /^\/cliente(\/|$)/);

        productions = [];
        await signIn(page, { next: '/cliente', username: 'client-a' });
        await page.waitForSelector('.producer-metric');
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        assert.match(await page.locator('#client-list').textContent(), /ainda não possui projetos/);
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());

        // A producer who follows a client link is taken to the producer area, never into this portal.
        loginRole = 'produtor';
        const producerArea = url => url.pathname === '/produtor';
        await page.route(producerArea, route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Produtor</title>' }));
        await page.goto(`http://localhost:4173/acesso.html?next=${encodeURIComponent('/cliente/projetos')}`);
        await page.locator('#access-login-form #username').fill('producer-a');
        await page.locator('#access-login-form #password').fill('synthetic-password');
        await Promise.all([
            page.waitForURL(producerArea),
            page.locator('#access-login-form button[type=submit]').click(),
        ]);
        assert.equal(await page.evaluate(() => localStorage.getItem('mirai.auth.cliente.access_token')), null);
        await page.evaluate(() => localStorage.removeItem('mirai.auth.produtor.access_token'));
        await page.unroute(producerArea);

        loginRole = 'cliente';
        failList = true;
        await signIn(page, { next: '/cliente', username: 'client-a' });
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Falha controlada'));
        assert.equal(await page.locator('#client-loading').isVisible(), false);

        // Roadmap 5.01: published settings drive notice, texts, indicators, filters and areas.
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());
        failList = false;
        productions = [{ id: 1, titulo: 'Faixa A', servico: 'Mixagem', status: 'revisao', etapas: '[]', prazo_entrega: null, created_at: new Date(now).toISOString(), updated_at: new Date(now).toISOString() }];
        portalSettings = {
            aviso: { ativo: true, nivel: 'atencao', texto: 'Recesso <b>de fim de ano</b>' },
            textos: { titulo_dashboard: 'Seu estúdio', descricao_dashboard: '', ajuda_arquivos: 'Envie stems em WAV.' },
            indicadores: ['pagamentos', 'andamento'],
            filtros: { situacao_padrao: 'ativos', ordenacao_padrao: 'prazo' },
            areas: { propostas: false },
        };
        await signIn(page, { next: '/cliente', username: 'client-a' });
        await page.waitForFunction(() => document.getElementById('client-loading').classList.contains('hidden'));
        await page.getByRole('link', { name: 'Dashboard' }).click();
        await page.waitForSelector('#client-metrics .producer-metric');
        assert.equal(await page.locator('#client-notice').textContent(), 'Recesso <b>de fim de ano</b>');
        assert.equal(await page.locator('#client-notice b').count(), 0);
        assert.equal(await page.locator('#client-notice').getAttribute('data-level'), 'atencao');
        assert.equal(await page.locator('#dashboard-title').textContent(), 'Seu estúdio');
        assert.equal(await page.locator('#client-dashboard-lead').isVisible(), false);
        assert.deepEqual(await page.locator('#client-metrics dt').allTextContents(), ['Pagamentos pendentes', 'Projetos em andamento']);
        assert.equal(await page.locator('#client-proposals-link').isVisible(), false);
        assert.equal(await page.locator('#client-proposal-summary').isVisible(), false);
        assert.equal(await page.locator('#client-status-filter').inputValue(), 'ativos');
        assert.equal(await page.locator('#client-order').inputValue(), 'prazo');
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        await page.locator('#client-list .producer-card').getByRole('button', { name: 'Abrir projeto' }).click();
        await page.waitForURL('**/cliente/projetos/1');
        assert.match(await page.locator('.producer-files').first().textContent(), /Envie stems em WAV\./);

        assert.deepEqual(errors, []);
        console.log('PASS: client login, dashboard, projects, files, preview, finance, safe text, errors and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
