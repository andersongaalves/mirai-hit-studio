// Reused by the service and combo editors; dates are entered locally and sent with timezone.
export function promotionForm(value = null, idPrefix = "promotion") {
    const element = document.createElement("fieldset");
    element.className = "catalog-promotion";
    const legend = document.createElement("legend");
    legend.textContent = "Promoção";
    element.append(legend);
    const controls = {};
    const field = (key, text, type) => {
        const label = document.createElement("label");
        label.textContent = text;
        const input = document.createElement("input");
        input.type = type;
        input.id = `${idPrefix}-${key}`;
        label.htmlFor = input.id;
        label.append(input);
        element.append(label);
        controls[key] = input;
        return input;
    };
    field("ativa", "Promoção ativa", "checkbox").checked = Boolean(value?.ativa);
    const percentage = field("percentual", "Desconto especial (%)", "number");
    percentage.min = "0.01";
    percentage.max = "100";
    percentage.step = "0.01";
    percentage.value = value?.percentual ?? "";
    for (const [key, text] of [["inicio", "Início (opcional)"], ["fim", "Fim (opcional)"]]) {
        const input = field(key, text, "datetime-local");
        if (value?.[key]) {
            const date = new Date(value[key]);
            if (!Number.isNaN(date.getTime())) {
                input.value = new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
            }
        }
    }
    return {
        element,
        read() {
            if (!percentage.value && !controls.ativa.checked) return null;
            if (!percentage.value || !percentage.checkValidity()) throw new Error("Informe um desconto entre 0,01% e 100%.");
            const inicio = controls.inicio.value ? new Date(controls.inicio.value).toISOString() : null;
            const fim = controls.fim.value ? new Date(controls.fim.value).toISOString() : null;
            if (inicio && fim && fim <= inicio) throw new Error("O fim da promoção deve ser posterior ao início.");
            return { ativa: controls.ativa.checked, percentual: percentage.value, inicio, fim };
        },
    };
}
