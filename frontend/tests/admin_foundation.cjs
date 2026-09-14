const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');

const root = path.resolve(__dirname, '..');

async function staticResponse(route) {
    const url = new URL(route.request().url());
    const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    assert.ok(file.startsWith(root + path.sep));
    try {
        return route.fulfill({
            body: await fs.readFile(file),
            contentType: {
                '.js': 'text/javascript',
                '.css': 'text/css',
                '.html': 'text/html',
            }[path.extname(file)] || 'application/octet-stream',
        });
    } catch {
        return route.fulfill({ status: 404, body: '' });
    }
}

(async () => {
    const browser = await chromium.launch({
        headless: true,
        channel: process.env.BROWSER_CHANNEL || 'msedge',
    });
    const context = await browser.newContext({ viewport: { width: 1024, height: 768 } });
    const page = await context.newPage();
    const errors = [];

    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
        if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:')) {
            errors.push(message.text());
        }
    });

    await context.route('**/*', async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === 'http://localhost:4173') return staticResponse(route);
        if (url.origin !== 'http://localhost:8000') return route.fulfill({ status: 200, body: '' });

        if (url.pathname === '/auth/login') {
            return route.fulfill({ json: { access_token: 'synthetic-admin-session', user: { id: 1, username: 'admin', role: 'admin', is_admin: true, ativo: true } } });
        }
        if (url.pathname === '/config') return route.fulfill({ json: {} });
        if (url.pathname === '/servicos') return route.fulfill({ json: [] });
        if (url.pathname === '/projetos') return route.fulfill({ json: [] });
        if (url.pathname === '/orcamentos') return route.fulfill({ json: [] });
        if (url.pathname === '/producoes') return route.fulfill({ json: [] });
        if (url.pathname === '/clientes') return route.fulfill({ json: [] });
        if (url.pathname === '/dashboard') return route.fulfill({ json: {
            metrics: { clientes_ativos: 0, orcamentos_abertos: 0, propostas_aguardando_decisao: 0, producoes_ativas: 0, producoes_atrasadas: 0 },
            pipeline: { orcamentos_abertos: 0, propostas_enviadas: 0, propostas_aprovadas: 0, producoes_ativas: 0 },
            attention: { producoes_atrasadas: 0, propostas_aguardando_decisao: 0 },
            recent_activity: [],
        } });
        if (url.pathname === '/usuarios') return route.fulfill({ json: [] });
        if (url.pathname === '/usuarios/produtores') return route.fulfill({ json: [] });
        if (url.pathname === '/newsletter/subscribers') return route.fulfill({ json: [] });
        if (url.pathname === '/newsletter/campaigns') return route.fulfill({ json: [] });
        return route.fulfill({ status: 404, json: { detail: 'Not found' } });
    });

    try {
        await page.goto('http://localhost:4173/admin.html');
        await page.waitForFunction(() => typeof window.fazerLogin === 'function');
        await page.locator('#username').fill('admin');
        await page.locator('#password').fill('synthetic-password');
        await page.locator('#login-panel').getByRole('button', { name: 'ENTRAR NO SISTEMA' }).click();
        await page.waitForFunction(() => !document.getElementById('admin-area').classList.contains('hidden'));

        const keyboardFocus = await page.evaluate(() => {
            const control = document.querySelector('.admin-nav__item[data-admin-target="dashboard-menu"]');
            control.focus();
            return {
            navigationControl: document.activeElement === control,
            };
        });
        assert.equal(keyboardFocus.navigationControl, true);

        const productionNav = page.locator('.admin-nav__item[data-admin-target="section-producoes"]');
        await productionNav.focus();
        await page.keyboard.press('Enter');
        assert.equal(await page.locator('#section-producoes').isVisible(), true);
        assert.equal(
            await page.locator('.admin-nav__item[aria-current="page"]').getAttribute('data-admin-target'),
            'section-producoes',
        );
        assert.equal(await page.locator('#section-producoes h1').evaluate(el => el === document.activeElement), true);

        await page.evaluate(() => window.mostrarDashboard());
        const serviceNav = page.locator('.admin-nav__item[data-admin-target="section-servicos"]');
        await serviceNav.focus();
        await page.keyboard.press('Space');
        assert.equal(await page.locator('#section-servicos').isVisible(), true);
        assert.equal(
            await page.locator('.admin-nav__item[aria-current="page"]').getAttribute('data-admin-target'),
            'section-servicos',
        );

        const duplicateListeners = await page.evaluate(async () => {
            const shell = await import('/js/admin/admin_shell.js');
            window.__navigationCalls = 0;
            const onNavigate = () => { window.__navigationCalls += 1; };
            shell.initializeAdminShell({ onNavigate });
            shell.initializeAdminShell({ onNavigate });
            document.querySelector('[data-admin-target="dashboard-menu"]').click();
            return window.__navigationCalls;
        });
        assert.equal(duplicateListeners, 1);

        await page.setViewportSize({ width: 375, height: 760 });
        const menuToggle = page.locator('#admin-nav-toggle');
        await menuToggle.click();
        assert.equal(await menuToggle.getAttribute('aria-expanded'), 'true');
        assert.equal(await page.locator('#admin-navigation').evaluate(el => el.classList.contains('is-open')), true);
        assert.equal(await page.locator('.admin-nav__item').first().evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Escape');
        assert.equal(await menuToggle.getAttribute('aria-expanded'), 'false');
        assert.equal(await menuToggle.evaluate(el => el === document.activeElement), true);

        const modalResult = await page.evaluate(async () => {
            const projects = await import('/js/admin/projetos.js');
            const opener = document.createElement('button');
            opener.id = 'synthetic-modal-opener';
            opener.textContent = 'Abrir projeto';
            opener.addEventListener('click', projects.novoProjeto);
            document.body.appendChild(opener);
            opener.focus();
            opener.click();
            await new Promise(resolve => queueMicrotask(resolve));
            return {
                role: document.getElementById('modal-projeto').getAttribute('role'),
                modal: document.getElementById('modal-projeto').getAttribute('aria-modal'),
                focused: document.activeElement?.id,
            };
        });
        assert.deepEqual(modalResult, { role: 'dialog', modal: 'true', focused: 'proj_titulo' });

        const projectModal = page.locator('#modal-projeto');
        const modalButtons = projectModal.getByRole('button');
        await modalButtons.last().focus();
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('#proj_titulo').evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Shift+Tab');
        assert.equal(await modalButtons.last().evaluate(el => el === document.activeElement), true);
        await page.keyboard.press('Escape');
        assert.equal(await projectModal.isVisible(), false);
        assert.equal(await page.locator('#synthetic-modal-opener').evaluate(el => el === document.activeElement), true);

        await page.locator('#synthetic-modal-opener').click();
        await projectModal.getByRole('button', { name: 'Cancelar' }).click();
        assert.equal(await projectModal.isVisible(), false);
        assert.equal(await page.locator('#synthetic-modal-opener').evaluate(el => el === document.activeElement), true);

        const stateResult = await page.evaluate(async () => {
            const { renderAdminState } = await import('/js/admin/ui.js');
            const host = document.createElement('div');
            document.body.appendChild(host);
            renderAdminState(host, 'error', '<img src=x onerror=alert(1)>');
            return {
                text: host.textContent,
                images: host.querySelectorAll('img').length,
                role: host.firstElementChild?.getAttribute('role'),
            };
        });
        assert.deepEqual(stateResult, {
            text: '<img src=x onerror=alert(1)>',
            images: 0,
            role: 'alert',
        });

        await page.evaluate(() => {
            const wrap = document.createElement('div');
            wrap.className = 'admin-table-wrap';
            const table = document.createElement('table');
            table.className = 'admin-table';
            table.innerHTML = '<tbody><tr><td>Conteúdo de teste</td></tr></tbody>';
            wrap.appendChild(table);
            document.getElementById('section-producoes').appendChild(wrap);

            const card = document.createElement('article');
            card.className = 'admin-entity-card';
            card.innerHTML = '<strong class="admin-entity-card__title">Entidade</strong><div class="admin-entity-card__actions"><button>Detalhes</button></div>';
            document.getElementById('section-producoes').appendChild(card);
        });

        for (const width of [320, 375, 390, 414, 768, 1024, 1440]) {
            await page.setViewportSize({ width, height: 800 });
            const layout = await page.evaluate(() => ({
                viewport: document.documentElement.clientWidth,
                scroll: document.documentElement.scrollWidth,
                shell: getComputedStyle(document.getElementById('admin-area')).display,
                sidebar: getComputedStyle(document.getElementById('admin-navigation')).display,
                mobileHeader: getComputedStyle(document.querySelector('.admin-mobile-header')).display,
                cardDirection: getComputedStyle(document.querySelector('.admin-entity-card')).flexDirection,
                tableCollapse: getComputedStyle(document.querySelector('.admin-table')).borderCollapse,
            }));
            assert.ok(layout.scroll <= layout.viewport + 1, `horizontal overflow at ${width}px`);
            assert.equal(layout.tableCollapse, 'collapse');
            if (width <= 900) {
                assert.equal(layout.shell, 'block');
                assert.equal(layout.sidebar, 'none');
                assert.equal(layout.mobileHeader, 'flex');
            } else {
                assert.equal(layout.shell, 'grid');
                assert.equal(layout.sidebar, 'flex');
                assert.equal(layout.mobileHeader, 'none');
            }
            assert.equal(layout.cardDirection, width <= 520 ? 'column' : 'row');
        }

        assert.equal(errors.length, 0, errors.join('\n'));
        console.log('PASS: admin shell keyboard navigation, active module, mobile menu, modal focus, safe states and responsive foundations.');
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
