const CRC_TAG = "6304";

function crc16Ccitt(value) {
    let crc = 0xffff;
    for (const character of value) {
        crc ^= character.charCodeAt(0) << 8;
        for (let bit = 0; bit < 8; bit += 1) {
            crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
        }
    }
    return crc.toString(16).toUpperCase().padStart(4, "0");
}

export function validatePixPayload(value, expectedAmount) {
    if (typeof value !== "string" || value.length < 30 || value.length > 10000 || /[^\x20-\x7e]/.test(value)) {
        return "malformed_payload";
    }

    const fields = new Map();
    let offset = 0;
    while (offset < value.length) {
        if (offset + 4 > value.length) return "malformed_payload";
        const tag = value.slice(offset, offset + 2);
        const lengthText = value.slice(offset + 2, offset + 4);
        if (!/^\d{2}$/.test(tag) || !/^\d{2}$/.test(lengthText) || fields.has(tag)) return "malformed_payload";
        const length = Number(lengthText);
        const fieldValue = value.slice(offset + 4, offset + 4 + length);
        if (fieldValue.length !== length) return "malformed_payload";
        fields.set(tag, fieldValue);
        offset += 4 + length;
        if (tag === "63") {
            if (length !== 4 || offset !== value.length) return "malformed_payload";
            if (crc16Ccitt(value.slice(0, offset - 4)) !== fieldValue.toUpperCase()) return "invalid_crc";
        }
    }

    if (fields.get("00") !== "01" || (fields.has("01") && !["11", "12"].includes(fields.get("01"))) || fields.get("53") !== "986" || fields.get("58") !== "BR" || !fields.has("63")) {
        return "malformed_payload";
    }
    if (![...fields.entries()].some(([tag, content]) => /^[2-5]\d$/.test(tag) && content.includes("br.gov.bcb.pix"))) {
        return "malformed_payload";
    }

    if (fields.has("54")) {
        const amount = fields.get("54");
        const expected = Number(expectedAmount);
        if (!/^\d{1,10}(\.\d{2})?$/.test(amount) || !Number.isFinite(expected) || Number(amount) !== expected) {
            return "amount_mismatch";
        }
    }
    return null;
}

export function pixImageMime(base64) {
    if (typeof base64 !== "string" || !/^[A-Za-z0-9+/=\r\n]+$/.test(base64)) return null;
    try {
        const bytes = atob(base64.replace(/\s/g, ""));
        if (bytes.startsWith("\x89PNG\r\n\x1a\n")) return "image/png";
        if (bytes.startsWith("\xff\xd8\xff")) return "image/jpeg";
    } catch {}
    return null;
}
