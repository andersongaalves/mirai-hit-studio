import { authFetch } from "./auth.js";

async function data(response) {
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof payload?.detail === "string" ? payload.detail : "Não foi possível revisar o beat.");
    return payload;
}

function field(form, label, name, value = "", options = {}) {
    const wrapper = document.createElement("label");
    wrapper.textContent = label;
    const input = document.createElement(options.multiline ? "textarea" : "input");
    input.name = name;
    if (!options.multiline) input.type = options.type || "text";
    if (options.accept) input.accept = options.accept;
    if (options.maxlength) input.maxLength = options.maxlength;
    if (options.type === "number") { input.min = options.min || "0.01"; input.step = options.step || "0.01"; }
    input.value = value ?? "";
    wrapper.append(input);
    form.append(wrapper);
    return input;
}

function formatRow(form, label, fileName, priceName, price, present, accept) {
    const row = document.createElement("div");
    row.className = "beat-form__format";
    const file = document.createElement("label");
    file.textContent = `${label}${present ? " · enviado" : ""}`;
    const input = document.createElement("input");
    input.type = "file"; input.name = fileName; input.accept = accept;
    file.append(input);
    const priceLabel = document.createElement("label");
    priceLabel.textContent = "Preço";
    const priceInput = document.createElement("input");
    priceInput.type = "number"; priceInput.name = priceName;
    priceInput.min = "0.01"; priceInput.step = "0.01"; priceInput.value = price ?? "";
    priceLabel.append(priceInput);
    row.append(file, priceLabel);
    form.append(row);
}

function beatCard(beat) {
    const card = document.createElement("article");
    card.className = "admin-list-item admin-beat-card";
    const title = document.createElement("h3"); title.textContent = beat.titulo;
    const meta = document.createElement("p"); meta.textContent = `${beat.produtor} · ${beat.status}`;
    const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none";
    const message = document.createElement("p"); message.className = "beat-review-message"; message.setAttribute("role", "status");
    audio.addEventListener("play", async () => {
        if (audio.src) return;
        try {
            const response = await authFetch(`/beats/${beat.id}/preview`);
            if (!response.ok) throw new Error("Prévia indisponível.");
            audio.src = URL.createObjectURL(await response.blob());
            await audio.play();
        } catch (error) { message.textContent = error.message; }
    }, { once: true });

    const form = document.createElement("form");
    form.className = "beat-form admin-beat-form";
    field(form, "Título", "titulo", beat.titulo, { maxlength: 160 });
    formatRow(form, "MP3 lease (com tag)", "mp3", "preco_lease", beat.preco_lease_base, beat.formato_novo, ".mp3");
    formatRow(form, "WAV lease (sem tag)", "wav", "preco_wav", beat.preco_wav_base, beat.tem_wav, ".wav");
    formatRow(form, "Multitrack (ZIP ou RAR)", "multitrack", "preco_multitrack", beat.preco_multitrack_base, beat.tem_multitrack, ".zip,.rar");
    const pair = document.createElement("div"); pair.className = "beat-form__pair";
    field(pair, "BPM", "bpm", beat.bpm, { type: "number", min: "30", step: "1" });
    field(pair, "Key", "tonalidade", beat.tonalidade, { maxlength: 24 });
    form.append(pair);
    field(form, "Gêneros", "generos", beat.generos, { maxlength: 240 });
    field(form, "Descrição", "descricao", beat.descricao, { multiline: true, maxlength: 5000 });
    field(form, "Preço (exclusivo)", "preco_exclusivo", beat.preco_exclusivo_base, { type: "number" });
    const actions = document.createElement("div"); actions.className = "admin-form-actions";
    const save = document.createElement("button"); save.type = "submit"; save.className = "btn-outline"; save.textContent = "Salvar revisão";
    save.disabled = beat.status === "vendido";
    actions.append(save);
    form.addEventListener("submit", async event => {
        event.preventDefault(); save.disabled = true; message.textContent = "Salvando...";
        const body = new FormData(form);
        for (const name of ["mp3", "wav", "multitrack"]) if (!body.get(name)?.size) body.delete(name);
        try { await data(await authFetch(`/admin/beats/${beat.id}`, { method: "PUT", body })); await initBeats(); }
        catch (error) { message.textContent = error.message; save.disabled = false; }
    });
    for (const [label, decisao] of [["Aprovar", "aprovar"], ["Rejeitar", "rejeitar"]]) {
        const button = document.createElement("button"); button.type = "button";
        button.className = decisao === "aprovar" ? "btn-cta" : "btn-small";
        button.textContent = label; button.disabled = beat.status === "vendido";
        button.onclick = async () => {
            const motivo = decisao === "rejeitar" ? window.prompt("Motivo da rejeição:") : "";
            if (decisao === "rejeitar" && !motivo?.trim()) return;
            button.disabled = true;
            try {
                await data(await authFetch(`/admin/beats/${beat.id}`, { method: "PATCH", body: JSON.stringify({ decisao, motivo: motivo || "" }) }));
                await initBeats();
            } catch (error) { message.textContent = error.message; button.disabled = false; }
        };
        actions.append(button);
    }
    form.append(actions, message);
    card.append(title, meta, audio, form);
    if (beat.motivo_rejeicao) { const reason = document.createElement("p"); reason.textContent = beat.motivo_rejeicao; card.append(reason); }
    return card;
}

export async function initBeats() {
    const root = document.getElementById("admin-beats-list");
    if (!root) return;
    root.textContent = "Carregando beats...";
    try {
        const beats = await data(await authFetch("/admin/beats"));
        root.replaceChildren(...beats.map(beatCard));
        if (!beats.length) root.textContent = "Nenhum beat enviado.";
    } catch (error) { root.textContent = error.message; }
}
