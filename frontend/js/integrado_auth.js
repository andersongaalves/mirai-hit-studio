document.querySelectorAll("[data-password-toggle]").forEach(button => {
    const input = document.getElementById(button.dataset.passwordToggle);
    if (!input || input.type !== "password") return;
    const label = button.querySelector("span");
    const hiddenLabel = label?.textContent || button.textContent;
    const visibleLabel = hiddenLabel.replace(/^Mostrar/, "Ocultar");
    button.addEventListener("click", () => {
        const visible = input.type === "password";
        input.type = visible ? "text" : "password";
        button.setAttribute("aria-pressed", String(visible));
        if (label) label.textContent = visible ? visibleLabel : hiddenLabel;
        else button.textContent = visible ? visibleLabel : hiddenLabel;
        input.focus();
    });
});
