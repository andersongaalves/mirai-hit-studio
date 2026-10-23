import { API_URL } from "../config.js";
import { getContextName, getCurrentUser, getToken } from "../admin/auth.js";

const tasks = new Map();
let initialized = false;
let panel;
let list;
let count;

function ownerKey() {
    const user = getCurrentUser();
    return user ? `${getContextName()}:${user.id}` : null;
}

function render() {
    if (!list) return;
    const owner = ownerKey();
    const visible = [...tasks.values()].filter(task => task.owner === owner).sort((a, b) => b.createdAt - a.createdAt);
    list.replaceChildren(...visible.map(task => {
        const row = document.createElement("li");
        row.dataset.state = task.status;
        const label = document.createElement("strong");
        label.textContent = task.label;
        const status = document.createElement("span");
        status.textContent = task.status === "uploading" ? "Enviando..." : task.status === "completed" ? "Concluído" : task.status === "failed" ? task.message : "Na fila";
        row.append(label, status);
        return row;
    }));
    const active = visible.filter(task => ["queued", "uploading"].includes(task.status)).length;
    count.textContent = String(active);
    count.hidden = active === 0;
    if (!visible.length) list.append(Object.assign(document.createElement("li"), { textContent: "Nenhum envio nesta sessão." }));
}

function receive(event) {
    const message = event.data || {};
    if (message.type === "mirai-upload-list") message.tasks?.forEach(task => tasks.set(task.id, task));
    if (message.type === "mirai-upload-task") {
        tasks.set(message.task.id, message.task);
        document.dispatchEvent(new CustomEvent("mirai:upload-task", { detail: message.task }));
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

    const button = document.createElement("button");
    button.type = "button";
    button.className = "upload-tasks-button";
    button.textContent = "Envios";
    count = document.createElement("span");
    count.hidden = true;
    button.append(count);
    panel = document.createElement("dialog");
    panel.className = "upload-tasks-dialog";
    const header = document.createElement("header");
    const title = document.createElement("h2");
    title.textContent = "Envios";
    const close = document.createElement("button");
    close.type = "button";
    close.textContent = "Fechar";
    close.addEventListener("click", () => panel.close());
    header.append(title, close);
    list = document.createElement("ul");
    panel.append(header, list);
    document.body.append(button, panel);
    button.addEventListener("click", () => panel.showModal());
    registration.active?.postMessage({ type: "mirai-upload-list" });
    render();
    return registration;
}

export async function enqueueUpload(endpoint, formData, { label = "Arquivo", meta = {}, method = "POST" } = {}) {
    const token = getToken();
    const owner = ownerKey();
    if (!token || !owner) throw new Error("Sessão encerrada.");
    const registration = await initialize();
    const id = crypto.randomUUID();
    const task = { id, label, owner, meta, status: "queued", message: "Aguardando envio.", createdAt: Date.now(), updatedAt: Date.now() };
    tasks.set(id, task);
    render();
    registration.active.postMessage({
        type: "mirai-upload-start",
        id,
        label,
        owner,
        meta,
        method,
        url: `${API_URL}${endpoint}`,
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
    render();
});
