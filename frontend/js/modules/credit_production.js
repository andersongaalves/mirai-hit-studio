import { creditQuantity } from "./service_credits.js";

const node = (tag, text = "") => {
    const item = document.createElement(tag);
    item.textContent = text;
    return item;
};

export function creditProductionForm(lots, handlers) {
    const available = lots.filter(lot => Number(lot.disponivel) > 0);
    if (!available.length) return null;
    const root = node("div");
    root.className = "credit-allocations";
    const open = node("button", "Nova produção com créditos");
    open.type = "button";
    open.className = "btn-small";
    const status = node("p");
    status.setAttribute("role", "status");
    root.append(open, status);
    open.onclick = async () => {
        open.disabled = true;
        let producers;
        try { producers = await handlers.loadProducers(); }
        catch (error) { status.textContent = error.message; open.disabled = false; return; }
        const form = node("form");
        form.className = "credit-allocations";
        const field = (label, input) => {
            const wrapper = node("label", label);
            wrapper.append(input);
            form.append(wrapper);
            return input;
        };
        const title = field("Título da produção", node("input"));
        title.required = true;
        title.maxLength = 150;
        const source = field("Lote de créditos", node("select"));
        available.forEach(lot => source.append(new Option(`${lot.servico_nome} · ${creditQuantity(lot.disponivel, lot.unidade)} · Lote #${lot.id}`, String(lot.id))));
        const quantity = field("Quantidade", node("input"));
        quantity.type = "number";
        quantity.required = true;
        const sync = () => {
            const lot = available.find(item => String(item.id) === source.value);
            quantity.min = lot.unidade === "hora" ? "0.001" : "1";
            quantity.step = quantity.min;
            quantity.max = lot.disponivel;
        };
        source.onchange = sync;
        sync();
        const producer = field("Produtor responsável", node("select"));
        producer.required = true;
        producer.append(new Option("Selecione", ""));
        producers.forEach(item => producer.append(new Option(item.nome_exibicao || item.username, String(item.id))));
        const reason = field("Motivo da reserva", node("textarea"));
        reason.required = true;
        reason.minLength = 5;
        reason.maxLength = 500;
        reason.rows = 2;
        const save = node("button", "Criar produção e reservar");
        save.type = "submit";
        save.className = "btn-small";
        const keys = new Map();
        form.onsubmit = async event => {
            event.preventDefault();
            if (save.disabled) return;
            reason.setCustomValidity(reason.value.trim().length < 5 ? "Informe o motivo (mínimo de 5 caracteres)." : "");
            title.setCustomValidity(title.value.trim() ? "" : "Informe o título da produção.");
            if (!form.reportValidity()) return;
            const payload = { lote_id: Number(source.value), quantidade: quantity.value, titulo: title.value.trim(),
                produtor_id: Number(producer.value), motivo: reason.value.trim() };
            const fingerprint = JSON.stringify(payload);
            if (!keys.has(fingerprint)) keys.set(fingerprint, crypto.randomUUID());
            save.disabled = true;
            try {
                const result = await handlers.onCreate({ ...payload, idempotency_key: keys.get(fingerprint) });
                status.textContent = `Produção #${result.producao_id} criada com créditos reservados.`;
                await handlers.onCreated(result);
                form.remove();
            } catch (error) {
                status.textContent = error.message || "Não foi possível confirmar a produção.";
                save.disabled = false;
            }
        };
        form.append(save);
        open.replaceWith(form);
        title.focus();
    };
    return root;
}
