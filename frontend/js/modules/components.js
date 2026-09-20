import * as UI from "../ui.js";
import { initPublicNavigation } from "../public_navigation.js";

export async function initComponents() {
    // Navbar
    await UI.carregarComponente("nav-placeholder", "components/nav.html");
    initPublicNavigation();

    // Footer
    await UI.carregarComponente("footer-placeholder", "components/footer.html");

    // Efeitos visuais
    UI.initParticles();
}
