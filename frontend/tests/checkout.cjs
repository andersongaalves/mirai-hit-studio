const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const tokenA = '11111111-1111-4111-8111-111111111111';
const tokenB = '22222222-2222-4222-8222-222222222222';
const tokenC = '33333333-3333-4333-8333-333333333333';
const tokenD = '44444444-4444-4444-8444-444444444444';
const tokenE = '55555555-5555-4555-8555-555555555555';
const tokenF = '66666666-6666-4666-8666-666666666666';
const tokenG = '77777777-7777-4777-8777-777777777777';
const summaries = new Map([
    [tokenA, summary('<img src=x onerror="window.xss=true">Mixagem')],
    [tokenB, summary('Trilha original')],
    [tokenC, summary('Masterização')],
    [tokenD, { ...summary('Produção'), status: 'parcialmente_paga', valor_pago: '99.00', saldo: '99.00', opcoes: [{ tipo: 'saldo', titulo: 'Saldo restante', valor: '99.00' }] }],
    [tokenE, { ...summary('Produção'), status: 'paga', valor_pago: '198.00', saldo: '0.00', opcoes: [] }],
    [tokenF, { ...summary('Produção'), status: 'cancelada', opcoes: [] }],
    [tokenG, summary('Beat exclusivo')],
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
    const pathname = url.pathname.startsWith('/checkout/') ? '/checkout.html' : url.pathname;
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
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ permissions: ['clipboard-read', 'clipboard-write'] });
        await context.addInitScript(() => localStorage.setItem('mirai.analytics_consent.v1', 'rejected'));
        let pixRequests = 0;
        let cardPayload = null;
        let sdkFailure = false;
        const pageErrors = [];
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173') return staticResponse(route);
            if (url.origin === 'https://sdk.mercadopago.com') {
                if (sdkFailure) return route.abort();
                return route.fulfill({ contentType: 'text/javascript', body: `
                    window.MercadoPago = class {
                        bricks() { return { create: async (_name, id, settings) => {
                            window.__brickSettings = settings;
                            const button = document.createElement('button');
                            button.type = 'button'; button.textContent = 'Pagar cartão';
                            document.getElementById(id).appendChild(button);
                            settings.callbacks.onReady();
                            return { unmount: async () => document.getElementById(id).replaceChildren() };
                        } }; }
                    };
                ` });
            }
            if (url.origin === 'http://localhost:8000') {
                const match = url.pathname.match(/^\/checkout\/([0-9a-f-]{36})(.*)$/i);
                if (url.pathname === '/checkout/config') return route.fulfill({ json: { mercado_pago_public_key: 'TEST-public-key' } });
                if (!match) return route.fulfill({ status: 404, json: { detail: 'not found' } });
                const [, token, suffix] = match;
                if (suffix === '' && route.request().method() === 'GET') {
                    const data = summaries.get(token);
                    return data ? route.fulfill({ json: data }) : route.fulfill({ status: 404, json: { detail: 'Checkout não encontrado.' } });
                }
                if (suffix === '/pix' && route.request().method() === 'POST') {
                    pixRequests += 1;
                    await new Promise(resolve => setTimeout(resolve, 80));
                    return route.fulfill({ json: {
                        status: 'pending', checkout_status: 'pendente', payment_option: route.request().postDataJSON().payment_option,
                        valor: '99.00', moeda: 'BRL', challenge_url: null,
                        pix: { qr_code: '000201-pix-code', qr_code_base64: 'iVBORw0KGgo=', ticket_url: 'https://www.mercadopago.com.br/pay', expiration_time: '2026-09-21T12:00:00Z' },
                    } });
                }
                if (suffix === '/card' && route.request().method() === 'POST') {
                    cardPayload = route.request().postDataJSON();
                    return route.fulfill({ json: {
                        status: token === tokenG ? 'rejected' : 'action_required', checkout_status: 'pendente', payment_option: cardPayload.payment_option,
                        valor: '198.00', moeda: 'BRL', pix: null,
                        challenge_url: token === tokenG ? null : 'https://www.mercadopago.com.br/auth/challenge',
                    } });
                }
                if (suffix === '/status') return route.fulfill({ json: { status: 'pendente', valor_pago: '0.00', saldo: '198.00', pagamento_status: 'processando' } });
            }
            if (url.hostname.includes('mercadopago.')) return route.fulfill({ contentType: 'text/html', body: '<p>Challenge</p>' });
            return route.fulfill({ status: 200, body: '' });
        });

        const pixPage = await context.newPage();
        pixPage.on('pageerror', error => pageErrors.push(error.message));
        await pixPage.goto(`http://localhost:4173/checkout/${tokenA}`);
        await pixPage.waitForSelector('#checkout-content:not(.hidden)');
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
        assert.equal(await pixPage.locator('#pix-code').inputValue(), '000201-pix-code');
        await pixPage.locator('#copy-pix').click();
        await pixPage.waitForFunction(() => document.getElementById('copy-pix')?.textContent === 'Código copiado');
        assert.equal(await pixPage.locator('#copy-pix').textContent(), 'Código copiado');
        assert.equal(await pixPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);

        const cardPage = await context.newPage();
        cardPage.on('pageerror', error => pageErrors.push(error.message));
        await cardPage.setViewportSize({ width: 320, height: 800 });
        await cardPage.goto(`http://localhost:4173/checkout/${tokenB}`);
        await cardPage.waitForSelector('#checkout-content:not(.hidden)');
        await cardPage.locator('#method-card').click();
        await cardPage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        await cardPage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'transient-token', payment_method_id: 'visa', installments: 3,
            payer: { email: 'buyer@example.com', identification: { type: 'CPF', number: '12345678900' } },
        }, { paymentTypeId: 'credit_card' }));
        assert.equal(cardPayload.payment_option, 'integral');
        assert.equal(cardPayload.installments, 3);
        assert.equal(cardPayload.card_token, 'transient-token');
        assert.equal('amount' in cardPayload, false);
        assert.equal('pan' in cardPayload || 'cvv' in cardPayload, false);
        assert.equal(await cardPage.locator('#challenge-container').isVisible(), true);
        assert.equal(await cardPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);

        sdkFailure = true;
        const failurePage = await context.newPage();
        failurePage.on('pageerror', error => pageErrors.push(error.message));
        await failurePage.goto(`http://localhost:4173/checkout/${tokenC}`);
        await failurePage.waitForSelector('#checkout-content:not(.hidden)');
        await failurePage.locator('#method-card').click();
        await failurePage.waitForSelector('#card-error:not(.hidden)');
        assert.match(await failurePage.locator('#card-error').textContent(), /Pix continua disponível/);
        await failurePage.locator('#method-pix').click();
        assert.equal(await failurePage.locator('#generate-pix').isVisible(), true);

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
        assert.equal(await statePage.locator('#checkout-form').isHidden(), true);
        await statePage.goto(`http://localhost:4173/checkout/${tokenF}`);
        assert.match(await statePage.locator('#checkout-terminal').textContent(), /cancelada/);
        sdkFailure = false;
        await statePage.goto(`http://localhost:4173/checkout/${tokenG}`);
        await statePage.locator('#method-card').click();
        await statePage.getByRole('button', { name: 'Pagar cartão' }).waitFor();
        await statePage.evaluate(async () => window.__brickSettings.callbacks.onSubmit({
            token: 'retry-token', payment_method_id: 'visa', installments: 1, payer: { email: 'buyer@example.com' },
        }, { paymentTypeId: 'credit_card' })).catch(() => {});
        assert.match(await statePage.locator('#payment-result').textContent(), /não foi aprovado/);
        await statePage.goto('http://localhost:4173/checkout/88888888-8888-4888-8888-888888888888');
        await statePage.waitForSelector('#checkout-error:not(.hidden)');
        assert.match(await statePage.locator('#checkout-error-message').textContent(), /não encontrado/i);

        assert.deepEqual(pageErrors, []);
        console.log('PASS: guest summary, XSS safety, Pix, double-submit, card tokenization, 3DS, SDK failure and mobile structure.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
