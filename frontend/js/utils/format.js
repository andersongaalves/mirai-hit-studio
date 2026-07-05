// ===========================
// MONEY
// ===========================

export function money(value = 0) {
    const number = Number(value);

    if (isNaN(number)) {
        return "R$ 0,00";
    }

    return number.toLocaleString(
        "pt-BR",

        {
            style: "currency",

            currency: "BRL",
        },
    );
}

// ===========================
// NUMBER
// ===========================

export function number(value = 0) {
    const number = Number(value);

    if (isNaN(number)) {
        return "0";
    }

    return number.toLocaleString("pt-BR");
}

// ===========================
// PERCENT
// ===========================

export function percent(value = 0) {
    return `${number(value)}%`;
}

// ===========================
// DATE
// ===========================

export function date(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleDateString("pt-BR");
}

// ===========================
// DATETIME
// ===========================

export function datetime(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString(
        "pt-BR",

        {
            dateStyle: "short",

            timeStyle: "short",
        },
    );
}
