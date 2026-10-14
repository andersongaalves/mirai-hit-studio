import { closeAdminModal, openAdminModal } from "./admin_modal.js";

export function confirmarClassificacao({ isTest, financialHistory = false, account = false }) {
    return new Promise(resolve => {
        const modal = document.createElement("div");
        modal.className = "modal hidden";
        modal.setAttribute("aria-labelledby", "classificacao-title");
        const panel = document.createElement("div");
        panel.className = "modal-content admin-form";
        const title = document.createElement("h2");
        title.id = "classificacao-title";
        title.textContent = isTest ? "Classificar como teste" : "Classificar como real";
        const message = document.createElement("p");
        message.textContent = account
            ? "A conta será identificada como teste ou real. Suas propostas mantêm classificação independente. Acesso, arquivos e pagamentos não serão alterados."
            : "A classificação do orçamento será aplicada à proposta e às operações vinculadas nos indicadores comerciais. Operações de teste deixam de contar nos indicadores oficiais. Pagamentos reais não serão apagados nem estornados e os documentos serão preservados.";
        const warning = document.createElement("p");
        warning.textContent = financialHistory
            ? "Esta proposta possui histórico financeiro. A classificação como teste altera apenas sua participação nos indicadores comerciais. Os pagamentos e documentos financeiros permanecerão preservados."
            : "";
        const label = document.createElement("label");
        label.className = "admin-checkbox";
        const ack = document.createElement("input");
        ack.type = "checkbox";
        label.append(ack, document.createTextNode(" Confirmo a classificação e a preservação dos registros."));
        const error = document.createElement("p");
        error.setAttribute("role", "alert");
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.className = "btn-small";
        cancel.textContent = "Cancelar";
        const save = document.createElement("button");
        save.type = "button";
        save.className = "btn-small btn-primary";
        save.textContent = "Confirmar classificação";
        save.disabled = true;
        ack.onchange = () => { save.disabled = !ack.checked; };
        const finish = result => {
            closeAdminModal(modal);
            modal.remove();
            resolve(result);
        };
        cancel.onclick = () => finish(null);
        save.onclick = () => { if (ack.checked) finish({ is_test: isTest, confirmar_historico_financeiro: financialHistory }); };
        panel.append(title, message, warning, label, error, cancel, save);
        modal.append(panel);
        document.body.append(modal);
        openAdminModal(modal, { onRequestClose: () => finish(null), initialFocus: cancel });
    });
}

export function adicionarFiltroAmbiente(anchorId, id, value, onChange) {
    const anchor = document.getElementById(anchorId);
    if (!anchor) return;
    let select = document.getElementById(id);
    if (!select) {
        const label = document.createElement("label");
        label.className = "admin-filter-field";
        const caption = document.createElement("span");
        caption.textContent = "Operações";
        label.append(caption);
        select = document.createElement("select");
        select.id = id;
        select.setAttribute("aria-label", "Ambiente das operações");
        for (const [v, text] of [["real", "Operações reais"], ["teste", "Operações de teste"], ["todos", "Todas as operações"]]) {
            const option = document.createElement("option");
            option.value = v;
            option.textContent = text;
            select.append(option);
        }
        label.append(select);
        const container = anchor.closest(".admin-filter-bar") || anchor.parentElement;
        container.append(label);
    }
    select.value = value;
    select.onchange = () => onChange(select.value);
}
