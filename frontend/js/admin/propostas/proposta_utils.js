export const PROPOSTA_ABAS = [
    {
        id: "cliente",
        label: "Cliente"
    },
    {
        id: "proposta",
        label: "Proposta"
    },
    {
        id: "itens",
        label: "Itens"
    },
    {
        id: "condicoes",
        label: "Condições"
    },
    {
        id: "pagamento",
        label: "Pagamento"
    },
    {
        id: "preview",
        label: "Preview"
    }
];

export function getTituloProposta(orcamento) {
    if (!orcamento) {
        return "Editor de Proposta";
    }

    return `Proposta - ${orcamento.nome_cliente}`;
}

export const CONDICOES_PADRAO = `Esta proposta contempla os serviços descritos neste documento.

Alterações de escopo poderão gerar revisão de valores e prazos.

O início da produção ocorre após confirmação do pagamento de entrada e envio dos materiais necessários.`;

export const PROPOSTA_LOGO_SRC = "assets/logo_mirai_BnW.png";

export function criarPropostaInicial(orcamento) {
    const valor = Number(orcamento?.valor_total ?? 0);

    return {
        numero: "",
        produtor_id: orcamento?.produtor_id ?? null,
        objeto: orcamento?.servico ?? "",
        descricao: orcamento?.detalhes ?? "",
        itens: [
            {
                descricao: orcamento?.servico ?? "",
                quantidade: 1,
                valor_unitario: valor,
                desconto: 0
            }
        ],
        condicoes: CONDICOES_PADRAO,
        pagamentos: [
            { tipo: "integral", titulo: "Pagamento completo", url: "", habilitado: false },
            { tipo: "parcial_1", titulo: "Pagamento parcial 1", url: "", habilitado: false },
            { tipo: "parcial_2", titulo: "Pagamento parcial 2", url: "", habilitado: false }
        ]
    };
}

export function calcularSubtotalItem(item) {
    const quantidade = Number(item.quantidade || 0);
    const valorUnitario = Number(item.valor_unitario || 0);
    const desconto = Number(item.desconto || 0);

    return Math.max(
        0,
        quantidade * valorUnitario - desconto
    );
}

export function calcularTotalItens(itens = []) {
    return itens.reduce(
        (total, item) => total + calcularSubtotalItem(item),
        0
    );
}

export function escapeHtml(value = "") {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
