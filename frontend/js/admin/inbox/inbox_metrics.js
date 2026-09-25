import { buscarMetricas } from "./inbox_api.js";
import { renderAdminState } from "../ui.js";

let version = 0;
let bound = false;
const $ = (id) => document.getElementById(id);
const number = (value) => value == null ? "Indisponível" : Number(value).toLocaleString("pt-BR");

function text(tag, value, className = "") {
    const element = document.createElement(tag);
    element.textContent = value;
    if (className) element.className = className;
    return element;
}

export function renderMetrics(container, data) {
    container.replaceChildren();
    for (const channel of data.channels || []) {
        const section = document.createElement("section");
        section.append(text("h3", channel.channel === "email" ? "E-mail" : "Site"));
        const values = document.createElement("dl");
        values.className = "inbox-metrics-values";
        const metrics = [
            ["Conversas iniciadas", channel.conversations_started],
            ["Dessas, encerradas", channel.cohort_closed],
            ["Dessas, encaminhadas", channel.cohort_handoffs],
            ["Respostas autônomas", channel.autonomous_replies], ["Respostas humanas", channel.human_replies],
            ["Sugestões geradas", channel.copilot_generated], ["Sugestões utilizadas", channel.copilot_used],
            ["Briefings iniciados", channel.briefings_started], ["Orçamentos desses briefings", channel.budgets_created],
            ["Chamadas ao fornecedor", channel.provider_calls], ["Tokens informados (subtotal)", channel.total_tokens],
            ["Chamadas com consumo completo", channel.usage_known_calls],
            ["Chamadas sem custo conhecido", channel.cost_unknown_calls],
        ];
        const operations = channel.operations || [];
        metrics.push(["Falhas do fornecedor", operations.filter(item => item.name === "provider" && item.result === "error")
            .reduce((sum, item) => sum + item.count, 0)]);
        for (const [label, value] of metrics) {
            const row = document.createElement("div");
            row.append(text("dt", label), text("dd", number(value)));
            values.append(row);
        }
        section.append(values);
        const technical = document.createElement("ul");
        for (const operation of operations) {
            technical.append(text("li", `${operation.name}: ${operation.result}${operation.error_code ? ` (${operation.error_code})` : ""} · ${number(operation.count)} · média ${number(operation.latency_ms)} ms`));
        }
        if (technical.childElementCount) section.append(technical);
        for (const cost of channel.costs || []) {
            section.append(text("p", `Custo estimado parcial: ${number(cost.amount)} ${cost.currency} (${number(cost.measured_calls)} chamadas)`));
        }
        container.append(section);
    }
    container.append(text("p", "Conversas e briefings: coortes iniciadas no período. Respostas e consumo: ocorrências no período. Encerramento não comprova resolução. Consumo técnico não possui histórico anterior à ativação."));
}

async function load() {
    const container = $("inbox-metrics-content");
    if (!container || !$("inbox-metrics")?.open) return;
    const current = ++version;
    renderAdminState(container, "loading", "Carregando métricas...");
    try {
        const data = await buscarMetricas(Number($("inbox-metrics-period")?.value || 7));
        if (current === version) renderMetrics(container, data);
    } catch {
        if (current === version) renderAdminState(container, "error", "Não foi possível carregar as métricas.");
    }
}

export function initMetrics() {
    if (bound || !$("inbox-metrics")) return;
    bound = true;
    $("inbox-metrics").addEventListener("toggle", load);
    $("inbox-metrics-period").addEventListener("change", load);
    $("inbox-metrics-refresh").addEventListener("click", load);
}

export function resetMetrics() {
    version++;
    if ($("inbox-metrics")) $("inbox-metrics").open = false;
    if ($("inbox-metrics-period")) $("inbox-metrics-period").value = "7";
    $("inbox-metrics-content")?.replaceChildren();
}
