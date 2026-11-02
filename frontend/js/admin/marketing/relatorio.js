// Marketing report: an automatic summary (highlights written from the numbers) plus every
// table, as a printable page (save as PDF) or a spreadsheet (CSV, opens in Excel/Sheets).

const numero = value => Number(value || 0).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
const moeda = value => Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const pct = value => `${(Number(value || 0) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const CANAIS = {
    Direct: "Direto", "Organic Search": "Busca orgânica", "Organic Social": "Redes sociais", Referral: "Outros sites",
    "Paid Search": "Busca paga", "Paid Social": "Redes sociais pagas", Email: "E-mail", Unassigned: "Não classificado",
};
const DISPOSITIVOS = { mobile: "Celular", desktop: "Computador", tablet: "Tablet" };

function mudanca(atual, anterior) {
    if (!anterior) return "";
    const change = (atual - anterior) / anterior;
    if (Math.abs(change) < 0.01) return " (estável em relação ao período anterior)";
    return ` (${change > 0 ? "alta" : "queda"} de ${pct(Math.abs(change))} em relação ao período anterior)`;
}

function topo(items, key, rename = {}) {
    const first = (items || []).filter(item => !/^\(not set\)$/.test(item.nome))[0];
    return first ? { nome: rename[first.nome] || first.nome, valor: first[key] } : null;
}

// Highlights in plain Portuguese, computed from the numbers (no guessing).
export function destaques(data) {
    const lines = [];
    const ga = data.google_analytics?.status === "ok" ? data.google_analytics : null;
    const cf = data.cloudflare?.status === "ok" ? data.cloudflare : null;
    const site = data.site?.status === "ok" ? data.site : null;
    if (ga) {
        lines.push(`${numero(ga.totais.activeUsers)} visitantes e ${numero(ga.totais.sessions)} sessões${mudanca(ga.totais.activeUsers, ga.anterior.activeUsers)}.`);
        const canal = topo(ga.canais, "sessoes", CANAIS);
        const total = (ga.canais || []).reduce((sum, item) => sum + item.sessoes, 0);
        if (canal && total) lines.push(`Principal canal: ${canal.nome}, com ${pct(canal.valor / total)} das sessões.`);
        const origem = topo(ga.origens, "sessoes");
        if (origem) lines.push(`Origem que mais trouxe visitas: ${origem.nome.replace("(direct) / (none)", "acesso direto")} (${numero(origem.valor)} sessões).`);
        const pagina = topo(ga.paginas, "visualizacoes");
        if (pagina) lines.push(`Página mais vista: ${pagina.nome === "/" ? "página inicial (/)" : pagina.nome} (${numero(pagina.valor)} visualizações).`);
        const device = topo(ga.dispositivos, "visitantes", DISPOSITIVOS);
        const people = (ga.dispositivos || []).reduce((sum, item) => sum + item.visitantes, 0);
        if (device && people) lines.push(`${pct(device.valor / people)} das pessoas usaram ${device.nome.toLowerCase()}.`);
        const cidade = topo(ga.cidades, "visitantes");
        if (cidade) lines.push(`Cidade com mais visitantes: ${cidade.nome}.`);
    } else if (cf) {
        lines.push(`${numero(cf.totais.visitantes)} visitantes (soma diária, Cloudflare) e ${numero(cf.totais.paginas)} páginas vistas.`);
    }
    if (site) {
        lines.push(`${numero(site.leads.total)} pedidos de orçamento${mudanca(site.leads.total, site.leads.anterior)}.`);
        if (ga?.totais.sessions) lines.push(`Conversão de sessões em pedido: ${pct(site.leads.total / ga.totais.sessions)}.`);
        const origem = (site.leads.por_origem || []).find(item => !item.nome.startsWith("Sem informação"));
        if (origem) lines.push(`Origem que mais gerou pedidos: ${origem.nome} (${numero(origem.quantidade)}).`);
        const servico = site.leads.por_servico?.[0];
        if (servico) lines.push(`Serviço mais pedido: ${servico.nome} (${numero(servico.quantidade)}).`);
        const [pedidos, , aceitas, pagos] = site.funil.map(step => step.quantidade);
        if (pedidos) lines.push(`Funil: ${numero(aceitas)} propostas aceitas e ${numero(pagos)} pagamentos confirmados a partir de ${numero(pedidos)} pedidos.`);
        lines.push(`Receita confirmada no período: ${moeda(site.receita_confirmada)}.`);
        if (site.newsletter.novos) lines.push(`${numero(site.newsletter.novos)} novas inscrições na newsletter (${numero(site.newsletter.ativos)} ativas).`);
    }
    if (!ga) lines.push("Google Analytics não conectado: canais, campanhas e páginas não entram neste relatório.");
    return lines;
}

// Every table of the report: [title, column headers, rows].
export function tabelas(data) {
    const ga = data.google_analytics?.status === "ok" ? data.google_analytics : null;
    const cf = data.cloudflare?.status === "ok" ? data.cloudflare : null;
    const site = data.site?.status === "ok" ? data.site : null;
    const out = [];
    if (ga) {
        const t = ga.totais;
        const a = ga.anterior;
        out.push(["Resumo (Google Analytics)", ["Métrica", "Período", "Período anterior"], [
            ["Visitantes", t.activeUsers, a.activeUsers], ["Novos visitantes", t.newUsers, a.newUsers],
            ["Sessões", t.sessions, a.sessions], ["Páginas vistas", t.screenPageViews, a.screenPageViews],
            ["Taxa de engajamento", pct(t.engagementRate), pct(a.engagementRate)],
            ["Duração média da sessão (s)", Math.round(t.averageSessionDuration), Math.round(a.averageSessionDuration)],
        ]]);
        out.push(["Visitantes por dia", ["Dia", "Visitantes", "Sessões"], ga.serie.map(item => [item.data, item.visitantes, item.sessoes])]);
        out.push(["Canais", ["Canal", "Sessões", "Visitantes"], ga.canais.map(item => [CANAIS[item.nome] || item.nome, item.sessoes, item.visitantes])]);
        out.push(["Origem / mídia", ["Origem", "Sessões", "Visitantes"], ga.origens.map(item => [item.nome, item.sessoes, item.visitantes])]);
        out.push(["Campanhas", ["Campanha", "Sessões", "Visitantes"], ga.campanhas.map(item => [item.nome, item.sessoes, item.visitantes])]);
        out.push(["Páginas mais vistas", ["Página", "Visualizações", "Visitantes"], ga.paginas.map(item => [item.nome, item.visualizacoes, item.visitantes])]);
        out.push(["Países", ["País", "Visitantes"], ga.paises.map(item => [item.nome, item.visitantes])]);
        out.push(["Cidades", ["Cidade", "Visitantes"], ga.cidades.map(item => [item.nome, item.visitantes])]);
        out.push(["Dispositivos", ["Dispositivo", "Visitantes"], ga.dispositivos.map(item => [DISPOSITIVOS[item.nome] || item.nome, item.visitantes])]);
        out.push(["Eventos do site", ["Evento", "Quantidade"], ga.eventos.map(item => [item.nome, item.quantidade])]);
    }
    if (cf) {
        out.push(["Tráfego (Cloudflare)", ["Dia", "Visitantes", "Páginas", "Requisições"],
            cf.serie.map(item => [item.data, item.visitantes, item.paginas, item.requisicoes])]);
        out.push(["Países (Cloudflare)", ["País", "Requisições"], cf.paises.map(item => [item.nome, item.requisicoes])]);
    }
    if (site) {
        out.push(["Funil comercial", ["Etapa", "Quantidade"], site.funil.map(item => [item.etapa, item.quantidade])]);
        out.push(["Pedidos por dia", ["Dia", "Pedidos"], site.leads.serie.map(item => [item.data, item.leads])]);
        out.push(["Pedidos por origem", ["Origem", "Pedidos"], site.leads.por_origem.map(item => [item.nome, item.quantidade])]);
        out.push(["Pedidos por serviço", ["Serviço", "Pedidos"], site.leads.por_servico.map(item => [item.nome, item.quantidade])]);
        out.push(["Campanhas que geraram pedidos", ["Campanha", "Pedidos"], site.leads.por_campanha.map(item => [item.nome, item.quantidade])]);
        out.push(["Páginas de entrada dos pedidos", ["Página", "Pedidos"], site.leads.paginas_de_entrada.map(item => [item.nome, item.quantidade])]);
        out.push(["Newsletter por origem", ["Origem", "Inscrições"], site.newsletter.por_origem.map(item => [item.nome, item.quantidade])]);
        out.push(["Chat com a IA", ["Canal", "Conversas"], site.chat.por_canal.map(item => [item.nome, item.quantidade])]);
        out.push(["Licenças de beats", ["Situação", "Pedidos"], site.beats.por_status.map(item => [item.nome, item.quantidade])]);
    }
    return out;
}

const periodo = data => `Últimos ${data.dias} dias · gerado em ${new Date().toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`;

function csvCell(value) {
    const text = String(value ?? "");
    // Neutralize spreadsheet formulas; quote separators, quotes and line breaks.
    const safe = /^[=+\-@\t\r]/.test(text) && !/^-?\d+([.,]\d+)?$/.test(text) ? `'${text}` : text;
    return /[;"\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

export function csv(data) {
    const lines = [["Relatório de marketing · Mirai Hit Studio"], [periodo(data)], [], ["Destaques"],
        ...destaques(data).map(line => [line]), []];
    for (const [title, headers, rows] of tabelas(data)) {
        lines.push([title], headers, ...rows, []);
    }
    // Semicolons and a BOM so Excel in Portuguese opens the columns and accents correctly.
    return "﻿" + lines.map(row => row.map(csvCell).join(";")).join("\r\n");
}

export function baixarCsv(data) {
    const blob = new Blob([csv(data)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `marketing-mirai-${new Date().toISOString().slice(0, 10)}-${data.dias}dias.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
}

// Printable page built with DOM APIs (no HTML strings from data): the browser saves it as PDF.
export function documentoRelatorio(doc, data) {
    doc.title = `Relatório de marketing · ${data.dias} dias`;
    const style = doc.createElement("style");
    style.textContent = `
        @page { size: A4; margin: 16mm; }
        * { box-sizing: border-box; }
        body { margin: 0; padding: 24px; color: #111827; background: #fff; font: 13px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
        header { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; border-bottom: 2px solid #0e7490; padding-bottom: 10px; }
        h1 { margin: 0; font-size: 22px; }
        h2 { margin: 22px 0 8px; font-size: 15px; color: #0e7490; break-after: avoid; }
        .periodo { color: #4b5563; font-size: 12px; }
        ul.destaques { margin: 12px 0 0; padding-left: 18px; }
        ul.destaques li { margin: 4px 0; }
        table { width: 100%; border-collapse: collapse; break-inside: avoid; font-variant-numeric: tabular-nums; }
        th, td { padding: 5px 8px; border-bottom: 1px solid #e5e7eb; text-align: left; vertical-align: top; }
        th { background: #f3f4f6; font-weight: 600; }
        td + td, th + th { text-align: right; }
        .acoes { margin: 16px 0; }
        .acoes button { padding: 8px 14px; border: 1px solid #0e7490; border-radius: 6px; background: #0e7490; color: #fff; font: inherit; cursor: pointer; }
        footer { margin-top: 24px; color: #6b7280; font-size: 11px; }
        @media print { .acoes { display: none; } body { padding: 0; } }
    `;
    doc.head.append(style);
    const body = doc.body;
    body.replaceChildren();
    const make = (tag, text, className) => {
        const node = doc.createElement(tag);
        if (text !== undefined) node.textContent = String(text);
        if (className) node.className = className;
        return node;
    };
    const header = make("header");
    const titles = make("div");
    titles.append(make("h1", "Relatório de marketing"), make("div", "Mirai Hit Studio", "periodo"));
    header.append(titles, make("div", periodo(data), "periodo"));
    body.append(header);
    const actions = make("div", undefined, "acoes");
    const print = make("button", "Salvar como PDF / imprimir");
    print.type = "button";
    print.addEventListener("click", () => doc.defaultView.print());
    actions.append(print);
    body.append(actions);
    body.append(make("h2", "Destaques"));
    const list = make("ul", undefined, "destaques");
    destaques(data).forEach(line => list.append(make("li", line)));
    body.append(list);
    for (const [title, headers, rows] of tabelas(data)) {
        if (!rows.length) continue;
        body.append(make("h2", title));
        const table = make("table");
        const head = make("tr");
        headers.forEach(name => head.append(make("th", name)));
        table.append(head);
        rows.forEach(row => {
            const tr = make("tr");
            row.forEach(cell => tr.append(make("td", typeof cell === "number" ? numero(cell) : cell)));
            table.append(tr);
        });
        body.append(table);
    }
    body.append(make("footer", "Fontes: Google Analytics 4 (com consentimento dos visitantes), Cloudflare e registros do site. Números agregados, sem dados pessoais."));
}

export function abrirRelatorio(data) {
    const view = window.open("", "_blank");
    if (!view) throw new Error("O navegador bloqueou a janela do relatório. Permita pop-ups para este site.");
    view.opener = null;
    view.document.open();
    view.document.write("<!doctype html><html lang=\"pt-BR\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"></head><body></body></html>");
    view.document.close();
    documentoRelatorio(view.document, data);
    setTimeout(() => view.print(), 300);
    return view;
}
