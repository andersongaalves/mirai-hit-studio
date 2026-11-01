// Beat catalog filters: search, genre, mood, producer, key and BPM range, all combinable.
// Shared by the client and producer catalogs. Filtering happens on the loaded list;
// the state lives in the URL query so a filtered catalog can be shared or reloaded.
const FACETS = [
    { key: "genero", label: "Gênero", values: beat => splitList(beat.generos) },
    { key: "mood", label: "Mood", values: beat => splitList(beat.moods) },
    { key: "produtor", label: "Produtor", values: beat => (beat.produtor ? [beat.produtor.trim()] : []) },
    { key: "key", label: "Key", values: beat => (beat.tonalidade ? [beat.tonalidade.trim().replace(/\s+/g, " ")] : []) },
];
const PARAMS = ["q", ...FACETS.map(facet => facet.key), "bpm_min", "bpm_max"];

export function splitList(value) {
    return String(value || "").split(/[,;/|]/).map(item => item.trim().replace(/\s+/g, " ")).filter(Boolean);
}

// Case and accent insensitive comparison: "Melancólico" = "melancolico".
export function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

function readState(search = location.search) {
    const params = new URLSearchParams(search);
    return Object.fromEntries(PARAMS.map(name => [name, (params.get(name) || "").trim()]));
}

function writeState(state) {
    const params = new URLSearchParams(location.search);
    PARAMS.forEach(name => (state[name] ? params.set(name, state[name]) : params.delete(name)));
    const query = params.toString();
    history.replaceState(history.state, "", `${location.pathname}${query ? `?${query}` : ""}${location.hash}`);
}

function bpmBound(value) {
    const number = Number(value);
    return value !== "" && Number.isFinite(number) ? number : null;
}

/** Every active filter except `skip`; used for the counts beside each option. */
export function matchesBeat(beat, state, skip = null) {
    for (const facet of FACETS) {
        if (facet.key === skip || !state[facet.key]) continue;
        const wanted = normalize(state[facet.key]);
        if (!facet.values(beat).some(value => normalize(value) === wanted)) return false;
    }
    if (skip !== "bpm") {
        const min = bpmBound(state.bpm_min);
        const max = bpmBound(state.bpm_max);
        if ((min !== null || max !== null) && !Number.isFinite(beat.bpm)) return false;
        if (min !== null && beat.bpm < min) return false;
        if (max !== null && beat.bpm > max) return false;
    }
    if (skip !== "q" && state.q) {
        const text = normalize([beat.titulo, beat.produtor, beat.generos, beat.moods, beat.tonalidade].join(" "));
        if (!normalize(state.q).split(/\s+/).every(word => text.includes(word))) return false;
    }
    return true;
}

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function field(label, control, extra = "") {
    const wrapper = el("label", `beat-filters__field ${extra}`.trim());
    wrapper.append(el("span", "beat-filters__label", label), control);
    return wrapper;
}

/**
 * Puts the filters above `list` (replacing any from a previous load) and hides or shows
 * the cards in place. entries: [{ beat, card }]. Nothing is shown for fewer than 2 beats.
 */
export function mountBeatFilters(list, entries, { idPrefix = "beat-filter" } = {}) {
    list.parentElement?.querySelectorAll(":scope > .beat-filters, :scope > .beat-filters__empty").forEach(node => node.remove());
    if (entries.length < 2) return null;
    const beats = entries.map(entry => entry.beat);
    const state = readState();
    const form = el("form", "beat-filters");
    form.setAttribute("role", "search");
    form.setAttribute("aria-label", "Filtrar beats");
    form.addEventListener("submit", event => event.preventDefault());

    const search = el("input");
    search.type = "search";
    search.id = `${idPrefix}-q`;
    search.placeholder = "Título, produtor, gênero...";
    search.autocomplete = "off";
    search.value = state.q;
    search.addEventListener("input", () => { state.q = search.value.trim(); update(); });

    const selects = new Map();
    FACETS.forEach(facet => {
        const select = el("select");
        select.id = `${idPrefix}-${facet.key}`;
        select.addEventListener("change", () => { state[facet.key] = select.value; update(); });
        selects.set(facet.key, select);
    });

    const range = el("div", "beat-filters__range");
    const bpmInput = (name, label) => {
        const input = el("input");
        input.type = "number";
        input.inputMode = "numeric";
        input.min = "30";
        input.max = "300";
        input.step = "1";
        input.id = `${idPrefix}-${name}`;
        input.placeholder = label;
        input.setAttribute("aria-label", `BPM ${label.toLowerCase()}`);
        input.value = state[name];
        input.addEventListener("input", () => { state[name] = input.value.trim(); update(); });
        return input;
    };
    const bpmMin = bpmInput("bpm_min", "Mín.");
    const bpmMax = bpmInput("bpm_max", "Máx.");
    range.append(bpmMin, el("span", "beat-filters__dash", "–"), bpmMax);
    const bpmGroup = el("div", "beat-filters__field beat-filters__field--bpm");
    bpmGroup.setAttribute("role", "group");
    bpmGroup.setAttribute("aria-labelledby", `${idPrefix}-bpm-label`);
    const bpmLabel = el("span", "beat-filters__label", "BPM");
    bpmLabel.id = `${idPrefix}-bpm-label`;
    bpmGroup.append(bpmLabel, range);

    const fields = el("div", "beat-filters__fields");
    fields.append(field("Buscar", search, "beat-filters__field--search"));
    FACETS.forEach(facet => fields.append(field(facet.label, selects.get(facet.key))));
    fields.append(bpmGroup);

    const footer = el("div", "beat-filters__footer");
    const summary = el("p", "beat-filters__summary");
    summary.setAttribute("aria-live", "polite");
    const clear = el("button", "beat-filters__clear", "Limpar filtros");
    clear.type = "button";
    clear.addEventListener("click", () => {
        PARAMS.forEach(name => { state[name] = ""; });
        search.value = "";
        bpmMin.value = "";
        bpmMax.value = "";
        update();
        search.focus();
    });
    footer.append(summary, clear);
    form.append(fields, footer);

    const empty = el("p", "beat-filters__empty producer-empty", "Nenhum beat combina com esses filtros.");
    empty.hidden = true;
    list.before(form);
    list.after(empty);

    function fillOptions() {
        FACETS.forEach(facet => {
            const select = selects.get(facet.key);
            const counts = new Map();
            const labels = new Map();
            beats.forEach(beat => {
                const values = new Map(facet.values(beat).map(value => [normalize(value), value]));
                const matches = matchesBeat(beat, state, facet.key);
                values.forEach((value, id) => {
                    if (!labels.has(id)) labels.set(id, value);
                    counts.set(id, (counts.get(id) || 0) + (matches ? 1 : 0));
                });
            });
            const current = normalize(state[facet.key]);
            const options = [new Option("Todos", "")];
            [...labels.entries()]
                .sort((a, b) => a[1].localeCompare(b[1], "pt-BR", { sensitivity: "base", numeric: true }))
                .forEach(([id, value]) => {
                    const count = counts.get(id) || 0;
                    const option = new Option(`${value} (${count})`, value);
                    // Options with no beat under the other filters stay listed but unavailable.
                    option.disabled = count === 0 && id !== current;
                    options.push(option);
                });
            select.replaceChildren(...options);
            const selected = [...labels.entries()].find(([id]) => id === current);
            select.value = selected ? selected[1] : "";
            if (!selected) state[facet.key] = "";
            select.closest(".beat-filters__field").hidden = labels.size === 0;
        });
    }

    function update() {
        fillOptions();
        let shown = 0;
        entries.forEach(({ beat, card }) => {
            const visible = matchesBeat(beat, state);
            card.hidden = !visible;
            if (visible) shown += 1;
        });
        const active = PARAMS.some(name => state[name]);
        summary.textContent = active ? `${shown} de ${entries.length} beats` : `${entries.length} beats`;
        clear.hidden = !active;
        empty.hidden = shown > 0;
        form.classList.toggle("beat-filters--active", active);
        writeState(state);
    }

    update();
    return form;
}
