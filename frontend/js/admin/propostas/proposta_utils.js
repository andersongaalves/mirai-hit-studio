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

export const PROPOSTA_LOGO_SRC = "assets/logo_mirai_BnW.png";

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

export { escapeHtml } from "../../utils/security.js";
