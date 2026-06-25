import { state } from './state.js';
import { $, $$, $$$ } from "./utils/dom.js";

export function obterCapaInteligente(linkAudio, linkCapa) {
    if (linkCapa && linkCapa.trim() !== "") return linkCapa;
    const ytRegex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
    const match = linkAudio.match(ytRegex);
    if (match && match[1]) return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
    return "img/logo-principal.png"; 
}

export function renderizarProjetos(lista) {
    const container = $('render-portfolio');
    
    if(lista.length === 0) {
        container.innerHTML = "<p style='text-align:center; grid-column: 1/-1;'>Nenhum projeto encontrado.</p>";
        return;
    }

    // Cria uma variável para acumular o HTML
    let htmlAcumulado = "";

    lista.forEach(p => {
        const capaFinal = obterCapaInteligente(p.link_audio, p.link_capa);
        const badgeHit = p.destaque ? `<span style="position:absolute; top:10px; right:10px; background:var(--cor-ciano); color:black; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:bold;">HIT 🔥</span>` : "";

        // Adiciona ao texto acumulado (sem mexer na tela ainda)
        htmlAcumulado += `
            <a href="${p.link_audio}" target="_blank" class="portfolio-card glass-card" style="position:relative;">
                ${badgeHit}
                <img src="${capaFinal}" alt="${p.titulo}" style="background-color: #0b0f19;">
                <div class="portfolio-info">
                    <span class="tag" style="background: var(--cor-roxo); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase;">${p.categoria}</span>
                    <h1 style="color: var(--cor-ciano); margin-top: 10px; font-size: 1.5rem">${p.titulo}</h1>
                    <p>${p.artista}</p>
                    <p style="font-size: 0.85rem; color: #888;">${p.descricao}</p>
                    <div style="color: var(--cor-ciano); font-weight: bold;">▶ Ouvir Faixa</div>
                </div>
            </a>
        `;
    });

    // Injeta na tela apenas UMA vez no final
    container.innerHTML = htmlAcumulado;
}

export function renderizarFiltros(projetos, callbackFiltrar) {
    const categorias = [...new Set(projetos.map(p => p.categoria))];
    const filterContainer = $('filtros-portfolio');
    
    filterContainer.innerHTML = `<button class="filter-btn active" data-cat="Todos">Todos</button>`;
    
    categorias.forEach(cat => {
        if(cat.trim() !== "") {
            filterContainer.innerHTML += `<button class="filter-btn" data-cat="${cat}">${cat}</button>`;
        }
    });

    // Event Listeners para os botões de filtro
    filterContainer.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            $$$('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            callbackFiltrar(e.target.getAttribute('data-cat'));
        });
    });
}