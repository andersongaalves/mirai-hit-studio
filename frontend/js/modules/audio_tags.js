import { authFetch } from "../admin/auth.js";
import { enqueueUpload } from "./upload_tasks.js";

const roots = new Set();
const node = (tag, text, className = "") => {
    const el = document.createElement(tag);
    el.textContent = text || "";
    el.className = className;
    return el;
};
function disclosure(title, content, className = "") {
    const details = node("details", "", `admin-disclosure ${className}`.trim());
    details.append(node("summary", title), content);
    return details;
}
async function data(response) {
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : "Não foi possível atualizar a tag.");
    return body;
}
function cleanup(root) {
    root.querySelectorAll("audio").forEach(audio => {
        audio.pause();
        if (audio.src.startsWith("blob:")) URL.revokeObjectURL(audio.src);
    });
}

const CONTROL_FIELDS = [
    ["intervalo_segundos", "Intervalo entre inserções (segundos)", 10, 120, 1],
    ["volume_percentual", "Volume fixo de fallback (%)", 1, 100, 1],
    ["alvo_relativo_db", "Nível da tag em relação ao áudio (dB)", -30, 12, 0.1],
    ["ganho_min_db", "Ganho mínimo permitido (dB)", -60, 0, 0.1],
    ["ganho_max_db", "Ganho máximo permitido (dB)", 0, 30, 0.1],
    ["silencio_lufs", "Abaixo de qual nível considerar silêncio (LUFS)", -90, -20, 0.1],
    ["limiter_dbfs", "Teto do limitador (dBFS)", -12, -0.1, 0.1],
];

function settingsPayload(form, version) {
    const payload = { versao: version, nivelamento_automatico: form.elements.nivelamento_automatico.checked };
    for (const [key] of CONTROL_FIELDS) payload[key] = Number(form.elements[key].value);
    return payload;
}

function settingsForm(current) {
    const form = node("form", "", "audio-tag-controls");
    const automatic = node("label", "", "audio-tag-toggle");
    const checkbox = node("input");
    checkbox.type = "checkbox";
    checkbox.name = "nivelamento_automatico";
    checkbox.checked = current.nivelamento_automatico !== false;
    automatic.append(checkbox, document.createTextNode(" Nivelamento automático por loudness (EBU R128)"));
    form.append(automatic);
    const grid = node("div", "", "audio-tag-controls__grid");
    for (const [key, text, min, max, step] of CONTROL_FIELDS) {
        const label = node("label", text);
        const input = node("input");
        input.type = "number";
        input.name = key;
        input.value = current[key];
        input.min = min;
        input.max = max;
        input.step = step;
        input.required = true;
        label.append(input);
        grid.append(label);
    }
    form.append(grid);
    const sync = () => {
        for (const name of ["alvo_relativo_db", "ganho_min_db", "ganho_max_db", "silencio_lufs"]) {
            form.elements[name].disabled = !checkbox.checked;
        }
    };
    checkbox.addEventListener("change", sync);
    sync();
    return form;
}

async function previewGenerator(root, form, feedback) {
    const content = node("div", "", "admin-disclosure__content audio-tag-preview-generator");
    content.append(node("p", "Gere um MP3 temporário sem alterar o arquivo original nem os projetos."));
    const fields = node("div", "", "audio-tag-preview-generator__fields");
    const sourceLabel = node("label", "Áudio de origem");
    const source = node("select");
    source.required = true;
    sourceLabel.append(source);
    const tagLabel = node("label", "Tag aplicada");
    const tag = node("select");
    tag.required = true;
    tagLabel.append(tag);
    fields.append(sourceLabel, tagLabel);
    const generate = node("button", "Gerar prévia com estes controles", "btn-cta");
    generate.type = "button";
    content.append(fields, generate);
    const section = disclosure("Gerar prévia de teste", content, "audio-tag-preview-disclosure");
    root.append(section);
    try {
        const options = await data(await authFetch("/admin/audio-tag/preview/opcoes"));
        source.append(new Option("Selecione um beat, prévia ou entrega", ""));
        for (const item of options.fontes) {
            const option = new Option(`${item.label} (${item.detail})`, `${item.type}:${item.id}`);
            source.append(option);
        }
        tag.append(new Option("Selecione uma tag", ""));
        for (const item of options.tags) {
            tag.append(new Option(`${item.label}${item.atual ? " - atual" : " - histórica"}`, String(item.id)));
        }
        generate.disabled = !options.fontes.length || !options.tags.length;
        if (generate.disabled) feedback.textContent = "Cadastre uma tag e mantenha ao menos um áudio elegível para testar.";
    } catch (error) {
        generate.disabled = true;
        feedback.textContent = error.message;
    }
    generate.addEventListener("click", async () => {
        if (!source.value || !tag.value || !form.reportValidity()) {
            feedback.textContent = "Escolha o áudio, a tag e revise os controles.";
            return;
        }
        const [source_type, source_id] = source.value.split(":");
        generate.disabled = true;
        feedback.textContent = "Gerando prévia...";
        try {
            const controls = settingsPayload(form, 0);
            delete controls.versao;
            const response = await authFetch("/admin/audio-tag/preview", {
                method: "POST",
                body: JSON.stringify({ ...controls, source_type, source_id: Number(source_id), tag_id: Number(tag.value) }),
            });
            if (!response.ok) {
                const body = await response.json().catch(() => null);
                throw new Error(body?.detail || "Não foi possível gerar a prévia.");
            }
            cleanup(content);
            content.querySelector("audio")?.remove();
            const player = node("audio");
            player.controls = true;
            player.preload = "metadata";
            player.src = URL.createObjectURL(await response.blob());
            content.append(player);
            feedback.textContent = "Prévia pronta. O arquivo é temporário e não foi salvo no projeto.";
        } catch (error) {
            feedback.textContent = error.message;
        } finally {
            generate.disabled = false;
        }
    });
}

export async function loadAudioTag(root, { admin = false } = {}) {
    if (!root) return;
    roots.add(root);
    cleanup(root);
    const serial = String(Number(root.dataset.serial || 0) + 1);
    root.dataset.serial = serial;
    const endpoint = admin ? "/admin/audio-tag" : "/portal/produtor/audio-tag";
    root.replaceChildren(node("p", "Carregando tag..."));
    try {
        const current = await data(await authFetch(endpoint));
        if (root.dataset.serial !== serial) return;
        root.replaceChildren(node("h2", admin ? "Tag padrão das prévias" : "Minha tag de áudio"));
        root.append(node("p", current.nome || (current.padrao_disponivel && !admin ? "Usando a tag padrão da Mirai." : "Nenhuma tag cadastrada.")));
        const feedback = node("p");
        feedback.setAttribute("role", "status");
        root.append(feedback);
        if (current.tag_id) {
            const listen = node("button", "Ouvir tag", "btn-outline");
            listen.type = "button";
            listen.onclick = async () => {
                listen.disabled = true;
                try {
                    const response = await authFetch(`${endpoint}/conteudo`);
                    if (!response.ok) throw new Error("Tag indisponível.");
                    const blob = await response.blob();
                    if (root.dataset.serial !== serial) return;
                    cleanup(root);
                    root.querySelector("audio")?.remove();
                    const audio = node("audio");
                    audio.controls = true;
                    audio.src = URL.createObjectURL(blob);
                    root.append(audio);
                    await audio.play().catch(() => {});
                } catch (error) { feedback.textContent = error.message; }
                finally { listen.disabled = false; }
            };
            root.append(listen);
        }
        const upload = node("form", "", "portfolio-submission-form");
        const label = node("label", "Arquivo da tag (MP3 ou WAV, até 2 MB e 10 segundos)");
        const file = node("input");
        file.type = "file";
        file.accept = ".mp3,.wav,audio/mpeg,audio/wav,audio/x-wav";
        file.required = true;
        label.append(file);
        const send = node("button", current.tag_id ? "Trocar tag" : "Cadastrar tag", "btn-cta");
        send.type = "submit";
        upload.append(label, send);
        upload.onsubmit = async event => {
            event.preventDefault();
            if (send.disabled || !file.files[0]) return;
            if (file.files[0].size > 2 * 1024 * 1024) { feedback.textContent = "A tag deve ter até 2 MB."; return; }
            const form = new FormData();
            form.append("arquivo", file.files[0]);
            form.append("versao", String(current.versao));
            try {
                await enqueueUpload(endpoint, form, {
                    label: admin ? "Tag padrão da Mirai" : "Minha tag de áudio",
                    meta: { kind: "audio-tag", admin },
                });
                feedback.textContent = "Envio iniciado. Acompanhe em Envios.";
                upload.reset();
            } catch (error) { feedback.textContent = error.message; }
        };
        root.append(disclosure(current.tag_id ? "Trocar tag padrão" : "Cadastrar tag padrão", upload, "audio-tag-upload-disclosure"));
        if (admin) {
            const form = settingsForm(current);
            form.append(node("p", "O modo automático mede áudio e tag. Se a medição não for possível, o sistema usa o volume fixo de fallback.", "admin-field-help"));
            const save = node("button", "Salvar parâmetros", "btn-outline");
            save.type = "submit";
            form.append(save);
            form.onsubmit = async event => {
                event.preventDefault();
                if (save.disabled) return;
                save.disabled = true;
                try {
                    await data(await authFetch(endpoint, { method: "PUT", body: JSON.stringify(settingsPayload(form, current.versao)) }));
                    if (root.dataset.serial === serial) await loadAudioTag(root, { admin });
                } catch (error) { feedback.textContent = error.message; save.disabled = false; }
            };
            const settingsContent = node("div", "", "admin-disclosure__content");
            settingsContent.append(form);
            root.append(disclosure("Editar nivelamento", settingsContent, "audio-tag-settings-disclosure"));
            await previewGenerator(root, form, feedback);
        }
    } catch (error) {
        if (root.dataset.serial !== serial) return;
        root.replaceChildren(node("p", error.message));
        const retry = node("button", "Tentar novamente", "btn-outline");
        retry.type = "button";
        retry.onclick = () => loadAudioTag(root, { admin });
        root.append(retry);
    }
}

document.addEventListener("admin:logout", () => {
    roots.forEach(root => {
        root.dataset.serial = String(Number(root.dataset.serial || 0) + 1);
        cleanup(root);
        root.replaceChildren();
    });
    roots.clear();
});

document.addEventListener("mirai:upload-task", event => {
    const task = event.detail;
    if (task.status !== "completed" || task.meta?.kind !== "audio-tag") return;
    roots.forEach(root => loadAudioTag(root, { admin: Boolean(task.meta.admin) }));
});
