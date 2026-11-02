// Admin > Marketing: headline numbers, visits over time with hover tooltip, channels,
// sources, campaigns, pages, places, devices, site events, leads by origin, commercial
// funnel; the Google Analytics setup guide when it is not connected; period switching.
const { chromium } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { openAdminSection, signIn } = require("./support/access.cjs");

const root = path.resolve(__dirname, "..");
const days = n => Array.from({ length: n }, (_, index) => {
    const date = new Date(Date.UTC(2026, 9, 6 + index));
    return date.toISOString().slice(0, 10);
});
const site = {
    status: "ok",
    leads: {
        total: 12, anterior: 8, com_origem: 9,
        serie: days(28).map((data, index) => ({ data, leads: index % 5 === 0 ? 2 : 0 })),
        por_origem: [{ nome: "instagram / social", quantidade: 5 }, { nome: "Google (busca)", quantidade: 3 }, { nome: "Direto <b>x</b>", quantidade: 1 }],
        por_servico: [{ nome: "Mixagem", quantidade: 7 }, { nome: "Beat", quantidade: 5 }],
        por_campanha: [{ nome: "lancamento-nov", quantidade: 4 }],
        paginas_de_entrada: [{ nome: "/artists", quantidade: 6 }],
    },
    funil: [{ etapa: "Pedidos de orçamento", quantidade: 12 }, { etapa: "Propostas enviadas", quantidade: 6 },
        { etapa: "Propostas aceitas", quantidade: 3 }, { etapa: "Pagamentos confirmados", quantidade: 2 }],
    receita_confirmada: 1450.5,
    newsletter: { novos: 4, ativos: 31, por_origem: [{ nome: "Footer", quantidade: 4 }] },
    chat: { conversas: 9, encaminhadas: 2, por_canal: [{ nome: "Site", quantidade: 9 }] },
    beats: { licencas: 3, por_status: [{ nome: "adquirida", quantidade: 2 }, { nome: "reservada", quantidade: 1 }] },
};
const ga = {
    status: "ok", agora_no_site: 3,
    totais: { activeUsers: 1200, newUsers: 900, sessions: 1500, screenPageViews: 4100, engagementRate: 0.62, averageSessionDuration: 95 },
    anterior: { activeUsers: 1000, newUsers: 700, sessions: 1600, screenPageViews: 3000, engagementRate: 0.6, averageSessionDuration: 80 },
    serie: days(28).map((data, index) => ({ data, visitantes: 30 + index, sessoes: 40 + index })),
    canais: [{ nome: "Organic Social", sessoes: 700, visitantes: 600 }, { nome: "Direct", sessoes: 500, visitantes: 400 }],
    origens: [{ nome: "instagram.com / referral", sessoes: 600, visitantes: 500 }, { nome: "(direct) / (none)", sessoes: 500, visitantes: 400 },
        { nome: "=HYPERLINK(\"x\")", sessoes: 1, visitantes: 1 }],
    paginas: [{ nome: "/", visualizacoes: 2000, visitantes: 900 }, { nome: "/artists", visualizacoes: 800, visitantes: 400 }],
    paises: [{ nome: "Brazil", visitantes: 1100 }], cidades: [{ nome: "São Paulo", visitantes: 500 }, { nome: "(not set)", visitantes: 9 }],
    dispositivos: [{ nome: "mobile", visitantes: 900 }, { nome: "desktop", visitantes: 300 }],
    eventos: [{ nome: "generate_lead", quantidade: 12 }, { nome: "begin_checkout", quantidade: 4 }, { nome: "ai_chat_open", quantidade: 0 }],
    campanhas: [{ nome: "lancamento-nov", sessoes: 300, visitantes: 250 }, { nome: "(not set)", sessoes: 900, visitantes: 800 }],
};

(async () => {
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
    const page = await context.newPage();
    const errors = [];
    const requests = [];
    let connected = true;
    page.on("pageerror", error => errors.push(error.message));
    await context.route("**/*", async route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin === "http://localhost:4173") {
            const file = path.resolve(root, "." + decodeURIComponent(url.pathname));
            assert.ok(file.startsWith(root + path.sep));
            const types = { ".js": "text/javascript", ".html": "text/html", ".css": "text/css", ".svg": "image/svg+xml" };
            try { return route.fulfill({ body: await fs.readFile(file), contentType: types[path.extname(file)] || "application/octet-stream" }); }
            catch { return route.fulfill({ status: 404, body: "" }); }
        }
        if (url.origin !== "http://localhost:8000") return route.fulfill({ status: 200, body: "" });
        const admin = { id: 1, username: "admin", role: "admin", is_admin: true, ativo: true };
        if (url.pathname === "/auth/login") return route.fulfill({ json: { access_token: "synthetic-admin", user: admin } });
        if (url.pathname === "/auth/me") return route.fulfill({ json: admin });
        if (url.pathname === "/admin/marketing") {
            requests.push(url.search);
            return route.fulfill({ json: {
                dias: Number(url.searchParams.get("dias")), atualizado_em: "2026-11-02T18:00:00Z",
                google_analytics: connected ? ga : { status: "nao_configurado", mensagem: "Conecte o Google Analytics para ver visitantes, origens e campanhas.", medicao: "G-W4GLJXPRDM" },
                cloudflare: { status: "ok", totais: { visitantes: 2400, paginas: 5000, requisicoes: 90000, ameacas: 12 },
                    serie: days(28).map((data, index) => ({ data, visitantes: 80 + index, paginas: 170, requisicoes: 3000 })),
                    paises: [{ nome: "BR", requisicoes: 80000 }] },
                site,
            } });
        }
        if (url.pathname === "/config") return route.fulfill({ json: {} });
        if (url.pathname === "/dashboard") return route.fulfill({ json: { metrics: {}, pipeline: {}, attention: {}, recent_activity: [] } });
        return route.fulfill({ json: [] });
    });

    try {
        await signIn(page, { next: "/admin.html", username: "admin" });
        await page.waitForFunction(() => !document.getElementById("admin-area").classList.contains("hidden"));
        await openAdminSection(page, "section-marketing");
        const content = page.locator("#marketing-content");
        await content.locator(".mkt-tile").first().waitFor();
        assert.deepEqual(requests, ["?dias=28"]);
        const text = await content.textContent();
        assert.match(text, /Google Analytics: conectado/);
        assert.match(text, /Visitantes1\.200▲ \+20% vs período anterior900 novos/);
        assert.match(text, /Agora no site3/);
        assert.match(text, /Sessões1\.500▼ -6% vs período anterior/);
        assert.match(text, /Pedidos de orçamento12▲ \+50%/);
        assert.match(text, /Conversão em pedido0,8%/);
        assert.match(text, /Receita confirmadaR\$\s1\.450,50/);
        // Channels and devices are translated; GA placeholders are filtered out.
        const channels = content.locator(".mkt-panel").filter({ hasText: "Canais" });
        assert.match(await channels.textContent(), /Redes sociais700.*Direto500/);
        assert.match(await content.locator(".mkt-panel").filter({ hasText: "Origem / mídia" }).textContent(), /Direto500/);
        assert.doesNotMatch(await content.locator(".mkt-panel").filter({ hasText: /^Campanhas/ }).first().textContent(), /not set/);
        assert.doesNotMatch(await content.locator(".mkt-panel").filter({ hasText: "Cidades" }).textContent(), /not set/);
        assert.match(await content.locator(".mkt-panel").filter({ hasText: "Dispositivos" }).textContent(), /Celular900.*Computador300/);
        const events = content.locator(".mkt-panel").filter({ hasText: "O que as pessoas fazem" });
        assert.match(await events.textContent(), /Pedido de orçamento enviado12/);
        assert.doesNotMatch(await events.textContent(), /Chat aberto/, "zero events are hidden");
        // Leads by origin: text is safe, bars proportional.
        const origin = content.locator(".mkt-panel").filter({ hasText: "Pedidos por origem" });
        assert.match(await origin.textContent(), /9 de 12 com origem registrada/);
        assert.equal(await origin.locator("b").count(), 0);
        const widths = await origin.locator(".mkt-bar__fill").evaluateAll(items => items.map(item => item.style.width));
        assert.equal(widths[0], "100%");
        assert.equal(widths[1], "60%");
        // Funnel with rates.
        assert.match(await content.locator(".mkt-funnel").textContent(), /Propostas aceitas3 · 25% dos pedidos/);

        // Visits chart: hover shows the day and value; a table view carries the same numbers.
        const chart = content.locator(".mkt-panel").filter({ hasText: "Visitantes por dia" });
        assert.match(await chart.locator("svg").getAttribute("aria-label"), /Visitantes por dia: total 1\.218, máximo 57/);
        const hits = chart.locator(".mkt-chart__hit");
        assert.equal(await hits.count(), 28);
        await hits.nth(27).hover();
        const tooltip = chart.locator(".mkt-tooltip");
        await tooltip.waitFor();
        assert.match(await tooltip.textContent(), /02\/11Visitantes: 57/);
        await chart.locator(".mkt-chart__table summary").click();
        assert.equal(await chart.locator(".mkt-chart__table tr").count(), 29);
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, "marketing-ga.png"), fullPage: true });

        // Export: automatic summary + every table, as PDF (print view) and CSV.
        await page.locator(".mkt-export > summary").click();
        const [download] = await Promise.all([
            page.waitForEvent("download"),
            page.getByRole("button", { name: "Planilha (CSV)" }).click(),
        ]);
        assert.match(download.suggestedFilename(), /^marketing-mirai-\d{4}-\d{2}-\d{2}-28dias\.csv$/);
        const csv = await fs.readFile(await download.path(), "utf8");
        assert.equal(csv.charCodeAt(0), 0xFEFF, "BOM for Excel");
        assert.match(csv, /Relatório de marketing · Mirai Hit Studio/);
        assert.match(csv, /Destaques/);
        assert.match(csv, /1\.200 visitantes e 1\.500 sessões \(alta de 20% em relação ao período anterior\)\./);
        assert.match(csv, /Principal canal: Redes sociais, com 58,3% das sessões\./);
        assert.match(csv, /Origem que mais gerou pedidos: instagram \/ social \(5\)\./);
        assert.match(csv, /\r\nCanais\r\nCanal;Sessões;Visitantes\r\nRedes sociais;700;600\r\n/);
        assert.match(csv, /'=HYPERLINK\(""x""\)/, "formulas are neutralized");
        await page.locator(".mkt-export > summary").click();
        const [report] = await Promise.all([
            context.waitForEvent("page"),
            page.getByRole("button", { name: "Relatório (PDF)" }).click(),
        ]);
        await report.locator("h1").waitFor();
        assert.equal(await report.locator("h1").textContent(), "Relatório de marketing");
        assert.match(await report.locator(".destaques").textContent(), /Receita confirmada no período: R\$\s1\.450,50\./);
        assert.ok(await report.locator("table").count() >= 15);
        assert.equal(await report.locator("b").count(), 0, "data is text, never HTML");
        assert.equal(await report.getByRole("button", { name: "Salvar como PDF / imprimir" }).count(), 1);
        if (process.env.SHOTS) await report.screenshot({ path: path.join(process.env.SHOTS, "marketing-report.png") });
        await report.close();
        assert.match(await page.locator("#marketing-exportar-status").textContent(), /Salvar como PDF/);

        // Period and refresh.
        await page.getByRole("button", { name: "90 dias" }).click();
        await page.waitForFunction(() => document.querySelector('[data-mkt-dias="90"]')?.getAttribute("aria-pressed") === "true");
        await page.waitForFunction(count => window.__mkt === undefined && document.querySelector("#marketing-content .mkt-tile"), 2);
        await page.getByRole("button", { name: "Atualizar" }).click();
        await page.waitForFunction(() => !document.getElementById("marketing-content").hasAttribute("aria-busy"));
        assert.deepEqual(requests, ["?dias=28", "?dias=90", "?dias=90&atualizar=true"]);

        // Without Google Analytics: setup guide; Cloudflare visits fill in.
        connected = false;
        await page.getByRole("button", { name: "7 dias" }).click();
        await content.locator(".mkt-setup").waitFor();
        const setup = await content.locator(".mkt-setup").textContent();
        assert.match(setup, /Google Analytics Data API/);
        assert.match(setup, /GA4_PROPERTY_ID/);
        assert.match(setup, /GA4_SERVICE_ACCOUNT_JSON/);
        assert.match(setup, /G-W4GLJXPRDM/);
        assert.match(setup, /Não cole a chave aqui/);
        const offline = await content.textContent();
        assert.match(offline, /Google Analytics: não configurado/);
        assert.match(offline, /Visitantes \(soma diária\)2\.400/);
        assert.match(offline, /Conversão em pedido—precisa do Google Analytics/);
        assert.match(await content.locator(".mkt-panel").filter({ hasText: "Visitantes por dia" }).textContent(), /Cloudflare/);
        assert.match(await content.locator(".mkt-panel").filter({ hasText: "Países (requisições)" }).textContent(), /BR80\.000/);

        // Phone width: no sideways scroll.
        await page.setViewportSize({ width: 390, height: 844 });
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        assert.ok(overflow <= 1, `horizontal overflow ${overflow}px`);
        if (process.env.SHOTS) await page.screenshot({ path: path.join(process.env.SHOTS, "marketing-mobile.png"), fullPage: true });
        assert.deepEqual(errors, []);
        console.log("PASS: marketing tiles, visits chart with tooltip/table, channels to funnel, GA setup guide, Cloudflare fallback, periods, mobile.");
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exit(1);
});
