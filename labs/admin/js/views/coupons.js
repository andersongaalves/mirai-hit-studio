// Discount coupons: percentage or fixed amount (same number in R$ and US$), per plugin or all.
import { api } from "../api.js";
import {
    busy, cell, checkbox, chip, confirm, date, dialog, el, field, fromLocalInput, input, money, pageHead, select,
    table, toLocalInput, toast,
} from "../ui.js";

const SITUACAO = { ativo: ["Ativo", "ok"], agendado: ["Agendado", "warn"], esgotado: ["Esgotado", ""], expirado: ["Expirado", ""], inativo: ["Inativo", "bad"] };
const reload = () => window.dispatchEvent(new HashChangeEvent("hashchange"));

function couponForm(coupon, plugins) {
    return dialog(coupon ? `Cupom ${coupon.codigo}` : "Novo cupom", close => {
        const form = el("form", { class: "dialog__form", novalidate: true });
        const code = input("codigo", coupon?.codigo || "", { required: true, minLength: 3, maxLength: 32, pattern: "[A-Za-z0-9][A-Za-z0-9_\\-]{2,31}",
            autocapitalize: "characters", spellcheck: false, placeholder: "BLACKFRIDAY30", disabled: Boolean(coupon?.usos_registrados) });
        code.addEventListener("input", () => { code.value = code.value.toUpperCase().replace(/\s+/g, ""); });
        const kind = select("tipo", { percentual: "Porcentagem (%)", valor: "Valor fixo" }, coupon?.tipo || "percentual");
        const value = input("valor", coupon?.valor || "", { type: "number", min: "0.01", step: "0.01", required: true });
        const hint = el("span", { class: "field__help" });
        const syncHint = () => {
            value.max = kind.value === "percentual" ? "100" : "99999.99";
            hint.textContent = kind.value === "percentual" ? "De 1 a 100. 100% libera o plugin sem pagamento."
                : "Mesmo número nas duas lojas (R$ e US$). Se cobrir o preço todo, o plugin sai sem pagamento.";
        };
        kind.addEventListener("change", syncHint);
        syncHint();
        const valueField = field("Desconto", value);
        valueField.append(hint);
        const plugin = select("plugin_id", { "": "Todos os plugins", ...Object.fromEntries(plugins.map(item => [item.id, item.nome])) }, coupon?.plugin_id ?? "");
        const from = input("valido_de", toLocalInput(coupon?.valido_de), { type: "datetime-local" });
        const until = input("valido_ate", toLocalInput(coupon?.valido_ate), { type: "datetime-local" });
        const max = input("max_usos", coupon?.max_usos ?? "", { type: "number", min: "1", step: "1", placeholder: "Sem limite" });
        const description = input("descricao", coupon?.descricao || "", { maxLength: 160, placeholder: "Só para você lembrar (não aparece na loja)" });
        const active = checkbox("ativo", coupon ? coupon.ativo : true, "Ativo");
        const status = el("p", { class: "form-status", role: "status" });
        const save = el("button", { class: "btn btn--small", type: "submit", text: coupon ? "Salvar" : "Criar cupom" });
        form.append(el("div", { class: "grid-form" },
            field("Código", code, { help: coupon?.usos_registrados ? "Já usado: o código não muda." : "Letras, números, - e _. O cliente digita sem diferença de maiúsculas." }),
            field("Tipo", kind), valueField, field("Vale para", plugin),
            field("Começa em", from, { help: "Vazio = já vale." }), field("Termina em", until, { help: "Vazio = sem prazo." }),
            field("Limite de usos", max, { help: "Cada conta usa uma vez." }), field("Observação", description, { full: true }),
            el("div", { class: "field field--full" }, active)),
            status,
            el("div", { class: "dialog__foot" }, el("button", { class: "btn btn--ghost btn--small", type: "button", text: "Cancelar", onclick: () => close(false) }), save));
        form.addEventListener("submit", event => {
            event.preventDefault();
            if (!form.reportValidity()) return;
            const body = {
                codigo: code.value.trim(), descricao: description.value.trim() || null, tipo: kind.value, valor: value.value,
                plugin_id: plugin.value ? Number(plugin.value) : null, valido_de: fromLocalInput(from.value),
                valido_ate: fromLocalInput(until.value), max_usos: max.value ? Number(max.value) : null, ativo: form.ativo.checked,
            };
            busy(save, async () => {
                if (coupon) await api(`/admin/labs/cupons/${coupon.id}`, { method: "PUT", body });
                else await api("/admin/labs/cupons", { method: "POST", body });
                toast(coupon ? "Cupom salvo." : `Cupom ${body.codigo} criado.`);
                close(true);
            }, status);
        });
        setTimeout(() => (coupon ? value : code).focus(), 0);
        return form;
    });
}

export async function render() {
    const [coupons, plugins] = await Promise.all([api("/admin/labs/cupons"), api("/admin/labs/plugins")]);
    const create = el("button", { class: "btn", type: "button", text: "Novo cupom",
        onclick: async () => { if (await couponForm(null, plugins)) reload(); } });
    const lines = coupons.map(coupon => {
        const [label, tone] = SITUACAO[coupon.situacao] || [coupon.situacao, ""];
        const discount = coupon.tipo === "percentual" ? `${Number(coupon.valor).toLocaleString("pt-BR")}%`
            : `${money(coupon.valor)} / ${money(coupon.valor, "usd")}`;
        const period = coupon.valido_de || coupon.valido_ate
            ? `${coupon.valido_de ? date(coupon.valido_de) : "agora"} → ${coupon.valido_ate ? date(coupon.valido_ate) : "sem prazo"}` : "Sem prazo";
        const actions = el("div", { class: "actions" },
            el("button", { class: "link-button", type: "button", text: "Editar",
                onclick: async () => { if (await couponForm(coupon, plugins)) reload(); } }));
        if (!coupon.usos_registrados) {
            actions.append(el("button", { class: "link-button", type: "button", text: "Apagar", onclick: async event => {
                const ok = await confirm({ title: `Apagar o cupom ${coupon.codigo}?`, button: "Apagar", danger: true });
                if (!ok) return;
                await busy(event.currentTarget, async () => {
                    await api(`/admin/labs/cupons/${coupon.id}`, { method: "DELETE" });
                    toast("Cupom apagado.");
                    reload();
                });
            } }));
        }
        return el("tr", {},
            cell([el("strong", { class: "mono", text: coupon.codigo }), coupon.descricao ? el("small", { text: coupon.descricao }) : null]),
            cell(chip(label, tone)), cell(discount, "nowrap"), cell(coupon.plugin || "Todos"), cell(period, "nowrap"),
            cell(`${coupon.usos}${coupon.max_usos ? ` / ${coupon.max_usos}` : ""}`, "num"), cell(actions));
    });
    return el("div", {},
        pageHead("Cupons", { lead: "O cliente digita o código na página do plugin antes de comprar. Vale no checkout em BRL e no Stripe em USD. Um uso conta enquanto a compra está aberta ou paga.", actions: [create] }),
        el("section", { class: "card" }, table(["Código", "Situação", "Desconto", "Plugin", "Período", ["Usos", "num"], ""], lines,
            "Nenhum cupom ainda.")));
}
