import { renderAdminState } from "../ui.js";
import { formatarDataDashboard } from "./dashboard_utils.js";


const METRICAS = [
    ["clientes_ativos", "Clientes ativos", "neutral"],
    ["orcamentos_abertos", "Orcamentos em aberto", "info"],
    ["propostas_aguardando_decisao", "Propostas aguardando decisao", "warning"],
    ["producoes_ativas", "Producoes ativas", "info"],
    ["producoes_atrasadas", "Producoes atrasadas", "danger"],
];

const PIPELINE = [
    ["orcamentos_abertos", "Orcamentos em aberto"],
    ["propostas_enviadas", "Propostas enviadas"],
    ["propostas_aprovadas", "Propostas aprovadas"],
    ["producoes_ativas", "Producoes ativas"],
];

function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = content;
    return node;
}

function criarLink(secao, texto) {
    const button = element("button", "btn-small", texto);
    button.type = "button";
    button.dataset.adminTarget = secao;
    return button;
}

function criarEstruturaDashboard() {
    const content = document.getElementById("dashboard-content");
    if (!content || document.getElementById("dashboard-metrics")) return;
    const metricsSection = element("section");
    metricsSection.setAttribute("aria-labelledby", "dashboard-metrics-title");
    const metricsTitle = element("h2", "admin-visually-hidden", "Indicadores operacionais");
    metricsTitle.id = "dashboard-metrics-title";
    const metrics = element("div", "dashboard-kpi-grid");
    metrics.id = "dashboard-metrics";
    metricsSection.append(metricsTitle, metrics);

    const pipelineSection = element("section", "dashboard-section");
    pipelineSection.setAttribute("aria-labelledby", "dashboard-pipeline-title");
    const pipelineTitle = element("h2", "", "Pipeline comercial");
    pipelineTitle.id = "dashboard-pipeline-title";
    const pipeline = element("ol", "dashboard-pipeline");
    pipeline.id = "dashboard-pipeline";
    pipelineSection.append(pipelineTitle, pipeline);

    const attentionSection = element("section", "dashboard-section");
    attentionSection.setAttribute("aria-labelledby", "dashboard-attention-title");
    const attentionTitle = element("h2", "", "Requer atencao");
    attentionTitle.id = "dashboard-attention-title";
    const attention = element("div");
    attention.id = "dashboard-attention";
    attentionSection.append(attentionTitle, attention);

    const activitySection = element("section", "dashboard-section");
    activitySection.setAttribute("aria-labelledby", "dashboard-activity-title");
    const activityTitle = element("h2", "", "Atividade recente");
    activityTitle.id = "dashboard-activity-title";
    const activity = element("div");
    activity.id = "dashboard-activity";
    activitySection.append(activityTitle, activity);
    content.replaceChildren(metricsSection, pipelineSection, attentionSection, activitySection);
}

function renderMetricas(data) {
    const host = document.getElementById("dashboard-metrics");
    if (!host) return;
    host.replaceChildren(...METRICAS.map(([campo, titulo, variante]) => {
        const card = element("article", `dashboard-kpi dashboard-kpi--${variante}`);
        const label = element("p", "dashboard-kpi__label", titulo);
        const value = element("strong", "dashboard-kpi__value", String(data.metrics[campo] ?? 0));
        card.append(label, value);
        return card;
    }));
}

function renderPipeline(data) {
    const host = document.getElementById("dashboard-pipeline");
    if (!host) return;
    host.replaceChildren(...PIPELINE.map(([campo, titulo]) => {
        const item = element("li", "dashboard-pipeline__item");
        item.append(element("span", "dashboard-pipeline__label", titulo));
        item.append(element("strong", "dashboard-pipeline__value", String(data.pipeline[campo] ?? 0)));
        return item;
    }));
}

function renderAtencao(data) {
    const host = document.getElementById("dashboard-attention");
    if (!host) return;
    const items = [];
    if (data.attention.producoes_atrasadas > 0) {
        const item = element("div", "dashboard-attention-item dashboard-attention-item--danger");
        item.append(element("span", "admin-badge admin-badge--danger", `${data.attention.producoes_atrasadas} producoes atrasadas`));
        item.append(criarLink("section-producoes", "Ver producoes"));
        items.push(item);
    }
    if (data.attention.propostas_aguardando_decisao > 0) {
        const item = element("div", "dashboard-attention-item");
        item.append(element("span", "admin-badge admin-badge--warning", `${data.attention.propostas_aguardando_decisao} propostas aguardando decisao`));
        item.append(criarLink("section-orcamentos", "Ver orcamentos"));
        items.push(item);
    }
    if (items.length === 0) {
        renderAdminState(host, "success", "Nenhuma acao pendente no momento.");
        return;
    }
    host.replaceChildren(...items);
}

function renderAtividade(data) {
    const host = document.getElementById("dashboard-activity");
    if (!host) return;
    if (!data.recent_activity.length) {
        renderAdminState(host, "empty", "Ainda nao ha atividade recente.");
        return;
    }
    const list = element("ul", "dashboard-activity-list");
    data.recent_activity.forEach((atividade) => {
        const item = element("li", "dashboard-activity-item");
        const details = element("div", "dashboard-activity-item__details");
        details.append(element("strong", "", atividade.titulo));
        details.append(element("time", "", formatarDataDashboard(atividade.data)));
        item.append(details, criarLink(atividade.secao, "Abrir"));
        list.append(item);
    });
    host.replaceChildren(list);
}

export function renderDashboardLoading() {
    renderAdminState(document.getElementById("dashboard-content"), "loading", "Carregando indicadores...");
}

export function renderDashboardError(onRetry) {
    renderAdminState(
        document.getElementById("dashboard-content"),
        "error",
        "Nao foi possivel carregar o dashboard.",
        { onRetry },
    );
}

export function renderDashboard(data) {
    const content = document.getElementById("dashboard-content");
    if (!content) return;
    criarEstruturaDashboard();
    renderMetricas(data);
    renderPipeline(data);
    renderAtencao(data);
    renderAtividade(data);
}
