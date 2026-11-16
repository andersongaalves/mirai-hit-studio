// Customers: Labs accounts and studio clients who have plugin licenses.
import { api } from "../api.js";
import { ORIGEM, PEDIDO, cell, chip, date, datetime, el, field, input, licenseChip, money, pageHead, table } from "../ui.js";

const CONTA = { labs: ["Conta da Labs", "ink"], estudio: ["Cliente do estúdio", "plain"], sem_conta: ["Sem login", ""] };

function accountChip(conta) {
    const [label, tone] = CONTA[conta.tipo] || [conta.tipo, ""];
    return chip(label, tone);
}

async function list(query) {
    const q = query.get("q") || "";
    const rows = await api(`/admin/labs/clientes${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    const search = input("q", q, { type: "search", placeholder: "Nome ou e-mail", maxLength: 120 });
    const form = el("form", { class: "filters", role: "search" }, field("Buscar", search),
        el("button", { class: "btn btn--ghost btn--small", type: "submit", text: "Buscar" }));
    form.querySelector(".field").classList.add("field--grow");
    form.addEventListener("submit", event => {
        event.preventDefault();
        const term = search.value.trim();
        window.location.hash = `#/clientes${term ? `?q=${encodeURIComponent(term)}` : ""}`;
    });
    const lines = rows.map(row => el("tr", {},
        cell([el("a", { class: "row-link", href: `#/clientes/${row.id}`, text: row.nome }), el("small", { text: row.email || "" })]),
        cell([accountChip(row.conta), row.teste ? chip("Teste") : null]),
        cell(String(row.licencas_ativas), "num"), cell(money(row.total_brl), "num"), cell(money(row.total_usd, "usd"), "num"),
        cell(date(row.conta.criada_em || row.criado_em), "nowrap")));
    return el("div", {},
        pageHead("Clientes", { lead: "Quem tem conta na Labs ou alguma licença de plugin. Contas da Labs entram só na loja; clientes do estúdio usam o mesmo login nos dois sites." }),
        form,
        el("section", { class: "card" }, el("h2", { class: "card__title", text: `${rows.length} cliente${rows.length === 1 ? "" : "s"}` }),
            table(["Cliente", "Conta", ["Licenças ativas", "num"], ["Comprou (BRL)", "num"], ["Comprou (USD)", "num"], "Desde"], lines,
                "Nenhum cliente encontrado.")));
}

async function detail(id) {
    const client = await api(`/admin/labs/clientes/${encodeURIComponent(id)}`);
    const account = client.conta;
    const info = el("dl", { class: "kv" },
        el("dt", { text: "E-mail" }), el("dd", { text: client.email || "—" }),
        el("dt", { text: "Telefone" }), el("dd", { text: client.telefone || "—" }),
        el("dt", { text: "Conta" }), el("dd", {}, accountChip(account)),
        el("dt", { text: "Usuário" }), el("dd", { text: account.usuario || "—" }),
        el("dt", { text: "Login ativo" }), el("dd", { text: account.tipo === "sem_conta" ? "—" : account.ativo ? "Sim" : "Não" }),
        el("dt", { text: "Cliente desde" }), el("dd", { text: date(client.criado_em) }));
    const licenses = client.licencas.map(row => el("tr", {},
        cell(el("a", { class: "row-link", href: `#/plugins/${row.plugin_id}?aba=licencas`, text: row.plugin })),
        cell(ORIGEM[row.origem] || row.origem), cell(licenseChip(row)),
        cell(row.status === "ativa" ? row.chave : "—", "mono nowrap"), cell(datetime(row.ativada_em || row.criada_em), "nowrap")));
    const orders = client.pedidos.map(row => {
        const [label, tone] = PEDIDO[row.status] || [row.status, ""];
        return el("tr", {}, cell(row.plugin), cell(chip(label, tone)), cell(money(row.valor, row.moeda), "num"),
            cell(row.cupom ? row.cupom.codigo : "—", "mono"), cell(datetime(row.criado_em), "nowrap"));
    });
    return el("div", {},
        pageHead(client.nome, { crumb: el("p", { class: "crumb" }, el("a", { href: "#/clientes", text: "Clientes" })),
            actions: client.teste ? [chip("Cliente de teste")] : [] }),
        el("div", { class: "two-col" },
            el("section", { class: "card" }, el("h2", { class: "card__title", text: `Licenças (${client.licencas.length})` }),
                table(["Plugin", "Origem", "Situação", "Chave", "Data"], licenses, "Nenhuma licença.")),
            el("section", { class: "card" }, el("h2", { class: "card__title", text: "Dados" }), info,
                el("p", { class: "muted small flush", text: "Senha, bloqueio de login e dados cadastrais ficam no Admin do estúdio (Usuários e Clientes)." }))),
        el("section", { class: "card" }, el("h2", { class: "card__title", text: `Pedidos (${client.pedidos.length})` }),
            table(["Plugin", "Situação", ["Valor", "num"], "Cupom", "Data"], orders, "Nenhum pedido.")));
}

export async function render({ params, query }) {
    return params[0] ? detail(params[0]) : list(query);
}
