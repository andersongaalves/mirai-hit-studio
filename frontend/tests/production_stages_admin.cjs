// Roadmap 3.0, 5.06/5.07: admin rendering of contract stages (values, approval, deadline, generation,
// responsible per stage and history) and the producer view of stage ownership.
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
<body><main id="root" style="padding:16px"></main><div id="producer-detail-content"></div>
<script type="module">
import { stagesPanel } from '/js/modules/production_stages.js';
import { renderDetail } from '/js/produtor/ui.js';
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
window.renderAssign = data => {
    document.getElementById('root').replaceChildren(stagesPanel({
        role: 'admin', heading: false, data,
        producers: [{ id: 2, username: 'producer-a' }, { id: 3, username: 'producer-b' }],
        onAssign: async (stage, userId, motivo) => { window.calls.push(['assign', stage.id, userId, motivo]); },
        onHistory: async stage => {
            window.calls.push(['history', stage.id]);
            return [
                { id: 1, anterior_nome: null, novo_nome: 'producer-a', atribuido_por_nome: null, motivo: 'Atribuicao inicial', created_at: '2026-10-14T12:00:00+00:00' },
                { id: 2, anterior_nome: 'producer-a', novo_nome: 'producer-b <b>x</b>', atribuido_por_nome: 'admin', motivo: 'Especialista', created_at: '2026-10-14T13:00:00+00:00' },
            ];
        },
    }));
};
window.renderProducer = data => {
    document.getElementById('root').replaceChildren(stagesPanel({
        role: 'produtor', data, onChange: async (stage, destino) => { window.calls.push(['producer', stage.id, destino]); },
    }));
};
window.renderProducerDetail = production => renderDetail(production, [], { onStatus() {}, onUpload() {}, onDownload() {} });
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

        // 5.07: responsible per stage, executor and history (admin).
        const owned = structuredClone(STAGES);
        owned.etapas[0] = { ...owned.etapas[0], responsavel_usuario_id: 2, responsavel_nome: 'producer-a' };
        owned.etapas[1] = { ...owned.etapas[1], responsavel_usuario_id: 9, responsavel_nome: 'ex-produtor' };
        owned.etapas[2] = { ...owned.etapas[2], responsavel_usuario_id: 2, responsavel_nome: 'producer-a', executor_usuario_id: 2, executor_nome: 'producer-a' };
        await page.setViewportSize({ width: 1280, height: 900 });
        await page.evaluate(data => window.renderAssign(data), owned);
        const ownedStages = page.locator('.production-stage');
        assert.match(await ownedStages.nth(2).textContent(), /Responsável: producer-a.*Executada por producer-a/s);
        const firstSelect = ownedStages.nth(0).getByLabel('Responsável pela etapa Rough Mix');
        assert.equal(await firstSelect.inputValue(), '2');
        const applyFirst = ownedStages.nth(0).getByRole('button', { name: 'Atribuir' });
        assert.equal(await applyFirst.isDisabled(), true);
        await firstSelect.selectOption('3');
        await ownedStages.nth(0).getByLabel('Motivo da troca na etapa Rough Mix').fill('Especialista em mix');
        await applyFirst.click();
        // An inactive former responsible still shows as the current value.
        assert.equal(await ownedStages.nth(1).getByRole('combobox').inputValue(), '9');
        assert.match(await ownedStages.nth(1).getByRole('combobox').locator('option:checked').textContent(), /ex-produtor/);
        await ownedStages.nth(1).getByRole('combobox').selectOption('');
        await ownedStages.nth(1).getByRole('button', { name: 'Atribuir' }).click();
        // Concluded stages keep who executed them.
        assert.equal(await ownedStages.nth(2).getByRole('combobox').isDisabled(), true);
        assert.equal(await ownedStages.nth(2).getByRole('button', { name: 'Atribuir' }).isDisabled(), true);
        const historyButton = ownedStages.nth(0).getByRole('button', { name: 'Histórico' });
        await historyButton.click();
        await page.waitForFunction(() => !document.querySelector('.production-stage__history').classList.contains('hidden'));
        assert.equal(await historyButton.getAttribute('aria-expanded'), 'true');
        const historyText = await ownedStages.nth(0).locator('.production-stage__history').textContent();
        assert.match(historyText, /— → producer-a · Atribuicao inicial/);
        assert.match(historyText, /producer-a → producer-b <b>x<\/b> · por admin · Especialista/);
        assert.equal(await page.locator('.production-stage__history b').count(), 0);
        await historyButton.click();
        assert.equal(await historyButton.getAttribute('aria-expanded'), 'false');
        assert.deepEqual((await page.evaluate(() => window.calls)).slice(-3), [
            ['assign', 1, 3, 'Especialista em mix'], ['assign', 2, null, ''], ['history', 1],
        ]);
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
        await page.setViewportSize({ width: 1280, height: 900 });

        // 5.07: producer view shows only "Você"/"outro produtor" and acts on its own stages.
        await page.evaluate(() => window.renderProducer({ producao_id: 7, progresso_percentual: 0, etapas: [
            { id: 11, ordem: 1, item_indice: 1, item_descricao: 'Plano', ordem_no_item: 1, nome: 'Rough Mix', status: 'pendente',
              prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: false, administrativa: false,
              unidade: '', revisoes_incluidas: null, prazo_dias: null, acoes: ['em_andamento'], minha: true, responsavel_rotulo: 'Voce' },
            { id: 12, ordem: 2, item_indice: 1, item_descricao: 'Plano', ordem_no_item: 2, nome: 'Mixagem', status: 'pendente',
              prazo: null, iniciada_em: null, concluida_em: null, depende_da_anterior: false, administrativa: false,
              unidade: '', revisoes_incluidas: null, prazo_dias: null, acoes: [], minha: false, responsavel_rotulo: 'Outro produtor' },
        ] }));
        const producerStages = page.locator('.production-stage');
        assert.match(await producerStages.nth(0).textContent(), /Responsável: Você/);
        assert.match(await producerStages.nth(1).textContent(), /Responsável: outro produtor/);
        assert.equal(await producerStages.nth(0).evaluate(el => el.classList.contains('production-stage--mine')), true);
        assert.equal(await producerStages.nth(1).locator('button, select').count(), 0);

        // 5.07: a stage-only producer has no overall status action in the production detail.
        const production = { id: 7, titulo: 'Faixa', cliente: 'Cliente', servico: 'Mix', status: 'aguardando_inicio', etapas: '[]',
            prazo_entrega: null, created_at: '2026-10-14T12:00:00Z', updated_at: '2026-10-14T12:00:00Z' };
        await page.evaluate(item => window.renderProducerDetail(item), { ...production, coordenador: false });
        assert.match(await page.locator('#producer-detail-content').textContent(), /pelas etapas atribuídas a você/);
        assert.equal(await page.locator('#producer-detail-content .producer-detail__actions').count(), 0);
        await page.evaluate(item => window.renderProducerDetail(item), { ...production, coordenador: true });
        assert.equal(await page.locator('#producer-detail-content .producer-detail__actions button').count(), 1);
        assert.doesNotMatch(await page.locator('#producer-detail-content').textContent(), /pelas etapas atribuídas/);

        assert.deepEqual(errors, []);
        console.log('PASS: admin stages show values and grouping, approve/reopen/resume, refusal feedback, deadlines, generation, responsible/history (5.07), producer ownership view and narrow layout.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
