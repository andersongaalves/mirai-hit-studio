// Roadmap 3.0, 5.06: admin rendering of contract stages (values, approval, deadline, generation).
// Browser-only: the shared module is rendered on a local page; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const PAGE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/css/variables.css"><link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/components/production-stages.css"></head>
<body><main id="root" style="padding:16px"></main>
<script type="module">
import { stagesPanel } from '/js/modules/production_stages.js';
window.calls = [];
window.failNext = false;
window.render = data => {
    document.getElementById('root').replaceChildren(stagesPanel({
        role: 'admin', heading: false, data,
        onChange: async (stage, destino) => {
            window.calls.push(['status', stage.id, destino]);
            if (window.failNext) { window.failNext = false; throw new Error('Conclua antes a etapa Rough Mix.'); }
        },
        onDeadline: async (stage, prazo) => { window.calls.push(['prazo', stage.id, prazo]); },
        onGenerate: async () => { window.calls.push(['gerar']); },
    }));
};
window.ready = true;
</script></body></html>`;

const STAGES = {
    producao_id: 7, progresso_percentual: 20, pode_gerar: false,
    etapas: [
        { id: 1, ordem: 1, item_indice: 1, item_descricao: 'Plano Start', ordem_no_item: 1, nome: 'Rough Mix', status: 'em_revisao',
          prazo: '2026-10-20T15:00:00+00:00', iniciada_em: null, concluida_em: null, depende_da_anterior: false, administrativa: false,
          unidade: 'faixa', revisoes_incluidas: 2, prazo_dias: 3, acoes: ['em_andamento', 'concluida'],
          servico_id: 1, peso_percentual: '20.00', valor: '160.00', responsavel_usuario_id: 2 },
        { id: 2, ordem: 2, item_indice: 1, item_descricao: 'Plano Start', ordem_no_item: 2, nome: 'Mixagem <script>x</script>', status: 'pendente',
          prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: true, administrativa: false,
          unidade: 'faixa', revisoes_incluidas: null, prazo_dias: 3, acoes: [],
          servico_id: 1, peso_percentual: '80.00', valor: '640.00', responsavel_usuario_id: 2 },
        { id: 3, ordem: 3, item_indice: 2, item_descricao: 'Master avulso', ordem_no_item: 1, nome: 'Master', status: 'concluida',
          prazo: null, iniciada_em: null, concluida_em: '2026-10-14T12:00:00+00:00', depende_da_anterior: false, administrativa: false,
          unidade: '', revisoes_incluidas: null, prazo_dias: null, acoes: ['em_andamento'],
          servico_id: 2, peso_percentual: '100.00', valor: '300.00', responsavel_usuario_id: 2 },
    ],
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== 'http://localhost:4173') return route.fulfill({ status: 404, body: '' });
            if (url.pathname === '/__stages.html') return route.fulfill({ contentType: 'text/html', body: PAGE });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            try {
                return route.fulfill({ body: await fs.readFile(file), contentType:
                    { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
            } catch { return route.fulfill({ status: 404, body: '' }); }
        });
        await page.goto('http://localhost:4173/__stages.html');
        await page.waitForFunction(() => window.ready === true);
        await page.evaluate(data => window.render(data), STAGES);

        const stages = page.locator('.production-stage');
        assert.equal(await stages.count(), 3);
        // Two contract items: stages are grouped under their item.
        assert.deepEqual(await page.locator('.production-stages__group').allTextContents(), ['Plano Start', 'Master avulso']);
        assert.match(await stages.nth(0).textContent(), /Em revisão.*2 revisões incluídas.*R\$\s160,00 \(20,00%\)/s);
        assert.match(await stages.nth(1).textContent(), /Mixagem <script>x<\/script>/);
        assert.equal(await page.locator('#root script').count(), 0);
        assert.equal(await page.getByRole('progressbar').getAttribute('aria-valuenow'), '20');

        // Approval with a server-side refusal first, then success.
        await page.evaluate(() => { window.failNext = true; });
        const approve = stages.nth(0).getByRole('button', { name: 'Aprovar e concluir' });
        await approve.click();
        await page.waitForFunction(() => document.querySelector('.production-stages__feedback').textContent.includes('Rough Mix'));
        assert.equal(await approve.isDisabled(), false);
        await approve.click();
        await stages.nth(2).getByRole('button', { name: 'Reabrir' }).click();
        await stages.nth(0).getByRole('button', { name: 'Retomar' }).click();

        // Deadline: a date or an explicit removal.
        const deadline = stages.nth(1).getByLabel('Prazo da etapa Mixagem <script>x</script>');
        await deadline.fill('2026-11-02');
        await stages.nth(1).getByRole('button', { name: 'Salvar prazo' }).click();
        assert.equal(await stages.nth(0).getByLabel(/Prazo da etapa Rough Mix/).inputValue(), '2026-10-20');
        await stages.nth(0).getByLabel(/Prazo da etapa Rough Mix/).fill('');
        await stages.nth(0).getByRole('button', { name: 'Salvar prazo' }).click();
        await page.waitForFunction(() => window.calls.length >= 6);
        assert.deepEqual(await page.evaluate(() => window.calls), [
            ['status', 1, 'concluida'], ['status', 1, 'concluida'], ['status', 3, 'em_andamento'],
            ['status', 1, 'em_andamento'], ['prazo', 2, '2026-11-02T12:00:00-03:00'], ['prazo', 1, null],
        ]);

        // Narrow screens keep everything inside the panel.
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        assert.equal(await page.locator('.production-stages').evaluate(el => el.scrollWidth <= el.clientWidth + 1), true);

        // Productions created before 5.06: generation from the frozen proposal.
        await page.evaluate(() => window.render({ producao_id: 8, progresso_percentual: 0, pode_gerar: true, etapas: [] }));
        assert.match(await page.locator('.production-stages__empty').textContent(), /criada antes das etapas contratuais/);
        await page.getByRole('button', { name: 'Gerar etapas do contrato' }).click();
        await page.waitForFunction(() => window.calls.at(-1)?.[0] === 'gerar');
        await page.evaluate(() => window.render({ producao_id: 9, progresso_percentual: 0, pode_gerar: false, etapas: [] }));
        assert.match(await page.locator('.production-stages__empty').textContent(), /Sem etapas de catálogo/);
        assert.equal(await page.getByRole('button', { name: 'Gerar etapas do contrato' }).count(), 0);

        assert.deepEqual(errors, []);
        console.log('PASS: admin stages show values and grouping, approve/reopen/resume, refusal feedback, deadlines, generation and narrow layout.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
