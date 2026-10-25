// AUD6-S07-007: API details are written for operators (no accents, internal terms).
// The client portal shows a plain message instead; anything unknown passes through.
const CLIENT_MESSAGES = [
    [/requer conciliacao/i, "Estamos conferindo um pagamento deste projeto. As informações de pagamento voltam assim que a conferência terminar."],
    [/^Situacao financeira inconsistente|^Dados financeiros invalidos/i, "As informações de pagamento estão em revisão pelo estúdio."],
    [/^Producao nao encontrada/i, "Projeto não encontrado."],
    [/^Proposta nao encontrada/i, "Proposta não encontrada."],
    [/^Servico nao encontrado/i, "Serviço não encontrado. Recarregue a página e escolha outro."],
    [/^Documento indisponivel/i, "Documento indisponível no momento."],
    [/^Esta producao nao aceita novos materiais/i, "Este projeto não aceita novos materiais."],
    [/^Tipo de arquivo nao permitido/i, "Esse tipo de arquivo não pode ser enviado por aqui."],
    [/^Nao foi possivel processar a proposta/i, "Não foi possível processar a proposta. Tente novamente."],
    [/^Nao foi possivel concluir/i, "Não foi possível concluir. Tente novamente."],
    [/^Chave ja utilizada/i, "Esta solicitação já foi enviada com outros dados. Recarregue a página e tente de novo."],
    [/^Cadastro do cliente indisponivel/i, "Seu cadastro está indisponível no momento. Fale com o estúdio."],
];

export function humanClientMessage(detail, fallback) {
    if (typeof detail !== "string" || !detail.trim() || /^not found$/i.test(detail.trim())) return fallback;
    const match = CLIENT_MESSAGES.find(([pattern]) => pattern.test(detail));
    return match ? match[1] : detail;
}
