// Licenses across every plugin: search by key, name or e-mail; revoke and reactivate.
import { api } from "../api.js";
import { LICENCA, ORIGEM, busy, cell, confirm, copy, datetime, el, field, input, licenseChip, money, pageHead, select, table, toast } from "../ui.js";

export async function render({ query }) {
    const q = query.get("q") || "";
    const status = query.get("status") || "";
    const origem = query.get("origem") || "";
    const plugin = query.get("plugin") || "";
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (status) params.set("status", status);
    if (origem) params.set("origem", origem);
    if (plugin) params.set("plugin_id", plugin);
    const [rows, plugins] = await Promise.all([api(`/admin/labs/licencas?${params}`), api("/admin/labs/plugins")]);

    const search = input("q", q, { type: "search", placeholder: "Chave MHL-..., nome ou e-mail", maxLength: 120 });
    const pluginSelect = select("plugin", { "": "Todos os plugins", ...Object.fromEntries(plugins.map(item => [item.id, item.nome])) }, plugin);
    const statusSelect = select("status", { "": "Todas as situações", ...Object.fromEntries(Object.entries(LICENCA).map(([key, [label]]) => [key, label])) }, status);
    const originSelect = select("origem", { "": "Todas as origens", ...ORIGEM }, origem);
    const form = el("form", { class: "filters", role: "search" }, field("Buscar", search), field("Plugin", pluginSelect),
        field("Situação", statusSelect), field("Origem", originSelect),
        el("button", { class: "btn btn--ghost btn--small", type: "submit", text: "Filtrar" }));
    form.querySelector(".field").classList.add("field--grow");
    const apply = () => {
        const next = new URLSearchParams();
        if (search.value.trim()) next.set("q", search.value.trim());
        if (pluginSelect.value) next.set("plugin", pluginSelect.value);
        if (statusSelect.value) next.set("status", statusSelect.value);
        if (originSelect.value) next.set("origem", originSelect.value);
        window.location.hash = `#/licencas${next.toString() ? `?${next}` : ""}`;
    };
    form.addEventListener("submit", event => { event.preventDefault(); apply(); });
    [pluginSelect, statusSelect, originSelect].forEach(node => node.addEventListener("change", apply));
    const reload = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

    const lines = rows.map(row => {
        const actions = el("div", { class: "actions" });
        if (row.status === "ativa") {
            actions.append(el("button", { class: "link-button", type: "button", text: "Copiar chave", onclick: () => copy(row.chave) }));
        }
        if (["ativa", "reservada"].includes(row.status)) {
            actions.append(el("button", { class: "link-button", type: "button", text: "Revogar", onclick: async event => {
                const ok = await confirm({ title: `Revogar a licença de ${row.cliente}?`, button: "Revogar", danger: true,
                    lines: [`${row.plugin}: o cliente deixa de baixar e a chave para de ativar.`, "Isso não devolve dinheiro; reembolso é em Pedidos."],
                    reason: { label: "Motivo (fica no histórico)", max: 40 } });
                if (!ok) return;
                await busy(event.currentTarget, async () => {
                    await api(`/admin/labs/licencas/${row.id}/revogar`, { method: "POST", body: { motivo: ok.motivo } });
                    toast("Licença revogada.");
                    reload();
                });
            } }));
        }
        if (row.status === "revogada") {
            actions.append(el("button", { class: "link-button", type: "button", text: "Reativar", onclick: async event => {
                const ok = await confirm({ title: `Reativar a licença de ${row.cliente}?`, button: "Reativar",
                    lines: [`${row.plugin}: a mesma chave volta a ativar e o download volta em My plugins.`] });
                if (!ok) return;
                await busy(event.currentTarget, async () => {
                    await api(`/admin/labs/licencas/${row.id}/reativar`, { method: "POST" });
                    toast("Licença reativada.");
                    reload();
                });
            } }));
        }
        return el("tr", {},
            cell([el("strong", { text: row.plugin })]),
            cell([el("a", { class: "row-link", href: `#/clientes/${row.cliente_id}`, text: row.cliente }), el("small", { text: row.email || "" })]),
            cell(ORIGEM[row.origem] || row.origem), cell([licenseChip(row), row.motivo && row.motivo !== "pagamento_revertido" && row.motivo !== "checkout_expirado" ? el("small", { text: row.motivo }) : null]),
            cell(row.chave, "mono nowrap"),
            cell(row.origem === "compra" || row.origem === "stripe" ? money(row.valor, row.moeda) : "—", "num"),
            cell([datetime(row.ativada_em || row.criada_em), row.encerrada_em ? el("small", { text: `encerrada ${datetime(row.encerrada_em)}` }) : null], "nowrap"),
            cell(actions));
    });
    return el("div", {},
        pageHead("Licenças", { lead: "Cada compra, presente ou plugin grátis gera uma licença com chave. A busca pela chave inteira encontra uma licença na hora." }),
        form,
        el("section", { class: "card" }, el("h2", { class: "card__title", text: `${rows.length} licença${rows.length === 1 ? "" : "s"}${rows.length >= 300 ? " (as 300 mais recentes)" : ""}` }),
            table(["Plugin", "Cliente", "Origem", "Situação", "Chave", ["Valor", "num"], "Data", ""], lines, "Nenhuma licença encontrada.")));
}
