import { renderAdminState } from "../ui.js";
import { formatarDataDashboard } from "./dashboard_utils.js";


const METRICAS = [
    ["clientes_ativos", "Clientes ativos", "neutral"],
    ["orcamentos_abertos", "Orçamentos em aberto", "info"],
    ["propostas_aguardando_decisao", "Propostas aguardando decisão", "warning"],
    ["producoes_ativas", "Produções ativas", "info"],
    ["producoes_atrasadas", "Produções atrasadas", "danger"],
];

const PIPELINE = [
    ["orcamentos_abertos", "Orçamentos em aberto"],
    ["propostas_enviadas", "Propostas enviadas"],
    ["propostas_aprovadas", "Propostas aprovadas"],
    ["producoes_ativas", "Produções ativas"],
];

const PENDENCIAS = [
    ["producoes_atrasadas", "produção atrasada", "produções atrasadas", "section-producoes", "Ver produções", "danger"],
    ["propostas_aguardando_decisao", "proposta aguardando decisão", "propostas aguardando decisão", "section-orcamentos", "Ver propostas", "warning"],
    ["solicitacoes_producao", "solicitação de produção para análise", "solicitações de produção para análise", "section-orcamentos", "Ver solicitações", "warning"],
    ["beats_em_revisao", "beat aguardando revisão", "beats aguardando revisão", "section-beats", "Revisar beats", "warning"],
    ["portfolio_em_revisao", "projeto de portfólio aguardando revisão", "projetos de portfólio aguardando revisão", "section-portfolio", "Revisar portfólio", "warning"],
    ["falhas_processamento_tag", "prévia com falha no processamento da tag", "prévias com falha no processamento da tag", "section-producoes", "Ver prévias", "danger"],
    ["pagamentos_em_conciliacao", "pagamento que exige conciliação", "pagamentos que exigem conciliação", "section-financeiro", "Conciliar pagamentos", "danger"],
    ["entregas_aguardando_aprovacao", "entrega aguardando aprovação", "entregas aguardando aprovação", "section-producoes", "Revisar entregas", "warning"],
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
    const attentionTitle = element("h2", "", "Requer atenção");
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
    content.replaceChildren(metricsSection, attentionSection, pipelineSection, activitySection);
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
    const items = PENDENCIAS.flatMap(([campo, singular, plural, secao, acao, variante]) => {
        const quantidade = Number(data.attention[campo]) || 0;
        if (quantidade <= 0) return [];
        const item = element("div", `dashboard-attention-item dashboard-attention-item--${variante}`);
        item.append(element("span", `admin-badge admin-badge--${variante}`, `${quantidade} ${quantidade === 1 ? singular : plural}`));
        item.append(criarLink(secao, acao));
        return [item];
    });
    if (items.length === 0) {
        renderAdminState(host, "success", "Nenhuma ação pendente no momento.");
        return;
    }
    host.replaceChildren(...items);
}

function renderAtividade(data) {
    const host = document.getElementById("dashboard-activity");
    if (!host) return;
    if (!data.recent_activity.length) {
        renderAdminState(host, "empty", "Ainda não há atividade recente.");
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
        "Não foi possível carregar o dashboard.",
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
