import * as Notify from "../../utils/notifications.js";
import * as API from "./producoes_api.js";
import { messagesPanel } from "../../modules/production_messages.js";
import { stagesPanel } from "../../modules/production_stages.js";
import { quotaEditor, quotaList } from "../../modules/file_quotas.js";
import { POLICIES, policyForm, policySummary } from "../../modules/policies.js";
import { creditAllocationsPanel } from "../../modules/credit_allocations.js";
import { stagePayoutsPanel } from "../../modules/stage_payouts.js";

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
    setTimeout(() => URL.revokeObjectURL(url), 30000);
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
        if (file.observacao) info.append(node("p", "file-note", `Observação: ${file.observacao}`));
        const actions = node("div", "producao-arquivo-row__actions");
        if (file.processamento_tag) {
            info.append(node("span", "", { pendente: "Processando tag", pronto: "Versão com tag pronta", erro: "Falha no processamento da tag" }[file.processamento_tag]));
            if (file.processamento_tag === "erro") {
                const retry = node("button", "btn-small", "Reprocessar tag");
                retry.type = "button";
                retry.onclick = () => run(retry, () => API.reprocessarTag(file.id));
                actions.append(retry);
            }
        }
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
    // Only the newest version of each group can receive a new version.
    const replaced = new Set(files.map(file => file.substitui_arquivo_id).filter(id => id != null));
    files.filter(file => !replaced.has(file.id))
        .forEach(file => replacement.append(new Option(`${file.nome_exibicao} (v${file.versao})`, String(file.id))));
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
        const note = byId("prod_arquivo_observacao")?.value.trim();
        if (note) form.append("observacao", note);
        run(byId("prod_arquivo_enviar"), async () => {
            await API.enviarArquivo(productionId, form);
            // A note belongs to one version; never carry it over to the next upload.
            if (byId("prod_arquivo_observacao")) byId("prod_arquivo_observacao").value = "";
        }, "Arquivo enviado.");
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

// Roadmap 5.06: contract stages load independently, like the message thread.
let producersCache = null;

async function carregarEtapas(id, revision) {
    const slot = byId("prod_etapas_contratuais");
    if (!slot) return;
    let data = null;
    let error = "";
    try {
        data = await API.buscarEtapasContratuais(id);
    } catch {
        error = "Não foi possível carregar as etapas do contrato agora.";
    }
    // 5.07: active producers for the responsible selector; a failure keeps the panel usable.
    if (producersCache === null && data?.etapas?.length) {
        producersCache = await API.buscarProdutoresAtivos().catch(() => null);
    }
    if (revision !== loadRevision || productionId !== id) return;
    const reload = () => carregarEtapas(id, revision);
    slot.replaceChildren(stagesPanel({
        role: "admin",
        heading: false,
        data,
        error,
        onChange: async (stage, destino) => {
            await API.atualizarEtapaContratual(id, stage.id, { status: destino, status_atual: stage.status });
            Notify.success("Etapa atualizada.");
            await reload();
        },
        onDeadline: async (stage, prazo) => {
            await API.atualizarEtapaContratual(id, stage.id, { prazo });
            Notify.success("Prazo da etapa salvo.");
            await reload();
        },
        producers: Array.isArray(producersCache) ? producersCache : [],
        onAssign: async (stage, userId, motivo) => {
            await API.atribuirEtapaContratual(id, stage.id, {
                responsavel_usuario_id: userId,
                responsavel_atual: stage.responsavel_usuario_id ?? null,
                motivo,
            });
            Notify.success("Responsável atualizado.");
            await reload();
        },
        onHistory: stage => API.historicoEtapaContratual(id, stage.id),
        onGenerate: async () => {
            try {
                await API.gerarEtapasContratuais(id);
                Notify.success("Etapas do contrato geradas.");
            } catch (generateError) {
                Notify.error(generateError.message || "Não foi possível gerar as etapas.");
            }
            await reload();
        },
    }));
}

// Roadmap 5.09: quotas load independently; the editor saves an admin exception.
async function carregarCotas(id, revision) {
    const slot = byId("prod_cotas");
    if (!slot) return;
    let data = null;
    try {
        data = await API.buscarCotasArquivos(id);
    } catch {
        if (revision === loadRevision && productionId === id) {
            slot.replaceChildren(node("p", "admin-help", "Não foi possível carregar as cotas agora."));
        }
        return;
    }
    if (revision !== loadRevision || productionId !== id) return;
    const edit = node("button", "btn-small", "Editar exceção");
    edit.type = "button";
    edit.addEventListener("click", () => {
        const editor = quotaEditor({ cotas: data.cotas, formatos: data.formatos_disponiveis, idPrefix: `prod-${id}-cota` });
        const save = node("button", "btn-small", "Salvar exceção");
        save.type = "button";
        const cancel = node("button", "btn-small", "Cancelar");
        cancel.type = "button";
        cancel.addEventListener("click", () => carregarCotas(id, revision));
        save.addEventListener("click", async () => {
            let cotas;
            try {
                cotas = editor.read();
            } catch (error) {
                Notify.error(error.message);
                return;
            }
            save.disabled = true;
            try {
                await API.salvarCotasArquivos(id, cotas);
                Notify.success("Cotas da produção atualizadas.");
                await carregarCotas(id, revision);
            } catch (error) {
                Notify.error(error.message || "Erro ao salvar cotas.");
                save.disabled = false;
            }
        });
        const actions = node("div", "producao-operacao-form");
        actions.append(save, cancel);
        slot.replaceChildren(editor.element, actions);
    });
    slot.replaceChildren(quotaList(data.cotas), edit);
}

// Roadmap 5.10: policies in force, with an exception that needs a reason.
async function carregarPoliticas(id, revision) {
    const slot = byId("prod_politicas");
    if (!slot) return;
    let data = null;
    try {
        data = await API.buscarPoliticas(id);
    } catch {
        if (revision === loadRevision && productionId === id) {
            slot.replaceChildren(node("p", "admin-help", "Não foi possível carregar as políticas agora."));
        }
        return;
    }
    if (revision !== loadRevision || productionId !== id) return;
    renderPoliticas(slot, id, revision, data);
}

function renderPoliticas(slot, id, revision, data) {
    const children = [policySummary(data.vigentes, data.origens)];
    if (data.excecao) children.push(node("p", "admin-help", `Motivo da exceção: ${data.motivo || "—"}`));
    else if (!data.contrato) children.push(node("p", "admin-help", "Contrato sem políticas congeladas (anterior à 5.10): vale o padrão global atual."));
    const actions = node("div", "producao-operacao-form");
    const edit = node("button", "btn-small", data.excecao ? "Editar exceção" : "Abrir exceção");
    edit.type = "button";
    edit.addEventListener("click", () => editarPoliticas(slot, id, revision, data));
    actions.append(edit);
    if (data.excecao) {
        const remove = node("button", "btn-small", "Remover exceção");
        remove.type = "button";
        remove.addEventListener("click", async () => {
            remove.disabled = true;
            try {
                renderPoliticas(slot, id, revision, await API.removerExcecaoPoliticas(id));
                Notify.success("Exceção removida; vale o contrato.");
            } catch (error) {
                Notify.error(error.message || "Erro ao remover a exceção.");
                remove.disabled = false;
            }
        });
        actions.append(remove);
    }
    children.push(actions);
    slot.replaceChildren(...children);
}

function editarPoliticas(slot, id, revision, data) {
    const base = Object.fromEntries(POLICIES.map(({ key }) => [key, data.contrato ? data.contrato[key] : data.vigentes[key]]));
    const form = policyForm({ values: data.excecao || {}, inherited: base, inheritLabel: data.contrato ? "Contrato" : "Padrão", idPrefix: `prod-${id}-politica`, allowDeliveryRelease: true });
    const reasonLabel = node("label", "policy-form__field");
    const reason = node("textarea");
    reason.rows = 2;
    reason.maxLength = 500;
    reason.required = true;
    reason.value = data.motivo || "";
    reasonLabel.append(node("span", "", "Motivo da exceção (obrigatório)"), reason);
    const save = node("button", "btn-small", "Salvar exceção");
    save.type = "button";
    const cancel = node("button", "btn-small", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", () => renderPoliticas(slot, id, revision, data));
    save.addEventListener("click", async () => {
        const politicas = form.read();
        if (!Object.keys(politicas).length) {
            Notify.error("Escolha ao menos uma política diferente do contrato, ou remova a exceção.");
            return;
        }
        if (reason.value.trim().length < 5) {
            Notify.error("Explique o motivo da exceção.");
            return;
        }
        save.disabled = true;
        try {
            renderPoliticas(slot, id, revision, await API.salvarExcecaoPoliticas(id, politicas, reason.value.trim()));
            Notify.success("Exceção de políticas salva.");
        } catch (error) {
            Notify.error(error.message || "Erro ao salvar a exceção.");
            save.disabled = false;
        }
    });
    const actions = node("div", "producao-operacao-form");
    actions.append(save, cancel);
    slot.replaceChildren(form.element, reasonLabel, actions);
}

// Roadmap 5.03: thread loads independently so a failure never blocks files or payouts.
async function carregarMensagens(id, revision) {
    const slot = byId("prod_mensagens");
    if (!slot) return;
    let messages = [];
    let error = "";
    try {
        messages = await API.buscarMensagens(id);
    } catch {
        error = "Não foi possível carregar as mensagens agora.";
    }
    if (revision !== loadRevision || productionId !== id) return;
    slot.replaceChildren(messagesPanel({
        role: "admin",
        heading: false,
        messages,
        files,
        error,
        onSend: async payload => {
            await API.enviarMensagem(id, payload);
            await carregarMensagens(id, revision);
        },
    }));
}

async function carregarCreditos(id, revision) {
    const slot = byId("prod_creditos");
    if (!slot) return;
    slot.textContent = "Carregando créditos...";
    try {
        const data = await API.contextoCreditos(id);
        if (revision !== loadRevision || productionId !== id) return;
        slot.replaceChildren(creditAllocationsPanel(data, {
            onReserve: payload => API.reservarCreditos(id, payload),
            onMove: (allocation, payload) => API.movimentarCreditos(id, allocation, payload),
            onReload: () => revision === loadRevision && productionId === id ? carregarCreditos(id, revision) : undefined,
        }));
    } catch (error) {
        if (revision !== loadRevision || productionId !== id) return;
        slot.textContent = error.message || "Créditos indisponíveis.";
        const retry = node("button", "btn-small", "Tentar novamente");
        retry.type = "button";
        retry.onclick = () => carregarCreditos(id, revision);
        slot.append(retry);
    }
}

async function carregarRepassesEtapas(id, revision) {
    const slot = byId("prod_repasses_etapas");
    if (!slot) return;
    slot.textContent = "Carregando repasses...";
    const legacy = byId("prod_repasse_legado");
    if (legacy) legacy.hidden = false;
    try {
        const rows = await API.buscarRepassesEtapas(id);
        if (revision !== loadRevision || productionId !== id) return;
        const current = () => {
            if (revision !== loadRevision || productionId !== id) throw new Error("Reabra a producao antes de registrar o repasse.");
        };
        slot.replaceChildren(stagePayoutsPanel(rows, {
            files,
            onIssue: () => { current(); return API.emitirRepassesEtapas(id); },
            onPay: (record, payload) => { current(); return API.pagarRepasseEtapa(id, record, payload); },
            onReload: () => revision === loadRevision && productionId === id ? carregarOperacao(id) : undefined,
        }));
        if (legacy) legacy.hidden = rows.length > 0 && !payout;
    } catch (error) {
        if (revision !== loadRevision || productionId !== id) return;
        slot.textContent = error.message || "Repasses por etapa indisponiveis.";
    }
}

export async function carregarOperacao(id) {
    const revision = ++loadRevision;
    productionId = id;
    const stagePayouts = byId("prod_repasses_etapas");
    if (stagePayouts) stagePayouts.textContent = "Carregando repasses...";
    carregarCreditos(id, revision);
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
        carregarRepassesEtapas(id, revision);
        carregarEtapas(id, revision);
        carregarCotas(id, revision);
        carregarPoliticas(id, revision);
        carregarMensagens(id, revision);
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
    byId("prod_mensagens")?.replaceChildren();
    byId("prod_etapas_contratuais")?.replaceChildren();
    byId("prod_cotas")?.replaceChildren();
    byId("prod_politicas")?.replaceChildren();
    byId("prod_creditos")?.replaceChildren();
    byId("prod_repasses_etapas")?.replaceChildren();
    const legacy = byId("prod_repasse_legado");
    if (legacy) legacy.hidden = false;
}
