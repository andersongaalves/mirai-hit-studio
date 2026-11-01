// AUD6-S08-003: Portuguese file picker instead of the browser's own ("Choose File").
// Wraps each native file input in the shared picker; the input stays the real control.
export function enhanceFilePickers(root) {
    if (!root) return;
    root.querySelectorAll('input[type="file"]:not([data-picker])').forEach(input => {
        input.dataset.picker = "";
        if (input.closest(".producer-upload__picker")) return; // already a custom picker
        const picker = document.createElement("span");
        picker.className = "producer-upload__picker";
        const button = document.createElement("span");
        button.className = "producer-upload__pick-button";
        button.textContent = "Escolher arquivo";
        button.setAttribute("aria-hidden", "true");
        const name = document.createElement("span");
        name.className = "producer-upload__filename";
        const empty = "Nenhum arquivo selecionado";
        const sync = () => {
            const files = [...(input.files || [])];
            name.textContent = files.length ? files.map(file => file.name).join(", ") : empty;
            name.title = name.textContent;
        };
        input.before(picker);
        picker.append(input, button, name);
        input.addEventListener("change", sync);
        input.form?.addEventListener("reset", () => setTimeout(sync));
        sync();
    });
}

// Keeps pickers on inputs that portal modules render later (tag, portfolio, deliveries).
export function watchFilePickers(root) {
    if (!root) return;
    enhanceFilePickers(root);
    new MutationObserver(records => {
        if (records.some(record => record.addedNodes.length)) enhanceFilePickers(root);
    }).observe(root, { childList: true, subtree: true });
}
