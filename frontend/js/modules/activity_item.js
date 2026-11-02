// One row of work in progress (uploads, previews being generated, queues): thumbnail, title,
// detail, when it started and a progress ring. Shared by the "Envios" list, the notification
// center ("Em andamento") and the tag manager, so every loading state looks the same.

const SVG = "http://www.w3.org/2000/svg";
const ICONS = {
    audio: "M3 10v4M7 7v10M11 4v16M15 8v8M19 10v4",
    imagem: "M4 5h16v14H4V5zm0 11 4.5-4.5 3.5 3.5 2.5-2.5L20 17M15.5 9.5a1.5 1.5 0 1 0 0-.01",
    pdf: "M7 3h7l5 5v13H7V3zm7 1.5V9h4.5M9.5 13h5M9.5 16h5",
    arquivo: "M7 3h7l5 5v13H7V3zm7 1.5V9h4.5",
    fila: "M4 6h16M4 12h16M4 18h10",
    sino: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4l2-2zM10 20a2 2 0 0 0 4 0",
};
export const ESTADOS = {
    na_fila: "Na fila",
    enviando: "Enviando",
    processando: "Processando",
    concluido: "Concluído",
    erro: "Falhou",
};
const ATIVOS = new Set(["na_fila", "enviando", "processando"]);
export const ativo = item => ATIVOS.has(item.estado);

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "" && text !== null && text !== undefined) node.textContent = String(text);
    return node;
}

export function icon(name, className = "activity-icon") {
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", className);
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("d", ICONS[name] || ICONS.arquivo);
    svg.append(path);
    return svg;
}

export function iconFor(mime = "", tipo = "") {
    const value = String(mime || "").toLowerCase();
    if (value.startsWith("image/")) return "imagem";
    if (value.startsWith("audio/") || ["previa", "lote_previas", "beat", "compressao", "audio-tag"].includes(tipo)) return "audio";
    if (value === "application/pdf") return "pdf";
    return "arquivo";
}

// Determinate ring when the progress is known, a spinning arc otherwise; check / cross at the end.
export function progressRing(estado, progresso = null) {
    const wrap = el("span", `activity-ring activity-ring--${estado}`);
    const percent = Number.isFinite(progresso) ? Math.max(0, Math.min(1, progresso)) : null;
    wrap.setAttribute("role", "img");
    const label = ESTADOS[estado] || estado;
    wrap.setAttribute("aria-label", percent !== null && ativo({ estado }) ? `${label}: ${Math.round(percent * 100)}%` : label);
    const svg = document.createElementNS(SVG, "svg");
    svg.setAttribute("viewBox", "0 0 36 36");
    svg.setAttribute("aria-hidden", "true");
    const track = document.createElementNS(SVG, "circle");
    track.setAttribute("class", "activity-ring__track");
    const bar = document.createElementNS(SVG, "circle");
    bar.setAttribute("class", "activity-ring__bar");
    for (const circle of [track, bar]) {
        circle.setAttribute("cx", "18");
        circle.setAttribute("cy", "18");
        circle.setAttribute("r", "15");
    }
    const length = 2 * Math.PI * 15;
    bar.setAttribute("stroke-dasharray", String(length));
    if (estado === "concluido" || estado === "erro") {
        bar.setAttribute("stroke-dashoffset", "0");
    } else if (percent !== null) {
        bar.setAttribute("stroke-dashoffset", String(length * (1 - percent)));
    } else {
        wrap.classList.add("is-indeterminate");
        bar.setAttribute("stroke-dashoffset", String(length * 0.72));
    }
    svg.append(track, bar);
    wrap.append(svg);
    if (estado === "concluido" || estado === "erro") {
        const mark = document.createElementNS(SVG, "path");
        mark.setAttribute("class", "activity-ring__mark");
        mark.setAttribute("d", estado === "concluido" ? "M11.5 18.5l4.5 4.5 8.5-9.5" : "M13 13l10 10M23 13l-10 10");
        svg.append(mark);
    } else if (percent !== null) {
        wrap.append(el("span", "activity-ring__value", `${Math.round(percent * 100)}`));
    }
    return wrap;
}

export function formatBytes(value) {
    if (!Number.isFinite(value) || value <= 0) return "";
    const units = ["B", "KB", "MB", "GB"];
    let size = value;
    let unit = 0;
    while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
    return `${size.toLocaleString("pt-BR", { maximumFractionDigits: unit === 0 || size >= 100 ? 0 : 1 })} ${units[unit]}`;
}

export function when(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const today = new Date();
    const sameDay = date.toDateString() === today.toDateString();
    const time = date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    return sameDay ? `hoje, ${time}` : `${date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}, ${time}`;
}

// item: { id, titulo, detalhe, estado, progresso, criado_em, concluido_em, miniatura, icone, mensagem, url, prefixo }
export function activityItem(item, { tag = "li", onOpen = null } = {}) {
    const row = el(tag, `activity-item activity-item--${item.estado}`);
    row.dataset.activity = item.id;
    row.dataset.state = item.estado;
    const thumb = el("span", "activity-thumb");
    thumb.append(icon(item.icone || "arquivo"));
    if (item.miniatura) {
        const img = document.createElement("img");
        img.alt = "";
        img.decoding = "async";
        img.loading = "lazy";
        img.referrerPolicy = "no-referrer";
        img.addEventListener("load", () => thumb.classList.add("is-loaded"));
        img.addEventListener("error", () => img.remove());
        img.src = item.miniatura;
        thumb.append(img);
    }
    const body = el("span", "activity-body");
    const title = el(item.url && onOpen ? "a" : "strong", "activity-title", item.titulo);
    if (item.url && onOpen) {
        title.href = item.url;
        title.addEventListener("click", event => onOpen(event, item));
    }
    body.append(title);
    if (item.detalhe) body.append(el("span", "activity-detail", item.detalhe));
    const meta = el("span", "activity-meta");
    const state = el("span", "activity-state", item.mensagem || ESTADOS[item.estado] || item.estado);
    meta.append(state);
    const stamp = item.concluido_em && !ativo(item) ? item.concluido_em : item.criado_em;
    if (stamp) {
        const time = document.createElement("time");
        time.dateTime = new Date(stamp).toISOString();
        time.textContent = `${item.prefixo || (ativo(item) ? "Iniciado" : "Concluído")} ${when(stamp)}`;
        meta.append(time);
    }
    body.append(meta);
    row.append(thumb, body, progressRing(item.estado, item.progresso));
    return row;
}
