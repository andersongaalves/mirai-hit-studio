// "Arquivos": every stored file in one place. Filters and grouping on top (type, role,
// storage service, protection), a folder tree, a detailed list with thumbnails and a
// details panel with download and (double-confirmed) deletion. Files that must stay
// explain why and cannot be deleted from here.
import { authFetch } from "../auth.js";
import * as Notify from "../../utils/notifications.js";
import { confirmarAcao } from "../../modules/confirm_dialog.js";

const CATEGORIAS = { audio: "Áudio", pdf: "PDF", imagem: "Imagem", compactado: "Compactado", outro: "Outro" };
const formatDay = value => (value ? new Date(value).toLocaleDateString("pt-BR") : "—");
const CATEGORIAS_PLURAL = { audio: "Áudios", pdf: "PDFs", imagem: "Imagens", compactado: "Compactados", outro: "Outros" };
const AGRUPAR = { nenhum: "Sem agrupar", funcao: "Função", categoria: "Tipo", servico: "Serviço", pasta: "Pasta", contexto: "Vínculo" };
const ORDENS = { recentes: "Mais recentes", antigos: "Mais antigos", maiores: "Maiores", nome: "Nome (A–Z)" };
const CONTEXTOS = { producao: "Produção", beat: "Beat", projeto: "Projeto do portfólio", proposta: "Proposta", tag: "Tag de áudio" };
const DETALHES = {
    versao: "Versão",
    etapa_id: "Etapa",
    estado: "Processamento",
    status: "Status do beat",
    slot: "Arquivo do beat",
    duracao_s: "Duração",
    lufs_integrado: "Volume (LUFS integrados)",
    comprimido_em: "Comprimido em",
    visivel_produtor: "Visível ao produtor",
    visivel_cliente: "Visível ao cliente",
    observacao: "Observação",
    sha256: "SHA-256",
};
const THUMB_LIMIT = 4 * 1024 * 1024;
const EMPTY_FILTERS = { busca: "", categoria: "", funcao: "", servico: "", protegido: "", pasta: "" };

const state = {
    data: null,
    filters: { ...EMPTY_FILTERS },
    agrupar: "nenhum",
    ordem: "recentes",
    selected: null,
    bound: false,
    loading: null,
    blobs: new Map(),
    observer: null,
};
const byId = id => document.getElementById(id);

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "" && text !== null && text !== undefined) node.textContent = String(text);
    return node;
}

function button(text, className = "btn-small", attrs = {}) {
    const node = el("button", className, text);
    node.type = "button";
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
}

export function formatBytes(value) {
    if (value === null || value === undefined) return "—";
    const units = ["B", "KB", "MB", "GB"];
    let size = Number(value) || 0;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
    const digits = unit === 0 || size >= 100 ? 0 : 1;
    return `${size.toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: 0 })} ${units[unit]}`;
}

const formatDate = value => (value
    ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
const plural = (count, one, many) => `${count.toLocaleString("pt-BR")} ${count === 1 ? one : many}`;

async function data(response, fallback) {
    if (response.status === 204) return null;
    const body = await response.json().catch(() => null);
    if (!response.ok) {
        const detail = body?.detail;
        const message = typeof detail === "string" ? detail : "";
        const error = new Error(message || fallback);
        error.status = response.status;
        throw error;
    }
    return body;
}

// ---------- Icons ----------

const ICON_PATHS = {
    audio: "M3 10v4M7 7v10M11 4v16M15 8v8M19 10v4",
    pdf: "M7 3h7l5 5v13H7V3zm7 1.5V9h4.5M9.5 13h5M9.5 16h5",
    imagem: "M4 5h16v14H4V5zm0 11 4.5-4.5 3.5 3.5 2.5-2.5L20 17M15.5 9.5a1.5 1.5 0 1 0 0-.01",
    compactado: "M6 3h12v18H6V3zm5 0v2h2v2h-2v2h2v2h-2v3",
    outro: "M7 3h7l5 5v13H7V3zm7 1.5V9h4.5",
    pasta: "M3 6h6l2 2h10v11H3V6z",
    cadeado: "M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5V11z",
};

function icon(name, className = "files-icon") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", className);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", ICON_PATHS[name] || ICON_PATHS.outro);
    svg.append(path);
    return svg;
}

// ---------- Thumbnails ----------

async function blobFor(entry) {
    if (state.blobs.has(entry.ref)) return state.blobs.get(entry.ref);
    const response = await authFetch(`/admin/arquivos/conteudo?ref=${encodeURIComponent(entry.ref)}`);
    if (!response.ok) throw new Error("Arquivo indisponível no armazenamento agora.");
    const url = URL.createObjectURL(await response.blob());
    state.blobs.set(entry.ref, url);
    return url;
}

function thumbnail(entry) {
    const box = el("span", `files-thumb files-thumb--${entry.categoria}`);
    const source = entry.miniatura
        || (entry.categoria === "imagem" && entry.baixar === "api" && (entry.tamanho_bytes || 0) <= THUMB_LIMIT ? "lazy" : "");
    box.append(icon(entry.categoria));
    if (!source) return box;
    const img = document.createElement("img");
    img.alt = "";
    img.loading = "lazy";
    img.decoding = "async";
    img.addEventListener("load", () => box.classList.add("is-loaded"));
    img.addEventListener("error", () => img.remove());
    if (source === "lazy") {
        img.dataset.ref = entry.ref;
        state.observer?.observe(img);
    } else {
        img.referrerPolicy = "no-referrer";
        img.src = source;
    }
    box.append(img);
    return box;
}

function observeThumbnails() {
    state.observer?.disconnect();
    if (!("IntersectionObserver" in window)) { state.observer = null; return; }
    state.observer = new IntersectionObserver(items => {
        items.filter(item => item.isIntersecting).forEach(item => {
            const img = item.target;
            state.observer.unobserve(img);
            const entry = state.data?.arquivos.find(file => file.ref === img.dataset.ref);
            if (entry) blobFor(entry).then(url => { img.src = url; }).catch(() => img.remove());
        });
    }, { rootMargin: "120px" });
}

// ---------- Filtering and grouping ----------

const pathOf = entry => entry.pasta.join("/");

export function filtrar(entries, filters) {
    const words = String(filters.busca || "").toLowerCase().split(/\s+/).filter(Boolean);
    return entries.filter(entry => {
        if (filters.categoria && entry.categoria !== filters.categoria) return false;
        if (filters.funcao && entry.funcao !== filters.funcao) return false;
        if (filters.servico && entry.servico !== filters.servico) return false;
        if (filters.protegido === "sim" && !entry.protegido) return false;
        if (filters.protegido === "nao" && entry.protegido) return false;
        if (filters.pasta) {
            const path = pathOf(entry);
            if (path !== filters.pasta && !path.startsWith(`${filters.pasta}/`)) return false;
        }
        if (words.length) {
            const text = `${entry.nome} ${entry.contexto?.titulo || ""} ${entry.funcao} ${entry.servico}`.toLowerCase();
            if (!words.every(word => text.includes(word))) return false;
        }
        return true;
    });
}

export function ordenar(entries, ordem) {
    const list = [...entries];
    if (ordem === "maiores") return list.sort((a, b) => (b.tamanho_bytes || 0) - (a.tamanho_bytes || 0));
    if (ordem === "nome") return list.sort((a, b) => a.nome.localeCompare(b.nome, "pt-BR"));
    const time = entry => (entry.criado_em ? new Date(entry.criado_em).getTime() : 0);
    if (ordem === "antigos") return list.sort((a, b) => time(a) - time(b));
    return list.sort((a, b) => time(b) - time(a));
}

function groupKey(entry, by) {
    if (by === "categoria") return CATEGORIAS[entry.categoria] || entry.categoria;
    if (by === "funcao") return entry.funcao;
    if (by === "servico") return entry.servico;
    if (by === "pasta") return entry.pasta.join(" / ");
    if (by === "contexto") {
        const context = entry.contexto || {};
        return `${CONTEXTOS[context.tipo] || "Outro"}${context.id ? ` #${context.id}` : ""}${context.titulo ? ` · ${context.titulo}` : ""}`;
    }
    return "";
}

export function agrupar(entries, by) {
    if (!by || by === "nenhum") return [{ titulo: "", arquivos: entries }];
    const groups = new Map();
    entries.forEach(entry => {
        const key = groupKey(entry, by);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(entry);
    });
    return [...groups.entries()]
        .map(([titulo, arquivos]) => ({ titulo, arquivos }))
        .sort((a, b) => (by === "pasta" || by === "contexto"
            ? a.titulo.localeCompare(b.titulo, "pt-BR") : b.arquivos.length - a.arquivos.length));
}

const sumSize = entries => entries.reduce((total, entry) => total + (entry.tamanho_bytes || 0), 0);

// ---------- Rendering ----------

function summary(root) {
    const { total, totais, compressao, arquivos } = state.data;
    const wrap = el("div", "files-summary");
    const all = button("", "files-stat", { "aria-pressed": String(!state.filters.categoria) });
    all.append(el("strong", "", plural(total.arquivos, "arquivo", "arquivos")),
        el("span", "", `${formatBytes(total.tamanho_bytes)} conhecidos`));
    all.addEventListener("click", () => setFilter("categoria", ""));
    wrap.append(all);
    Object.entries(CATEGORIAS_PLURAL).forEach(([key, label]) => {
        const count = totais[key]?.arquivos || 0;
        if (!count) return;
        const chip = button("", `files-stat files-stat--${key}`, { "aria-pressed": String(state.filters.categoria === key) });
        const name = count === 1 ? (key === "pdf" ? "PDF" : CATEGORIAS[key]) : label;
        chip.append(icon(key, "files-stat__icon"), el("strong", "", `${count.toLocaleString("pt-BR")} ${name}`),
            el("span", "", formatBytes(totais[key].tamanho_bytes)));
        chip.addEventListener("click", () => setFilter("categoria", state.filters.categoria === key ? "" : key));
        wrap.append(chip);
    });
    const locked = arquivos.filter(entry => entry.protegido).length;
    const note = el("p", "files-summary__note");
    note.append(icon("cadeado", "files-inline-icon"),
        ` ${plural(locked, "arquivo protegido", "arquivos protegidos")} (não podem ser apagados) · `
        + `${plural(arquivos.length - locked, "livre", "livres")} para excluir`);
    root.append(wrap, note);
    if (compressao?.previas_entregues) {
        const card = el("p", "files-compression");
        card.setAttribute("role", "status");
        const done = compressao.comprimidas;
        card.textContent = `Prévias de produções entregues: ${done} de ${compressao.previas_entregues} já comprimidas `
            + `em MP3 ${String(compressao.bitrate).replace("k", " kbps")}`
            + (compressao.pendentes ? ` · ${compressao.pendentes} na fila (o servidor comprime uma por vez quando está livre).` : ".");
        root.append(card);
    }
}

function select(id, label, options, value, onChange) {
    const field = el("label", "files-field");
    field.append(el("span", "", label));
    const input = document.createElement("select");
    input.id = id;
    options.forEach(([optionValue, text]) => {
        const option = el("option", "", text);
        option.value = optionValue;
        input.append(option);
    });
    input.value = value;
    input.addEventListener("change", () => onChange(input.value));
    field.append(input);
    return field;
}

function toolbar(root) {
    const { arquivos, funcoes, servicos } = state.data;
    const bar = el("div", "files-toolbar");
    bar.setAttribute("role", "search");
    const search = el("label", "files-field files-field--search");
    search.append(el("span", "", "Buscar"));
    const input = document.createElement("input");
    input.type = "search";
    input.id = "arquivos-busca";
    input.placeholder = "Nome, produção, beat…";
    input.value = state.filters.busca;
    let timer = 0;
    input.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => setFilter("busca", input.value, { keepFocus: "arquivos-busca" }), 180);
    });
    search.append(input);
    const count = key => arquivos.filter(entry => entry.categoria === key).length;
    bar.append(
        search,
        select("arquivos-tipo", "Tipo", [["", "Todos os tipos"],
            ...Object.entries(CATEGORIAS).filter(([key]) => count(key)).map(([key, label]) => [key, `${label} (${count(key)})`])],
        state.filters.categoria, value => setFilter("categoria", value)),
        select("arquivos-funcao", "Função", [["", "Todas as funções"],
            ...funcoes.map(item => [item.valor, `${item.valor} (${item.arquivos})`])],
        state.filters.funcao, value => setFilter("funcao", value)),
        select("arquivos-servico", "Serviço", [["", "Todos os serviços"],
            ...servicos.map(item => [item.valor, `${item.valor} (${item.arquivos})`])],
        state.filters.servico, value => setFilter("servico", value)),
        select("arquivos-protegido", "Proteção", [["", "Todos"], ["sim", "Protegidos"], ["nao", "Livres para excluir"]],
            state.filters.protegido, value => setFilter("protegido", value)),
        select("arquivos-agrupar", "Agrupar por", Object.entries(AGRUPAR), state.agrupar, value => {
            state.agrupar = value;
            remember();
            render();
        }),
        select("arquivos-ordem", "Ordenar", Object.entries(ORDENS), state.ordem, value => {
            state.ordem = value;
            remember();
            render();
        }),
    );
    const active = Object.entries(state.filters).some(([, value]) => value);
    if (active) {
        const clear = button("Limpar filtros", "btn-small files-clear");
        clear.addEventListener("click", () => {
            state.filters = { ...EMPTY_FILTERS };
            render();
        });
        bar.append(clear);
    }
    root.append(bar);
}

function folderTree() {
    const nav = el("nav", "files-tree");
    nav.setAttribute("aria-label", "Pastas");
    nav.append(el("h2", "files-tree__title", "Pastas"));
    const pastas = state.data.pastas;
    const children = parent => pastas.filter(item => item.nivel === (parent ? parent.nivel + 1 : 1)
        && (!parent || item.caminho.startsWith(`${parent.caminho}/`)));
    const node = item => {
        const li = el("li");
        const kids = children(item);
        const pick = button("", "files-tree__item", { "aria-current": String(state.filters.pasta === item.caminho) });
        pick.append(icon("pasta", "files-inline-icon"), el("span", "files-tree__name", item.nome),
            el("span", "files-tree__count", item.arquivos));
        pick.title = `${item.caminho} · ${formatBytes(item.tamanho_bytes)}`;
        pick.addEventListener("click", () => setFilter("pasta", state.filters.pasta === item.caminho ? "" : item.caminho));
        if (!kids.length) {
            li.append(pick);
            return li;
        }
        const details = document.createElement("details");
        details.open = item.nivel === 1 ? state.filters.pasta.startsWith(item.caminho) || pastas.length < 40
            : state.filters.pasta.startsWith(item.caminho);
        const summaryEl = el("summary");
        summaryEl.append(pick);
        const list = el("ul");
        kids.forEach(kid => list.append(node(kid)));
        details.append(summaryEl, list);
        li.append(details);
        return li;
    };
    const list = el("ul", "files-tree__list");
    const all = el("li");
    const allButton = button("", "files-tree__item", { "aria-current": String(!state.filters.pasta) });
    allButton.append(icon("pasta", "files-inline-icon"), el("span", "files-tree__name", "Todos os arquivos"),
        el("span", "files-tree__count", state.data.arquivos.length));
    allButton.addEventListener("click", () => setFilter("pasta", ""));
    all.append(allButton);
    list.append(all);
    children(null).forEach(item => list.append(node(item)));
    nav.append(list);
    return nav;
}

function row(entry) {
    const tr = el("tr", "files-row");
    tr.tabIndex = 0;
    tr.dataset.ref = entry.ref;
    tr.setAttribute("aria-label", `${entry.nome}: ${entry.funcao}, ${entry.servico}. Abrir detalhes`);
    if (entry.criado_em) tr.title = `Enviado em ${formatDate(entry.criado_em)}`;
    if (state.selected === entry.ref) tr.classList.add("is-selected");
    const name = el("td", "files-cell files-cell--name");
    const text = el("div", "files-name");
    text.append(el("strong", "", entry.nome), el("span", "files-path", entry.pasta.join(" / ")));
    name.append(thumbnail(entry), text);
    const lock = el("td", "files-cell files-cell--lock");
    if (entry.protegido) {
        const badge = el("span", "files-lock");
        badge.append(icon("cadeado", "files-inline-icon"), el("span", "sr-only", "Protegido"));
        badge.title = entry.motivo_protecao;
        lock.append(badge);
    }
    const cell = (className, value, label) => {
        const td = el("td", `files-cell ${className}`, value);
        td.dataset.label = label;
        return td;
    };
    tr.append(
        name,
        cell("files-cell--role", entry.funcao, "Função"),
        cell("files-cell--type", CATEGORIAS[entry.categoria] || entry.categoria, "Tipo"),
        cell("files-cell--service", entry.servico, "Serviço"),
        cell("files-cell--size", formatBytes(entry.tamanho_bytes), "Tamanho"),
        cell("files-cell--date", formatDay(entry.criado_em), "Data"),
        lock,
    );
    const openIt = () => openDetails(entry.ref);
    tr.addEventListener("click", openIt);
    tr.addEventListener("keydown", event => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openIt();
        }
    });
    return tr;
}

function list(entries) {
    const main = el("div", "files-main");
    const groups = agrupar(ordenar(entries, state.ordem), state.agrupar);
    const status = el("p", "files-results", entries.length
        ? `${plural(entries.length, "arquivo", "arquivos")} · ${formatBytes(sumSize(entries))}`
            + (groups.length > 1 ? ` · ${plural(groups.length, "grupo", "grupos")}` : "")
        : "Nenhum arquivo com esses filtros.");
    status.id = "arquivos-resultado";
    status.setAttribute("aria-live", "polite");
    main.append(status);
    if (!entries.length) return main;
    const table = el("table", "files-table");
    table.setAttribute("aria-describedby", "arquivos-resultado");
    const head = el("thead");
    const headRow = el("tr");
    ["Arquivo", "Função", "Tipo", "Serviço", "Tamanho", "Data", ""].forEach(label => {
        const th = el("th", "", label);
        th.scope = "col";
        headRow.append(th);
    });
    head.append(headRow);
    table.append(head);
    groups.forEach(group => {
        const body = el("tbody");
        if (group.titulo) {
            const header = el("tr", "files-group");
            const th = el("th", "", "");
            th.colSpan = 7;
            th.scope = "rowgroup";
            th.append(el("strong", "", group.titulo),
                el("span", "", ` · ${plural(group.arquivos.length, "arquivo", "arquivos")} · ${formatBytes(sumSize(group.arquivos))}`));
            header.append(th);
            body.append(header);
        }
        group.arquivos.forEach(entry => body.append(row(entry)));
        table.append(body);
    });
    main.append(table);
    return main;
}

// ---------- Details ----------

function detailValue(key, value) {
    if (value === null || value === undefined || value === "") return null;
    if (typeof value === "boolean") return value ? "Sim" : "Não";
    if (key === "comprimido_em") return formatDate(value);
    if (key === "duracao_s") return `${Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`;
    if (key === "lufs_integrado") return `${Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} LUFS`;
    if (key === "versao") return `v${value}`;
    if (key === "etapa_id") return `#${value}`;
    return String(value);
}

function definition(listEl, term, value, className = "") {
    if (value === null || value === undefined || value === "") return;
    const wrap = el("div", `files-def ${className}`);
    wrap.append(el("dt", "", term), el("dd", "", value));
    listEl.append(wrap);
}

async function download(entry, trigger) {
    if (entry.baixar === "url") {
        if (entry.url) window.open(entry.url, "_blank", "noopener");
        return;
    }
    trigger.disabled = true;
    try {
        const url = await blobFor(entry);
        const link = document.createElement("a");
        link.href = url;
        link.download = entry.nome;
        document.body.append(link);
        link.click();
        link.remove();
    } catch (error) {
        Notify.error(error.message);
    } finally {
        trigger.disabled = false;
    }
}

function preview(entry) {
    const box = el("div", "files-preview");
    if (entry.categoria === "imagem" && (entry.miniatura || entry.url)) {
        const img = document.createElement("img");
        img.alt = `Prévia de ${entry.nome}`;
        img.referrerPolicy = "no-referrer";
        img.src = entry.url || entry.miniatura;
        box.append(img);
        return box;
    }
    if (entry.categoria === "audio" && entry.baixar === "url" && entry.url) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.preload = "none";
        audio.src = entry.url;
        box.append(audio);
        return box;
    }
    const canLoad = entry.baixar === "api" && ["audio", "imagem"].includes(entry.categoria);
    box.append(entry.miniatura ? thumbnail(entry) : icon(entry.categoria, "files-preview__icon"));
    if (canLoad) {
        const load = button(entry.categoria === "audio" ? "Ouvir aqui" : "Ver imagem", "btn-small");
        load.addEventListener("click", async () => {
            load.disabled = true;
            try {
                const url = await blobFor(entry);
                const media = document.createElement(entry.categoria === "audio" ? "audio" : "img");
                if (entry.categoria === "audio") {
                    media.controls = true;
                    media.autoplay = true;
                } else {
                    media.alt = `Prévia de ${entry.nome}`;
                }
                media.src = url;
                box.replaceChildren(media);
            } catch (error) {
                Notify.error(error.message);
                load.disabled = false;
            }
        });
        box.append(load);
    }
    return box;
}

function consequences(entry) {
    const items = [`Sai do ${entry.servico} e não pode ser recuperado.`];
    if (entry.ref.startsWith("arq:")) {
        items.push("Some do portal do produtor e do cliente desta produção.");
        if (entry.funcao === "Prévia") items.push("A versão com tag desta prévia sai junto.");
    }
    if (entry.ref.startsWith("audiotag:")) items.push("A tag deixa de existir para novas prévias.");
    items.push("A exclusão fica registrada na auditoria com o motivo.");
    return items;
}

async function remove(entry) {
    const result = await confirmarAcao({
        titulo: `Excluir "${entry.nome}"?`,
        mensagem: `${entry.funcao} · ${CATEGORIAS[entry.categoria] || entry.categoria} · ${formatBytes(entry.tamanho_bytes)}`,
        consequencias: consequences(entry),
        palavra: "EXCLUIR",
        botao: "Excluir arquivo",
        motivo: { rotulo: "Motivo (fica na auditoria)", minimo: 3 },
    });
    if (!result) return;
    try {
        await data(await authFetch(`/admin/arquivos?ref=${encodeURIComponent(entry.ref)}`, {
            method: "DELETE",
            body: JSON.stringify({ motivo: result.motivo }),
        }), "Não foi possível excluir o arquivo.");
        Notify.success("Arquivo excluído.");
        closeDetails();
        await load({ force: true });
    } catch (error) {
        Notify.error(error.message);
    }
}

function closeDetails({ restoreFocus = true } = {}) {
    const ref = state.selected;
    state.selected = null;
    const panel = byId("arquivos-detalhes");
    if (panel) {
        panel.hidden = true;
        panel.replaceChildren();
    }
    document.querySelectorAll(".files-row.is-selected").forEach(item => item.classList.remove("is-selected"));
    if (restoreFocus && ref) document.querySelector(`.files-row[data-ref="${CSS.escape(ref)}"]`)?.focus();
}

function openDetails(ref) {
    const entry = state.data?.arquivos.find(item => item.ref === ref);
    const panel = byId("arquivos-detalhes");
    if (!entry || !panel) return;
    state.selected = ref;
    document.querySelectorAll(".files-row").forEach(item => item.classList.toggle("is-selected", item.dataset.ref === ref));
    const head = el("div", "files-details__head");
    const title = el("h2", "files-details__title", entry.nome);
    title.id = "arquivos-detalhes-titulo";
    title.tabIndex = -1;
    const close = button("×", "files-details__close", { "aria-label": "Fechar detalhes" });
    close.addEventListener("click", () => closeDetails());
    head.append(title, close);

    const chips = el("div", "files-chips");
    chips.append(el("span", "files-chip files-chip--role", entry.funcao),
        el("span", `files-chip files-chip--${entry.categoria}`, CATEGORIAS[entry.categoria] || entry.categoria),
        el("span", "files-chip files-chip--service", entry.servico));

    const facts = el("dl", "files-defs");
    definition(facts, "Serviço de armazenamento", entry.servico);
    definition(facts, "Função", entry.funcao);
    definition(facts, "Tipo", `${CATEGORIAS[entry.categoria] || entry.categoria} · ${entry.mime_type}`);
    definition(facts, "Tamanho", entry.tamanho_bytes === null || entry.tamanho_bytes === undefined
        ? "Não registrado" : `${formatBytes(entry.tamanho_bytes)} (${Number(entry.tamanho_bytes).toLocaleString("pt-BR")} bytes)`);
    definition(facts, "Enviado em", entry.criado_em ? formatDate(entry.criado_em) : "Não registrado");
    const context = entry.contexto || {};
    definition(facts, "Vinculado a", `${CONTEXTOS[context.tipo] || "Outro"}${context.id ? ` #${context.id}` : ""}`
        + `${context.titulo ? ` · ${context.titulo}` : ""}`);
    definition(facts, "Pasta", entry.pasta.join(" / "));
    definition(facts, "Download", entry.baixar === "url" ? "Link público" : "Pelo Admin (privado)");

    const protection = el("p", entry.protegido ? "files-protection is-locked" : "files-protection");
    protection.append(icon(entry.protegido ? "cadeado" : "outro", "files-inline-icon"),
        entry.protegido ? ` Protegido: ${entry.motivo_protecao}` : " Livre para excluir.");

    const extra = el("dl", "files-defs files-defs--extra");
    Object.entries(DETALHES).forEach(([key, label]) => {
        const value = detailValue(key, entry.detalhes?.[key]);
        if (value !== null) definition(extra, label, value, key === "sha256" ? "files-def--mono" : "");
    });

    const actions = el("div", "files-details__actions");
    const get = button(entry.baixar === "url" ? "Abrir link" : "Baixar", "btn-small files-download");
    get.disabled = entry.baixar === "url" && !entry.url;
    get.addEventListener("click", () => download(entry, get));
    const del = button("Excluir", "btn-small files-delete");
    if (entry.protegido) {
        del.disabled = true;
        del.title = entry.motivo_protecao;
        del.setAttribute("aria-describedby", "arquivos-protecao");
    }
    protection.id = "arquivos-protecao";
    del.addEventListener("click", () => remove(entry));
    actions.append(get, del);

    panel.replaceChildren(head, preview(entry), chips, facts, protection);
    if (extra.childElementCount) {
        const more = el("details", "files-more");
        more.open = true;
        more.append(el("summary", "", "Mais informações"), extra);
        panel.append(more);
    }
    panel.append(actions);
    panel.hidden = false;
    title.focus({ preventScroll: false });
}

// ---------- State ----------

function remember() {
    try {
        localStorage.setItem("mirai.admin.arquivos", JSON.stringify({ agrupar: state.agrupar, ordem: state.ordem }));
    } catch { /* storage unavailable: preferences just reset */ }
}

function restore() {
    try {
        const saved = JSON.parse(localStorage.getItem("mirai.admin.arquivos") || "{}");
        if (AGRUPAR[saved.agrupar]) state.agrupar = saved.agrupar;
        if (ORDENS[saved.ordem]) state.ordem = saved.ordem;
    } catch { /* ignore */ }
}

function setFilter(key, value, { keepFocus = "" } = {}) {
    state.filters[key] = value;
    render();
    if (keepFocus) {
        const input = byId(keepFocus);
        input?.focus();
        input?.setSelectionRange?.(input.value.length, input.value.length);
    }
}

function render() {
    const root = byId("arquivos-content");
    if (!root || !state.data) return;
    observeThumbnails();
    const selected = state.selected;
    root.replaceChildren();
    summary(root);
    toolbar(root);
    const layout = el("div", "files-layout");
    const entries = filtrar(state.data.arquivos, state.filters);
    layout.append(folderTree(), list(entries));
    root.append(layout);
    if (selected && state.data.arquivos.some(entry => entry.ref === selected)) openDetails(selected);
    else closeDetails({ restoreFocus: false });
}

async function load({ force = false } = {}) {
    const root = byId("arquivos-content");
    if (!root) return;
    if (state.loading) return state.loading;
    if (!state.data || force) {
        if (!state.data) root.replaceChildren(el("p", "files-results", "Carregando arquivos…"));
        state.loading = authFetch("/admin/arquivos")
            .then(response => data(response, "Não foi possível carregar os arquivos."))
            .then(body => { state.data = body; })
            .finally(() => { state.loading = null; });
        try {
            await state.loading;
        } catch (error) {
            root.replaceChildren(el("p", "files-results files-results--error", error.message));
            return;
        }
    }
    render();
}

export async function initArquivos() {
    if (!state.bound) {
        state.bound = true;
        restore();
        byId("arquivos-atualizar")?.addEventListener("click", () => load({ force: true }));
        document.addEventListener("keydown", event => {
            if (event.key === "Escape" && state.selected && !document.querySelector(".confirm-dialog-overlay")) closeDetails();
        });
    }
    await load({ force: true });
}

document.addEventListener("admin:logout", () => {
    state.data = null;
    state.selected = null;
    state.filters = { ...EMPTY_FILTERS };
    state.observer?.disconnect();
    state.blobs.forEach(url => URL.revokeObjectURL(url));
    state.blobs.clear();
    byId("arquivos-content")?.replaceChildren();
    const panel = byId("arquivos-detalhes");
    if (panel) { panel.hidden = true; panel.replaceChildren(); }
});
