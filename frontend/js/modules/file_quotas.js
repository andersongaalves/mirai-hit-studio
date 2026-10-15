// Roadmap 3.0, 5.09: contractual file quotas, shared by the service editor, the admin
// production modal and the portals. Everything is rendered as text; the server enforces.

export const QUOTA_TYPES = Object.freeze([
    { tipo: "material", label: "Materiais do cliente" },
    { tipo: "referencia", label: "Referências" },
    { tipo: "previa", label: "Prévias" },
    { tipo: "entrega", label: "Entregas" },
]);

export const FORMAT_LABELS = Object.freeze({
    "audio/mpeg": "MP3",
    "audio/wav": "WAV",
    "audio/x-wav": "WAV (x-wav)",
    "audio/flac": "FLAC",
    "audio/mp4": "M4A/AAC",
    "video/mp4": "MP4 (vídeo)",
    "application/pdf": "PDF",
    "application/zip": "ZIP",
});

const FIELDS = [
    ["max_arquivos", "Arquivos", 1, 100],
    ["max_versoes", "Versões por arquivo", 1, 50],
    ["max_tamanho_mb", "MB por arquivo", 1, 50],
    ["max_total_mb", "Espaço total (MB)", 1, 5000],
];

function element(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

function mb(bytes) {
    return (Number(bytes || 0) / (1024 * 1024)).toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

export function typeLabel(tipo) {
    return QUOTA_TYPES.find(item => item.tipo === tipo)?.label ?? tipo;
}

/** One-line, human description of a quota (and its usage when present). */
export function describeQuota(cota) {
    if (!cota) return "Sem limite contratual para este tipo.";
    const parts = [];
    if (cota.max_arquivos != null) {
        parts.push(cota.arquivos_usados != null
            ? `${cota.arquivos_usados} de ${cota.max_arquivos} arquivo(s)`
            : `até ${cota.max_arquivos} arquivo(s)`);
    }
    if (cota.max_versoes != null) parts.push(`até ${cota.max_versoes} versão(ões) por arquivo`);
    if (cota.max_tamanho_mb != null) parts.push(`até ${cota.max_tamanho_mb} MB por arquivo`);
    if (cota.max_total_mb != null) {
        parts.push(cota.total_usado_bytes != null
            ? `espaço ${mb(cota.total_usado_bytes)} de ${cota.max_total_mb} MB`
            : `espaço total ${cota.max_total_mb} MB`);
    }
    if (Array.isArray(cota.formatos)) parts.push(`formatos: ${cota.formatos.map(item => FORMAT_LABELS[item] || item).join(", ")}`);
    return parts.length ? parts.join(" · ") : "Sem limite contratual para este tipo.";
}

/** True when a new logical file can no longer be added (count or space exhausted). */
export function quotaExhausted(cota) {
    if (!cota) return false;
    const files = cota.max_arquivos != null && cota.arquivos_usados >= cota.max_arquivos;
    const space = cota.max_total_mb != null && cota.total_usado_bytes >= cota.max_total_mb * 1024 * 1024;
    return Boolean(files || space);
}

/**
 * Editor of the four file types. Returns { element, read() } where read() gives the
 * payload list or throws Error with a user message. Unchecked types are "no limit".
 */
export function quotaEditor({ cotas = [], formatos = Object.keys(FORMAT_LABELS), idPrefix = "cota" }) {
    const root = element("div", "file-quotas");
    const rows = QUOTA_TYPES.map(({ tipo, label }) => {
        const current = cotas.find(item => item.tipo === tipo) || null;
        const row = element("fieldset", "file-quota");
        const legend = element("legend");
        const enabled = element("input");
        enabled.type = "checkbox";
        enabled.checked = Boolean(current);
        enabled.id = `${idPrefix}-${tipo}-ativo`;
        const legendLabel = element("label");
        legendLabel.htmlFor = enabled.id;
        legendLabel.textContent = ` Limitar ${label.toLowerCase()}`;
        legend.append(enabled, legendLabel);
        row.append(legend);
        const body = element("div", "file-quota__body");
        const inputs = {};
        FIELDS.forEach(([field, text, min, max]) => {
            const wrapper = element("label", "file-quota__field");
            const input = element("input");
            input.type = "number";
            input.min = String(min);
            input.max = String(max);
            input.step = "1";
            input.placeholder = "sem limite";
            input.value = current?.[field] ?? "";
            input.setAttribute("aria-label", `${text} — ${label}`);
            inputs[field] = input;
            wrapper.append(element("span", "", text), input);
            body.append(wrapper);
        });
        const formats = element("div", "file-quota__formats");
        formats.append(element("span", "", "Formatos (nenhum marcado = todos):"));
        const boxes = formatos.map(mime => {
            const label2 = element("label", "file-quota__format");
            const box = element("input");
            box.type = "checkbox";
            box.value = mime;
            box.checked = Array.isArray(current?.formatos) && current.formatos.includes(mime);
            box.setAttribute("aria-label", `${FORMAT_LABELS[mime] || mime} — ${label}`);
            label2.append(box, document.createTextNode(` ${FORMAT_LABELS[mime] || mime}`));
            formats.append(label2);
            return box;
        });
        body.append(formats);
        row.append(body);
        const sync = () => {
            body.classList.toggle("is-disabled", !enabled.checked);
            [...Object.values(inputs), ...boxes].forEach(control => { control.disabled = !enabled.checked; });
        };
        enabled.addEventListener("change", sync);
        sync();
        root.append(row);
        return { tipo, label, enabled, inputs, boxes };
    });
    const read = () => rows.filter(row => row.enabled.checked).map(row => {
        const cota = { tipo: row.tipo };
        FIELDS.forEach(([field, text, min, max]) => {
            const raw = row.inputs[field].value.trim();
            if (raw === "") { cota[field] = null; return; }
            const value = Number(raw);
            if (!Number.isInteger(value) || value < min || value > max) {
                throw new Error(`${text} de ${row.label.toLowerCase()} deve ser um número inteiro entre ${min} e ${max}.`);
            }
            cota[field] = value;
        });
        const chosen = row.boxes.filter(box => box.checked).map(box => box.value);
        cota.formatos = chosen.length ? chosen : null;
        return cota;
    });
    return { element: root, read };
}

/** Read-only list with usage, for the admin modal. */
export function quotaList(cotas = []) {
    const list = element("ul", "file-quotas__list");
    if (!cotas.length) {
        list.append(element("li", "", "Sem cotas contratuais: valem só os limites gerais (50 MB por arquivo)."));
        return list;
    }
    cotas.forEach(cota => {
        const item = element("li", quotaExhausted(cota) ? "is-exhausted" : "");
        item.append(
            element("strong", "", `${typeLabel(cota.tipo)}: `),
            document.createTextNode(describeQuota(cota)),
            element("span", "file-quotas__origin", cota.origem === "admin" ? " (exceção do Admin)" : " (contrato)"),
        );
        list.append(item);
    });
    return list;
}
