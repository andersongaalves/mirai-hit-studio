export function formatStatus(status) {

    const statusMap = {

        novo: "🟡 Novo",
        em_analise: "🔵 Em análise",
        aprovado: "🟢 Aprovado",
        recusado: "🔴 Recusado",
        arquivado: "⚫ Arquivado"
    };


    return (

        statusMap[status]

        ||

        status

    );

}

export const STATUS_OPTIONS = [

    {
        value: "novo",
        label: "🟡 Novo"
    },

    {
        value: "em_analise",
        label: "🔵 Em análise"
    },

    {
        value: "aprovado",
        label: "🟢 Aprovado"
    },

    {
        value: "recusado",
        label: "🔴 Recusado"
    },

    {
        value: "arquivado",
        label: "⚫ Arquivado"
    }

];