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
const adminPolicyBudgetId = Number(process.env.E2E_ADMIN_POLICY_BUDGET_ID);

for (const [name, value] of Object.entries({
    password,
    budgetId,
    producerId,
    provisionClientId,
    otherProductionId,
    clientProposalId,
    otherClientProposalId,
    adminPolicyBudgetId,
})) {
    assert.ok(value, `missing ${name}`);
}

// AUD6-S02-003: panels sign in through /acesso, which returns to the requested panel.
async function login(page, path, username) {
    await page.goto(`${FRONTEND}/acesso?next=${encodeURIComponent(path)}`);
    await page.locator('#username').fill(username);
    await page.locator('#password').fill(password);
    await Promise.all([
        page.waitForURL(url => url.pathname === path),
        page.getByRole('button', { name: 'Entrar', exact: true }).click(),
    ]);
    await page.locator('#admin-area').waitFor({ state: 'visible' });
    const loadingSelector = path.startsWith('/produtor')
        ? '#producer-loading'
        : path.startsWith('/cliente')
            ? '#client-loading'
            : null;
    if (loadingSelector) await page.locator(loadingSelector).waitFor({ state: 'hidden' });
}

async function resetSession(page) {
    await page.goto(`${FRONTEND}/`);
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

function syntheticWav() {
    const sampleRate = 8000;
    const samples = Buffer.alloc(sampleRate / 10 * 2);
    const wav = Buffer.alloc(44 + samples.length);
    wav.write('RIFF', 0);
    wav.writeUInt32LE(wav.length - 8, 4);
    wav.write('WAVEfmt ', 8);
    wav.writeUInt32LE(16, 16);
    wav.writeUInt16LE(1, 20);
    wav.writeUInt16LE(1, 22);
    wav.writeUInt32LE(sampleRate, 24);
    wav.writeUInt32LE(sampleRate * 2, 28);
    wav.writeUInt16LE(2, 32);
    wav.writeUInt16LE(16, 34);
    wav.write('data', 36);
    wav.writeUInt32LE(samples.length, 40);
    samples.copy(wav, 44);
    return wav;
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

        await login(page, '/admin', 'e2e-admin');
        const openPolicyEditor = () => page.evaluate(async budgetId => {
            const controller = await import('/js/admin/propostas/propostas.js');
            await controller.abrirEditorProposta({ id: budgetId });
        }, adminPolicyBudgetId);
        await openPolicyEditor();
        await page.getByRole('button', { name: 'Pagamento', exact: true }).click();
        const policy = page.locator('#proposta_politica_pagamento');
        assert.equal(await policy.inputValue(), 'entrada_50_50');
        await policy.selectOption('integral');
        await Promise.all([
            page.waitForResponse(response => response.request().method() === 'PATCH'
                && /\/propostas\/\d+$/.test(new URL(response.url()).pathname)),
            page.locator('#btn-save-proposta').click(),
        ]);
        assert.equal(await policy.inputValue(), 'integral');
        await page.evaluate(() => window.fecharEditorProposta());
        await openPolicyEditor();
        await page.getByRole('button', { name: 'Pagamento', exact: true }).click();
        assert.equal(await page.locator('#proposta_politica_pagamento').inputValue(), 'integral');
        await page.locator('#proposta_politica_pagamento').selectOption('entrada_50_50');
        await Promise.all([
            page.waitForResponse(response => response.request().method() === 'PATCH'
                && /\/propostas\/\d+$/.test(new URL(response.url()).pathname)),
            page.locator('#btn-save-proposta').click(),
        ]);
        await page.evaluate(() => window.fecharEditorProposta());

        await resetSession(page);
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
        await page.getByRole('link', { name: 'Ir para pagamento' }).click();
        await page.waitForURL(`**/checkout?proposta=${clientProposalId}`);
        await page.locator('#checkout-content').waitFor({ state: 'visible' });
        assert.equal(await page.locator('input[name="payment_option"]').count(), 2);
        await page.getByRole('button', { name: 'Gerar Pix' }).click();
        await page.locator('#checkout-terminal').getByText('Pagamento confirmado!', { exact: true }).waitFor();
        assert.equal(await page.getByText('Pagamento confirmado!', { exact: true }).count(), 1);
        assert.equal(await page.locator('#payment-result').isHidden(), true);

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
        await page.waitForFunction(() => document.querySelector('.producer-upload__feedback')?.textContent.includes('Envio iniciado'));
        await page.waitForFunction(() => [...document.querySelectorAll('.producer-file')]
            .some(item => item.textContent.includes('material-cliente.wav')));
        assert.match(await page.locator('.producer-file-list').last().textContent(), /material-cliente\.wav/);
        assert.equal(await page.locator('#client-alert').textContent(), '');
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
        await page.getByText('Enviar prévia', { exact: true }).click();
        await page.getByLabel('Tipo de arquivo').selectOption('previa');
        await page.getByLabel('Arquivo para enviar').setInputFiles({
            name: 'preview-browser.mp3',
            mimeType: 'audio/mpeg',
            buffer: Buffer.from('ID3-browser-preview'),
        });
        await page.getByRole('button', { name: 'Enviar arquivo' }).click();
        // Producer previews are shared with the client on upload (decisao de 14/10).
        await page.waitForFunction(() => document.getElementById('producer-alert').textContent.includes('Envio iniciado'));
        await page.waitForFunction(() => [...document.querySelectorAll('.producer-file')]
            .some(item => item.textContent.includes('preview-browser.mp3')));
        const finalDelivery = page.locator('details.final-delivery-disclosure')
            .filter({ hasText: 'Enviar entrega final' });
        await finalDelivery.getByText('Enviar entrega final', { exact: true }).click();
        await finalDelivery.getByLabel('Tipo de entrega').selectOption('outro');
        await finalDelivery.getByLabel('Título').fill('Entrega E2E Browser');
        await finalDelivery.getByLabel('Arquivo principal').setInputFiles({
            name: 'entrega-browser.wav',
            mimeType: 'audio/wav',
            buffer: syntheticWav(),
        });
        await finalDelivery.getByRole('button', { name: 'Enviar pacote final' }).click();
        const finalDeliveryTask = page.locator('.upload-tasks-dialog li')
            .filter({ hasText: 'Entrega final · Entrega E2E Browser' });
        await finalDeliveryTask.waitFor();
        await page.waitForFunction(() => [...document.querySelectorAll('.upload-tasks-dialog li')]
            .some(item => item.textContent.includes('Entrega final · Entrega E2E Browser')
                && ['completed', 'failed'].includes(item.dataset.state)));
        assert.equal(await finalDeliveryTask.getAttribute('data-state'), 'completed', await finalDeliveryTask.textContent());
        await page.waitForFunction(() => [...document.querySelectorAll('.final-delivery-card')]
            .some(item => item.textContent.includes('Entrega E2E Browser')));
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
        assert.equal(preview.visivel_cliente, true);
        assert.equal(delivery.visivel_cliente, true);
        assert.ok(producerFiles.some(item => item.nome_exibicao === 'material-cliente.wav'));

        await resetSession(page);
        await login(page, '/admin', 'e2e-admin');
        expectStatus(await api(page, 'PUT', `/producoes/${productionId}/repasse`, {
            valor_combinado: '275.90',
        }), 200, 'admin defines payout');
        expectStatus(await api(page, 'POST', `/producoes/${productionId}/repasse/liberar`, {
            motivo_confirmacao: 'E2E sintetico',
        }), 200, 'admin releases payout');
        const paid = expectStatus(await api(page, 'POST', `/producoes/${productionId}/repasse/pagar`, {
            referencia_pagamento: 'E2E-BROWSER-SYNTHETIC',
            motivo_confirmacao: 'E2E sintetico',
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
        const deliveryItem = page.locator('.final-delivery-card').filter({ hasText: 'Entrega E2E Browser' });
        assert.equal(await deliveryItem.getByRole('button', { name: 'Baixar arquivo' }).count(), 0);
        expectStatus(await api(page, 'GET', `/portal/cliente/arquivos/${delivery.id}/conteudo`),
            402, 'unpaid final delivery denied by real backend');
        const balanceLink = deliveryItem.getByRole('link', { name: 'Pagar saldo e liberar' });
        const balanceUrl = new URL(await balanceLink.getAttribute('href'));
        assert.equal(balanceUrl.origin, FRONTEND);
        assert.match(balanceUrl.pathname, /^\/checkout\/[0-9a-f-]{36}$/);
        await balanceLink.click();
        await page.waitForURL(balanceUrl.href);
        await page.locator('#checkout-content').waitFor({ state: 'visible' });
        assert.equal(await page.locator('input[name="payment_option"]').count(), 1);
        assert.equal(await page.locator('input[name="payment_option"]').inputValue(), 'saldo');
        await page.getByRole('button', { name: 'Gerar Pix' }).click();
        await page.locator('#checkout-terminal').getByText('Pagamento confirmado!', { exact: true }).waitFor();
        await page.goto(`${FRONTEND}/cliente/projetos/${productionId}`);
        await page.locator('#client-loading').waitFor({ state: 'hidden' });
        await deliveryItem.getByRole('button', { name: 'Baixar arquivo' }).waitFor();
        const downloadPromise = page.waitForEvent('download');
        await deliveryItem.getByRole('button', { name: 'Baixar arquivo' }).click();
        const download = await downloadPromise;
        // The API exposes Content-Disposition cross-origin (AUD-S12-002).
        assert.equal(download.suggestedFilename(), 'entrega-browser.wav');

        for (const width of [320, 375, 390, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 850 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        }

        await resetSession(page);
        await login(page, '/produtor', 'e2e-producer-a');
        await page.getByRole('link', { name: 'Financeiro' }).click();
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
