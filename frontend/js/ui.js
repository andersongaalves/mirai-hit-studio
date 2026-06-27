import { state } from './state.js';
import { getProjetos } from './api.js'; // <- Movido para o topo!
import { money } from "./utils/format.js";
import { $, $$, $$$ } from "./utils/dom.js";

export const PARAM_TEMPLATES = {
    "duracao": { html: `<div class="form-group"><label>Duração Estimada (s)</label><input type="number" id="duracao" value="180" min="30"></div>`, detalhe: (v) => `Duração: ${v}s` },
    "pessoas": { html: `<div class="form-group"><label>Artistas</label><input type="number" id="pessoas" value="1" min="1"></div>`, detalhe: (v) => `Artistas: ${v}` },
    "canais_voz": { html: `<div class="form-group"><label>Canais de Voz</label><input type="number" id="canais_voz" value="5" min="1"></div>`, detalhe: (v) => `Canais Voz: ${v}` },
    "inst_aberto": { html: `<div class="form-group"><label>Instrumental aberto (Stems)?</label><select id="inst_aberto"><option value="nao">Não</option><option value="sim">Sim</option></select></div><div class="form-group" id="container_canais_inst" style="display: none;"><label>Qtd Canais Instrumental</label><input type="number" id="canais_inst" value="1" min="1"></div>`, detalhe: (v, extra) => v === 'sim' ? `Inst Aberto: Sim (${extra} canais)` : `Inst Aberto: Não` },
    "melodias": { html: `<div class="form-group"><label>Melodias</label><input type="number" id="melodias" value="5" min="1"></div>`, detalhe: (v) => `Melodias: ${v}` },
    "instrumentacao": { html: `<div class="form-group"><label>Instrumentação</label><select id="instrumentacao"><option value="eletronicos">Eletrônicos</option><option value="hibridos">Híbridos</option><option value="gravados">100% Gravados</option></select></div>`, detalhe: (v) => `Inst: ${v}` },
    "exclusividade": { html: `<div class="form-group"><label>Exclusividade</label><select id="exclusividade"><option value="sim">Sim</option><option value="nao">Não (Lease)</option></select></div>`, detalhe: (v) => `Exclusivo: ${v}` },
    "revisoes": { html: `<div class="form-group"><label>Revisões</label><select id="revisoes"><option value="1">1</option><option value="2">2</option><option value="3">3</option></select></div>`, detalhe: (v) => `Revisões: ${v}` },
    "prazo": { html: `<div class="form-group"><label>Prazo</label><select id="prazo"><option value="normal">Normal</option><option value="urgente">Urgente</option><option value="express">Express</option></select></div>`, detalhe: (v) => `Prazo: ${v}` },
    "descricao": { html: `<div class="form-group"><label>Descrição</label><textarea id="descricao"></textarea></div>` },
    "guia": { html: `<div class="form-group"><label>Link da Guia</label><input type="text" id="guia"></div>` }
};

export function renderizarBotoes(servicos) {

    const boxAvulso = $("render-avulsos");
    const boxCombo = $("render-combos");

    if (!boxAvulso || !boxCombo) return;

    boxAvulso.innerHTML = "";
    boxCombo.innerHTML = "";

    servicos.forEach(srv => {

        const subtituloHTML = srv.subtitulo
            ? `
                <small class="service-subtitle">
                    ${srv.subtitulo}
                </small>
            `
            : "";

        const descricaoHTML = srv.descricao_servico
            ? `
                <div class="service-details">
                    <div class="service-description">
                        ${formatarDescricao(srv.descricao_servico)}
                    </div>

                    <div class="service-price">
                        A partir de

                        <strong>
                            ${money(srv.valor_base)}
                        </strong>
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
                    id="srv_${srv.id}"
                    value="${srv.id}"

                >

                <label for="srv_${srv.id}">
                    <span class="service-title">
                        ${srv.nome}
                    </span>

                    ${subtituloHTML}
                    ${descricaoHTML}
                </label>
            </div>
        `;

        if (srv.categoria === "combo") {
            boxCombo.innerHTML += html;
        }

        else {
            boxAvulso.innerHTML += html;
        }
    });

    if (boxAvulso.innerHTML)
        $("categoria-avulso").style.display = "block";

    if (boxCombo.innerHTML)
        $("categoria-combo").style.display = "block";
}

function formatarDescricao(texto){

    if(!texto) return "";

    return texto
        .replace(/\[titulo\]([\s\S]*?)\[\/titulo\]/g,
            "<h5>$1</h5>")

        .replace(/\[item\]([\s\S]*?)\[\/item\]/g,
            "<div class='service-item'>$1</div>")

        .replace(/\[beneficio\]([\s\S]*?)\[\/beneficio\]/g,
            "<div class='service-benefit'>$1</div>");
}

export function obterCapaInteligente(linkAudio, linkCapa) {
    if (linkCapa && linkCapa.trim() !== "") return linkCapa;
    const ytRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
    const match = linkAudio.match(ytRegex);
    if (match && match[1]) return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
    return "img/logo-principal.png"; 
}

// Renderiza o Carrossel da Home Page
export async function renderizarPortfolio() {
    const track = $('home-portfolio-track');
    if (!track) return; // Se não estiver na home, não faz nada

    const lista = await getProjetos();
    const listaHits = lista.filter(p => p.destaque === true);

    if (listaHits.length === 0) {
        track.innerHTML = "<p style='text-align:center; width: 100%; color: #aaa;'>Nenhum Hit adicionado. Marque projetos como 'Hit' no Admin.</p>";
        return;
    }

    let htmlLote = `<div class="carousel-lote" style="display: flex; gap: 20px; flex-shrink: 0;">`;
    
    listaHits.forEach(p => {
        const capa = obterCapaInteligente(p.link_audio, p.link_capa);
        htmlLote += `
            <a href="${p.link_audio}" target="_blank" class="scrolling-card glass-card">
                <img src="${capa}" alt="${p.titulo}" style="background-color: #0b0f19;">
                <div class="scrolling-info">
                    <span class="tag" style="background: var(--cor-roxo); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase;">${p.categoria}</span>
                    <h3 style="color: var(--cor-ciano); margin: 10px 0 5px 0;">${p.titulo}</h3>
                    <p style="font-size: 0.85rem; color: #ccc; margin-bottom: 15px;">${p.artista}</p>
                    <p style="color: #fff; text-decoration: none; font-weight: bold;">▶ Ouvir Faixa</p>
                </div>
            </a>`;
    });
    htmlLote += `</div>`;
    
    // Duplica o HTML para criar o efeito de carrossel infinito
    track.innerHTML = htmlLote + htmlLote + htmlLote;
    
    setTimeout(() => { 
        if(track.children[0]) track.scrollLeft = track.children[0].offsetWidth + 20; 
    }, 100);
}

export function initHeroParallax() {
    document.addEventListener("mousemove", (e) => {
        const logo = $$('.hero-logo');
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
        const response = await fetch(arquivo);
        elemento.innerHTML = await response.text();

    } catch (err) {
        console.error(err);
    }
}

export function initParticles() {
    // Cria o container e adiciona ao body
    const container = document.createElement('div');
    container.id = 'particles-container';
    document.body.appendChild(container);

    const particleCount = 35; // Quantidade de partículas na tela

    for (let i = 0; i < particleCount; i++) {
        const particle = document.createElement('div');
        particle.classList.add('particle');
        
        // Randomizações para dar efeito natural
        const size = Math.random() * 4 + 2; // Tamanho entre 2px e 6px
        const posX = Math.random() * 100; // Posição horizontal (0% a 100% da tela)
        const duration = Math.random() * 15 + 10; // Duração da subida (10s a 25s)
        const delay = Math.random() * 15; // Atraso para não subirem todas juntas
        
        // Mistura as cores do seu tema (50% de chance de ser roxo)
        const isPurple = Math.random() > 0.5;
        if (isPurple) {
            particle.style.background = 'var(--cor-roxo)';
            particle.style.boxShadow = '0 0 10px var(--cor-roxo), 0 0 20px var(--cor-roxo)';
        }

        // Aplica os estilos embutidos
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.left = `${posX}vw`;
        particle.style.setProperty('--duration', `${duration}s`);
        particle.style.animationDelay = `${delay}s`;

        container.appendChild(particle);
    }
}

export function renderizarFormularioParametros(parametrosString) {
    const container = $('render-parametros');
    if (!container || !parametrosString) return;

    let html = "";
    // Separa os parâmetros que vêm da API (ex: "duracao,pessoas,prazo")
    const params = parametrosString.split(',');

    params.forEach(param => {
        const paramLimpo = param.trim();
        // Se existir um template para esse parâmetro, adiciona ao HTML
        if (PARAM_TEMPLATES[paramLimpo]) {
            html += PARAM_TEMPLATES[paramLimpo].html;
        }
    });

    container.innerHTML = html;

    // --- LÓGICA ESPECIAL PARA O INSTRUMENTAL ABERTO ---
    // Faz o campo "Quantidade de Canais" aparecer apenas se a pessoa marcar "Sim"
    const selectInstAberto = $('inst_aberto');
    const containerCanais = $('container_canais_inst');
    
    if (selectInstAberto && containerCanais) {
        selectInstAberto.addEventListener('change', (e) => {
            containerCanais.style.display = e.target.value === 'sim' ? 'block' : 'none';
            // Dispara um evento global de input para a calculadora refazer as contas imediatamente
            document.body.dispatchEvent(new Event('input', { bubbles: true }));
        });
    }
}