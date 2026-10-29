// AUD6-S02-003: panels have no login form of their own. Without a session they
// send the visitor to /acesso, which returns to the requested panel after login.
// Suites sign in the same way users do.

async function signIn(page, { origin = 'http://localhost:4173', next, username, password = 'synthetic-password' }) {
    await page.goto(`${origin}/acesso.html?next=${encodeURIComponent(next)}`);
    const form = page.locator('#access-login-form');
    await form.locator('#username').fill(username);
    await form.locator('#password').fill(password);
    const target = new URL(next, origin).pathname;
    await Promise.all([
        page.waitForURL(url => url.pathname === target),
        form.locator('button[type=submit]').click(),
    ]);
}

// Runs `action` (for example a logout) and resolves once the panel has sent the
// visitor to /acesso. Suites do not serve /acesso themselves, so a stub page is
// served for that address while waiting. Returns the action result and the query.
async function expectAccessPage(page, action = async () => undefined) {
    const matcher = url => url.pathname === '/acesso';
    const handler = route => route.fulfill({ contentType: 'text/html', body: '<!doctype html><title>Acesso</title>' });
    await page.route(matcher, handler);
    try {
        const [result] = await Promise.all([
            action(),
            page.waitForURL(matcher),
        ]);
        return { result, params: new URL(page.url()).searchParams };
    } finally {
        await page.unroute(matcher, handler);
    }
}

// For suites that drive one admin module directly on a panel page without a
// session: answering the /acesso redirect with 204 keeps the browser on the page.
async function stayWithoutSession(page) {
    await page.route(url => url.pathname === '/acesso', route => route.fulfill({ status: 204, body: '' }));
}

async function revealAdminNavigation(page, target) {
    await page.locator(`[data-admin-target="${target}"]`).evaluate(control => {
        const group = control.closest('details');
        if (group) group.open = true;
    });
}

async function openAdminSection(page, target) {
    await revealAdminNavigation(page, target);
    await page.locator(`[data-admin-target="${target}"]`).click();
}

module.exports = { expectAccessPage, openAdminSection, revealAdminNavigation, signIn, stayWithoutSession };
