// ===========================
// CONFIG
// ===========================

const TIME_VISIBLE = 3500;

const TIME_REMOVE = 3900;

const ICONS = {
    success: "✔",

    error: "✖",

    warning: "⚠",

    info: "ℹ",
};

// ===========================
// CONTAINER
// ===========================

function getContainer() {
    let container = document.querySelector(".notification-container");

    if (!container) {
        container = document.createElement("div");

        container.className = "notification-container";

        document.body.appendChild(container);
    }

    return container;
}

// ===========================
// CREATE
// ===========================

function notify(type, title, message) {
    const container = getContainer();

    const card = document.createElement("div");

    card.className = `notification ${type}`;

    const icon = document.createElement("div");

    icon.className = "notification-icon";

    icon.textContent = ICONS[type] || ICONS.info;

    const content = document.createElement("div");

    const titleElement = document.createElement("div");

    titleElement.className = "notification-title";

    titleElement.textContent = title;

    const messageElement = document.createElement("div");

    messageElement.className = "notification-message";

    messageElement.textContent = message;

    content.append(
        titleElement,

        messageElement,
    );

    card.append(
        icon,

        content,
    );

    container.appendChild(card);

    setTimeout(
        () => {
            card.classList.add("hide");
        },

        TIME_VISIBLE,
    );

    setTimeout(
        () => {
            card.remove();
        },

        TIME_REMOVE,
    );
}

// ===========================
// EXPORTS
// ===========================

export function success(message) {
    notify(
        "success",

        "Sucesso",

        message,
    );
}

export function warning(message) {
    notify(
        "warning",

        "Atenção",

        message,
    );
}

export function error(message) {
    notify(
        "error",

        "Erro",

        message,
    );
}

export function info(message) {
    notify(
        "info",

        "Info",

        message,
    );
}
