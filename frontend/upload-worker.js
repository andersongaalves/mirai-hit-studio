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

// Upload progress: browsers that can stream a request body (Chromium) count the bytes as
// they leave; the others still upload normally and show an indeterminate ring.
const STREAMING = (() => {
    try {
        let duplexAccessed = false;
        const hasContentType = new Request("https://upload.invalid", {
            body: new ReadableStream(),
            method: "POST",
            get duplex() { duplexAccessed = true; return "half"; },
        }).headers.has("Content-Type");
        return duplexAccessed && !hasContentType;
    } catch {
        return false;
    }
})();

function bodyOf(task) {
    const body = new FormData();
    task.entries.forEach(([name, value]) => body.append(name, value));
    return body;
}

async function streamed(task, report) {
    // Let the browser encode the multipart body (boundary included), then count it going out.
    const encoded = new Request(task.url, { method: task.method, body: bodyOf(task) });
    let sent = 0;
    const counter = new TransformStream({
        transform(chunk, controller) {
            sent += chunk.byteLength;
            report(sent);
            controller.enqueue(chunk);
        },
    });
    try {
        return await fetch(task.url, {
            method: task.method,
            headers: { Authorization: `Bearer ${task.token}`, "Content-Type": encoded.headers.get("Content-Type") },
            body: encoded.body.pipeThrough(counter),
            duplex: "half",
        });
    } catch (error) {
        // Nothing reached the server yet (e.g. a connection without streaming support):
        // send it again the classic way. A fully sent body is never sent twice.
        if (sent === 0 || sent < (task.size || 0) * 0.98) return null;
        throw error;
    }
}

async function run(task) {
    task.status = "uploading";
    task.progress = STREAMING && task.size ? 0 : null;
    task.updatedAt = Date.now();
    await broadcast(task);
    let last = 0;
    const report = bytes => {
        const now = Date.now();
        // A little under 100% until the server answers (it still has to store the file).
        task.progress = Math.min(0.97, bytes / Math.max(task.size, 1));
        if (now - last > 250) {
            last = now;
            task.updatedAt = now;
            broadcast(task);
        }
    };
    try {
        let response = STREAMING && task.size ? await streamed(task, report) : null;
        if (!response) {
            task.progress = null;
            await broadcast(task);
            response = await fetch(task.url, {
                method: task.method,
                headers: { Authorization: `Bearer ${task.token}` },
                body: bodyOf(task),
            });
        }
        if (!response.ok) throw Object.assign(new Error(failureMessage(response.status)), { status: response.status });
        task.status = "completed";
        task.progress = 1;
        task.message = "Envio concluído.";
    } catch (error) {
        task.status = "failed";
        task.message = error?.message && !/fetch|network/i.test(error.message)
            ? error.message : "Não foi possível concluir o envio. Verifique a conexão e tente novamente.";
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
        size: Number(message.size) || 0,
        token: message.token,
        entries: message.entries,
        status: "queued",
        message: "Aguardando envio.",
        progress: null,
        createdAt: Date.now(),
        updatedAt: Date.now(),
    };
    tasks.set(task.id, task);
    event.waitUntil(run(task));
});
