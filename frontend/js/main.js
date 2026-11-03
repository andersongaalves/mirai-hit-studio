import "./modules/globals.js";

import { initComponents } from "./modules/components.js";
import { initAnalytics } from "./analytics.js";
import { registrarOrigem } from "./modules/origem.js";
import { initSiteChatLauncher } from "./chat/chat_launcher.js";
import { inAdminPreview } from "./modules/preview_frame.js";

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
        await initComponents();
        // Pages shown in the Admin's preview are not visits: no origin, analytics or chat.
        const preview = inAdminPreview();
        if (!preview) {
            registrarOrigem();
            initAnalytics();
        }

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

            "./modules/portfolio.js?v=20261017-portfolio-creditos",

            (module) => module.initPortfolioPage(),
        );

        await loadModule(
            "beats-public",

            "./modules/beats_public.js",

            (module) => module.initBeatsPage(),
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
if (!inAdminPreview()) initSiteChatLauncher();
