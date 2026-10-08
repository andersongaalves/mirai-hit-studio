const { chromium } = require('playwright');
const assert = require('node:assert/strict');

const FRONTEND = 'http://localhost:4173';
const API = 'http://localhost:8000';
const password = process.env.E2E_PASSWORD;
const budgetId = Number(process.env.E2E_FLOW_BUDGET_ID);
const producerId = Number(process.env.E2E_PRODUCER_A_ID);
const provisionClientId = Number(process.env.E2E_PROVISION_CLIENT_ID);
const otherProductionId = Number(process.env.E2E_OTHER_PRODUCTION_ID);
const clientProposalId = Number(process.env.E2E_CLIENT_PROPOSAL_ID);
const otherClientProposalId = Number(process.env.E2E_OTHER_CLIENT_PROPOSAL_ID);

for (const [name, value] of Object.entries({
    password,
    budgetId,
    producerId,
    provisionClientId,
    otherProductionId,
    clientProposalId,
    otherClientProposalId,
})) {
    assert.ok(value, `missing ${name}`);
}

async function login(page, path, username) {
    await page.goto(`${FRONTEND}${path}`);
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await page.getByRole('button', { name: 'Entrar' }).click();
    await page.locator('#admin-area').waitFor({ state: 'visible' });
    const loadingSelector = path.startsWith('/produtor')
        ? '#producer-loading'
        : path.startsWith('/cliente')
            ? '#client-loading'
            : null;
    if (loadingSelector) await page.locator(loadingSelector).waitFor({ state: 'hidden' });
}

async function resetSession(page) {
    await page.evaluate(() => localStorage.clear());
}

async function api(page, method, path, body = undefined) {
    const result = await page.evaluate(async ({ apiRoot, method, path, body }) => {
        const context = location.pathname.startsWith('/produtor')
            ? 'produtor'
            : location.pathname.startsWith('/cliente')
                ? 'cliente'
                : 'admin';
        const token = localStorage.getItem(`mirai.auth.${context}.access_token`);
        const response = await fetch(apiRoot + path, {
            method,
            headers: {
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
                ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
            },
            ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        });
        const contentType = response.headers.get('content-type') || '';
        const data = contentType.includes('application/json') ? await response.json() : await response.text();
        return { status: response.status, data };
    }, { apiRoot: API, method, path, body });
    return result;
}

function expectStatus(result, status, label) {
    assert.equal(result.status, status, `${label}: ${JSON.stringify(result.data)}`);
    return result.data;
}

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 1024, height: 850 } });
    const page = await context.newPage();
    const pageErrors = [];
    const serverErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('response', response => {
        if (response.url().startsWith(API) && response.status() >= 500) {
            serverErrors.push(`${response.status()} ${response.url()}`);
        }
    });

    try {
        await page.goto(`${FRONTEND}/#servicos`);
        await page.locator('#servicos').waitFor({ state: 'visible' });
        assert.equal(new URL(page.url()).hash, '#servicos');
        const catalog = await page.evaluate(async apiRoot => {
            const response = await fetch(`${apiRoot}/servicos`);
            return { status: response.status, body: await response.json() };
        }, API);
        assert.equal(catalog.status, 200);
        assert.ok(Array.isArray(catalog.body) && catalog.body.length > 0);

        await login(page, '/cliente', 'e2e-client-a');
        const proposalBeforeNavigation = expectStatus(
            await api(page, 'GET', `/portal/cliente/propostas/${clientProposalId}`),
            200,
            'client proposal before deep link',
        );
        assert.equal(proposalBeforeNavigation.status, 'enviada');
        await page.goto(`${FRONTEND}/cliente/propostas/${clientProposalId}`);
        await page.locator('#admin-area').waitFor({ state: 'visible' });
        await page.locator('#client-loading').waitFor({ state: 'hidden' });
        await page.locator('#proposal-detail-title').waitFor({ state: 'visible' });
        assert.match(await page.locator('#client-proposal-detail-content').textContent(), /Produção musical E2E/);
        assert.match(await page.locator('#client-proposal-detail-content').textContent(), /R\$\s*1\.200,00/);
        expectStatus(
            await api(page, 'GET', `/portal/cliente/propostas/${otherClientProposalId}`),
            404,
            'client proposal ownership',
        );
        const proposalDownloadPromise = page.waitForEvent('download');
        await page.getByRole('button', { name: 'Baixar PDF' }).click();
        const proposalDownload = await proposalDownloadPromise;
        assert.match(proposalDownload.suggestedFilename(), /^proposta-\d+(?:-v1)?\.pdf$/);
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', { name: 'Aceitar proposta' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Proposta aceita'));
        const acceptedProposal = expectStatus(
            await api(page, 'GET', `/portal/cliente/propostas/${clientProposalId}`),
            200,
            'accepted client proposal',
        );
        assert.equal(acceptedProposal.status, 'aceita');
        assert.equal(acceptedProposal.situacao_comercial, 'aguardando_pagamento');

        await resetSession(page);
        await login(page, '/admin', 'e2e-admin');
        expectStatus(await api(page, 'POST', '/usuarios', {
            username: 'e2e-provisioned-client',
            password,
            role: 'cliente',
            cliente_id: provisionClientId,
        }), 201, 'admin provisions client identity');
        expectStatus(await api(page, 'PATCH', `/orcamentos/${budgetId}/produtor`, {
            produtor_id: producerId,
        }), 200, 'admin assigns producer');
        const production = expectStatus(await api(page, 'POST', '/producoes', {
            titulo: 'E2E Browser Integrado',
            cliente: 'E2E Cliente A',
            servico: 'Mixagem',
            observacoes: 'notas internas de teste',
            etapas: JSON.stringify([{ nome: 'Producao', feito: false }]),
            produtor_id: producerId,
            orcamento_id: budgetId,
        }), 200, 'admin creates production');
        const productionId = production.id;
        const deadline = new Date(Date.now() + 7 * 86400000).toISOString();
        expectStatus(await api(page, 'PATCH', `/producoes/${productionId}/prazo`, {
            prazo_entrega: deadline,
        }), 200, 'admin sets deadline');

        await resetSession(page);
        await login(page, '/produtor', 'e2e-producer-a');
        await page.getByRole('link', { name: 'Minhas produções' }).click();
        await page.waitForURL('**/produtor/producoes');
        let card = page.locator('#producer-list .producer-card').filter({ hasText: 'E2E Browser Integrado' });
        assert.equal(await card.count(), 1);
        await card.getByRole('button', { name: 'Abrir detalhes' }).click();
        await page.waitForURL(`**/produtor/producoes/${productionId}`);
        await page.getByRole('button', { name: 'Confirmar início' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Andamento atualizado'));

        await resetSession(page);
        await login(page, '/cliente', 'e2e-client-a');
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        await page.waitForURL('**/cliente/projetos');
        card = page.locator('#client-list .producer-card').filter({ hasText: 'E2E Browser Integrado' });
        assert.equal(await card.count(), 1);
        await card.getByRole('button', { name: 'Abrir projeto' }).click();
        await page.waitForURL(`**/cliente/projetos/${productionId}`);
        assert.match(await page.locator('.client-finance-grid').textContent(), /R\$\s*1\.000,00/);
        await page.getByLabel('Tipo de arquivo').selectOption('material');
        await page.getByLabel('Arquivo para enviar').setInputFiles({
            name: 'material-cliente.wav',
            mimeType: 'audio/wav',
            buffer: Buffer.from('RIFF-browser-client-material'),
        });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('client-alert').textContent.includes('Arquivo enviado'));
        assert.equal(expectStatus(
            await api(page, 'GET', `/portal/cliente/producoes/${otherProductionId}`),
            404,
            'client ownership',
        ).detail, 'Producao nao encontrada.');
        expectStatus(await api(page, 'GET', '/portal/produtor/repasses'), 403, 'client payout isolation');

        await resetSession(page);
        await login(page, '/produtor', 'e2e-producer-a');
        await page.getByRole('link', { name: 'Minhas produções' }).click();
        card = page.locator('#producer-list .producer-card').filter({ hasText: 'E2E Browser Integrado' });
        await card.getByRole('button', { name: 'Abrir detalhes' }).click();
        await page.getByLabel('Tipo de arquivo').selectOption('previa');
        await page.getByLabel('Arquivo para enviar').setInputFiles({
            name: 'preview-browser.mp3',
            mimeType: 'audio/mpeg',
            buffer: Buffer.from('ID3-browser-preview'),
        });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Arquivo enviado'));
        await page.getByLabel('Tipo de arquivo').selectOption('entrega');
        await page.getByLabel('Arquivo para enviar').setInputFiles({
            name: 'entrega-browser.wav',
            mimeType: 'audio/wav',
            buffer: Buffer.from('RIFF-browser-delivery'),
        });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Arquivo enviado'));
        await page.getByRole('button', { name: 'Enviar para revisão' }).click();
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Andamento atualizado'));
        expectStatus(await api(page, 'GET', `/portal/produtor/producoes/${otherProductionId}`), 404, 'producer ownership');
        const producerFiles = expectStatus(
            await api(page, 'GET', `/portal/produtor/producoes/${productionId}/arquivos`),
            200,
            'producer file list',
        );
        const preview = producerFiles.find(item => item.nome_exibicao === 'preview-browser.mp3');
        const delivery = producerFiles.find(item => item.nome_exibicao === 'entrega-browser.wav');
        assert.ok(preview && delivery);
        assert.ok(producerFiles.some(item => item.nome_exibicao === 'material-cliente.wav'));

        await resetSession(page);
        await login(page, '/admin', 'e2e-admin');
        for (const file of [preview, delivery]) {
            expectStatus(await api(page, 'PATCH', `/producoes/${productionId}/arquivos/${file.id}/visibilidade`, {
                visivel_produtor: true,
                visivel_cliente: true,
            }), 200, `admin releases ${file.tipo}`);
        }
        expectStatus(await api(page, 'PUT', `/producoes/${productionId}/repasse`, {
            valor_combinado: '275.90',
        }), 200, 'admin defines payout');
        expectStatus(await api(page, 'POST', `/producoes/${productionId}/repasse/liberar`), 200, 'admin releases payout');
        const paid = expectStatus(await api(page, 'POST', `/producoes/${productionId}/repasse/pagar`, {
            referencia_pagamento: 'E2E-BROWSER-SYNTHETIC',
        }), 200, 'admin records synthetic payout');
        assert.equal(paid.status, 'pago');

        await resetSession(page);
        await login(page, '/cliente', 'e2e-client-a');
        await page.getByRole('link', { name: 'Meus projetos' }).click();
        card = page.locator('#client-list .producer-card').filter({ hasText: 'E2E Browser Integrado' });
        await card.getByRole('button', { name: 'Abrir projeto' }).click();
        const previewItem = page.locator('.producer-file').filter({ hasText: 'preview-browser.mp3' });
        await previewItem.getByRole('button', { name: 'Reproduzir' }).click();
        await previewItem.locator('audio.client-player').waitFor({ state: 'attached' });
        const deliveryItem = page.locator('.producer-file').filter({ hasText: 'entrega-browser.wav' });
        const downloadPromise = page.waitForEvent('download');
        await deliveryItem.getByRole('button', { name: 'Baixar' }).click();
        const download = await downloadPromise;
        assert.match(download.suggestedFilename(), /^(entrega-browser|arquivo)\.wav$/);

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 850 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }

        await resetSession(page);
        await login(page, '/produtor', 'e2e-producer-a');
        await page.getByRole('link', { name: 'Recebimentos' }).click();
        await page.waitForURL('**/produtor/financeiro');
        const payouts = await page.locator('#producer-payouts').textContent();
        assert.match(payouts, /R\$\s*275,90/);
        assert.match(payouts, /pago/i);

        const anonymous = await context.request.get(`${API}/portal/cliente/producoes`);
        assert.equal(anonymous.status(), 401);
        assert.deepEqual(pageErrors, []);
        assert.deepEqual(serverErrors, []);
        console.log(JSON.stringify({
            result: 'PORTALS_E2E_PASS',
            production_id: productionId,
            storage: 'fake-integrated',
            browser_api_interception: false,
            services_contract: 'home-#servicos-and-api-/servicos',
        }));
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
