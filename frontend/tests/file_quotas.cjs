// Roadmap 3.0, 5.09: contractual file quotas in the browser: the shared editor (payload and
// validation), the admin usage list and the upload hints of the client and producer portals.
// Browser-only: the shared modules are rendered on a local page; no backend is contacted.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

const PAGE = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="/css/variables.css"><link rel="stylesheet" href="/css/base.css">
<link rel="stylesheet" href="/css/components/file-quotas.css"></head>
<body><main id="root" style="padding:16px"></main>
<div id="producer-detail-content"></div><div id="client-detail-content"></div>
<script type="module">
import { quotaEditor, quotaList, syncUploadHints } from '/js/modules/file_quotas.js';
import { renderDetail as renderProducer } from '/js/produtor/ui.js';
import { renderDetail as renderClient } from '/js/cliente/ui.js';
window.renderEditor = cotas => {
    window.editor = quotaEditor({ cotas, idPrefix: 'teste' });
    document.getElementById('root').replaceChildren(window.editor.element);
};
window.readEditor = () => {
    try { return { ok: window.editor.read() }; } catch (error) { return { error: error.message }; }
};
window.renderList = cotas => document.getElementById('root').replaceChildren(quotaList(cotas));
window.renderPortals = (production, files, cotas) => {
    renderProducer(production, files, { onStatus() {}, onUpload() {}, onDownload() {} });
    renderClient(production, files, { indisponivel: true }, { onUpload() {}, onRefreshFiles() {}, onDownload() {}, onPreview() {} });
    syncUploadHints(document, cotas);
};
window.sync = cotas => syncUploadHints(document, cotas);
window.ready = true;
</script></body></html>`;

const MB = 1024 * 1024;
const PRODUCTION = {
    id: 7, titulo: 'Single', servico: 'Mixagem', cliente: 'Cliente A', status: 'em_andamento',
    prazo_entrega: null, updated_at: '2026-10-14T12:00:00+00:00', etapas: '[]', valor_produtor: null,
};
const FILES = [
    { id: 11, tipo: 'previa', nome_exibicao: 'mix.mp3', versao: 1, substitui_arquivo_id: null, mime_type: 'audio/mpeg',
      tamanho_bytes: 1000, enviado_por_mim: true, created_at: '2026-10-14T12:00:00+00:00' },
    { id: 12, tipo: 'material', nome_exibicao: 'voz.wav', versao: 1, substitui_arquivo_id: null, mime_type: 'audio/wav',
      tamanho_bytes: 600 * 1024, enviado_por_mim: true, created_at: '2026-10-14T12:00:00+00:00' },
];
const QUOTAS = [
    { tipo: 'material', max_arquivos: 3, max_versoes: null, max_tamanho_mb: null, max_total_mb: 1, formatos: null,
      origem: 'contrato', arquivos_usados: 1, total_usado_bytes: 600 * 1024 },
    { tipo: 'previa', max_arquivos: 1, max_versoes: 2, max_tamanho_mb: 10, max_total_mb: null, formatos: ['audio/mpeg'],
      origem: 'admin', arquivos_usados: 1, total_usado_bytes: 1000 },
];

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin !== 'http://localhost:4173') return route.fulfill({ status: 404, body: '' });
            if (url.pathname === '/__quotas.html') return route.fulfill({ contentType: 'text/html', body: PAGE });
            const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            try {
                return route.fulfill({ body: await fs.readFile(file), contentType:
                    { '.js': 'text/javascript', '.css': 'text/css' }[path.extname(file)] || 'application/octet-stream' });
            } catch { return route.fulfill({ status: 404, body: '' }); }
        });
        await page.goto('http://localhost:4173/__quotas.html');
        await page.waitForFunction(() => window.ready === true);

        // Editor: an existing quota is prefilled; unchecked types send nothing ("no limit").
        await page.evaluate(cotas => window.renderEditor(cotas), [QUOTAS[1]]);
        assert.equal(await page.locator('.file-quota').count(), 4);
        assert.equal(await page.getByLabel('Limitar prévias').isChecked(), true);
        assert.equal(await page.getByLabel('Arquivos — Materiais do cliente').isDisabled(), true);
        assert.equal(await page.getByLabel('MP3 — Prévias').isChecked(), true);
        await page.getByLabel('Limitar materiais do cliente').check();
        await page.getByLabel('Arquivos — Materiais do cliente').fill('2');
        await page.getByLabel('Espaço total (MB) — Materiais do cliente').fill('6000');
        assert.deepEqual(await page.evaluate(() => window.readEditor()), {
            error: 'Espaço total (MB) de materiais do cliente deve ser um número inteiro entre 1 e 5000.',
        });
        await page.getByLabel('Espaço total (MB) — Materiais do cliente').fill('500');
        await page.getByLabel('WAV — Materiais do cliente', { exact: true }).check();
        await page.getByLabel('Versões por arquivo — Prévias').fill('');
        assert.deepEqual(await page.evaluate(() => window.readEditor()), { ok: [
            { tipo: 'material', max_arquivos: 2, max_versoes: null, max_tamanho_mb: null, max_total_mb: 500, formatos: ['audio/wav'] },
            { tipo: 'previa', max_arquivos: 1, max_versoes: null, max_tamanho_mb: 10, max_total_mb: null, formatos: ['audio/mpeg'] },
        ] });
        await page.getByLabel('Limitar prévias').uncheck();
        assert.equal((await page.evaluate(() => window.readEditor())).ok.length, 1);

        // Admin list: usage, origin and exhaustion; text only.
        await page.evaluate(cotas => window.renderList(cotas), [
            ...QUOTAS, { tipo: 'entrega', max_arquivos: null, max_versoes: null, max_tamanho_mb: null, max_total_mb: null,
                         formatos: ['<img src=x onerror=alert(1)>'], origem: 'contrato', arquivos_usados: 0, total_usado_bytes: 0 },
        ]);
        const items = page.locator('.file-quotas__list li');
        assert.match(await items.nth(0).textContent(), /Materiais do cliente: 1 de 3 arquivo\(s\) · espaço 0,6 de 1 MB \(contrato\)/);
        assert.match(await items.nth(1).textContent(), /Prévias: 1 de 1 arquivo\(s\) · até 2 versão\(ões\) por arquivo · até 10 MB por arquivo · formatos: MP3 \(exceção do Admin\)/);
        assert.equal(await items.nth(1).getAttribute('class'), 'is-exhausted');
        assert.equal(await page.locator('#root img').count(), 0);
        await page.evaluate(() => window.renderList([]));
        assert.match(await page.locator('#root').textContent(), /Sem cotas contratuais/);

        // Portals: the hint follows the selected type and whether a new file or a new version is sent.
        await page.evaluate(([production, files, cotas]) => window.renderPortals(production, files, cotas), [PRODUCTION, FILES, QUOTAS]);
        const producer = page.locator('#producer-detail-content form.producer-upload');
        const producerHint = producer.locator('[data-quota-hint]');
        assert.match(await producerHint.textContent(), /Cota do contrato: 1 de 1 arquivo\(s\).*Limite de arquivos atingido/);
        assert.equal(await producerHint.getAttribute('class'), 'file-quota-hint is-exhausted');
        await producer.getByLabel('Versão substituída').selectOption('11');
        assert.doesNotMatch(await producerHint.textContent(), /Limite de arquivos atingido/);
        await producer.getByLabel('Tipo de arquivo').selectOption('entrega');
        assert.equal(await producerHint.isVisible(), false);

        const client = page.locator('#client-detail-content form.producer-upload');
        const clientHint = client.locator('[data-quota-hint]');
        assert.equal(await clientHint.textContent(), 'Cota do contrato: 1 de 3 arquivo(s) · espaço 0,6 de 1 MB.');
        await client.getByLabel('Tipo de arquivo').selectOption('referencia');
        assert.equal(await clientHint.isVisible(), false);
        await client.getByLabel('Tipo de arquivo').selectOption('material');
        // New usage after an upload: the space is gone even for a new version.
        await page.evaluate(cotas => window.sync(cotas), [{ ...QUOTAS[0], total_usado_bytes: MB }]);
        assert.match(await clientHint.textContent(), /O espaço contratado acabou/);
        await page.evaluate(() => window.sync([]));
        assert.equal(await clientHint.isVisible(), false);

        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            await page.evaluate(cotas => window.renderEditor(cotas), QUOTAS);
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
            assert.equal(overflow, false, `quota editor overflows at ${width}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: file quotas editor, admin usage list and portal upload hints.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
