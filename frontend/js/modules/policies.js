// Roadmap 3.0, 5.10: contractual portal policies, shared by the global editor, the service
// editor and the production modal. A closed list of typed choices; the server enforces them.

export const POLICIES = Object.freeze([
    { key: "publicacao_previa", label: "Prévias do produtor", options: [
        ["automatica", "Vão direto para o cliente"],
        ["aprovacao_admin", "Só após aprovação do Admin"],
    ] },
    { key: "revisoes_excedentes", label: "Revisões além das incluídas", options: [
        ["permitir", "Permitir (contadas como extra)"],
        ["exigir_admin", "Somente o Admin libera"],
    ] },
    { key: "cliente_ve_etapas", label: "Cliente vê as etapas", options: [
        [true, "Sim"],
        [false, "Não (só o progresso geral)"],
    ] },
    { key: "cliente_ve_prazos_etapas", label: "Cliente vê os prazos das etapas", options: [
        [true, "Sim"],
        [false, "Não"],
    ] },
    { key: "financeiro_cliente", label: "Financeiro no portal do cliente", options: [
        ["completo", "Completo (com histórico de pagamentos)"],
        ["resumido", "Resumido (status, saldo e link de pagamento)"],
    ] },
    { key: "entrega_final", label: "Entrega final ao cliente", options: [
        ["apos_quitacao", "Só após a quitação do saldo"],
        ["liberada", "Liberada mesmo com saldo pendente"],
    ] },
]);

export const ORIGIN_LABELS = Object.freeze({
    excecao: "exceção do Admin",
    contrato: "contrato",
    global: "padrão global",
    sistema: "padrão do sistema",
});

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

export function optionLabel(key, value) {
    const policy = POLICIES.find(item => item.key === key);
    const option = policy?.options.find(([optionValue]) => optionValue === value);
    return option ? option[1] : String(value ?? "");
}

/**
 * Form with one select per policy. With `inherited` (complete values of the level below),
 * every select starts with an "inherit" option and read() returns only the keys set;
 * without it, read() returns every key.
 */
export function policyForm({ values = {}, inherited = null, inheritLabel = "Herdar", idPrefix = "politica" }) {
    const root = element("div", "policy-form");
    const selects = POLICIES.map(({ key, label, options }) => {
        const field = element("label", "policy-form__field");
        const select = element("select");
        select.id = `${idPrefix}-${key}`;
        select.name = key;
        if (inherited) {
            const inherit = element("option", "", `${inheritLabel}: ${optionLabel(key, inherited[key])}`);
            inherit.value = "";
            select.append(inherit);
        }
        options.forEach(([value, text]) => {
            const option = element("option", "", text);
            option.value = String(value);
            select.append(option);
        });
        const current = values[key];
        select.value = current === undefined || current === null ? (inherited ? "" : String(options[0][0])) : String(current);
        field.append(element("span", "", label), select);
        root.append(field);
        return { key, select, options };
    });
    const read = () => {
        const result = {};
        selects.forEach(({ key, select, options }) => {
            if (select.value === "") return;
            const match = options.find(([value]) => String(value) === select.value);
            if (match) result[key] = match[0];
        });
        return result;
    };
    return { element: root, read };
}

/** Read-only list of the policies in force and where each one comes from. */
export function policySummary(vigentes = {}, origens = {}) {
    const list = element("ul", "policy-summary");
    POLICIES.forEach(({ key, label }) => {
        const item = element("li", origens[key] === "excecao" ? "is-exception" : "");
        item.append(
            element("strong", "", `${label}: `),
            document.createTextNode(optionLabel(key, vigentes[key])),
            element("span", "policy-summary__origin", ` (${ORIGIN_LABELS[origens[key]] || origens[key] || "—"})`),
        );
        list.append(item);
    });
    return list;
}
