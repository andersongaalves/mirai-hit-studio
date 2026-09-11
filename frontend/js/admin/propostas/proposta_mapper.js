// Transport allowlists: UI fields and derived amounts never enter PATCH.
const campos = ["produtor_id", "objeto", "descricao", "itens", "pagamentos", "condicoes"];
const responseFields = ["id", "orcamento_id", "numero", "versao", "status",
    "cliente_snapshot", "totais", "pdf_path", "gerada_em", "enviada_em",
    "aprovada_em", "created_at", "updated_at", ...campos];

export function buildPropostaPayload(proposta) {
    const payload = {};
    for (const campo of campos) {
        if (Object.hasOwn(proposta, campo)) payload[campo] = structuredClone(proposta[campo]);
    }
    if (payload.itens) payload.itens = payload.itens.map(item => ({
        descricao: item.descricao, quantidade: item.quantidade,
        valor_unitario: item.valor_unitario, desconto: item.desconto ?? 0
    }));
    if (payload.pagamentos) payload.pagamentos = payload.pagamentos.map(item => ({
        tipo: item.tipo, titulo: item.titulo, url: item.url, habilitado: item.habilitado
    }));
    return payload;
}

export function mapResponseToState(response) {
    const proposta = {};
    for (const field of responseFields) {
        if (Object.hasOwn(response, field)) proposta[field] = structuredClone(response[field]);
    }
    const snapshot = proposta.cliente_snapshot;
    const orcamento = snapshot ? {
        ...snapshot.orcamento, nome_cliente: snapshot.cliente.nome,
        email: snapshot.cliente.email, whatsapp: snapshot.cliente.whatsapp
    } : null;
    return { proposta, orcamento };
}
