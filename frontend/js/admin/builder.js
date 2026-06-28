import { builderState } from "./builder_state.js";

function gerarId() {
    return crypto.randomUUID();
}

export function resetBuilder() {
    builderState.intro = "";
    builderState.sections = [];
    builderState.benefits = [];
}

export function carregarBuilder(json) {

    resetBuilder();

    if (!json) return;

    let dados = json;

    if (typeof json === "string") {
        try {
            dados = JSON.parse(json);
        }

        catch {
            return;
        }
    }

    builderState.intro = dados.intro ?? "";
    builderState.sections = (dados.sections ?? []).map(secao => ({
        id: secao.id ?? gerarId(),
        icon: secao.icon ?? "",
        title: secao.title ?? "",
        items: [...(secao.items ?? [])]
    }));

    builderState.benefits = [...(dados.benefits ?? [])];

}

export function adicionarSecao() {

    builderState.sections.push({
        id: gerarId(),
        icon: "",
        title: "",
        open: true,
        items:[]
    });
}

export function removerSecao(id) {

    builderState.sections = builderState.sections.filter(
        secao => secao.id !== id
    );
}

export function atualizarSecao(id, campo, valor) {
    const secao = builderState.sections.find(
        secao => secao.id === id
    );
    if (!secao) return;

    secao[campo] = valor;
}

export function adicionarItem(idSecao) {
    const secao = builderState.sections.find(
        secao => secao.id === idSecao
    );
    if (!secao) return;
    secao.items.push("");
}

export function atualizarItem(idSecao, index, valor) {
    const secao = builderState.sections.find(
        secao => secao.id === idSecao
    );
    if (!secao) return;

    secao.items[index] = valor;
}

export function removerItem(idSecao, index) {
    const secao = builderState.sections.find(
        secao => secao.id === idSecao
    );

    if (!secao) return;
    secao.items.splice(index, 1);
}

export function adicionarBeneficio() {
    builderState.benefits.push("");
}

export function atualizarBeneficio(index, valor) {
    builderState.benefits[index] = valor;
}

export function removerBeneficio(index) {
    builderState.benefits.splice(index, 1);
}

export function gerarObjeto() {

    return {
        intro: builderState.intro,

        sections: builderState.sections.map(secao => ({
            icon: secao.icon,
            title: secao.title,
            items: secao.items.filter(item => item.trim())

        })),
        benefits: builderState.benefits.filter(item => item.trim())
    };
}

export function gerarJSON() {
    return JSON.stringify(
        gerarObjeto()
    );
}

export function obterState() {
    return builderState;
}

export function atualizarIntro(valor) {
    builderState.intro = valor;
}

export function alternarSecao(id){

    const secao = builderState.sections.find(

        s=>s.id===id

    );

    if(!secao) return;

    secao.open = !secao.open;

}