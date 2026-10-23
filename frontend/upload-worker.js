const tasks = new Map();

function publicTask(task) {
    const { token: _token, entries: _entries, ...safe } = task;
    return safe;
}

async function broadcast(task) {
    const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    clients.forEach(client => client.postMessage({ type: "mirai-upload-task", task: publicTask(task) }));
}

function failureMessage(status) {
    if (status === 401 || status === 403) return "Sessão expirada ou sem permissão.";
    if (status === 413) return "O arquivo excede o limite permitido.";
    if (status >= 500) return "O servidor não concluiu o envio. Tente novamente.";
    return "O envio foi recusado. Revise os dados e tente novamente.";
}

async function run(task) {
    task.status = "uploading";
    task.updatedAt = Date.now();
    await broadcast(task);
    try {
        const body = new FormData();
        task.entries.forEach(([name, value]) => body.append(name, value));
        const response = await fetch(task.url, {
            method: task.method,
            headers: { Authorization: `Bearer ${task.token}` },
            body,
        });
        if (!response.ok) throw Object.assign(new Error(failureMessage(response.status)), { status: response.status });
        task.status = "completed";
        task.message = "Envio concluído.";
    } catch (error) {
        task.status = "failed";
        task.message = error?.message || "Não foi possível concluir o envio.";
        task.httpStatus = Number.isInteger(error?.status) ? error.status : null;
    } finally {
        task.token = null;
        task.entries = [];
        task.updatedAt = Date.now();
        await broadcast(task);
    }
}

self.addEventListener("install", event => event.waitUntil(self.skipWaiting()));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));
self.addEventListener("message", event => {
    const message = event.data || {};
    if (message.type === "mirai-upload-list") {
        event.source?.postMessage({ type: "mirai-upload-list", tasks: [...tasks.values()].map(publicTask) });
        return;
    }
    if (message.type !== "mirai-upload-start") return;
    const task = {
        id: message.id,
        label: message.label,
        owner: message.owner,
        meta: message.meta || {},
        url: message.url,
        method: message.method || "POST",
        token: message.token,
        entries: message.entries,
        status: "queued",
        message: "Aguardando envio.",
        createdAt: Date.now(),
        updatedAt: Date.now(),
    };
    tasks.set(task.id, task);
    event.waitUntil(run(task));
});
