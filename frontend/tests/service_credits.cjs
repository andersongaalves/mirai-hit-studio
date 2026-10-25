const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const { expectAccessPage, signIn } = require('./support/access.cjs');
const root = path.resolve(__dirname, "..");
const real = process.env.MIRAI_CREDITS_REAL_BACKEND === "POSTGRES_17_DISPOSABLE_ONLY";
if (process.env.MIRAI_CREDITS_REAL_BACKEND && !real) throw new Error("Invalid disposable backend acknowledgement");
const password = real ? process.env.E2E_PASSWORD : "synthetic-only";
assert.ok(password);

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    try {
        for (const username of ["e2e-client-a", "e2e-client-b"]) {
            const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
            const page = await context.newPage();
            const errors = [];
            let failWallet = false;
            page.on("pageerror", error => errors.push(error.message));
            const user = { id: username.endsWith("a") ? 2 : 3, username, role: "cliente", is_admin: false, ativo: true, cliente_id: username.endsWith("a") ? 1 : 2 };
            await context.route("**/*", async route => {
                const url = new URL(route.request().url());
                if (!["http://localhost:4173", "http://localhost:8000"].includes(url.origin)) return route.abort();
                if (real) return route.continue();
                if (url.origin === "http://localhost:4173") {
                    const pathname = url.pathname.startsWith("/cliente") ? "/portal-cliente.html" : decodeURIComponent(url.pathname);
                    const file = path.resolve(root, "." + pathname);
                    assert.ok(file.startsWith(root + path.sep));
                    const types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".ttf": "font/ttf", ".png": "image/png" };
                    try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
                    catch { return route.fulfill({ status: 404, body: "" }); }
                }
                if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "synthetic-only", user } });
                if (url.pathname === "/auth/me") return route.fulfill({ json: user });
                if (url.pathname === "/portal/cliente/configuracao") return route.fulfill({ status: 503, json: { detail: "Synthetic settings unavailable" } });
                if (url.pathname === "/portal/cliente/creditos") {
                    if (failWallet) return route.fulfill({ status: 503, json: { detail: "Créditos temporariamente indisponíveis." } });
                    if (username.endsWith("b")) return route.fulfill({ json: { saldos: [], lotes: [] } });
                    return route.fulfill({ json: {
                        saldos: [{ servico_id: 1, servico_nome: "Mix <img src=x onerror=alert(1)>", unidade: "canal", disponivel: "20.000", bloqueado: "5.000" },
                            { servico_id: 2, servico_nome: "Sessão vocal", unidade: "hora", disponivel: "1.125", bloqueado: "0" }],
                        lotes: [{ id: 1, proposta_id: 70, servico_nome: "Mix", quantidade: "20.000", unidade: "canal", estado: "disponivel", created_at: "2026-10-18T12:00:00Z" }],
                    } });
                }
                return route.fulfill({ json: [] });
            });
            await signIn(page, { next: "/cliente/creditos", username, password });
            const panel = page.locator("#client-credits-content");
            if (username.endsWith("a")) {
                await panel.getByText("Disponíveis: 20 canais", { exact: true }).waitFor();
                assert.equal(await panel.getByText("Disponíveis: 20 canais", { exact: true }).count(), 1);
                assert.equal(await page.locator('[data-route="credits"]').getAttribute("aria-current"), "page");
                assert.ok(!(await panel.innerText()).includes("R$"));
                assert.equal(await panel.locator("img").count(), 0);
                if (!real) {
                    assert.ok((await panel.innerText()).includes("1,125 horas"));
                    assert.ok((await panel.innerText()).includes("Em conciliação: 5 canais"));
                    failWallet = true;
                    await page.reload();
                    await panel.getByRole("button", { name: "Tentar novamente" }).waitFor();
                    failWallet = false;
                    await panel.getByRole("button", { name: "Tentar novamente" }).click();
                    await panel.getByText("Disponíveis: 20 canais", { exact: true }).waitFor();
                    assert.equal(await page.locator("#client-alert").isVisible(), false);
                }
                const output = path.join(os.tmpdir(), "mirai-service-credits");
                await fs.mkdir(output, { recursive: true });
                for (const width of [1280, 390]) {
                    await page.setViewportSize({ width, height: 900 });
                    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
                    await page.screenshot({ path: path.join(output, `wallet-${width}.png`), fullPage: true });
                }
            } else {
                await panel.getByText("Você ainda não possui créditos de serviços.", { exact: true }).waitFor();
                assert.ok(!(await panel.innerText()).includes("20 canais"));
            }
            assert.deepEqual(errors, []);
            await context.close();
        }
        console.log(real ? "CREDITS_POSTGRES_BROWSER_PASS" : "SERVICE_CREDITS_UI_PASS");
    } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
