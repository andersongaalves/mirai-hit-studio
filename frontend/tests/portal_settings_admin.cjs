// Roadmap 3.0, 5.01: admin editor for versioned portal settings.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { expectAccessPage, openAdminSection, signIn } = require('./support/access.cjs');

const root = path.resolve(__dirname, '..');
const DEFAULTS = {
    cliente: {
        aviso: { ativo: false, nivel: 'info', texto: '' },
        textos: { titulo_dashboard: 'Seus projetos', descricao_dashboard: 'Acompanhe o que está acontecendo e saiba quando precisa agir.', ajuda_arquivos: '' },
        indicadores: ['andamento', 'concluidos', 'avaliacao', 'pagamentos'],
        filtros: { situacao_padrao: 'todos', ordenacao_padrao: 'recente' },
        areas: { propostas: true },
    },
    produtor: {
        aviso: { ativo: false, nivel: 'info', texto: '' },
        textos: { descricao_dashboard: 'O que precisa da sua atenção hoje.', ajuda_financeiro: 'Valores e pagamentos registrados pela administração.' },
        indicadores: ['ativas', 'revisao', 'vencidos', 'a_receber', 'pago'],
        filtros: { status_padrao: 'todos', ordenacao_padrao: 'prazo' },
    },
};
const store = { cliente: [], produtor: [] };
const writes = [];
// 5.10: global policies (versioned).
const POLICY_DEFAULTS = { publicacao_previa: 'automatica', revisoes_excedentes: 'permitir', cliente_ve_etapas: true, cliente_ve_prazos_etapas: true, financeiro_cliente: 'completo', entrega_final: 'apos_quitacao', produtor_ve_contato_cliente: true };
let policyVersions = [];
const policyWrites = [];
let policyConflict = false;
function policyState() {
    const current = policyVersions.at(-1);
    return { versao: current?.versao || 0, politicas: current?.politicas || POLICY_DEFAULTS, padroes: POLICY_DEFAULTS,
        versoes: [...policyVersions].reverse().map(item => ({ versao: item.versao, autor_usuario_id: 1, restaurada_de_versao: item.restaurada ?? null, created_at: '2026-10-15T12:00:00+00:00' })) };
}
let forceConflict = false;

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

function current(portal) {
    const latest = store[portal].at(-1);
    return { portal, versao: latest?.versao || 0, config: latest?.config || DEFAULTS[portal], padrao: DEFAULTS[portal] };
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
        if (url.pathname === '/auth/login') {
            return route.fulfill({ json: { access_token: 'synthetic-admin', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
        }
        if (url.pathname === '/auth/me') return route.fulfill({ json: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } });
        if (url.pathname.startsWith('/politicas/globais')) {
            if (request.method() !== 'GET') {
                const body = request.postDataJSON();
                policyWrites.push({ path: url.pathname, body });
                if (policyConflict) {
                    policyConflict = false;
                    return route.fulfill({ status: 409, json: { detail: 'As politicas foram alteradas por outra pessoa. Recarregue antes de publicar.' } });
                }
                const restored = url.pathname.endsWith('/restaurar') ? policyVersions.find(item => item.versao === body.versao) : null;
                policyVersions.push({ versao: policyVersions.length + 1, politicas: restored ? restored.politicas : body.politicas, restaurada: restored?.versao });
            }
            return route.fulfill({ json: policyState() });
        }
        const settings = url.pathname.match(/^\/admin\/portais\/(cliente|produtor)\/configuracao(\/versoes(?:\/(\d+)\/restaurar)?)?$/);
        if (settings) {
            const [, portal, versionsPath, restoreVersion] = settings;
            if (request.method() === 'GET' && !versionsPath) return route.fulfill({ json: current(portal) });
            if (request.method() === 'GET') {
                return route.fulfill({ json: [...store[portal]].reverse().map(item => ({
                    versao: item.versao, autor_usuario_id: 1, restaurada_de_versao: item.restored || null,
                    created_at: '2026-10-14T10:00:00+00:00',
                })) });
            }
            const body = request.postDataJSON();
            writes.push({ method: request.method(), portal, body, restoreVersion });
            if (forceConflict || body.base_versao !== current(portal).versao) {
                forceConflict = false;
                return route.fulfill({ status: 409, json: { detail: 'A configuração foi alterada por outra pessoa. Recarregue antes de publicar.' } });
            }
            const config = restoreVersion ? store[portal].find(item => item.versao === Number(restoreVersion)).config : body.config;
            store[portal].push({ versao: current(portal).versao + 1, config, restored: restoreVersion ? Number(restoreVersion) : null });
            return route.fulfill({ json: { portal, versao: current(portal).versao, config } });
        }
        if (url.pathname === '/config') return route.fulfill({ json: {} });
        if (url.pathname === '/config/portfolio-segments') return route.fulfill({ json: { segments: [], revision: '0'.repeat(64) } });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 },
            recent_activity: [],
        } });
        if (['/servicos', '/projetos/admin', '/orcamentos', '/producoes', '/clientes', '/usuarios', '/usuarios/produtores', '/newsletter/subscribers', '/newsletter/campaigns'].includes(url.pathname)) {
            return route.fulfill({ json: [] });
        }
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await signIn(page, { next: '/admin.html', username: 'admin' });
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));

        await openAdminSection(page, 'section-custos');
        await page.getByRole('tab', { name: 'Portais' }).click();
        await page.getByText('Textos e experiência dos portais', { exact: true }).click();
        await page.getByText('Políticas contratuais', { exact: true }).click();
        await page.waitForFunction(() => document.getElementById('portal-settings-version').textContent.includes('Nenhuma versão'));
        const form = page.locator('#portal-settings-form');
        assert.equal(await form.locator('input[name="indicadores"]:checked').count(), 4);
        assert.equal(await form.locator('[name="textos.titulo_dashboard"]').inputValue(), 'Seus projetos');
        if (process.env.VISUAL_OUTPUT) {
            await page.locator('#admin-config-portals').screenshot({ path: path.join(process.env.VISUAL_OUTPUT, 'portal-settings-1280.png') });
        }

        await form.getByLabel('Exibir aviso no topo do portal').check();
        await form.locator('[name="aviso.nivel"]').selectOption('atencao');
        await form.locator('[name="aviso.texto"]').fill('Recesso de 20 a 27/12');
        await form.getByLabel('Projetos concluídos').uncheck();
        await form.locator('[name="filtros.situacao_padrao"]').selectOption('ativos');
        await form.getByLabel('Mostrar a área de propostas').uncheck();
        await page.getByRole('button', { name: 'Publicar nova versão' }).click();
        await page.waitForFunction(() => document.getElementById('portal-settings-version').textContent.includes('v1'));
        assert.deepEqual(writes[0], {
            method: 'PUT', portal: 'cliente', restoreVersion: undefined,
            body: {
                base_versao: 0,
                config: {
                    aviso: { ativo: true, nivel: 'atencao', texto: 'Recesso de 20 a 27/12' },
                    textos: DEFAULTS.cliente.textos,
                    indicadores: ['andamento', 'avaliacao', 'pagamentos'],
                    filtros: { situacao_padrao: 'ativos', ordenacao_padrao: 'recente' },
                    areas: { propostas: false },
                },
            },
        });
        assert.match(await page.locator('#portal-settings-versions').textContent(), /v1.*Em uso/);

        // No indicator selected is blocked before any request.
        for (const box of await form.locator('input[name="indicadores"]').all()) await box.uncheck();
        await page.getByRole('button', { name: 'Publicar nova versão' }).click();
        assert.equal(writes.length, 1);

        // A conflict reloads the published state instead of overwriting it.
        await page.getByRole('button', { name: 'Usar valores padrão' }).click();
        forceConflict = true;
        await page.getByRole('button', { name: 'Publicar nova versão' }).click();
        await page.waitForFunction(() => document.querySelector('#portal-settings-form [name="aviso.texto"]').value === 'Recesso de 20 a 27/12');
        assert.equal(store.cliente.length, 1);

        await page.getByRole('button', { name: 'Usar valores padrão' }).click();
        await page.getByRole('button', { name: 'Publicar nova versão' }).click();
        await page.waitForFunction(() => document.getElementById('portal-settings-version').textContent.includes('v2'));
        await page.locator('#portal-settings-versions li').filter({ hasText: 'v1' }).getByRole('button', { name: 'Restaurar' }).click();
        await page.waitForFunction(() => document.getElementById('portal-settings-version').textContent.includes('v3'));
        assert.deepEqual(writes.at(-1), { method: 'POST', portal: 'cliente', restoreVersion: '1', body: { base_versao: 2 } });
        assert.match(await page.locator('#portal-settings-versions').textContent(), /restaurada da v1/);

        await page.locator('#portal-settings-portal').selectOption('produtor');
        await page.waitForFunction(() => document.querySelector('#portal-settings-form [name="textos.ajuda_financeiro"]'));
        assert.equal(await form.locator('[name="areas.propostas"]').count(), 0);
        assert.equal(await form.locator('input[name="indicadores"]:checked').count(), 5);

        // 5.10: global policies; publishing sends the typed values and the base version.
        await page.waitForSelector('#policy-settings-form select');
        assert.match(await page.locator('#policy-settings-version').textContent(), /padrões do sistema/);
        await page.locator('#policy-settings-form').getByLabel('Cliente vê os prazos das etapas').selectOption('false');
        await page.getByRole('button', { name: 'Publicar políticas' }).click();
        await page.waitForFunction(() => document.getElementById('policy-settings-version').textContent.includes('v1'));
        assert.deepEqual(policyWrites.at(-1).body, { politicas: { ...POLICY_DEFAULTS, cliente_ve_prazos_etapas: false }, base_versao: 0 });
        policyConflict = true;
        await page.getByRole('button', { name: 'Publicar políticas' }).click();
        await page.waitForFunction(() => document.body.textContent.includes('As politicas foram alteradas por outra pessoa'));
        await page.locator('#policy-settings-form').getByLabel('Prévias do produtor').selectOption('aprovacao_admin');
        await page.getByRole('button', { name: 'Publicar políticas' }).click();
        await page.waitForFunction(() => document.getElementById('policy-settings-version').textContent.includes('v2'));
        await page.getByRole('button', { name: 'Restaurar políticas v1' }).click();
        await page.waitForFunction(() => document.getElementById('policy-settings-version').textContent.includes('v3'));
        assert.deepEqual(policyWrites.at(-1), { path: '/politicas/globais/restaurar', body: { versao: 1, base_versao: 2 } });
        assert.equal(await page.locator('#policy-settings-form').getByLabel('Prévias do produtor').inputValue(), 'automatica');
        await page.getByRole('button', { name: 'Usar padrões do sistema' }).click();
        assert.equal(await page.locator('#policy-settings-form').getByLabel('Cliente vê os prazos das etapas').inputValue(), 'true');

        for (const width of [390, 768, 1280]) {
            await page.setViewportSize({ width, height: 900 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, `overflow at ${width}`);
        }
        assert.deepEqual(errors, []);
        console.log('PASS: portal settings editor publishes typed versions, blocks empty indicators, handles conflicts and restores; global policies (5.10) publish, conflict and restore.');
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
