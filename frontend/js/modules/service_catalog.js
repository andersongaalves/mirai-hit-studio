// Catalog rework (after 5.10): typed limits of a service instead of free-text sections.
// Mirrors backend/schemas/servico_estrutura.py: legacy structures are converted on read.
import { serviceStructure } from "../utils/security.js";

export const LIMIT_FIELDS = Object.freeze([
    { key: "faixas", label: "Faixas enviadas pelo cliente", min: 1, max: 100, enforced: true },
    { key: "duracao_min", label: "Duração máxima por faixa (min)", min: 1, max: 60, enforced: true },
    { key: "revisoes", label: "Revisões incluídas", min: 0, max: 20, enforced: true },
    { key: "melodias", label: "Melodias", min: 1, max: 50, enforced: false },
    { key: "artistas", label: "Artistas", min: 1, max: 20, enforced: false },
]);

const EMPTY_LIMITS = Object.freeze({ faixas: null, duracao_min: null, revisoes: null, melodias: null, artistas: null });
const PATTERNS = [
    ["faixas", /^ate\s+(\d+)\s+(?:canais|canal|faixas?)\b/],
    ["duracao_min", /^ate\s+(\d+)\s+min(?:uto|utos)?\b/],
    ["revisoes", /^(\d+)\s+revis(?:ao|oes)\b/],
    ["melodias", /^ate\s+(\d+)\s+melodias?\b/],
    ["artistas", /^(\d+)\s+artistas?\b/],
];

const plain = text => String(text).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

function cleanLimits(value = {}) {
    const limits = { ...EMPTY_LIMITS };
    LIMIT_FIELDS.forEach(({ key, min, max }) => {
        const number = value?.[key];
        if (Number.isInteger(number) && number >= min && number <= max) limits[key] = number;
    });
    return limits;
}

function convertLegacy(data) {
    const legacy = serviceStructure(data) || { intro: "", sections: [], benefits: [] };
    const limites = { ...EMPTY_LIMITS };
    const destaques = [];
    const items = [...legacy.sections.flatMap(section => section.items), ...legacy.benefits];
    items.forEach(item => {
        const text = String(item).trim();
        if (!text) return;
        for (const [key, pattern] of PATTERNS) {
            const match = plain(text).match(pattern);
            if (match && limites[key] === null) {
                const parsed = cleanLimits({ [key]: Number(match[1]) })[key];
                if (parsed !== null) {
                    limites[key] = parsed;
                    return;
                }
            }
        }
        if (!destaques.includes(text.slice(0, 200)) && destaques.length < 20) destaques.push(text.slice(0, 200));
    });
    return { versao: 2, intro: legacy.intro || "", destaques, limites };
}

/** Any stored structure (string or object, v2 or legacy) as { versao, intro, destaques, limites }. */
export function readStructure(value) {
    let data = value;
    if (typeof value === "string") {
        try {
            data = JSON.parse(value || "{}");
        } catch {
            return { versao: 2, intro: "", destaques: [], limites: { ...EMPTY_LIMITS } };
        }
    }
    if (data && typeof data === "object" && !Array.isArray(data) && data.versao === 2) {
        return {
            versao: 2,
            intro: typeof data.intro === "string" ? data.intro : "",
            destaques: Array.isArray(data.destaques) ? data.destaques.filter(item => typeof item === "string").slice(0, 20) : [],
            limites: cleanLimits(data.limites),
        };
    }
    return convertLegacy(data);
}

const plural = (count, one, many) => `${count} ${count === 1 ? one : many}`;

/** Short public lines for the limits ("Até 5 faixas", "1 revisão"...). */
export function limitLines(limites = {}) {
    const lines = [];
    if (limites.faixas) lines.push(`Até ${plural(limites.faixas, "faixa", "faixas")}`);
    if (limites.duracao_min) lines.push(`Até ${limites.duracao_min} min por faixa`);
    if (Number.isInteger(limites.revisoes)) lines.push(limites.revisoes === 0 ? "Sem revisões" : plural(limites.revisoes, "revisão", "revisões"));
    if (limites.melodias) lines.push(`Até ${plural(limites.melodias, "melodia", "melodias")}`);
    if (limites.artistas) lines.push(plural(limites.artistas, "artista", "artistas"));
    return lines;
}
