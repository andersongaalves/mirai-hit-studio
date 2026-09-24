import { money } from "../../utils/format.js";

export function formatEstimatedValue(value) {
    return value == null ? "A definir" : money(value);
}

const STATUS_LABELS = {
    novo: "🆕 Novo",
    em_analise: "🟡 Em análise",
    proposta_enviada: "🔵 Proposta enviada",
    aprovado: "🟢 Aprovado",
    arquivado: "📦 Arquivado",
};

export const STATUS_OPTIONS = Object.entries(STATUS_LABELS).map(
    ([value, label]) => ({
        value,
        label,
    }),
);

export function formatStatus(status) {
    return STATUS_LABELS[status] ?? status ?? "";
}
