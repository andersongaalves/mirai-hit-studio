const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, signIn } = require('./support/access.cjs');

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
const noteEdits = [];
const deletedFiles = [];
const listens = [];
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

        const user = { id: 2, username: 'producer-a', nome_exibicao: 'Ana Produtora', role: loginRole, is_admin: loginRole === 'admin', ativo: true, painel_beats: true };
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
        if (url.pathname === '/portal/produtor/audio-tag' && request.method() === 'GET') {
            return route.fulfill({ json: { tag_id: null, nome: null, padrao_disponivel: true, versao: 0 } });
        }
        if (url.pathname === '/portal/produtor/catalogo-beats' && request.method() === 'GET') {
            return route.fulfill({ json: [{ id: 81, produtor_id: 3, produtor: 'Outro Produtor', titulo: 'Beat publicado', descricao: '', bpm: 92, tonalidade: 'C', generos: 'R&B', preco_lease: '80.00', preco_exclusivo: '450.00', status: 'aprovado', ativo: true, motivo_rejeicao: null, created_at: new Date().toISOString() },
                { id: 82, produtor: 'Outro Produtor', titulo: 'Beat exclusivo', descricao: '', bpm: 88, tonalidade: null, generos: 'Trap', preco_lease: null, preco_wav: null, preco_multitrack: null, preco_exclusivo: null, created_at: new Date().toISOString(), vendido: true }] });
        }
        if (url.pathname === '/portal/produtor/beats/configuracao' && request.method() === 'GET') {
            return route.fulfill({ json: { limits: { capa_mb: 10, mp3_mb: 1, wav_mb: 50, multitrack_mb: 50, multitrack_mode: 'arquivo' }, ready: true, message: '' } });
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
        const noteEdit = url.pathname.match(/^\/portal\/produtor\/arquivos\/(\d+)\/observacao$/);
        if (noteEdit && request.method() === 'PATCH') {
            const file = files.find(item => item.id === Number(noteEdit[1]));
            noteEdits.push(request.postDataJSON());
            file.observacao = request.postDataJSON().observacao;
            return route.fulfill({ json: file });
        }
        const fileDelete = url.pathname.match(/^\/portal\/produtor\/arquivos\/(\d+)$/);
        if (fileDelete && request.method() === 'DELETE') {
            const id = Number(fileDelete[1]);
            deletedFiles.push(id);
            files = files.filter(file => file.id !== id);
            return route.fulfill({ status: 204 });
        }
        if (/^\/portal\/produtor\/arquivos\/\d+\/conteudo$/.test(url.pathname)) {
            listens.push(url.search);
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
        if (/^\/portal\/produtor\/producoes\/\d+\/entregas-finais$/.test(url.pathname) && request.method() === 'GET') {
            return route.fulfill({ json: [] });
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
        await signIn(page, { next: '/produtor', username: 'producer-a' });
        await page.waitForSelector('.producer-metric');
        assert.equal(await page.locator('.producer-metric').count(), 5);
        assert.match(await page.locator('#producer-metrics').textContent(), /Produções ativas2/);
        assert.match(await page.locator('#producer-metrics').textContent(), /Em revisão1/);
        // AUD6-S08-001: no own tag yet, so the dashboard points to "Meu perfil".
        const tagNotice = page.locator('#producer-tag-notice');
        await tagNotice.waitFor();
        assert.match(await tagNotice.textContent(), /ainda não cadastrou sua tag.*tag padrão da Mirai/);
        assert.equal(await page.getByRole('link', { name: 'Minha tag', exact: true }).count(), 0);
        assert.equal(await tagNotice.getByRole('link', { name: 'Cadastrar minha tag' }).getAttribute('href'), '/produtor/perfil');
        assert.equal(await page.getByRole('link', { name: 'Catálogo', exact: true }).count(), 0, 'the catalog lives inside Beats');
        const nav = page.locator('#producer-navigation');
        await nav.getByRole('link', { name: 'Beats', exact: true }).click();
        await page.waitForURL('**/produtor/beats');
        assert.equal(await nav.getByRole('link', { name: 'Beats', exact: true }).getAttribute('aria-current'), 'page');
        assert.equal(await page.locator('#producer-beats').getByRole('link', { name: 'Meus beats' }).getAttribute('aria-current'), 'page');
        await page.waitForSelector('#producer-beats-list .producer-card');
        assert.match(await page.locator('#producer-beats-list').textContent(), /<Beat seguro>/);
        assert.equal(await page.locator('#producer-beats-list script, #producer-beats-list img').count(), 0);
        const producerBeatBox = await page.locator('#producer-beats-list .beat-card').boundingBox();
        assert.ok(Math.abs(producerBeatBox.width - producerBeatBox.height) < 2, 'producer beat card must remain square');
        assert.equal(await page.locator('#producer-beats-list .producer-beat-card__content').evaluate(element => (
            element.scrollHeight <= element.clientHeight && element.scrollWidth <= element.clientWidth
        )), true, 'producer beat content must fit inside the square');
        assert.match(await page.locator('#producer-beats-list').textContent(), /Producer A/);
        await page.locator('#producer-beats').getByRole('link', { name: 'Catálogo' }).click();
        await page.waitForURL('**/produtor/catalogo');
        assert.equal(await nav.getByRole('link', { name: 'Beats', exact: true }).getAttribute('aria-current'), 'page');
        assert.equal(await page.locator('#producer-catalog').getByRole('link', { name: 'Catálogo' }).getAttribute('aria-current'), 'page');
        await page.waitForSelector('#producer-catalog-list .producer-card');
        assert.match(await page.locator('#producer-catalog-list').textContent(), /Outro Produtor/);
        assert.equal(
            await page.locator('#producer-catalog-list button').count(),
            await page.locator('#producer-catalog-list .beat-preview button').count(),
            'catalog only exposes preview player controls',
        );
        assert.doesNotMatch(await page.locator('#producer-catalog-list').textContent(), /Comprar|Solicitar/);
        const soldBeat = page.locator('#producer-catalog-list .beat-card--sold');
        assert.match(await soldBeat.textContent(), /Beat exclusivo.*Vendido/s);
        assert.equal(await soldBeat.locator('.beat-preview, .beat-card__prices').count(), 0);
        await page.locator('#producer-catalog').getByRole('link', { name: 'Meus beats' }).click();
        await page.waitForURL('**/produtor/beats');
        await page.getByLabel('Título').fill('Novo beat');
        await page.locator('#producer-beat-form [name="preco_lease"]').fill('120');
        await page.locator('#producer-beat-form [name="capa"]').setInputFiles({ name: 'capa.png', mimeType: 'image/png', buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==', 'base64') });
        await page.getByRole('dialog', { name: 'Ajustar imagem' }).getByRole('button', { name: 'Usar corte' }).click();
        await page.waitForFunction(() => !document.querySelector('#producer-beat-form [name="capa"]').dataset.cropPending);
        await page.locator('#producer-beat-form [name="mp3"]').setInputFiles({ name: 'beat.mp3', mimeType: 'audio/mpeg', buffer: Buffer.alloc(1024 * 1024 + 1, 1) });
        await page.getByRole('button', { name: 'Enviar para revisão' }).click();
        assert.match(await page.locator('#producer-beat-upload-status').textContent(), /excede o limite de 1 MB/);
        assert.equal(beatUploads, 0);
        await page.locator('#producer-beat-form [name="mp3"]').setInputFiles({ name: 'beat.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('ID3synthetic') });
        assert.deepEqual(await page.locator('#producer-beat-form [name="capa"]').evaluate(async input => {
            const header = new DataView(await input.files[0].arrayBuffer());
            return [header.getUint32(16), header.getUint32(20)];
        }), [1024, 1024]);
        await page.getByRole('button', { name: 'Enviar para revisão' }).click();
        await page.waitForFunction(() => [...document.querySelectorAll('.upload-tasks-dialog li span')]
            .some(item => item.textContent === 'Concluído'));
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
        // The producer edits the note of their own preview; studio files have no edit button.
        const own = page.locator('.producer-file').filter({ hasText: 'historical.mp3' });
        assert.equal(await page.locator('.producer-file').first().getByRole('button', { name: /observação/ }).count(), 0);
        await own.getByRole('button', { name: 'Editar observação' }).click();
        await own.getByLabel('Observação').fill('Segunda ideia, voz mais alta');
        await own.getByRole('button', { name: 'Salvar' }).click();
        await page.waitForFunction(() => /Sua observação: Segunda ideia, voz mais alta/.test(
            [...document.querySelectorAll('.producer-file')].find(item => item.textContent.includes('historical.mp3'))?.textContent || ''));
        assert.deepEqual(noteEdits, [{ observacao: 'Segunda ideia, voz mais alta' }]);
        // Listen in the page without saving a file.
        await own.getByRole('button', { name: 'Ouvir' }).click();
        await own.locator('audio.ouvir-arquivo__media').waitFor({ state: 'attached' });
        assert.ok(listens.includes('?ouvir=true'), JSON.stringify(listens));
        const studio = await page.evaluate(async () => {
            const module = await import('/js/modules/ouvir_arquivo.js');
            return [module.opcoesEstudio({ processamento_tag: 'pronto' }), module.opcoesEstudio({ processamento_tag: null }),
                module.podeOuvir({ mime_type: 'application/pdf' })];
        });
        assert.deepEqual(studio, [
            [{ versao: 'processada', rotulo: 'Ouvir com tag' }, { versao: 'original', rotulo: 'Ouvir original' }],
            [{ versao: null, rotulo: 'Ouvir' }], false,
        ]);
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

        const finalDelivery = page.locator('details.final-delivery-disclosure').filter({ hasText: 'Enviar entrega final' });
        assert.equal(await finalDelivery.getAttribute('open'), null);
        await finalDelivery.getByText('Enviar entrega final', { exact: true }).click();
        const category = finalDelivery.getByLabel('Tipo de entrega');
        assert.deepEqual(await category.locator('option').allTextContents(), ['Beat exclusivo', 'Outro tipo de entrega']);
        assert.equal(await finalDelivery.getByLabel('Título do beat').isVisible(), true);
        assert.equal(await finalDelivery.getByLabel('BPM').isVisible(), true);
        assert.equal(await finalDelivery.getByLabel('Key / Tom').isVisible(), true);
        assert.equal(await finalDelivery.getByLabel(/Compositores\/programadores adicionais/).isVisible(), true);
        assert.equal(await finalDelivery.getByText(/licença exclusiva.*gerada automaticamente/i).isVisible(), true);
        await category.selectOption('outro');
        assert.equal(await finalDelivery.getByLabel('Título da entrega').isVisible(), true);
        assert.equal(await finalDelivery.getByLabel('BPM').isVisible(), false);
        assert.equal(await finalDelivery.getByText('WAV final').isVisible(), false);
        assert.equal(await finalDelivery.getByText('Arquivo principal').isVisible(), true);
        await finalDelivery.getByText('Enviar entrega final', { exact: true }).click();

        await page.getByText('Enviar prévia', { exact: true }).click();
        await page.getByLabel('Observação para esta versão').fill('Mix com graves reduzidos');
        await page.getByLabel('Arquivo para enviar').setInputFiles({ name: 'preview.mp3', mimeType: 'audio/mpeg', buffer: Buffer.from('preview') });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.getByRole('button', { name: /^Envios/ }).click();
        await page.waitForFunction(() => document.querySelector('.upload-tasks-dialog')?.textContent.includes('Concluído'));
        assert.equal(uploads, 1);
        assert.match(lastUploadBody, /name="observacao"[\s\S]*Mix com graves reduzidos/);
        await page.getByRole('button', { name: 'Fechar' }).click();
        await page.waitForFunction(() => [...document.querySelectorAll('.producer-file')].some(item => item.textContent.includes('preview.mp3')));
        assert.match(await page.locator('.producer-file').filter({ hasText: 'preview.mp3' }).textContent(), /Compartilhada com o cliente/);
        // AUD-S08-001: only previews use the loose-file replacement flow.
        const replacementValues = () => page.getByLabel('Versão substituída').locator('option')
            .evaluateAll(options => options.map(option => option.value));
        assert.deepEqual(await replacementValues(), ['', '8', '10']);
        await page.getByRole('button', { name: 'Confirmar início' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Andamento atualizado'));
        assert.equal(productions[0].status, 'em_producao');
        page.once('dialog', dialog => dialog.accept());
        await page.locator('.producer-file').filter({ hasText: 'historical.mp3' })
            .getByRole('button', { name: 'Excluir prévia' }).click();
        await page.waitForFunction(() => !document.body.textContent.includes('historical.mp3'));
        assert.deepEqual(deletedFiles, [8]);
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

        // AUD6-S02-003: "Sair" sends the producer to the single access page.
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());

        productions = [];
        payouts = [];
        await signIn(page, { next: '/produtor', username: 'producer-a' });
        await page.waitForSelector('.producer-metric');
        assert.match(await page.locator('#producer-metrics').textContent(), /Produções ativas0/);
        await page.getByRole('link', { name: 'Minhas produções' }).click();
        assert.match(await page.locator('#producer-list').textContent(), /ainda não possui produções/);
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());

        // An administrator who follows a producer link goes to the Admin, never into this portal.
        loginRole = 'admin';
        const adminArea = url => url.pathname === '/admin';
        await page.route(adminArea, route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Admin</title>' }));
        await page.goto(`http://localhost:4173/acesso.html?next=${encodeURIComponent('/produtor/producoes')}`);
        await page.locator('#access-login-form #username').fill('admin');
        await page.locator('#access-login-form #password').fill('synthetic-password');
        await Promise.all([page.waitForURL(adminArea), page.locator('#access-login-form button[type=submit]').click()]);
        assert.equal(await page.evaluate(() => localStorage.getItem('mirai.auth.produtor.access_token')), null);
        await page.evaluate(() => localStorage.removeItem('mirai.auth.admin.access_token'));
        await page.unroute(adminArea);

        // AUD-S08-002: a payout failure must not block the production workspace.
        loginRole = 'produtor';
        failPayouts = true;
        await signIn(page, { next: '/produtor', username: 'producer-a' });
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('repasses'));
        assert.equal(await page.locator('.producer-metric').count(), 5);
        failPayouts = false;
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());

        failList = true;
        await signIn(page, { next: '/produtor', username: 'producer-a' });
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Falha controlada'));
        assert.equal(await page.locator('#producer-loading').isVisible(), false);

        // Roadmap 5.01: published settings drive notice, texts, indicators and filters.
        await expectAccessPage(page, () => page.getByRole('button', { name: 'Sair' }).click());
        failList = false;
        portalSettings = {
            aviso: { ativo: true, nivel: 'info', texto: 'Novo fluxo de entregas a partir de segunda.' },
            textos: { descricao_dashboard: 'Foco nos prazos da semana.', ajuda_financeiro: 'Repasses às sextas.' },
            indicadores: ['vencidos', 'ativas'],
            filtros: { status_padrao: 'revisao', ordenacao_padrao: 'recente' },
        };
        await signIn(page, { next: '/produtor', username: 'producer-a' });
        await page.waitForFunction(() => document.getElementById('producer-loading').classList.contains('hidden'));
        await page.getByRole('link', { name: 'Dashboard' }).click();
        await page.waitForSelector('#producer-metrics .producer-metric');
        assert.equal(await page.locator('#producer-notice').textContent(), 'Novo fluxo de entregas a partir de segunda.');
        assert.equal(await page.locator('#producer-dashboard-lead').textContent(), 'Foco nos prazos da semana.');
        assert.deepEqual(await page.locator('#producer-metrics dt').allTextContents(), ['Prazos vencidos', 'Produções ativas']);
        assert.equal(await page.locator('#producer-status-filter').inputValue(), 'revisao');
        assert.equal(await page.locator('#producer-order').inputValue(), 'recente');
        assert.equal(await page.locator('#producer-finance-help').textContent(), 'Repasses às sextas.');
        // AUD6-S02-011: the portal shows the display name, never the login.
        assert.equal(await page.locator('#producer-greeting').textContent(), 'Ana Produtora');
        assert.equal(await page.locator('#producer-username').textContent(), 'Ana Produtora');

        assert.deepEqual(errors, []);
        console.log('PASS: producer login/logout, dashboard, list, detail, progress, safe text, errors and responsive structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
