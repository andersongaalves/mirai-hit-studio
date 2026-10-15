// Roadmap 3.0, 5.06: contract stages of a production, shared by the three portals.
// The server decides which transitions each viewer may perform (`acoes`); values are
// only present in the admin response. Everything is rendered as text.

export const STAGE_LABELS = Object.freeze({
    pendente: "Pendente",
    em_andamento: "Em andamento",
    em_revisao: "Em revisão",
    concluida: "Concluída",
});

function actionLabel(from, to) {
    if (to === "em_andamento") return from === "pendente" ? "Iniciar" : from === "concluida" ? "Reabrir" : "Retomar";
    if (to === "em_revisao") return "Enviar para revisão";
    if (to === "concluida") return "Aprovar e concluir";
    return "Voltar para pendente";
}

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function formatDate(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("pt-BR");
}

function dateInputValue(value) {
    if (!value) return "";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "" : date.toISOString().slice(0, 10);
}

function money(value) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
}

/**
 * options: { role, data: {progresso_percentual, etapas, pode_gerar}, error, heading,
 *            onChange(stage, destino) -> Promise, onDeadline(stage, isoOrNull) -> Promise,
 *            onGenerate() -> Promise,
 *            producers: [{id, username}], onAssign(stage, userIdOrNull, motivo) -> Promise,
 *            onHistory(stage) -> Promise<rows> }   (5.07, admin only)
 */
export function stagesPanel({
    role, data, error = "", heading = true, onChange, onDeadline, onGenerate,
    producers = [], onAssign, onHistory,
}) {
    const stages = data?.etapas ?? [];
    const panel = element("section", "production-stages");
    panel.setAttribute("aria-label", "Etapas do contrato");
    if (heading) panel.append(element("h2", "", "Etapas do contrato"));
    if (error) panel.append(element("p", "production-stages__error", error));

    if (!stages.length) {
        if (role === "admin") {
            panel.append(element("p", "production-stages__empty", data?.pode_gerar
                ? "Esta produção foi criada antes das etapas contratuais. Gere as etapas a partir da proposta."
                : "Sem etapas de catálogo no contrato desta produção."));
            if (data?.pode_gerar && onGenerate) {
                const generate = element("button", "btn-small", "Gerar etapas do contrato");
                generate.type = "button";
                generate.addEventListener("click", async () => {
                    generate.disabled = true;
                    try { await onGenerate(); } finally { generate.disabled = false; }
                });
                panel.append(generate);
            }
        }
        return panel;
    }

    const percent = Math.max(0, Math.min(100, Number(data.progresso_percentual) || 0));
    const progress = element("div", "production-stages__progress");
    progress.setAttribute("role", "progressbar");
    progress.setAttribute("aria-valuemin", "0");
    progress.setAttribute("aria-valuemax", "100");
    progress.setAttribute("aria-valuenow", String(percent));
    progress.setAttribute("aria-label", "Progresso do contrato");
    const bar = element("span", "production-stages__bar");
    bar.style.width = `${percent}%`;
    progress.append(bar);
    panel.append(progress, element("p", "production-stages__percent", `${percent}% concluído`));

    const feedback = element("p", "production-stages__feedback");
    feedback.setAttribute("role", "status");
    // Group by contract item and, inside combos (5.08), by component service label.
    const groupKey = stage => `${stage.item_indice}|${stage.item_descricao}`;
    const multipleItems = new Set(stages.map(groupKey)).size > 1;
    const list = element("ol", "production-stages__list");
    let currentItem = null;
    stages.forEach(stage => {
        if (multipleItems && groupKey(stage) !== currentItem) {
            currentItem = groupKey(stage);
            list.append(element("li", "production-stages__group", stage.item_descricao || `Item ${stage.item_indice}`));
        }
        const item = element("li", `production-stage production-stage--${stage.status}`);
        item.dataset.stageId = String(stage.id);
        const head = element("p", "production-stage__head");
        head.append(
            element("strong", "", stage.nome),
            element("span", `production-stage__status production-stage__status--${stage.status}`, STAGE_LABELS[stage.status] || stage.status),
        );
        if (stage.administrativa) head.append(element("span", "production-stage__tag", "Administrativa"));
        item.append(head);

        const meta = [];
        meta.push(stage.prazo ? `Prazo: ${formatDate(stage.prazo)}` : "Sem prazo definido");
        if (stage.concluida_em) meta.push(`Concluída em ${formatDate(stage.concluida_em)}`);
        if (stage.depende_da_anterior) meta.push("Depende da etapa anterior");
        // 5.07: producers see only "Você"/"Outro produtor"; the admin sees names and the executor.
        if (role === "produtor" && stage.responsavel_rotulo) meta.push(`Responsável: ${stage.responsavel_rotulo === "Voce" ? "Você" : stage.responsavel_rotulo === "Sem responsavel" ? "sem responsável" : "outro produtor"}`);
        if (role === "admin") meta.push(`Responsável: ${stage.responsavel_nome || "sem responsável"}`);
        if (role === "admin" && stage.executor_nome) meta.push(`Executada por ${stage.executor_nome}`);
        if (role !== "cliente" && Number.isInteger(stage.revisoes_incluidas)) meta.push(`${stage.revisoes_incluidas} revisões incluídas`);
        if (role === "admin" && stage.valor != null) meta.push(`${money(stage.valor)} (${String(stage.peso_percentual).replace(".", ",")}%)`);
        item.append(element("p", "production-stage__meta", meta.join(" · ")));

        const actions = Array.isArray(stage.acoes) ? stage.acoes : [];
        if (role === "produtor" && stage.minha) item.classList.add("production-stage--mine");
        if ((actions.length && onChange) || (role === "admin" && (onDeadline || onAssign))) {
            const controls = element("div", "production-stage__actions");
            actions.forEach(destino => {
                const button = element("button", destino === "concluida" ? "btn-cta" : "btn-outline", actionLabel(stage.status, destino));
                button.type = "button";
                button.dataset.destino = destino;
                button.addEventListener("click", async () => {
                    controls.querySelectorAll("button").forEach(control => { control.disabled = true; });
                    feedback.textContent = "Atualizando etapa...";
                    try {
                        await onChange(stage, destino);
                        feedback.textContent = "";
                    } catch (changeError) {
                        feedback.textContent = changeError.message || "Não foi possível atualizar a etapa.";
                    } finally {
                        // The caller normally re-renders; if its reload fails the controls stay usable.
                        controls.querySelectorAll("button").forEach(control => { control.disabled = false; });
                    }
                });
                controls.append(button);
            });
            if (role === "admin" && onDeadline) {
                const label = element("label", "production-stage__deadline");
                const input = element("input");
                input.type = "date";
                input.value = dateInputValue(stage.prazo);
                input.setAttribute("aria-label", `Prazo da etapa ${stage.nome}`);
                const save = element("button", "btn-outline", "Salvar prazo");
                save.type = "button";
                save.addEventListener("click", async () => {
                    save.disabled = true;
                    try {
                        await onDeadline(stage, input.value ? `${input.value}T12:00:00-03:00` : null);
                        feedback.textContent = "";
                    } catch (deadlineError) {
                        feedback.textContent = deadlineError.message || "Não foi possível salvar o prazo.";
                    } finally {
                        save.disabled = false;
                    }
                });
                label.append(input);
                controls.append(label, save);
            }
            if (role === "admin" && onAssign) {
                const assign = element("div", "production-stage__assign");
                const select = element("select");
                select.setAttribute("aria-label", `Responsável pela etapa ${stage.nome}`);
                select.append(new Option("Sem responsável", ""));
                const known = new Set();
                producers.forEach(producer => {
                    known.add(producer.id);
                    select.append(new Option(producer.username, String(producer.id)));
                });
                // A responsible no longer active still shows as the current value.
                if (stage.responsavel_usuario_id && !known.has(stage.responsavel_usuario_id)) {
                    select.append(new Option(stage.responsavel_nome || `Usuário #${stage.responsavel_usuario_id}`, String(stage.responsavel_usuario_id)));
                }
                select.value = stage.responsavel_usuario_id ? String(stage.responsavel_usuario_id) : "";
                const reason = element("input");
                reason.type = "text";
                reason.maxLength = 300;
                reason.placeholder = "Motivo (opcional)";
                reason.setAttribute("aria-label", `Motivo da troca na etapa ${stage.nome}`);
                const apply = element("button", "btn-outline", "Atribuir");
                apply.type = "button";
                const concluded = stage.status === "concluida";
                select.disabled = concluded;
                reason.disabled = concluded;
                apply.disabled = true;
                if (concluded) apply.title = "Etapa concluída preserva quem executou; reabra para reatribuir.";
                select.addEventListener("change", () => {
                    apply.disabled = concluded || select.value === (stage.responsavel_usuario_id ? String(stage.responsavel_usuario_id) : "");
                });
                apply.addEventListener("click", async () => {
                    apply.disabled = true;
                    try {
                        await onAssign(stage, select.value ? Number(select.value) : null, reason.value.trim());
                        feedback.textContent = "";
                    } catch (assignError) {
                        feedback.textContent = assignError.message || "Não foi possível atribuir a etapa.";
                        apply.disabled = false;
                    }
                });
                assign.append(select, reason, apply);
                if (onHistory) {
                    const historyButton = element("button", "btn-outline", "Histórico");
                    historyButton.type = "button";
                    historyButton.setAttribute("aria-expanded", "false");
                    const historyList = element("ol", "production-stage__history hidden");
                    historyButton.addEventListener("click", async () => {
                        const open = historyButton.getAttribute("aria-expanded") === "true";
                        if (open) {
                            historyList.classList.add("hidden");
                            historyButton.setAttribute("aria-expanded", "false");
                            return;
                        }
                        historyButton.disabled = true;
                        try {
                            const rows = await onHistory(stage);
                            historyList.replaceChildren(...rows.map(row => element("li", "", [
                                formatDate(row.created_at),
                                `${row.anterior_nome || "—"} → ${row.novo_nome || "sem responsável"}`,
                                row.atribuido_por_nome ? `por ${row.atribuido_por_nome}` : "",
                                row.motivo || "",
                            ].filter(Boolean).join(" · "))));
                            if (!rows.length) historyList.append(element("li", "", "Sem registros."));
                            historyList.classList.remove("hidden");
                            historyButton.setAttribute("aria-expanded", "true");
                        } catch (historyError) {
                            feedback.textContent = historyError.message || "Não foi possível carregar o histórico.";
                        } finally {
                            historyButton.disabled = false;
                        }
                    });
                    assign.append(historyButton);
                    controls.append(assign, historyList);
                } else {
                    controls.append(assign);
                }
            }
            item.append(controls);
        }
        list.append(item);
    });
    panel.append(list, feedback);
    return panel;
}
