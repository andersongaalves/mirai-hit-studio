// Browser-only analytics checks. Every network request is intercepted locally.
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
        return route.fulfill({ body: await fs.readFile(file), contentType: { '.js': 'text/javascript', '.html': 'text/html', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
    } catch { return route.fulfill({ status: 200, body: '' }); }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const analyticsRequests = [], leadPayloads = [];
        let shouldFailLead = false;
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173') return staticResponse(route);
            if (url.origin === 'https://www.googletagmanager.com') {
                analyticsRequests.push(url.href);
                return route.fulfill({ contentType: 'text/javascript', body: '' });
            }
            if (url.origin === 'http://localhost:8000') {
                if (url.pathname === '/config') return route.fulfill({ json: { desconto: 0, val_extra_duracao: 0, val_extra_pessoa: 0, val_extra_canal_voz: 0, val_extra_canal_inst: 0, val_extra_melodia: 0, val_inst_hibrido: 0, val_inst_gravado: 0, val_lease_desconto: 0, val_extra_revisao: 0, val_prazo_urgente: 0, val_prazo_express: 0 } });
                if (url.pathname === '/servicos') return route.fulfill({ json: [{ id: 7, nome: 'Servico', categoria: 'avulso', valor_base: 100, aplica_desconto: false, parametros: '' }] });
                if (url.pathname === '/orcamentos' && route.request().method() === 'POST') {
                    leadPayloads.push(route.request().postDataJSON());
                    return route.fulfill(shouldFailLead ? { status: 500, json: { detail: 'erro sintetico' } } : { json: { id: leadPayloads.length } });
                }
                return route.fulfill({ json: [] });
            }
            return route.fulfill({ status: 200, body: '' });
        });

        await page.goto('http://localhost:4173/calculadora.html');
        await page.waitForSelector('#analytics-consent-dialog');
        assert.equal(analyticsRequests.length, 0);
        assert.equal(await page.evaluate(async () => (await import('/js/analytics.js')).track('view_service', { service_id: 7, email: 'blocked@example.com' })), false);
        await page.getByRole('button', { name: 'Recusar metricas' }).click();
        assert.equal(await page.evaluate(() => localStorage.getItem('mirai.analytics_consent.v1')), 'rejected');
        assert.equal(analyticsRequests.length, 0);

        await page.getByRole('button', { name: 'Privacidade' }).click();
        await page.getByRole('button', { name: 'Aceitar metricas' }).click();
        await page.waitForFunction(() => window.dataLayer?.some(item => item[0] === 'event' && item[1] === 'page_view'), null, { timeout: 5000 });
        await page.waitForTimeout(50);
        assert.equal(await page.evaluate(() => localStorage.getItem('mirai.analytics_consent.v1')), 'accepted');
        assert.equal(analyticsRequests.length, 1);
        await page.evaluate(async () => (await import('/js/analytics.js')).track('view_service', { service_id: 7, email: 'blocked@example.com', whatsapp: '000', briefing: 'private' }));
        const serviceEvent = await page.evaluate(() => window.dataLayer.find(item => item[0] === 'event' && item[1] === 'view_service'));
        assert.deepEqual(serviceEvent[2], { service_id: 7 });

        await page.waitForSelector('#srv_7', { state: 'attached', timeout: 5000 });
        await page.evaluate(async () => {
            const { state } = await import('/js/state.js');
            state.servicoSelecionadoOBJ = { id: 7, nome: 'Servico', parametros: '', valor_base: 100, aplica_desconto: false };
            state.valorTotalCalculado = 100;
            document.getElementById('nome_cliente').value = 'Pessoa privada';
            document.getElementById('email').value = 'private@example.com';
            document.getElementById('whatsapp').value = '000000000';
        });
        await page.evaluate(() => document.getElementById('btn-solicitar').click());
        await page.waitForFunction(() => window.dataLayer?.filter(item => item[0] === 'event' && item[1] === 'generate_lead').length === 1, null, { timeout: 5000 });
        assert.equal(leadPayloads.length, 1);
        shouldFailLead = true;
        await page.evaluate(() => document.getElementById('btn-solicitar').click());
        await page.waitForTimeout(50);
        const leadEvents = await page.evaluate(() => window.dataLayer.filter(item => item[0] === 'event' && item[1] === 'generate_lead'));
        assert.deepEqual(leadEvents, [['event', 'generate_lead', { service_id: 7 }]]);
        await page.getByRole('button', { name: 'Privacidade' }).click();
        await page.getByRole('button', { name: 'Recusar metricas' }).click();
        assert.equal(await page.evaluate(async () => (await import('/js/analytics.js')).track('view_service', { service_id: 7 })), false);

        const noProvider = await context.newPage();
        await noProvider.goto('http://localhost:4173/analytics-test.html');
        const absent = await noProvider.evaluate(async () => {
            const analytics = await import('/js/analytics.js');
            analytics.initAnalytics();
            analytics.setAnalyticsConsent('accepted');
            return analytics.track('view_service', { service_id: 7 });
        });
        assert.equal(absent, false);
        await noProvider.close();
        assert.deepEqual(errors, []);
        console.log('PASS: consent gate, preference persistence, provider loading, PII filtering, lead confirmation and provider absence.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
