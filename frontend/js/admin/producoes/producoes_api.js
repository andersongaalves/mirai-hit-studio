import { authFetch } from "../auth.js";

const jsonHeaders = { "Content-Type": "application/json" };

async function handleResponse(response, fallback) {
    const text = await response.text();
    let data = null;
    if (text) {
        try {
            data = JSON.parse(text);
        } catch {
            data = null;
        }
    }
    if (!response.ok) {
        const detail = typeof data?.detail === "string" ? data.detail : fallback;
        const error = new Error(detail);
        error.status = response.status;
        throw error;
    }
    return data;
}

export async function buscarProducoes(ambiente = "real") {
    return handleResponse(
        await authFetch(`/producoes?ambiente=${encodeURIComponent(ambiente)}`),
        "Erro ao buscar produções.",
    );
}

export async function buscarProducao(id) {
    return handleResponse(
        await authFetch(`/producoes/${id}`),
        "Erro ao buscar produção.",
    );
}

async function atualizar(id, endpoint, payload, fallback) {
    const response = await authFetch(`/producoes/${id}/${endpoint}`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    });
    return handleResponse(response, fallback);
}

export function atualizarStatus(id, status) {
    return atualizar(id, "status", { status }, "Erro ao atualizar status.");
}

export function atualizarEtapas(id, etapas) {
    return atualizar(
        id,
        "etapas",
        { etapas: JSON.stringify(etapas) },
        "Erro ao atualizar etapas.",
    );
}

export function atualizarPrazo(id, prazoEntrega) {
    return atualizar(
        id,
        "prazo",
        { prazo_entrega: prazoEntrega || null },
        "Erro ao atualizar prazo.",
    );
}

export function atualizarObservacoes(id, observacoes) {
    return atualizar(
        id,
        "observacoes",
        { observacoes },
        "Erro ao atualizar observações.",
    );
}

export async function buscarArquivos(id) {
    return handleResponse(await authFetch(`/producoes/${id}/arquivos`), "Erro ao buscar arquivos.");
}

export async function enviarArquivo(id, form) {
    return handleResponse(await authFetch(`/producoes/${id}/arquivos`, {
        method: "POST",
        body: form,
    }), "Erro ao enviar arquivo.");
}

export async function atualizarVisibilidadeArquivo(producaoId, arquivoId, payload) {
    return handleResponse(await authFetch(`/producoes/${producaoId}/arquivos/${arquivoId}/visibilidade`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao atualizar visibilidade.");
}

export async function baixarArquivo(producaoId, arquivoId) {
    const response = await authFetch(`/producoes/${producaoId}/arquivos/${arquivoId}/conteudo`);
    if (!response.ok) return handleResponse(response, "Erro ao baixar arquivo.");
    const disposition = response.headers.get("content-disposition") || "";
    const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    return {
        blob: await response.blob(),
        filename: encoded ? decodeURIComponent(encoded) : "arquivo",
    };
}

export async function buscarRepasse(id) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse`), "Erro ao buscar repasse.");
}

export async function definirRepasse(id, valor) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse`, {
        method: "PUT",
        headers: jsonHeaders,
        body: JSON.stringify({ valor_combinado: valor }),
    }), "Erro ao definir repasse.");
}

export async function liberarRepasse(id) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/liberar`, { method: "POST" }), "Erro ao liberar repasse.");
}

export async function pagarRepasse(id, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/pagar`, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao registrar pagamento.");
}

export async function corrigirRepasse(id, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/repasse/correcao`, {
        method: "PATCH",
        headers: jsonHeaders,
        body: JSON.stringify(payload),
    }), "Erro ao corrigir repasse.");
}

export async function buscarMensagens(id) {
    return handleResponse(await authFetch(`/producoes/${id}/mensagens`), "Erro ao buscar mensagens.");
}

export async function enviarMensagem(id, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/mensagens`, {
        method: "POST",
        body: JSON.stringify(payload),
    }), "Erro ao enviar mensagem.");
}

// Roadmap 5.06: contract stages with values, deadlines and approval.
export async function buscarEtapasContratuais(id) {
    return handleResponse(await authFetch(`/producoes/${id}/etapas-contratuais`), "Erro ao buscar etapas do contrato.");
}

export async function atualizarEtapaContratual(id, etapaId, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/etapas-contratuais/${etapaId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
    }), "Erro ao atualizar etapa.");
}

export async function gerarEtapasContratuais(id) {
    return handleResponse(await authFetch(`/producoes/${id}/etapas-contratuais/gerar`, {
        method: "POST",
    }), "Erro ao gerar etapas.");
}

// Roadmap 5.07: responsible per stage and its history.
export async function buscarProdutoresAtivos() {
    return handleResponse(await authFetch("/usuarios/produtores"), "Erro ao buscar produtores.");
}

export async function atribuirEtapaContratual(id, etapaId, payload) {
    return handleResponse(await authFetch(`/producoes/${id}/etapas-contratuais/${etapaId}/responsavel`, {
        method: "PATCH",
        body: JSON.stringify(payload),
    }), "Erro ao atribuir etapa.");
}

export async function historicoEtapaContratual(id, etapaId) {
    return handleResponse(await authFetch(`/producoes/${id}/etapas-contratuais/${etapaId}/historico`), "Erro ao buscar histórico.");
}

// Roadmap 5.09: contractual file quotas of the production and the admin exception.
export async function buscarCotasArquivos(id) {
    return handleResponse(await authFetch(`/producoes/${id}/cotas-arquivos`), "Erro ao buscar cotas de arquivos.");
}

export async function salvarCotasArquivos(id, cotas) {
    return handleResponse(await authFetch(`/producoes/${id}/cotas-arquivos`, {
        method: "PUT",
        body: JSON.stringify({ cotas }),
    }), "Erro ao salvar cotas de arquivos.");
}

// Roadmap 5.10: portal policies in force for the production and the admin exception.
export async function buscarPoliticas(id) {
    return handleResponse(await authFetch(`/producoes/${id}/politicas`), "Erro ao buscar políticas.");
}

export async function salvarExcecaoPoliticas(id, politicas, motivo) {
    return handleResponse(await authFetch(`/producoes/${id}/politicas`, {
        method: "PUT",
        body: JSON.stringify({ politicas, motivo }),
    }), "Erro ao salvar a exceção.");
}

export async function removerExcecaoPoliticas(id) {
    return handleResponse(await authFetch(`/producoes/${id}/politicas`, { method: "DELETE" }), "Erro ao remover a exceção.");
}
