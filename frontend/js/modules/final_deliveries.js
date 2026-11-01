// Final deliveries per stage: the final version of each stage, kept apart from previews.
// One per stage (a new one replaces the previous on the server); deliveries without a
// stage are listed as general. Older duplicates from before the rule are returned apart.

export function splitByStage(deliveries = []) {
    const newest = [...deliveries].sort((a, b) =>
        String(b.created_at).localeCompare(String(a.created_at)) || b.id - a.id);
    const current = [];
    const older = [];
    const seen = new Set();
    newest.forEach(delivery => {
        const stage = delivery.etapa_id;
        if (stage == null) { current.push(delivery); return; }
        if (seen.has(stage)) { older.push(delivery); return; }
        seen.add(stage);
        current.push(delivery);
    });
    // Stages in contract order (ids are created in order); general deliveries last.
    current.sort((a, b) => (a.etapa_id ?? Infinity) - (b.etapa_id ?? Infinity) || b.id - a.id);
    return { current, older };
}

/** Label filled by stage_files.js with the stage name (or "Entrega geral"). */
export function stageLabel(delivery) {
    const label = document.createElement("span");
    label.className = "final-delivery-card__stage";
    label.dataset.stageLabel = delivery.etapa_id == null ? "" : String(delivery.etapa_id);
    label.textContent = delivery.etapa_id == null ? "Entrega geral" : "Etapa";
    return label;
}

export function deliveriesSection(deliveries, renderCard, { older = true, help = "" } = {}) {
    const section = document.createElement("section");
    section.className = "final-deliveries";
    section.setAttribute("aria-labelledby", "final-deliveries-title");
    const title = document.createElement("h3");
    title.id = "final-deliveries-title";
    title.textContent = "Entregas finais";
    section.append(title);
    if (help) {
        const note = document.createElement("p");
        note.className = "final-deliveries__help";
        note.textContent = help;
        section.append(note);
    }
    const split = splitByStage(deliveries);
    const list = document.createElement("div");
    list.className = "final-delivery-list";
    list.dataset.stageGroup = "";
    split.current.forEach(delivery => list.append(renderCard(delivery)));
    section.append(list);
    if (older && split.older.length) {
        const details = document.createElement("details");
        details.className = "final-deliveries__older";
        const summary = document.createElement("summary");
        summary.textContent = `Versões anteriores (${split.older.length})`;
        const olderList = document.createElement("div");
        olderList.className = "final-delivery-list";
        split.older.forEach(delivery => olderList.append(renderCard(delivery)));
        details.append(summary, olderList);
        section.append(details);
    }
    return section;
}
