function selectTab(tabs, selected, focus = false) {
    tabs.forEach(tab => {
        const active = tab === selected;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !active;
    });
    if (focus) selected.focus();
}

document.querySelectorAll("[data-admin-tabs], .integrado-admin__config-tabs").forEach(tablist => {
    const tabs = [...tablist.querySelectorAll(":scope > [role='tab']")];
    tabs.forEach((tab, index) => {
        tab.addEventListener("click", () => selectTab(tabs, tab));
        tab.addEventListener("keydown", event => {
            const next = event.key === "ArrowRight" ? (index + 1) % tabs.length
                : event.key === "ArrowLeft" ? (index - 1 + tabs.length) % tabs.length
                    : event.key === "Home" ? 0
                        : event.key === "End" ? tabs.length - 1 : -1;
            if (next < 0) return;
            event.preventDefault();
            selectTab(tabs, tabs[next], true);
        });
    });
    if (tabs.length) selectTab(tabs, tabs.find(tab => tab.getAttribute("aria-selected") === "true") || tabs[0]);
});
