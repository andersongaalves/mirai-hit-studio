import { carregarComponente } from "../ui.js";
import { initPublicNavigation } from "../public_navigation.js";
import { initPublicVerticals } from "./public_verticals.js";

export async function initComponents() {
    await carregarComponente("nav-placeholder", "/components/nav.html");
    await carregarComponente("footer-placeholder", "/components/footer.html");
    initPublicNavigation();
    // Not awaited: the page renders while the published areas are checked.
    initPublicVerticals();
}
