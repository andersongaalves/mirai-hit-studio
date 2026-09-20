import { escapeHtml, safeURL } from "./utils/security.js";
import { getProjetos } from "./api.js"; // <- Movido para o topo!
import { money } from "./utils/format.js";
import { $, $$ } from "./utils/dom.js";
import { renderizarEstrutura } from "./modules/service_renderer.js";
import { state } from "./state.js";

export const PARAM_TEMPLATES = {
    duracao: {
        html: `<div class="form-group"><label for="duracao">Duração estimada (s)</label><input type="number" id="duracao" value="180" min="30"></div>`,
        detalhe: (v) => `Duração: ${v}s`,
    },
    pessoas: {
        html: `<div class="form-group"><label for="pessoas">Artistas</label><input type="number" id="pessoas" value="1" min="1"></div>`,
        detalhe: (v) => `Artistas: ${v}`,
    },
    canais_voz: {
        html: `<div class="form-group"><label for="canais_voz">Canais de voz</label><input type="number" id="canais_voz" value="5" min="1"></div>`,
        detalhe: (v) => `Canais Voz: ${v}`,
    },
    inst_aberto: {
        html: `<div class="form-group"><label for="inst_aberto">Instrumental aberto (stems)?</label><select id="inst_aberto"><option value="nao">Não</option><option value="sim">Sim</option></select></div><div class="form-group" id="container_canais_inst" hidden><label for="canais_inst">Canais do instrumental</label><input type="number" id="canais_inst" value="1" min="1"></div>`,
        detalhe: (v, extra) =>
            v === "sim"
                ? `Inst Aberto: Sim (${extra} canais)`
                : `Inst Aberto: Não`,
    },
    melodias: {
        html: `<div class="form-group"><label for="melodias">Melodias</label><input type="number" id="melodias" value="5" min="1"></div>`,
        detalhe: (v) => `Melodias: ${v}`,
    },
    instrumentacao: {
        html: `<div class="form-group"><label for="instrumentacao">Instrumentação</label><select id="instrumentacao"><option value="eletronicos">Eletrônicos</option><option value="hibridos">Híbridos</option><option value="gravados">100% gravados</option></select></div>`,
        detalhe: (v) => `Inst: ${v}`,
    },
    exclusividade: {
        html: `<div class="form-group"><label for="exclusividade">Exclusividade</label><select id="exclusividade"><option value="sim">Sim</option><option value="nao">Não (lease)</option></select></div>`,
        detalhe: (v) => `Exclusivo: ${v}`,
    },
    revisoes: {
        html: `<div class="form-group"><label for="revisoes">Revisões</label><select id="revisoes"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></div>`,
        detalhe: (v) => `Revisões: ${v}`,
    },
    prazo: {
        html: `<div class="form-group"><label for="prazo">Prazo desejado</label><select id="prazo"><option value="normal">Normal</option><option value="urgente">Urgente</option><option value="express">Express</option></select></div>`,
        detalhe: (v) => `Prazo: ${v}`,
    },
    descricao: {
        html: `<div class="form-group"><label for="descricao">Descrição do projeto</label><textarea id="descricao" maxlength="5000" placeholder="Contexto, referências e resultado esperado"></textarea></div>`,
    },
    guia: {
        html: `<div class="form-group"><label for="guia">Link de referência <span>(opcional)</span></label><input type="url" id="guia" maxlength="500" placeholder="https://"></div>`,
    },
};

export function renderizarBotoes(servicos) {
    servicos = Array.isArray(servicos) ? servicos.filter(s => s && Number.isInteger(s.id)) : [];
    const boxAvulso = $("render-avulsos");
    const boxCombo = $("render-combos");

    if (!boxAvulso || !boxCombo) return;

    boxAvulso.innerHTML = "";
    boxCombo.innerHTML = "";
    $("categoria-avulso").hidden = true;
    $("categoria-combo").hidden = true;

    servicos.forEach((srv) => {
        const temDesconto =
            srv.aplica_desconto &&
            state.configGlobal.desconto > 0;

        const valorFinal = temDesconto
            ? srv.valor_base * state.configGlobal.mult_desconto
            : srv.valor_base;

        const subtituloHTML = srv.subtitulo
            ? `
                <small class="service-subtitle">
                    ${escapeHtml(srv.subtitulo)}
                </small>
            `
            : "";

        const descontoHTML = temDesconto
            ? `
                <span class="service-discount">
                    -${escapeHtml(state.configGlobal.desconto)}% OFF
                </span>
                <br>
            `
            : "";

        const descricaoHTML = srv.estrutura_servico
            ? `
            <div class="service-details">

                <div class="service-description">
                    ${renderizarEstrutura(srv.estrutura_servico)}
                </div>

                <div class="service-price">
                    A partir de

                    <strong>
                        ${money(valorFinal)}
                    </strong>

                    ${descontoHTML}

                </div>

                <div class="service-selected">

                    ✓ Serviço selecionado

                </div>

            </div>
        `
            : "";

        const html = `
            <div class="radio-card">

                <input
                    type="radio"
                    name="servico"
                    id="srv_${escapeHtml(srv.id)}"
                    value="${escapeHtml(srv.id)}"
                >

                <label for="srv_${escapeHtml(srv.id)}">
                    <span class="service-title">
                        ${escapeHtml(srv.nome)}
                    </span>

                    ${subtituloHTML}
                    ${descricaoHTML}
                </label>

            </div>
        `;

        if (srv.categoria === "combo") {
            boxCombo.innerHTML += html;
        } else {
            boxAvulso.innerHTML += html;
        }
    });

    if (boxAvulso.innerHTML) {
        $("categoria-avulso").hidden = false;
    }

    if (boxCombo.innerHTML) {
        $("categoria-combo").hidden = false;
    }
}

export function obterCapaInteligente(linkAudio, linkCapa) {
    if (safeURL(linkCapa)) return safeURL(linkCapa);
    const ytRegex =
        /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
    const match = safeURL(linkAudio).match(ytRegex);
    if (match && match[1])
        return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
    return "img/logo-principal.png";
}

// Renderiza o Carrossel da Home Page
export async function renderizarPortfolio() {
    const track = $("home-portfolio-track");
    if (!track) return; // Se não estiver na home, não faz nada

    const lista = await getProjetos();
    const listaHits = Array.isArray(lista) ? lista.filter((p) => p?.destaque === true) : [];

    if (listaHits.length === 0) {
        track.replaceChildren();
        const empty = document.createElement("p");
        empty.className = "public-empty";
        empty.textContent = "O portfólio público está sendo preparado com trabalhos identificados e autorizados.";
        track.appendChild(empty);
        return;
    }

    let htmlLote = `<div class="carousel-lote" style="display: flex; gap: 20px; flex-shrink: 0;">`;

    listaHits.forEach((p) => {
        const capa = obterCapaInteligente(p.link_audio, p.link_capa);
        htmlLote += `
            <a href="${escapeHtml(safeURL(p.link_audio))}" target="_blank" rel="noopener noreferrer" class="scrolling-card glass-card" data-analytics-listen data-project-id="${escapeHtml(p.id)}">
                <img src="${escapeHtml(capa)}" alt="${escapeHtml(p.titulo)}" style="background-color: #0b0f19;">
                <div class="scrolling-info">
                    <span class="tag" style="background: var(--cor-roxo); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase;">${escapeHtml(p.categoria)}</span>
                    <h3 style="color: var(--cor-ciano); margin: 10px 0 5px 0;">${escapeHtml(p.titulo)}</h3>
                    <p style="font-size: 0.85rem; color: #ccc; margin-bottom: 15px;">${escapeHtml(p.artista)}</p>
                    <p style="color: #fff; text-decoration: none; font-weight: bold;">▶ Ouvir Faixa</p>
                </div>
            </a>`;
    });
    htmlLote += `</div>`;

    // Duplica o HTML para criar o efeito de carrossel infinito
    track.innerHTML = htmlLote + htmlLote + htmlLote;

    setTimeout(() => {
        if (track.children[0])
            track.scrollLeft = track.children[0].offsetWidth + 20;
    }, 100);
}

export function initHeroParallax() {
    document.addEventListener("mousemove", (e) => {
        const logo = $$(".hero-logo");
        if (!logo) return;
        let x = (e.clientX / window.innerWidth - 0.5) * 20;
        let y = (e.clientY / window.innerHeight - 0.5) * 20;
        logo.style.transform = `translate(${x}px, ${y}px)`;
    });
}

export async function carregarComponente(id, arquivo) {
    const elemento = $(id);

    if (!elemento) return;

    try {
        const url = new URL(arquivo, location.href);
        if (url.origin !== location.origin) throw new Error("Componente externo bloqueado.");
        const response = await fetch(arquivo);
        if (!response.ok) throw new Error("Componente indisponível.");
        elemento.innerHTML = await response.text();
    } catch (err) {
        console.error(err);
    }
}

export function initParticles() {
    // Cria o container e adiciona ao body
    const container = document.createElement("div");
    container.id = "particles-container";
    document.body.appendChild(container);

    const particleCount = 35; // Quantidade de partículas na tela

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement("div");
        particle.classList.add("particle");

        // Randomizações para dar efeito natural
        const size = Math.random() * 4 + 2; // Tamanho entre 2px e 6px
        const posX = Math.random() * 100; // Posição horizontal (0% a 100% da tela)
        const duration = Math.random() * 15 + 10; // Duração da subida (10s a 25s)
        const delay = Math.random() * 15; // Atraso para não subirem todas juntas

        // Mistura as cores do seu tema (50% de chance de ser roxo)
        const isPurple = Math.random() > 0.5;
        if (isPurple) {
            particle.style.background = "var(--cor-roxo)";
            particle.style.boxShadow =
                "0 0 10px var(--cor-roxo), 0 0 20px var(--cor-roxo)";
        }

        // Aplica os estilos embutidos
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${posX}vw`;
        particle.style.setProperty("--duration", `${duration}s`);
        particle.style.animationDelay = `${delay}s`;

        container.appendChild(particle);
    }
}

export function renderizarFormularioParametros(parametrosString) {
    const container = $("render-parametros");
    if (!container) return;

    let html = "";
    // Separa os parâmetros que vêm da API (ex: "duracao,pessoas,prazo")
    const params = (typeof parametrosString === "string" ? parametrosString : "").split(",");

    params.forEach((param) => {
        const paramLimpo = param.trim();
        // Se existir um template para esse parâmetro, adiciona ao HTML
        if (Object.hasOwn(PARAM_TEMPLATES, paramLimpo)) {
            html += PARAM_TEMPLATES[paramLimpo].html;
        }
    });

    container.innerHTML = html;

    // --- LÓGICA ESPECIAL PARA O INSTRUMENTAL ABERTO ---
    // Faz o campo "Quantidade de Canais" aparecer apenas se a pessoa marcar "Sim"
    const selectInstAberto = $("inst_aberto");
    const containerCanais = $("container_canais_inst");

    if (selectInstAberto && containerCanais) {
        selectInstAberto.addEventListener("change", (e) => {
            containerCanais.hidden = e.target.value !== "sim";
            // Dispara um evento global de input para a calculadora refazer as contas imediatamente
            document.body.dispatchEvent(new Event("input", { bubbles: true }));
        });
    }
}
