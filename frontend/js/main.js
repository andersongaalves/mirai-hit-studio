import "./modules/globals.js";

import { initComponents } from "./modules/components.js";
import { initAnalytics } from "./analytics.js";

import {$} from "./utils/dom.js";

// ===========================
// LOAD MODULE
// ===========================

async function loadModule(elementId, path, callback) {
    if (!$(elementId)) {
        return;
    }

    const module = await import(path);

    await callback(module);
}

// ===========================
// INIT
// ===========================

async function initApp() {
    try {
        initAnalytics();
        await initComponents();

        await loadModule(
            "btn-newsletter",

            "./modules/newsletter.js",

            (module) => module.initNewsletter(),
        );

        await loadModule(
            "home-portfolio-track",

            "./modules/home.js",

            (module) => module.initHome(),
        );

        await loadModule(
            "render-portfolio",

            "./modules/portfolio.js",

            (module) => module.initPortfolioPage(),
        );

        await loadModule(
            "render-parametros",

            "./modules/calculator.js",

            (module) => module.initEventosCalculadora(),
        );

        await loadModule(
            "render-parametros",

            "./modules/orcamento.js",

            (module) => module.initOrcamento(),
        );
    } catch (error) {
        console.error("Erro ao iniciar aplicação:", error);
    }
}

// ===========================
// START
// ===========================

initApp();
