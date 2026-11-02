// Before (Rough Mix) and after (final) comparison. Shared by the client portal and the Admin.
import { controlesOuvir, podeOuvir } from "./ouvir_arquivo.js";

function latest(list) {
    return [...list].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)) || b.id - a.id)[0] || null;
}

/**
 * before: newest audio in a "Rough" stage, or a preview named "rough".
 * after: newest audio in a "Master" stage, else the released delivery, else the newest delivery file.
 * Returns null when there is no rough or no distinct final.
 */
export function pickBeforeAfter(stages = [], files = [], deliveries = []) {
    const audio = files.filter(file => podeOuvir(file) && !file.bloqueado_pagamento && !["pendente", "erro"].includes(file.processamento_tag));
    const stageIds = pattern => new Set(stages.filter(stage => pattern.test(stage.nome || "")).map(stage => stage.id));
    const roughStages = stageIds(/rough/i);
    const masterStages = stageIds(/master/i);
    const before = latest(audio.filter(file => roughStages.has(file.etapa_id)))
        || latest(audio.filter(file => file.tipo === "previa" && /rough/i.test(file.nome_exibicao || "")));
    if (!before) return null;
    const released = deliveries.filter(delivery => !delivery.bloqueado_pagamento);
    const deliveryAudio = released.map(delivery => delivery.arquivo_principal).filter(file => file && podeOuvir(file));
    const after = latest(audio.filter(file => masterStages.has(file.etapa_id) && file.id !== before.id))
        || latest(deliveryAudio)
        || latest(audio.filter(file => file.tipo === "entrega"));
    return after && after.id !== before.id ? { before, after } : null;
}

/**
 * pair: from pickBeforeAfter. load(file, versao) resolves a Blob.
 * beforeVersion / afterVersion: the version to play for each file (e.g. the untagged original).
 */
/** Pair chosen by id (the Admin's choice) among the files the viewer has. */
export function pairFromIds(files = [], antesId, depoisId) {
    const antes = files.find(file => file.id === antesId);
    const depois = files.find(file => file.id === depoisId);
    return antes && depois && antes.id !== depois.id ? { before: antes, after: depois } : null;
}

function formatDb(value) {
    return `${value > 0 ? "+" : ""}${String(value.toFixed(1)).replace(".", ",")} dB`;
}

/**
 * loudness: { ganho_antes_db, lufs_depois } from the server; both versions then play at the
 * final's integrated loudness (the reference).
 */
export function beforeAfterSection(pair, { load, onError, beforeVersion = null, afterVersion = null, heading = "h2", id = "before-after-title", eyebrow, lead, loudness = null }) {
    const section = document.createElement("section");
    section.className = "before-after";
    section.setAttribute("aria-labelledby", id);
    const text = (tag, className, value) => {
        const item = document.createElement(tag);
        if (className) item.className = className;
        item.textContent = value;
        return item;
    };
    const title = text(heading, "", "Antes e depois");
    title.id = id;
    section.append(text("p", "before-after__eyebrow", eyebrow), title, text("p", "before-after__lead", lead));
    const sources = {
        antes: { file: pair.before, versao: beforeVersion },
        depois: { file: pair.after, versao: afterVersion },
    };
    const gain = Number(loudness?.ganho_antes_db);
    const matched = Number.isFinite(gain);
    section.append(controlesOuvir(pair.after, {
        titulo: pair.after.nome_exibicao,
        opcoes: [{ versao: "antes", rotulo: "Antes · Rough Mix" }, { versao: "depois", rotulo: "Depois · Final" }],
        inicial: "depois",
        load: key => load(sources[key].file, sources[key].versao),
        onError,
        ganhos: matched ? { antes: gain, depois: 0 } : null,
    }));
    if (matched) {
        const reference = Number(loudness.lufs_depois);
        const lufs = Number.isFinite(reference) ? ` (${String(reference.toFixed(1)).replace(".", ",")} LUFS integrados)` : "";
        section.append(text("p", "before-after__loudness",
            `Volumes igualados pela versão final${lufs}: a Rough Mix toca com ${formatDb(gain)}.`));
    }
    return section;
}
