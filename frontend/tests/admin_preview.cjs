// Admin > Pré-visualização: public pages in the frame (no analytics), portal screens as a
// chosen account through a read-only preview session that never touches real sign-ins.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { openAdminSection, signIn } = require("./support/access.cjs");

const root = path.resolve(__dirname, "..");
const types = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".svg": "image/svg+xml", ".webp": "image/webp", ".png": "image/png" };
const admin = { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true };
const ana = { id: 2, username: "ana", nome_exibicao: "Ana <b>Cliente</b>", role: "cliente", is_admin: false, ativo: true, cliente_id: 7 };
const contas = [
    { id: 2, nome: "Ana <b>Cliente</b>", login: "ana", portal: "cliente", teste: false },
    { id: 9, nome: "Conta QA", login: "qa", portal: "cliente", teste: true },
];

function fileFor(pathname) {
    if (pathname === "/" ) return "/index.html";
    if (/^\/cliente(\/|$)/.test(pathname)) return "/portal-cliente.html";
    if (/^\/produtor(\/|$)/.test(pathname)) return "/portal-produtor.html";
    if (["/artists", "/creators", "/media-games", "/portfolio", "/beats", "/acesso", "/cadastro", "/privacidade"].includes(pathname)) return `${pathname}.html`;
    if (pathname === "/orcamento") return "/calculadora.html";
    return pathname;
}

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const context = await browser.newContext({ viewport: { width: 1360, height: 900 } });
    await context.addInitScript(() => localStorage.setItem("mirai.analytics_consent.v1", "accepted"));
    const page = await context.newPage();
    const errors = [];
    const calls = [];
    const thirdParty = [];
    page.on("pageerror", error => errors.push(error.message));
    await context.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") {
            const file = path.resolve(root, "." + decodeURIComponent(fileFor(url.pathname)));
            assert.ok(file.startsWith(root + path.sep));
            try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
            catch { return route.fulfill({ status: 404, body: "" }); }
        }
        if (url.origin !== "http://localhost:8000") {
            thirdParty.push(url.origin);
            return route.fulfill({ status: 204, body: "" });
        }
        const auth = request.headers().authorization || "";
        calls.push({ method: request.method(), path: url.pathname, auth, search: url.search });
        if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "admin-token", user: admin } });
        if (url.pathname === "/auth/me") return route.fulfill({ json: auth === "Bearer preview-token" ? ana : admin });
        if (url.pathname === "/admin/preview/contas") return route.fulfill({ json: contas });
        if (url.pathname === "/admin/preview/sessao" && request.method() === "POST") {
            assert.equal(auth, "Bearer admin-token");
            assert.deepEqual(request.postDataJSON(), { usuario_id: 2 });
            return route.fulfill({ status: 201, json: { token: "preview-token", expira_em: new Date(Date.now() + 30 * 60000).toISOString(), minutos: 30, portal: "cliente", inicio: "/cliente", conta: contas[0] } });
        }
        if (url.pathname === "/portal/cliente/producoes") return route.fulfill({ json: [] });
        if (url.pathname === "/portal/cliente/propostas") return route.fulfill({ json: [] });
        if (url.pathname.endsWith("/notificacoes")) return route.fulfill({ json: { itens: [], nao_vistas: 0, tem_mais: false } });
        if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        if (url.pathname === "/config") return route.fulfill({ json: {} });
        return route.fulfill({ json: [] });
    });

    try {
        await signIn(page, { next: "/admin.html", username: "admin" });
        await page.waitForFunction(() => !document.getElementById("admin-area").classList.contains("hidden"));
        await openAdminSection(page, "section-preview");
        const frame = page.frameLocator("#preview-frame");
        // Public page: the home, as a visitor, with no analytics, origin or chat from the Admin.
        await frame.locator(".site-nav[data-initialized='true']").waitFor();
        assert.equal(await frame.locator("#site-chat-launcher").count(), 0);
        assert.equal(await page.evaluate(() => document.getElementById("preview-frame").contentWindow.localStorage.getItem("mirai.origem.v1")), null);
        assert.equal(thirdParty.filter(origin => origin.includes("googletagmanager")).length, 0, "no analytics from previews");
        assert.equal(await page.locator("#preview-nova-aba").getAttribute("href"), "/");

        // Device sizes scale the frame to the stage.
        await page.getByRole("button", { name: "Celular" }).click();
        assert.equal(await page.getByRole("button", { name: "Celular" }).getAttribute("aria-pressed"), "true");
        assert.equal(await page.locator("#preview-frame").evaluate(frameElement => frameElement.style.width), "390px");
        await page.getByRole("button", { name: "Computador" }).click();
        const scale = await page.locator("#preview-frame").evaluate(frameElement => frameElement.style.transform);
        assert.match(scale, /^scale\(0\.\d+\)$/, `desktop is scaled to fit: ${scale}`);

        // Portal screen: first pick an account; names are text.
        await page.locator("#preview-tela").selectOption("/cliente/projetos");
        await page.getByText("Escolha uma conta de cliente para ver o portal como ela vê.").waitFor();
        assert.equal(await page.locator("#preview-nova-aba").isHidden(), true, "portal screens never open outside the Admin");
        const options = page.locator("#preview-conta-lista option");
        await page.waitForFunction(() => document.querySelectorAll("#preview-conta-lista option").length === 3);
        assert.deepEqual(await options.allTextContents(), ["Escolha uma conta", "Ana <b>Cliente</b> (ana)", "Conta QA (qa) · teste"]);
        await page.locator("#preview-conta-lista").selectOption("2");
        await frame.locator("#admin-preview-banner").waitFor();
        assert.equal(await frame.locator("#admin-preview-banner").textContent(), "Visualização do Admin · Ana <b>Cliente</b> · somente leitura");
        await page.waitForFunction(() => document.getElementById("preview-status").textContent.includes("vendo como Ana"));
        assert.match(await page.locator("#preview-status").textContent(), /Endereço: \/cliente\/projetos.*só leitura até/);
        // The portal ran on the preview session, and the real sign-ins were untouched.
        assert.ok(calls.some(call => call.path === "/auth/me" && call.auth === "Bearer preview-token"));
        assert.ok(calls.filter(call => call.path.startsWith("/portal/")).every(call => call.auth === "Bearer preview-token"));
        assert.deepEqual(await page.evaluate(() => [localStorage.getItem("mirai.auth.cliente.access_token"), localStorage.getItem("mirai.auth.admin.access_token")]), [null, "admin-token"]);
        // Nothing is sent from the preview: writes stop in the browser (and the API refuses them).
        const before = calls.filter(call => call.method !== "GET").length;
        const write = await page.evaluate(async () => {
            const auth = await document.getElementById("preview-frame").contentWindow.eval("import('/js/admin/auth.js')");
            const response = await auth.authFetch("/portal/cliente/producoes/1/mensagens", { method: "POST", body: JSON.stringify({ texto: "x" }) });
            return [response.status, (await response.json()).detail];
        });
        assert.deepEqual(write, [403, "Modo de visualização do Admin: nada pode ser enviado ou alterado."]);
        assert.equal(calls.filter(call => call.method !== "GET").length, before);
        if (process.env.SHOTS) {
            await page.getByRole("button", { name: "Celular" }).click();
            await page.waitForTimeout(400);
            await page.screenshot({ path: path.join(process.env.SHOTS, "admin-preview-celular.png") });
            await page.getByRole("button", { name: "Computador" }).click();
            await page.waitForTimeout(400);
            await page.screenshot({ path: path.join(process.env.SHOTS, "admin-preview-desktop.png") });
        }
        // Switching screens in the same portal reuses the session (one audit entry).
        await page.locator("#preview-tela").selectOption("/cliente/explorar");
        await frame.locator("#admin-preview-banner").waitFor();
        assert.equal(calls.filter(call => call.path === "/admin/preview/sessao").length, 1);
        // Admin sign-out ends the preview sessions of this tab.
        await page.evaluate(() => document.dispatchEvent(new CustomEvent("admin:logout")));
        assert.equal(await page.evaluate(() => sessionStorage.getItem("mirai.preview.cliente")), null);

        // Outside the Admin frame the portals ignore preview sessions.
        await page.evaluate(() => sessionStorage.setItem("mirai.preview.cliente", JSON.stringify({ token: "preview-token", expira_em: new Date(Date.now() + 600000).toISOString(), conta: { nome: "x" } })));
        const direct = await context.newPage();
        await direct.goto("http://localhost:4173/acesso.html");
        const viaPortal = await direct.evaluate(async () => (await import("/js/modules/preview_frame.js")).inAdminPreview());
        assert.equal(viaPortal, false);
        await direct.close();

        for (const width of [390, 1024]) {
            await page.setViewportSize({ width, height: 900 });
            const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            assert.ok(overflow <= 1, `admin preview overflow at ${width}px: ${overflow}px`);
        }
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, "admin-preview.png") });
        assert.deepEqual(errors, []);
        console.log("PASS: admin preview of public pages and portals, device sizes, read-only session and no analytics.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
