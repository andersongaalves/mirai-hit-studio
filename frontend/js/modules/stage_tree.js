// Sub-stages: in a combo, a component service whose name matches a stage of another
// component (e.g. the "Masterização" service inside a combo whose "Mixagem" service
// already ends with a "Masterização" stage) is shown as the internal steps of that stage,
// instead of a second "Masterização". Presentation only: each stage keeps its own status,
// value and files.

function simplify(value) {
    return String(value || "")
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/[^\p{L}\p{N}\s]/gu, " ")
        .replace(/\s+/g, " ")
        .trim()
        .toLowerCase();
}

export function groupKey(stage) {
    return `${stage.item_indice}|${stage.item_descricao}`;
}

// "🎮 Start — 🎧 Masterização" -> "masterizacao" (the component service of a combo).
function serviceName(stage) {
    const parts = String(stage.item_descricao || "").split(/\s[—–-]\s/);
    return simplify(parts[parts.length - 1]);
}

/** Map of parent stage id -> its sub-stages (in order), and the set of sub-stage ids. */
export function stageTree(stages = []) {
    const groups = new Map();
    stages.forEach(stage => {
        const key = groupKey(stage);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(stage);
    });
    const children = new Map();
    const childIds = new Set();
    if (groups.size < 2) return { children, childIds };
    for (const [key, members] of groups) {
        const name = serviceName(members[0]);
        if (!name) continue;
        const parent = stages.find(stage => groupKey(stage) !== key && !childIds.has(stage.id) && simplify(stage.nome) === name);
        if (!parent || members.some(member => children.has(member.id))) continue;
        children.set(parent.id, [...(children.get(parent.id) || []), ...members]);
        members.forEach(member => childIds.add(member.id));
    }
    return { children, childIds };
}

/** Stages in display order; a sub-stage comes right after its parent, marked "↳". */
export function orderedStages(stages = []) {
    const { children, childIds } = stageTree(stages);
    const result = [];
    stages.filter(stage => !childIds.has(stage.id)).forEach(stage => {
        result.push({ stage, label: stage.nome, parent: null });
        (children.get(stage.id) || []).forEach(child => result.push({ stage: child, label: `↳ ${child.nome}`, parent: stage }));
    });
    return result;
}
