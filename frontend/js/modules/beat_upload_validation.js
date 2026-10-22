const MB = 1024 * 1024;
const FILES = {
    capa: { label: "capa", extensions: ["jpg", "jpeg", "png", "webp"] },
    mp3: { label: "MP3", extensions: ["mp3"] },
    wav: { label: "WAV", extensions: ["wav"] },
    multitrack: { label: "multitrack", extensions: ["zip", "rar"] },
};

function extension(file) {
    return (file?.name || "").split(".").pop().toLowerCase();
}

function fail(field, message) {
    field?.setCustomValidity(message);
    field?.setAttribute("aria-invalid", "true");
    field?.focus();
    return { valid: false, message };
}

export function applyBeatUploadLimits(form, limits) {
    if (!form || !limits) return;
    for (const control of form.querySelectorAll("input, textarea")) {
        if (control.dataset.beatValidationBound) continue;
        control.addEventListener("input", () => {
            control.setCustomValidity("");
            control.removeAttribute("aria-invalid");
        });
        control.addEventListener("change", () => {
            control.setCustomValidity("");
            control.removeAttribute("aria-invalid");
        });
        control.dataset.beatValidationBound = "true";
    }
    for (const [name, spec] of Object.entries(FILES)) {
        const input = form.elements[name];
        if (!input) continue;
        input.dataset.maxBytes = String(limits[`${name}_mb`] * MB);
        let hint = input.closest("label")?.querySelector(".beat-file-limit");
        if (!hint) {
            hint = document.createElement("small");
            hint.className = "beat-file-limit";
            input.insertAdjacentElement("afterend", hint);
        }
        hint.textContent = `${spec.extensions.map(item => item.toUpperCase()).join(" ou ")} · até ${limits[`${name}_mb`]} MB`;
    }
    const linkMode = limits.multitrack_mode === "link";
    form.querySelector("[data-multitrack-file]")?.classList.toggle("hidden", linkMode);
    form.querySelector("[data-multitrack-link]")?.classList.toggle("hidden", !linkMode);
    const filePrice = form.elements.preco_multitrack;
    const linkPrice = form.elements.preco_multitrack_link;
    if (filePrice && linkPrice) {
        if (linkMode && !linkPrice.value) linkPrice.value = filePrice.value;
        if (!linkMode && !filePrice.value) filePrice.value = linkPrice.value;
        filePrice.disabled = linkMode;
        linkPrice.disabled = !linkMode;
    }
    if (form.elements.multitrack) form.elements.multitrack.disabled = linkMode;
    if (form.elements.multitrack_url) form.elements.multitrack_url.disabled = !linkMode;
}

export function validateBeatUpload(form, config, { requireFiles = true, existing = {} } = {}) {
    for (const input of form.querySelectorAll("input, textarea")) {
        input.setCustomValidity("");
        input.removeAttribute("aria-invalid");
    }
    if (!config) return { valid: false, message: "Não foi possível confirmar os limites de upload. Recarregue a página." };
    if (config.ready === false) return { valid: false, message: config.message || "Sua conta ainda não está pronta para enviar beats." };
    if (!form.checkValidity()) {
        form.reportValidity();
        return { valid: false, message: "Revise os campos obrigatórios destacados." };
    }
    for (const [name, spec] of Object.entries(FILES)) {
        const input = form.elements[name];
        const file = input?.files?.[0];
        if (requireFiles && ["capa", "mp3"].includes(name) && !file) {
            return fail(input, `Selecione o arquivo ${spec.label}.`);
        }
        if (!file) continue;
        if (!spec.extensions.includes(extension(file))) {
            return fail(input, `O arquivo ${spec.label} deve ser ${spec.extensions.map(item => item.toUpperCase()).join(" ou ")}.`);
        }
        const limit = config.limits[`${name}_mb`];
        if (file.size > limit * MB) {
            return fail(input, `O arquivo ${spec.label} excede o limite de ${limit} MB.`);
        }
    }
    const multitrackPrice = config.limits.multitrack_mode === "link" ? "preco_multitrack_link" : "preco_multitrack";
    const prices = ["preco_lease", "preco_wav", multitrackPrice, "preco_exclusivo"];
    if (!prices.some(name => Number(form.elements[name]?.value) > 0)) {
        return fail(form.elements.preco_lease, "Informe ao menos um preço válido.");
    }
    for (const [priceName, fileName, label, present] of [
        ["preco_wav", "wav", "WAV", existing.tem_wav],
        ...(config.limits.multitrack_mode === "arquivo"
            ? [["preco_multitrack", "multitrack", "multitrack", existing.tem_multitrack]]
            : []),
    ]) {
        if (Number(form.elements[priceName]?.value) > 0 && !form.elements[fileName]?.files?.[0] && !present) {
            return fail(form.elements[fileName], `Selecione o arquivo ${label} correspondente ao preço informado.`);
        }
    }
    if (config.limits.multitrack_mode === "link" && Number(form.elements[multitrackPrice]?.value) > 0) {
        const link = form.elements.multitrack_url;
        if (!link?.value.trim() && !existing.tem_multitrack) {
            return fail(link, "Informe o link HTTPS do multitrack.");
        }
        if (link?.value) {
            let parsed = null;
            try { parsed = new URL(link.value); } catch { /* handled below */ }
            if (!link.validity.valid || parsed?.protocol !== "https:") {
                return fail(link, "Informe um link HTTPS válido para o multitrack.");
            }
        }
    }
    return { valid: true, message: "" };
}
