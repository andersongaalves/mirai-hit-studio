import { authFetch } from "../admin/auth.js";
import { bindImageCrop } from "./image_crop.js";
import { uploadBusy } from "./upload_feedback.js";
import { enqueueUpload } from "./upload_tasks.js";

const labels = { pendente: "Aguardando revisão", aprovado: "Publicado", recusado: "Recusado" };
const node = (tag, text, className) => {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    if (className) el.className = className;
    return el;
};
async function request(path, payload) {
    const response = await authFetch(path, payload ? {
        method: "POST", body: payload instanceof FormData ? payload : JSON.stringify(payload),
    } : {});
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Não foi possível salvar o envio.");
    return data;
}

function field(form, key, label, { options, type = "text", required = true, maxLength = 150 } = {}) {
    const wrap = node("label", label);
    const input = node(options ? "select" : "input");
    input.name = key;
    input.id = `portfolio-submit-${key}`;
    if (options) {
        for (const [value, text] of options) {
            const option = node("option", text);
            option.value = value;
            input.append(option);
        }
    } else {
        input.type = type;
        input.maxLength = maxLength;
        if (type === "url") input.placeholder = "https://";
    }
    input.required = required;
    if (type === "checkbox") wrap.prepend(input);
    else wrap.append(input);
    form.append(wrap);
    return input;
}

export async function loadPortfolioSubmissions(root, { admin = false, productions = [], onPublished } = {}) {
    if (!root) return;
    const serial = String(Number(root.dataset.serial || 0) + 1);
    root.dataset.serial = serial;
    root.replaceChildren(node("p", "Carregando envios..."));
    try {
        const items = await request(admin ? "/projetos/envios/admin" : "/portal/produtor/portfolio");
        if (root.dataset.serial !== serial) return;
        root.replaceChildren();
        const message = node("p");
        message.setAttribute("role", "status");
        root.append(message);
        if (!admin) {
            const form = node("form", "", "portfolio-submission-form");
            let requestId = crypto.randomUUID();
            field(form, "titulo", "Título").minLength = 3;
            field(form, "artista", "Artista", { maxLength: 100 });
            field(form, "categoria", "Serviço realizado", { maxLength: 100 });
            field(form, "link_audio", "Link público da música", { type: "url", maxLength: 500 });
            const coverMode = field(form, "capa_origem", "Capa", {
                options: [["arquivo", "Enviar imagem"], ["link", "Usar link"]],
            });
            const coverFile = field(form, "imagem", "Imagem da capa", { type: "file" });
            coverFile.accept = "image/jpeg,image/png,image/webp,image/avif";
            bindImageCrop(coverFile);
            const coverUrl = field(form, "link_capa", "Link público da capa", { type: "url", maxLength: 500 });
            const coverPreview = node("img", "", "portfolio-cover-preview");
            coverPreview.alt = "Prévia da capa selecionada";
            coverPreview.hidden = true;
            coverFile.closest("label").append(coverPreview);
            const updateCoverMode = () => {
                const useFile = coverMode.value === "arquivo";
                coverFile.disabled = !useFile;
                coverFile.required = useFile;
                coverFile.closest("label").hidden = !useFile;
                coverUrl.disabled = useFile;
                coverUrl.required = !useFile;
                coverUrl.closest("label").hidden = useFile;
                coverPreview.hidden = !useFile || !coverPreview.hasAttribute("src");
            };
            coverMode.addEventListener("change", updateCoverMode);
            coverFile.addEventListener("change", () => {
                coverFile.setCustomValidity("");
                coverPreview.removeAttribute("src");
                coverPreview.hidden = true;
                const file = coverFile.files[0];
                if (!file) return;
                if (!["image/jpeg", "image/png", "image/webp", "image/avif"].includes(file.type)
                    || !file.size || file.size > 10 * 1024 * 1024) {
                    coverFile.setCustomValidity("Envie uma imagem JPG, PNG, WebP ou AVIF de até 10 MB.");
                    coverFile.reportValidity();
                    return;
                }
                const reader = new FileReader();
                reader.addEventListener("load", () => {
                    if (coverFile.files[0] !== file) return;
                    coverPreview.src = reader.result;
                    coverPreview.hidden = coverMode.value !== "arquivo";
                });
                reader.readAsDataURL(file);
            });
            updateCoverMode();
            field(form, "vertical", "Área", { options: [["artists", "Artistas"], ["creators", "Criadores"], ["media_games", "Media & Games"]] });
            field(form, "case_type", "Classificação", { options: [["client_case", "Caso de cliente"], ["demo", "Demo"], ["concept_project", "Projeto conceitual"], ["study", "Estudo"]] });
            field(form, "funcao", "Minha participação", { options: [["producao", "Produção"], ["mixagem", "Mixagem"], ["masterizacao", "Masterização"], ["composicao", "Composição"], ["gravacao", "Gravação"], ["beat", "Beat"]] });
            field(form, "producao_id", "Produção vinculada", { required: false, options: [["", "Sem vínculo"], ...productions.map(p => [String(p.id), p.titulo])] });
            field(form, "descricao", "Descrição", { required: false, maxLength: 20000 });
            const consent = field(form, "autorizacao_artista", "Tenho autorização do artista para publicar este projeto e seus materiais.", { type: "checkbox" });
            const submit = node("button", "Enviar para revisão", "btn-cta");
            submit.type = "submit";
            form.append(submit);
            form.addEventListener("submit", async event => {
                event.preventDefault();
                if (submit.disabled) return;
                const finish = uploadBusy(submit);
                message.textContent = "";
                const data = Object.fromEntries(new FormData(form));
                delete data.capa_origem;
                delete data.imagem;
                data.request_id = requestId;
                data.producao_id = data.producao_id ? Number(data.producao_id) : null;
                data.autorizacao_artista = consent.checked;
                try {
                    if (coverMode.value === "arquivo") {
                        const multipart = new FormData();
                        multipart.append("dados", JSON.stringify(data));
                        multipart.append("imagem", coverFile.files[0]);
                        message.textContent = "Envio iniciado. Acompanhe em Envios.";
                        await enqueueUpload("/portal/produtor/portfolio/com-capa", multipart, {
                            label: `Portfólio · ${data.titulo}`,
                            meta: { kind: "portfolio-submission", requestId },
                            onStatus: async task => {
                                if (task.status === "failed") {
                                    message.textContent = task.message;
                                    return;
                                }
                                if (task.status !== "completed") return;
                                await loadPortfolioSubmissions(root, { productions });
                                const status = root.querySelector('[role="status"]');
                                if (status) status.textContent = "Projeto enviado para revisão do estúdio.";
                            },
                        });
                        return;
                    } else {
                        await request("/portal/produtor/portfolio", data);
                    }
                    if (root.dataset.serial !== serial) return;
                    requestId = crypto.randomUUID();
                    await loadPortfolioSubmissions(root, { productions });
                    root.querySelector('[role="status"]').textContent = "Projeto enviado para revisão do estúdio.";
                } catch (error) {
                    message.textContent = error.message;
                } finally {
                    finish();
                }
            });
            root.append(form);
        }
        const list = node("div", "", "producer-list");
        if (!items.length) list.append(node("p", "Nenhum envio encontrado."));
        for (const item of items) {
            const card = node("article", "", "producer-card admin-list-item portfolio-submission");
            card.dataset.submissionId = item.id;
            const content = node("div");
            content.append(node("h3", item.dados.titulo), node("p", item.dados.artista), node("p", labels[item.status]));
            if (item.motivo) content.append(node("p", item.motivo));
            card.append(content);
            if (admin) {
                content.append(node("p", `Produtor #${item.produtor_id} · ${item.dados.categoria} · ${item.dados.vertical} · ${item.dados.case_type}`));
                if (item.producao_id) content.append(node("p", `Produção #${item.producao_id}`));
                content.append(node("p", item.dados.descricao));
                for (const [key, label] of [["link_audio", "Ouvir projeto"], ["link_capa", "Ver capa"]]) {
                    const link = node("a", label);
                    const url = new URL(item.dados[key]);
                    if (!["https:", "http:"].includes(url.protocol)) continue;
                    link.href = url.href;
                    link.target = "_blank";
                    link.rel = "noopener noreferrer";
                    content.append(link);
                }
                if (item.status === "pendente") {
                    const review = node("form", "", "portfolio-submission-review");
                    const reason = field(review, "motivo", "Motivo da recusa", { required: false, maxLength: 500 });
                    for (const [decision, label] of [["aprovar", "Aprovar e publicar"], ["recusar", "Recusar"]]) {
                        const button = node("button", label, "btn-outline");
                        button.type = "button";
                        button.addEventListener("click", async () => {
                            if (decision === "recusar" && reason.value.trim().length < 3) {
                                reason.required = true;
                                reason.minLength = 3;
                                reason.reportValidity();
                                return;
                            }
                            review.querySelectorAll("button").forEach(b => { b.disabled = true; });
                            try {
                                await request(`/projetos/envios/${item.id}/revisao`, { versao: item.versao, decisao: decision, motivo: reason.value.trim() || null });
                                await loadPortfolioSubmissions(root, { admin: true, onPublished });
                                if (decision === "aprovar") await onPublished?.();
                            } catch (error) {
                                message.textContent = error.message;
                                review.querySelectorAll("button").forEach(b => { b.disabled = false; });
                            }
                        });
                        review.append(button);
                    }
                    review.addEventListener("submit", event => event.preventDefault());
                    card.append(review);
                }
            }
            list.append(card);
        }
        root.append(list);
    } catch (error) {
        if (root.dataset.serial !== serial) return;
        const notice = node("p", error.message);
        notice.setAttribute("role", "alert");
        root.replaceChildren(notice);
        const retry = node("button", "Tentar novamente", "btn-outline");
        retry.type = "button";
        retry.onclick = () => loadPortfolioSubmissions(root, { admin, productions, onPublished });
        root.append(retry);
    }
}

document.addEventListener("admin:logout", () => {
    for (const id of ["producer-portfolio-content", "portfolio-submissions-admin"]) {
        const root = document.getElementById(id);
        if (root) {
            root.dataset.serial = String(Number(root.dataset.serial || 0) + 1);
            root.replaceChildren();
        }
    }
});
