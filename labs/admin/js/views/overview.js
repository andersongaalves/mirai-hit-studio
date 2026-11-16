import { api } from "../api.js";
import { PLUGIN_STATUS, cell, chip, datetime, el, money, pageHead, plural, select, table } from "../ui.js";

const SVG = "http://www.w3.org/2000/svg";
const svg = (tag, attrs = {}) => {
    const node = document.createElementNS(SVG, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
};

function tile(label, value, sub = "") {
    return el("div", { class: "tile" }, el("span", { class: "tile__label", text: label }),
        el("strong", { class: "tile__value", text: value }), sub ? el("span", { class: "tile__sub", text: sub }) : null);
}

// Licenses activated per day: paid (ink) stacked under free/courtesy (gray), 2px gap.
function chart(series) {
    const width = 720, height = 180, top = 4, bottom = 0;
    const max = Math.max(1, ...series.map(day => day.vendas + day.gratis));
    const step = Math.max(1, Math.ceil(max / 4));
    const ceiling = step * 4;
    const plot = height - top - bottom;
    const slot = width / series.length;
    const barWidth = Math.max(2, Math.min(18, slot - 3));
    const y = value => top + plot - (value / ceiling) * plot;
    const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, preserveAspectRatio: "none", role: "img",
        "aria-label": "Licenças ativadas por dia" });
    for (let tick = 0; tick <= ceiling; tick += step) {
        root.append(svg("line", { class: "grid", x1: 0, x2: width, y1: y(tick), y2: y(tick) }));
    }
    const wrap = el("div", { class: "chart" });
    const tip = el("div", { class: "chart__tip", hidden: true });
    const rounded = (x, top0, w, h, r) => {
        const radius = Math.min(r, h, w / 2);
        return `M${x},${top0 + h}V${top0 + radius}Q${x},${top0} ${x + radius},${top0}H${x + w - radius}Q${x + w},${top0} ${x + w},${top0 + radius}V${top0 + h}Z`;
    };
    series.forEach((day, index) => {
        const x = index * slot + (slot - barWidth) / 2;
        const label = new Date(`${day.dia}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
        const hit = svg("rect", { class: "hit", x: index * slot, y: top, width: slot, height: plot, tabindex: 0,
            "aria-label": `${label}: ${day.vendas} vendas, ${day.gratis} grátis ou cortesia` });
        root.append(hit);
        const total = day.vendas + day.gratis;
        if (total) {
            const paidTop = y(day.vendas);
            if (day.vendas) {
                const path = day.gratis ? svg("rect", { class: "bar", x, y: paidTop, width: barWidth, height: y(0) - paidTop })
                    : svg("path", { class: "bar", d: rounded(x, paidTop, barWidth, y(0) - paidTop, 4) });
                root.append(path);
            }
            if (day.gratis) {
                const freeTop = y(total);
                const freeHeight = Math.max(1, paidTop - freeTop - (day.vendas ? 2 : 0));
                root.append(svg("path", { class: "bar bar--free", d: rounded(x, freeTop, barWidth, freeHeight, 4) }));
            }
        }
        const show = () => {
            tip.replaceChildren(el("strong", { text: label }), el("br"),
                `${plural(day.vendas, "venda", "vendas")} · ${day.gratis} grátis/cortesia`);
            tip.hidden = false;
            tip.style.left = `${((index + 0.5) / series.length) * 100}%`;
            tip.style.top = `${(y(total) / height) * 100}%`;
        };
        hit.addEventListener("mouseenter", show);
        hit.addEventListener("focus", show);
        hit.addEventListener("mouseleave", () => { tip.hidden = true; });
        hit.addEventListener("blur", () => { tip.hidden = true; });
    });
    // Axis labels in HTML: the SVG stretches to the card width and would distort text.
    const dayLabel = index => new Date(`${series[index].dia}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
    const axis = el("div", { class: "chart__axis" },
        el("span", { text: dayLabel(0) }), el("span", { text: dayLabel(Math.floor(series.length / 2)) }),
        el("span", { text: dayLabel(series.length - 1) }));
    wrap.append(el("span", { class: "chart__max", text: `máx. ${ceiling}/dia` }), root, tip, axis);
    return wrap;
}

export async function render({ query, rerender }) {
    const days = Number(query.get("dias")) || 30;
    const data = await api(`/admin/labs/resumo?dias=${days}`);
    const period = select("dias", { 7: "Últimos 7 dias", 30: "Últimos 30 dias", 90: "Últimos 90 dias", 365: "Último ano" }, String(days));
    period.addEventListener("change", () => { window.location.hash = `#/visao-geral?dias=${period.value}`; });
    const root = el("div", {}, pageHead("Visão geral", {
        lead: "Vendas, licenças e downloads da loja. Clientes de teste ficam fora dos totais.",
        actions: [el("label", { class: "field" }, el("span", { class: "sr-only", text: "Período" }), period)],
    }));
    const r = data.receita;
    root.append(el("div", { class: "tiles" },
        tile("Receita BRL", money(r.periodo.brl), `Total: ${money(r.total.brl)}`),
        tile("Receita USD", money(r.periodo.usd, "usd"), `Total: ${money(r.total.usd, "usd")}`),
        tile("Vendas", String(data.vendas_periodo), `${data.gratis_periodo} grátis ou cortesia`),
        tile("Downloads", String(data.downloads_periodo), "instaladores baixados"),
        tile("Licenças ativas", String(data.licencas.ativas), `${data.licencas.aguardando_pagamento} aguardando pagamento`),
        tile("Contas da Labs", String(data.contas_labs.total), `${data.contas_labs.novas_periodo} novas no período`),
    ));
    const chartCard = el("section", { class: "card" },
        el("div", { class: "card__head" }, el("h2", { class: "card__title", text: "Licenças ativadas por dia" }),
            el("div", { class: "legend" }, el("span", { text: "Vendas" }), el("span", { class: "legend--free", text: "Grátis e cortesia" }))),
        chart(data.serie));
    const recent = el("section", { class: "card" }, el("h2", { class: "card__title", text: "Últimas licenças" }),
        data.ultimas_licencas.length
            ? el("div", { class: "stack" }, ...data.ultimas_licencas.map(item => el("div", {},
                el("strong", { text: item.plugin }), " · ", item.cliente,
                el("div", { class: "muted small", text: `${datetime(item.ativada_em)} · ${item.origem === "compra" || item.origem === "stripe" ? money(item.valor, item.moeda) : item.origem}` }))))
            : el("p", { class: "muted flush", text: "Nenhuma licença ainda." }));
    root.append(el("div", { class: "two-col" }, chartCard, recent));
    const rows = data.plugins.map(plugin => {
        const [label, tone] = PLUGIN_STATUS[plugin.status] || [plugin.status, ""];
        return el("tr", {},
            cell(el("a", { class: "row-link", href: `#/plugins/${plugin.id}`, text: plugin.nome })),
            cell(chip(label, tone)), cell(plugin.versao ? `v${plugin.versao}` : "—", "mono"),
            cell(String(plugin.licencas_ativas), "num"), cell(money(plugin.receita_brl), "num"),
            cell(money(plugin.receita_usd, "usd"), "num"), cell(String(plugin.downloads_periodo), "num"));
    });
    root.append(el("section", { class: "card" }, el("h2", { class: "card__title", text: "Por plugin" }),
        table(["Plugin", "Situação", "Versão", ["Licenças", "num"], ["Receita BRL", "num"], ["Receita USD", "num"], ["Downloads", "num"]],
            rows, "Nenhum plugin cadastrado.")));
    void rerender;
    return root;
}
