export const STATUS_PRODUCAO = [

    {
        value: "aguardando_inicio",
        label: "🟡 Aguardando início"
    },

    {
        value: "em_producao",
        label: "🔵 Em produção"
    },

    {
        value: "revisao",
        label: "🟣 Revisão"
    },

    {
        value: "finalizado",
        label: "🟢 Finalizado"
    },

    {
        value: "entregue",
        label: "📦 Entregue"
    }

];

export function calcularPrazo(
    prazo
) {

    if (!prazo) {

        return "📅 Sem prazo";

    }


    const hoje =
        new Date();


    const entrega =
        new Date(
            prazo
        );


    const diferenca = Math.ceil(

        (
            entrega - hoje
        )

        /

        (
            1000 * 60 * 60 * 24
        )

    );


    if (diferenca > 0) {

        return `⏳ Faltam ${diferenca} dias`;

    }


    if (diferenca === 0) {

        return "🔥 Entrega hoje";

    }


    return `⚠️ Atrasado há ${Math.abs(diferenca)} dias`;

}