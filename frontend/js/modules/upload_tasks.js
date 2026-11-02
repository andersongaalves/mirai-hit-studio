import { UPLOAD_API } from "../config.js";
import { getContextName, getCurrentUser, getToken } from "../admin/auth.js";
import { activityItem, formatBytes, iconFor } from "./activity_item.js";

const tasks = new Map();
// Thumbnails live in the page (object URLs of the chosen images), never in the worker.
const thumbnails = new Map();
let initialized = false;
let panel;
let list;
let count;
let button;

function ownerKey() {
    const user = getCurrentUser();
    return user ? `${getContextName()}:${user.id}` : null;
}

const ESTADO = { queued: "na_fila", uploading: "enviando", completed: "concluido", failed: "erro" };

function describe(task) {
    const files = task.meta?.arquivos || [];
    const size = files.reduce((total, file) => total + (file.tamanho || 0), 0);
    const names = files.map(file => file.nome).filter(Boolean);
    const detail = [names.length > 2 ? `${names.slice(0, 2).join(", ")} e mais ${names.length - 2}` : names.join(", "),
        formatBytes(size)].filter(Boolean).join(" · ");
    const estado = ESTADO[task.status] || "na_fila";
    const progress = Number.isFinite(task.progress) ? task.progress : null;
    return {
        id: `upload:${task.id}`,
        titulo: task.label,
        detalhe: detail,
        estado,
        progresso: estado === "enviando" ? progress : null,
        mensagem: estado === "erro" ? task.message
            : estado === "enviando" && progress !== null ? `Enviando ${Math.round(progress * 100)}%`
                : estado === "enviando" ? "Enviando..." : undefined,
        criado_em: task.createdAt,
        concluido_em: ["completed", "failed"].includes(task.status) ? task.updatedAt : null,
        prefixo: estado === "concluido" ? "Enviado" : estado === "erro" ? "Tentado" : "Iniciado",
        miniatura: thumbnails.get(task.id) || null,
        icone: iconFor(files.find(file => file.tipo)?.tipo || ""),
        status: task.status,
    };
}

// Uploads of this session for the signed-in person, newest first (for the notification center).
export function uploadActivities() {
    const owner = ownerKey();
    return [...tasks.values()].filter(task => task.owner === owner).sort((a, b) => b.createdAt - a.createdAt).map(describe);
}

function render() {
    document.dispatchEvent(new CustomEvent("mirai:activities"));
    if (!list) return;
    const items = uploadActivities();
    list.replaceChildren(...items.map(item => {
        const row = activityItem(item);
        // Kept for compatibility: the worker's own state names.
        row.dataset.state = item.status;
        return row;
    }));
    const active = items.filter(item => ["na_fila", "enviando"].includes(item.estado)).length;
    count.textContent = String(active);
    count.hidden = active === 0;
    button.classList.toggle("is-busy", active > 0);
    button.setAttribute("aria-label", active ? `Envios, ${active} em andamento` : "Envios");
    if (!items.length) list.append(Object.assign(document.createElement("li"), { className: "activity-empty", textContent: "Nenhum envio nesta sessão." }));
}

function receive(event) {
    const message = event.data || {};
    if (message.type === "mirai-upload-list") message.tasks?.forEach(task => tasks.set(task.id, { ...tasks.get(task.id), ...task }));
    if (message.type === "mirai-upload-task") {
        tasks.set(message.task.id, { ...tasks.get(message.task.id), ...message.task });
        if (["completed", "failed"].includes(message.task.status)) {
            document.dispatchEvent(new CustomEvent("mirai:upload-task", { detail: message.task }));
        }
    }
    render();
}

async function initialize() {
    if (initialized) return navigator.serviceWorker.ready;
    initialized = true;
    if (!("serviceWorker" in navigator)) throw new Error("Envios em segundo plano não são suportados neste navegador.");
    await navigator.serviceWorker.register("/upload-worker.js", { scope: "/" });
    const registration = await navigator.serviceWorker.ready;
    navigator.serviceWorker.addEventListener("message", receive);

    button = document.createElement("button");
    button.type = "button";
    button.className = "upload-tasks-button";
    button.textContent = "Envios";
    count = document.createElement("span");
    count.hidden = true;
    button.append(count);
    panel = document.createElement("dialog");
    panel.className = "upload-tasks-dialog";
    panel.setAttribute("aria-labelledby", "upload-tasks-title");
    const header = document.createElement("header");
    const title = document.createElement("h2");
    title.id = "upload-tasks-title";
    title.textContent = "Envios";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fechar";
    close.addEventListener("click", () => panel.close());
    header.append(title, close);
    list = document.createElement("ul");
    list.className = "activity-list";
    panel.append(header, list);
    document.body.append(button, panel);
    // AUD6-S07-003: keep the floating button from covering the end of the page.
    document.body.classList.add("has-upload-tasks");
    button.addEventListener("click", () => panel.showModal());
    registration.active?.postMessage({ type: "mirai-upload-list" });
    render();
    return registration;
}

function filesOf(formData) {
    return [...formData.entries()]
        .filter(([, value]) => typeof File !== "undefined" && value instanceof File && value.size > 0)
        .map(([, file]) => file);
}

export async function enqueueUpload(endpoint, formData, { label = "Arquivo", meta = {}, method = "POST" } = {}) {
    const token = getToken();
    const owner = ownerKey();
    if (!token || !owner) throw new Error("Sessão encerrada.");
    const registration = await initialize();
    const id = crypto.randomUUID();
    const files = filesOf(formData);
    const image = files.find(file => file.type.startsWith("image/"));
    if (image) thumbnails.set(id, URL.createObjectURL(image));
    const details = { ...meta, arquivos: files.map(file => ({ nome: file.name, tamanho: file.size, tipo: file.type })) };
    const size = files.reduce((total, file) => total + file.size, 0);
    const task = { id, label, owner, meta: details, status: "queued", message: "Aguardando envio.", progress: null,
        createdAt: Date.now(), updatedAt: Date.now() };
    tasks.set(id, task);
    render();
    registration.active.postMessage({
        type: "mirai-upload-start",
        id,
        label,
        owner,
        meta: details,
        method,
        size,
        url: `${UPLOAD_API}${endpoint}`,
        token,
        entries: [...formData.entries()],
    });
    return task;
}

export function startUploadTasks() {
    return initialize();
}

document.addEventListener("admin:logout", () => {
    tasks.clear();
    thumbnails.forEach(url => URL.revokeObjectURL(url));
    thumbnails.clear();
    render();
});
