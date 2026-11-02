// Double confirmation for deletions, irreversible actions and submissions that go to
// review without a chance to edit: the dialog explains what happens and the button only
// unlocks after the person types the confirmation word (and the reason, when asked).
// Resolves to false when cancelled, or to { motivo } when confirmed.

const FOCUSABLE = "button:not([disabled]), input:not([disabled]), textarea:not([disabled]), a[href]";
let open = null;

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

const normalize = value => String(value || "").trim().toLocaleUpperCase("pt-BR")
    .normalize("NFD").replace(/[̀-ͯ]/g, "");

export function confirmarAcao({
    titulo,
    mensagem = "",
    consequencias = [],
    palavra = "EXCLUIR",
    botao = "Excluir",
    tom = "perigo",
    motivo = null,
} = {}) {
    if (open) open.cancel();
    return new Promise(resolve => {
        const previous = document.activeElement;
        const overlay = el("div", "confirm-dialog-overlay");
        const dialog = el("div", `confirm-dialog confirm-dialog--${tom}`);
        const id = `confirm-dialog-${Date.now().toString(36)}`;
        dialog.setAttribute("role", "alertdialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", `${id}-title`);
        dialog.setAttribute("aria-describedby", `${id}-body`);

        const heading = el("h2", "confirm-dialog__title", titulo || "Confirmar ação");
        heading.id = `${id}-title`;
        const body = el("div", "confirm-dialog__body");
        body.id = `${id}-body`;
        if (mensagem) body.append(el("p", "confirm-dialog__message", mensagem));
        const items = (consequencias || []).filter(Boolean);
        if (items.length) {
            const list = el("ul", "confirm-dialog__list");
            items.forEach(text => list.append(el("li", "", text)));
            body.append(list);
        }

        const form = el("form", "confirm-dialog__form");
        form.noValidate = true;
        let reason = null;
        if (motivo) {
            const field = el("label", "confirm-dialog__field");
            field.append(el("span", "", motivo.rotulo || "Motivo (fica no histórico)"));
            reason = document.createElement("textarea");
            reason.rows = 2;
            reason.maxLength = motivo.maximo || 300;
            reason.name = "motivo";
            reason.value = motivo.valor || "";
            field.append(reason);
            form.append(field);
        }
        const typed = el("label", "confirm-dialog__field");
        const hint = el("span");
        hint.append("Para confirmar, digite ", el("strong", "", palavra));
        typed.append(hint);
        const input = document.createElement("input");
        input.type = "text";
        input.name = "confirmacao";
        input.autocomplete = "off";
        input.spellcheck = false;
        input.setAttribute("autocapitalize", "characters");
        input.setAttribute("aria-label", `Digite ${palavra} para confirmar`);
        typed.append(input);
        form.append(typed);

        const actions = el("div", "confirm-dialog__actions");
        const cancel = el("button", "btn-small", "Cancelar");
        cancel.type = "button";
        const confirm = el("button", "btn-small confirm-dialog__confirm", botao);
        confirm.type = "submit";
        confirm.disabled = true;
        actions.append(cancel, confirm);
        form.append(actions);

        dialog.append(heading, body, form);
        overlay.append(dialog);

        const minimum = motivo ? (motivo.minimo ?? 3) : 0;
        const ready = () => normalize(input.value) === normalize(palavra)
            && (!reason || reason.value.trim().length >= minimum);
        const update = () => { confirm.disabled = !ready(); };
        input.addEventListener("input", update);
        reason?.addEventListener("input", update);

        const finish = value => {
            if (open?.overlay !== overlay) return;
            open = null;
            document.removeEventListener("keydown", onKey, true);
            overlay.remove();
            document.body.classList.remove("confirm-dialog-open");
            if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
            resolve(value);
        };
        const onKey = event => {
            if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                finish(false);
            } else if (event.key === "Tab") {
                const focusable = [...dialog.querySelectorAll(FOCUSABLE)];
                if (!focusable.length) return;
                const first = focusable[0];
                const last = focusable.at(-1);
                if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
                else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
            }
        };
        cancel.addEventListener("click", () => finish(false));
        overlay.addEventListener("mousedown", event => { if (event.target === overlay) finish(false); });
        form.addEventListener("submit", event => {
            event.preventDefault();
            if (!ready()) return;
            finish({ motivo: reason ? reason.value.trim() : "" });
        });

        open = { overlay, cancel: () => finish(false) };
        document.addEventListener("keydown", onKey, true);
        document.body.classList.add("confirm-dialog-open");
        document.body.append(overlay);
        (reason || input).focus();
    });
}
