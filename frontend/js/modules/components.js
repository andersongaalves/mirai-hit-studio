import { carregarComponente } from "../ui.js";
import { initPublicNavigation } from "../public_navigation.js";

export async function initComponents() {
    // Navbar
    await carregarComponente("nav-placeholder", "components/nav.html");
    initPublicNavigation();

    // Footer
    await carregarComponente("footer-placeholder", "components/footer.html");
}
