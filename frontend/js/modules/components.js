import { carregarComponente } from "../ui.js";
import { initPublicNavigation } from "../public_navigation.js";

export async function initComponents() {
    await carregarComponente("nav-placeholder", "components/nav.html");
    await carregarComponente("footer-placeholder", "components/footer.html");
    initPublicNavigation();
}
