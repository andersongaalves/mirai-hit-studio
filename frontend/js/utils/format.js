export function money(value) {
    return Number(value).toLocaleString(

        "pt-BR",

        {
            style: "currency",
            currency: "BRL"
        }

    );

}

export function number(value) {
    return Number(value).toLocaleString(
        "pt-BR"
    );

}

export function percent(value) {
    return `${value}%`;

}

export function date(value) {
    return new Date(value)
        .toLocaleDateString("pt-BR");

}