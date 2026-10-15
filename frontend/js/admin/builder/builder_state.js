/**
 * Estado global do editor de conteúdo do serviço (catálogo estruturado).
 *
 * Este objeto nunca deve ser substituído; apenas suas propriedades mudam.
 */
export const builderState = Object.seal({
    intro: "",

    destaques: [],

    limites: { faixas: null, duracao_min: null, revisoes: null, melodias: null, artistas: null },
});
