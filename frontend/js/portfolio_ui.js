import { escapeHtml, safeURL } from "./utils/security.js";
import { $, $$$ } from "./utils/dom.js";

export function obterCapaInteligente(linkAudio, linkCapa) {
    if (safeURL(linkCapa)) return safeURL(linkCapa);
    const ytRegex =
        /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})/i;
    const match = safeURL(linkAudio).match(ytRegex);
    if (match && match[1])
        return `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg`;
    return "img/logo-principal.png";
}

export function renderizarProjetos(lista) {
    lista = Array.isArray(lista) ? lista.filter(p => p && typeof p === "object") : [];
    const container = $("render-portfolio");

    if (lista.length === 0) {
        container.innerHTML =
            "<p style='text-align:center; grid-column: 1/-1;'>Nenhum projeto encontrado.</p>";
        return;
    }

    // Cria uma variável para acumular o HTML
    let htmlAcumulado = "";

    lista.forEach((p) => {
        const capaFinal = obterCapaInteligente(p.link_audio, p.link_capa);
        const badgeHit = p.destaque
            ? `<span style="position:absolute; top:10px; right:10px; background:var(--cor-ciano); color:black; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:bold;">HIT 🔥</span>`
            : "";

        // Adiciona ao texto acumulado (sem mexer na tela ainda)
        htmlAcumulado += `
            <a href="${escapeHtml(safeURL(p.link_audio))}" target="_blank" rel="noopener noreferrer" class="portfolio-card glass-card" style="position:relative;">
                ${badgeHit}
                <img src="${escapeHtml(capaFinal)}" alt="${escapeHtml(p.titulo)}" style="background-color: #0b0f19;">
                <div class="portfolio-info">
                    <span class="tag" style="background: var(--cor-roxo); color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase;">${escapeHtml(p.categoria)}</span>
                    <h1 style="color: var(--cor-ciano); margin-top: 10px; font-size: 1.5rem">${escapeHtml(p.titulo)}</h1>
                    <p>${escapeHtml(p.artista)}</p>
                    <p style="font-size: 0.85rem; color: #888;">${escapeHtml(p.descricao)}</p>
                    <div style="color: var(--cor-ciano); font-weight: bold;">▶ Ouvir Faixa</div>
                </div>
            </a>
        `;
    });

    // Injeta na tela apenas UMA vez no final
    container.innerHTML = htmlAcumulado;
}

export function renderizarFiltros(projetos, callbackFiltrar) {
    projetos = Array.isArray(projetos) ? projetos.filter(p => p && typeof p.categoria === "string") : [];
    const categorias = [...new Set(projetos.map((p) => p.categoria))];
    const filterContainer = $("filtros-portfolio");

    filterContainer.innerHTML = `<button class="filter-btn active" data-cat="Todos">Todos</button>`;

    categorias.forEach((cat) => {
        if (cat.trim() !== "") {
            filterContainer.innerHTML += `<button class="filter-btn" data-cat="${escapeHtml(cat)}">${escapeHtml(cat)}</button>`;
        }
    });

    // Event Listeners para os botões de filtro
    filterContainer.querySelectorAll(".filter-btn").forEach((btn) => {
        btn.addEventListener("click", (e) => {
            $$$(".filter-btn").forEach((b) => b.classList.remove("active"));
            e.target.classList.add("active");
            callbackFiltrar(e.target.getAttribute("data-cat"));
        });
    });
}
