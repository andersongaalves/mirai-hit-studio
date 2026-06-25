import * as UI from "../ui.js";

export async function initComponents() {

    // Navbar
    await UI.carregarComponente(
        "nav-placeholder",
        "components/nav.html"
    );

    // Footer
    await UI.carregarComponente(
        "footer-placeholder",
        "components/footer.html"
    );

    // Efeitos visuais
    UI.initParticles();

}