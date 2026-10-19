const element = (tag, text = "", className = "") => {
    const node = document.createElement(tag);
    node.textContent = text;
    node.className = className;
    return node;
};
const money = cents => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(cents / 100);
const labels = { previsto: "Previsto", bloqueado: "Bloqueado", a_receber: "A receber", pago: "Pago" };

export function stagePayoutsPanel(rows, { files = [], onIssue, onPay, onReload }) {
    const root = element("div", "", "stage-payouts");
    const notice = element("p");
    notice.setAttribute("role", "status");
    notice.setAttribute("aria-live", "polite");
    root.append(notice);
    let busy = false;
    const retryKeys = new Map();
    async function run(button, action) {
        if (busy) return;
        busy = true;
        button.disabled = true;
        try {
            await action();
            await onReload();
        } catch (error) {
            notice.textContent = error.message || "Nao foi possivel registrar o repasse.";
        } finally {
            busy = false;
            button.disabled = false;
        }
    }
    if (!rows.length) root.append(element("p", "Nenhuma etapa contratual para remunerar.", "admin-empty"));
    if (rows.some(row => !row.id && row.estado === "a_receber" && row.bruto_centavos > 0)) {
        const issue = element("button", "Registrar repasses elegiveis", "btn-small");
        issue.type = "button";
        issue.onclick = () => run(issue, onIssue);
        root.append(issue);
    }
    rows.forEach(row => {
        const item = element("section", "", "stage-payout-row");
        item.append(element("h4", row.etapa_nome),
            element("p", labels[row.estado] || "Bloqueado"),
            element("p", `Base: ${money(row.bruto_centavos)} | Produtor: ${money(row.produtor_centavos)} | Mirai: ${money(row.mirai_centavos)}`));
        if (row.bloqueio) item.append(element("p", row.bloqueio, "admin-help"));
        if (row.id && row.estado === "a_receber" && row.produtor_centavos > 0) {
            const form = element("form", "", "producao-operacao-form");
            const reference = element("input");
            reference.id = `stage-payout-reference-${row.id}`;
            reference.required = true;
            reference.minLength = 3;
            reference.maxLength = 160;
            const referenceLabel = element("label", "Referencia da transferencia");
            referenceLabel.htmlFor = reference.id;
            referenceLabel.append(reference);
            const receipt = element("select");
            receipt.id = `stage-payout-receipt-${row.id}`;
            receipt.append(new Option("Sem comprovante", ""));
            files.filter(file => file.tipo === "comprovante").forEach(file => receipt.append(new Option(file.nome_exibicao, String(file.id))));
            const receiptLabel = element("label", "Comprovante");
            receiptLabel.htmlFor = receipt.id;
            receiptLabel.append(receipt);
            const pay = element("button", "Registrar pagamento", "btn-small");
            pay.type = "submit";
            form.append(referenceLabel, receiptLabel, pay);
            form.onsubmit = event => {
                event.preventDefault();
                const payload = { referencia: reference.value.trim(), comprovante_arquivo_id: Number(receipt.value) || null };
                reference.setCustomValidity(payload.referencia.length >= 3 ? "" : "Informe a referencia da transferencia.");
                if (!form.reportValidity()) return;
                const digest = JSON.stringify([row.id, payload]);
                if (!retryKeys.has(digest)) retryKeys.set(digest, crypto.randomUUID());
                run(pay, () => onPay(row.id, { ...payload, idempotency_key: retryKeys.get(digest) }));
            };
            item.append(form);
        }
        root.append(item);
    });
    return root;
}
