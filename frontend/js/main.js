import { state } from "./state.js";
import * as API from "./api.js";
import * as UI from "./ui.js";
import * as PUI from "./portfolio_ui.js";
import { CalculatorLogic } from "./calculator.js";

// ==========================================
// FUNÇÕES GLOBAIS
// ==========================================

window.filtrarProjetos = filtrar;

window.moverCarrossel = (dir) => {

    const track = document.getElementById(
        "home-portfolio-track"
    );

    if (!track) return;

    track.scrollBy({

        left: dir * 320,

        behavior: "smooth"

    });

};

// ==========================================
// PORTFÓLIO
// ==========================================

async function initPortfolioPage() {

    state.todosProjetos = await API.getProjetos();

    PUI.renderizarFiltros(

        state.todosProjetos,

        filtrar

    );

    PUI.renderizarProjetos(

        state.todosProjetos

    );

}

function filtrar(categoria) {

    if (categoria === "Todos") {

        PUI.renderizarProjetos(

            state.todosProjetos

        );

        return;

    }

    PUI.renderizarProjetos(

        state.todosProjetos.filter(

            projeto => projeto.categoria === categoria

        )

    );

}

// ==========================================
// CALCULADORA
// ==========================================

async function initCalculadora() {

    const [config, servicos] = await Promise.all([

        API.getAPI("config"),

        API.getAPI("servicos")

    ]);

    state.configGlobal = {

        ...config,

        mult_desconto:

            (100 - config.desconto) / 100

    };

    state.servicosDB = servicos;

    UI.renderizarBotoes(

        state.servicosDB

    );

}

window.avancarPasso = function(passo) {
    // Esconde todos os passos
    document.querySelectorAll('.step-content').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.step-indicator').forEach(el => el.classList.remove('active'));
    
    // Mostra o passo atual e atualiza a barra superior
    document.getElementById(`step-${passo}`).classList.remove('hidden');
    
    // Preenche os indicadores ativos até ao passo atual
    for(let i = 1; i <= passo; i++) {
        const ind = document.getElementById(`ind-${i}`);
        if(ind) ind.classList.add('active');
    }

    // Se chegou ao passo 3, recalcula tudo por garantia
    if(passo === 3) calcular();
};

window.voltarPasso = function(passo) {
    // Reutiliza a lógica de avançar para retroceder visualmente
    window.avancarPasso(passo);
};

function calcular() {

    if (!state.servicoSelecionadoOBJ)

        return;

    let total =

        state.servicoSelecionadoOBJ.valor_base;

    state.servicoSelecionadoOBJ.parametros

        .split(",")

        .forEach(param => {

            const el = document.getElementById(

                param.trim()

            );

            if (!el) return;

            if (

                CalculatorLogic[param]

            ) {

                total +=
                    CalculatorLogic[param](
                    el.value,
                    document.getElementById("canais_inst")?.value
                );
            }
        });

    const badge = document.getElementById("badge-desconto");

    if (state.servicoSelecionadoOBJ.aplica_desconto) {

        total *= state.configGlobal.mult_desconto;

        if (badge) {

            badge.style.display = "inline-block";

            badge.innerText =
                `DESCONTO DE ${state.configGlobal.desconto}% APLICADO`;

        }

    } else {

        if (badge) {

            badge.style.display = "none";

        }

    }

    state.valorTotalCalculado = total;

    const valor = document.getElementById(

        "valorTotal"

    );

    if (valor)

        valor.innerText =

            `R$ ${total.toFixed(2).replace(".", ",")}`;

}

const btnSolicitar = document.getElementById(
    "btn-solicitar"
);

if (btnSolicitar) {
    btnSolicitar.addEventListener(
        "click",

        async () => {

            if (!state.servicoSelecionadoOBJ) {
                alert("Selecione um serviço.");

                return;

            }

            const payload = {

                nome_cliente:
                    document.getElementById("nome_cliente").value,
                email:
                    document.getElementById("email").value,
                whatsapp:
                    document.getElementById("whatsapp").value,
                servico:
                    state.servicoSelecionadoOBJ.nome,
                valor_total:
                    state.valorTotalCalculado,
                link_guia:
                    document.getElementById("guia")?.value || "",
                detalhes: ""

            };

            try {
                await API.postOrcamento(payload);

                alert("Proposta enviada com sucesso!");

            } catch (error) {
                console.error(error);

                alert("Erro ao enviar proposta.");
            }
        }
    );
}

const btnNewsletter =
    document.getElementById("btn-newsletter");

if (btnNewsletter) {
    btnNewsletter.addEventListener(
        "click",

        async () => {
            const payload = {
                email: document
                    .getElementById("email")
                    .value
                    .trim()

            };

            try {
                await API.postNewsletter(
                    payload
                );

                alert(
                    "Cadastro realizado com sucesso!"
                );

            } catch (error) {
                console.error(error);

                alert(
                    error.message
                );
            }
        }
    );
}

// ==========================================
// COMPONENTES GLOBAIS
// ==========================================

UI.carregarComponente(

    "nav-placeholder",

    "components/nav.html"

);

UI.carregarComponente(

    "footer-placeholder",

    "components/footer.html"

);

UI.initParticles();

// ==========================================
// ROTEAMENTO
// ==========================================

if (

    document.getElementById(

        "render-portfolio"

    )

) {

    initPortfolioPage();

}

if (

    document.getElementById(
        "home-portfolio-track"

    )

) {

    UI.renderizarPortfolio();

    UI.initHeroParallax();

}

if (
    document.getElementById(
        "render-parametros"
    )
) {

    initCalculadora();

    // Seleção do serviço
    document.body.addEventListener('input', (e) => {
        if (e.target.name === 'servico') {
            state.servicoSelecionadoOBJ = state.servicosDB.find(s => s.id == e.target.value);
            
            // 1. Desbloqueia o botão para o Passo 2
            const btnNext1 = document.getElementById('btn-next-1');
            if (btnNext1) {
                btnNext1.disabled = false;
                btnNext1.classList.remove('disabled');
            }
            
            // 2. Renderiza a descrição
            const infoDesc = document.getElementById('info-desc');
            if (infoDesc) infoDesc.innerText = state.servicoSelecionadoOBJ.descricao_servico || "Personalize as opções abaixo:";

            // 3. Renderiza os inputs no Passo 2
            UI.renderizarFormularioParametros(state.servicoSelecionadoOBJ.parametros);
        }
        
        // Atualiza a matemática em tempo real se estiver no passo 2
        calcular();
    });

    // Recalcula quando qualquer parâmetro mudar

    document.body.addEventListener(

        "input",

        () => {

            if (

                state.servicoSelecionadoOBJ

            ) {

                calcular();

            }

        }

    );

}