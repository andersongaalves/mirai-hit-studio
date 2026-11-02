// Avisos e pop-ups: the Admin writes pop-ups with a live preview, pauses, edits and
// deletes them, publishes the notice at the top of each portal; the portals show the
// pop-ups centered with an X and remember who closed them.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const DEFAULT_CONFIG = {
    cliente: { aviso: { ativo: false, nivel: 'info', texto: '' }, textos: { titulo_dashboard: 'Seus projetos' }, indicadores: ['andamento'], filtros: {}, areas: { propostas: true } },
    produtor: { aviso: { ativo: false, nivel: 'info', texto: '' }, textos: { descricao_dashboard: 'Hoje' }, indicadores: ['ativas'], filtros: {} },
};
const configs = { cliente: { versao: 3, config: DEFAULT_CONFIG.cliente }, produtor: { versao: 0, config: DEFAULT_CONFIG.produtor } };
let popups = [];
const writes = [];
const closes = [];
const portalPopups = [
    { id: 41, titulo: 'Feriado <b>prolongado</b>', mensagem: 'Linha 1\nLinha 2', tema: 'amarelo', tamanho: 'pequeno', botao_rotulo: 'Ver projetos', botao_url: '/cliente/projetos', frequencia: 'uma_vez' },
    { id: 42, titulo: 'Novidade', mensagem: 'Agora com antes e depois.', tema: 'roxo', tamanho: 'medio', botao_rotulo: null, botao_url: null, frequencia: 'cada_sessao' },
];

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
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });
        const admin = { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true };
        if (url.pathname === '/auth/login') return route.fulfill({ json: { access_token: 'synthetic-admin', user: admin } });
        if (url.pathname === '/auth/me') return route.fulfill({ json: admin });
        if (url.pathname === '/admin/popups' && request.method() === 'GET') return route.fulfill({ json: popups });
        if (url.pathname === '/admin/popups' && request.method() === 'POST') {
            const body = request.postDataJSON();
            writes.push(['POST', body]);
            const item = { ...body, id: popups.length + 10, fechamentos: 0, created_at: '2026-11-02T03:00:00Z', updated_at: '2026-11-02T03:00:00Z' };
            popups = [item, ...popups];
            return route.fulfill({ status: 201, json: item });
        }
        const one = url.pathname.match(/^\/admin\/popups\/(\d+)$/);
        if (one) {
            const id = Number(one[1]);
            if (request.method() === 'DELETE') {
                writes.push(['DELETE', id]);
                popups = popups.filter(item => item.id !== id);
                return route.fulfill({ status: 204 });
            }
            const body = request.postDataJSON();
            writes.push(['PUT', id, body]);
            popups = popups.map(item => (item.id === id ? { ...item, ...body } : item));
            return route.fulfill({ json: popups.find(item => item.id === id) });
        }
        const settings = url.pathname.match(/^\/admin\/portais\/(cliente|produtor)\/configuracao$/);
        if (settings) {
            const portal = settings[1];
            if (request.method() === 'PUT') {
                const body = request.postDataJSON();
                writes.push(['CONFIG', portal, body]);
                configs[portal] = { versao: configs[portal].versao + 1, config: body.config };
            }
            return route.fulfill({ json: { portal, versao: configs[portal].versao, config: configs[portal].config, padrao: DEFAULT_CONFIG[portal] } });
        }
        if (url.pathname === '/portal/popups') return route.fulfill({ json: portalPopups });
        const close = url.pathname.match(/^\/portal\/popups\/(\d+)\/fechar$/);
        if (close) {
            closes.push(Number(close[1]));
            return route.fulfill({ status: 204 });
        }
        if (url.pathname === '/config') return route.fulfill({ json: {} });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: {}, pipeline: {}, attention: {}, recent_activity: [],
        } });
        return route.fulfill({ json: [] });
    });

    try {
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));
        await openAdminSection(page, 'section-avisos');
        const form = page.getByRole('form', { name: 'Novo pop-up' });
        await form.waitFor();
        assert.match(await page.locator('#avisos-popups-panel').textContent(), /Nenhum pop-up enviado ainda/);

        // The preview follows every field.
        const preview = page.locator('.avisos-preview__stage .portal-popup');
        await form.getByLabel('Título').fill('Manutenção <img src=x>');
        await form.getByLabel('Mensagem').fill('O portal fica fora do ar\nno domingo às 22h.');
        await form.getByText('Produtores', { exact: true }).click();
        await form.getByLabel('Roxo').check();
        await form.getByText('Médio', { exact: true }).click();
        await form.getByLabel('Botão (opcional)').fill('Saiba mais');
        assert.equal(await page.locator('.avisos-preview__stage').locator('img').count(), 0);
        assert.equal(await preview.locator('.portal-popup__title').textContent(), 'Manutenção <img src=x>');
        assert.match(await preview.getAttribute('class'), /portal-popup--roxo.*portal-popup--medio/);
        assert.equal(await preview.locator('.portal-popup__close').getAttribute('aria-label'), 'Fechar');
        assert.match(await page.locator('.avisos-preview__audience').textContent(), /Produtores/);
        // A button needs both its text and its link.
        await form.getByRole('button', { name: 'Enviar pop-up' }).click();
        assert.match(await form.textContent(), /texto e o link do botão/);
        assert.equal(writes.length, 0);
        await form.getByLabel('Link do botão').fill('/produtor/producoes');
        assert.equal(await preview.locator('.portal-popup__action').textContent(), 'Saiba mais');
        await form.getByRole('button', { name: 'Enviar pop-up' }).click();
        const card = page.locator('.avisos-card').filter({ hasText: 'Manutenção' });
        await card.waitFor();
        assert.deepEqual(writes[0], ['POST', {
            titulo: 'Manutenção <img src=x>', mensagem: 'O portal fica fora do ar\nno domingo às 22h.', publico: 'produtor',
            tema: 'roxo', tamanho: 'medio', botao_rotulo: 'Saiba mais', botao_url: '/produtor/producoes',
            frequencia: 'uma_vez', inicio: null, fim: null, ativo: true,
        }]);
        assert.match(await card.textContent(), /No ar/);
        assert.match(await card.textContent(), /Produtores/);

        // Pause, edit and delete.
        await card.getByRole('button', { name: /^Pausar/ }).click();
        await page.locator('.avisos-card').filter({ hasText: 'Pausado' }).waitFor();
        assert.equal(writes.at(-1)[2].ativo, false);
        await page.getByRole('button', { name: /^Editar pop-up/ }).click();
        const editForm = page.getByRole('form', { name: 'Editar pop-up' });
        assert.equal(await editForm.getByLabel('Título').inputValue(), 'Manutenção <img src=x>');
        await editForm.getByLabel('Título').fill('Manutenção programada');
        await editForm.getByLabel('Ativo (desmarque para salvar sem publicar)').check();
        await editForm.getByRole('button', { name: 'Salvar alterações' }).click();
        await page.locator('.avisos-card').filter({ hasText: 'Manutenção programada' }).filter({ hasText: 'No ar' }).waitFor();
        assert.equal(writes.at(-1)[0], 'PUT');
        page.once('dialog', dialog => dialog.accept());
        await page.getByRole('button', { name: 'Excluir pop-up Manutenção programada' }).click();
        await page.getByText('Nenhum pop-up enviado ainda.').waitFor();
        assert.equal(writes.at(-1)[0], 'DELETE');

        // The notice at the top of each portal is published from here (a new settings version).
        await page.getByRole('tab', { name: 'Aviso no topo' }).click();
        const producerNotice = page.getByRole('form', { name: 'Aviso no topo: Portal do produtor' });
        await producerNotice.waitFor();
        await producerNotice.getByLabel('Exibir aviso no topo do portal').check();
        await producerNotice.getByLabel('Tipo').selectOption('atencao');
        await producerNotice.getByLabel('Texto (até 280 caracteres)').fill('Recesso de 20 a 27/12');
        assert.equal(await producerNotice.locator('.avisos-topo__preview').textContent(), 'Recesso de 20 a 27/12');
        await producerNotice.getByRole('button', { name: 'Publicar aviso' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('Aviso publicado'));
        const config = writes.find(item => item[0] === 'CONFIG');
        assert.deepEqual(config, ['CONFIG', 'produtor', { base_versao: 0, config: { ...DEFAULT_CONFIG.produtor, aviso: { ativo: true, nivel: 'atencao', texto: 'Recesso de 20 a 27/12' } } }]);

        for (const width of [390, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            await page.getByRole('tab', { name: 'Pop-ups' }).click();
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `overflow at ${width}`);
        }

        // The portals: one pop-up at a time, centered, with an X; text stays text.
        await page.evaluate(async () => {
            sessionStorage.clear();
            const module = await import('/js/modules/portal_popup.js');
            window.popupsDone = module.startPortalPopups().then(() => { window.popupsFinished = true; });
        });
        const dialog = page.getByRole('dialog', { name: 'Feriado <b>prolongado</b>' });
        await dialog.waitFor();
        assert.equal(await dialog.locator('b').count(), 0);
        assert.equal(await dialog.locator('.portal-popup__message').evaluate(node => getComputedStyle(node).whiteSpace), 'pre-line');
        assert.equal(await dialog.getByRole('link', { name: 'Ver projetos' }).getAttribute('href'), '/cliente/projetos');
        const box = await dialog.boundingBox();
        assert.ok(Math.abs(box.x + box.width / 2 - 640) < 2, 'centered');
        assert.equal(await page.locator('.portal-popup-overlay').count(), 1, 'one at a time');
        await dialog.getByRole('button', { name: 'Fechar' }).click();
        const second = page.getByRole('dialog', { name: 'Novidade' });
        await second.waitFor();
        assert.deepEqual(closes, [41]);
        await page.keyboard.press('Escape');
        await page.waitForFunction(() => window.popupsFinished === true);
        assert.deepEqual(closes, [41], 'a per-session pop-up is remembered by the browser, not the server');
        assert.equal(await page.evaluate(() => sessionStorage.getItem('mirai.popup.sessao.42')), '1');

        assert.deepEqual(errors, []);
        console.log('PASS: avisos e pop-ups — editor with live preview, validation, pause/edit/delete, top notice per portal, and portal pop-ups centered with X, one at a time, remembered.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
