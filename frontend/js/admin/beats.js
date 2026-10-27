import { authFetch } from "./auth.js";
import { bindImageCrop } from "../modules/image_crop.js";
import { uploadBusy } from "../modules/upload_feedback.js";
import { applyBeatUploadLimits, validateBeatUpload } from "../modules/beat_upload_validation.js";
import { beatPreview } from "../modules/beat_preview.js";
import { enqueueUpload } from "../modules/upload_tasks.js";

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

function uploadSettings(config) {
    const section = document.createElement("section");
    section.className = "admin-card beat-upload-settings";
    const title = document.createElement("h2"); title.textContent = "Limites de upload";
    const help = document.createElement("p"); help.textContent = "Defina o limite por arquivo. O total configurado não pode ultrapassar 260 MB.";
    const form = document.createElement("form"); form.className = "beat-upload-settings__form";
    const fields = [
        ["capa_mb", "Capa", 10], ["mp3_mb", "MP3", 50],
        ["wav_mb", "WAV", 100], ["multitrack_mb", "ZIP ou RAR", 150],
    ];
    for (const [name, label, max] of fields) {
        const wrapper = document.createElement("label"); wrapper.textContent = `${label} (MB)`;
        const input = document.createElement("input");
        input.type = "number"; input.name = name; input.min = "1"; input.max = String(max);
        input.step = "1"; input.required = true; input.value = config[name];
        wrapper.append(input); form.append(wrapper);
    }
    const modeLabel = document.createElement("label"); modeLabel.textContent = "Origem do multitrack";
    const mode = document.createElement("select"); mode.name = "multitrack_mode";
    mode.append(new Option("Arquivo no site", "arquivo"), new Option("Link externo", "link"));
    mode.value = config.multitrack_mode; modeLabel.append(mode); form.append(modeLabel);
    const save = document.createElement("button"); save.type = "submit"; save.className = "btn-outline"; save.textContent = "Salvar limites";
    const message = document.createElement("p"); message.className = "beat-review-message"; message.setAttribute("role", "status");
    form.append(save, message);
    form.addEventListener("submit", async event => {
        event.preventDefault();
        if (!form.reportValidity()) return;
        const payload = Object.fromEntries(fields.map(([name]) => [name, Number(form.elements[name].value)]));
        payload.multitrack_mode = form.elements.multitrack_mode.value;
        if (Object.values(payload).reduce((sum, value) => sum + value, 0) > 260) {
            message.textContent = "A soma dos limites não pode ultrapassar 260 MB.";
            return;
        }
        const finish = uploadBusy(save, "Salvando...");
        try {
            await data(await authFetch("/admin/beats/configuracao", { method: "PUT", body: JSON.stringify(payload) }));
            message.textContent = "Limites salvos.";
            await initBeats();
        } catch (error) { message.textContent = error.message; }
        finally { finish(); }
    });
    section.append(title, help, form);
    return section;
}

const LICENSE_LABELS = { lease: "Lease", lease_mp3: "MP3 lease", lease_wav: "WAV lease", multitrack: "Multitrack", exclusivo: "Exclusivo" };
const LICENSE_STATUS = { reservada: "Reservada", adquirida: "Adquirida", cancelada: "Cancelada" };
const CANCEL_REASONS = { expirada: "reserva expirada", admin: "liberada pelo Admin", pagamento_revertido: "pagamento revertido" };

function dateTime(value) {
    return value ? new Date(value).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "";
}

async function adminAction(path, question, button, message) {
    const motivo = window.prompt(question);
    if (!motivo?.trim()) return;
    button.disabled = true;
    try {
        await data(await authFetch(path, { method: "POST", body: JSON.stringify({ motivo: motivo.trim() }) }));
        await initBeats();
    } catch (error) { message.textContent = error.message; button.disabled = false; }
}

function licensesSection(beat, message) {
    const licenses = beat.licencas || [];
    if (!licenses.length && !beat.pode_voltar_ao_catalogo) return null;
    const section = document.createElement("section");
    section.className = "admin-beat-licenses";
    const heading = document.createElement("h4"); heading.textContent = "Licenças";
    const list = document.createElement("ul");
    for (const license of licenses) {
        const item = document.createElement("li");
        const text = document.createElement("span");
        let detail = `${LICENSE_LABELS[license.tipo] || license.tipo} · ${LICENSE_STATUS[license.status] || license.status} · proposta #${license.proposta_id}`;
        if (license.status === "reservada" && license.expira_em) detail += ` · reservada até ${dateTime(license.expira_em)}`;
        if (license.status === "cancelada" && license.motivo_cancelamento) detail += ` · ${CANCEL_REASONS[license.motivo_cancelamento] || license.motivo_cancelamento}`;
        text.textContent = detail;
        item.append(text);
        if (license.status === "reservada") {
            const release = document.createElement("button");
            release.type = "button"; release.className = "btn-small"; release.textContent = "Liberar reserva";
            release.onclick = () => adminAction(`/admin/beats/licencas/${license.id}/liberar`, "Motivo para liberar a reserva:", release, message);
            item.append(release);
        }
        if (license.status === "adquirida") {
            const contract = document.createElement("button");
            contract.type = "button"; contract.className = "btn-small"; contract.textContent = "Baixar contrato";
            contract.onclick = async () => {
                contract.disabled = true;
                try {
                    const response = await authFetch(`/admin/beats/licencas/${license.id}/contrato`);
                    if (!response.ok) throw new Error("Não foi possível baixar o contrato.");
                    const encoded = (response.headers.get("content-disposition") || "").match(/filename\*=UTF-8''([^;]+)/i)?.[1];
                    const url = URL.createObjectURL(await response.blob());
                    const link = document.createElement("a");
                    link.href = url; link.download = encoded ? decodeURIComponent(encoded) : `contrato-${license.id}.pdf`;
                    link.click();
                    setTimeout(() => URL.revokeObjectURL(url), 30000);
                } catch (error) { message.textContent = error.message; }
                finally { contract.disabled = false; }
            };
            item.append(contract);
        }
        list.append(item);
    }
    section.append(heading, list);
    if (beat.pode_voltar_ao_catalogo) {
        const relist = document.createElement("button");
        relist.type = "button"; relist.className = "btn-outline"; relist.textContent = "Devolver ao catálogo";
        relist.onclick = () => adminAction(`/admin/beats/${beat.id}/voltar-ao-catalogo`, "Motivo para devolver o beat ao catálogo:", relist, message);
        section.append(relist);
    }
    return section;
}

function beatCard(beat, config) {
    const card = document.createElement("article");
    card.className = "admin-list-item admin-beat-card";
    const summary = document.createElement("div");
    summary.className = "admin-beat-card__summary";
    const content = document.createElement("div");
    content.className = "admin-beat-card__content";
    const title = document.createElement("h3"); title.textContent = beat.titulo;
    const cover = beat.capa_url ? document.createElement("img") : null;
    if (cover) { cover.className = "beat-cover"; cover.src = beat.capa_url; cover.alt = `Capa de ${beat.titulo}`; cover.loading = "lazy"; }
    const meta = document.createElement("p"); meta.textContent = `${beat.produtor} · ${beat.status}`;
    const message = document.createElement("p"); message.className = "beat-review-message"; message.setAttribute("role", "status");
    const audio = beatPreview(async () => {
        const response = await authFetch(`/beats/${beat.id}/preview`);
        if (!response.ok) throw new Error("Prévia indisponível.");
        return response.blob();
    });

    const form = document.createElement("form");
    form.className = "beat-form admin-beat-form";
    field(form, "Título", "titulo", beat.titulo, { maxlength: 160 });
    bindImageCrop(field(form, beat.capa_url ? "Substituir capa" : "Adicionar capa", "capa", "", { type: "file", accept: ".jpg,.jpeg,.png,.webp" }), { ratio: 1, width: 1024 });
    formatRow(form, "MP3 lease (com tag)", "mp3", "preco_lease", beat.preco_lease_base, beat.formato_novo, ".mp3");
    formatRow(form, "WAV lease (sem tag)", "wav", "preco_wav", beat.preco_wav_base, beat.tem_wav, ".wav");
    const multitrackFile = document.createElement("div"); multitrackFile.dataset.multitrackFile = ""; form.append(multitrackFile);
    formatRow(multitrackFile, "Multitrack (ZIP ou RAR)", "multitrack", "preco_multitrack", beat.preco_multitrack_base, beat.tem_multitrack && beat.multitrack_origem === "arquivo", ".zip,.rar");
    const multitrackLink = document.createElement("div"); multitrackLink.className = "beat-form__format hidden"; multitrackLink.dataset.multitrackLink = "";
    field(multitrackLink, beat.multitrack_origem === "link" ? "Substituir link HTTPS" : "Link HTTPS do multitrack", "multitrack_url", "", { type: "url", maxlength: 2000 });
    field(multitrackLink, "Preço", "preco_multitrack_link", beat.preco_multitrack_base, { type: "number" });
    form.append(multitrackLink);
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
        event.preventDefault();
        if (save.disabled) return;
        const validation = validateBeatUpload(form, { limits: config }, { requireFiles: false, existing: beat });
        if (!validation.valid) { message.textContent = validation.message; return; }
        const finish = uploadBusy(save, "Salvando...");
        message.textContent = "Salvando...";
        const body = new FormData(form);
        if (config.multitrack_mode === "link") {
            body.set("preco_multitrack", body.get("preco_multitrack_link") || "");
            body.delete("preco_multitrack_link"); body.delete("multitrack");
        } else {
            body.delete("multitrack_url"); body.delete("preco_multitrack_link");
        }
        for (const name of ["mp3", "wav", "multitrack", "capa"]) if (!body.get(name)?.size) body.delete(name);
        const hasFiles = ["mp3", "wav", "multitrack", "capa"].some(name => body.get(name) instanceof File);
        try {
            if (hasFiles) {
                await enqueueUpload(`/admin/beats/${beat.id}`, body, {
                    method: "PUT",
                    label: `Revisão do beat · ${beat.titulo}`,
                    meta: { kind: "admin-beat" },
                });
                message.textContent = "Envio iniciado. Acompanhe em Envios.";
            } else {
                await data(await authFetch(`/admin/beats/${beat.id}`, { method: "PUT", body }));
                await initBeats();
            }
        }
        catch (error) { message.textContent = error.message; save.disabled = false; }
        finally { finish(); }
    });
    applyBeatUploadLimits(form, config);
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
    content.append(title, meta, audio);
    const licenses = licensesSection(beat, message);
    if (licenses) content.append(licenses);
    if (beat.motivo_rejeicao) { const reason = document.createElement("p"); reason.textContent = beat.motivo_rejeicao; content.append(reason); }
    summary.append(content);
    if (cover) summary.append(cover);
    card.append(summary, form);
    return card;
}

document.addEventListener("mirai:upload-task", event => {
    if (event.detail.status === "completed" && event.detail.meta?.kind === "admin-beat") initBeats();
});

export async function initBeats() {
    const root = document.getElementById("admin-beats-list");
    const settings = document.getElementById("admin-beat-upload-settings");
    if (!root) return;
    root.textContent = "Carregando beats...";
    try {
        const [beats, config] = await Promise.all([
            data(await authFetch("/admin/beats")),
            data(await authFetch("/admin/beats/configuracao")),
        ]);
        settings?.replaceChildren(uploadSettings(config));
        root.replaceChildren(...beats.map(beat => beatCard(beat, config)));
        if (!beats.length) root.textContent = "Nenhum beat enviado.";
    } catch (error) { root.textContent = error.message; }
}
