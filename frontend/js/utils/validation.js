export function required(value) {
    return value.trim() !== "";
}

export function email(email) {
    return /\S+@\S+\.\S+/.test(email);
}