import * as API from "../api.js";
import * as Notify from "../utils/notifications.js";
import * as Validation from "../utils/validation.js";
import { $ } from "../utils/dom.js";
import { track } from "../analytics.js";

export function initNewsletter() {
    const form = $("newsletter-form");

    if (!form) return;

    form.addEventListener(
        "submit",

        async (event) => {
            event.preventDefault();

            const inputEmail = $("newsletter-email");

            if (!inputEmail) {
                console.error("Campo newsletter-email não encontrado.");
                return;
            }

            const email = inputEmail.value.trim().toLowerCase();

            if (!Validation.required(email)) {
                Notify.warning("Digite seu e-mail.");

                inputEmail.focus();
                return;
            }

            try {
                const button = $("btn-newsletter");
                if (button?.disabled) return;
                if (button) button.disabled = true;
                await API.postNewsletter({
                    email,
                    source: "site_footer",
                });

                track("newsletter_subscribe");
                Notify.success("Inscrição realizada com sucesso!");
                inputEmail.value = "";
            } catch (error) {
                console.error(error);

                Notify.error("Não foi possível concluir a inscrição.");
            } finally {
                const button = $("btn-newsletter");
                if (button) button.disabled = false;
            }
        },
    );
}
