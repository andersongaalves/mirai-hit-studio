// Admin > Arquivos: filters (type, role, service, protection), grouping, folder tree,
// detailed list with thumbnails, details panel, download, protected files and the double
// confirmation (type EXCLUIR + reason) before a deletion.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const PIXEL = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==', 'base64');

function entry(ref, nome, extra) {
    return {
        ref, nome, mime_type: 'audio/mpeg', categoria: 'audio', tamanho_bytes: 1024, criado_em: '2026-10-30T12:00:00Z',
        contexto: { tipo: 'producao', id: 1, titulo: 'Faixa A' }, funcao: 'Prévia', servico: 'Cloudflare R2',
        miniatura: null, protegido: false, motivo_protecao: null, baixar: 'api', url: null, detalhes: {},
        pasta: ['Produções', '#1 Faixa A', 'Prévias'], ...extra,
    };
}

let files = [
    entry('arq:1', 'rough.mp3', { protegido: true, motivo_protecao: 'Tem uma versão mais nova: as versões anteriores formam o histórico.', criado_em: '2026-10-01T12:00:00Z' }),
    entry('arq:2', 'rough-v2.mp3', { tamanho_bytes: 5 * 1024 * 1024, detalhes: { versao: 2, sha256: 'ab'.repeat(32), lufs_integrado: -14.2 } }),
    entry('arq:3', 'briefing.pdf', { mime_type: 'application/pdf', categoria: 'pdf', funcao: 'Material do cliente', servico: 'Supabase Storage',
        pasta: ['Produções', '#1 Faixa A', 'Materiais'] }),
    entry('arq:4', 'foto.png', { mime_type: 'image/png', categoria: 'imagem', funcao: 'Referência', pasta: ['Produções', '#1 Faixa A', 'Referências'], tamanho_bytes: PIXEL.length }),
    entry('beat:7:capa', 'Noite · Capa', { mime_type: 'image/jpeg', categoria: 'imagem', funcao: 'Capa do beat', servico: 'Cloudinary',
        baixar: 'url', url: 'https://res.cloudinary.com/demo/image/upload/capa.png', miniatura: 'https://res.cloudinary.com/demo/image/upload/capa.png',
        protegido: true, motivo_protecao: 'Arquivo de um beat: exclua o beat inteiro (o produtor pode, pelo portal).',
        contexto: { tipo: 'beat', id: 7, titulo: 'Noite' }, pasta: ['Beats', '#7 Noite'], tamanho_bytes: null }),
    entry('audiotag:3', 'tag-mirai.mp3', { funcao: 'Tag de áudio', servico: 'Banco de dados', contexto: { tipo: 'tag', id: 3, titulo: 'tag-mirai.mp3' }, pasta: ['Tags de áudio'] }),
];

function listing() {
    const facet = field => {
        const counts = {};
        files.forEach(item => {
            counts[item[field]] ||= { valor: item[field], arquivos: 0, tamanho_bytes: 0 };
            counts[item[field]].arquivos += 1;
            counts[item[field]].tamanho_bytes += item.tamanho_bytes || 0;
        });
        return Object.values(counts).sort((a, b) => b.arquivos - a.arquivos);
    };
    const pastas = {};
    files.forEach(item => item.pasta.forEach((_, depth) => {
        const key = item.pasta.slice(0, depth + 1).join('/');
        pastas[key] ||= { caminho: key, nome: item.pasta[depth], nivel: depth + 1, arquivos: 0, tamanho_bytes: 0 };
        pastas[key].arquivos += 1;
    }));
    const totais = {};
    ['audio', 'pdf', 'imagem', 'compactado', 'outro'].forEach(name => {
        const these = files.filter(item => item.categoria === name);
        totais[name] = { arquivos: these.length, tamanho_bytes: these.reduce((t, i) => t + (i.tamanho_bytes || 0), 0) };
    });
    return {
        arquivos: files, pastas: Object.values(pastas).sort((a, b) => a.caminho.localeCompare(b.caminho)), totais,
        funcoes: facet('funcao'), servicos: facet('servico'),
        total: { arquivos: files.length, tamanho_bytes: files.reduce((t, i) => t + (i.tamanho_bytes || 0), 0) },
        compressao: { previas_entregues: 4, comprimidas: 3, pendentes: 1, bitrate: '96k' },
    };
}

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    const errors = [];
    const deletes = [];
    const downloads = [];
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.hostname === 'res.cloudinary.com') return route.fulfill({ body: PIXEL, contentType: 'image/png' });
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });
        const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'synthetic-admin', user: admin } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: admin });
        if (url.pathname === '/admin/arquivos' && request.method() === 'GET') return route.fulfill({ json: listing() });
        if (url.pathname === '/admin/arquivos/conteudo') {
            const ref = url.searchParams.get('ref');
            downloads.push(ref);
            if (ref === 'arq:4') return route.fulfill({ body: PIXEL, contentType: 'image/png' });
            return route.fulfill({ body: Buffer.from('ID3synthetic'), contentType: 'audio/mpeg',
                headers: { 'Content-Disposition': "attachment; filename*=UTF-8''rough-v2.mp3" } });
        }
        if (url.pathname === '/admin/arquivos' && request.method() === 'DELETE') {
            const ref = url.searchParams.get('ref');
            deletes.push([ref, request.postDataJSON()]);
            files = files.filter(item => item.ref !== ref);
            return route.fulfill({ status: 204 });
        }
        if (url.pathname === '/config') return route.fulfill({ json: {} });
        if (url.pathname === '/dashboard') return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        return route.fulfill({ json: [] });
    });

    try {
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));
        await openAdminSection(page, 'section-arquivos');
        const rows = page.locator('.files-row');
        await rows.first().waitFor();
        assert.equal(await rows.count(), 6);
        const content = page.locator('#arquivos-content');
        assert.match(await content.textContent(), /3 de 4 já comprimidas em MP3 96 kbps · 1 na fila/);
        assert.match(await content.textContent(), /2 arquivos protegidos/);
        // Newest first, with role, type, service in the detailed list.
        assert.match(await rows.first().textContent(), /rough-v2\.mp3.*Prévia.*Áudio.*Cloudflare R2.*5 MB/);
        assert.match(await rows.first().locator('.files-path').textContent(), /Produções \/ #1 Faixa A \/ Prévias/);

        // Thumbnails: public cover by URL, private image loaded through the API, icons otherwise.
        const cover = page.locator('.files-row[data-ref="beat:7:capa"] .files-thumb img');
        assert.equal(await cover.getAttribute('src'), 'https://res.cloudinary.com/demo/image/upload/capa.png');
        await page.locator('.files-row[data-ref="arq:4"] .files-thumb.is-loaded').waitFor();
        assert.ok(downloads.includes('arq:4'));
        assert.equal(await page.locator('.files-row[data-ref="arq:3"] .files-thumb img').count(), 0);
        assert.equal(await page.locator('.files-row[data-ref="arq:1"] .files-lock').count(), 1);

        // Filters on top: type, role, service, protection; search; folder tree.
        await page.locator('#arquivos-tipo').selectOption('pdf');
        assert.equal(await rows.count(), 1);
        assert.match(await page.locator('#arquivos-resultado').textContent(), /^1 arquivo/);
        await page.getByRole('button', { name: 'Limpar filtros' }).click();
        assert.equal(await rows.count(), 6);
        await page.locator('#arquivos-servico').selectOption('Cloudflare R2');
        assert.equal(await rows.count(), 3);
        await page.locator('#arquivos-funcao').selectOption('Prévia');
        assert.equal(await rows.count(), 2);
        await page.locator('#arquivos-protegido').selectOption('nao');
        assert.deepEqual(await rows.evaluateAll(items => items.map(item => item.dataset.ref)), ['arq:2']);
        await page.getByRole('button', { name: 'Limpar filtros' }).click();
        await page.locator('#arquivos-busca').fill('noite');
        await page.waitForFunction(() => document.querySelectorAll('.files-row').length === 1);
        assert.equal(await page.evaluate(() => document.activeElement.id), 'arquivos-busca');
        await page.getByRole('button', { name: 'Limpar filtros' }).click();
        await page.locator('.files-tree__item', { hasText: 'Beats' }).first().click();
        assert.deepEqual(await rows.evaluateAll(items => items.map(item => item.dataset.ref)), ['beat:7:capa']);
        await page.locator('.files-tree__item', { hasText: 'Todos os arquivos' }).click();
        assert.equal(await rows.count(), 6);

        // Grouping by service, then by role; the choice is remembered.
        await page.locator('#arquivos-agrupar').selectOption('servico');
        const groups = page.locator('.files-group');
        assert.equal(await groups.count(), 4);
        assert.match(await groups.first().textContent(), /Cloudflare R2 · 3 arquivos/);
        await page.locator('#arquivos-agrupar').selectOption('funcao');
        assert.match(await groups.first().textContent(), /Prévia · 2 arquivos/);
        assert.equal(JSON.parse(await page.evaluate(() => localStorage.getItem('mirai.admin.arquivos'))).agrupar, 'funcao');
        await page.locator('#arquivos-agrupar').selectOption('nenhum');
        await page.locator('#arquivos-ordem').selectOption('maiores');
        assert.equal(await rows.first().getAttribute('data-ref'), 'arq:2');

        // Details: service, role, type and the most relevant facts.
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, 'arquivos-lista.png') });
        await page.locator('.files-row[data-ref="arq:2"]').click();
        const panel = page.locator('#arquivos-detalhes');
        await panel.waitFor();
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, 'arquivos-detalhes.png') });
        const details = await panel.textContent();
        assert.match(details, /Serviço de armazenamentoCloudflare R2/);
        assert.match(details, /FunçãoPrévia/);
        assert.match(details, /TipoÁudio · audio\/mpeg/);
        assert.match(details, /Vinculado aProdução #1 · Faixa A/);
        assert.match(details, /Volume \(LUFS integrados\)-14,2 LUFS/);
        assert.match(details, /Livre para excluir/);
        assert.equal(await page.evaluate(() => document.activeElement.id), 'arquivos-detalhes-titulo');
        const [download] = await Promise.all([
            page.waitForEvent('download'),
            panel.getByRole('button', { name: 'Baixar' }).click(),
        ]);
        assert.equal(download.suggestedFilename(), 'rough-v2.mp3');
        assert.ok(downloads.includes('arq:2'));
        await page.keyboard.press('Escape');
        await panel.waitFor({ state: 'hidden' });
        assert.equal(await page.evaluate(() => document.activeElement.dataset.ref), 'arq:2');

        // Protected files cannot be deleted and say why.
        await page.locator('.files-row[data-ref="arq:1"]').press('Enter');
        assert.match(await panel.textContent(), /Protegido: Tem uma versão mais nova/);
        assert.equal(await panel.getByRole('button', { name: 'Excluir' }).isDisabled(), true);

        // Public files open their link instead of downloading through the API.
        await page.locator('.files-row[data-ref="beat:7:capa"]').click();
        assert.equal(await panel.getByRole('button', { name: 'Abrir link' }).count(), 1);
        assert.equal(await panel.locator('.files-preview img').getAttribute('src'), 'https://res.cloudinary.com/demo/image/upload/capa.png');

        // Double confirmation: explains, then needs the reason and the word EXCLUIR.
        await page.locator('.files-row[data-ref="arq:3"]').click();
        await panel.getByRole('button', { name: 'Excluir' }).click();
        const dialog = page.getByRole('alertdialog');
        await dialog.waitFor();
        assert.match(await dialog.textContent(), /Excluir "briefing\.pdf"\?/);
        assert.match(await dialog.textContent(), /Sai do Supabase Storage e não pode ser recuperado/);
        const confirm = dialog.getByRole('button', { name: 'Excluir arquivo' });
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, 'arquivos-confirmacao.png') });
        assert.equal(await confirm.isDisabled(), true);
        await dialog.getByLabel('Digite EXCLUIR para confirmar').fill('excluir');
        assert.equal(await confirm.isDisabled(), true, 'reason still missing');
        await dialog.locator('textarea').fill('Enviado por engano');
        assert.equal(await confirm.isDisabled(), false);
        await dialog.getByLabel('Digite EXCLUIR para confirmar').fill('EXCLUI');
        assert.equal(await confirm.isDisabled(), true);
        // Cancel keeps the file.
        await page.keyboard.press('Escape');
        await dialog.waitFor({ state: 'detached' });
        assert.equal(deletes.length, 0);
        assert.equal(await panel.isVisible(), true, 'Escape on the dialog does not close the details');
        await panel.getByRole('button', { name: 'Excluir' }).click();
        await dialog.locator('textarea').fill('Enviado por engano');
        await dialog.getByLabel('Digite EXCLUIR para confirmar').fill('Excluir');
        await dialog.getByRole('button', { name: 'Excluir arquivo' }).click();
        await page.waitForFunction(() => !document.querySelector('.files-row[data-ref="arq:3"]'));
        assert.deepEqual(deletes, [['arq:3', { motivo: 'Enviado por engano' }]]);
        assert.equal(await rows.count(), 5);
        await panel.waitFor({ state: 'hidden' });

        // Phone width: the list becomes cards, nothing overflows sideways.
        await page.setViewportSize({ width: 390, height: 844 });
        await rows.first().waitFor();
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        assert.ok(overflow <= 1, `horizontal overflow ${overflow}px`);
        assert.equal(await page.locator('.files-table thead').isVisible(), false);
        assert.equal(await rows.first().locator('.files-cell--role').evaluate(cell => getComputedStyle(cell, '::before').content), '"Função: "');
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, 'arquivos-mobile.png'), fullPage: true });

        assert.deepEqual(errors, []);
        console.log('arquivos_admin: ok');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
