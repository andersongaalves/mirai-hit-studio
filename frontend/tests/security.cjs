// Intercept every request: synthetic responses only, including session races.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'msedge' });
    try {
        const context = await browser.newContext();
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await context.route('**/*', async route => {
            const url = new URL(route.request().url());
            if (url.origin === 'http://localhost:4173') {
                const file = path.resolve(root, '.' + url.pathname);
                assert.ok(file.startsWith(root + path.sep));
                try { return route.fulfill({ body: await fs.readFile(file), contentType: { '.js':'text/javascript', '.html':'text/html', '.css':'text/css' }[path.extname(file)] || 'application/octet-stream' }); }
                catch { return route.fulfill({ body: '' }); }
            }
            return route.fulfill({ json: [] });
        });
        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fazerLogout === 'function');
        const result = await page.evaluate(async () => {
            const security = await import('/js/utils/security.js');
            const renderer = await import('/js/modules/service_renderer.js');
            const builder = await import('/js/admin/builder/builder_dom.js');
            const preview = await import('/js/admin/builder/builder_preview.js');
            const { builderState } = await import('/js/admin/builder/builder_state.js');
            const portfolio = await import('/js/portfolio_ui.js');
            const attack = '<img src=x onerror="window.executed=true"><script>window.executed=true</script>';
            const quote = '\" autofocus onfocus=\"window.executed=true';
            window.executed = false;
            const host = document.createElement('div');
            host.id = 'security-test'; document.body.append(host);
            host.innerHTML = renderer.renderizarEstrutura({ intro:attack, sections:[{icon:attack,title:attack,items:[attack]}], benefits:[attack] });
            host.append(builder.createSectionCardElement({icon:quote,title:quote,open:true}));
            Object.assign(builderState, { intro:attack, sections:[{icon:attack,title:attack,items:[attack]}], benefits:[attack] });
            preview.renderPreview();
            for (const id of ['render-portfolio','filtros-portfolio']) { const div = document.createElement('div'); div.id=id; host.append(div); }
            portfolio.renderizarProjetos([{titulo:attack,artista:attack,descricao:attack,categoria:quote,link_audio:'javascript:alert(1)',link_capa:'data:text/html,x'}]);
            portfolio.renderizarFiltros([{categoria:quote}], () => {});
            const invalid = ['javascript:alert(1)', 'data:text/html,x', 'file:///etc/passwd', 'vbscript:msgbox(1)', 'https://user:pass@example.com', 'https://example.com/\n'];
            return {
                urls:invalid.every(url => security.safeURL(url) === ''),
                safe:security.safeURL('https://example.com/pay'),
                invalid:security.serviceStructure('[1]') === null,
                fallback:renderer.renderizarEstrutura('{bad').includes('indispon'),
                scripts:host.querySelectorAll('script,[onerror],[onfocus]').length,
                previewUnsafe:document.querySelectorAll('#builder-preview-render img, #builder-preview-render script').length,
                field:host.querySelector('.builder-title').value,
                quote, href:host.querySelector('.portfolio-card').getAttribute('href'),
                text:host.textContent.includes(attack)
            };
        });
        assert.equal(result.urls, true); assert.equal(result.safe, 'https://example.com/pay');
        assert.equal(result.invalid, true); assert.equal(result.fallback, true);
        assert.equal(result.scripts, 0); assert.equal(result.previewUnsafe, 0);
        assert.equal(result.field, result.quote); assert.equal(result.href, ''); assert.equal(result.text, true);
        assert.equal(await page.evaluate(() => window.executed), false);
        const session = await page.evaluate(async () => {
            const auth = await import('/js/admin/auth.js');
            const { orcamentosState } = await import('/js/admin/orcamentos/orcamentos_state.js');
            const { propostaState } = await import('/js/admin/propostas/proposta_state.js');
            const { clientesState } = await import('/js/admin/clientes/clientes_state.js');
            const { builderState } = await import('/js/admin/builder/builder_state.js');
            let logoutEvents = 0;
            document.addEventListener('admin:logout', () => logoutEvents++);
            localStorage.setItem('access_token', 'old');
            orcamentosState.lista = [{nome_cliente:'private'}];
            clientesState.lista = [{nome:'private'}];
            propostaState.proposta = {id:1};
            document.getElementById('lista-servicos').textContent = 'private';
            document.getElementById('proposta-title').textContent = 'private';
            let resolveHeader;
            window.fetch = () => new Promise(resolve => { resolveHeader=resolve; });
            const stale = auth.authFetch('/late').then(() => false, () => true);
            auth.logout();
            localStorage.setItem('access_token', 'new');
            resolveHeader(new Response('{}', {status:401}));
            const staleRejected = await stale;
            const newSessionPreserved = auth.getToken() === 'new';
            let resolveBody;
            window.fetch = async () => { const response = new Response('{}'); response.json = () => new Promise(resolve => { resolveBody=resolve; }); return response; };
            const response = await auth.authFetch('/body');
            const body = response.json().then(() => false, () => true);
            auth.logout(); resolveBody({private:'old'});
            const bodyRejected = await body;
            localStorage.setItem('access_token', 'invalid');
            const before = logoutEvents;
            window.fetch = async () => new Response('{}', {status:401});
            await Promise.allSettled([auth.authFetch('/a'), auth.authFetch('/b')]);
            let calls = 0;
            window.fetch = async () => { calls++; return new Response('{}'); };
            await auth.authFetch('/after').catch(() => {});
            return {staleRejected,newSessionPreserved,bodyRejected,logoutOnce:logoutEvents-before === 1,calls,
                cleared:orcamentosState.lista.length === 0 && clientesState.lista.length === 0 && propostaState.proposta === null && builderState.intro === '',
                dom:document.getElementById('lista-servicos').textContent === '' && document.getElementById('proposta-title').textContent === '',
                token:auth.getToken(), modal:document.getElementById('modal-proposta').classList.contains('hidden')};
        });
        for (const key of ['staleRejected','newSessionPreserved','bodyRejected','logoutOnce','cleared','dom','modal']) assert.equal(session[key], true, key);
        assert.equal(session.calls, 0); assert.equal(session.token, null); assert.deepEqual(errors, []);
        console.log('PASS: XSS, unsafe URLs, malformed services, builder/portfolio escaping, logout cleanup, stale headers/body, concurrent 401 and no retry loop.');
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
