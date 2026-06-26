import "./modules/globals.js";

import { initComponents } from "./modules/components.js";
import { $ } from "./utils/dom.js";

async function init() {

    await initComponents();

    if ($("btn-newsletter")) {

        const { initNewsletter } =
            await import("./modules/newsletter.js");

        initNewsletter();

    }

    if ($("home-portfolio-track")) {

        const { initHome } =
            await import("./modules/home.js");

        await initHome();

    }

    if ($("render-portfolio")) {

        const { initPortfolioPage } =
            await import("./modules/portfolio.js");

        await initPortfolioPage();

    }

    if ($("render-parametros")) {

        const {

            initEventosCalculadora

        } = await import("./modules/calculator.js");

        const {

            initOrcamento

        } = await import("./modules/orcamento.js");

        await initEventosCalculadora();

        initOrcamento();

    }

}

init();