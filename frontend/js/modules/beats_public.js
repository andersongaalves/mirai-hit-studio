// Public beat catalog (/beats) and beat pages (/beats/<id>): anyone can browse and
// listen to the tagged previews; buying goes through a client account (sign in or a
// free sign-up), then continues on the same beat in the client portal.
import { API_URL } from "../config.js";
import { AUTH_CONTEXTS } from "../admin/auth.js";
import { accessPath } from "../auth_next.js";
import { beatCard, beatPage } from "./beat_catalog.js";
import { mountBeatFilters } from "./beat_filters.js";
import { pausePreviews } from "./beat_preview.js";

const TITLE = "Beats para comprar e licenciar | Mirai Hit Studio";
let catalog = null;
let terms = null;

async function getJson(path, fallback) {
    let response;
    try { response = await fetch(`${API_URL}${path}`); } catch { throw new Error(fallback); }
    if (!response.ok) throw new Error(fallback);
    return response.json();
}

async function listen(id) {
    const response = await fetch(`${API_URL}/beats/publico/${id}/previa`);
    if (response.status === 429) throw new Error("Muitas prévias em pouco tempo. Aguarde alguns minutos.");
    if (!response.ok) throw new Error("Não foi possível carregar a prévia.");
    return response.blob();
}

function signedInClient() {
    try { return Boolean(localStorage.getItem(AUTH_CONTEXTS.cliente.storageKey)); } catch { return false; }
}

// The purchase continues on the same beat inside the client portal, with the license
// already highlighted; without a client session the sign-in page comes first.
function purchasePath(id, kind) {
    const next = `/cliente/beats/${id}?licenca=${encodeURIComponent(kind)}`;
    return signedInClient() ? next : accessPath(next, "comprar_beat");
}

function route() {
    const match = location.pathname.match(/^\/beats\/(\d+)\/?$/);
    return match ? { view: "beat", id: Number(match[1]) } : { view: "catalog" };
}

function show(view) {
    document.getElementById("beats-public-catalog").hidden = view !== "catalog";
    document.getElementById("beats-public-beat").hidden = view !== "beat";
}

function navigate(path, state = {}) {
    pausePreviews();
    history.pushState(state, "", path);
    render();
}

async function loadCatalog() {
    if (!catalog) catalog = getJson("/beats/publico", "Não foi possível carregar o catálogo de beats agora.").catch(error => {
        catalog = null;
        throw error;
    });
    return catalog;
}

async function loadTerms() {
    if (terms) return { items: terms, error: false };
    try { terms = await getJson("/beats/licencas", ""); return { items: terms, error: false }; } catch { return { items: [], error: true }; }
}

let rendered = null;
async function renderCatalog() {
    show("catalog");
    document.title = TITLE;
    const list = document.getElementById("beats-public-list");
    if (rendered) {
        mountBeatFilters(list, rendered.entries, { idPrefix: "public-beat-filter" });
        if (rendered.scroll !== null) { window.scrollTo(0, rendered.scroll); rendered.scroll = null; }
        return;
    }
    try {
        const beats = await loadCatalog();
        const cards = beats.map(beat => beatCard(beat, {
            href: `/beats/${beat.id}`,
            onOpen: () => { rendered.scroll = window.scrollY; navigate(`/beats/${beat.id}`, { fromCatalog: true }); },
            loadPreview: () => listen(beat.id),
            lazy: true,
        }));
        list.replaceChildren(...cards);
        rendered = { entries: beats.map((beat, index) => ({ beat, card: cards[index] })), scroll: null };
        mountBeatFilters(list, rendered.entries, { idPrefix: "public-beat-filter" });
        if (!beats.length) list.textContent = "Nenhum beat disponível no momento.";
    } catch (error) {
        const message = document.createElement("p"); message.className = "beat-page__warning"; message.textContent = error.message;
        list.replaceChildren(message);
    }
}

function backToCatalog() {
    if (history.state?.fromCatalog) history.back();
    else navigate("/beats");
}

let request = 0;
async function renderBeat(id) {
    const current = ++request;
    show("beat");
    const host = document.getElementById("beats-public-beat");
    host.textContent = "Carregando beat...";
    window.scrollTo(0, 0);
    try {
        const [beats, loaded] = await Promise.all([loadCatalog(), loadTerms()]);
        if (current !== request) return;
        const beat = beats.find(item => item.id === id);
        if (!beat) {
            const back = document.createElement("a"); back.className = "btn-outline beat-page__back"; back.href = "/beats"; back.textContent = "Ver o catálogo";
            const missing = document.createElement("p"); missing.className = "beat-page__lead"; missing.textContent = "Este beat não está mais disponível no catálogo.";
            host.replaceChildren(back, missing);
            return;
        }
        document.title = `${beat.titulo} · prod. ${beat.produtor} | Mirai Hit Studio`;
        const note = document.createElement("p");
        note.className = "beat-page__purchase-note";
        if (signedInClient()) {
            note.textContent = "A compra continua na sua conta de cliente, com a licença escolhida.";
        } else {
            const signup = document.createElement("a"); signup.href = "/cadastro"; signup.textContent = "crie uma conta grátis";
            const signin = document.createElement("a"); signin.href = accessPath(`/cliente/beats/${beat.id}`, "comprar_beat"); signin.textContent = "entre";
            note.append("Para comprar, ", signin, " na sua conta de cliente ou ", signup, ". Depois do login você volta para este beat.");
        }
        host.replaceChildren(beatPage(beat, {
            terms: loaded.items,
            termsError: loaded.error,
            loadPreview: () => listen(beat.id),
            lazy: true,
            buyLink: kind => purchasePath(beat.id, kind),
            purchaseNote: note,
            onBack: backToCatalog,
        }));
    } catch (error) {
        if (current !== request) return;
        const message = document.createElement("p"); message.className = "beat-page__warning"; message.textContent = error.message;
        const back = document.createElement("a"); back.className = "btn-outline beat-page__back"; back.href = "/beats"; back.textContent = "Ver o catálogo";
        host.replaceChildren(back, message);
    }
}

function render() {
    const current = route();
    if (current.view === "beat") renderBeat(current.id);
    else renderCatalog();
}

export function initBeatsPage() {
    // A client who is already signed in goes straight to the portal; nobody else sees a sign-in prompt twice.
    if (signedInClient()) document.querySelector("[data-beats-account]")?.setAttribute("hidden", "");
    window.addEventListener("popstate", () => { pausePreviews(); render(); });
    render();
}
