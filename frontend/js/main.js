import "./modules/globals.js";

import { initComponents } from "./modules/components.js";
import { initHome } from "./modules/home.js";
import { initPortfolioPage } from "./modules/portfolio.js";
import { initEventosCalculadora } from "./modules/calculator.js";
import { initNewsletter } from "./modules/newsletter.js";
import { initOrcamento } from "./modules/orcamento.js";

import { $ } from "./utils/dom.js";

async function init() {

    // Navbar + Footer + Partículas
    await initComponents();

    // Newsletter (Footer)
    initNewsletter();

    // Home
    await initHome();

    // Página de Portfólio
    if ($("render-portfolio")) {

        await initPortfolioPage();

    }

    // Página da Calculadora
    if ($("render-parametros")) {

        await initEventosCalculadora();

        initOrcamento();

    }

}

init();