import { closeAdminModal, openAdminModal } from "../admin_modal.js";
import { formatarData } from "./clientes_utils.js";
import { buscarCreditosCliente, criarProducaoCreditos, produtoresParaCreditos } from "./clientes_api.js";
import { renderServiceCredits } from "../../modules/service_credits.js";
import { creditProductionForm } from "../../modules/credit_production.js";


let current = null;
let onSave = null;
let creditRevision = 0;


function field(id) {
    return document.getElementById(id);
}


function renderHistory(items = []) {
    const container = field("cliente-historico");
    if (!container) return;
    container.replaceChildren();
    if (!items.length) {
        const empty = document.createElement("p");
        empty.className = "admin-empty";
        empty.textContent = "Nenhuma interação comercial registrada.";
        container.appendChild(empty);
        return;
    }
    const list = document.createElement("ol");
    list.className = "cliente-history-list";
    items.forEach((item) => {
        const row = document.createElement("li");
        const title = document.createElement("strong");
        const date = document.createElement("time");
        title.textContent = item.titulo;
        date.textContent = formatarData(item.data, "Data não informada");
        if (item.data) date.dateTime = item.data;
        row.append(title, date);
        // AUD6-S09-002: each event opens the record it talks about.
        const target = item.producao_id
            ? ["Abrir produção", () => openRecord("section-producoes", async () => {
                const { visualizarProducao } = await import("../producoes/producoes.js");
                await visualizarProducao(item.producao_id);
            })]
            : item.orcamento_id
                ? ["Abrir orçamento", () => openRecord("section-orcamentos", async () => {
                    const { visualizarOrcamento } = await import("../orcamentos/orcamentos.js");
                    visualizarOrcamento(item.orcamento_id);
                })]
                : null;
        if (target) {
            const open = document.createElement("button");
            open.type = "button";
            open.className = "btn-small cliente-history-open";
            open.textContent = target[0];
            open.addEventListener("click", () => target[1]().catch(() => {}));
            row.append(open);
        }
        list.appendChild(row);
    });
    container.appendChild(list);
}


async function openRecord(section, open) {
    closeClienteModal();
    await window.mostrarSecao?.(section);
    await open();
}


function payload() {
    return {
        nome: field("cliente-nome").value.trim(),
        email: field("cliente-email").value.trim() || null,
        telefone: field("cliente-telefone").value.trim() || null,
        observacoes: field("cliente-observacoes").value,
        ativo: field("cliente-ativo").checked,
    };
}


export function openClienteModal(cliente = null, handlers = {}) {
    const revision = ++creditRevision;
    current = cliente;
    onSave = handlers.onSave || null;
    field("cliente-modal-title").textContent = cliente ? "Cliente" : "Novo cliente";
    field("cliente-nome").value = cliente?.nome || "";
    field("cliente-email").value = cliente?.email || "";
    field("cliente-telefone").value = cliente?.telefone || "";
    field("cliente-observacoes").value = cliente?.observacoes || "";
    field("cliente-ativo").checked = cliente?.ativo ?? true;
    field("cliente-history-block").classList.toggle("hidden", !cliente);
    renderHistory(cliente?.historico || []);
    field("cliente-creditos-block")?.classList.toggle("hidden", !cliente);
    const creditRoot = field("cliente-creditos-content"), loadCredits = field("cliente-creditos-load");
    creditRoot?.replaceChildren();
    if (loadCredits) {
        loadCredits.disabled = false;
        loadCredits.onclick = async () => {
            if (!current?.id || loadCredits.disabled || !creditRoot) return;
            const id = current.id;
            loadCredits.disabled = true;
            creditRoot.textContent = "Carregando créditos...";
            try {
                const data = await buscarCreditosCliente(id);
                if (creditRevision !== revision || current?.id !== id) return;
                renderServiceCredits(creditRoot, data, { emptyText: "Nenhum crédito registrado." });
                if (current.ativo) {
                    const creation = creditProductionForm(data.lotes || [], {
                        loadProducers: produtoresParaCreditos,
                        onCreate: payload => criarProducaoCreditos(id, payload),
                        onCreated: async result => {
                            if (creditRevision !== revision || current?.id !== id) return;
                            closeClienteModal();
                            window.mostrarSecao?.("section-producoes");
                            const { visualizarProducao } = await import("../producoes/producoes.js");
                            await visualizarProducao(result.producao_id);
                        },
                    });
                    if (creation) creditRoot.append(creation);
                }
            } catch (error) {
                if (creditRevision === revision) creditRoot.textContent = error.message;
            } finally {
                if (creditRevision === revision) loadCredits.disabled = false;
            }
        };
    }

    const save = field("cliente-save");
    save.onclick = async () => {
        if (save.disabled || !onSave) return;
        save.disabled = true;
        try {
            await onSave(current?.id || null, payload());
        } finally {
            save.disabled = false;
        }
    };
    openAdminModal("modal-cliente", {
        onRequestClose: closeClienteModal,
        initialFocus: "#cliente-nome",
    });
}


export function closeClienteModal() {
    ++creditRevision;
    field("cliente-creditos-content")?.replaceChildren();
    current = null;
    onSave = null;
    closeAdminModal("modal-cliente");
}
