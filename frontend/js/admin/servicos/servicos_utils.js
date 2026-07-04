export const DICIONARIO_PARAMETROS = {
    duracao: "Duração",
    pessoas: "Artistas",
    canais_voz: "Canais Voz",
    inst_aberto: "Inst Aberto",
    melodias: "Melodias",
    instrumentacao: "Tipo de Instrumentação",
    exclusividade: "Exclusividade",
    revisoes: "Revisões",
    prazo: "Prazo",
    descricao: "Caixa de Descrição",
    guia: "Link para Guia"
};

export function getParametroLabel(parametro) {
    return DICIONARIO_PARAMETROS[parametro] ?? parametro;
}
