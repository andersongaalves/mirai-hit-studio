let styled = false;
export function uploadBusy(button, text = "Enviando...") {
    if (!styled) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = "/css/components/upload-feedback.css";
        document.head.append(link);
        styled = true;
    }
    const original = button.textContent;
    const disabled = button.disabled;
    const form = button.closest("form");
    button.disabled = true;
    button.textContent = text;
    button.classList.add("upload-busy");
    button.setAttribute("aria-busy", "true");
    form?.setAttribute("aria-busy", "true");
    return () => {
        button.textContent = original;
        button.disabled = disabled;
        button.classList.remove("upload-busy");
        button.removeAttribute("aria-busy");
        form?.removeAttribute("aria-busy");
    };
}
