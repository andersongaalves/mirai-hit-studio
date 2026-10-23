import { authFetch } from "../admin/auth.js";
import { enqueueUpload } from "./upload_tasks.js";

const roots = new Set();
const node = (tag, text, className = "") => {
    const el = document.createElement(tag);
    el.textContent = text || "";
    el.className = className;
    return el;
};
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
        root.append(upload);
        if (admin) {
            const form = node("form", "", "portfolio-submission-form");
            for (const [key, text, min, max] of [["intervalo_segundos", "Intervalo (segundos)", 10, 120], ["volume_percentual", "Volume da tag (%)", 1, 100]]) {
                const label = node("label", text);
                const input = node("input");
                input.type = "number";
                input.name = key;
                input.value = current[key];
                input.min = min;
                input.max = max;
                input.step = 1;
                input.required = true;
                label.append(input);
                form.append(label);
            }
            const save = node("button", "Salvar parâmetros", "btn-outline");
            save.type = "submit";
            form.append(save);
            form.onsubmit = async event => {
                event.preventDefault();
                if (save.disabled) return;
                save.disabled = true;
                const values = Object.fromEntries(new FormData(form));
                try {
                    await data(await authFetch(endpoint, { method: "PUT", body: JSON.stringify({ versao: current.versao,
                        intervalo_segundos: Number(values.intervalo_segundos), volume_percentual: Number(values.volume_percentual) }) }));
                    if (root.dataset.serial === serial) await loadAudioTag(root, { admin });
                } catch (error) { feedback.textContent = error.message; save.disabled = false; }
            };
            root.append(form);
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
