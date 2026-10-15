// Roadmap 3.0, 5.10: contractual portal policies in the browser: the shared form (complete and
// inherited), the summary with origins, review counting in the stages panel and the client
// views that follow the contract (hidden deadlines, summary finance).
// Browser-only: the shared modules are rendered on a local page; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const PAGE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/css/variables.css"><link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/components/policies.css">
<link rel="stylesheet" href="/css/components/production-stages.css"></head>
<body><main id="root" style="padding:16px"></main><div id="client-detail-content"></div>
<script type="module">
import { policyForm, policySummary } from '/js/modules/policies.js';
import { stagesPanel } from '/js/modules/production_stages.js';
import { renderDetail as renderClient } from '/js/cliente/ui.js';
window.renderForm = options => {
    window.form = policyForm(options);
    document.getElementById('root').replaceChildren(window.form.element);
};
window.readForm = () => window.form.read();
window.renderSummary = (values, origins) => document.getElementById('root').replaceChildren(policySummary(values, origins));
window.renderStages = (role, data) => document.getElementById('root').replaceChildren(stagesPanel({ role, data }));
window.renderClient = (production, finance) => renderClient(production, [], finance, { onUpload() {}, onRefreshFiles() {}, onDownload() {}, onPreview() {} });
window.ready = true;
</script></body></html>`;

const DEFAULTS = { publicacao_previa: 'automatica', revisoes_excedentes: 'permitir', cliente_ve_etapas: true,
    cliente_ve_prazos_etapas: true, financeiro_cliente: 'completo' };
const stage = (extra) => ({ id: 1, ordem: 1, item_indice: 1, item_descricao: 'Plano', ordem_no_item: 1, nome: 'Rough Mix',
    status: 'em_revisao', prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: false,
    administrativa: false, acoes: [], ...extra });

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== 'http://localhost:4173') return route.fulfill({ status: 404, body: '' });
            if (url.pathname === '/__policies.html') return route.fulfill({ contentType: 'text/html', body: PAGE });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            try {
                return route.fulfill({ body: await fs.readFile(file), contentType:
                    { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
            } catch { return route.fulfill({ status: 404, body: '' }); }
        });
        await page.goto('http://localhost:4173/__policies.html');
        await page.waitForFunction(() => window.ready === true);

        // Global form: every key, booleans typed.
        await page.evaluate(values => window.renderForm({ values, idPrefix: 'g' }), DEFAULTS);
        assert.equal(await page.locator('.policy-form select').count(), 5);
        await page.getByLabel('Cliente vê as etapas').selectOption('false');
        await page.getByLabel('Prévias do produtor').selectOption('aprovacao_admin');
        assert.deepEqual(await page.evaluate(() => window.readForm()), {
            ...DEFAULTS, cliente_ve_etapas: false, publicacao_previa: 'aprovacao_admin' });

        // Service form: inherits by default and sends only what it overrides.
        await page.evaluate(values => window.renderForm({ values: { financeiro_cliente: 'resumido' }, inherited: values,
            inheritLabel: 'Padrão global', idPrefix: 's' }), { ...DEFAULTS, cliente_ve_prazos_etapas: false });
        assert.equal(await page.getByLabel('Cliente vê os prazos das etapas').locator('option').first().textContent(), 'Padrão global: Não');
        assert.deepEqual(await page.evaluate(() => window.readForm()), { financeiro_cliente: 'resumido' });
        await page.getByLabel('Revisões além das incluídas').selectOption('exigir_admin');
        await page.getByLabel('Financeiro no portal do cliente').selectOption('');
        assert.deepEqual(await page.evaluate(() => window.readForm()), { revisoes_excedentes: 'exigir_admin' });

        // Summary: value and origin of each policy, text only.
        await page.evaluate(([values, origins]) => window.renderSummary(values, origins), [
            { ...DEFAULTS, publicacao_previa: 'aprovacao_admin' },
            { publicacao_previa: 'excecao', revisoes_excedentes: 'contrato', cliente_ve_etapas: 'contrato',
              cliente_ve_prazos_etapas: 'global', financeiro_cliente: '<img src=x onerror=alert(1)>' },
        ]);
        const items = page.locator('.policy-summary li');
        assert.equal(await items.nth(0).textContent(), 'Prévias do produtor: Só após aprovação do Admin (exceção do Admin)');
        assert.equal(await items.nth(0).getAttribute('class'), 'is-exception');
        assert.match(await items.nth(3).textContent(), /\(padrão global\)$/);
        assert.equal(await page.locator('#root img').count(), 0);

        // Stages: review rounds used, extra rounds and unlimited stages; the client never sees them.
        const reviews = [[{ revisoes_incluidas: 2, revisoes_usadas: 0 }, /2 revisões incluídas(?! \()/],
            [{ revisoes_incluidas: 2, revisoes_usadas: 1 }, /2 revisões incluídas \(1 usada\)/],
            [{ revisoes_incluidas: 1, revisoes_usadas: 3 }, /1 revisão incluída \(3 usadas, 2 extra\)/],
            [{ revisoes_incluidas: null, revisoes_usadas: 2 }, /2 revisões usadas/]];
        for (const [extra, pattern] of reviews) {
            await page.evaluate(data => window.renderStages('produtor', data), { producao_id: 7, progresso_percentual: 0, etapas: [stage(extra)] });
            assert.match(await page.locator('.production-stage__meta').textContent(), pattern);
        }
        await page.evaluate(data => window.renderStages('cliente', data), { producao_id: 7, progresso_percentual: 0,
            etapas: [stage({ revisoes_incluidas: 1, revisoes_usadas: 3 })] });
        const clientMeta = await page.locator('.production-stage__meta').textContent();
        assert.doesNotMatch(clientMeta, /revis|Sem prazo/);

        // Client finance: the summary view shows status, balance and due date only.
        const production = { id: 7, titulo: 'Single', servico: 'Mix', status: 'em_producao', prazo_entrega: null,
            updated_at: '2026-10-14T12:00:00+00:00', etapas: '[]' };
        const charge = { status: 'parcial', valor_total: null, valor_pago: null, saldo_pendente: '400.00', moeda: 'BRL',
            vencimento: null, pagamentos: [] };
        await page.evaluate(([p, f]) => window.renderClient(p, f), [production, { producao_id: 7, cobranca: charge, checkout_url: null, resumido: true }]);
        const finance = await page.locator('.client-finance-grid').textContent();
        assert.match(finance, /Situação.*Saldo pendente.*Vencimento/);
        assert.doesNotMatch(finance, /Valor cobrado|Valor pago/);
        await page.evaluate(([p, f]) => window.renderClient(p, f), [production, { producao_id: 7, checkout_url: null,
            cobranca: { ...charge, valor_total: '800.00', valor_pago: '400.00' } }]);
        assert.match(await page.locator('.client-finance-grid').textContent(), /Valor cobrado.*Valor pago/);

        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            await page.evaluate(values => window.renderForm({ values, inherited: values, idPrefix: 'w' }), DEFAULTS);
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1), false,
                `policy form overflows at ${width}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: policy forms (complete and inherited), summary with origins, review counting and client policy views.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
