export const STATUS_PRODUCAO = [
    { value: "aguardando_inicio", label: "Aguardando início" },
    { value: "em_producao", label: "Em produção" },
    { value: "revisao", label: "Revisão" },
    { value: "finalizado", label: "Finalizado" },
    { value: "entregue", label: "Entregue" },
];

export const PRAZO_PROXIMO_DIAS = 3;

const STATUS_VARIANTS = {
    aguardando_inicio: "neutral",
    em_producao: "info",
    revisao: "warning",
    finalizado: "success",
    entregue: "success",
};

const PRAZO_VARIANTS = {
    atrasado: "danger",
    proximo: "warning",
    normal: "info",
    finalizado: "success",
    sem_prazo: "neutral",
};

const STATUS_FINAL = new Set(["finalizado", "entregue"]);
const DIA_MS = 24 * 60 * 60 * 1000;

function normalize(value = "") {
    return String(value ?? "").trim().toLocaleLowerCase("pt-BR");
}

export function obterStatusLabel(status) {
    return STATUS_PRODUCAO.find((item) => item.value === status)?.label
        || status
        || "Não informado";
}

export function obterStatusVariant(status) {
    return STATUS_VARIANTS[status] || "neutral";
}

export function obterPrazoVariant(tipo) {
    return PRAZO_VARIANTS[tipo] || "neutral";
}

export function parseEtapas(value) {
    try {
        const etapas = JSON.parse(value || "[]");
        if (!Array.isArray(etapas)) return [];
        return etapas
            .filter((item) => item && typeof item.nome === "string")
            .map((item) => ({
                nome: item.nome.trim(),
                feito: item.feito === true,
            }))
            .filter((item) => item.nome);
    } catch {
        return [];
    }
}

export function calcularProgresso(value) {
    const etapas = parseEtapas(value);
    const concluidas = etapas.filter((item) => item.feito).length;
    return {
        concluidas,
        total: etapas.length,
        percentual: etapas.length
            ? Math.round((concluidas / etapas.length) * 100)
            : 0,
    };
}

export function classificarPrazo(prazo, status, agora = new Date()) {
    if (STATUS_FINAL.has(status)) return { tipo: "finalizado", dias: null };
    if (!prazo) return { tipo: "sem_prazo", dias: null };

    const entrega = new Date(prazo);
    if (Number.isNaN(entrega.getTime())) {
        return { tipo: "sem_prazo", dias: null };
    }

    const diferenca = entrega.getTime() - agora.getTime();
    if (diferenca < 0) {
        return {
            tipo: "atrasado",
            dias: -Math.max(1, Math.ceil(Math.abs(diferenca) / DIA_MS)),
        };
    }
    const dias = Math.ceil(diferenca / DIA_MS);
    if (dias <= PRAZO_PROXIMO_DIAS) return { tipo: "proximo", dias };
    return { tipo: "normal", dias };
}

export function formatarPrazo(prazo, status, agora = new Date()) {
    const classificacao = classificarPrazo(prazo, status, agora);
    if (classificacao.tipo === "finalizado") return "Concluída";
    if (classificacao.tipo === "sem_prazo") return "Sem prazo";
    if (classificacao.dias === 0) return "Entrega hoje";
    if (classificacao.tipo === "atrasado") {
        const dias = Math.abs(classificacao.dias);
        return `Atrasada há ${dias} dia${dias === 1 ? "" : "s"}`;
    }
    return `Faltam ${classificacao.dias} dia${classificacao.dias === 1 ? "" : "s"}`;
}

export function formatarData(value) {
    if (!value) return "Não informado";
    const data = new Date(value);
    if (Number.isNaN(data.getTime())) return "Não informado";
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short",
    }).format(data);
}

export function paraDatetimeLocal(value) {
    if (!value) return "";
    const data = new Date(value);
    if (Number.isNaN(data.getTime())) return "";
    const local = new Date(data.getTime() - data.getTimezoneOffset() * 60_000);
    return local.toISOString().slice(0, 16);
}

function correspondeBusca(item, busca) {
    if (!busca) return true;
    return [
        item.titulo,
        item.cliente,
        item.servico,
        item.produtor_nome,
        item.proposta_numero,
        item.id,
        item.orcamento_id,
    ].some((value) => normalize(value).includes(busca));
}

function prioridade(item, agora) {
    const prazo = classificarPrazo(item.prazo_entrega, item.status, agora);
    if (prazo.tipo === "atrasado") return 0;
    if (prazo.tipo === "proximo") return 1;
    if (prazo.tipo === "normal") return 2;
    if (prazo.tipo === "sem_prazo") return 3;
    return 4;
}

export function filtrarOrdenarProducoes(
    producoes = [],
    filtro = {},
    agora = new Date(),
) {
    const busca = normalize(filtro.busca);
    const status = filtro.status || "todos";
    const prazo = filtro.prazo || "todos";

    return producoes
        .filter((item) => correspondeBusca(item, busca))
        .filter((item) => status === "todos" || item.status === status)
        .filter((item) => {
            if (prazo === "todos") return true;
            return classificarPrazo(item.prazo_entrega, item.status, agora).tipo === prazo;
        })
        .sort((a, b) => {
            const prioridadeA = prioridade(a, agora);
            const prioridadeB = prioridade(b, agora);
            if (prioridadeA !== prioridadeB) return prioridadeA - prioridadeB;

            const prazoA = a.prazo_entrega
                ? new Date(a.prazo_entrega).getTime()
                : Infinity;
            const prazoB = b.prazo_entrega
                ? new Date(b.prazo_entrega).getTime()
                : Infinity;
            if (prazoA !== prazoB) return prazoA - prazoB;
            return Number(b.id || 0) - Number(a.id || 0);
        });
}
