const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const tokenA = '11111111-1111-4111-8111-111111111111';
const tokenB = '22222222-2222-4222-8222-222222222222';
const tokenC = '33333333-3333-4333-8333-333333333333';
const tokenD = '44444444-4444-4444-8444-444444444444';
const tokenE = '55555555-5555-4555-8555-555555555555';
const tokenF = '66666666-6666-4666-8666-666666666666';
const tokenG = '77777777-7777-4777-8777-777777777777';
const tokenH = '88888888-8888-4888-8888-888888888888';
const tokenI = '99999999-9999-4999-8999-999999999999';
const tokenJ = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaab';
const tokenK = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
const tokenL = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc';
function pixCode(amount = '99.00', initiation = '12') {
    const fields = [
        ['00', '01'], ...(initiation === null ? [] : [['01', initiation]]),
        ['26', `0014br.gov.bcb.pix013600000000-0000-0000-0000-000000000000`],
        ['52', '0000'], ['53', '986'], ['54', amount], ['58', 'BR'],
        ['59', 'Mirai Studio'], ['60', 'SAO'], ['62', '0503***'],
    ].map(([tag, value]) => `${tag}${String(value.length).padStart(2, '0')}${value}`).join('');
    let crc = 0xffff;
    for (const character of `${fields}6304`) {
        crc ^= character.charCodeAt(0) << 8;
        for (let bit = 0; bit < 8; bit += 1) crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
    }
    return `${fields}6304${crc.toString(16).toUpperCase().padStart(4, '0')}`;
}

function qrCodec(mode, input) {
    const result = spawnSync('python', [path.join(__dirname, 'checkout_qr.py')], {
        input: JSON.stringify({ mode, ...input }), encoding: 'utf8', maxBuffer: 1024 * 1024,
    });
    assert.equal(result.status, 0, `QR codec failed: ${result.stderr}`);
    return JSON.parse(result.stdout);
}

const mercadoPagoSample = '00020126580014br.gov.bcb.pix0136b76aa9c2-2ec4-4110-954e-ebfe34f05b61520400005303986540510.005802BR5912TESTPVBWOSBE6009Sao Paulo62240520mpqrinter715936942186304C3C0';
const summaries = new Map([
    [tokenA, summary('<img src=x onerror="window.xss=true">Mixagem')],
    [tokenB, summary('Trilha original')],
    [tokenC, summary('Masterização')],
    [tokenD, { ...summary('Produção'), status: 'parcialmente_paga', valor_pago: '99.00', saldo: '99.00', opcoes: [{ tipo: 'saldo', titulo: 'Saldo restante', valor: '99.00' }] }],
    [tokenE, { ...summary('Produção'), status: 'paga', valor_pago: '198.00', saldo: '0.00', opcoes: [] }],
    [tokenF, { ...summary('Produção'), status: 'cancelada', opcoes: [] }],
    [tokenG, summary('Beat exclusivo')],
    [tokenH, summary('Pix malformado')],
    [tokenI, summary('Pix expirado')],
    [tokenJ, { ...summary('Pix sem campo 01'), opcoes: [{ tipo: 'integral', titulo: 'Pagamento completo', valor: '10.00' }] }],
    [tokenK, summary('Pagamento total')],
    [tokenL, { ...summary('Pix recuperável'), tentativa: { metodo: 'pix', tipo: 'entrada', status: 'processando', recuperavel: true } }],
]);

function summary(description) {
    return {
        proposta_numero: 'MHS-000001', descricao: description, valor_total: '198.00', valor_pago: '0.00',
        saldo: '198.00', moeda: 'BRL', status: 'pendente', tentativa: null,
        opcoes: [
            { tipo: 'integral', titulo: 'Pagamento completo', valor: '198.00' },
            { tipo: 'entrada', titulo: 'Entrada', valor: '99.00' },
        ],
    };
}

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const pathname = url.pathname === '/checkout' || url.pathname.startsWith('/checkout/') ? '/checkout.html' : url.pathname;
    const file = path.resolve(root, '.' + decodeURIComponent(pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        const types = { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css', '.png': 'image/png', '.webp': 'image/webp' };
        return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || 'application/octet-stream' });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const qrImage = qrCodec('encode', { payload: pixCode() }).image;
    const mercadoPagoQrImage = qrCodec('encode', { payload: mercadoPagoSample }).image;
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
        await context.addInitScript(() => {
            if (sessionStorage.getItem('mirai.test_unknown_consent') !== 'yes') {
                localStorage.setItem('mirai.analytics_consent.v1', 'rejected');
            }
        });
        let pixRequests = 0;
        let authenticatedPixRequests = 0;
        let cancelPixRequests = 0;
        let pendingRequests = 0;
        let pendingFailure = false;
        let pendingStatus = 'pending';
        let pendingExpired = false;
        let pendingAmount = '99.00';
        let authenticatedPaid = false;
        let publicPaid = false;
        let cardPayload = null;
        let pixPayload = null;
        let sdkFailure = false;
        let securityFailure = false;
        let challengeUrl = 'https://www.mercadopago.com/auth/challenge';
        let missingPublicKey = false;
        let configStatus = 200;
        const previewApiRequests = [];
        const pageErrors = [];
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173' || url.origin === 'https://deploy-preview-19--miraihitstudio.netlify.app') return staticResponse(route);
            // Non-production hosts point to a reserved .invalid API that never resolves.
            if (url.hostname.endsWith('.invalid')) return route.abort('namenotresolved');
            if (url.origin === 'https://sdk.mercadopago.com') {
                if (sdkFailure) return route.abort();
                return route.fulfill({ contentType: 'text/javascript', body: `
                    window.MercadoPago = class {
                        constructor(publicKey) { window.__publicKey = publicKey; }
                        bricks() { return { create: async (_name, id, settings) => {
                            window.__brickSettings = settings;
                            const button = document.createElement('button');
                            button.type = 'button'; button.textContent = 'Pagar cartão';
                            document.getElementById(id).appendChild(button);
                            settings.callbacks.onReady();
                            return { unmount: async () => {
                                window.__brickUnmounts = (window.__brickUnmounts || 0) + 1;
                                document.getElementById(id).replaceChildren();
                            } };
                        } }; }
                    };
                ` });
            }
            if (url.pathname === '/v2/security.js' && url.hostname === 'www.mercadopago.com') {
                if (securityFailure) return route.abort();
                return route.fulfill({ contentType: 'text/javascript', body: "window.MP_DEVICE_SESSION_ID = 'official-device-123';" });
            }
            if (url.origin === 'http://localhost:8000' || url.origin === 'https://mirai-hit-studio.onrender.com') {
                const previewRequest = url.origin === 'https://mirai-hit-studio.onrender.com';
                const corsHeaders = previewRequest ? {
                    'Access-Control-Allow-Origin': 'https://deploy-preview-19--miraihitstudio.netlify.app',
                    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
                    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                } : {};
                if (previewRequest) previewApiRequests.push(route.request().url());
                if (previewRequest && route.request().method() === 'OPTIONS') return route.fulfill({ status: 204, headers: corsHeaders });
                if (url.pathname === '/portal/cliente/propostas/70/checkout' && route.request().method() === 'GET') {
                    assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    return route.fulfill({ headers: corsHeaders, json: {
                        proposta_numero: 'MHS-000070', descricao: 'Proposta autenticada', valor_total: '200.00',
                        valor_pago: authenticatedPaid ? '100.00' : '0.00',
                        saldo: authenticatedPaid ? '100.00' : '200.00', moeda: 'BRL', politica_pagamento: 'entrada_50_50',
                        status: authenticatedPaid ? 'parcialmente_paga' : 'pendente', tentativa: null,
                        opcoes: authenticatedPaid ? [{ tipo: 'saldo', titulo: 'Saldo restante', valor: '100.00' }] : [
                            { tipo: 'integral', titulo: 'Pagamento completo', valor: '200.00' },
                            { tipo: 'entrada', titulo: 'Entrada', valor: '100.00' },
                        ],
                    } });
                }
                if (url.pathname === '/portal/cliente/propostas/70/checkout/card' && route.request().method() === 'POST') {
                    assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    assert.equal(route.request().postDataJSON().payment_option, 'entrada');
                    authenticatedPaid = true;
                    return route.fulfill({ headers: corsHeaders, json: {
                        status: 'approved', checkout_status: 'parcialmente_paga', payment_option: 'entrada',
                        valor: '100.00', moeda: 'BRL', pix: null, challenge_url: null,
                    } });
                }
                if (url.pathname === '/portal/cliente/propostas/42/checkout' && route.request().method() === 'GET') {
                    assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    return route.fulfill({ json: {
                        proposta_numero: 'MHS-000042', descricao: 'Proposta autenticada', valor_total: '300.00',
                        valor_pago: '0.00', saldo: '300.00', moeda: 'BRL', politica_pagamento: 'integral',
                        status: 'pendente', tentativa: null,
                        opcoes: [{ tipo: 'integral', titulo: 'Pagamento completo', valor: '300.00' }],
                    } });
                }
                if (url.pathname === '/portal/cliente/propostas/42/checkout/pix' && route.request().method() === 'POST') {
                    assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    authenticatedPixRequests += 1;
                    return route.fulfill({ json: {
                        status: 'pending', checkout_status: 'pendente', payment_option: 'integral',
                        valor: '300.00', moeda: 'BRL', challenge_url: null,
                        pix: { qr_code: 'auth-pix-code', qr_code_base64: null, ticket_url: null, expiration_time: null },
                    } });
                }
                if (url.pathname === '/portal/cliente/propostas/71/checkout' && route.request().method() === 'GET') {
                    return route.fulfill({ json: {
                        ...summary('Pix autenticado'), tentativa: { metodo: 'pix', tipo: 'entrada', status: 'processando', recuperavel: true },
                    } });
                }
                if (url.pathname === '/portal/cliente/propostas/71/checkout/pending-payment' && route.request().method() === 'GET') {
                    assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    pendingRequests++;
                    return route.fulfill({ json: {
                        status: 'pending', checkout_status: 'pendente', payment_option: 'entrada', valor: '99.00', moeda: 'BRL',
                        pix: { qr_code: pixCode(), qr_code_base64: qrImage, ticket_url: 'https://www.mercadopago.com.br/pay', expiration_time: '2099-09-21T12:00:00Z' },
                    } });
                }
                const match = url.pathname.match(/^\/checkout\/([0-9a-f-]{36})(.*)$/i);
                if (url.pathname === '/checkout/config') {
                    if (previewRequest) assert.equal(route.request().headers().authorization, 'Bearer client-token');
                    if (configStatus !== 200) return route.fulfill({ status: configStatus, json: { detail: 'Pagamento indisponível.' } });
                    return route.fulfill({ headers: corsHeaders, json: missingPublicKey ? {} : { mercado_pago_public_key: 'TEST-public-key' } });
                }
                if (!match) return route.fulfill({ status: 404, json: { detail: 'not found' } });
                const [, token, suffix] = match;
                if (suffix === '' && route.request().method() === 'GET') {
                    const data = summaries.get(token);
                    const current = token === tokenK && publicPaid
                        ? { ...data, status: 'paga', valor_pago: '198.00', saldo: '0.00', opcoes: [] }
                        : token === tokenL && pendingStatus === 'approved'
                            ? { ...data, status: 'paga', valor_pago: '198.00', saldo: '0.00', opcoes: [], tentativa: null }
                            : token === tokenL && pendingStatus === 'rejected'
                                ? { ...data, tentativa: null }
                        : data;
                    return current ? route.fulfill({ json: current }) : route.fulfill({ status: 404, json: { detail: 'Checkout não encontrado.' } });
                }
                if (suffix === '/pix' && route.request().method() === 'POST') {
                    pixRequests += 1;
                    pixPayload = route.request().postDataJSON();
                    await new Promise(resolve => setTimeout(resolve, 80));
                    const malformed = token === tokenH;
                    const expired = token === tokenI;
                    const documentedPix = token === tokenJ;
                    return route.fulfill({ json: {
                        status: 'pending', checkout_status: 'pendente', payment_option: route.request().postDataJSON().payment_option,
                        valor: documentedPix ? '10.00' : '99.00', moeda: 'BRL', challenge_url: null,
                        pix: { qr_code: malformed ? '000201-pix-code' : documentedPix ? mercadoPagoSample : pixCode(), qr_code_base64: documentedPix ? mercadoPagoQrImage : qrImage, ticket_url: 'https://www.mercadopago.com.br/pay', expiration_time: expired ? '2020-09-21T12:00:00Z' : '2099-09-21T12:00:00Z' },
                    } });
                }
                if (suffix === '/pending-payment' && token === tokenL) {
                    pendingRequests++;
                    if (pendingFailure) return route.fulfill({ status: 503, json: { detail: 'Indisponível.' } });
                    return route.fulfill({ json: {
                        status: pendingStatus, checkout_status: pendingStatus === 'approved' ? 'paga' : 'pendente',
                        payment_option: 'entrada', valor: pendingAmount, moeda: 'BRL',
                        pix: pendingStatus === 'pending' ? {
                            qr_code: pixCode(), qr_code_base64: qrImage, ticket_url: 'https://www.mercadopago.com.br/pay',
                            expiration_time: pendingExpired ? '2020-09-21T12:00:00Z' : '2099-09-21T12:00:00Z',
                        } : null,
                    } });
                }
                if (suffix === '/cancel-pix' && route.request().method() === 'POST') {
                    cancelPixRequests += 1;
                    return route.fulfill({ json: { status: 'cancelado' } });
                }
                if (suffix === '/card' && route.request().method() === 'POST') {
                    cardPayload = route.request().postDataJSON();
                    if (token === tokenK) publicPaid = true;
                    return route.fulfill({ json: {
                        status: token === tokenG ? 'rejected' : token === tokenK ? 'approved' : 'action_required',
                        checkout_status: token === tokenK ? 'paga' : 'pendente', payment_option: cardPayload.payment_option,
                        valor: '198.00', moeda: 'BRL', pix: null,
                        challenge_url: token === tokenG ? null : challengeUrl,
                    } });
                }
                if (suffix === '/status') return route.fulfill({ json: { status: 'pendente', valor_pago: '0.00', saldo: '198.00', pagamento_status: 'processando' } });
            }
            if (url.hostname.includes('mercadopago.')) return route.fulfill({ contentType: 'text/html', body: '<p>Challenge</p>' });
            return route.fulfill({ status: 200, body: '' });
        });

        const routingPage = await context.newPage();
        routingPage.on('pageerror', error => pageErrors.push(error.message));
        await routingPage.goto('http://localhost:4173/checkout/test-token-routing-123?source=test');
        await routingPage.waitForSelector('#checkout-error:not(.hidden)');
        assert.equal(await routingPage.evaluate(() => location.pathname), '/checkout/test-token-routing-123');
        assert.equal(await routingPage.evaluate(() => location.search), '?source=test');
        assert.match(await routingPage.locator('#checkout-error-message').textContent(), /link de checkout inválido/i);
        await routingPage.goto('http://localhost:4173/checkout/test-token-routing-123/');
        await routingPage.waitForSelector('#checkout-error:not(.hidden)');
        assert.equal(await routingPage.evaluate(() => location.pathname), '/checkout/test-token-routing-123/');
        await routingPage.close();

        const pixPage = await context.newPage();
        pixPage.on('pageerror', error => pageErrors.push(error.message));
        await pixPage.goto(`http://localhost:4173/checkout/${tokenA}`);
        await pixPage.waitForSelector('#checkout-content:not(.hidden)');
        await pixPage.evaluate(() => {
            sessionStorage.setItem('mirai.test_unknown_consent', 'yes');
            localStorage.removeItem('mirai.analytics_consent.v1');
        });
        await pixPage.reload();
        await pixPage.waitForSelector('#checkout-content:not(.hidden)');
        await pixPage.locator('#analytics-consent-dialog').waitFor({ state: 'visible' });
        assert.equal(await pixPage.locator('#analytics-consent-dialog').evaluate(element => getComputedStyle(element).position), 'static');
        await pixPage.getByRole('button', { name: 'Gerar Pix' }).click({ trial: true });
        const pixValidation = await pixPage.evaluate(async ({ code, mercadoPagoSample, invalidInitiation }) => {
            const { validatePixPayload, pixImageMime } = await import('/js/pix.js');
            return {
                valid: validatePixPayload(code, '99.00'),
                malformed: validatePixPayload('000201-pix-code', '99.00'),
                badCrc: validatePixPayload(`${code.slice(0, -4)}0000`, '99.00'),
                amountMismatch: validatePixPayload(code, '98.00'),
                mercadoPagoWithoutOptionalTag: validatePixPayload(mercadoPagoSample, '10.00'),
                invalidInitiationMethod: validatePixPayload(invalidInitiation, '99.00'),
                jpegMime: pixImageMime('/9j/4AAQSkZJRgABAQ=='),
            };
        }, { code: pixCode(), mercadoPagoSample, invalidInitiation: pixCode('99.00', '99') });
        assert.equal(pixValidation.valid, null);
        assert.equal(pixValidation.malformed, 'malformed_payload');
        assert.equal(pixValidation.badCrc, 'invalid_crc');
        assert.equal(pixValidation.amountMismatch, 'amount_mismatch');
        assert.equal(pixValidation.mercadoPagoWithoutOptionalTag, null);
        assert.equal(pixValidation.invalidInitiationMethod, 'malformed_payload');
        assert.equal(pixValidation.jpegMime, 'image/jpeg');
        assert.equal(await pixPage.locator('#project-description').textContent(), '<img src=x onerror="window.xss=true">Mixagem');
        assert.equal(await pixPage.locator('#project-description img').count(), 0);
        assert.equal(await pixPage.evaluate(() => window.xss), undefined);
        assert.equal(await pixPage.locator('input[name="payment_option"]:checked').getAttribute('value'), 'integral');
        await pixPage.getByLabel('Entrada').check();
        await pixPage.evaluate(() => {
            const button = document.getElementById('generate-pix');
            button.click();
            button.click();
        });
        await pixPage.waitForSelector('#pix-result:not(.hidden)');
        assert.equal(pixRequests, 1);
        assert.equal(await pixPage.locator('#pix-code').inputValue(), pixCode());
        const renderedQr = await pixPage.locator('#pix-qr').getAttribute('src');
        assert.ok(renderedQr.startsWith('data:image/png;base64,'));

        const cancelPage = await context.newPage();
        await cancelPage.goto(`http://localhost:4173/checkout/${tokenB}`);
        await cancelPage.waitForSelector('#checkout-content:not(.hidden)');
        await cancelPage.getByLabel('Entrada').check();
        await cancelPage.locator('#generate-pix').click();
        await cancelPage.waitForSelector('#pix-result:not(.hidden)');
        const pixBeforeSwitch = pixRequests;
        await cancelPage.locator('#method-card').click();
        assert.equal(await cancelPage.locator('#pix-result').isHidden(), true);
        assert.equal(await cancelPage.locator('#pix-code').isVisible(), false);
        assert.equal(await cancelPage.locator('#pix-ticket').isVisible(), false);
        assert.match(await cancelPage.locator('#card-error').textContent(), /Pix pendente/);
        assert.equal(await cancelPage.getByRole('button', { name: 'Pagar cartão' }).count(), 0);
        await cancelPage.locator('#method-pix').click();
        assert.equal(await cancelPage.locator('#pix-result').isVisible(), true);
        await cancelPage.getByLabel('Pagamento completo').check();
        assert.equal(await cancelPage.locator('#pix-result').isHidden(), true);
        await cancelPage.getByLabel('Entrada').check();
        assert.equal(await cancelPage.locator('#pix-result').isVisible(), true);
        assert.equal(pixRequests, pixBeforeSwitch);
        await cancelPage.locator('#method-card').click();
        await cancelPage.locator('#cancel-pix').click();
        await cancelPage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        assert.equal(cancelPixRequests, 1);
        assert.equal(await cancelPage.locator('#pix-pending-notice').isHidden(), true);
        await cancelPage.close();

        await pixPage.waitForFunction(() => document.getElementById('pix-qr')?.naturalWidth > 0);
        const decodedQr = qrCodec('decode', { image: renderedQr.slice('data:image/png;base64,'.length) }).payload;
        assert.equal(decodedQr, pixCode(), 'the rendered QR must encode the provider copy-and-paste code');
        assert.equal(decodedQr, await pixPage.locator('#pix-code').inputValue());
        assert.match(await pixPage.locator('#pix-expiration').textContent(), /21\/09\/2099.*horário local/);
        assert.equal(await pixPage.locator('#payment-options').getAttribute('aria-describedby'), 'payment-option-help');
        await pixPage.locator('#copy-pix').click();
        await pixPage.waitForFunction(() => document.getElementById('copy-pix')?.textContent === 'Código copiado');
        assert.equal(await pixPage.locator('#copy-pix').textContent(), 'Código copiado');
        assert.equal(await pixPage.locator('#pix-code').inputValue(), pixCode(), 'the displayed copy-and-paste code is unchanged');
        assert.equal(await pixPage.evaluate(() => navigator.clipboard.readText()), decodedQr);
        // AUD6-S06-005: backend wording for operators becomes buyer-facing guidance.
        const human = await pixPage.evaluate(async () => {
            const { humanCheckoutMessage } = await import('/js/checkout.js');
            return [
                humanCheckoutMessage('Pagamento em processamento requer conciliacao.', 409),
                humanCheckoutMessage('Checkout temporariamente indisponivel.', 503),
                humanCheckoutMessage('qualquer', 429),
                humanCheckoutMessage('A reserva deste beat expirou ou foi liberada. Solicite a licença novamente no catálogo.', 409),
            ];
        });
        assert.match(human[0], /Estamos conferindo/);
        assert.doesNotMatch(human.join(' '), /conciliacao|indisponivel/);
        assert.match(human[1], /temporariamente indisponível/);
        assert.match(human[2], /Muitas tentativas/);
        assert.match(human[3], /reserva deste beat expirou/);
        assert.equal(await pixPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
        const recoveredPage = await context.newPage();
        await recoveredPage.goto(`http://localhost:4173/checkout/${tokenL}`);
        await recoveredPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Você já possui um Pix pendente'));
        assert.equal(await recoveredPage.locator('#pix-result').isHidden(), true, 'Entrada Pix stays hidden while Integral is selected');
        assert.equal(await recoveredPage.locator('#generate-pix').isDisabled(), true);
        await recoveredPage.getByLabel('Entrada').check();
        assert.equal(await recoveredPage.locator('#pix-code').inputValue(), pixCode());
        assert.equal(await recoveredPage.locator('#generate-pix').textContent(), 'Visualizar Pix existente');
        const beforeRecovery = pendingRequests;
        await recoveredPage.locator('#generate-pix').click();
        await recoveredPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Você já possui um Pix pendente'));
        assert.equal(pendingRequests, beforeRecovery + 1);
        assert.equal(pixRequests, pixBeforeSwitch, 'recovery must not create another Order');
        await recoveredPage.locator('#method-card').click();
        assert.equal(await recoveredPage.locator('#pix-result').isHidden(), true);
        await recoveredPage.locator('#method-pix').click();
        assert.equal(await recoveredPage.locator('#pix-code').inputValue(), pixCode());
        await recoveredPage.reload();
        await recoveredPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Você já possui um Pix pendente'));
        await recoveredPage.getByLabel('Entrada').check();
        assert.equal(await recoveredPage.locator('#pix-code').inputValue(), pixCode());
        pendingAmount = '98.00';
        await recoveredPage.locator('#generate-pix').click();
        await recoveredPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Não foi possível recuperar'));
        assert.equal(await recoveredPage.locator('#pix-result').isHidden(), true);
        pendingAmount = '99.00';
        pendingExpired = true;
        await recoveredPage.locator('#generate-pix').click();
        await recoveredPage.waitForFunction(() => document.querySelector('#pix-validation-message')?.textContent.includes('expirou'));
        assert.equal(await recoveredPage.locator('#pix-code').isHidden(), true);
        assert.equal(await recoveredPage.locator('#pix-ticket').isHidden(), true);
        pendingExpired = false;
        pendingFailure = true;
        await recoveredPage.locator('#generate-pix').click();
        await recoveredPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('cobrança continua pendente'));
        assert.equal(await recoveredPage.locator('#pix-result').isHidden(), true, 'unconfirmed Pix data is not reused');
        pendingFailure = false;
        pendingStatus = 'approved';
        await recoveredPage.locator('#generate-pix').click();
        await recoveredPage.waitForFunction(() => document.querySelector('#checkout-terminal')?.textContent.includes('Pagamento confirmado!'));
        assert.equal(await recoveredPage.locator('#pix-result').isHidden(), true);
        assert.equal(pixRequests, pixBeforeSwitch);
        await recoveredPage.close();

        pendingStatus = 'pending';
        const rejectedRecoveryPage = await context.newPage();
        await rejectedRecoveryPage.goto(`http://localhost:4173/checkout/${tokenL}`);
        await rejectedRecoveryPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Você já possui um Pix pendente'));
        await rejectedRecoveryPage.getByLabel('Entrada').check();
        pendingStatus = 'rejected';
        await rejectedRecoveryPage.locator('#generate-pix').click();
        await rejectedRecoveryPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('não foi aprovado'));
        assert.equal(await rejectedRecoveryPage.locator('#pix-result').isHidden(), true);
        await rejectedRecoveryPage.close();
        pendingStatus = 'pending';

        const authRecoveryPage = await context.newPage();
        await authRecoveryPage.addInitScript(() => localStorage.setItem('mirai.auth.cliente.access_token', 'client-token'));
        await authRecoveryPage.goto('http://localhost:4173/checkout?proposta=71');
        await authRecoveryPage.waitForFunction(() => document.querySelector('#payment-result')?.textContent.includes('Você já possui um Pix pendente'));
        await authRecoveryPage.getByLabel('Entrada').check();
        assert.equal(await authRecoveryPage.locator('#pix-code').inputValue(), pixCode());
        assert.equal(authenticatedPixRequests, 0);
        await authRecoveryPage.close();
        const documentedPixPage = await context.newPage();
        await documentedPixPage.goto(`http://localhost:4173/checkout/${tokenJ}`);
        await documentedPixPage.waitForSelector('#checkout-content:not(.hidden)');
        await documentedPixPage.locator('#generate-pix').click();
        await documentedPixPage.waitForSelector('#pix-result:not(.hidden)');
        assert.equal(await documentedPixPage.locator('#pix-code').inputValue(), mercadoPagoSample);
        await documentedPixPage.waitForFunction(() => document.getElementById('pix-qr')?.naturalWidth > 0);
        const documentedQr = await documentedPixPage.locator('#pix-qr').getAttribute('src');
        assert.equal(qrCodec('decode', { image: documentedQr.slice('data:image/png;base64,'.length) }).payload, mercadoPagoSample);
        assert.equal(await documentedPixPage.locator('#copy-pix').isVisible(), true);
        await documentedPixPage.close();

        for (const token of [tokenH, tokenI]) {
            const guardedPixPage = await context.newPage();
            await guardedPixPage.goto(`http://localhost:4173/checkout/${token}`);
            await guardedPixPage.waitForSelector('#checkout-content:not(.hidden)');
            await guardedPixPage.locator('#generate-pix').click();
            await guardedPixPage.waitForSelector('#pix-result:not(.hidden)');
            assert.equal(await guardedPixPage.locator('#pix-code').isVisible(), false);
            assert.equal(await guardedPixPage.locator('#pix-qr').isVisible(), false);
            assert.equal(await guardedPixPage.locator('#copy-pix').isVisible(), false);
            assert.equal(await guardedPixPage.locator('#pix-validation-message').isVisible(), true);
            await guardedPixPage.close();
        }

        const cardPage = await context.newPage();
        cardPage.on('pageerror', error => pageErrors.push(error.message));
        const cardConsole = [];
        cardPage.on('console', message => cardConsole.push(message.text()));
        await cardPage.setViewportSize({ width: 320, height: 800 });
        await cardPage.goto(`http://localhost:4173/checkout/${tokenB}`);
        await cardPage.waitForSelector('#checkout-content:not(.hidden)');
        await cardPage.locator('#method-card').click();
        await cardPage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        assert.equal(await cardPage.evaluate(() => window.__brickSettings.initialization.amount), 198);
        await cardPage.locator('input[name="payment_option"][value="entrada"]').check();
        await cardPage.waitForFunction(() => window.__brickSettings.initialization.amount === 99);
        await cardPage.locator('input[name="payment_option"][value="integral"]').check();
        await cardPage.waitForFunction(() => window.__brickSettings.initialization.amount === 198);
        await cardPage.locator('#method-pix').click();
        await cardPage.waitForFunction(() => window.__brickUnmounts === 3);
        assert.equal(await cardPage.getByRole('button', { name: 'Pagar cartão' }).count(), 0);
        await cardPage.locator('#method-card').click();
        await cardPage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        assert.equal(await cardPage.evaluate(() => window.__brickSettings.initialization.amount), 198);
        await cardPage.evaluate(() => window.__brickSettings.callbacks.onError({ cause: 'no_installments_in_selected_range', message: 'sensitive provider detail' }));
        assert.match(await cardPage.locator('#card-error').textContent(), /Pix continua disponível/);
        assert.equal(cardConsole.some(message => message.includes('sensitive provider detail')), false);
        await cardPage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'transient-token', payment_method_id: 'visa', installments: 3,
            payer: { email: 'buyer@example.com', identification: { type: 'CPF', number: '12345678900' } },
        }, { paymentTypeId: 'credit_card' }));
        assert.equal(cardPayload.payment_option, 'integral');
        assert.equal(cardPayload.installments, 3);
        assert.equal(cardPayload.card_token, 'transient-token');
        assert.equal(cardPayload.device_id, 'official-device-123');
        assert.equal('amount' in cardPayload, false);
        assert.equal('pan' in cardPayload || 'cvv' in cardPayload, false);
        assert.equal(await cardPage.locator('#challenge-container').isVisible(), true);
        const challengeCases = [
            ['https://www.mercadopago.com/auth/card/validation/pages/remedies/opaque', true],
            ['https://www.mercadopago.com.ar/auth/card/validation/pages/remedies/opaque', true],
            ['https://www.mercadopago.exemplo-malicioso.com/auth/challenge', false],
            ['https://mercadopago.com.evil.example/auth/challenge', false],
            ['https://foo.mercadopago.com/auth/challenge', false],
            ['https://www.mercadopago.com.br/auth/challenge', false],
            ['http://www.mercadopago.com/auth/challenge', false],
            ['https://user:pass@www.mercadopago.com/auth/challenge', false],
            ['https://www.mercadopago.com:443/auth/challenge', false],
            ['https://%77ww.mercadopago.com/auth/challenge', false],
            ['https://www.mercadopago.com\\@evil.example/auth/challenge', false],
        ];
        for (const [url, allowed] of challengeCases) {
            challengeUrl = url;
            await cardPage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
                token: 'challenge-token', payment_method_id: 'visa', installments: 1,
                payer: { email: 'buyer@example.com' },
            }, { paymentTypeId: 'credit_card' }));
            assert.equal(await cardPage.locator('#challenge-container').isVisible(), allowed, url);
            if (!allowed) {
                assert.equal(await cardPage.locator('#challenge-frame').getAttribute('src'), 'about:blank');
                assert.match(await cardPage.locator('#payment-result').textContent(), /não pôde ser exibida/);
            }
        }
        challengeUrl = 'https://www.mercadopago.com/auth/challenge';
        assert.equal(await cardPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);

        missingPublicKey = true;
        const configFailurePage = await context.newPage();
        await configFailurePage.goto(`http://localhost:4173/checkout/${tokenB}`);
        await configFailurePage.waitForSelector('#checkout-content:not(.hidden)');
        await configFailurePage.locator('#method-card').click();
        await configFailurePage.waitForSelector('#card-error:not(.hidden)');
        assert.match(await configFailurePage.locator('#card-error').textContent(), /configuração/);
        missingPublicKey = false;
        configStatus = 503;
        const unavailableConfigPage = await context.newPage();
        await unavailableConfigPage.goto(`http://localhost:4173/checkout/${tokenB}`);
        await unavailableConfigPage.waitForSelector('#checkout-content:not(.hidden)');
        await unavailableConfigPage.locator('#method-card').click();
        await unavailableConfigPage.waitForSelector('#card-error:not(.hidden)');
        assert.match(await unavailableConfigPage.locator('#card-error').textContent(), /configuração/);
        configStatus = 200;

        sdkFailure = true;
        const failurePage = await context.newPage();
        failurePage.on('pageerror', error => pageErrors.push(error.message));
        await failurePage.goto(`http://localhost:4173/checkout/${tokenC}`);
        await failurePage.waitForSelector('#checkout-content:not(.hidden)');
        await failurePage.locator('#method-card').click();
        await failurePage.waitForSelector('#card-error:not(.hidden)');
        assert.match(await failurePage.locator('#card-error').textContent(), /use Pix/i);
        await failurePage.locator('#method-pix').click();
        assert.equal(await failurePage.locator('#generate-pix').isVisible(), true);
        sdkFailure = false;
        await failurePage.locator('#method-card').click();
        await failurePage.getByRole('button', { name: 'Pagar cartão' }).waitFor();

        securityFailure = true;
        const noDevicePage = await context.newPage();
        await noDevicePage.goto(`http://localhost:4173/checkout/${tokenC}`);
        await noDevicePage.waitForSelector('#checkout-content:not(.hidden)');
        await noDevicePage.locator('#generate-pix').click();
        await noDevicePage.waitForSelector('#pix-result:not(.hidden)');
        assert.equal(pixPayload.device_id, null);
        await noDevicePage.close();
        securityFailure = false;

        const blockedDevicePage = await context.newPage();
        await blockedDevicePage.addInitScript(() => {
            const appendChild = Element.prototype.appendChild;
            Element.prototype.appendChild = function (child) {
                if (child?.src === 'https://www.mercadopago.com/v2/security.js') {
                    throw new Error('security_script_blocked');
                }
                return appendChild.call(this, child);
            };
        });
        await blockedDevicePage.goto(`http://localhost:4173/checkout/${tokenC}`);
        await blockedDevicePage.waitForSelector('#checkout-content:not(.hidden)');
        await blockedDevicePage.locator('#generate-pix').click();
        await blockedDevicePage.waitForSelector('#pix-result:not(.hidden)');
        assert.equal(pixPayload.device_id, null);
        await blockedDevicePage.close();

        for (const [width, height] of [[375, 800], [390, 844], [414, 896], [768, 900], [1024, 900], [1440, 1000]]) {
            await failurePage.setViewportSize({ width, height });
            assert.equal(await failurePage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true, `overflow at ${width}`);
        }

        const statePage = await context.newPage();
        await statePage.goto(`http://localhost:4173/checkout/${tokenD}`);
        await statePage.waitForSelector('#checkout-content:not(.hidden)');
        assert.match(await statePage.locator('#checkout-terminal').textContent(), /Entrada confirmada/);
        assert.equal(await statePage.locator('input[name="payment_option"]:checked').getAttribute('value'), 'saldo');
        await statePage.goto(`http://localhost:4173/checkout/${tokenE}`);
        assert.match(await statePage.locator('#checkout-terminal').textContent(), /Pagamento confirmado/);
        assert.equal((await statePage.locator('#checkout-terminal').textContent()).match(/Pagamento confirmado/g).length, 1);
        assert.equal(await statePage.locator('#checkout-terminal a').getAttribute('href'), '/acesso');
        assert.equal(await statePage.locator('#payment-result').isHidden(), true);
        assert.equal(await statePage.locator('#checkout-form').isHidden(), true);
        await statePage.goto(`http://localhost:4173/checkout/${tokenF}`);
        assert.match(await statePage.locator('#checkout-terminal').textContent(), /cancelada/);
        await statePage.goto(`http://localhost:4173/checkout/${tokenG}`);
        await statePage.locator('#method-card').click();
        await statePage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        await statePage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'retry-token', payment_method_id: 'visa', installments: 1, payer: { email: 'buyer@example.com' },
        }, { paymentTypeId: 'credit_card' })).catch(() => {});
        assert.match(await statePage.locator('#payment-result').textContent(), /não foi aprovado/);
        await statePage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'debit-token', payment_method_id: 'debvisa', installments: 1, payer: { email: 'buyer@example.com' },
        }, { paymentTypeId: 'debit_card' })).catch(() => {});
        assert.equal(cardPayload.payment_method_type, 'debit_card');
        await statePage.goto(`http://localhost:4173/checkout/${tokenK}`);
        await statePage.locator('#method-card').click();
        await statePage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        await statePage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'synthetic-token', payment_method_id: 'visa', installments: 1,
            payer: { email: 'buyer@example.invalid' },
        }, { paymentTypeId: 'credit_card' }));
        await statePage.waitForFunction(() => document.querySelector('#checkout-terminal').textContent.includes('Pagamento confirmado!'));
        assert.equal(await statePage.locator('#payment-result').isHidden(), true);
        assert.equal(await statePage.locator('#checkout-terminal a').getAttribute('href'), '/acesso');
        await statePage.goto('http://localhost:4173/checkout/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
        await statePage.waitForSelector('#checkout-error:not(.hidden)');
        assert.match(await statePage.locator('#checkout-error-message').textContent(), /não encontrado/i);

        const authenticatedPage = await context.newPage();
        authenticatedPage.on('pageerror', error => pageErrors.push(error.message));
        await authenticatedPage.addInitScript(() => localStorage.setItem('mirai.auth.cliente.access_token', 'client-token'));
        await authenticatedPage.goto('http://localhost:4173/checkout?proposta=42');
        await authenticatedPage.waitForSelector('#checkout-content:not(.hidden)');
        assert.equal(await authenticatedPage.locator('input[name="payment_option"]').count(), 1);
        assert.equal(await authenticatedPage.locator('input[name="payment_option"]').first().inputValue(), 'integral');
        await authenticatedPage.getByRole('button', { name: 'Gerar Pix' }).click();
        await authenticatedPage.waitForSelector('#pix-result:not(.hidden)');
        assert.equal(authenticatedPixRequests, 1);
        await authenticatedPage.close();

        const previewPage = await context.newPage();
        previewPage.on('pageerror', error => pageErrors.push(error.message));
        await previewPage.addInitScript(() => localStorage.setItem('mirai.auth.cliente.access_token', 'client-token'));
        await previewPage.goto('https://deploy-preview-19--miraihitstudio.netlify.app/checkout?proposta=70');
        // AUD-S12-004: previews never reach the production API; they fail closed.
        await previewPage.waitForSelector('#checkout-error:not(.hidden)');
        assert.deepEqual(previewApiRequests, []);
        assert.equal(await previewPage.locator('#checkout-content:not(.hidden)').count(), 0);
        assert.equal(await previewPage.evaluate(() => typeof window.__brickSettings), 'undefined');
        await previewPage.close();

        assert.deepEqual(pageErrors, []);
        console.log('PASS: guest checkout, authenticated preview card config, Pix, card tokenization, 3DS and mobile structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
