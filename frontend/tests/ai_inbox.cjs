const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const id = '2af0260f-8486-4a0a-9a43-9e1dd1b4f19e';
const inboundId = '37fbd45c-76c2-4e19-948f-bb5e5392ebdf';
const now = '2026-09-24T12:00:00Z';
const malicious = '<img src=x onerror=window.inboxXss=true>';
let conversation = {
    id, channel: 'site', status: 'waiting_human', mode: 'human', assigned_user_id: null,
    assigned_username: null, cliente_id: null, cliente_nome: malicious, cliente_email: null,
    sender_reference: null, email_subject: null, handoff_reason: 'manual_request', version: 1,
    created_at: now, updated_at: now, closed_at: null, has_more_messages: false, next_before: null,
    briefing: { status: 'draft', interest: 'Mixagem', service_id: 1, service_name: 'Mixagem',
        contact_name: 'Cliente', contact_email: 'cliente@example.com', contact_phone: null,
        details: { project_type: null, style: 'trap', track_count: 24, requested_deadline: null,
            goal: null, references: [], notes: malicious }, missing_fields: ['contact_phone'],
        orcamento_id: null, created_at: now, updated_at: now, submitted_at: null },
    messages: [{ id: inboundId, direction: 'inbound', role: 'user', kind: 'message',
        content: malicious, created_at: now, received_at: now, delivery: 'sent' }],
};
let suggestionId = '9d182f84-f159-4438-8d07-09674fc995da';
const calls = [];
let metricsFailure = false;
const metricsResponse = { channels: [{ channel: 'site', conversations_started: 0,
    cohort_closed: 0, cohort_handoffs: 0, autonomous_replies: 0, human_replies: 0,
    copilot_generated: 0, copilot_used: 0, briefings_started: 0, budgets_created: 0,
    provider_calls: 0, total_tokens: null, usage_known_calls: 0, cost_unknown_calls: 0,
    costs: [{ amount: 1, currency: malicious, measured_calls: 1 }] }] };

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({ body: await fs.readFile(file),
            contentType: { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' }[path.extname(file)] || 'application/octet-stream' });
    } catch { return route.fulfill({ status: 404, body: '' }); }
}

function listPage(url) {
    const filtered = url.searchParams.get('channel') === 'email' || url.searchParams.get('search') === 'sem resultado' ? [] : [conversation];
    return { items: filtered.map(item => ({
        id: item.id, channel: item.channel, status: item.status, mode: item.mode,
        assigned_user_id: item.assigned_user_id, assigned_username: item.assigned_username,
        cliente_id: item.cliente_id, cliente_nome: item.cliente_nome, email_subject: item.email_subject,
        handoff_reason: item.handoff_reason, last_message_preview: malicious, last_message_at: now,
        created_at: now, updated_at: now,
    })), total: filtered.length, page: 1, page_size: 20, pages: filtered.length ? 1 : 0 };
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    const context = await browser.newContext({ viewport: { width: 1024, height: 800 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('dialog', dialog => dialog.accept());
    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 404 });
        calls.push(`${request.method()} ${url.pathname}`);
        if (url.pathname === '/auth/login') return route.fulfill({ json: {
            access_token: 'test-token', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true },
        } });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 }, recent_activity: [],
        } });
        if (url.pathname === '/admin/ai/conversations/metrics') return route.fulfill(metricsFailure
            ? { status: 503, json: { detail: 'private error' } } : { json: metricsResponse });
        if (url.pathname === '/admin/ai/conversations' && request.method() === 'GET') return route.fulfill({ json: listPage(url) });
        if (url.pathname === `/admin/ai/conversations/${id}` && request.method() === 'GET') return route.fulfill({ json: conversation });
        if (url.pathname === `/admin/ai/conversations/${id}/assign`) {
            conversation = { ...conversation, status: 'open', mode: 'human', assigned_user_id: 1, assigned_username: 'admin' };
            return route.fulfill({ json: { conversation } });
        }
        if (url.pathname === `/admin/ai/conversations/${id}/mode`) {
            conversation = { ...conversation, mode: request.postDataJSON().mode };
            return route.fulfill({ json: { conversation } });
        }
        if (url.pathname === `/admin/ai/conversations/${id}/suggestions` && request.method() === 'POST') {
            const suggestion = { id: suggestionId, direction: 'outbound', role: 'assistant', kind: 'suggestion',
                content: 'Texto da IA', created_at: now, received_at: null, delivery: 'draft' };
            conversation = { ...conversation, messages: [...conversation.messages.filter(message => message.kind !== 'suggestion'), suggestion] };
            return route.fulfill({ json: { suggestion: { id: suggestionId, conversation_id: id, target_message_id: inboundId,
                text: suggestion.content, created_at: now } } });
        }
        if (url.pathname === `/admin/ai/conversations/${id}/suggestions/${suggestionId}` && request.method() === 'DELETE') {
            conversation = { ...conversation, messages: conversation.messages.filter(message => message.kind !== 'suggestion') };
            return route.fulfill({ json: { conversation } });
        }
        if (url.pathname === `/admin/ai/conversations/${id}/messages` && request.method() === 'POST') {
            const payload = request.postDataJSON();
            assert.deepEqual(Object.keys(payload).sort(), ['idempotency_key', 'suggestion_id', 'text']);
            assert.equal(payload.text, 'Texto editado pelo atendente');
            conversation = { ...conversation, messages: [...conversation.messages.filter(message => message.kind !== 'suggestion'),
                { id: crypto.randomUUID(), direction: 'outbound', role: 'assistant', kind: 'message', content: payload.text,
                    created_at: now, received_at: null, delivery: 'sent' }] };
            return route.fulfill({ json: { message: conversation.messages.at(-1), delivery: 'sent' } });
        }
        if (url.pathname === `/admin/ai/conversations/${id}/close`) {
            conversation = { ...conversation, status: 'closed', closed_at: now };
            return route.fulfill({ json: { conversation } });
        }
        if (['/config', '/servicos', '/projetos/admin', '/orcamentos', '/producoes', '/clientes', '/usuarios'].includes(url.pathname)) {
            return route.fulfill({ json: url.pathname === '/config' ? {} : [] });
        }
        if (url.pathname === '/usuarios/produtores') return route.fulfill({ json: [] });
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });
    try {
        await page.goto('http://localhost:4173/admin.html');
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('test-password');
        await page.getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.locator('[data-admin-target="section-inbox"]').click();
        assert.equal(calls.filter(call => call.includes('/metrics')).length, 0);
        await page.locator('#inbox-metrics summary').click();
        await page.locator('#inbox-metrics-content dd').first().waitFor();
        assert.equal(await page.locator('#inbox-metrics-content dd').first().innerText(), '0');
        assert.equal(await page.locator('#inbox-metrics-content img').count(), 0);
        assert.ok((await page.locator('#inbox-metrics-content').innerText()).includes('Indisponível'));
        assert.equal(calls.filter(call => call.includes('/metrics')).length, 1);
        metricsFailure = true;
        await page.locator('#inbox-metrics-period').selectOption('30');
        await page.getByText('Não foi possível carregar as métricas.').waitFor();
        assert.equal(await page.getByText('private error', { exact: true }).count(), 0);
        metricsFailure = false;
        await page.locator('#inbox-metrics-refresh').click();
        await page.locator('#inbox-metrics-content dd').first().waitFor();
        await page.getByRole('button', { name: `Abrir conversa ${malicious}` }).click();
        assert.equal(await page.locator('#inbox-detail img, #inbox-list img').count(), 0);
        assert.equal(await page.evaluate(() => Boolean(window.inboxXss)), false);
        assert.ok((await page.locator('.inbox-briefing').innerText()).includes(malicious));
        assert.ok((await page.locator('.inbox-briefing').innerText()).includes('24'));
        await page.getByRole('button', { name: 'Assumir atendimento' }).click();
        await page.locator('#inbox-mode-select').selectOption('copilot');
        await page.getByRole('button', { name: 'Gerar sugestão' }).click();
        await page.getByRole('button', { name: 'Regenerar sugestão' }).waitFor();
        assert.equal(await page.locator('#inbox-reply-text').inputValue(), 'Texto da IA');
        await page.getByRole('button', { name: 'Ignorar sugestão' }).click();
        await page.waitForFunction(() => !document.querySelector('#inbox-detail .inbox-message--suggestion'));
        await page.getByRole('button', { name: 'Gerar sugestão' }).click();
        await page.getByRole('button', { name: 'Regenerar sugestão' }).waitFor();
        await page.locator('#inbox-reply-text').fill('Texto editado pelo atendente');
        await page.getByRole('button', { name: 'Enviar resposta' }).click();
        await page.getByText('Texto editado pelo atendente').waitFor();
        await page.getByRole('button', { name: 'Encerrar' }).click();
        await page.locator('#inbox-detail .admin-badge').filter({ hasText: 'Encerrada' }).waitFor();
        if (process.env.AI_METRICS_SCREENSHOTS) {
            await page.waitForFunction(() => document.querySelectorAll('.notification').length === 0);
        }
        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `overflow ${width}`);
            if (process.env.AI_METRICS_SCREENSHOTS && [320, 1440].includes(width)) {
                await page.locator('#inbox-metrics summary').evaluate(node => node.scrollIntoView({ block: 'start' }));
                await page.screenshot({ path: path.join(process.env.AI_METRICS_SCREENSHOTS, `mirai-ai-metrics-${width}.png`) });
            }
        }
        assert.ok(calls.includes(`POST /admin/ai/conversations/${id}/messages`));
        await page.getByRole('button', { name: 'Sair' }).click();
        assert.equal(await page.locator('#inbox-detail').innerText(), '');
        assert.equal(await page.locator('#inbox-list').innerText(), '');
        assert.equal(await page.locator('#inbox-metrics-content').innerText(), '');
        assert.equal(await page.locator('#inbox-metrics').evaluate(node => node.open), false);
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('test-password');
        await page.getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.locator('[data-admin-target="section-inbox"]').click();
        await page.locator('.inbox-conversation-item').waitFor();
        const beforeSearch = calls.filter(call => call === 'GET /admin/ai/conversations').length;
        await page.locator('#inbox-search').fill('sem resultado');
        await page.getByText('Nenhuma conversa encontrada.').waitFor();
        assert.equal(calls.filter(call => call === 'GET /admin/ai/conversations').length, beforeSearch + 1);
        assert.deepEqual(errors, []);
        console.log('PASS: Inbox navigation, actions, Copilot, XSS and responsive widths.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
