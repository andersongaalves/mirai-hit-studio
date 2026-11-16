// Orders from both checkouts: studio checkout in BRL (Mercado Pago) and Stripe in USD.
import { api } from "../api.js";
import { PEDIDO, busy, cell, chip, confirm, datetime, el, field, input, money, pageHead, select, table, toast } from "../ui.js";

const STUDIO_ADMIN = "https://miraihitstudio.com.br/admin";

export async function render({ query }) {
    const q = query.get("q") || "";
    const moeda = query.get("moeda") || "";
    const status = query.get("status") || "";
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (moeda) params.set("moeda", moeda);
    if (status) params.set("status", status);
    const rows = await api(`/admin/labs/pedidos?${params}`);

    const search = input("q", q, { type: "search", placeholder: "Cliente, e-mail, plugin ou ID do Stripe", maxLength: 120 });
    const currency = select("moeda", { "": "Todas as moedas", brl: "BRL (checkout Mirai)", usd: "USD (Stripe)" }, moeda);
    const state = select("status", { "": "Todas as situações", ...Object.fromEntries(Object.entries(PEDIDO).map(([key, [label]]) => [key, label])) }, status);
    const filters = el("form", { class: "filters", role: "search" },
        field("Buscar", search), field("Moeda", currency), field("Situação", state),
        el("button", { class: "btn btn--ghost btn--small", type: "submit", text: "Filtrar" }));
    filters.querySelector(".field").classList.add("field--grow");
    const apply = () => {
        const next = new URLSearchParams();
        if (search.value.trim()) next.set("q", search.value.trim());
        if (currency.value) next.set("moeda", currency.value);
        if (state.value) next.set("status", state.value);
        window.location.hash = `#/pedidos${next.toString() ? `?${next}` : ""}`;
    };
    filters.addEventListener("submit", event => { event.preventDefault(); apply(); });
    currency.addEventListener("change", apply);
    state.addEventListener("change", apply);

    const lines = rows.map(row => {
        const [label, tone] = PEDIDO[row.status] || [row.status, ""];
        const actions = el("div", { class: "actions" });
        if (row.pode_reembolsar) {
            actions.append(el("button", { class: "btn btn--danger btn--small", type: "button", text: "Reembolsar",
                onclick: async event => {
                    const ok = await confirm({ title: `Reembolsar ${money(row.valor, "usd")} para ${row.cliente.nome}?`,
                        lines: ["O valor volta pelo Stripe e a licença é suspensa na hora.", "Não dá para desfazer."],
                        button: "Reembolsar", danger: true, reason: { label: "Motivo (fica no histórico)", max: 40 } });
                    if (!ok) return;
                    const button = event.currentTarget;
                    await busy(button, async () => {
                        await api(`/admin/labs/pedidos/stripe/${row.pedido_id}/reembolsar`, { method: "POST", body: { motivo: ok.motivo } });
                        toast("Reembolso feito.");
                        window.dispatchEvent(new HashChangeEvent("hashchange"));
                    });
                } }));
        } else if (row.moeda === "brl" && row.cobranca_id && row.status === "pago") {
            actions.append(el("a", { class: "link-button", href: STUDIO_ADMIN, target: "_blank", rel: "noopener",
                text: "Estorno no Admin do estúdio ↗" }));
        }
        return el("tr", {},
            cell([el("strong", { text: row.plugin }), el("small", { text: row.moeda === "usd" ? `Stripe #${row.pedido_id}` : `Proposta #${row.proposta_id}` })]),
            cell([el("a", { class: "row-link", href: `#/clientes/${row.cliente.id}`, text: row.cliente.nome }),
                el("small", { text: row.cliente.email || "" }), row.cliente.teste ? chip("Teste") : null]),
            cell(chip(label, tone)),
            cell([money(row.valor, row.moeda), row.cupom ? el("small", { text: `cupom ${row.cupom.codigo} (−${money(row.cupom.desconto, row.moeda)})` }) : null], "num"),
            cell([datetime(row.criado_em), row.pago_em ? el("small", { text: `pago ${datetime(row.pago_em)}` }) : null], "nowrap"),
            cell(actions));
    });
    const paid = rows.filter(row => row.status === "pago");
    const sum = currency => paid.filter(row => row.moeda === currency).reduce((total, row) => total + Number(row.valor), 0);
    return el("div", {},
        pageHead("Pedidos", { lead: "Compras pela loja em português (checkout da Mirai, BRL) e em inglês (Stripe, USD). Estornos em BRL são feitos no Financeiro do estúdio." }),
        filters,
        el("section", { class: "card" },
            el("div", { class: "card__head" }, el("h2", { class: "card__title", text: `${rows.length} pedido${rows.length === 1 ? "" : "s"}` }),
                el("span", { class: "muted small", text: `Pagos nesta lista: ${money(sum("brl"))} · ${money(sum("usd"), "usd")}` })),
            table(["Pedido", "Cliente", "Situação", ["Valor", "num"], "Data", ""], lines, "Nenhum pedido encontrado.")));
}
