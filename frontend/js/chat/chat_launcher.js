function positionLauncher(launcher) {
    const banner = document.getElementById("analytics-consent-dialog")
        || document.getElementById("analytics-preferences");
    const rect = banner?.getBoundingClientRect();
    const launcherRect = launcher.getBoundingClientRect();
    const sharesColumn = rect
        && rect.left < launcherRect.right
        && rect.right > launcherRect.left;
    launcher.style.bottom = `${sharesColumn ? Math.max(16, innerHeight - rect.top + 12) : 16}px`;
}

export function initSiteChatLauncher() {
    if (document.getElementById("site-chat-launcher")) return;

    const launcher = document.createElement("button");
    launcher.type = "button";
    launcher.id = "site-chat-launcher";
    launcher.className = "site-chat-launcher btn-small";
    launcher.textContent = "Assistente Mirai";
    launcher.setAttribute("aria-controls", "site-chat");
    launcher.setAttribute("aria-expanded", "false");
    launcher.setAttribute("aria-haspopup", "dialog");
    document.body.append(launcher);

    const resize = new ResizeObserver(() => positionLauncher(launcher));
    resize.observe(document.body);
    const consentChanges = new MutationObserver(() => positionLauncher(launcher));
    consentChanges.observe(document.body, { childList: true });
    const onResize = () => positionLauncher(launcher);
    window.addEventListener("resize", onResize);
    positionLauncher(launcher);

    let loading = false;
    launcher.addEventListener("click", async () => {
        if (loading) return;
        loading = true;
        launcher.disabled = true;
        launcher.textContent = "Abrindo chat...";
        try {
            const { initSiteChat } = await import("./chat.js");
            await initSiteChat({ open: true, replaceLauncher: launcher });
            resize.disconnect();
            consentChanges.disconnect();
            window.removeEventListener("resize", onResize);
        } catch {
            loading = false;
            launcher.disabled = false;
            launcher.textContent = "Tentar abrir o chat";
        }
    });
}
