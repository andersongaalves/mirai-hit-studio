// Admin > Mirai Hit Labs: create a plugin, installers by link, licenses and revocation.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const types = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.svg': 'image/svg+xml' };
const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };

function view(plugin) {
    return {
        slug: plugin.slug, nome: plugin.nome, tagline: plugin.tagline, descricao: plugin.descricao, categoria: plugin.categoria,
        versao: plugin.versao, formatos: plugin.formatos, recursos: plugin.recursos, requisitos: plugin.requisitos,
        preco: plugin.preco, preco_vigente: plugin.preco_promocional || plugin.preco, em_promocao: Boolean(plugin.preco_promocional),
        gratuito: Number(plugin.preco) === 0, capa_url: plugin.capa_url || null, video_url: plugin.video_url, destaque: plugin.destaque,
        sistemas: [], publicado_em: null, id: plugin.id, status: plugin.status, ordem: plugin.ordem,
        preco_promocional: plugin.preco_promocional, instaladores: plugin.instaladores || [],
        licencas: { ativas: plugin.ativas || 0, reservadas: 0, revogadas: 0 },
    };
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
        const page = await context.newPage();
        const errors = [];
        const writes = [];
        let plugins = [];
        let licenses = [{ id: 7, cliente_id: 1, cliente: 'Cliente A', email: 'a@example.test', origem: 'compra', status: 'ativa',
            chave: 'MHL-AAAA-BBBB-CCCC-DDDD', valor: '149.90', proposta_id: 3, ativada_em: null, encerrada_em: null, motivo: null }];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const request = route.request();
            const url = new URL(request.url());
            if (url.origin === 'http://localhost:4173') {
                const file = url.pathname === '/acesso' ? '/acesso.html' : url.pathname;
                try { return route.fulfill({ body: await fs.readFile(path.join(root, file)), contentType: types[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ status: 404, body: '' }); }
            }
            if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 204, body: '' });
            const p = url.pathname;
            const method = request.method();
            if (p === '/auth/login') return route.fulfill({ json: { access_token: 'admin-token', user: admin } });
            if (p === '/auth/me') return route.fulfill({ json: admin });
            if (p === '/admin/labs/plugins' && method === 'GET') return route.fulfill({ json: plugins.map(view) });
            if (p === '/admin/labs/plugins' && method === 'POST') {
                const body = request.postDataJSON();
                writes.push(['create', body]);
                const created = { ...body, id: 11, instaladores: [] };
                plugins = [created];
                return route.fulfill({ status: 201, json: view(created) });
            }
            const link = p.match(/^\/admin\/labs\/plugins\/11\/instaladores\/(windows|macos)\/link$/);
            if (link && method === 'PUT') {
                const body = request.postDataJSON();
                writes.push(['link', link[1], body]);
                plugins[0].instaladores = [{ sistema: link[1], nome: 'macOS', versao: body.versao, tamanho_bytes: null, tipo: 'link', nome_arquivo: null, link: body.link }];
                return route.fulfill({ json: view(plugins[0]) });
            }
            if (p === '/admin/labs/plugins/11/licencas') return route.fulfill({ json: licenses });
            if (p === '/admin/labs/licencas/7/revogar') {
                writes.push(['revoke', request.postDataJSON()]);
                licenses = [{ ...licenses[0], status: 'revogada', motivo: 'chargeback' }];
                return route.fulfill({ json: { id: 7, status: 'revogada' } });
            }
            if (p === '/clientes') return route.fulfill({ json: [{ id: 2, nome: 'Cliente B', email: 'b@example.test' }] });
            if (p === '/admin/labs/plugins/11/cortesias') {
                writes.push(['gift', request.postDataJSON()]);
                return route.fulfill({ status: 201, json: { id: 8, status: 'ativa' } });
            }
            if (p.endsWith('/notificacoes')) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
            if (p === '/dashboard') return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
            return route.fulfill({ json: [] });
        });
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await openAdminSection(page, 'section-labs');
        await page.getByText('Nenhum plugin ainda.').waitFor();

        // New plugin: the address follows the name until edited.
        await page.locator('#labs-admin-new').click();
        const panel = page.locator('#labs-admin-panel');
        await panel.getByRole('heading', { name: 'Novo plugin' }).waitFor();
        await panel.locator('input[name="nome"]').fill('Mirai Saturator Pró');
        assert.equal(await panel.locator('input[name="slug"]').inputValue(), 'mirai-saturator-pro');
        assert.match(await panel.locator('.labs-admin__url').textContent(), /labs\.miraihitstudio\.com\.br\/plugins\/mirai-saturator-pro/);
        await panel.locator('input[name="tagline"]').fill('Saturação analógica');
        await panel.locator('input[name="preco"]').fill('149.90');
        await panel.locator('label.labs-admin__check', { hasText: 'VST3' }).click();
        await panel.locator('label.labs-admin__check', { hasText: 'AU' }).first().click();
        await panel.locator('textarea[name="recursos"]').fill('Três modos\n\nOversampling 4x');
        await panel.getByRole('button', { name: 'Criar plugin' }).click();
        await panel.getByRole('heading', { name: 'Editar Mirai Saturator Pró' }).waitFor();
        const created = writes.find(item => item[0] === 'create')[1];
        assert.equal(created.slug, 'mirai-saturator-pro');
        assert.deepEqual(created.formatos, ['VST3', 'AU']);
        assert.deepEqual(created.recursos, ['Três modos', 'Oversampling 4x']);
        assert.equal(created.preco, '149.90');
        assert.equal(created.status, 'rascunho');
        assert.equal(await page.locator('.labs-admin__card').count(), 1);
        assert.match(await page.locator('.labs-admin__card').textContent(), /Rascunho[\s\S]*R\$\s?149,90[\s\S]*Windows pendente[\s\S]*macOS pendente/);

        // Installer by link for macOS.
        const mac = panel.locator('.labs-admin__installer', { hasText: 'macOS' });
        await mac.locator('input[name="versao"]').fill('1.0.2');
        await mac.locator('input[name="link"]').fill('https://drive.example.test/mac.zip');
        await mac.getByRole('button', { name: 'Salvar' }).click();
        await panel.locator('.labs-admin__installer', { hasText: 'macOS' }).getByText(/Link · v1\.0\.2/).waitFor();
        assert.deepEqual(writes.find(item => item[0] === 'link').slice(1), ['macos', { link: 'https://drive.example.test/mac.zip', versao: '1.0.2' }]);
        // A non-zip file is refused before upload.
        const win = panel.locator('.labs-admin__installer', { hasText: 'Windows' });
        await win.locator('input[name="arquivo"]').setInputFiles({ name: 'setup.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('MZ') });
        await win.getByRole('button', { name: 'Salvar' }).click();
        await win.getByText('Envie o instalador em .zip.').waitFor();

        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            const wide = await page.evaluate(() => [...document.querySelectorAll('#section-labs *')].filter(node => node.getBoundingClientRect().right > document.documentElement.clientWidth + 1).slice(0, 5).map(node => `${node.tagName}.${node.className} ${Math.round(node.getBoundingClientRect().right)}`));
            assert.deepEqual(wide, [], `overflow at ${width}`);
        }
        if (process.env.SHOT_DIR) await page.screenshot({ path: `${process.env.SHOT_DIR}/labs-admin-editor.png`, fullPage: true });

        // Licenses: list, revoke with a reason, courtesy for a client found by search.
        await page.locator('.labs-admin__card').getByRole('button', { name: 'Licenças' }).click();
        await panel.getByRole('heading', { name: 'Licenças · Mirai Saturator Pró' }).waitFor();
        assert.match(await panel.locator('table').textContent(), /Cliente A[\s\S]*Compra[\s\S]*Ativa[\s\S]*MHL-AAAA-BBBB-CCCC-DDDD/);
        await panel.getByRole('button', { name: 'Revogar' }).click();
        const dialog = page.getByRole('alertdialog');
        await dialog.locator('textarea[name="motivo"], input[name="motivo"]').fill('chargeback');
        await dialog.getByRole('button', { name: 'Revogar' }).click();
        await panel.getByText('Revogada').waitFor();
        assert.deepEqual(writes.find(item => item[0] === 'revoke')[1], { motivo: 'chargeback' });
        assert.equal(await panel.locator('table').textContent().then(text => text.includes('MHL-AAAA')), false);
        await panel.locator('input[name="busca"]').fill('Cliente');
        await panel.locator('select[name="cliente_id"] option[value="2"]').waitFor({ state: 'attached' });
        await panel.getByRole('button', { name: 'Dar licença' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Licença de cortesia criada.'));
        assert.deepEqual(writes.find(item => item[0] === 'gift')[1], { cliente_id: 2 });
        assert.deepEqual(errors, []);
        console.log('PASS: Labs admin creates plugins, sets installers, lists and revokes licenses and gives courtesy licenses.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
