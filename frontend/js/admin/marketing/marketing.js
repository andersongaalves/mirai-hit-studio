// Admin "Marketing": visits, where they come from (channels, sources, campaigns, places,
// devices) and what they turn into (site events, leads, proposals, payments). Google
// Analytics 4, Cloudflare and the site's own records, each block failing on its own.
import { authFetch } from "../auth.js";
import { abrirRelatorio, baixarCsv } from "./relatorio.js";

const SVG = "http://www.w3.org/2000/svg";
const PERIODOS = [[7, "7 dias"], [28, "28 dias"], [90, "90 dias"]];
const EVENTOS = {
    page_view: "Páginas vistas",
    view_vertical: "Visitas a Artists / Creators / Games",
    view_service: "Serviço aberto",
    listen_portfolio: "Áudio do portfólio ouvido",
    begin_briefing: "Começou um pedido",
    generate_lead: "Pedido de orçamento enviado",
    newsletter_subscribe: "Inscrição na newsletter",
    ai_chat_open: "Chat aberto",
    ai_chat_message: "Mensagens no chat",
    ai_chat_handoff: "Chat passado para a equipe",
    begin_checkout: "Abriu o pagamento",
    payment_method_selected: "Escolheu forma de pagamento",
    payment_attempt: "Tentou pagar",
};
const CANAIS = {
    Direct: "Direto", "Organic Search": "Busca orgânica", "Organic Social": "Redes sociais", Referral: "Outros sites",
    "Paid Search": "Busca paga", "Paid Social": "Redes sociais pagas", Email: "E-mail", Unassigned: "Não classificado",
    Display: "Display", "Organic Video": "Vídeo", "Cross-network": "Várias redes", "Organic Shopping": "Shopping",
};
const DISPOSITIVOS = { mobile: "Celular", desktop: "Computador", tablet: "Tablet", "smart tv": "TV" };
const LICENCAS = { reservada: "Reservadas", adquirida: "Adquiridas", cancelada: "Canceladas" };

const state = { dias: 28, data: null, loading: null, bound: false };
const byId = id => document.getElementById(id);

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "" && text !== null && text !== undefined) node.textContent = String(text);
    return node;
}

const numero = value => Number(value || 0).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
const moeda = value => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const pct = value => `${(Number(value || 0) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const duracao = seconds => {
    const total = Math.round(Number(seconds || 0));
    return total >= 60 ? `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, "0")} s` : `${total} s`;
};
const dia = value => new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

function variacao(atual, anterior) {
    if (!anterior) return null;
    const change = (atual - anterior) / anterior;
    return { change, texto: `${change >= 0 ? "+" : ""}${(change * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}% vs período anterior` };
}

// ---------- Pieces ----------

function tile(label, value, { hint = "", delta = null, fonte = "" } = {}) {
    const card = el("article", "mkt-tile");
    card.append(el("span", "mkt-tile__label", label), el("strong", "mkt-tile__value", value));
    if (delta) {
        const badge = el("span", `mkt-tile__delta ${delta.change >= 0 ? "is-up" : "is-down"}`);
        badge.append(el("span", "", delta.change >= 0 ? "▲" : "▼"), ` ${delta.texto}`);
        card.append(badge);
    }
    if (hint) card.append(el("span", "mkt-tile__hint", hint));
    if (fonte) card.append(el("span", "mkt-tile__source", fonte));
    return card;
}

function panel(title, { subtitle = "", fonte = "", wide = false } = {}) {
    const box = el("section", `mkt-panel${wide ? " mkt-panel--wide" : ""}`);
    const head = el("header", "mkt-panel__head");
    const titleEl = el("h2", "mkt-panel__title", title);
    head.append(titleEl);
    if (fonte) head.append(el("span", "mkt-source", fonte));
    box.append(head);
    if (subtitle) box.append(el("p", "mkt-panel__subtitle", subtitle));
    return box;
}

function empty(text) {
    return el("p", "mkt-empty", text);
}

// Ranked list with horizontal bars; the numbers are text, so it reads as a table too.
function barList(items, { valueKey = "quantidade", label = item => item.nome, format = numero, unit = "" } = {}) {
    if (!items?.length) return empty("Nada no período.");
    const max = Math.max(...items.map(item => Number(item[valueKey]) || 0), 1);
    const total = items.reduce((sum, item) => sum + (Number(item[valueKey]) || 0), 0);
    const list = el("ol", "mkt-bars");
    items.forEach(item => {
        const value = Number(item[valueKey]) || 0;
        const row = el("li", "mkt-bar");
        row.title = `${label(item)}: ${format(value)}${unit}${total ? ` (${pct(value / total)})` : ""}`;
        const name = el("span", "mkt-bar__name", label(item));
        const amount = el("span", "mkt-bar__value", `${format(value)}${unit}`);
        const track = el("span", "mkt-bar__track");
        const fill = el("span", "mkt-bar__fill");
        fill.style.width = `${Math.max(2, (value / max) * 100)}%`;
        track.append(fill);
        row.append(name, amount, track);
        list.append(row);
    });
    return list;
}

// Single-series line over time with a crosshair tooltip (one axis, recessive grid).
function lineChart(points, { key, label, fonte, barras = false }) {
    const wrap = el("div", "mkt-chart");
    if (!points?.length) {
        wrap.append(empty("Sem dados no período."));
        return wrap;
    }
    const width = 720;
    const height = 220;
    const pad = { top: 16, right: 12, bottom: 28, left: 40 };
    const values = points.map(point => Number(point[key]) || 0);
    const max = Math.max(...values, 1);
    // Columns sit inside their day slot; a line runs edge to edge.
    const plot = width - pad.left - pad.right;
    const step = barras ? plot / points.length : plot / Math.max(points.length - 1, 1);
    const x = index => pad.left + (barras ? (index + 0.5) * step : index * step);
    const y = value => pad.top + (height - pad.top - pad.bottom) * (1 - value / max);
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("class", "mkt-chart__svg");
    svg.setAttribute("role", "img");
    const totalValue = values.reduce((sum, value) => sum + value, 0);
    svg.setAttribute("aria-label", `${label} por dia: total ${numero(totalValue)}, máximo ${numero(Math.max(...values))}.`);
    const add = (name, attrs) => {
        const node = document.createElementNS(SVG, name);
        Object.entries(attrs).forEach(([attr, value]) => node.setAttribute(attr, String(value)));
        svg.append(node);
        return node;
    };
    for (const fraction of max < 4 ? [0, 1] : [0, 0.5, 1]) {
        const value = max * fraction;
        add("line", { x1: pad.left, x2: width - pad.right, y1: y(value), y2: y(value), class: "mkt-chart__grid" });
        const tick = add("text", { x: pad.left - 6, y: y(value) + 4, class: "mkt-chart__tick", "text-anchor": "end" });
        tick.textContent = numero(value);
    }
    const labelEvery = Math.max(1, Math.ceil(points.length / 7));
    points.forEach((point, index) => {
        if (index % labelEvery && index !== points.length - 1) return;
        const tick = add("text", { x: x(index), y: height - 8, class: "mkt-chart__tick", "text-anchor": "middle" });
        tick.textContent = dia(point.data);
    });
    if (barras) {
        // Counts per day: columns with a 2px gap, rounded data-end, anchored to the baseline.
        const barWidth = Math.max(2, Math.min(18, step - 2));
        values.forEach((value, index) => {
            if (!value) return;
            const top = y(value);
            add("rect", { x: x(index) - barWidth / 2, y: top, width: barWidth, height: Math.max(1, y(0) - top),
                rx: Math.min(4, barWidth / 2), class: "mkt-chart__bar" });
        });
    } else {
        const path = values.map((value, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
        add("path", { d: `${path} L${x(points.length - 1)},${y(0)} L${x(0)},${y(0)} Z`, class: "mkt-chart__area" });
        add("path", { d: path, class: "mkt-chart__line" });
    }
    const cross = add("line", { x1: 0, x2: 0, y1: pad.top, y2: y(0), class: "mkt-chart__cross", visibility: "hidden" });
    const dot = add("circle", { r: 4.5, class: "mkt-chart__dot", visibility: "hidden" });
    const tooltip = el("div", "mkt-tooltip");
    tooltip.hidden = true;
    const show = index => {
        const value = values[index];
        cross.setAttribute("x1", x(index));
        cross.setAttribute("x2", x(index));
        cross.setAttribute("visibility", "visible");
        dot.setAttribute("cx", x(index));
        dot.setAttribute("cy", y(value));
        dot.setAttribute("visibility", barras ? "hidden" : "visible");
        tooltip.replaceChildren(el("strong", "", dia(points[index].data)), el("span", "", `${label}: ${numero(value)}`));
        tooltip.hidden = false;
        const box = svg.getBoundingClientRect();
        const left = (x(index) / width) * box.width;
        tooltip.style.left = `${Math.min(Math.max(left, 60), box.width - 60)}px`;
    };
    const hide = () => {
        cross.setAttribute("visibility", "hidden");
        dot.setAttribute("visibility", "hidden");
        tooltip.hidden = true;
    };
    points.forEach((point, index) => {
        add("rect", { x: x(index) - step / 2, y: pad.top, width: Math.max(step, 6), height: height - pad.top - pad.bottom,
            class: "mkt-chart__hit" }).addEventListener("mouseenter", () => show(index));
    });
    svg.addEventListener("mouseleave", hide);
    wrap.append(svg, tooltip);
    // Keyboard / screen reader view of the same numbers.
    const table = el("details", "mkt-chart__table");
    table.append(el("summary", "", "Ver em tabela"));
    const grid = el("table");
    const head = el("tr");
    head.append(el("th", "", "Dia"), el("th", "", label));
    grid.append(head);
    points.forEach((point, index) => {
        const row = el("tr");
        row.append(el("td", "", dia(point.data)), el("td", "", numero(values[index])));
        grid.append(row);
    });
    table.append(grid);
    wrap.append(table);
    if (fonte) wrap.append(el("p", "mkt-chart__source", fonte));
    return wrap;
}

function funnel(steps) {
    const list = el("ol", "mkt-funnel");
    const first = Number(steps[0]?.quantidade) || 0;
    steps.forEach((step, index) => {
        const value = Number(step.quantidade) || 0;
        const row = el("li", "mkt-funnel__step");
        const bar = el("span", "mkt-funnel__bar");
        bar.style.width = `${first ? Math.max(4, (value / first) * 100) : 4}%`;
        const rate = index && first ? ` · ${pct(value / first)} dos pedidos` : "";
        row.append(el("span", "mkt-funnel__label", step.etapa), el("strong", "mkt-funnel__value", `${numero(value)}${rate}`), bar);
        list.append(row);
    });
    return list;
}

function setupCard(ga) {
    const card = panel("Conectar o Google Analytics", { wide: true });
    card.classList.add("mkt-setup");
    card.append(el("p", "", ga.mensagem));
    const steps = el("ol", "mkt-setup__steps");
    [
        "No Google Cloud (console.cloud.google.com), crie ou escolha um projeto e ative a API \"Google Analytics Data API\".",
        "Em IAM e administrador → Contas de serviço, crie uma conta de serviço e gere uma chave do tipo JSON (o arquivo é baixado).",
        `No Google Analytics, em Administrador → Gerenciamento de acesso à propriedade, adicione o e-mail da conta de serviço com o papel Leitor (propriedade do fluxo ${ga.medicao || "G-W4GLJXPRDM"}).`,
        "Ainda no Administrador → Detalhes da propriedade, copie o ID da propriedade (só números).",
        "No Render, serviço mirai-hit-studio → Environment, crie GA4_PROPERTY_ID com esse número e GA4_SERVICE_ACCOUNT_JSON com o conteúdo inteiro do arquivo JSON. Salve: o serviço reinicia sozinho.",
    ].forEach(text => steps.append(el("li", "", text)));
    card.append(steps, el("p", "mkt-panel__subtitle", "Não cole a chave aqui nem em conversas: ela fica só no Render. Os números de visitas da Cloudflare e os do próprio site já aparecem sem isso."));
    return card;
}

function status(source, label) {
    const ok = source?.status === "ok";
    const chip = el("span", `mkt-status mkt-status--${ok ? "ok" : source?.status === "nao_configurado" ? "off" : "warn"}`);
    chip.append(el("span", "mkt-status__dot"), `${label}: ${ok ? "conectado" : source?.status === "nao_configurado" ? "não configurado" : "indisponível"}`);
    if (!ok && source?.mensagem) chip.title = source.mensagem;
    return chip;
}

// ---------- Render ----------

function render() {
    const root = byId("marketing-content");
    const data = state.data;
    if (!root || !data) return;
    const ga = data.google_analytics || {};
    const cf = data.cloudflare || {};
    const site = data.site || {};
    const gaOk = ga.status === "ok";
    const cfOk = cf.status === "ok";
    const siteOk = site.status === "ok";
    root.replaceChildren();

    const bar = el("div", "mkt-sources");
    bar.append(status(ga, "Google Analytics"), status(cf, "Cloudflare"), status(site, "Dados do site"));
    bar.append(el("span", "mkt-updated", `Atualizado ${new Date(data.atualizado_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`));
    root.append(bar);

    // Headline numbers.
    const tiles = el("div", "mkt-tiles");
    const leads = siteOk ? site.leads.total : 0;
    if (gaOk) {
        const t = ga.totais;
        const a = ga.anterior;
        tiles.append(
            tile("Visitantes", numero(t.activeUsers), { delta: variacao(t.activeUsers, a.activeUsers), hint: `${numero(t.newUsers)} novos`, fonte: "Google Analytics" }),
            tile("Agora no site", ga.agora_no_site === null ? "—" : numero(ga.agora_no_site), { hint: "últimos 30 minutos", fonte: "Google Analytics" }),
            tile("Sessões", numero(t.sessions), { delta: variacao(t.sessions, a.sessions), hint: `duração média ${duracao(t.averageSessionDuration)}`, fonte: "Google Analytics" }),
            tile("Páginas vistas", numero(t.screenPageViews), { delta: variacao(t.screenPageViews, a.screenPageViews), hint: `engajamento ${pct(t.engagementRate)}`, fonte: "Google Analytics" }),
        );
    } else if (cfOk) {
        tiles.append(
            tile("Visitantes (soma diária)", numero(cf.totais.visitantes), { hint: "IPs únicos por dia", fonte: "Cloudflare" }),
            tile("Páginas vistas", numero(cf.totais.paginas), { fonte: "Cloudflare" }),
        );
    }
    if (siteOk) {
        tiles.append(
            tile("Pedidos de orçamento", numero(leads), { delta: variacao(leads, site.leads.anterior), fonte: "Site" }),
            tile("Conversão em pedido", gaOk && ga.totais.sessions ? pct(leads / ga.totais.sessions) : "—",
                { hint: gaOk ? "pedidos ÷ sessões" : "precisa do Google Analytics", fonte: "Site + GA" }),
            tile("Receita confirmada", moeda(site.receita_confirmada), { hint: `${numero(site.funil[3]?.quantidade)} pagamentos`, fonte: "Site" }),
        );
    }
    root.append(tiles);

    if (!gaOk && ga.status === "nao_configurado") root.append(setupCard(ga));
    else if (!gaOk && ga.mensagem) root.append(el("p", "mkt-alert", ga.mensagem));

    const grid = el("div", "mkt-grid");
    // Visits over time: GA when connected, else Cloudflare.
    if (gaOk || cfOk) {
        const visits = panel("Visitantes por dia", { wide: true, fonte: gaOk ? "Google Analytics" : "Cloudflare" });
        visits.append(lineChart(gaOk ? ga.serie : cf.serie, { key: "visitantes", label: "Visitantes" }));
        grid.append(visits);
    }
    if (siteOk) {
        const leadsPanel = panel("Pedidos de orçamento por dia", { wide: true, fonte: "Site" });
        leadsPanel.append(lineChart(site.leads.serie, { key: "leads", label: "Pedidos", barras: true }));
        grid.append(leadsPanel);
    }
    if (gaOk) {
        const channels = panel("Canais", { subtitle: "De onde vêm as sessões, agrupado pelo Google.", fonte: "Google Analytics" });
        channels.append(barList(ga.canais, { valueKey: "sessoes", label: item => CANAIS[item.nome] || item.nome }));
        const sources = panel("Origem / mídia", { subtitle: "Site ou rede de origem e o tipo de tráfego.", fonte: "Google Analytics" });
        sources.append(barList(ga.origens, { valueKey: "sessoes", label: item => item.nome.replace("(direct) / (none)", "Direto") }));
        const campaigns = panel("Campanhas", { subtitle: "Links com utm_campaign.", fonte: "Google Analytics" });
        campaigns.append(barList(ga.campanhas.filter(item => !/^\((not set|direct|organic|referral)\)$/.test(item.nome)), { valueKey: "sessoes" }));
        const pages = panel("Páginas mais vistas", { fonte: "Google Analytics" });
        pages.append(barList(ga.paginas, { valueKey: "visualizacoes" }));
        const countries = panel("Países", { fonte: "Google Analytics" });
        countries.append(barList(ga.paises, { valueKey: "visitantes" }));
        const cities = panel("Cidades", { fonte: "Google Analytics" });
        cities.append(barList(ga.cidades.filter(item => item.nome !== "(not set)"), { valueKey: "visitantes" }));
        const devices = panel("Dispositivos", { fonte: "Google Analytics" });
        devices.append(barList(ga.dispositivos, { valueKey: "visitantes", label: item => DISPOSITIVOS[item.nome] || item.nome }));
        const events = panel("O que as pessoas fazem no site", { subtitle: "Eventos registrados com consentimento.", fonte: "Google Analytics" });
        events.append(barList(ga.eventos.filter(item => item.quantidade), { label: item => EVENTOS[item.nome] || item.nome }));
        grid.append(channels, sources, campaigns, pages, countries, cities, devices, events);
    } else if (cfOk) {
        const countries = panel("Países (requisições)", { fonte: "Cloudflare" });
        countries.append(barList(cf.paises, { valueKey: "requisicoes" }));
        grid.append(countries);
    }
    if (siteOk) {
        const origin = panel("Pedidos por origem", {
            subtitle: `Campanha ou site de onde veio a visita que virou pedido. ${numero(site.leads.com_origem)} de ${numero(leads)} com origem registrada.`,
            fonte: "Site",
        });
        origin.append(barList(site.leads.por_origem));
        const services = panel("Pedidos por serviço", { fonte: "Site" });
        services.append(barList(site.leads.por_servico));
        const landing = panel("Páginas de entrada dos pedidos", { fonte: "Site" });
        landing.append(barList(site.leads.paginas_de_entrada));
        const leadCampaigns = panel("Campanhas que geraram pedidos", { fonte: "Site" });
        leadCampaigns.append(barList(site.leads.por_campanha));
        const funnelPanel = panel("Funil comercial", { subtitle: "No período escolhido.", fonte: "Site", wide: true });
        funnelPanel.append(funnel(site.funil));
        const newsletter = panel("Newsletter", { subtitle: `${numero(site.newsletter.novos)} inscrições no período · ${numero(site.newsletter.ativos)} ativas no total.`, fonte: "Site" });
        newsletter.append(barList(site.newsletter.por_origem));
        const chat = panel("Chat com a IA", { subtitle: `${numero(site.chat.conversas)} conversas · ${numero(site.chat.encaminhadas)} passadas para a equipe.`, fonte: "Site" });
        chat.append(barList(site.chat.por_canal));
        const beats = panel("Licenças de beats", { subtitle: `${numero(site.beats.licencas)} pedidos de licença no período.`, fonte: "Site" });
        beats.append(barList(site.beats.por_status, { label: item => LICENCAS[item.nome] || item.nome }));
        grid.append(origin, services, landing, leadCampaigns, funnelPanel, newsletter, chat, beats);
    } else if (site.mensagem) {
        root.append(el("p", "mkt-alert", site.mensagem));
    }
    root.append(grid);
    root.querySelectorAll("[data-mkt-dias]").forEach(button => button.setAttribute("aria-pressed", String(Number(button.dataset.mktDias) === state.dias)));
}

async function load({ atualizar = false } = {}) {
    const root = byId("marketing-content");
    if (!root) return;
    if (state.loading) return state.loading;
    if (!state.data) root.replaceChildren(el("p", "mkt-empty", "Carregando dados de marketing…"));
    root.setAttribute("aria-busy", "true");
    state.loading = (async () => {
        const response = await authFetch(`/admin/marketing?dias=${state.dias}${atualizar ? "&atualizar=true" : ""}`);
        const body = await response.json().catch(() => null);
        if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Não foi possível carregar o marketing.");
        state.data = body;
    })();
    try {
        await state.loading;
        render();
    } catch (error) {
        root.replaceChildren(el("p", "mkt-alert", error.message));
    } finally {
        state.loading = null;
        root.removeAttribute("aria-busy");
    }
}

export async function initMarketing() {
    if (!state.bound) {
        state.bound = true;
        const periods = byId("marketing-periodos");
        PERIODOS.forEach(([value, label]) => {
            const button = el("button", "mkt-period", label);
            button.type = "button";
            button.dataset.mktDias = String(value);
            button.setAttribute("aria-pressed", String(value === state.dias));
            button.addEventListener("click", () => {
                if (state.dias === value) return;
                state.dias = value;
                state.data = null;
                periods.querySelectorAll("button").forEach(item => item.setAttribute("aria-pressed", String(item === button)));
                load();
            });
            periods?.append(button);
        });
        byId("marketing-atualizar")?.addEventListener("click", () => load({ atualizar: true }));
        const exportFeedback = byId("marketing-exportar-status");
        const ready = () => {
            const menu = document.querySelector("#section-marketing .mkt-export");
            if (menu) menu.open = false;
            if (state.data) return true;
            if (exportFeedback) exportFeedback.textContent = "Aguarde os dados carregarem para exportar.";
            return false;
        };
        byId("marketing-exportar-pdf")?.addEventListener("click", () => {
            if (!ready()) return;
            try {
                abrirRelatorio(state.data);
                if (exportFeedback) exportFeedback.textContent = "Relatório aberto em outra aba: use \"Salvar como PDF\".";
            } catch (error) {
                if (exportFeedback) exportFeedback.textContent = error.message;
            }
        });
        byId("marketing-exportar-csv")?.addEventListener("click", () => {
            if (!ready()) return;
            baixarCsv(state.data);
            if (exportFeedback) exportFeedback.textContent = "Planilha baixada.";
        });
    }
    await load();
}

document.addEventListener("admin:logout", () => {
    state.data = null;
    byId("marketing-content")?.replaceChildren();
});
