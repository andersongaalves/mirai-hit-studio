const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const http = require("node:http");
const path = require("node:path");
const { chromium } = require("playwright");

const root = path.resolve(__dirname, "..");
const checkoutToken = "11111111-1111-4111-8111-111111111111";
const runs = Number(process.env.PERF_RUNS || 3);
const pages = [
    { name: "home", path: "/", ready: ".site-nav[data-initialized='true']" },
    { name: "artists", path: "/artists", ready: ".site-nav[data-initialized='true']" },
    { name: "creators", path: "/creators", ready: ".site-nav[data-initialized='true']" },
    { name: "media-games", path: "/media-games", ready: ".site-nav[data-initialized='true']" },
    { name: "portfolio", path: "/portfolio", ready: ".portfolio-card" },
    { name: "orcamento", path: "/orcamento", ready: "#srv_1" },
    { name: "checkout", path: `/checkout/${checkoutToken}`, ready: "#checkout-content:not(.hidden)" },
];
const profiles = [
    { name: "mobile", viewport: { width: 390, height: 844 }, cpu: 4, latency: 150, down: 1_600_000, up: 750_000 },
    { name: "desktop", viewport: { width: 1440, height: 900 }, cpu: 1, latency: 20, down: 10_000_000, up: 5_000_000 },
];
const aliases = {
    "/": "index.html",
    "/artists": "artists.html",
    "/creators": "creators.html",
    "/media-games": "media-games.html",
    "/portfolio": "portfolio.html",
    "/orcamento": "calculadora.html",
    [`/checkout/${checkoutToken}`]: "checkout.html",
};
const contentTypes = {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".ttf": "font/ttf",
};

function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)];
}

function round(value) {
    return Math.round((value || 0) * 10) / 10;
}

async function startServer() {
    const server = http.createServer(async (request, response) => {
        const pathname = decodeURIComponent(new URL(request.url, "http://local").pathname);
        const relative = aliases[pathname] || pathname.replace(/^\//, "");
        const file = path.resolve(root, relative);
        if (!file.startsWith(`${root}${path.sep}`) && file !== path.join(root, "index.html")) {
            response.writeHead(403).end();
            return;
        }
        try {
            const body = await fs.readFile(file);
            response.writeHead(200, {
                "Content-Type": contentTypes[path.extname(file)] || "application/octet-stream",
                "Cache-Control": "no-store",
                "Content-Length": body.length,
            });
            response.end(body);
        } catch {
            response.writeHead(404).end();
        }
    });
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    return { server, origin: `http://127.0.0.1:${server.address().port}` };
}

function apiResponse(route) {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/config") return route.fulfill({ json: { desconto: 0 } });
    if (pathname === "/servicos") return route.fulfill({ json: [{
        id: 1, nome: "Produção musical", categoria: "avulso", valor_base: 500,
        aplica_desconto: false, parametros: "descricao,guia", estrutura_servico: null,
    }] });
    if (pathname === "/projetos") return route.fulfill({ json: [{
        id: 1, titulo: "Demo Mirai", artista: "Mirai Hit Studio", categoria: "Trilha",
        descricao: "Demonstração identificada.", link_audio: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        link_capa: "/img/mirai-studio-hero.webp", destaque: true,
        vertical: "media_games", segmentos_json: ["games"], case_type: "demo",
    }] });
    if (pathname === `/checkout/${checkoutToken}`) return route.fulfill({ json: {
        proposta_numero: "MHS-001", descricao: "Trilha original", valor_total: "500.00",
        valor_pago: "0.00", saldo: "500.00", moeda: "BRL", status: "pendente", tentativa: null,
        opcoes: [{ tipo: "integral", titulo: "Pagamento completo", valor: "500.00" }],
    } });
    return route.fulfill({ json: [] });
}

async function measure(browser, origin, profile, target) {
    const context = await browser.newContext({ viewport: profile.viewport });
    await context.addInitScript(() => {
        localStorage.setItem("mirai.analytics_consent.v1", "rejected");
        window.__miraiPerf = { lcp: 0, lcpElement: null, cls: 0, clsSources: [], longTasks: [] };
        new PerformanceObserver(list => {
            const entries = list.getEntries();
            const latest = entries.at(-1);
            window.__miraiPerf.lcp = latest?.startTime || window.__miraiPerf.lcp;
            if (latest?.element) window.__miraiPerf.lcpElement = {
                tag: latest.element.tagName,
                id: latest.element.id,
                className: String(latest.element.className || ""),
                url: latest.url ? new URL(latest.url).pathname : "",
                text: String(latest.element.textContent || "").trim().slice(0, 80),
            };
        }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver(list => {
            for (const entry of list.getEntries()) if (!entry.hadRecentInput) {
                window.__miraiPerf.cls += entry.value;
                window.__miraiPerf.clsSources.push(...entry.sources.map(source => ({
                    tag: source.node?.tagName || "",
                    id: source.node?.id || "",
                    className: String(source.node?.className || ""),
                })));
            }
        }).observe({ type: "layout-shift", buffered: true });
        new PerformanceObserver(list => {
            for (const entry of list.getEntries()) window.__miraiPerf.longTasks.push(entry.duration);
        }).observe({ type: "longtask", buffered: true });
    });
    await context.route("http://localhost:8000/**", apiResponse);
    const page = await context.newPage();
    const client = await context.newCDPSession(page);
    await client.send("Network.enable");
    await client.send("Network.setCacheDisabled", { cacheDisabled: true });
    await client.send("Network.emulateNetworkConditions", {
        offline: false, latency: profile.latency,
        downloadThroughput: profile.down / 8, uploadThroughput: profile.up / 8,
    });
    await client.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
    await client.send("Performance.enable");
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
    await page.goto(`${origin}${target.path}`, { waitUntil: "load" });
    await page.waitForSelector(target.ready, { timeout: 10_000 });
    await page.waitForTimeout(800);

    const browserMetrics = await page.evaluate(() => {
        const navigation = performance.getEntriesByType("navigation")[0];
        const resources = performance.getEntriesByType("resource");
        const perf = window.__miraiPerf;
        const bytes = entry => entry.transferSize || entry.encodedBodySize || 0;
        const resourceBytes = resources.reduce((total, entry) => total + bytes(entry), 0);
        const byType = {};
        for (const entry of resources) {
            const type = entry.initiatorType || "other";
            byType[type] = (byType[type] || 0) + bytes(entry);
        }
        return {
            lcp: perf.lcp,
            lcpElement: perf.lcpElement,
            cls: perf.cls,
            clsSources: perf.clsSources,
            fcp: performance.getEntriesByName("first-contentful-paint")[0]?.startTime || 0,
            tbtProxy: perf.longTasks.reduce((total, duration) => total + Math.max(0, duration - 50), 0),
            requests: resources.length + 1,
            bytes: resourceBytes + bytes(navigation),
            jsBytes: byType.script || 0,
            cssBytes: byType.css || 0,
            imageBytes: byType.img || 0,
            domContentLoaded: navigation.domContentLoadedEventEnd,
            load: navigation.loadEventEnd,
            resources: resources.map(entry => ({ name: new URL(entry.name).pathname, type: entry.initiatorType, bytes: bytes(entry) })),
        };
    });
    const cdpMetrics = await client.send("Performance.getMetrics");
    const metric = name => cdpMetrics.metrics.find(item => item.name === name)?.value || 0;
    await context.close();
    assert.deepEqual(errors, [], `${target.name}/${profile.name} console errors`);
    return {
        ...browserMetrics,
        scriptMs: metric("ScriptDuration") * 1000,
        taskMs: metric("TaskDuration") * 1000,
        layoutMs: metric("LayoutDuration") * 1000,
    };
}

(async () => {
    const { server, origin } = await startServer();
    const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || "msedge" });
    const output = { environment: { runs, browser: "Edge headless", localServer: true }, results: [] };
    try {
        for (const profile of profiles) {
            for (const target of pages) {
                const samples = [];
                for (let index = 0; index < runs; index += 1) samples.push(await measure(browser, origin, profile, target));
                const numericKeys = ["lcp", "cls", "fcp", "tbtProxy", "requests", "bytes", "jsBytes", "cssBytes", "imageBytes", "domContentLoaded", "load", "scriptMs", "taskMs", "layoutMs"];
                const summary = { page: target.name, profile: profile.name };
                for (const key of numericKeys) summary[key] = round(median(samples.map(sample => sample[key])));
                summary.lcpElement = samples.at(-1).lcpElement;
                summary.clsSources = samples.at(-1).clsSources;
                summary.largestResources = [...samples.at(-1).resources].sort((a, b) => b.bytes - a.bytes).slice(0, 5);
                const loaded = samples.flatMap(sample => sample.resources.map(resource => resource.name));
                assert.ok(!loaded.includes("/css/pages/admin.css"), `${target.name} must not load Admin CSS`);
                if (target.name !== "orcamento") assert.ok(!loaded.includes("/css/pages/calculator.css"), `${target.name} must not load calculator CSS`);
                if (target.name !== "portfolio") assert.ok(!loaded.includes("/css/pages/portfolio.css"), `${target.name} must not load portfolio CSS`);
                assert.ok(!loaded.includes("/css/chat.css"), `${target.name} must defer chat CSS until intent`);
                assert.ok(!loaded.includes("/js/chat/chat.js"), `${target.name} must defer full chat JS until intent`);
                assert.ok(!loaded.some(name => name.includes("mercadopago.com/js")), `${target.name} must not preload Mercado Pago SDK`);
                output.results.push(summary);
            }
        }
        assert.ok((await fs.stat(path.join(root, "assets/favicon.png"))).size < 16_000, "favicon must stay below 16 KB");
        assert.ok((await fs.stat(path.join(root, "img/logo-horizontal.png"))).size < 80_000, "checkout logo must stay below 80 KB");
        console.log(JSON.stringify(output, null, 2));
    } finally {
        await browser.close();
        await new Promise(resolve => server.close(resolve));
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
