import { creditQuantity } from "./service_credits.js";

const element = (tag, text = "", className = "") => {
    const item = document.createElement(tag);
    item.textContent = text;
    item.className = className;
    return item;
};

export function creditAllocationsPanel(data, handlers) {
    const root = element("div", "", "credit-allocations");
    const notice = element("p");
    notice.setAttribute("role", "status");
    notice.setAttribute("aria-live", "polite");
    notice.hidden = true;
    const keys = new Map();
    const keyFor = payload => {
        const digest = JSON.stringify(payload);
        if (!keys.has(digest)) keys.set(digest, crypto.randomUUID());
        return keys.get(digest);
    };
    let busy = false;
    async function run(button, action) {
        if (busy) return;
        busy = true;
        button.disabled = true;
        notice.hidden = false;
        notice.textContent = "Registrando movimentação...";
        try {
            await action();
            notice.textContent = "Movimentação registrada.";
            await handlers.onReload();
        } catch (error) {
            notice.textContent = error.message || "Não foi possível confirmar a movimentação.";
        } finally {
            busy = false;
            button.disabled = false;
        }
    }
    if (data.mensagem) root.append(element("p", data.mensagem, "admin-help"));
    const reason = element("textarea");
    reason.rows = 2;
    reason.minLength = 5;
    reason.maxLength = 500;
    reason.required = true;
    reason.id = "credit-allocation-reason";
    const label = element("label", "Motivo da movimentação");
    label.htmlFor = reason.id;
    root.append(label, reason, notice);
    const validReason = () => {
        reason.setCustomValidity(reason.value.trim().length >= 5 ? "" : "Informe o motivo (mínimo de 5 caracteres).");
        return reason.reportValidity();
    };
    if (data.pode_reservar && data.lotes.length) {
        const form = element("form", "", "producao-operacao-form");
        const select = element("select");
        select.id = "credit-allocation-lot";
        const selectLabel = element("label", "Lote de créditos");
        selectLabel.htmlFor = select.id;
        data.lotes.forEach(lot => select.append(new Option(`${lot.servico_nome} · ${creditQuantity(lot.disponivel, lot.unidade)} · Lote #${lot.id}`, String(lot.id))));
        const quantity = element("input");
        quantity.id = "credit-allocation-quantity";
        quantity.type = "number";
        quantity.required = true;
        const quantityLabel = element("label", "Quantidade");
        quantityLabel.htmlFor = quantity.id;
        const sync = () => {
            const lot = data.lotes.find(item => String(item.id) === select.value);
            quantity.min = lot.unidade === "hora" ? "0.001" : "1";
            quantity.step = quantity.min;
            quantity.max = lot.disponivel;
        };
        select.onchange = sync;
        sync();
        const save = element("button", "Reservar créditos", "btn-small");
        save.type = "submit";
        form.onsubmit = event => {
            event.preventDefault();
            if (!form.reportValidity() || !validReason()) return;
            const payload = { lote_id: Number(select.value), quantidade: quantity.value, motivo: reason.value.trim() };
            run(save, () => handlers.onReserve({ ...payload, idempotency_key: keyFor(payload) }));
        };
        selectLabel.append(select);
        quantityLabel.append(quantity);
        form.append(selectLabel, quantityLabel, save);
        root.append(form);
    } else if (data.pode_reservar) root.append(element("p", "Nenhum crédito disponível para reserva.", "admin-empty"));
    const states = { reservada: "Reservada", consumida: "Utilizada", devolvida: "Devolvida", estornada: "Estornada" };
    data.alocacoes.forEach(item => {
        const row = element("article", "", "producao-arquivo-row");
        row.append(element("strong", `${item.servico_nome} · ${creditQuantity(item.quantidade, item.unidade)}`),
            element("span", states[item.estado] || "Indisponível"));
        const actions = [];
        if (item.estado === "reservada" && ["em_producao", "revisao"].includes(data.producao_status)) actions.push(["consumo", "Confirmar uso"]);
        if (item.estado === "reservada" && data.producao_status === "aguardando_inicio") actions.push(["devolucao", "Devolver reserva"]);
        if (item.estado === "consumida" && data.producao_status === "aguardando_inicio") actions.push(["estorno", "Estornar uso"]);
        actions.forEach(([tipo, text]) => {
            const button = element("button", text, "btn-small");
            button.type = "button";
            button.onclick = () => {
                if (!validReason()) return;
                const payload = { tipo, motivo: reason.value.trim() };
                run(button, () => handlers.onMove(item.id, { ...payload, idempotency_key: keyFor({ id: item.id, ...payload }) }));
            };
            row.append(button);
        });
        root.append(row);
    });
    return root;
}
