import * as Notify from "../../utils/notifications.js";
import * as API from "./producoes_api.js";

let productionId = null;
let files = [];
let payout = null;
let loadRevision = 0;

const byId = id => document.getElementById(id);
const node = (tag, className, text) => {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = text;
    return item;
};
const money = value => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));

async function run(button, action, message) {
    const activeProductionId = productionId;
    button.disabled = true;
    try {
        await action();
        if (message) Notify.success(message);
        if (productionId === activeProductionId) await carregarOperacao(activeProductionId);
    } catch (error) {
        Notify.error(error.message || "A operação não pôde ser concluída.");
    } finally {
        button.disabled = false;
    }
}

function saveBlob({ blob, filename }) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
}

function renderFiles() {
    const root = byId("prod_arquivos");
    root.replaceChildren();
    if (!files.length) root.append(node("p", "admin-empty", "Nenhum arquivo registrado."));
    files.forEach(file => {
        const row = node("article", "producao-arquivo-row");
        const info = node("div", "producao-arquivo-row__info");
        info.append(
            node("strong", "", file.nome_exibicao),
            node("span", "", `${file.tipo} · versão ${file.versao} · ${Math.ceil(file.tamanho_bytes / 1024)} KB`),
        );
        const actions = node("div", "producao-arquivo-row__actions");
        const download = node("button", "btn-small", "Baixar");
        download.type = "button";
        download.onclick = () => run(download, async () => saveBlob(await API.baixarArquivo(productionId, file.id)));
        const producer = node("label", "producao-check");
        const producerCheck = node("input");
        producerCheck.type = "checkbox";
        producerCheck.checked = file.visivel_produtor;
        producer.append(producerCheck, document.createTextNode(" Produtor"));
        const client = node("label", "producao-check");
        const clientCheck = node("input");
        clientCheck.type = "checkbox";
        clientCheck.checked = file.visivel_cliente;
        client.append(clientCheck, document.createTextNode(" Cliente"));
        const update = () => run(producerCheck, () => API.atualizarVisibilidadeArquivo(productionId, file.id, {
            visivel_produtor: producerCheck.checked,
            visivel_cliente: clientCheck.checked,
        }), "Visibilidade atualizada.");
        producerCheck.onchange = update;
        clientCheck.onchange = update;
        actions.append(producer, client, download);
        row.append(info, actions);
        root.append(row);
    });

    const replacement = byId("prod_arquivo_substitui");
    replacement.replaceChildren(new Option("Nova versão independente", ""));
    files.forEach(file => replacement.append(new Option(`${file.nome_exibicao} (v${file.versao})`, String(file.id))));
    const receipt = byId("prod_repasse_comprovante");
    receipt.replaceChildren(new Option("Sem comprovante", ""));
    files.filter(file => file.tipo === "comprovante").forEach(file => receipt.append(new Option(file.nome_exibicao, String(file.id))));
}

function renderPayout() {
    const summary = byId("prod_repasse_resumo");
    summary.replaceChildren();
    const value = byId("prod_repasse_valor");
    const reference = byId("prod_repasse_referencia");
    const receipt = byId("prod_repasse_comprovante");
    const save = byId("prod_repasse_salvar");
    const release = byId("prod_repasse_liberar");
    const pay = byId("prod_repasse_pagar");
    value.value = payout?.valor_combinado || "";
    reference.value = payout?.referencia_pagamento || "";
    receipt.value = payout?.comprovante_arquivo_id ? String(payout.comprovante_arquivo_id) : "";
    if (payout) {
        summary.append(node("p", "", `${money(payout.valor_combinado)} · ${payout.status} · produtor #${payout.produtor_id}`));
        save.textContent = payout.status === "definido" ? "Atualizar valor" : "Corrigir registro";
    } else {
        summary.append(node("p", "admin-empty", "Nenhum repasse definido."));
        save.textContent = "Definir repasse";
    }
    release.classList.toggle("hidden", payout?.status !== "definido");
    pay.classList.toggle("hidden", payout?.status !== "liberado");
}

function bindActions() {
    const uploadForm = byId("prod_arquivo_form");
    uploadForm.onsubmit = event => {
        event.preventDefault();
        const input = byId("prod_arquivo_input");
        if (!input.files[0]) return;
        const form = new FormData();
        form.append("arquivo", input.files[0]);
        form.append("tipo", byId("prod_arquivo_tipo").value);
        form.append("visivel_produtor", String(byId("prod_arquivo_produtor").checked));
        form.append("visivel_cliente", String(byId("prod_arquivo_cliente").checked));
        const replacement = byId("prod_arquivo_substitui").value;
        if (replacement) form.append("substitui_arquivo_id", replacement);
        run(byId("prod_arquivo_enviar"), () => API.enviarArquivo(productionId, form), "Arquivo enviado.");
    };
    byId("prod_repasse_salvar").onclick = () => {
        const amount = byId("prod_repasse_valor").value;
        const payload = { valor_combinado: amount };
        if (payout?.status === "pago") {
            payload.referencia_pagamento = byId("prod_repasse_referencia").value || null;
            payload.comprovante_arquivo_id = Number(byId("prod_repasse_comprovante").value) || null;
        }
        const action = payout && payout.status !== "definido"
            ? () => API.corrigirRepasse(productionId, payload)
            : () => API.definirRepasse(productionId, amount);
        run(byId("prod_repasse_salvar"), action, "Repasse atualizado.");
    };
    byId("prod_repasse_liberar").onclick = () => run(
        byId("prod_repasse_liberar"),
        () => API.liberarRepasse(productionId),
        "Repasse liberado.",
    );
    byId("prod_repasse_pagar").onclick = () => run(
        byId("prod_repasse_pagar"),
        () => API.pagarRepasse(productionId, {
            referencia_pagamento: byId("prod_repasse_referencia").value || null,
            comprovante_arquivo_id: Number(byId("prod_repasse_comprovante").value) || null,
        }),
        "Pagamento registrado.",
    );
}

export async function carregarOperacao(id) {
    const revision = ++loadRevision;
    productionId = id;
    if (!byId("prod_arquivos") || !byId("prod_repasse_resumo")) return;
    byId("prod_arquivos").textContent = "Carregando arquivos...";
    byId("prod_repasse_resumo").textContent = "Carregando repasse...";
    try {
        const result = await Promise.all([API.buscarArquivos(id), API.buscarRepasse(id)]);
        if (revision !== loadRevision || productionId !== id) return;
        [files, payout] = result;
        renderFiles();
        renderPayout();
        bindActions();
    } catch (error) {
        byId("prod_arquivos").textContent = "Não foi possível carregar arquivos e repasse.";
        byId("prod_repasse_resumo").textContent = "";
        Notify.error(error.message || "Erro ao carregar a operação.");
    }
}

export function limparOperacao() {
    loadRevision++;
    productionId = null;
    files = [];
    payout = null;
    byId("prod_arquivo_form")?.reset();
}
