// Answers the site's double-confirmation dialog (js/modules/confirm_dialog.js) the way
// page.once('dialog', ...) used to answer window.confirm/prompt: an in-page watcher fills
// the reason, types the confirmation word and submits (or cancels). armConfirm answers
// the next dialog only; autoConfirm answers every dialog on this page from now on.
// window.__confirmLog keeps the text of each dialog answered, for assertions.

function watcher() {
    if (window.__confirmWatcher) return;
    window.__confirmWatcher = true;
    window.__confirmQueue = window.__confirmQueue || [];
    window.__confirmLog = window.__confirmLog || [];
    const answer = dialog => {
        if (dialog.dataset.answered) return;
        const choice = window.__confirmQueue.length ? window.__confirmQueue.shift() : window.__confirmAuto;
        if (!choice) return;
        dialog.dataset.answered = "1";
        window.__confirmLog.push(dialog.textContent);
        const cancel = [...dialog.querySelectorAll("button")].find(button => button.textContent === "Cancelar");
        if (choice.accept === false) { cancel.click(); return; }
        const set = (field, value) => {
            if (!field) return;
            field.value = value;
            field.dispatchEvent(new Event("input", { bubbles: true }));
        };
        set(dialog.querySelector("textarea[name=motivo]"), choice.motivo ?? "Motivo de teste");
        set(dialog.querySelector("input[name=confirmacao]"), dialog.querySelector(".confirm-dialog__field strong")?.textContent || "");
        dialog.querySelector("form").requestSubmit();
    };
    const scan = () => document.querySelectorAll(".confirm-dialog").forEach(answer);
    new MutationObserver(scan).observe(document, { childList: true, subtree: true });
    scan();
}

async function armConfirm(page, choice = {}) {
    await page.evaluate(watcher);
    await page.evaluate(value => window.__confirmQueue.push(value), { accept: true, ...choice });
}

async function autoConfirm(page, choice = {}) {
    const value = { accept: true, ...choice };
    await page.addInitScript(auto => { window.__confirmAuto = auto; }, value);
    await page.addInitScript(watcher);
    if (page.url() && page.url() !== "about:blank") {
        await page.evaluate(auto => { window.__confirmAuto = auto; }, value).catch(() => undefined);
        await page.evaluate(watcher).catch(() => undefined);
    }
}

module.exports = { armConfirm, autoConfirm };
