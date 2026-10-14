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
 *            onGenerate() -> Promise }
 */
export function stagesPanel({ role, data, error = "", heading = true, onChange, onDeadline, onGenerate }) {
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
    const multipleItems = new Set(stages.map(stage => stage.item_indice)).size > 1;
    const list = element("ol", "production-stages__list");
    let currentItem = null;
    stages.forEach(stage => {
        if (multipleItems && stage.item_indice !== currentItem) {
            currentItem = stage.item_indice;
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
        if (role !== "cliente" && Number.isInteger(stage.revisoes_incluidas)) meta.push(`${stage.revisoes_incluidas} revisões incluídas`);
        if (role === "admin" && stage.valor != null) meta.push(`${money(stage.valor)} (${String(stage.peso_percentual).replace(".", ",")}%)`);
        item.append(element("p", "production-stage__meta", meta.join(" · ")));

        const actions = Array.isArray(stage.acoes) ? stage.acoes : [];
        if ((actions.length && onChange) || (role === "admin" && onDeadline)) {
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
            item.append(controls);
        }
        list.append(item);
    });
    panel.append(list, feedback);
    return panel;
}
