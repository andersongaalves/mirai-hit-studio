import { authFetch } from "./auth.js";

async function data(response) {
    const payload = await response.json().catch(() => null);
    if (!response.ok) throw new Error(payload?.detail || "Não foi possível revisar os beats.");
    return payload;
}

export async function initBeats() {
    const root = document.getElementById("admin-beats-list");
    if (!root) return;
    root.textContent = "Carregando beats...";
    try {
        const beats = await data(await authFetch("/admin/beats"));
        root.replaceChildren(...beats.map(beat => {
            const card = document.createElement("article"); card.className = "admin-list-item";
            const title = document.createElement("h3"); title.textContent = beat.titulo;
            const meta = document.createElement("p"); meta.textContent = `${beat.produtor} · ${beat.status} · ${beat.bpm ? `${beat.bpm} BPM` : "BPM não informado"}`;
            const audio = document.createElement("audio"); audio.controls = true; audio.preload = "none";
            audio.addEventListener("play", async () => { if (audio.src) return; const response = await authFetch(`/beats/${beat.id}/preview`); if (!response.ok) throw new Error(); audio.src = URL.createObjectURL(await response.blob()); await audio.play(); }, { once: true });
            const actions = document.createElement("div"); actions.className = "admin-form-actions";
            for (const [label, decisao] of [["Aprovar", "aprovar"], ["Rejeitar", "rejeitar"]]) {
                const button = document.createElement("button"); button.type = "button"; button.className = decisao === "aprovar" ? "btn-cta" : "btn-small"; button.textContent = label;
                button.disabled = beat.status === "vendido";
                button.onclick = async () => {
                    const motivo = decisao === "rejeitar" ? window.prompt("Motivo da rejeição:") : "";
                    if (decisao === "rejeitar" && !motivo?.trim()) return;
                    await data(await authFetch(`/admin/beats/${beat.id}`, { method: "PATCH", body: JSON.stringify({ decisao, motivo: motivo || "" }) }));
                    await initBeats();
                }; actions.append(button);
            }
            if (beat.motivo_rejeicao) { const reason = document.createElement("p"); reason.textContent = beat.motivo_rejeicao; card.append(title, meta, audio, reason, actions); }
            else card.append(title, meta, audio, actions);
            return card;
        }));
        if (!beats.length) root.textContent = "Nenhum beat enviado.";
    } catch (error) { root.textContent = error.message; }
}
