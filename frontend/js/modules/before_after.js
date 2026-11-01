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
export function beforeAfterSection(pair, { load, onError, beforeVersion = null, afterVersion = null, heading = "h2", id = "before-after-title", eyebrow, lead }) {
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
    section.append(controlesOuvir(pair.after, {
        titulo: pair.after.nome_exibicao,
        opcoes: [{ versao: "antes", rotulo: "Antes · Rough Mix" }, { versao: "depois", rotulo: "Depois · Final" }],
        inicial: "depois",
        load: key => load(sources[key].file, sources[key].versao),
        onError,
    }));
    return section;
}
